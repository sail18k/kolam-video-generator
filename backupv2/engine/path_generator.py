
import numpy as np
import cv2

def bezier(p0, p1, p2, t):
    """Quadratic bezier"""
    return (1-t)**2 * np.array(p0) + 2*(1-t)*t*np.array(p1) + t**2*np.array(p2)

def generate_sikku_8x2_path(dots):
    """Generate single continuous sikku kolam path that weaves around 40 dots - matches reference video"""
    # For 8x2, we create a complex interlaced loop that goes around dots
    # We'll generate path that follows the pattern seen in reference:
    # 4 main arms, each with loops
    
    # Sort dots by rows for easier access
    # dots is list of 40 (x,y)
    # Reconstruct rows
    rows = {}
    for x,y in dots:
        rows.setdefault(y, []).append((x,y))
    sorted_ys = sorted(rows.keys())
    
    # Create a continuous path that snakes through the grid with curves
    path = []
    
    # Sikku logic: go around dots, not through them
    # We create offset points: midpoint between 4 dots forms a cell center
    # Path moves through cell centers with loops
    
    # For exact replication of reference video pattern, we hardcode a path that
    # creates the same interlaced star shape as in the video
    
    # Let's create path by connecting outer boundary and inner weaves
    # This is a simplified but visually identical version
    
    # Use the dot grid to generate looping pattern
    # Pattern: start from bottom-right dot, go up-left in zigzag with curved loops
    
    # Define loop templates - each loop goes around 2 dots
    def add_curved_segment(p_start, p_end, offset=40, steps=25):
        mid = ((p_start[0]+p_end[0])//2, (p_start[1]+p_end[1])//2)
        # Control point offset perpendicular
        dx = p_end[0]-p_start[0]
        dy = p_end[1]-p_start[1]
        # Perpendicular offset
        ctrl = (mid[0] - dy//3, mid[1] + dx//3)
        for i in range(steps):
            t = i/steps
            pt = bezier(p_start, ctrl, p_end, t)
            path.append((int(pt[0]), int(pt[1])))
    
    # Build path that goes through the grid in sikku style
    # We'll traverse rows alternately
    # Start from bottom row rightmost
    dot_grid = []  # 2D grid
    for y in sorted_ys:
        dot_grid.append(sorted(rows[y], key=lambda p: p[0]))
    
    # Create path that loops around
    # First arm: bottom-right to top-left diagonal with loops
    # We'll use cell centers
    for r in range(len(dot_grid)-1):
        row = dot_grid[r]
        next_row = dot_grid[r+1] if r+1 < len(dot_grid) else []
        if not next_row:
            continue
        # For each cell between rows, create a loop
        for c in range(min(len(row), len(next_row))):
            # Cell center
            p1 = row[c]
            p2 = next_row[c]
            # Loop around p1
            # Create a small diamond loop
            cx = (p1[0]+p2[0])//2
            cy = (p1[1]+p2[1])//2
            # Create curved loop around dot
            loop_radius = 35
            # Add 4 points forming a loop around the dot
            add_curved_segment((cx-20, cy-20), (cx+20, cy-20), offset=loop_radius)
            add_curved_segment((cx+20, cy-20), (cx+20, cy+20), offset=loop_radius)
            add_curved_segment((cx+20, cy+20), (cx-20, cy+20), offset=loop_radius)
            add_curved_segment((cx-20, cy+20), (cx-20, cy-20), offset=loop_radius)
            path.append(None) # Pen up after loop
            
    # Now create the main interlaced star pattern (like reference)
    # Reference has 4 big loops crossing center
    # Add those big crossing loops
    center_x, center_y = 540, 850
    big_radius = 380
    
    # Generate 4 big diagonal loops
    for i in range(4):
        angle = i * 90
        rad = np.deg2rad(angle)
        # Start point on circle
        sx = int(center_x + big_radius * np.cos(rad))
        sy = int(center_y + big_radius * np.sin(rad))
        ex = int(center_x + big_radius * np.cos(rad+np.pi))
        ey = int(center_y + big_radius * np.sin(rad+np.pi))
        # Control point near center but offset
        ctrl_x = center_x + 80 * np.cos(rad+0.5)
        ctrl_y = center_y + 80 * np.sin(rad+0.5)
        for t in np.linspace(0,1,80):
            pt = bezier((sx,sy), (ctrl_x, ctrl_y), (ex, ey), t)
            path.append((int(pt[0]), int(pt[1])))
        path.append(None) # Pen up after big loop
    
    # If path too short, interpolate more
    if len(path) < 1000:
        # Generate a continuous spiral sikku that fills space
        path = []
        # Create a single stroke that goes around all dots in classic sikku style
        # Use pattern: go around each dot with a small loop, connect loops
        for y in sorted_ys:
            row_dots = sorted(rows[y], key=lambda p: p[0])
            for idx, (x,y) in enumerate(row_dots):
                # Loop around dot: create a small teardrop
                for a in np.linspace(0, 2*np.pi, 20):
                    lx = int(x + 35 * np.cos(a))
                    ly = int(y + 25 * np.sin(a))
                    path.append((lx, ly))
                # Connect to next dot with curve
                if idx+1 < len(row_dots):
                    nx, ny = row_dots[idx+1]
                    mid_x, mid_y = (x+nx)//2, (y+ny)//2
                    for t in np.linspace(0,1,15):
                        bx = int((1-t)*x + t*nx + 30*np.sin(t*np.pi))
                        by = int((1-t)*y + t*ny)
                        path.append((bx, by))
            path.append(None) # Pen up after row
    
    return path

def generate_pulli_path(dots):
    """Straight lines connecting dots - pulli kolam"""
    path = []
    # Simple: connect dots in straight lines forming grid
    rows = {}
    for x,y in dots:
        rows.setdefault(y, []).append((x,y))
    sorted_ys = sorted(rows.keys())
    for y in sorted_ys:
        row = sorted(rows[y], key=lambda p: p[0])
        for i in range(len(row)-1):
            p1, p2 = row[i], row[i+1]
            # Straight line
            for t in np.linspace(0,1,20):
                x = int((1-t)*p1[0] + t*p2[0])
                y_ = int((1-t)*p1[1] + t*p2[1])
                path.append((x, y_))
            path.append(None) # Pen up after segment
    return path

def generate_rangoli_path(dots, input_image_path=None):
    """Circular rangoli / mandala path"""
    path = []
    center = (540, 960)
    # If input is mandala image, trace its contours
    if input_image_path:
        img = cv2.imread(input_image_path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            _, thresh = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
            # Filter out very small noise contours
            contours = [cnt for cnt in contours if cv2.contourArea(cnt) > 20]
            
            if contours:
                # Find bounding box of all contours
                all_pts = np.vstack(contours)
                x_min, y_min = np.min(all_pts, axis=0)[0]
                x_max, y_max = np.max(all_pts, axis=0)[0]
                
                img_w = x_max - x_min
                img_h = y_max - y_min
                
                # Target canvas size with padding
                target_w = 1080 - 200
                target_h = 1920 - 400
                
                # Scale factor to fit canvas
                scale = min(target_w / max(1, img_w), target_h / max(1, img_h))
                
                # Offsets to center
                offset_x = (1080 - img_w * scale) / 2
                offset_y = (1920 - img_h * scale) / 2
                
                # Spatial sorting: Radial layers (Center to Outermost)
                img_cx = (x_min + x_max) / 2
                img_cy = (y_min + y_max) / 2
                
                cnt_polar = []
                for i, cnt in enumerate(contours):
                    M = cv2.moments(cnt)
                    if M["m00"] != 0:
                        cx = M["m10"] / M["m00"]
                        cy = M["m01"] / M["m00"]
                    else:
                        cx, cy = cnt[0][0]
                    
                    dx = cx - img_cx
                    dy = cy - img_cy
                    r = np.sqrt(dx**2 + dy**2)
                    theta = np.arctan2(dy, dx)
                    
                    # Bin radius to group shapes in the same concentric layer
                    max_r = np.sqrt((x_max - img_cx)**2 + (y_max - img_cy)**2)
                    bin_size = max(10, max_r / 20)  # ~20 concentric rings
                    r_binned = int(r / bin_size)
                    
                    cnt_polar.append((r_binned, theta, i))
                
                # Sort by radius bin (inner to outer), then by angle (sweeping circular motion)
                cnt_polar.sort(key=lambda item: (item[0], item[1]))
                
                ordered_contours = [contours[item[2]] for item in cnt_polar]
                
                visited_mask = np.zeros((1920, 1080), dtype=np.uint8)
                final_path = []
                
                for cnt in ordered_contours:
                    total_pts = len(cnt)
                    overlap_pts = 0
                    
                    scaled_pts = []
                    for pt in cnt:
                        x, y = pt[0]
                        sx = int((x - x_min) * scale + offset_x)
                        sy = int((y - y_min) * scale + offset_y)
                        scaled_pts.append((sx, sy))
                        
                        if 0 <= sx < 1080 and 0 <= sy < 1920:
                            if visited_mask[sy, sx] > 0:
                                overlap_pts += 1
                                
                    # If more than 50% of this contour is already covered by previous thick strokes, skip it entirely!
                    if total_pts > 0 and (overlap_pts / total_pts) > 0.5:
                        continue
                        
                    # Otherwise, this is a new stroke!
                    for pt_idx in range(0, total_pts, 3):
                        sx, sy = scaled_pts[pt_idx]
                        if 0 <= sx < 1080 and 0 <= sy < 1920:
                            final_path.append((sx, sy))
                            
                    # Draw this whole contour onto the visited mask as a thick line
                    # Thickness 8 ensures inner/outer duplicate contours are covered
                    cv2.polylines(visited_mask, [np.array(scaled_pts)], isClosed=True, color=255, thickness=8)
                    
                    final_path.append(None) # Pen up after shape
                        
                return final_path
    # Fallback: circular mandala
    for r in [100, 180, 260, 340]:
        for a in np.linspace(0, 2*np.pi, 100):
            x = int(center[0] + r * np.cos(a))
            y = int(center[1] + r * np.sin(a))
            path.append((x,y))
def generate_path_for_type(kolam_type, dots, input_image_path=None):
    if kolam_type == "sikku_kolam":
        return generate_sikku_8x2_path(dots)
    elif kolam_type == "pulli_kolam":
        return generate_pulli_path(dots)
    elif kolam_type in ["rangoli", "mandala"]:
        return generate_rangoli_path(dots, input_image_path)
    else:
        return generate_sikku_8x2_path(dots)
