import cv2
import numpy as np
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

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
    
    # Pen tip is at bottom of hand image (approx)
    # In our hand image, pen tip is at bottom-left
    # We want to align tip to pen_tip_pos
    
    # Estimate tip offset in hand image: near bottom center
    hh, hw = hand_img.shape[:2]
    tip_in_hand = (hw//3, hh - 30)  # approx tip location in hand image
    
    # Position to place hand
    x = pen_tip_pos[0] - tip_in_hand[0]
    y = pen_tip_pos[1] - tip_in_hand[1]
    
    # Clip to background bounds
    bg_h, bg_w = background.shape[:2]
    
    # Overlay with alpha blending
    for c in range(3):
        # Get region
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(bg_w, x+hw), min(bg_h, y+hh)  # Note: hand w/h swapped? Actually hw is width
        # Correct: hand_img shape is (h,w,4)
        h_hand, w_hand = hand_img.shape[:2]
        x2 = min(bg_w, x + w_hand)
        y2 = min(bg_h, y + h_hand)
        if x2 <= x1 or y2 <= y1:
            continue
        # Corresponding hand region
        hx1, hy1 = x1 - x, y1 - y
        hx2, hy2 = hx1 + (x2-x1), hy1 + (y2-y1)
        
        hand_crop = hand_img[hy1:hy2, hx1:hx2]
        if hand_crop.shape[2] == 4:
            alpha = hand_crop[:,:,3] / 255.0
            for ch in range(3):
                background[y1:y2, x1:x2, ch] = (1-alpha)*background[y1:y2, x1:x2, ch] + alpha*hand_crop[:,:,ch]
        else:
            background[y1:y2, x1:x2] = hand_crop[:,:,:3]
    
    return background

def render_kolam_video(dots, path, wood_path, hand_path, output_path, fps=25, line_thickness=6, show_watermark=True):
    """Headless renderer - exact replica of reference video"""
    width, height = 1080, 1920
    
    # Prepare footer watermark (Subscribe, Like, Share)
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
    
    # Video writer - using ffmpeg with GPU acceleration if available
    import subprocess
    
    ffmpeg_cmd = [
        'ffmpeg',
        '-y', # Overwrite
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{width}x{height}',
        '-pix_fmt', 'bgr24',
        '-r', str(fps),
        '-i', '-', # Input from stdin
        '-c:v', 'h264_nvenc', # GPU Encoder
        '-preset', 'p6',
        '-b:v', '8M',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
    
    use_ffmpeg = False
    try:
        process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        use_ffmpeg = True
        print("Using FFmpeg with GPU acceleration (h264_nvenc)")
    except Exception as e:
        print(f"Failed to start FFmpeg, falling back to OpenCV: {e}")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # Create base frame with dots
    base = wood.copy()
    for x,y in dots:
        cv2.circle(base, (x,y), 5, (255,255,255), -1, lineType=cv2.LINE_AA)
    
    # Drawing canvas
    canvas = base.copy()
    
    # For smooth drawing, dynamically set frames based on path length
    total_points = len(path)
    # Draw at a constant speed (e.g., 5 points per frame)
    points_per_frame = 5
    target_frames = max(100, total_points // points_per_frame)
    
    frame_count = 0
    last_idx = 0
    
    # Draw progressively
    for frame_idx in range(target_frames):
        # Calculate how many points to draw in this frame
        current_idx = min(int((frame_idx + 1) * total_points / target_frames), total_points)
        
        # Draw the segments for this frame
        for i in range(last_idx, current_idx):
            if i > 0:
                p1 = path[i-1]
                p2 = path[i]
                if p1 is not None and p2 is not None:
                    cv2.line(canvas, p1, p2, (255,255,255), line_thickness, lineType=cv2.LINE_AA)
                
        # Write frame if we advanced the point
        if current_idx > 0:
            frame = canvas.copy()
            tip_pos = path[current_idx - 1]
            if tip_pos is None:
                # Fallback to the last valid position
                for k in range(current_idx - 1, -1, -1):
                    if path[k] is not None:
                        tip_pos = path[k]
                        break
            
            # Overlay hand at current tip
            if tip_pos is not None:
                if hand_img is not None:
                    frame = overlay_hand(frame, hand_img, tip_pos)
                else:
                    # Draw small pen indicator if no hand
                    cv2.circle(frame, tip_pos, 8, (255, 200, 200), -1)
            
            # Apply footer watermark (Like, Share, Subscribe)
            if watermark_data is not None:
                fade = min(1.0, (frame_count + 1) / 15.0) if frame_count < 15 else 1.0
                frame = apply_footer_watermark(frame, watermark_data, opacity=fade)
            
            if use_ffmpeg:
                process.stdin.write(frame.tobytes())
            else:
                out.write(frame)
            frame_count += 1
            
        # Print progress every 5%
        if frame_idx % max(1, target_frames // 20) == 0 or frame_idx == target_frames - 1:
            progress = (frame_idx + 1) / target_frames * 100
            import sys
            sys.stdout.write(f"\r  -> Rendering progress: {progress:.1f}% ({frame_idx+1}/{target_frames} frames)")
            sys.stdout.flush()
            
        last_idx = current_idx
        if current_idx >= total_points:
            break
    
    # Hold final frame for 1 second (25 frames)
    final_frame = canvas.copy()
    if watermark_data is not None:
        final_frame = apply_footer_watermark(final_frame, watermark_data, opacity=1.0)
    if use_ffmpeg:
        for _ in range(fps):
            process.stdin.write(final_frame.tobytes())
            frame_count += 1
        process.stdin.close()
        process.wait()
    else:
        for _ in range(fps):
            out.write(final_frame)
            frame_count += 1
        out.release()
        
    print(f"\nVideo saved: {output_path}, {frame_count} frames, {frame_count/fps:.1f}s")
    return output_path
