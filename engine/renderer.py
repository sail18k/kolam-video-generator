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


class _VideoFrameWriter:
    """FFmpeg/NVENC-first frame writer with checked fallback and cleanup."""

    def __init__(self, output_path, width, height, fps):
        self.output_path = os.path.abspath(output_path)
        self.width, self.height, self.fps = width, height, fps
        self.frame_count = 0
        self.process = None
        self.capture = None
        self.writer = None
        self.temp_path = None
        self.closed = False

        parent = os.path.dirname(self.output_path) or os.getcwd()
        os.makedirs(parent, exist_ok=True)
        fd, self.temp_path = tempfile.mkstemp(prefix=".kolam_", suffix=".mp4", dir=parent)
        os.close(fd)
        os.unlink(self.temp_path)

        ffmpeg = shutil.which("ffmpeg")
        nvenc_ok, nvenc_error = self._probe(ffmpeg, "h264_nvenc", fps) if ffmpeg else (False, "ffmpeg not found")
        codec = "h264_nvenc" if nvenc_ok else None
        if nvenc_ok:
            print("Using FFmpeg with GPU acceleration (h264_nvenc)")
        else:
            print(f"NVENC unavailable; using FFmpeg software H.264: {nvenc_error[-400:]}")
            if ffmpeg:
                software_ok, software_error = self._probe(ffmpeg, "libx264", fps)
                if software_ok:
                    codec = "libx264"
                else:
                    print(f"FFmpeg software H.264 unavailable; trying OpenCV: {software_error[-400:]}")

        if ffmpeg and codec:
            try:
                self.capture = tempfile.TemporaryFile()
                cmd = [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "warning",
                    "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{width}x{height}",
                    "-pix_fmt", "bgr24", "-r", str(fps), "-i", "-", "-an",
                    "-c:v", codec,
                ]
                if codec == "h264_nvenc":
                    cmd += ["-preset", "p6", "-b:v", "8M"]
                else:
                    cmd += ["-preset", "veryfast", "-crf", "18"]
                cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", self.temp_path]
                self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=self.capture)
            except OSError as exc:
                if self.capture:
                    self.capture.close()
                    self.capture = None
                print(f"Failed to start FFmpeg, using OpenCV MP4 fallback: {exc}")

        if self.process is None:
            self.writer = cv2.VideoWriter(
                self.temp_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
            )
            if not self.writer.isOpened():
                self._discard_temp()
                raise RuntimeError("Neither FFmpeg nor OpenCV could initialize a video encoder.")

    @staticmethod
    def _probe(ffmpeg, codec, fps):
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
            f"testsrc=size=1080x1920:rate={fps}", "-frames:v", "1", "-c:v", codec, "-f", "null", "-"
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            return result.returncode == 0, (result.stderr or result.stdout or "").strip()
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

    def _stderr_text(self):
        if not self.capture:
            return ""
        try:
            self.capture.flush()
            self.capture.seek(0, os.SEEK_END)
            size = self.capture.tell()
            self.capture.seek(max(0, size - 8000))
            return self.capture.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _discard_temp(self):
        if self.temp_path:
            try:
                os.remove(self.temp_path)
            except OSError:
                pass

    def write(self, frame):
        if frame.shape != (self.height, self.width, 3) or frame.dtype != np.uint8:
            raise ValueError("Video frame must be uint8 BGR at the configured output dimensions.")
        frame = np.ascontiguousarray(frame)
        if self.process is not None:
            if self.process.poll() is not None:
                raise RuntimeError(f"FFmpeg stopped while rendering. {self._stderr_text()}")
            try:
                self.process.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError) as exc:
                raise RuntimeError(f"FFmpeg frame pipe failed. {self._stderr_text()}") from exc
        else:
            self.writer.write(frame)
        self.frame_count += 1

    def close(self):
        if self.closed:
            return
        self.closed = True
        error = None
        if self.process is not None:
            try:
                if self.process.stdin and not self.process.stdin.closed:
                    self.process.stdin.close()
                return_code = self.process.wait(timeout=120)
                if return_code != 0:
                    error = RuntimeError(f"FFmpeg exited with code {return_code}. {self._stderr_text()}")
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
                error = RuntimeError("FFmpeg timed out while finalizing the MP4.")
            finally:
                if self.capture:
                    self.capture.close()
                    self.capture = None
        elif self.writer is not None:
            self.writer.release()
            self.writer = None

        if error is None and self.temp_path and os.path.exists(self.temp_path) and os.path.getsize(self.temp_path) > 0:
            os.replace(self.temp_path, self.output_path)
        else:
            self._discard_temp()
            if error is None:
                error = RuntimeError("Video encoder completed without producing a valid output file.")
        if error:
            raise error

    def __del__(self):
        try:
            if self.process is not None and self.process.poll() is None:
                if self.process.stdin and not self.process.stdin.closed:
                    self.process.stdin.close()
                self.process.wait(timeout=5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        try:
            if self.writer is not None:
                self.writer.release()
            if self.capture is not None:
                self.capture.close()
            if not self.closed:
                self._discard_temp()
        except Exception:
            pass

def create_footer_watermark(width=1080, height=1920):
    """Generate high-quality Subscribe, Like, and Share footer watermark badge"""
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    bw, bh = 880, 84
    bx = (width - bw) // 2
    by = 1730  # Positioned in mobile safe zone (footer area)
    
    # 1. Soft drop shadow behind the pill
    draw.rounded_rectangle(
        [bx - 2, by + 4, bx + bw + 2, by + bh + 8],
        radius=44,
        fill=(0, 0, 0, 140)
    )
    
    # 2. Translucent glassmorphism pill container
    draw.rounded_rectangle(
        [bx, by, bx + bw, by + bh],
        radius=42,
        fill=(15, 17, 23, 220),
        outline=(255, 255, 255, 75),
        width=2
    )
    
    # Fonts
    try:
        font_btn = ImageFont.truetype('arialbd.ttf', 28)
        font_sub = ImageFont.truetype('arialbd.ttf', 26)
    except Exception:
        font_btn = ImageFont.load_default()
        font_sub = font_btn
        
    has_emoji = False
    try:
        font_emoji = ImageFont.truetype('seguiemj.ttf', 32)
        has_emoji = True
    except Exception:
        pass
        
    # --- 1. LIKE SECTION ---
    like_drawn = False
    if has_emoji:
        try:
            draw.text((bx + 55, by + 19), '👍', font=font_emoji, embedded_color=True)
            draw.text((bx + 105, by + 25), 'LIKE', font=font_btn, fill=(255, 255, 255, 245))
            like_drawn = True
        except Exception:
            like_drawn = False
            
    if not like_drawn:
        # Vector heart icon fallback
        r = 13
        cx, cy = bx + 68, by + bh // 2 - 2
        draw.ellipse([cx - r - 2, cy - r, cx + 2, cy + r], fill=(255, 60, 95, 255))
        draw.ellipse([cx - 2, cy - r, cx + r + 2, cy + r], fill=(255, 60, 95, 255))
        draw.polygon([(cx - r - 2, cy + 2), (cx + r + 2, cy + 2), (cx, cy + r + 9)], fill=(255, 60, 95, 255))
        draw.text((bx + 95, by + 25), 'LIKE', font=font_btn, fill=(255, 255, 255, 245))
        
    # Divider 1
    div1_x = bx + 265
    draw.line([(div1_x, by + 18), (div1_x, by + bh - 18)], fill=(255, 255, 255, 55), width=2)
    
    # --- 2. SHARE SECTION ---
    pts_share = [
        (bx + 325 + 8, by + bh // 2 - 16),
        (bx + 325 + 22, by + bh // 2),
        (bx + 325 + 8, by + bh // 2 + 16),
        (bx + 325 + 8, by + bh // 2 + 7),
        (bx + 325 - 16, by + bh // 2 + 7),
        (bx + 325 - 16, by + bh // 2 - 3),
        (bx + 325 + 8, by + bh // 2 - 3),
    ]
    draw.polygon(pts_share, fill=(45, 195, 255, 255))
    draw.text((bx + 360, by + 25), 'SHARE', font=font_btn, fill=(255, 255, 255, 245))
    
    # Divider 2
    div2_x = bx + 540
    draw.line([(div2_x, by + 18), (div2_x, by + bh - 18)], fill=(255, 255, 255, 55), width=2)
    
    # --- 3. SUBSCRIBE BUTTON ---
    sub_x = bx + 555
    sub_w = 310
    sub_h = 60
    sub_y = by + (bh - sub_h) // 2
    
    # YouTube Red badge
    draw.rounded_rectangle(
        [sub_x, sub_y, sub_x + sub_w, sub_y + sub_h],
        radius=30,
        fill=(225, 25, 35, 245),
        outline=(255, 120, 120, 120),
        width=1
    )
    
    bell_drawn = False
    if has_emoji:
        try:
            draw.text((sub_x + 22, sub_y + 11), '🔔', font=font_emoji, embedded_color=True)
            draw.text((sub_x + 72, sub_y + 14), 'SUBSCRIBE', font=font_sub, fill=(255, 255, 255, 255))
            bell_drawn = True
        except Exception:
            bell_drawn = False
            
    if not bell_drawn:
        # Vector bell icon
        cx, cy = sub_x + 36, sub_y + sub_h // 2
        draw.ellipse([cx - 3, cy - 15, cx + 3, cy - 11], fill=(255, 255, 255, 255))
        pts_bell = [
            (cx - 9, cy + 7), (cx - 7, cy - 4), (cx - 4, cy - 11),
            (cx + 4, cy - 11), (cx + 7, cy - 4), (cx + 9, cy + 7)
        ]
        draw.polygon(pts_bell, fill=(255, 255, 255, 255))
        draw.rounded_rectangle([cx - 12, cy + 6, cx + 12, cy + 9], radius=2, fill=(255, 255, 255, 255))
        draw.ellipse([cx - 4, cy + 9, cx + 4, cy + 14], fill=(255, 255, 255, 255))
        draw.text((sub_x + 60, sub_y + 14), 'SUBSCRIBE', font=font_sub, fill=(255, 255, 255, 255))
        
    # Crop to active bounding box for ultra-fast frame blending
    pad = 12
    x1 = max(0, bx - pad)
    y1 = max(0, by - pad)
    x2 = min(width, bx + bw + pad)
    y2 = min(height, by + bh + pad + 8)
    
    crop = overlay.crop((x1, y1, x2, y2))
    crop_np = np.array(crop)
    
    bgr_crop = cv2.cvtColor(crop_np[:, :, :3], cv2.COLOR_RGB2BGR)
    alpha_crop = crop_np[:, :, 3].astype(np.float32) / 255.0
    alpha_crop = np.expand_dims(alpha_crop, axis=-1)
    
    return {
        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
        'bgr': bgr_crop,
        'alpha': alpha_crop
    }

def apply_footer_watermark(frame, watermark_data, opacity=1.0):
    """Blends the pre-computed watermark onto the target frame with optional opacity"""
    if watermark_data is None or opacity <= 0.0:
        return frame
    x1, y1 = watermark_data['x1'], watermark_data['y1']
    x2, y2 = watermark_data['x2'], watermark_data['y2']
    
    roi = frame[y1:y2, x1:x2].astype(np.float32)
    bgr = watermark_data['bgr'].astype(np.float32)
    alpha = watermark_data['alpha'] * float(opacity)
    
    blended = (1.0 - alpha) * roi + alpha * bgr
    frame[y1:y2, x1:x2] = blended.astype(np.uint8)
    return frame

def create_header_title(title="AK Kolam", width=1080, height=1920):
    """Generate high-quality header title pill badge (e.g. AK Kolam)"""
    if not title:
        return None
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    try:
        font = ImageFont.truetype('arialbd.ttf', 38)
    except Exception:
        font = ImageFont.load_default()
        
    bbox = draw.textbbox((0, 0), title, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    bw = tw + 80
    bh = 72
    bx = (width - bw) // 2
    by = 130
    
    # Soft drop shadow
    draw.rounded_rectangle([bx - 2, by + 4, bx + bw + 2, by + bh + 6], radius=36, fill=(0, 0, 0, 140))
    # Frosted glass pill body with subtle gold border
    draw.rounded_rectangle(
        [bx, by, bx + bw, by + bh],
        radius=36,
        fill=(15, 17, 23, 220),
        outline=(255, 215, 0, 160),
        width=2
    )
    
    # Center text
    tx = bx + (bw - tw) // 2
    ty = by + (bh - th) // 2 - 2
    draw.text((tx, ty), title, font=font, fill=(255, 255, 255, 250))
    
    pad = 12
    x1 = max(0, bx - pad)
    y1 = max(0, by - pad)
    x2 = min(width, bx + bw + pad)
    y2 = min(height, by + bh + pad + 6)
    
    crop = overlay.crop((x1, y1, x2, y2))
    crop_np = np.array(crop)
    bgr_crop = cv2.cvtColor(crop_np[:, :, :3], cv2.COLOR_RGB2BGR)
    alpha_crop = (crop_np[:, :, 3].astype(np.float32) / 255.0)[:, :, np.newaxis]
    
    return {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'bgr': bgr_crop, 'alpha': alpha_crop}

def load_and_prepare_hand(hand_path, target_width=380):
    """Load hand image and remove white background, resize"""
    img = cv2.imread(hand_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        # Create placeholder
        return None
    
    # If image has no alpha, remove white background
    if img.shape[2] == 3:
        # Convert white to transparent
        # Create alpha channel
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, alpha = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        # Clean alpha
        alpha = cv2.GaussianBlur(alpha, (3,3), 0)
        b,g,r = cv2.split(img)
        img = cv2.merge([b,g,r,alpha])
    
    # Resize keeping aspect
    h,w = img.shape[:2]
    scale = target_width / w
    new_w = target_width
    new_h = int(h * scale)
    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img

def overlay_hand(background, hand_img, pen_tip_pos, angle_offset=0):
    """Overlay hand so pen tip aligns with drawing position"""
    if hand_img is None:
        return background
    
    # Estimate tip offset in hand image: near bottom center
    hh, hw = hand_img.shape[:2]
    tip_in_hand = (hw//3, hh - 30)  # approx tip location in hand image
    
    # Position to place hand
    x = pen_tip_pos[0] - tip_in_hand[0]
    y = pen_tip_pos[1] - tip_in_hand[1]
    
    # Clip to background bounds
    bg_h, bg_w = background.shape[:2]
    h_hand, w_hand = hand_img.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2 = min(bg_w, x + w_hand)
    y2 = min(bg_h, y + h_hand)
    if x2 <= x1 or y2 <= y1:
        return background
    
    # Corresponding hand region
    hx1, hy1 = x1 - x, y1 - y
    hx2, hy2 = hx1 + (x2-x1), hy1 + (y2-y1)
    
    hand_crop = hand_img[hy1:hy2, hx1:hx2]
    if hand_crop.shape[2] == 4:
        alpha = (hand_crop[:,:,3].astype(np.float32) / 255.0)[:,:,np.newaxis]
        bg_roi = background[y1:y2, x1:x2].astype(np.float32)
        fg = hand_crop[:,:,:3].astype(np.float32)
        background[y1:y2, x1:x2] = ((1.0 - alpha) * bg_roi + alpha * fg).astype(np.uint8)
    else:
        background[y1:y2, x1:x2] = hand_crop[:,:,:3]
    
    return background

def render_kolam_video(dots, path, wood_path, hand_path, output_path, fps=25, line_thickness=6, show_watermark=True, title="AK Kolam", cover_image_path=None, point_colors=None, point_widths=None, progress_callback=None, drawing_speed: float = 1.2):
    """Headless renderer - exact replica of reference video with smooth continuous drawing and speed control"""
    width, height = 1080, 1920
    
    # Prepare header title (AK Kolam) and footer watermark (Subscribe, Like, Share)
    header_data = create_header_title(title, width, height) if title else None
    watermark_data = create_footer_watermark(width, height) if show_watermark else None
    
    # Load wood background and resize to 1080x1920
    wood = cv2.imread(wood_path)
    if wood is None:
        # Create procedural wood
        wood = np.zeros((height, width, 3), dtype=np.uint8)
        wood[:] = (30, 20, 15)  # dark brown base
        # Add grain
        for i in range(0, height, 4):
            cv2.line(wood, (0,i), (width,i), (45+np.random.randint(-5,5), 30+np.random.randint(-5,5), 20), 1)
    else:
        wood = cv2.resize(wood, (width, height))
    
    # Prepare hand
    hand_img = load_and_prepare_hand(hand_path, target_width=420)
    
    # Probe NVENC before choosing a codec so initialization failures are handled
    # before any output frames are consumed.
    frame_writer = _VideoFrameWriter(output_path, width, height, fps)
    frame_count = 0
    def write_frame_to_output(f_img):
        nonlocal frame_count
        frame_writer.write(f_img)
        frame_count = frame_writer.frame_count
    
    # Create base frame with dots
    base = wood.copy()
    for x,y in dots:
        cv2.circle(base, (x,y), 5, (255,255,255), -1, lineType=cv2.LINE_AA)
    
    # Drawing canvas
    canvas = base.copy()

    # Write cover teaser frames if provided (ensures YouTube Shorts displays thumbnail cover)
    if cover_image_path and os.path.exists(cover_image_path):
        cover = cv2.imread(cover_image_path)
        if cover is not None:
            cover = cv2.resize(cover, (width, height))
            cover_frames = 15  # ~0.6s teaser hook
            for c_idx in range(cover_frames):
                if c_idx >= cover_frames - 3:
                    # 3-frame quick cross-fade to blank drawing floor
                    alpha = (cover_frames - 1 - c_idx) / 3.0
                    blend = cv2.addWeighted(cover, alpha, canvas, 1.0 - alpha, 0)
                    write_frame_to_output(blend)
                else:
                    write_frame_to_output(cover)
    
    # Decompose path into continuous strokes separated by None delimiters
    strokes = []
    curr_pts = []
    curr_colors = []
    curr_widths = []

    for idx, pt in enumerate(path):
        if pt is None:
            if curr_pts:
                strokes.append({
                    'points': curr_pts,
                    'colors': curr_colors,
                    'widths': curr_widths
                })
                curr_pts = []
                curr_colors = []
                curr_widths = []
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
        strokes.append({
            'points': curr_pts,
            'colors': curr_colors,
            'widths': curr_widths
        })

    # Compute Euclidean lengths and cumulative distance for each stroke
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

    # Arc-length timing is independent of sampling density. At speed 1.0, the
    # legacy manual-path pace is about 8.85 canvas pixels per frame.
    eff_speed = max(0.01, float(drawing_speed))
    pixels_per_frame = 8.85 * eff_speed
    minimum_frames = [2 for _ in strokes]
    target_draw_frames = max(sum(minimum_frames), int(round(total_path_length / pixels_per_frame)))

    # Compute transition frame counts between independent strokes
    trans_frames = []
    for k in range(len(strokes) - 1):
        p_end = strokes[k]['points'][-1]
        p_next = strokes[k+1]['points'][0]
        gap_dist = ((p_next[0] - p_end[0])**2 + (p_next[1] - p_end[1])**2) ** 0.5
        # A lifted hand can reposition faster than it draws, while the same
        # configurable multiplier still controls the travel interval.
        transition_distance_per_frame = pixels_per_frame * 3.0
        t_f = max(2, min(30, int(math.ceil(gap_dist / transition_distance_per_frame))))
        trans_frames.append(t_f)
    total_trans_frames = sum(trans_frames)

    # Apportion frames by arc length with largest-remainder rounding. Every
    # stroke retains a small visible start/end interval, including short dots.
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

    # Draw progressively with sub-segment continuous interpolation
    for k, s in enumerate(strokes):
        pts = s['points']
        colors = s['colors']
        widths = s['widths']
        cum_dist = s['cum_dist']
        stroke_len = s['length']
        n_pts = len(pts)
        n_frames = stroke_frames[k]
        
        last_rendered_dist = 0.0
        last_rendered_pt = pts[0]
        last_rendered_idx = 0
        search_i = 1
        
        if n_pts == 1 or stroke_len < 1e-4:
            # Single-point dot stroke or zero-length stroke
            c = colors[0] if colors[0] is not None else (255, 255, 255)
            w = widths[0] if widths[0] is not None else line_thickness
            cv2.circle(canvas, pts[0], max(1, w // 2), c, -1, lineType=cv2.LINE_AA)
            for f in range(n_frames):
                tip_pos = pts[0]
                frame = canvas.copy()
                if hand_img is not None:
                    frame = overlay_hand(frame, hand_img, tip_pos)
                else:
                    cv2.circle(frame, tip_pos, 8, (255, 200, 200), -1)
                if header_data is not None:
                    frame = apply_footer_watermark(frame, header_data, opacity=1.0)
                if watermark_data is not None:
                    frame = apply_footer_watermark(frame, watermark_data, opacity=1.0)
                write_frame_to_output(frame)
                anim_frame_idx += 1
                if progress_callback and total_anim_frames > 0:
                    prog = (anim_frame_idx / total_anim_frames) * 100.0
                    progress_callback(prog, anim_frame_idx, total_anim_frames)
        else:
            for f in range(n_frames):
                if f == n_frames - 1:
                    target_dist = stroke_len
                else:
                    target_dist = ((f + 1) / float(n_frames)) * stroke_len
                
                # Advance from last_rendered_dist to target_dist
                target_i = bisect.bisect_left(cum_dist, target_dist, lo=search_i)
                target_i = min(n_pts - 1, max(1, target_i))
                search_i = target_i
                
                # Draw intermediate vertices
                for j in range(last_rendered_idx + 1, target_i):
                    c = colors[j] if colors[j] is not None else (255, 255, 255)
                    w = widths[j] if widths[j] is not None else line_thickness
                    cv2.line(canvas, last_rendered_pt, pts[j], c, w, lineType=cv2.LINE_AA)
                    last_rendered_pt = pts[j]
                    last_rendered_idx = j
                
                # Interpolate along active segment
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
                
                if curr_pt != last_rendered_pt:
                    c = colors[target_i] if colors[target_i] is not None else (255, 255, 255)
                    w = widths[target_i] if widths[target_i] is not None else line_thickness
                    cv2.line(canvas, last_rendered_pt, curr_pt, c, w, lineType=cv2.LINE_AA)
                    last_rendered_pt = curr_pt
                
                # Keep last_rendered_idx at the last fully-traversed vertex so
                # the next frame does not re-draw segments already on the canvas.
                # target_i is the segment endpoint; if the interpolated point
                # hasn't reached it yet, the last completed vertex is target_i-1.
                last_rendered_idx = max(last_rendered_idx, target_i - 1)
                last_rendered_dist = target_dist
                tip_pos = curr_pt
                
                frame = canvas.copy()
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
                    sys.stdout.write(f"\r  -> Rendering progress: {prog:.1f}% ({anim_frame_idx}/{total_anim_frames} frames)")
                    sys.stdout.flush()
                    if progress_callback:
                        try:
                            progress_callback(prog, anim_frame_idx, total_anim_frames)
                        except Exception:
                            pass
        
        # Stroke finished: smooth pen-up repositioning transition across gap to next stroke
        if k < len(strokes) - 1:
            next_start = strokes[k+1]['points'][0]
            curr_tip = strokes[k]['points'][-1]
            n_trans = trans_frames[k]
            for tf in range(n_trans):
                tau = float(tf + 1) / float(n_trans)
                ease = tau * tau * (3.0 - 2.0 * tau)
                tx = int(round((1.0 - ease) * curr_tip[0] + ease * next_start[0]))
                ty = int(round((1.0 - ease) * curr_tip[1] + ease * next_start[1]))
                trans_tip = (tx, ty)
                
                # Canvas untouched during pen-up transition
                frame = canvas.copy()
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

    # Hold final frame for 1 second (25 frames)
    final_frame = canvas.copy()
    if header_data is not None:
        final_frame = apply_footer_watermark(final_frame, header_data, opacity=1.0)
    if watermark_data is not None:
        final_frame = apply_footer_watermark(final_frame, watermark_data, opacity=1.0)
    for _ in range(fps):
        write_frame_to_output(final_frame)
    
    frame_writer.close()
        
    print(f"\nVideo saved: {output_path}, {frame_count} frames, {frame_count/fps:.1f}s")
    return output_path
