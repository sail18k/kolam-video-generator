import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Auspicious Traditional Indian Rangoli / Kolam Color Palette (in BGR format)
RANGOLI_PALETTE = np.array([
    [42, 28, 228],   # Kumkum Crimson Red
    [28, 218, 255],  # Turmeric Gold Yellow
    [30, 132, 255],  # Saffron / Marigold Orange
    [185, 55, 248],  # Lotus Pink / Magenta
    [218, 122, 18],  # Peacock Royal Blue
    [65, 195, 48],   # Parrot / Lime Green
    [242, 202, 32],  # Vibrant Sky Cyan
    [162, 42, 132],  # Festive Royal Purple
    [32, 168, 255],  # Deep Radiant Amber
    [125, 225, 80],  # Fresh Mint Green
], dtype=np.uint8)


def get_title_for_kolam(kolam_type, grid="none"):
    """Format catchy, professional YouTube Shorts title badge text"""
    clean_type = (kolam_type or "kolam").replace("_", " ").strip().title()
    if "Mandala" in clean_type:
        return "MANDALA KOLAM DESIGN"
    elif "Rangoli" in clean_type:
        return "BEAUTIFUL RANGOLI KOLAM"
    elif "Sikku" in clean_type:
        grid_str = f" | {grid}" if grid and grid != "none" else ""
        return f"SIKKU KOLAM{grid_str}"
    elif "Pulli" in clean_type:
        grid_str = f" | {grid}" if grid and grid != "none" else ""
        return f"PULLI KOLAM{grid_str}"
    else:
        return f"{clean_type.upper()} KOLAM DESIGN"


def colorize_kolam_sketch(sketch_img):
    """
    Naturally fills sketch cells with harmonious Kolam/Rangoli powder colors,
    incorporating radial symmetry, 3D powder depth, and raised white rice flour lines.
    """
    gray = cv2.cvtColor(sketch_img, cv2.COLOR_BGR2GRAY)
    
    # Auto-detect line/background polarity
    if gray.mean() > 128:
        # Dark lines on light background
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    else:
        # Light lines on dark background
        _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
        
    coords = cv2.findNonZero(thresh)
    if coords is None:
        # Fallback if thresholding found nothing
        return sketch_img, np.full(sketch_img.shape[:2], 255, dtype=np.uint8)

    x, y, w, h = cv2.boundingRect(coords)
    cx, cy = x + w / 2.0, y + h / 2.0
    max_radius = max(1.0, max(w, h) / 2.0)

    # Close small gaps in sketch lines to keep cells well-defined
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closed_lines = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    cells = cv2.bitwise_not(closed_lines)
    
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cells)

    lut = np.zeros((num_labels, 3), dtype=np.uint8)
    max_label = np.argmax(stats[:, cv2.CC_STAT_AREA])

    # Assign harmonious colors to internal cells
    filled_any = False
    for label in range(1, num_labels):
        if label == max_label:
            continue
        area = stats[label, cv2.CC_STAT_AREA]
        # Ignore tiny speckles or huge outer canvas
        if area < 8 or area > (sketch_img.shape[0] * sketch_img.shape[1] * 0.45):
            continue

        c_x, c_y = centroids[label]
        dist = np.sqrt((c_x - cx) ** 2 + (c_y - cy) ** 2)
        angle = np.arctan2(c_y - cy, c_x - cx) % (2 * np.pi)

        # Concentric ring index
        ring = int((dist / max_radius) * 8.0)
        # Symmetrical sector alternation
        sector = int((angle / (2 * np.pi)) * 8) % 2

        color_idx = (ring * 2 + sector) % len(RANGOLI_PALETTE)
        lut[label] = RANGOLI_PALETTE[color_idx]
        filled_any = True

    # If the sketch didn't have enclosed cells (e.g., pure open lines),
    # generate a vibrant rainbow powder stroke coloring
    if not filled_any:
        colored = np.zeros_like(sketch_img)
        # Create multi-colored radial gradient for lines
        Y, X = np.ogrid[:sketch_img.shape[0], :sketch_img.shape[1]]
        dist_grid = np.sqrt((X - cx)**2 + (Y - cy)**2)
        angle_grid = np.arctan2(Y - cy, X - cx) % (2 * np.pi)
        color_map_idx = ((dist_grid / max_radius * 6.0).astype(int) + (angle_grid / (2*np.pi) * 4).astype(int)) % len(RANGOLI_PALETTE)
        colored[thresh > 0] = RANGOLI_PALETTE[color_map_idx[thresh > 0]]
        art_alpha_u8 = thresh.copy()
        return colored, art_alpha_u8

    # Vectorized color assignment
    colored = lut[labels]

    # 3D powder depth: distance transform gives raised powder cushion appearance
    dt = cv2.distanceTransform(cells, cv2.DIST_L2, 3)
    dt_shade = np.clip(0.82 + 0.35 * (dt / 8.0), 0.82, 1.15)[:, :, np.newaxis]
    colored = np.clip(colored.astype(np.float32) * dt_shade, 0, 255).astype(np.uint8)

    # Fine powder micro-texture
    noise = np.random.normal(0, 3.0, colored.shape).astype(np.float32)
    colored = np.clip(colored.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # Alpha mask (active colored artwork area)
    art_alpha = (labels != max_label) | (thresh > 0)
    art_alpha_u8 = art_alpha.astype(np.uint8) * 255

    # Raised white rice flour powder outlines
    colored[thresh > 0] = [255, 255, 255]

    return colored, art_alpha_u8


def generate_kolam_thumbnail(
    input_image_path,
    output_thumbnail_path,
    kolam_type="kolam",
    grid="none",
    wood_path="engine/assets/wood.jpg",
    dots=None,
    width=1080,
    height=1920,
    title="AK Kolam"
):
    """
    Creates a captivating, high-CTR YouTube Short thumbnail (1080x1920, 9:16)
    with the input Kolam naturally filled with vibrant traditional rangoli colors,
    3D powder texture, realistic drop shadows, and eye-catching modern badges.
    """
    if not os.path.exists(input_image_path):
        raise FileNotFoundError(f"Input image not found: {input_image_path}")

    sketch = cv2.imread(input_image_path)
    if sketch is None:
        raise ValueError(f"Could not load image: {input_image_path}")

    # 1. Colorize the Kolam artwork
    colored_art, alpha_mask = colorize_kolam_sketch(sketch)

    # 2. Crop tightly around the artwork
    coords = cv2.findNonZero(alpha_mask)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        pad = 16
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(sketch.shape[1], x + w + pad)
        y2 = min(sketch.shape[0], y + h + pad)
        art_crop = colored_art[y1:y2, x1:x2]
        alpha_crop = alpha_mask[y1:y2, x1:x2]
    else:
        art_crop = colored_art
        alpha_crop = alpha_mask

    # 3. Prepare 1080x1920 Canvas
    if wood_path and os.path.exists(wood_path):
        wood = cv2.imread(wood_path)
        thumb = cv2.resize(wood, (width, height))
    else:
        # Fallback rich dark teakwood base
        thumb = np.full((height, width, 3), 32, dtype=np.uint8)

    # 4. Center Spotlight & Radial Vignette (Highlights the Kolam dramatically)
    Y, X = np.ogrid[:height, :width]
    center_y, center_x = height // 2, width // 2
    dist_from_center = np.sqrt((X - center_x) ** 2 + (Y - center_y) ** 2)
    max_d = np.sqrt((width / 2.0) ** 2 + (height / 2.0) ** 2)
    spotlight = 1.30 - 0.60 * (dist_from_center / max_d)
    spotlight = np.clip(spotlight, 0.40, 1.30)[:, :, np.newaxis]
    thumb = np.clip(thumb.astype(np.float32) * spotlight, 0, 255).astype(np.uint8)

    # 5. Scale Artwork to fit ~82% width of frame
    target_w = int(width * 0.82)
    scale = target_w / max(1, art_crop.shape[1])
    scaled_w = int(art_crop.shape[1] * scale)
    scaled_h = int(art_crop.shape[0] * scale)

    # Keep within vertical safe bounds (max 1160px height)
    max_h = int(height * 0.60)
    if scaled_h > max_h:
        scale = max_h / float(art_crop.shape[0])
        scaled_w = int(art_crop.shape[1] * scale)
        scaled_h = int(art_crop.shape[0] * scale)

    art_scaled = cv2.resize(art_crop, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
    alpha_scaled = cv2.resize(alpha_crop, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)

    pos_x = (width - scaled_w) // 2
    pos_y = center_y - (scaled_h // 2)

    # 6. Realistic 3D Drop Shadow under Kolam onto Floor
    shadow = cv2.GaussianBlur(alpha_scaled, (45, 45), 0).astype(np.float32) / 255.0
    sy1 = max(0, pos_y + 14)
    sy2 = min(height, sy1 + scaled_h)
    sx1 = max(0, pos_x + 4)
    sx2 = min(width, sx1 + scaled_w)
    sh = sy2 - sy1
    sw = sx2 - sx1
    if sh > 0 and sw > 0:
        sh_mask = shadow[:sh, :sw, np.newaxis]
        thumb[sy1:sy2, sx1:sx2] = (thumb[sy1:sy2, sx1:sx2] * (1.0 - 0.65 * sh_mask)).astype(np.uint8)

    # 7. Warm Golden Halo Glow behind Artwork
    glow = cv2.GaussianBlur(alpha_scaled, (75, 75), 0).astype(np.float32) / 255.0
    gy1 = max(0, pos_y)
    gy2 = min(height, pos_y + scaled_h)
    gx1 = max(0, pos_x)
    gx2 = min(width, pos_x + scaled_w)
    gh = gy2 - gy1
    gw = gx2 - gx1
    if gh > 0 and gw > 0:
        g_mask = glow[:gh, :gw, np.newaxis]
        gold_glow = np.full((gh, gw, 3), [15, 120, 240], dtype=np.float32)
        thumb[gy1:gy2, gx1:gx2] = np.clip(
            thumb[gy1:gy2, gx1:gx2].astype(np.float32) + gold_glow * (0.28 * g_mask),
            0,
            255
        ).astype(np.uint8)

    # 8. Composite Kolam Artwork onto Floor Canvas
    a_norm = (alpha_scaled.astype(np.float32) / 255.0)[:, :, np.newaxis]
    roi = thumb[pos_y : pos_y + scaled_h, pos_x : pos_x + scaled_w].astype(np.float32)
    blended = (1.0 - a_norm) * roi + a_norm * art_scaled.astype(np.float32)
    thumb[pos_y : pos_y + scaled_h, pos_x : pos_x + scaled_w] = np.clip(blended, 0, 255).astype(np.uint8)

    # 9. Draw crisp dots if dots pattern provided
    if dots:
        # Scale and center dots matching artwork position
        pass  # Sketch outline already contains the rendered structure

    # 10. Modern Typography & YouTube Shorts Callouts (using PIL)
    thumb_pil = Image.fromarray(cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(thumb_pil)

    try:
        font_title = ImageFont.truetype("arialbd.ttf", 44)
        font_sub = ImageFont.truetype("arialbd.ttf", 30)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = font_title

    # Top Title Badge (AK Kolam)
    title_text = title if title else "AK Kolam"
    bbox_t = draw.textbbox((0, 0), title_text, font=font_title)
    t_w = bbox_t[2] - bbox_t[0]
    t_h = bbox_t[3] - bbox_t[1]
    badge_w = t_w + 90
    badge_h = 76
    bx = (width - badge_w) // 2
    by = 130

    # Top Drop shadow & pill body
    draw.rounded_rectangle([bx, by + 4, bx + badge_w, by + badge_h + 4], radius=38, fill=(0, 0, 0, 160))
    draw.rounded_rectangle(
        [bx, by, bx + badge_w, by + badge_h],
        radius=38,
        fill=(18, 20, 28, 225),
        outline=(255, 215, 0, 160),
        width=2
    )
    tx = bx + (badge_w - t_w) // 2
    ty = by + (badge_h - t_h) // 2 - 2
    draw.text((tx, ty), title_text, font=font_title, fill=(255, 245, 220))

    # Bottom Pill Badge: "EASY STEP-BY-STEP TUTORIAL"
    bot_text = "EASY STEP-BY-STEP TUTORIAL"
    bbox_b = draw.textbbox((0, 0), bot_text, font=font_sub)
    b_w = bbox_b[2] - bbox_b[0]
    bb_w = b_w + 70
    bb_h = 62
    bbx = (width - bb_w) // 2
    bby = 1730

    # Bottom Drop shadow & pill body
    draw.rounded_rectangle([bbx, bby + 4, bbx + bb_w, bby + bb_h + 4], radius=31, fill=(0, 0, 0, 160))
    draw.rounded_rectangle(
        [bbx, bby, bbx + bb_w, bby + bb_h],
        radius=31,
        fill=(210, 30, 45, 235),
        outline=(255, 255, 255, 120),
        width=2
    )
    draw.text((bbx + 35, bby + 13), bot_text, font=font_sub, fill=(255, 255, 255))

    # Convert back to BGR and save
    final_thumbnail = cv2.cvtColor(np.array(thumb_pil), cv2.COLOR_RGB2BGR)
    os.makedirs(os.path.dirname(os.path.abspath(output_thumbnail_path)), exist_ok=True)
    cv2.imwrite(output_thumbnail_path, final_thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 95])

    return output_thumbnail_path
