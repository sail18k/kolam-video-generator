"""
Reference-Guided Stroke Correction and Path Alignment Engine
Headless Kolam Video Generator V2

Aligns human-drawn vector strokes to uploaded reference Kolam/Rangoli images:
- Human drawing determines WHAT to draw and the ORDER/DIRECTION to draw it.
- The reference image determines WHERE the corrected strokes should go.
- Preserves stroke order, stroke direction, endpoints, and pen-up transitions.
- Supports conservative, confidence-weighted geometric correction.
"""

import os
import math
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

import numpy as np
import cv2
from scipy.spatial import cKDTree

logger = logging.getLogger("kolam.reference_alignment")


@dataclass
class CorrectionConfig:
    """Configurable parameters for reference-guided stroke correction."""
    max_matching_distance: float = 65.0      # Maximum distance in canvas px to consider a match
    high_confidence_threshold: float = 0.65  # Threshold above which full reference geometry is applied
    low_confidence_threshold: float = 0.35   # Threshold below which original human stroke is retained
    orientation_weight: float = 35.0         # Penalty weight for orientation discrepancy
    step_weight: float = 2.0                 # Penalty weight for sudden step size jumps
    enable_smoothing: bool = True            # Apply gentle smoothing to eliminate pixel discretization jitter
    smoothing_window: int = 5                # Window size for local moving average smoothing
    resample_step_size: float = 4.0          # Dense point step size (matches renderer expectation)
    max_gap_recovery_distance: float = 20.0  # Max gap in px to bridge closed loops
    enable_gap_recovery: bool = True         # Allow closing tiny gaps in closed contours


class ReferencePath:
    """Represents an ordered continuous polyline/curve extracted from the reference image."""

    def __init__(self, points: np.ndarray, is_closed: bool = False, path_id: int = 0):
        # points shape: (M, 2) in (x, y) float32 coordinates
        self.points = np.ascontiguousarray(points, dtype=np.float32)
        self.is_closed = bool(is_closed)
        self.id = int(path_id)
        self.length = float(self._compute_length())
        self.tangents = self._compute_tangents()
        self.tree = cKDTree(self.points)

    def _compute_length(self) -> float:
        if len(self.points) < 2:
            return 0.0
        diffs = self.points[1:] - self.points[:-1]
        return float(np.sum(np.linalg.norm(diffs, axis=1)))

    def _compute_tangents(self) -> np.ndarray:
        n = len(self.points)
        if n < 2:
            return np.zeros((n, 2), dtype=np.float32)
        tangents = np.zeros((n, 2), dtype=np.float32)
        if self.is_closed and n >= 3:
            # Central difference with loop wrap
            tangents[0] = self.points[1] - self.points[-1]
            tangents[1:-1] = self.points[2:] - self.points[:-2]
            tangents[-1] = self.points[0] - self.points[-2]
        else:
            tangents[0] = self.points[1] - self.points[0]
            if n > 2:
                tangents[1:-1] = self.points[2:] - self.points[:-2]
            tangents[-1] = self.points[-1] - self.points[-2]

        norms = np.linalg.norm(tangents, axis=1, keepdims=True)
        return tangents / np.maximum(1e-6, norms)

    def query(self, pts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Queries nearest distances and indices on this path for given points."""
        return self.tree.query(pts)


@dataclass
class ReferenceGeometry:
    """Preprocessed reference image data and extracted centerline geometric structures."""
    original_image: Optional[np.ndarray]     # Raw uploaded image (BGR)
    fitted_image: np.ndarray                 # 1080x1920 canvas image with aspect-ratio fitting
    binary_mask: np.ndarray                  # 1080x1920 binary mask of drawing lines (uint8, 0/255)
    skeleton: np.ndarray                     # 1080x1920 1-pixel centerline skeleton (uint8, 0/255)
    distance_map: np.ndarray                 # 1080x1920 distance transform to skeleton (float32)
    orientation_map: np.ndarray              # 1080x1920 line orientation angle in radians [0, pi)
    paths: List[ReferencePath] = field(default_factory=list)
    skel_points: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), dtype=np.float32))
    skel_tree: Optional[cKDTree] = None
    image_roi: Tuple[int, int, int, int] = (0, 0, 1080, 1920) # (pad_x, pad_y, w, h)
    scale: float = 1.0


def morph_thinning_opencv(binary_mask: np.ndarray) -> np.ndarray:
    """
    Computes a true 1-pixel wide skeleton using morphological hit-or-miss with Golay structuring elements.
    High performance, deterministic, and preserves 8-connectivity and line topology.
    """
    coords = cv2.findNonZero(binary_mask)
    if coords is None:
        return np.zeros_like(binary_mask)

    thinned = binary_mask.copy()
    x, y, w, h = cv2.boundingRect(coords)
    x0, y0 = max(0, x - 2), max(0, y - 2)
    x1, y1 = min(binary_mask.shape[1], x + w + 2), min(binary_mask.shape[0], y + h + 2)
    roi = thinned[y0:y1, x0:x1]

    # 8 Golay structuring elements for thinning
    k1 = np.array([[-1, -1, -1], [ 0,  1,  0], [ 1,  1,  1]], dtype=np.int8)
    kernels = [np.rot90(k1, i) for i in range(4)]
    k2 = np.array([[ 0, -1, -1], [ 1,  1, -1], [ 0,  1,  0]], dtype=np.int8)
    kernels += [np.rot90(k2, i) for i in range(4)]

    for _ in range(60):
        prev = roi.copy()
        for kernel in kernels:
            hit = cv2.morphologyEx(roi, cv2.MORPH_HITMISS, kernel)
            roi = cv2.subtract(roi, hit)
        if np.array_equal(roi, prev):
            break

    thinned[y0:y1, x0:x1] = roi
    return thinned


def build_reference_distance_map(skeleton: np.ndarray) -> np.ndarray:
    """Computes exact Euclidean distance transform from every pixel to the nearest skeleton centerline."""
    if cv2.countNonZero(skeleton) == 0:
        return np.full(skeleton.shape, 9999.0, dtype=np.float32)
    inverted = cv2.bitwise_not(skeleton)
    return cv2.distanceTransform(inverted, cv2.DIST_L2, 5)


def build_orientation_map(skeleton: np.ndarray, binary_mask: np.ndarray) -> np.ndarray:
    """
    Computes local tangent orientation angles [0, pi) across the image using the structure tensor.
    Angles represent the direction of drawing lines (perpendicular to gradient).
    """
    smooth = cv2.GaussianBlur(binary_mask.astype(np.float32) / 255.0, (5, 5), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    
    jxx = cv2.GaussianBlur(gx * gx, (5, 5), 1.0)
    jyy = cv2.GaussianBlur(gy * gy, (5, 5), 1.0)
    jxy = cv2.GaussianBlur(gx * gy, (5, 5), 1.0)
    
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy) + (np.pi / 2.0)
    return (theta % np.pi).astype(np.float32)


def extract_skeleton_paths(skeleton: np.ndarray) -> List[ReferencePath]:
    """
    Decomposes the skeleton raster into ordered, continuous, non-branching ReferencePath polylines.
    Identifies endpoints and junctions to segment branches, and traces closed loops cleanly.
    """
    if cv2.countNonZero(skeleton) == 0:
        return []

    skel_bin = (skeleton > 0).astype(np.uint8)
    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    h, w = skeleton.shape
    neighbor_count = np.zeros_like(skel_bin, dtype=np.uint8)

    def is_linked(y: int, x: int, dy: int, dx: int) -> bool:
        ny, nx = y + dy, x + dx
        if not (0 <= ny < h and 0 <= nx < w and skel_bin[ny, nx]):
            return False
        # Suppress a diagonal shortcut when an orthogonal pixel already connects
        # the same local pixels. This prevents ordinary one-pixel curves from
        # being mistaken for dense junctions under 8-neighbor counting.
        if dy and dx and (skel_bin[y + dy, x] or skel_bin[y, x + dx]):
            return False
        return True

    for sy, sx in np.column_stack(np.where(skel_bin)):
        neighbor_count[sy, sx] = sum(1 for dy, dx in offsets if is_linked(int(sy), int(sx), dy, dx))

    visited = np.zeros_like(skel_bin, dtype=bool)
    paths: List[ReferencePath] = []
    path_id = 1

    # 1. Trace branches starting from endpoints (degree 1) or junctions (degree > 2)
    seeds = np.column_stack(np.where((neighbor_count == 1) | (neighbor_count > 2)))

    for sy, sx in seeds:
        for dy, dx in offsets:
            ny, nx = sy + dy, sx + dx
            if is_linked(int(sy), int(sx), dy, dx) and not visited[ny, nx]:
                path = [(float(sx), float(sy))]
                cy, cx = ny, nx
                while True:
                    path.append((float(cx), float(cy)))
                    visited[cy, cx] = True
                    if neighbor_count[cy, cx] != 2:
                        break
                    
                    next_pt = None
                    for ddy, ddx in offsets:
                        nny, nnx = cy + ddy, cx + ddx
                        if is_linked(cy, cx, ddy, ddx) and not visited[nny, nnx]:
                            next_pt = (nnx, nny)
                            break
                    if next_pt is None:
                        break
                    cx, cy = next_pt

                if len(path) >= 4:
                    pts_arr = np.array(path, dtype=np.float32)
                    paths.append(ReferencePath(pts_arr, is_closed=False, path_id=path_id))
                    path_id += 1

    # 2. Trace closed loops where neighbor_count == 2 everywhere (e.g. concentric circles/petals)
    unvisited = np.column_stack(np.where(skel_bin & (~visited)))
    for sy, sx in unvisited:
        if visited[sy, sx]:
            continue
        path = [(float(sx), float(sy))]
        visited[sy, sx] = True
        cy, cx = sy, sx
        while True:
            next_pt = None
            for dy, dx in offsets:
                ny, nx = cy + dy, cx + dx
                if is_linked(cy, cx, dy, dx) and not visited[ny, nx]:
                    next_pt = (nx, ny)
                    break
            if next_pt is None:
                break
            cx, cy = next_pt
            path.append((float(cx), float(cy)))
            visited[cy, cx] = True

        if len(path) >= 5:
            pts_arr = np.array(path, dtype=np.float32)
            paths.append(ReferencePath(pts_arr, is_closed=True, path_id=path_id))
            path_id += 1

    return paths


def preprocess_reference_image(
    image_input: Union[str, Path, np.ndarray],
    target_width: int = 1080,
    target_height: int = 1920
) -> ReferenceGeometry:
    """
    Loads, aspect-ratio normalizes (matching CSS object-fit: contain), and extracts
    centerline geometry and distance transforms from the reference image.
    Supports grayscale, RGB, RGBA, photo, and color Rangoli inputs.
    """
    orig_bgr: Optional[np.ndarray] = None

    if isinstance(image_input, (str, Path)):
        p = Path(image_input)
        if not p.exists():
            raise FileNotFoundError(f"Reference image not found at path: {p}")
        raw = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if raw is None:
            raise ValueError(f"OpenCV could not decode reference image: {p}")
    elif isinstance(image_input, np.ndarray):
        raw = image_input.copy()
    else:
        raise TypeError(f"Unsupported image_input type: {type(image_input)}")

    # Handle image color channels
    if len(raw.shape) == 2:
        orig_bgr = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
    elif len(raw.shape) == 3 and raw.shape[2] == 4:
        # RGBA: composite over white background
        alpha = raw[:, :, 3].astype(np.float32) / 255.0
        rgb = raw[:, :, :3].astype(np.float32)
        white_bg = np.full_like(rgb, 255.0)
        blended = rgb * alpha[:, :, np.newaxis] + white_bg * (1.0 - alpha[:, :, np.newaxis])
        orig_bgr = np.clip(blended, 0, 255).astype(np.uint8)
    elif len(raw.shape) == 3 and raw.shape[2] == 3:
        orig_bgr = raw.copy()
    else:
        raise ValueError(f"Invalid image array shape: {raw.shape}")

    orig_h, orig_w = orig_bgr.shape[:2]
    if orig_h == 0 or orig_w == 0:
        raise ValueError("Reference image has zero width or height.")

    # 1. Aspect-Ratio Fitting (CSS object-fit: contain into 1080x1920)
    scale = min(target_width / float(orig_w), target_height / float(orig_h))
    new_w = max(1, int(round(orig_w * scale)))
    new_h = max(1, int(round(orig_h * scale)))

    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(orig_bgr, (new_w, new_h), interpolation=interp)

    pad_x = (target_width - new_w) // 2
    pad_y = (target_height - new_h) // 2

    # Estimate background polarity inside the image ROI
    gray_roi = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    mean_val = float(np.mean(gray_roi))
    is_light_bg = mean_val > 120.0

    canvas_bg_color = (255, 255, 255) if is_light_bg else (0, 0, 0)
    fitted_bgr = np.full((target_height, target_width, 3), canvas_bg_color, dtype=np.uint8)
    fitted_bgr[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    # 2. Extract Line Structures
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced_roi = clahe.apply(gray_roi)

    # Adaptive Thresholding & Otsu
    block_size = max(15, (min(new_w, new_h) // 30) * 2 + 1)
    if is_light_bg:
        thresh_adapt = cv2.adaptiveThreshold(
            enhanced_roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block_size, 8
        )
        _, thresh_otsu = cv2.threshold(enhanced_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        thresh_adapt = cv2.adaptiveThreshold(
            enhanced_roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, 8
        )
        _, thresh_otsu = cv2.threshold(enhanced_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    blurred_roi = cv2.GaussianBlur(gray_roi, (5, 5), 1.0)
    edges = cv2.Canny(blurred_roi, 40, 120)

    combined_roi = cv2.bitwise_or(thresh_adapt, thresh_otsu)
    combined_roi = cv2.bitwise_or(combined_roi, edges)

    # Noise reduction: remove speckles and close tiny gaps
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    clean_roi = cv2.morphologyEx(combined_roi, cv2.MORPH_OPEN, kernel_open)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    clean_roi = cv2.morphologyEx(clean_roi, cv2.MORPH_CLOSE, kernel_close)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(clean_roi, connectivity=8)
    mask_roi = np.zeros_like(clean_roi)
    for lbl in range(1, num_labels):
        if stats[lbl, cv2.CC_STAT_AREA] >= 15:
            mask_roi[labels == lbl] = 255

    binary_mask = np.zeros((target_height, target_width), dtype=np.uint8)
    binary_mask[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = mask_roi

    # 3. Centerline Skeletonization via Golay hit-or-miss thinning
    skeleton = morph_thinning_opencv(binary_mask)
    distance_map = build_reference_distance_map(skeleton)
    orientation_map = build_orientation_map(skeleton, binary_mask)

    # 4. Extract continuous paths
    paths = extract_skeleton_paths(skeleton)

    # 5. Build global skeleton KDTree
    skel_coords = np.column_stack(np.where(skeleton > 0)) # (row, col) = (y, x)
    if len(skel_coords) > 0:
        skel_points = np.fliplr(skel_coords).astype(np.float32) # (x, y)
        skel_tree = cKDTree(skel_points)
    else:
        skel_points = np.zeros((0, 2), dtype=np.float32)
        skel_tree = None

    return ReferenceGeometry(
        original_image=orig_bgr,
        fitted_image=fitted_bgr,
        binary_mask=binary_mask,
        skeleton=skeleton,
        distance_map=distance_map,
        orientation_map=orientation_map,
        paths=paths,
        skel_points=skel_points,
        skel_tree=skel_tree,
        image_roi=(pad_x, pad_y, new_w, new_h),
        scale=scale
    )


def match_stroke_to_reference(
    stroke_points: np.ndarray,
    ref_geom: ReferenceGeometry,
    max_match_dist: float = 65.0
) -> Tuple[Optional[ReferencePath], float, Dict[str, Any]]:
    """
    Matches a sequence of human points to the candidate reference paths.
    Considers proximity, orientation consistency, and endpoint correspondence.
    Returns: (best_path, confidence, diagnostics_info)
    """
    n_pts = len(stroke_points)
    if n_pts < 2 or ref_geom.skel_tree is None or len(ref_geom.skel_points) == 0:
        return None, 0.0, {"reason": "empty_reference_or_stroke"}

    dists_skel, _ = ref_geom.skel_tree.query(stroke_points)
    median_dist = float(np.median(dists_skel))
    mean_dist = float(np.mean(dists_skel))
    in_range_ratio = float(np.mean(dists_skel <= max_match_dist))

    # Compute human tangents
    human_tangents = np.zeros((n_pts, 2), dtype=np.float32)
    human_tangents[0] = stroke_points[1] - stroke_points[0]
    if n_pts > 2:
        human_tangents[1:-1] = stroke_points[2:] - stroke_points[:-2]
    human_tangents[-1] = stroke_points[-1] - stroke_points[-2]
    h_norms = np.linalg.norm(human_tangents, axis=1, keepdims=True)
    human_tangents = human_tangents / np.maximum(1e-6, h_norms)

    diag: Dict[str, Any] = {
        "median_dist": median_dist,
        "mean_dist": mean_dist,
        "in_range_ratio": in_range_ratio,
        "candidates_evaluated": 0,
        "best_path_id": None
    }

    if median_dist > max_match_dist or in_range_ratio < 0.35:
        confidence = max(0.0, 1.0 - (median_dist / (max_match_dist * 2.0))) * in_range_ratio
        return None, float(confidence), diag

    # Score each reference path candidate
    best_score = float("inf")
    best_path: Optional[ReferencePath] = None
    best_path_dists: Optional[np.ndarray] = None
    best_path_idxs: Optional[np.ndarray] = None
    best_ori_score = 0.0
    best_coverage = 0.0

    for path in ref_geom.paths:
        if path.length < 15.0:
            continue
        diag["candidates_evaluated"] += 1
        dists, idxs = path.query(stroke_points)
        path_med_d = float(np.median(dists))
        if path_med_d > max_match_dist * 1.5:
            continue

        ref_t = path.tangents[idxs]
        dots = np.abs(np.sum(human_tangents * ref_t, axis=1))
        ori_score = float(np.mean(dots))
        coverage = float(np.mean(dists <= max_match_dist))
        if coverage < 0.30:
            continue

        score = path_med_d * (1.8 - 0.8 * ori_score) * (1.2 - 0.2 * coverage)
        if score < best_score:
            best_score = score
            best_path = path
            best_path_dists = dists
            best_path_idxs = idxs
            best_ori_score = ori_score
            best_coverage = coverage

    if best_path is None or best_path_dists is None or best_path_idxs is None:
        confidence = float(np.clip(1.0 - (median_dist / max_match_dist), 0.0, 0.49))
        return None, confidence, diag

    best_med_d = float(np.median(best_path_dists))
    dist_conf = max(0.0, 1.0 - (best_med_d / max_match_dist))
    confidence = float(np.clip(dist_conf * (0.3 + 0.7 * best_ori_score) * (0.5 + 0.5 * best_coverage), 0.0, 1.0))

    diag["best_path_id"] = best_path.id
    diag["best_score"] = float(best_score)
    diag["best_med_dist"] = best_med_d
    diag["best_ori_score"] = best_ori_score
    diag["best_coverage"] = best_coverage
    diag["confidence"] = confidence

    return best_path, confidence, diag


def viterbi_align_to_skeleton(
    human_pts: np.ndarray,
    ref_geom: ReferenceGeometry,
    config: CorrectionConfig
) -> np.ndarray:
    """
    Performs orientation-aware, continuity-penalized Viterbi dynamic programming map-matching
    across all skeleton points. Handles complex strokes that cross intersections or multi-branch junctions.
    """
    n_pts = len(human_pts)
    if n_pts < 2 or ref_geom.skel_tree is None or len(ref_geom.skel_points) == 0:
        return human_pts.copy()

    # Local human tangents
    human_tangents = np.zeros((n_pts, 2), dtype=np.float32)
    human_tangents[:-1] = human_pts[1:] - human_pts[:-1]
    human_tangents[-1] = human_tangents[-2] if n_pts > 1 else np.array([1.0, 0.0])
    h_norms = np.linalg.norm(human_tangents, axis=1, keepdims=True)
    human_tangents /= np.maximum(1e-6, h_norms)

    # Query K candidate skeleton points per stroke point
    K = min(10, len(ref_geom.skel_points))
    dists, indices = ref_geom.skel_tree.query(human_pts, k=K)

    dp = np.zeros((n_pts, K), dtype=np.float64)
    parent = np.zeros((n_pts, K), dtype=int)

    theta_map = ref_geom.orientation_map
    h_img, w_img = theta_map.shape

    # Emission for initial point
    for c in range(K):
        p_c = ref_geom.skel_points[indices[0, c]]
        px, py = int(round(np.clip(p_c[0], 0, w_img - 1))), int(round(np.clip(p_c[1], 0, h_img - 1)))
        th = theta_map[py, px]
        ref_t = np.array([np.cos(th), np.sin(th)])
        ori_diff = 1.0 - abs(float(np.dot(human_tangents[0], ref_t)))
        dp[0, c] = dists[0, c] + ori_diff * config.orientation_weight

    # Forward DP
    for i in range(1, n_pts):
        prev_pts = ref_geom.skel_points[indices[i - 1]]
        curr_pts = ref_geom.skel_points[indices[i]]
        delta_p = human_pts[i] - human_pts[i - 1]

        for c in range(K):
            p_c = curr_pts[c]
            px, py = int(round(np.clip(p_c[0], 0, w_img - 1))), int(round(np.clip(p_c[1], 0, h_img - 1)))
            th = theta_map[py, px]
            ref_t = np.array([np.cos(th), np.sin(th)])
            ori_diff = 1.0 - abs(float(np.dot(human_tangents[i], ref_t)))
            emission = dists[i, c] + ori_diff * config.orientation_weight

            step_diff = np.linalg.norm((p_c - prev_pts) - delta_p, axis=1)
            fwd_prog = np.dot(p_c - prev_pts, delta_p)
            backward_pen = np.where(fwd_prog < -0.5, 600.0, 0.0)

            trans_cost = step_diff * config.step_weight + backward_pen
            total = dp[i - 1] + trans_cost + emission
            best_prev = int(np.argmin(total))
            dp[i, c] = total[best_prev]
            parent[i, c] = best_prev

    # Backtrack
    best_end = int(np.argmin(dp[-1]))
    seq = [best_end]
    for i in range(n_pts - 1, 0, -1):
        seq.append(parent[i, seq[-1]])
    seq.reverse()

    aligned = np.array([ref_geom.skel_points[indices[i, seq[i]]] for i in range(n_pts)], dtype=np.float32)
    return aligned


def align_stroke_to_reference(
    stroke: Dict[str, Any],
    ref_geom: ReferenceGeometry,
    config: Optional[CorrectionConfig] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Aligns a single human stroke to the reference geometry:
    - Preserves stroke ID, color, width, drawing sequence, and drawing direction.
    - Accurately fits to candidate reference paths for high confidence.
    - Seamlessly falls back to Viterbi map-matching across complex intersections.
    - Smoothly blends for medium confidence.
    - Retains original stroke for low confidence.
    """
    cfg = config or CorrectionConfig()
    pts_raw = stroke.get("points", [])
    if len(pts_raw) < 2:
        return stroke, {"status": "too_few_points"}

    human_pts = np.array([[p["x"], p["y"]] for p in pts_raw], dtype=np.float32)
    human_times = np.array([p.get("t", 0.0) for p in pts_raw], dtype=np.float32)

    # Check overall proximity to reference skeleton
    if ref_geom.skel_tree is None or len(ref_geom.skel_points) == 0:
        return stroke, {"status": "empty_reference", "confidence": 0.0}

    skel_dists, _ = ref_geom.skel_tree.query(human_pts)
    skel_med_d = float(np.median(skel_dists))
    if skel_med_d > cfg.max_matching_distance:
        return stroke, {
            "status": "low_confidence_retained",
            "confidence": 0.0,
            "median_dist": skel_med_d
        }

    # 1. Candidate Path Matching
    best_path, confidence, match_diag = match_stroke_to_reference(
        human_pts, ref_geom, max_match_dist=cfg.max_matching_distance
    )

    best_coverage = match_diag.get("best_coverage", 0.0)

    # If best_path has solid coverage (>= 60%), use subsegment projection along that path
    use_path_subsegment = (best_path is not None and best_coverage >= 0.55 and confidence >= cfg.low_confidence_threshold)

    if use_path_subsegment and best_path is not None:
        path_pts = best_path.points
        _, idxs = best_path.query(human_pts)
        i_start = int(idxs[0])
        i_end = int(idxs[-1])

        if best_path.is_closed:
            if i_end >= i_start:
                arc1 = path_pts[i_start:i_end + 1]
                arc2 = np.vstack([path_pts[i_start::-1], path_pts[:i_end - 1:-1]]) if i_end > 0 else path_pts[i_start::-1]
            else:
                arc1 = np.vstack([path_pts[i_start:], path_pts[:i_end + 1]])
                arc2 = path_pts[i_start:i_end - 1:-1] if i_end > 0 else path_pts[i_start::-1]

            d1, _ = cKDTree(arc1).query(human_pts)
            d2, _ = cKDTree(arc2).query(human_pts)
            ref_subseg = arc1 if np.mean(d1) <= np.mean(d2) else arc2
        else:
            if i_end >= i_start:
                ref_subseg = path_pts[i_start:i_end + 1]
            else:
                ref_subseg = path_pts[i_end:i_start + 1][::-1]

        h_dir = human_pts[-1] - human_pts[0]
        r_dir = ref_subseg[-1] - ref_subseg[0]
        if np.dot(h_dir, r_dir) < 0:
            ref_subseg = ref_subseg[::-1]

        n_target = len(human_pts)
        diffs = ref_subseg[1:] - ref_subseg[:-1]
        cum_dist = np.insert(np.cumsum(np.linalg.norm(diffs, axis=1)), 0, 0.0)
        total_len = cum_dist[-1]

        if total_len > 1e-4 and len(ref_subseg) >= 2:
            t_eval = np.linspace(0.0, total_len, n_target)
            aligned_x = np.interp(t_eval, cum_dist, ref_subseg[:, 0])
            aligned_y = np.interp(t_eval, cum_dist, ref_subseg[:, 1])
            aligned_pts = np.column_stack([aligned_x, aligned_y])
        else:
            aligned_pts = viterbi_align_to_skeleton(human_pts, ref_geom, cfg)
    elif skel_med_d <= cfg.max_matching_distance:
        # Multi-branch stroke or intersection traversal: use Viterbi alignment
        aligned_pts = viterbi_align_to_skeleton(human_pts, ref_geom, cfg)
        confidence = float(np.clip(1.0 - (skel_med_d / cfg.max_matching_distance), 0.5, 0.95))
    else:
        return stroke, {"status": "low_confidence_retained", "confidence": confidence}

    # Endpoint preservation and confidence blending
    blend_weight = float(np.clip((confidence - cfg.low_confidence_threshold) / 
                                 max(1e-4, cfg.high_confidence_threshold - cfg.low_confidence_threshold), 0.0, 1.0))
    alpha = 0.5 + 0.5 * blend_weight if confidence >= cfg.high_confidence_threshold else blend_weight * 0.7

    corrected_pts = alpha * aligned_pts + (1.0 - alpha) * human_pts

    # Anchor endpoints to human intent if within reasonable proximity
    if np.linalg.norm(human_pts[0] - corrected_pts[0]) < 25.0:
        corrected_pts[0] = 0.3 * human_pts[0] + 0.7 * corrected_pts[0]
    if np.linalg.norm(human_pts[-1] - corrected_pts[-1]) < 25.0:
        corrected_pts[-1] = 0.3 * human_pts[-1] + 0.7 * corrected_pts[-1]

    # Gentle Moving Average Smoothing
    if cfg.enable_smoothing and len(corrected_pts) > 6:
        w_size = cfg.smoothing_window
        kernel = np.ones(w_size) / float(w_size)
        pad_size = w_size // 2
        px = np.pad(corrected_pts[:, 0], pad_size, mode="edge")
        py = np.pad(corrected_pts[:, 1], pad_size, mode="edge")
        sm_x = np.convolve(px, kernel, mode="valid")
        sm_y = np.convolve(py, kernel, mode="valid")
        sm_x[0], sm_x[-1] = corrected_pts[0, 0], corrected_pts[-1, 0]
        sm_y[0], sm_y[-1] = corrected_pts[0, 1], corrected_pts[-1, 1]
        corrected_pts = np.column_stack([sm_x, sm_y])

    # Reconstruct stroke points dictionary
    n_pts = len(corrected_pts)
    final_points = []
    for i in range(n_pts):
        ix = int(round(np.clip(corrected_pts[i, 0], 0.0, 1079.0)))
        iy = int(round(np.clip(corrected_pts[i, 1], 0.0, 1919.0)))
        it = float(human_times[min(i, len(human_times) - 1)])
        if final_points and final_points[-1]["x"] == ix and final_points[-1]["y"] == iy:
            continue
        final_points.append({"x": ix, "y": iy, "t": it})

    if not final_points:
        return stroke, {"status": "empty_resample", "confidence": confidence}

    corrected_stroke = {
        "id": stroke.get("id"),
        "color_bgr": stroke.get("color_bgr"),
        "width": stroke.get("width"),
        "points": final_points
    }

    diag = {
        "status": "aligned",
        "confidence": confidence,
        "matched_path_id": best_path.id if best_path else None,
        "points_before": len(human_pts),
        "points_after": len(final_points),
        "median_dist_before": skel_med_d,
        "median_dist_after": float(np.median(ref_geom.skel_tree.query(corrected_pts)[0]))
    }

    return corrected_stroke, diag


def correct_stroke_sequence(
    strokes: List[Dict[str, Any]],
    ref_geom: Optional[ReferenceGeometry] = None,
    config: Optional[CorrectionConfig] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Corrects a sequence of user strokes against the reference geometry:
    - Retains original stroke order, stroke count, colors, widths, and IDs.
    - Corrects high/medium confidence strokes while preserving low-confidence strokes.
    - Applies conservative gap recovery for closed contours.
    """
    cfg = config or CorrectionConfig()
    diagnostics: Dict[str, Any] = {
        "total_strokes": len(strokes),
        "corrected_count": 0,
        "retained_count": 0,
        "per_stroke": []
    }

    if ref_geom is None or not strokes:
        diagnostics["retained_count"] = len(strokes)
        return strokes, diagnostics

    corrected_strokes: List[Dict[str, Any]] = []

    for stroke in strokes:
        try:
            corr_stroke, stroke_diag = align_stroke_to_reference(stroke, ref_geom, cfg)
            if stroke_diag.get("status") == "aligned":
                diagnostics["corrected_count"] += 1
            else:
                diagnostics["retained_count"] += 1
            diagnostics["per_stroke"].append(stroke_diag)
            corrected_strokes.append(corr_stroke)
        except Exception as e:
            logger.warning(f"Error correcting stroke {stroke.get('id')}: {e}. Retaining original.")
            diagnostics["retained_count"] += 1
            diagnostics["per_stroke"].append({"status": "error", "error": str(e)})
            corrected_strokes.append(stroke)

    # Optional conservative gap recovery: close loop if endpoints are adjacent on a closed contour
    if cfg.enable_gap_recovery:
        for s in corrected_strokes:
            pts = s.get("points", [])
            if len(pts) >= 15:
                p0 = pts[0]
                pn = pts[-1]
                gap_dist = math.hypot(p0["x"] - pn["x"], p0["y"] - pn["y"])
                if 2.0 < gap_dist <= cfg.max_gap_recovery_distance:
                    d0 = ref_geom.distance_map[p0["y"], p0["x"]]
                    dn = ref_geom.distance_map[pn["y"], pn["x"]]
                    if d0 < 15.0 and dn < 15.0:
                        pts.append({"x": p0["x"], "y": p0["y"], "t": pn["t"] + 10.0})

    return corrected_strokes, diagnostics


def validate_corrected_path(
    path: List[Optional[Tuple[int, int]]],
    width: int = 1080,
    height: int = 1920
) -> List[Optional[Tuple[int, int]]]:
    """
    Validates renderer-compatible path tuples:
    - Strictly clamps non-None points to canvas bounds [0, width-1] x [0, height-1].
    - Eliminates consecutive None delimiters.
    - Strips leading and trailing None delimiters.
    """
    cleaned: List[Optional[Tuple[int, int]]] = []
    for pt in path:
        if pt is None:
            if cleaned and cleaned[-1] is not None:
                cleaned.append(None)
        else:
            x, y = pt
            cx = max(0, min(int(round(x)), width - 1))
            cy = max(0, min(int(round(y)), height - 1))
            cleaned.append((cx, cy))

    while cleaned and cleaned[-1] is None:
        cleaned.pop()
    return cleaned


def render_corrected_sketch(
    strokes: List[Dict[str, Any]],
    output_path: str,
    width: int = 1080,
    height: int = 1920
) -> str:
    """
    Renders corrected strokes into a high-contrast monochrome sketch image
    (black lines on pure white canvas) for procedural thumbnail generation.
    """
    sketch = np.full((height, width, 3), 255, dtype=np.uint8)

    for stroke in strokes:
        pts = stroke.get("points", [])
        thickness = max(4, int(stroke.get("width", 6)))
        for i in range(1, len(pts)):
            p1 = (pts[i - 1]["x"], pts[i - 1]["y"])
            p2 = (pts[i]["x"], pts[i]["y"])
            cv2.line(sketch, p1, p2, (0, 0, 0), thickness, lineType=cv2.LINE_AA)
        for pt in pts:
            cv2.circle(sketch, (pt["x"], pt["y"]), max(2, thickness // 2), (0, 0, 0), -1, lineType=cv2.LINE_AA)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cv2.imwrite(output_path, sketch, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return output_path


def save_alignment_diagnostics(
    debug_dir: Union[str, Path],
    ref_geom: ReferenceGeometry,
    original_strokes: List[Dict[str, Any]],
    corrected_strokes: List[Dict[str, Any]],
    diagnostics: Dict[str, Any]
) -> str:
    """
    Saves internal debug artifacts to a job-specific temporary directory.
    Never clutters production outputs.
    """
    out_dir = Path(debug_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(out_dir / "01_reference_fitted.png"), ref_geom.fitted_image)
    cv2.imwrite(str(out_dir / "02_reference_mask.png"), ref_geom.binary_mask)
    cv2.imwrite(str(out_dir / "03_reference_skeleton.png"), ref_geom.skeleton)
    render_corrected_sketch(original_strokes, str(out_dir / "04_original_strokes.png"))
    render_corrected_sketch(corrected_strokes, str(out_dir / "05_corrected_strokes.png"))

    # Comparison visual overlay
    overlay = ref_geom.fitted_image.copy()
    skel_pts = ref_geom.skel_points.astype(int)
    for p in skel_pts:
        cv2.circle(overlay, (p[0], p[1]), 1, (0, 255, 0), -1)

    for s in original_strokes:
        pts = s.get("points", [])
        for i in range(1, len(pts)):
            p1 = (pts[i - 1]["x"], pts[i - 1]["y"])
            p2 = (pts[i]["x"], pts[i]["y"])
            cv2.line(overlay, p1, p2, (0, 200, 255), 2, lineType=cv2.LINE_AA)

    for s in corrected_strokes:
        pts = s.get("points", [])
        for i in range(1, len(pts)):
            p1 = (pts[i - 1]["x"], pts[i - 1]["y"])
            p2 = (pts[i]["x"], pts[i]["y"])
            cv2.line(overlay, p1, p2, (255, 255, 255), 3, lineType=cv2.LINE_AA)

    cv2.imwrite(str(out_dir / "06_alignment_comparison.png"), overlay)

    with open(out_dir / "alignment_summary.json", "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, indent=2)

    return str(out_dir)


def serialize_reference_geometry(ref_geom: ReferenceGeometry, max_pts_per_path: int = 250) -> Dict[str, Any]:
    """
    Serializes ReferenceGeometry into lightweight JSON-friendly structures
    suitable for immediate in-browser spatial indexing and live snapping.
    """
    serialized_paths = []
    for p in ref_geom.paths:
        n = len(p.points)
        if n < 2:
            continue

        # Subsample if path is exceptionally dense to keep payload minimal (< 50 KB)
        if n > max_pts_per_path:
            indices = np.linspace(0, n - 1, max_pts_per_path, dtype=int)
            pts = p.points[indices]
            tangents = p.tangents[indices]
        else:
            pts = p.points
            tangents = p.tangents

        pts_list = [[round(float(x), 1), round(float(y), 1)] for x, y in pts]
        tangents_list = [[round(float(tx), 2), round(float(ty), 2)] for tx, ty in tangents]

        serialized_paths.append({
            "id": int(p.id),
            "is_closed": bool(p.is_closed),
            "points": pts_list,
            "tangents": tangents_list
        })

    return {
        "paths": serialized_paths,
        "roi": [int(v) for v in ref_geom.image_roi],
        "scale": float(ref_geom.scale)
    }


def refine_live_aligned_strokes(
    strokes: List[Dict[str, Any]],
    ref_geom: Optional[ReferenceGeometry] = None,
    config: Optional[CorrectionConfig] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validates and conservatively refines strokes that were already live-aligned
    in the browser in real time:
    - Enforces strict canvas coordinate bounds (0..1079, 0..1919).
    - With a reference, validates the whole trajectory against the centerline and
      projects accepted submitted points to it; rejected spans become pen-up gaps.
    - Without a reference, performs bounded legacy cleanup and optional small-loop
      recovery without smoothing live-aligned points.
    - Preserves stroke order, direction, timing, and IDs for accepted points.
    """
    cfg = config or CorrectionConfig()
    refined_strokes = []
    rejected_samples = 0
    accepted_distances: List[float] = []
    max_deviation = 3.0

    if ref_geom is not None and (ref_geom.skel_tree is None or len(ref_geom.skel_points) == 0):
        raise ValueError("The uploaded blueprint has no usable centerline geometry.")

    def add_runs(stroke: Dict[str, Any], runs: List[List[Dict[str, Any]]]) -> None:
        for run_idx, points in enumerate(runs):
            if not points:
                continue
            base_id = stroke.get("id", "stroke")
            out_id = base_id if run_idx == 0 else f"{base_id}_sub{run_idx + 1}"
            refined_strokes.append({
                "id": out_id,
                "color_bgr": stroke.get("color_bgr"),
                "width": stroke.get("width"),
                "points": points,
            })

    for stroke in strokes:
        pts = stroke.get("points", [])
        if not pts:
            continue

        # Pointer jumps always create pen-up boundaries, even if both endpoints happen
        # to land on valid but disconnected blueprint components.
        input_runs: List[List[Dict[str, Any]]] = []
        closed_legacy = False
        if ref_geom is None and len(pts) >= 6:
            try:
                closed_legacy = math.hypot(float(pts[0]["x"]) - float(pts[-1]["x"]), float(pts[0]["y"]) - float(pts[-1]["y"])) <= 20.0
            except (KeyError, TypeError, ValueError):
                closed_legacy = False
        current = list(pts) if closed_legacy else [pts[0]]
        if not closed_legacy:
            for prev, point in zip(pts, pts[1:]):
                try:
                    distance = math.hypot(float(point["x"]) - float(prev["x"]), float(point["y"]) - float(prev["y"]))
                except (KeyError, TypeError, ValueError):
                    distance = float("inf")
                if distance > 35.0:
                    if current:
                        input_runs.append(current)
                    current = [point]
                else:
                    current.append(point)
        if current:
            input_runs.append(current)

        if ref_geom is None:
            # Legacy residual cleanup remains available to callers without a blueprint.
            # Live-aligned coordinates are already snapped, so do not smooth them.
            clean_runs = []
            for run_idx, run in enumerate(input_runs):
                clean = []
                for point in run:
                    try:
                        x = int(round(np.clip(float(point["x"]), 0.0, 1079.0)))
                        y = int(round(np.clip(float(point["y"]), 0.0, 1919.0)))
                        t = float(point.get("t", 0.0))
                    except (KeyError, TypeError, ValueError, OverflowError):
                        continue
                    if not clean or (clean[-1]["x"], clean[-1]["y"]) != (x, y):
                        clean.append({"x": x, "y": y, "t": t})
                if cfg.enable_gap_recovery and len(clean) >= 6:
                    gap = math.hypot(clean[0]["x"] - clean[-1]["x"], clean[0]["y"] - clean[-1]["y"])
                    if gap <= cfg.max_gap_recovery_distance:
                        clean[-1]["x"], clean[-1]["y"] = clean[0]["x"], clean[0]["y"]
                clean_runs.append(clean)
            add_runs(stroke, clean_runs)
            continue

        # Strict mode checks every 2px along the submitted trajectory. Accepted
        # browser points are projected to the centerline, while the validation
        # samples stay diagnostic-only so existing point counts and timing survive.
        strict_runs: List[List[Dict[str, Any]]] = []
        for run in input_runs:
            active: List[Dict[str, Any]] = []

            def projected(point, nearest_idx):
                px, py = ref_geom.skel_points[int(nearest_idx)]
                return {
                    "x": int(round(np.clip(px, 0.0, 1079.0))),
                    "y": int(round(np.clip(py, 0.0, 1919.0))),
                    "t": float(point.get("t", 0.0)),
                }

            if len(run) == 1:
                point = run[0]
                distance, nearest_idx = ref_geom.skel_tree.query([float(point["x"]), float(point["y"])], k=1)
                if float(distance) <= max_deviation:
                    accepted_distances.append(float(distance))
                    strict_runs.append([projected(point, nearest_idx)])
                else:
                    rejected_samples += 1
                continue

            first = run[0]
            first_distance, first_idx = ref_geom.skel_tree.query([float(first["x"]), float(first["y"])], k=1)
            if float(first_distance) <= max_deviation:
                accepted_distances.append(float(first_distance))
                active = [projected(first, first_idx)]
            else:
                rejected_samples += 1

            for p0, p1 in zip(run, run[1:]):
                x0, y0 = float(p0["x"]), float(p0["y"])
                x1, y1 = float(p1["x"]), float(p1["y"])
                length = math.hypot(x1 - x0, y1 - y0)
                steps = max(1, int(math.ceil(length / 2.0)))
                fractions = np.linspace(0.0, 1.0, steps + 1, dtype=np.float32)
                samples = np.column_stack((x0 + (x1 - x0) * fractions, y0 + (y1 - y0) * fractions)).astype(np.float32)
                distances, indices = ref_geom.skel_tree.query(samples, k=1)
                valid_segment = bool(np.all(distances <= max_deviation))
                if valid_segment:
                    accepted_distances.extend(float(d) for d in distances)
                    endpoint = projected(p1, indices[-1])
                    if not active:
                        active = [projected(p0, indices[0])]
                    if (active[-1]["x"], active[-1]["y"]) != (endpoint["x"], endpoint["y"]):
                        active.append(endpoint)
                else:
                    rejected_samples += int(np.count_nonzero(distances > max_deviation))
                    if len(active) >= 2:
                        strict_runs.append(active)
                    active = []
                    endpoint_distance = float(distances[-1])
                    if endpoint_distance <= max_deviation:
                        active = [projected(p1, indices[-1])]

            if len(active) >= 2:
                strict_runs.append(active)

        # Keep legitimate isolated dots only when they lie on blueprint geometry.
        add_runs(stroke, strict_runs)

    if ref_geom is not None and not refined_strokes:
        raise ValueError("No submitted drawing points remain on the uploaded blueprint centerline.")

    distances = np.asarray(accepted_distances, dtype=np.float32)
    diag = {
        "status": "live_aligned_validated" if ref_geom is not None else "live_aligned_refined",
        "total_strokes": len(strokes),
        "refined_count": len(refined_strokes),
        "rejected_samples": rejected_samples,
        "geometry_error_mean": float(np.mean(distances)) if len(distances) else 0.0,
        "geometry_error_p95": float(np.percentile(distances, 95)) if len(distances) else 0.0,
        "geometry_error_p99": float(np.percentile(distances, 99)) if len(distances) else 0.0,
        "geometry_error_max": float(np.max(distances)) if len(distances) else 0.0,
    }
    return refined_strokes, diag

