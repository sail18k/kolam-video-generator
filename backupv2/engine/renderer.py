import cv2
import numpy as np
import os
from pathlib import Path

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

def render_kolam_video(dots, path, wood_path, hand_path, output_path, fps=25, line_thickness=6):
    """Headless renderer - exact replica of reference video"""
    width, height = 1080, 1920
    
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
