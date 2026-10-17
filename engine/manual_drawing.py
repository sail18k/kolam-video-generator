"""
Manual Drawing Module for Headless Kolam Video Generator V2
Handles validation, normalization, and conversion of browser-recorded vector strokes
into renderer-compatible continuous paths, color/width buffers, and thumbnail sketches.
"""

import os
import math
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import cv2


class _StrokeCoverageIndex:
    """Spatial hash of previously accepted stroke centerlines."""

    def __init__(self, tolerance: float = 1.75, cell_size: float = 8.0):
        self.tolerance = tolerance
        self.cell_size = cell_size
        self.cells: Dict[Tuple[int, int], List[Tuple[float, float, float, float]]] = defaultdict(list)

    def _key(self, x: float, y: float) -> Tuple[int, int]:
        return (math.floor(x / self.cell_size), math.floor(y / self.cell_size))

    def covers(self, sample: Tuple[float, float, float, float]) -> bool:
        x, y, tx, ty = sample
        cx, cy = self._key(x, y)
        reach = int(math.ceil(self.tolerance / self.cell_size))
        for gy in range(cy - reach, cy + reach + 1):
            for gx in range(cx - reach, cx + reach + 1):
                for ox, oy, otx, oty in self.cells.get((gx, gy), ()):
                    if abs(tx * otx + ty * oty) < 0.75:
                        continue
                    if math.hypot(x - ox, y - oy) <= self.tolerance:
                        return True
        return False

    def add(self, points: List[Dict[str, Any]]) -> None:
        for sample in _sample_polyline(points):
            self.cells[self._key(sample[0], sample[1])].append(sample[:4])


def _sample_polyline(points: List[Dict[str, Any]], spacing: float = 2.0):
    """Return equally spaced (x, y, tangent-x, tangent-y, time) samples."""
    if not points:
        return []
    if len(points) == 1:
        p = points[0]
        return [(float(p["x"]), float(p["y"]), 0.0, 0.0, float(p.get("t", 0.0)))]

    result = []
    for p0, p1 in zip(points, points[1:]):
        x0, y0 = float(p0["x"]), float(p0["y"])
        x1, y1 = float(p1["x"]), float(p1["y"])
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        steps = max(1, int(math.ceil(length / spacing)))
        tx, ty = dx / length, dy / length
        t0, t1 = float(p0.get("t", 0.0)), float(p1.get("t", 0.0))
        for i in range(steps):
            f = i / steps
            result.append((x0 + dx * f, y0 + dy * f, tx, ty, t0 + (t1 - t0) * f))
    last = points[-1]
    prev = points[-2]
    dx, dy = float(last["x"]) - float(prev["x"]), float(last["y"]) - float(prev["y"])
    length = math.hypot(dx, dy) or 1.0
    result.append((float(last["x"]), float(last["y"]), dx / length, dy / length, float(last.get("t", 0.0))))
    return result


def _uncovered_runs(points: List[Dict[str, Any]], coverage: _StrokeCoverageIndex):
    """Remove long, direction-consistent intervals already drawn by earlier strokes."""
    samples = _sample_polyline(points)
    if not samples:
        return [], 0.0
    covered = [coverage.covers(sample[:4]) for sample in samples]
    ratio = sum(covered) / float(len(covered))
    if ratio >= 0.92:
        return [], ratio
    if ratio <= 0.02:
        return [points], ratio

    runs = []
    current = []
    for sample, is_covered in zip(samples, covered):
        if is_covered:
            if len(current) >= 2:
                runs.append(current)
            current = []
        else:
            current.append({
                "x": max(0, min(1079, int(round(sample[0])))),
                "y": max(0, min(1919, int(round(sample[1])))),
                "t": float(sample[4]),
            })
    if len(current) >= 2:
        runs.append(current)
    return runs or ([points] if ratio < 0.10 else []), ratio


def hex_to_bgr(hex_color: str, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    """Converts a CSS hex color (#RRGGBB or #RGB) to an OpenCV BGR tuple."""
    if not hex_color or not isinstance(hex_color, str):
        return default
    
    clean = hex_color.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join([c * 2 for c in clean])
    elif len(clean) != 6:
        return default
        
    try:
        r = int(clean[0:2], 16)
        g = int(clean[2:4], 16)
        b = int(clean[4:6], 16)
        return (b, g, r)
    except Exception:
        return default


def validate_and_normalize_drawing_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates drawing studio payload and normalizes stroke coordinates,
    clamping all values to 1080x1920 bounds and enforcing integer types.
    """
    if not isinstance(payload, dict):
        raise ValueError("Invalid payload: must be a JSON object.")
        
    strokes_raw = payload.get("strokes")
    if not strokes_raw or not isinstance(strokes_raw, list):
        raise ValueError("No strokes provided in drawing payload.")
        
    canvas_info = payload.get("canvas", {})
    canvas_w = int(canvas_info.get("width", 1080)) if isinstance(canvas_info, dict) else 1080
    canvas_h = int(canvas_info.get("height", 1920)) if isinstance(canvas_info, dict) else 1920
    
    normalized_strokes = []
    seen_ids = set()
    seen_signatures = set()
    coverage = _StrokeCoverageIndex()
    
    for s_idx, stroke in enumerate(strokes_raw):
        if not isinstance(stroke, dict):
            continue
            
        pts_raw = stroke.get("points")
        if not pts_raw or not isinstance(pts_raw, list):
            continue
            
        color_bgr = hex_to_bgr(stroke.get("color", "#FFFFFF"))
        width = int(stroke.get("width", 6))
        width = max(2, min(width, 40))
        
        cleaned_points = []
        for pt in pts_raw:
            if isinstance(pt, dict):
                x = pt.get("x")
                y = pt.get("y")
                t = pt.get("t", 0)
            elif isinstance(pt, (list, tuple)) and len(pt) >= 2:
                x, y = pt[0], pt[1]
                t = pt[2] if len(pt) > 2 else 0
            else:
                continue
                
            try:
                x_val = int(round(float(x)))
                y_val = int(round(float(y)))
                t_val = float(t) if t is not None else 0.0
            except (ValueError, TypeError, OverflowError):
                continue

            if not math.isfinite(x_val) or not math.isfinite(y_val) or not math.isfinite(t_val):
                continue
                
            # Clamp strictly to canvas coordinates
            x_val = max(0, min(x_val, 1079))
            y_val = max(0, min(y_val, 1919))
            
            # Skip consecutive identical points
            if cleaned_points and cleaned_points[-1]["x"] == x_val and cleaned_points[-1]["y"] == y_val:
                continue
                
            cleaned_points.append({"x": x_val, "y": y_val, "t": t_val})
            
        if not cleaned_points:
            continue
            
        # Deduplicate accidental duplicate stroke objects in payload:
        # 1. By unique stroke ID (if present and non-empty)
        stroke_id = str(stroke.get("id", "")).strip()
        if stroke_id and stroke_id in seen_ids:
            continue
            
        # 2. By exact coordinate and timestamp signature (prevents identical double submission)
        coords = tuple((p["x"], p["y"]) for p in cleaned_points)
        sig = min(coords, tuple(reversed(coords)))
        if sig in seen_signatures:
            continue
            
        if stroke_id:
            seen_ids.add(stroke_id)
        seen_signatures.add(sig)
            
        # If single isolated point (tap / dot), add tiny segment so it renders visibly
        single_tap = len(cleaned_points) == 1
        if single_tap:
            p0 = cleaned_points[0]
            offset_x = min(1079, p0["x"] + 1)
            cleaned_points.append({"x": offset_x, "y": p0["y"], "t": p0["t"] + 10})
            
        runs, _overlap = _uncovered_runs(cleaned_points, coverage)
        for run_idx, run in enumerate(runs):
            # Very short residuals are rasterization noise, not a useful stroke.
            run_length = sum(math.hypot(b["x"] - a["x"], b["y"] - a["y"]) for a, b in zip(run, run[1:]))
            if len(run) > 1 and run_length < 2.0 and not single_tap:
                continue
            out_id = stroke_id or f"stroke_{len(normalized_strokes)+1}"
            if len(runs) > 1:
                out_id = f"{out_id}_part{run_idx+1}"
            normalized_strokes.append({
                "id": out_id,
                "color_bgr": color_bgr,
                "width": width,
                "points": run
            })
            coverage.add(run)
        
    if not normalized_strokes:
        raise ValueError("Drawing does not contain any valid stroke points.")
        
    return {
        "canvas": {"width": canvas_w, "height": canvas_h},
        "title": str(payload.get("title", "AK Kolam")),
        "dot_grid": str(payload.get("dot_grid", "none")),
        "strokes": normalized_strokes,
        "reference_image": payload.get("reference_image"),
        "correction_enabled": bool(payload.get("correction_enabled", True)),
        "live_aligned": bool(payload.get("live_aligned", False))
    }


def strokes_to_renderer_path(
    normalized_strokes: List[Dict[str, Any]],
    step_size: int = 4
) -> Tuple[List[Optional[Tuple[int, int]]], List[Optional[Tuple[int, int, int]]], List[Optional[int]]]:
    """
    Converts strokes into an ordered sequence of 2D coordinates with `None` delimiters,
    interpolating line segments to ensure continuous smooth pen trajectories.
    Eliminates zero-length segments and redundant duplicate points.
    Returns: (path, point_colors, point_widths)
    """
    path: List[Optional[Tuple[int, int]]] = []
    point_colors: List[Optional[Tuple[int, int, int]]] = []
    point_widths: List[Optional[int]] = []
    
    for s_idx, stroke in enumerate(normalized_strokes):
        pts = stroke.get("points", [])
        if not pts:
            continue
        color = stroke.get("color_bgr", (255, 255, 255))
        width = stroke.get("width", 6)
        
        # Pen-up delimiter between independent strokes
        if path and path[-1] is not None:
            path.append(None)
            point_colors.append(None)
            point_widths.append(None)
            
        for i in range(len(pts)):
            curr_pt = (int(pts[i]["x"]), int(pts[i]["y"]))
            
            if i == 0:
                if not path or path[-1] is None or path[-1] != curr_pt:
                    path.append(curr_pt)
                    point_colors.append(color)
                    point_widths.append(width)
            else:
                prev_pt = (int(pts[i-1]["x"]), int(pts[i-1]["y"]))
                dx = curr_pt[0] - prev_pt[0]
                dy = curr_pt[1] - prev_pt[1]
                dist = math.hypot(dx, dy)
                
                # Zero-length step: skip redundant duplicate
                if dist < 0.5:
                    continue
                
                # Strict Blueprint Tracing: never interpolate across large gaps or blocked intervals!
                if dist > 40.0:
                    if path and path[-1] is not None:
                        path.append(None)
                        point_colors.append(None)
                        point_widths.append(None)
                    path.append(curr_pt)
                    point_colors.append(color)
                    point_widths.append(width)
                elif dist > step_size:
                    num_steps = max(1, int(dist / step_size))
                    for step in range(1, num_steps + 1):
                        frac = step / float(num_steps)
                        ix = int(round(prev_pt[0] + dx * frac))
                        iy = int(round(prev_pt[1] + dy * frac))
                        ix = max(0, min(ix, 1079))
                        iy = max(0, min(iy, 1919))
                        cand = (ix, iy)
                        if not path or path[-1] is None or path[-1] != cand:
                            path.append(cand)
                            point_colors.append(color)
                            point_widths.append(width)
                else:
                    if not path or path[-1] is None or path[-1] != curr_pt:
                        path.append(curr_pt)
                        point_colors.append(color)
                        point_widths.append(width)
                        
    # Strip trailing None delimiters
    while path and path[-1] is None:
        path.pop()
        point_colors.pop()
        point_widths.pop()
                    
    return path, point_colors, point_widths


def render_strokes_to_sketch_image(
    normalized_strokes: List[Dict[str, Any]],
    output_path: str,
    width: int = 1080,
    height: int = 1920
) -> str:
    """
    Renders the vector strokes as a clean, high-contrast monochrome sketch image
    (black drawing on white background) compatible with `generate_kolam_thumbnail`.
    """
    # Create white canvas
    sketch = np.full((height, width, 3), 255, dtype=np.uint8)
    
    for stroke in normalized_strokes:
        pts = stroke["points"]
        thickness = max(4, int(stroke["width"]))
        
        for i in range(1, len(pts)):
            p1 = (pts[i-1]["x"], pts[i-1]["y"])
            p2 = (pts[i]["x"], pts[i]["y"])
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) <= 40.0:
                cv2.line(sketch, p1, p2, (0, 0, 0), thickness, lineType=cv2.LINE_AA)
            
        # Draw rounded caps at points for crisp look
        for pt in pts:
            cv2.circle(sketch, (pt["x"], pt["y"]), max(2, thickness // 2), (0, 0, 0), -1, lineType=cv2.LINE_AA)
            
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cv2.imwrite(output_path, sketch, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return output_path
