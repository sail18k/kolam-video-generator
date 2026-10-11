
import numpy as np

def generate_8x2_dots(width=1080, height=1920):
    """Generate exact 40 dots like reference video - diamond 8x2 pattern"""
    dots = []
    # Row definition for 8x2: [2,4,6,8,8,6,4,2] = 40 dots
    rows = [2,4,6,8,8,6,4,2]
    spacing_x = 110
    spacing_y = 110
    center_x = width // 2
    start_y = 480  # top offset like reference
    
    for r_idx, count in enumerate(rows):
        y = start_y + r_idx * spacing_y
        # Center this row
        total_width = (count - 1) * spacing_x
        start_x = center_x - total_width // 2
        for c in range(count):
            x = start_x + c * spacing_x
            dots.append((int(x), int(y)))
    return dots

def generate_custom_dots(grid_type, width=1080, height=1920):
    if grid_type == "none":
        return []
    elif grid_type == "8x2" or grid_type == "8-2":
        return generate_8x2_dots(width, height)
    elif grid_type == "6x2":
        rows = [2,4,6,6,4,2]
        # similar logic
        dots=[]
        spacing_x=120
        spacing_y=120
        center_x=width//2
        start_y=550
        for r_idx, count in enumerate(rows):
            y=start_y + r_idx*spacing_y
            total_width=(count-1)*spacing_x
            start_x=center_x - total_width//2
            for c in range(count):
                x=start_x + c*spacing_x
                dots.append((int(x), int(y)))
        return dots
    else:
        return generate_8x2_dots(width, height)
