"""
3D Raised-Powder Kolam Renderer
Headless Kolam Video Generator V2/V3

Renders a convincing raised rice-flour / powder Kolam on a wood surface using
deterministic height-field (2.5D) rendering with:
  - Distance-field-derived smooth raised cross-sections
  - Directional lighting with specular highlights
  - Soft contact shadows underneath raised powder
  - Subtle ambient occlusion at line intersections
  - Fine static powder-grain texture (temporally stable)
  - 3D airborne pen-lift elevation on transitions (-18px)
  - Progressive animation from the shared stroke timeline

Uses the same validated geometry, stroke order, and frame timing as the 2D
renderer so both outputs represent identical drawing progression and duration.
"""

import cv2
import numpy as np
import os
import math
import bisect
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from engine.renderer import (
    _VideoFrameWriter,
    create_footer_watermark,
    create_header_title,
    apply_footer_watermark,
    load_and_prepare_hand,
    overlay_hand,
)


# --------------------------------------------------------------------------- #
#  Height-field material parameters
# --------------------------------------------------------------------------- #

# Light direction (normalized) — top-left illumination
_LIGHT_DIR = np.array([0.4, -0.5, 0.75], dtype=np.float32)
_LIGHT_DIR /= np.linalg.norm(_LIGHT_DIR)

# Maximum powder height in pixels for the cross-section
_MAX_HEIGHT = 5.0

# Distance-field radius controlling the powder bevel width
_BEVEL_RADIUS = 8.0

# Powder base color (warm white rice flour)
_POWDER_COLOR = np.array([245, 240, 232], dtype=np.float32)  # RGB

# Shadow parameters
_SHADOW_OPACITY = 0.35
_SHADOW_OFFSET = (2, 3)  # (dx, dy) pixels

# Ambient occlusion strength
_AO_STRENGTH = 0.18

# Powder grain texture amplitude
_GRAIN_AMPLITUDE = 6.0

# Specular highlight parameters
_SPEC_POWER = 24.0
_SPEC_STRENGTH = 0.45


def _generate_static_grain(height: int, width: int, amplitude: float = _GRAIN_AMPLITUDE, seed: int = 42) -> np.ndarray:
    """Precomputes a static powder grain texture map for temporal stability."""
    rng = np.random.RandomState(seed)
    grain = rng.normal(0, amplitude, (height, width)).astype(np.float32)
    grain = cv2.GaussianBlur(grain, (3, 3), 0.5)
    return grain


def _build_stroke_mask(base_mask: np.ndarray, strokes, stroke_frames, frame_within_stroke,
                       current_stroke_idx, line_thickness=6):
    """
    Build a binary mask of all visible strokes up to the current animation position,
    reusing base_mask containing all previously completed strokes for maximum performance.
    """
    mask = base_mask.copy()

    if current_stroke_idx < len(strokes):
        s = strokes[current_stroke_idx]
        pts = s['points']
        cum_dist = s['cum_dist']
        stroke_len = s['length']
        n_pts = len(pts)
        n_frames = stroke_frames[current_stroke_idx]
        f = frame_within_stroke

        if n_pts == 1 or stroke_len < 1e-4:
            w = s['widths'][0] if s['widths'][0] is not None else line_thickness
            cv2.circle(mask, pts[0], max(1, w // 2), 255, -1, lineType=cv2.LINE_AA)
        elif n_pts >= 2:
            if f == n_frames - 1:
                target_dist = stroke_len
            else:
                target_dist = ((f + 1) / float(n_frames)) * stroke_len

            target_i = bisect.bisect_left(cum_dist, target_dist, lo=1)
            target_i = min(n_pts - 1, max(1, target_i))

            # Draw complete segments up to target_i-1
            for j in range(1, target_i):
                w = s['widths'][j] if s['widths'][j] is not None else line_thickness
                cv2.line(mask, pts[j-1], pts[j], 255, w, lineType=cv2.LINE_AA)

            # Interpolate within active segment
            seg_d0 = cum_dist[target_i - 1]
            seg_d1 = cum_dist[target_i]
            seg_len = seg_d1 - seg_d0

            if f == n_frames - 1:
                curr_pt = pts[-1]
            elif seg_len > 1e-6:
                alpha = (target_dist - seg_d0) / seg_len
                alpha = max(0.0, min(1.0, alpha))
                cx = int(round((1.0 - alpha) * pts[target_i - 1][0] + alpha * pts[target_i][0]))
                cy = int(round((1.0 - alpha) * pts[target_i - 1][1] + alpha * pts[target_i][1]))
                curr_pt = (cx, cy)
            else:
                curr_pt = pts[target_i]

            last_pt = pts[target_i - 1] if target_i > 0 else pts[0]
            w = s['widths'][target_i] if s['widths'][target_i] is not None else line_thickness
            cv2.line(mask, last_pt, curr_pt, 255, w, lineType=cv2.LINE_AA)

    return mask


def _compute_height_field(stroke_mask: np.ndarray, bevel_radius: float = _BEVEL_RADIUS, max_height: float = _MAX_HEIGHT) -> np.ndarray:
    """Compute a smooth raised cross-section height field from the stroke mask."""
    if cv2.countNonZero(stroke_mask) == 0:
        return np.zeros_like(stroke_mask, dtype=np.float32)

    dist = cv2.distanceTransform(stroke_mask, cv2.DIST_L2, 5)
    normalized = np.clip(dist / bevel_radius, 0.0, 1.0)
    # Cosine-based rounded cross-section
    height = max_height * (1.0 - np.cos(np.pi * normalized)) / 2.0
    return height.astype(np.float32)


def _compute_normals(height_field: np.ndarray) -> np.ndarray:
    """Compute surface normals from the height field using Sobel gradients."""
    gx = cv2.Sobel(height_field, cv2.CV_32F, 1, 0, ksize=3) * 0.25
    gy = cv2.Sobel(height_field, cv2.CV_32F, 0, 1, ksize=3) * 0.25

    nz = np.ones_like(gx)
    norm = np.sqrt(gx * gx + gy * gy + nz * nz)
    norm = np.maximum(norm, 1e-6)

    nx = -gx / norm
    ny = -gy / norm
    nz_n = nz / norm

    return np.stack([nx, ny, nz_n], axis=-1)


def _apply_lighting(normals: np.ndarray, height_field: np.ndarray, stroke_mask: np.ndarray,
                    wood_bg: np.ndarray, powder_color=_POWDER_COLOR, grain_map: np.ndarray = None) -> np.ndarray:
    """
    Apply directional lighting, shadows, AO, and texture to create 3D powder appearance.
    Optimized through bounding-box ROI processing to minimize per-frame computation.
    """
    h, w = height_field.shape
    result = wood_bg.copy()

    nonzero = cv2.findNonZero(stroke_mask)
    if nonzero is None:
        return result

    x, y, bw, bh = cv2.boundingRect(nonzero)
    margin = 30
    x1 = max(0, x - margin)
    y1 = max(0, y - margin)
    x2 = min(w, x + bw + margin)
    y2 = min(h, y + bh + margin)

    sub_mask = stroke_mask[y1:y2, x1:x2]
    sub_hf = height_field[y1:y2, x1:x2]
    sub_norm = normals[y1:y2, x1:x2]
    sub_wood = result[y1:y2, x1:x2].astype(np.float32)

    mask_float = (sub_mask > 0).astype(np.float32)

    # Diffuse lighting (N · L)
    ndotl = (sub_norm[:, :, 0] * _LIGHT_DIR[0] +
             sub_norm[:, :, 1] * _LIGHT_DIR[1] +
             sub_norm[:, :, 2] * _LIGHT_DIR[2])
    ndotl = np.clip(ndotl, 0.0, 1.0)
    illumination = 0.55 + 0.45 * ndotl

    # Specular highlights
    half_vec = _LIGHT_DIR + np.array([0, 0, 1], dtype=np.float32)
    half_vec /= np.linalg.norm(half_vec)
    ndoth = np.clip(sub_norm[:, :, 0] * half_vec[0] +
                    sub_norm[:, :, 1] * half_vec[1] +
                    sub_norm[:, :, 2] * half_vec[2], 0.0, 1.0)
    specular = _SPEC_STRENGTH * np.power(ndoth, _SPEC_POWER)

    # Contact shadow
    sh, sw = sub_mask.shape
    shadow_mask = np.zeros((sh, sw), dtype=np.float32)
    sx, sy = _SHADOW_OFFSET
    if sy > 0 and sx > 0:
        shadow_mask[sy:, sx:] = mask_float[:-sy, :-sx]
    elif sy > 0:
        shadow_mask[sy:, :] = mask_float[:-sy, :]
    shadow_only = np.clip(shadow_mask - mask_float, 0.0, 1.0)
    shadow_soft = cv2.GaussianBlur(shadow_only, (7, 7), 1.5)

    # Ambient occlusion
    ao_mask = cv2.GaussianBlur(mask_float, (15, 15), 3.0)
    ao_factor = 1.0 - _AO_STRENGTH * np.clip(ao_mask - 0.5, 0.0, 0.5) * 2.0

    # Static powder grain
    if grain_map is not None:
        sub_grain = grain_map[y1:y2, x1:x2]
    else:
        sub_grain = 0.0

    # Compose powder color (RGB -> BGR)
    height_alpha = np.clip(sub_hf / (_MAX_HEIGHT * 0.3), 0.0, 1.0)
    powder_bgr = powder_color[::-1].reshape(1, 1, 3)

    lit_powder = powder_bgr * illumination[:, :, np.newaxis] * ao_factor[:, :, np.newaxis]
    lit_powder = lit_powder + specular[:, :, np.newaxis] * 255.0
    if isinstance(sub_grain, np.ndarray):
        lit_powder = lit_powder + sub_grain[:, :, np.newaxis]
    lit_powder = np.clip(lit_powder, 0, 255)

    sub_wood = sub_wood * (1.0 - _SHADOW_OPACITY * shadow_soft[:, :, np.newaxis])
    alpha_3d = height_alpha[:, :, np.newaxis]
    blended = (1.0 - alpha_3d) * sub_wood + alpha_3d * lit_powder

    result[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)
    return result


def render_kolam_video_3d(dots, path, wood_path, hand_path, output_path,
                          fps=25, line_thickness=6, show_watermark=True,
                          title="AK Kolam", cover_image_path=None,
                          point_colors=None, point_widths=None,
                          progress_callback=None, drawing_speed: float = 1.2):
    """
    3D raised-powder Kolam renderer.

    Produces a video with convincing raised rice-flour powder lines on a wood
    surface. Uses the exact same validated geometry, stroke order, and frame
    timing as the 2D renderer so both outputs show identical drawing progression.
    """
    width, height = 1080, 1920

    header_data = create_header_title(title, width, height) if title else None
    watermark_data = create_footer_watermark(width, height) if show_watermark else None

    # Load wood background
    wood = cv2.imread(wood_path)
    if wood is None:
        wood = np.zeros((height, width, 3), dtype=np.uint8)
        wood[:] = (30, 20, 15)
        for i in range(0, height, 4):
            cv2.line(wood, (0, i), (width, i),
                     (45 + np.random.randint(-5, 5), 30 + np.random.randint(-5, 5), 20), 1)
    else:
        wood = cv2.resize(wood, (width, height))

    # Prepare hand
    hand_img = load_and_prepare_hand(hand_path, target_width=420)

    # Initialize video writer
    frame_writer = _VideoFrameWriter(output_path, width, height, fps)
    frame_count = 0

    def write_frame_to_output(f_img):
        nonlocal frame_count
        frame_writer.write(f_img)
        frame_count = frame_writer.frame_count

    # Base frame with dots on wood
    base_wood = wood.copy()
    for x, y in dots:
        cv2.circle(base_wood, (x, y), 5, (255, 255, 255), -1, lineType=cv2.LINE_AA)

    # Write cover teaser frames if provided (matches 2D renderer exactly)
    if cover_image_path and os.path.exists(cover_image_path):
        cover = cv2.imread(cover_image_path)
        if cover is not None:
            cover = cv2.resize(cover, (width, height))
            cover_frames = 15
            for c_idx in range(cover_frames):
                if c_idx >= cover_frames - 3:
                    alpha = (cover_frames - 1 - c_idx) / 3.0
                    blend = cv2.addWeighted(cover, alpha, base_wood, 1.0 - alpha, 0)
                    write_frame_to_output(blend)
                else:
                    write_frame_to_output(cover)

    # Parse strokes (identical logic to 2D renderer)
    strokes = []
    curr_pts = []
    curr_colors = []
    curr_widths = []

    for idx, pt in enumerate(path):
        if pt is None:
            if curr_pts:
                strokes.append({'points': curr_pts, 'colors': curr_colors, 'widths': curr_widths})
                curr_pts, curr_colors, curr_widths = [], [], []
        else:
            try:
                x, y = int(round(float(pt[0]))), int(round(float(pt[1])))
            except (TypeError, ValueError, IndexError, OverflowError):
                if curr_pts:
                    strokes.append({"points": curr_pts, "colors": curr_colors, "widths": curr_widths})
                    curr_pts, curr_colors, curr_widths = [], [], []
                continue
            if not (0 <= x < width and 0 <= y < height):
                if curr_pts:
                    strokes.append({"points": curr_pts, "colors": curr_colors, "widths": curr_widths})
                    curr_pts, curr_colors, curr_widths = [], [], []
                continue
            point = (x, y)
            if curr_pts and curr_pts[-1] == point:
                continue
            curr_pts.append(point)
            c = point_colors[idx] if point_colors and idx < len(point_colors) else None
            w = point_widths[idx] if point_widths and idx < len(point_widths) else None
            curr_colors.append(c)
            curr_widths.append(w)

    if curr_pts:
        strokes.append({'points': curr_pts, 'colors': curr_colors, 'widths': curr_widths})

    # Compute cumulative arc-lengths
    for s in strokes:
        pts = s['points']
        n = len(pts)
        cum_dist = [0.0]
        total_d = 0.0
        for i in range(1, n):
            dx = float(pts[i][0] - pts[i-1][0])
            dy = float(pts[i][1] - pts[i-1][1])
            d = (dx * dx + dy * dy) ** 0.5
            total_d += d
            cum_dist.append(total_d)
        s['cum_dist'] = cum_dist
        s['length'] = total_d

    total_path_length = sum(s['length'] for s in strokes)

    # Arc-length timing (identical to 2D renderer)
    eff_speed = max(0.01, float(drawing_speed))
    pixels_per_frame = 8.85 * eff_speed
    minimum_frames = [2 for _ in strokes]
    target_draw_frames = max(sum(minimum_frames), int(round(total_path_length / pixels_per_frame)))

    # Transition frame counts
    trans_frames = []
    for k in range(len(strokes) - 1):
        p_end = strokes[k]['points'][-1]
        p_next = strokes[k+1]['points'][0]
        gap_dist = ((p_next[0] - p_end[0])**2 + (p_next[1] - p_end[1])**2) ** 0.5
        transition_distance_per_frame = pixels_per_frame * 3.0
        t_f = max(2, min(30, int(math.ceil(gap_dist / transition_distance_per_frame))))
        trans_frames.append(t_f)
    total_trans_frames = sum(trans_frames)

    # Apportion frames by arc length
    if strokes:
        extra_frames = target_draw_frames - sum(minimum_frames)
        if extra_frames > 0 and total_path_length > 1e-3:
            shares = [extra_frames * s['length'] / total_path_length for s in strokes]
            additions = [int(math.floor(share)) for share in shares]
            remainder = extra_frames - sum(additions)
            order = sorted(range(len(strokes)), key=lambda i: (-(shares[i] - additions[i]), i))
            for i in order[:remainder]:
                additions[i] += 1
            stroke_frames = [minimum_frames[i] + additions[i] for i in range(len(strokes))]
        else:
            stroke_frames = minimum_frames
    else:
        stroke_frames = []

    total_anim_frames = sum(stroke_frames) + total_trans_frames
    anim_frame_idx = 0

    # Precompute static powder grain texture map (temporally stable, zero per-frame allocation)
    grain_map = _generate_static_grain(height, width)

    # Progressive 3D rendering with persistent base mask
    completed_mask = np.zeros((height, width), dtype=np.uint8)

    for k, s in enumerate(strokes):
        pts = s['points']
        cum_dist = s['cum_dist']
        stroke_len = s['length']
        n_pts = len(pts)
        n_frames = stroke_frames[k]

        for f in range(n_frames):
            current_mask = _build_stroke_mask(
                completed_mask, strokes, stroke_frames, f, k, line_thickness
            )

            hf = _compute_height_field(current_mask)
            normals = _compute_normals(hf)

            frame = _apply_lighting(normals, hf, current_mask, base_wood,
                                    _POWDER_COLOR, grain_map)

            # Compute pen tip position for hand overlay
            if n_pts == 1 or stroke_len < 1e-4:
                tip_pos = pts[0]
            else:
                if f == n_frames - 1:
                    tip_pos = pts[-1]
                else:
                    target_dist = ((f + 1) / float(n_frames)) * stroke_len
                    target_i = bisect.bisect_left(cum_dist, target_dist, lo=1)
                    target_i = min(n_pts - 1, max(1, target_i))
                    seg_d0 = cum_dist[target_i - 1]
                    seg_d1 = cum_dist[target_i]
                    seg_len = seg_d1 - seg_d0

                    if seg_len > 1e-6:
                        alpha = (target_dist - seg_d0) / seg_len
                        alpha = max(0.0, min(1.0, alpha))
                        cx = int(round((1.0 - alpha) * pts[target_i - 1][0] + alpha * pts[target_i][0]))
                        cy = int(round((1.0 - alpha) * pts[target_i - 1][1] + alpha * pts[target_i][1]))
                        tip_pos = (cx, cy)
                    else:
                        tip_pos = pts[target_i]

            if hand_img is not None:
                frame = overlay_hand(frame, hand_img, tip_pos)
            else:
                cv2.circle(frame, tip_pos, 8, (255, 200, 200), -1)

            if header_data is not None:
                fade = min(1.0, (frame_count + 1) / 15.0) if frame_count < 15 else 1.0
                frame = apply_footer_watermark(frame, header_data, opacity=fade)
            if watermark_data is not None:
                fade = min(1.0, (frame_count + 1) / 15.0) if frame_count < 15 else 1.0
                frame = apply_footer_watermark(frame, watermark_data, opacity=fade)

            write_frame_to_output(frame)
            anim_frame_idx += 1

            if total_anim_frames > 0 and (anim_frame_idx % max(1, total_anim_frames // 20) == 0 or anim_frame_idx == total_anim_frames):
                prog = (anim_frame_idx / total_anim_frames) * 100.0
                import sys
                sys.stdout.write(f"\r  -> 3D Rendering progress: {prog:.1f}% ({anim_frame_idx}/{total_anim_frames} frames)")
                sys.stdout.flush()
                if progress_callback:
                    try:
                        progress_callback(prog, anim_frame_idx, total_anim_frames)
                    except Exception:
                        pass

        # Update completed mask at end of stroke
        if n_pts == 1 or stroke_len < 1e-4:
            w = s['widths'][0] if s['widths'][0] is not None else line_thickness
            cv2.circle(completed_mask, pts[0], max(1, w // 2), 255, -1, lineType=cv2.LINE_AA)
        else:
            for j in range(1, n_pts):
                w = s['widths'][j] if s['widths'][j] is not None else line_thickness
                cv2.line(completed_mask, pts[j-1], pts[j], 255, w, lineType=cv2.LINE_AA)

        # Pen-up transition to next stroke with 3D airborne elevation
        if k < len(strokes) - 1:
            next_start = strokes[k+1]['points'][0]
            curr_tip = strokes[k]['points'][-1]
            n_trans = trans_frames[k]

            trans_mask = completed_mask.copy()
            hf_trans = _compute_height_field(trans_mask)
            normals_trans = _compute_normals(hf_trans)
            trans_base = _apply_lighting(normals_trans, hf_trans, trans_mask, base_wood,
                                          _POWDER_COLOR, grain_map)

            for tf in range(n_trans):
                tau = float(tf + 1) / float(n_trans)
                ease = tau * tau * (3.0 - 2.0 * tau)
                tx = int(round((1.0 - ease) * curr_tip[0] + ease * next_start[0]))
                ty = int(round((1.0 - ease) * curr_tip[1] + ease * next_start[1]))
                # 3D Airborne pen lift elevation (-18px at apex) with soft ease landing
                lift_y = int(round(-18.0 * math.sin(math.pi * tau)))
                trans_tip = (tx, ty + lift_y)

                frame = trans_base.copy()
                if hand_img is not None:
                    frame = overlay_hand(frame, hand_img, trans_tip)
                else:
                    cv2.circle(frame, trans_tip, 8, (255, 200, 200), -1)

                if header_data is not None:
                    frame = apply_footer_watermark(frame, header_data, opacity=1.0)
                if watermark_data is not None:
                    frame = apply_footer_watermark(frame, watermark_data, opacity=1.0)

                write_frame_to_output(frame)
                anim_frame_idx += 1
                if progress_callback and total_anim_frames > 0:
                    prog = (anim_frame_idx / total_anim_frames) * 100.0
                    progress_callback(prog, anim_frame_idx, total_anim_frames)

    # Hold final frame for 1 second (25 frames), matching 2D renderer
    final_mask = completed_mask.copy()
    hf_final = _compute_height_field(final_mask)
    normals_final = _compute_normals(hf_final)
    final_3d = _apply_lighting(normals_final, hf_final, final_mask, base_wood,
                                _POWDER_COLOR, grain_map)

    if header_data is not None:
        final_3d = apply_footer_watermark(final_3d, header_data, opacity=1.0)
    if watermark_data is not None:
        final_3d = apply_footer_watermark(final_3d, watermark_data, opacity=1.0)

    # Final hold: keep hand at final position for first 8 frames, then lift away
    for hf in range(fps):
        frame = final_3d.copy()
        if hf < 8 and hand_img is not None and len(strokes) > 0:
            frame = overlay_hand(frame, hand_img, strokes[-1]['points'][-1])
        write_frame_to_output(frame)

    frame_writer.close()

    print(f"\n3D Video saved: {output_path}, {frame_count} frames, {frame_count/fps:.1f}s")
    return output_path
