import os
import cv2
import numpy as np


def analyze_artwork_motifs(image_path, kolam_type="auto", grid="none", dots=None):
    """
    Analyzes the visual contours, geometry, and symmetry of the Kolam sketch
    to detect specific artistic motifs, symmetry order, and construction style.
    """
    if not image_path or not os.path.exists(image_path):
        return {
            "motif": "general",
            "symmetry": 4,
            "has_dots": False,
            "aspect": 1.0,
            "style": kolam_type or "kolam"
        }

    img = cv2.imread(image_path)
    if img is None:
        return {
            "motif": "general",
            "symmetry": 4,
            "has_dots": False,
            "aspect": 1.0,
            "style": kolam_type or "kolam"
        }

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gray.mean() > 128:
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    else:
        _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)

    coords = cv2.findNonZero(thresh)
    if coords is None:
        return {
            "motif": "general",
            "symmetry": 4,
            "has_dots": False,
            "aspect": 1.0,
            "style": kolam_type or "kolam"
        }

    x, y, w, h = cv2.boundingRect(coords)
    cx, cy = x + w / 2.0, y + h / 2.0
    aspect = w / float(max(1, h))

    contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # 1. Feature scoring
    bell_score = 0
    lotus_score = 0
    small_blobs = 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 40:
            if 10 < area < 350:
                small_blobs += 1
            continue

        hull = cv2.convexHull(cnt)
        hull_area = max(1.0, cv2.contourArea(hull))
        solidity = area / hull_area
        bx, by, bw, bh = cv2.boundingRect(cnt)
        b_aspect = bw / float(max(1, bh))

        # Bell motif check: flared trapezoid shape (top narrower than bottom)
        if 0.55 < b_aspect < 1.65 and 0.35 < solidity < 0.75 and 400 < area < 60000:
            top_half = thresh[by : by + bh // 2, bx : bx + bw]
            bot_half = thresh[by + bh // 2 : by + bh, bx : bx + bw]
            if np.count_nonzero(bot_half) > np.count_nonzero(top_half) * 1.25:
                bell_score += 1

        # Lotus petal check: elongated pointed radiating lobes
        if (1.4 < b_aspect < 4.5 or 0.22 < b_aspect < 0.7) and 0.45 < solidity < 0.88 and area > 250:
            lotus_score += 1

    # 2. Polar rotational symmetry
    pts = coords.reshape(-1, 2)
    angles = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx) % (2 * np.pi)
    hist, _ = np.histogram(angles, bins=72)
    fft = np.abs(np.fft.rfft(hist - np.mean(hist)))
    sym_order = int(np.argmax(fft[2:16]) + 2) if len(fft) > 16 else 4

    # Determine primary motif
    has_grid = bool(grid and grid != "none" and grid != "auto")
    if dots and len(dots) > 0:
        has_grid = True

    if has_grid and kolam_type == "sikku_kolam":
        motif = "sikku"
    elif has_grid and kolam_type == "pulli_kolam":
        motif = "pulli"
    elif bell_score >= 3:
        motif = "bell"
    elif lotus_score >= 25 or sym_order in [6, 8, 12]:
        motif = "lotus"
    elif kolam_type == "mandala" or 0.88 < aspect < 1.15:
        motif = "mandala"
    elif lotus_score > 10:
        motif = "flower"
    else:
        motif = "rangoli"

    return {
        "motif": motif,
        "symmetry": sym_order,
        "has_dots": has_grid,
        "bell_score": bell_score,
        "lotus_score": lotus_score,
        "aspect": aspect,
        "style": kolam_type
    }


def build_safe_title(channel_name, title_ta, title_en, hook_en=None, max_len=95):
    """
    Constructs an engaging bilingual title that is strictly under max_len characters (YouTube limit is 100).
    """
    if hook_en:
        candidate = f"{channel_name} | {title_ta} | {title_en} ({hook_en}) #shorts"
        if len(candidate) <= max_len:
            return candidate
    candidate = f"{channel_name} | {title_ta} | {title_en} #shorts"
    if len(candidate) <= max_len:
        return candidate
    avail = max_len - len(f"{channel_name} | {title_ta} |  #shorts")
    trimmed_en = title_en[:avail].rstrip()
    if " " in trimmed_en:
        trimmed_en = trimmed_en.rsplit(" ", 1)[0]
    return f"{channel_name} | {title_ta} | {trimmed_en} #shorts"


def generate_dynamic_seo_metadata(
    image_path,
    kolam_type="auto",
    grid="none",
    dots=None,
    path=None,
    duration_seconds=30,
    channel_name="AK Kolam"
):
    """
    Dynamically generates highly engaging, SEO-optimized, non-generic YouTube Shorts
    Title, Description, and Tags (Bilingual Tamil + English) based on the exact
    motifs, symmetry, duration, and drawing style of the generated video.
    """
    analysis = analyze_artwork_motifs(image_path, kolam_type, grid, dots)
    motif = analysis["motif"]
    sym = analysis["symmetry"]
    has_dots = analysis["has_dots"]
    num_points = len(path) if path else 0

    # Pacing / Time Descriptor
    if duration_seconds <= 35:
        speed_ta = "சுலபமாக 1 நிமிடத்தில்"
        speed_en = "Quick 1-Minute"
    elif duration_seconds <= 60:
        speed_ta = "எளிதாக 2 நிமிடத்தில்"
        speed_en = "Easy Step-by-Step"
    else:
        speed_ta = "அழகான நேர்த்தியான படிமுறை"
        speed_en = "Detailed Step-by-Step"

    # Construction Descriptor (Dots vs Freehand)
    if has_dots:
        grid_clean = grid.replace("x", "-") if grid and grid != "none" else "புள்ளி"
        construct_ta = f"{grid_clean} புள்ளி"
        construct_en = f"{grid} Dots"
    else:
        construct_ta = "புள்ளி இல்லாத"
        construct_en = "Without Dots"

    # --- Motif-Specific Dynamic Content ---
    if motif == "bell":
        title_ta = f"வெள்ளிக்கிழமை பூஜை மணி கோலம் 🔔"
        title_en = f"Friday Pooja Bell Rangoli"
        hook_en = construct_en
        seo_title = build_safe_title(channel_name, title_ta, title_en, hook_en)

        desc_intro = f"""🔔 {channel_name} - Friday Special Temple Bell Rangoli | வெள்ளிக்கிழமை பூஜை மணி கோலம்

வீட்டு பூஜை அறைக்கும், வெள்ளிக்கிழமை வழிபாட்டிற்கும் ஏற்ற மங்களகரமான மணி ரங்கோலி கோலம்! {construct_ta} முறையில் {speed_ta} போடக்கூடிய அற்புதமான வடிவமைப்பு.
Learn how to draw a sacred Temple Bell Rangoli for Friday morning pooja and festival doorstep decoration. Step-by-step tutorial {construct_en.lower()}."""

        significance = """✨ பூஜை அறை மற்றும் தலைவாசலில் மணி கோலம் போடுவதால் வீட்டில் மங்களமும் லட்சுமி கடாட்சமும் பெருகும்!
✨ Drawing bell motifs at the entrance brings divine positive energy and peace to the home."""

        queries = f"{channel_name}, பூஜை மணி கோலம், மணி ரங்கோலி, வெள்ளிக்கிழமை கோலம், Friday Special Bell Kolam, Temple Bell Rangoli, Pooja Room Kolam, Bell Rangoli without dots, Friday Kolam Designs, Mandir Entrance Rangoli, Margazhi Bell Kolam, Easy Bell Muggulu."
        hashtags = "#AKKolam #BellKolam #FridayKolam #PoojaKolam #BellRangoli #Kolam #Rangoli #Shorts #TempleBell #Muggulu #TrendingShorts #கோலம் #பூஜைகோலம்"
        tags_list = [channel_name, "மணி கோலம்", "பூஜை மணி கோலம்", "வெள்ளிக்கிழமை கோலம்", "bell kolam", "bell rangoli", "friday kolam", "pooja room rangoli", "temple bell rangoli", "kolam without dots", "kolam", "rangoli", "muggulu", "shorts"]

    elif motif == "lotus":
        sym_desc_ta = f"{sym} இதழ் " if sym in [6, 8, 12] else ""
        sym_desc_en = f"{sym}-Petal " if sym in [6, 8, 12] else ""

        title_ta = f"{sym_desc_ta}தாமரை ரங்கோலி கோலம் 🌸"
        title_en = f"{sym_desc_en}Lotus Rangoli"
        hook_en = construct_en
        seo_title = build_safe_title(channel_name, title_ta, title_en, hook_en)

        desc_intro = f"""🌸 {channel_name} - {sym_desc_en}Lotus Rangoli / தாமரை மலர் கோலம்

மகாலட்சுமிக்கு உகந்த மங்களகரமான {sym_desc_ta}தாமரை ரங்கோலி கோலம்! {construct_ta} முறையில் {speed_ta} எளிதாக போடலாம்.
Beautiful {sym_desc_en.lower()}Lotus Rangoli design for Lakshmi Pooja, Friday worship, and doorstep decoration. Simple and elegant tutorial {construct_en.lower()}."""

        significance = """🌸 தாமரை கோலம் வரைவதால் அஷ்டலட்சுமி அருள் மற்றும் மன அமைதி உண்டாகும்!
🌸 The sacred Lotus (Kamal) motif symbolizes purity, prosperity, and divine blessings of Goddess Mahalakshmi."""

        queries = f"{channel_name}, தாமரை கோலம், Lotus Rangoli, 8 Petal Lotus Kolam, Mahalakshmi Lotus Kolam, Friday Lotus Kolam, Kamal Rangoli, Lotus Kolam without dots, Pooja Room Lotus Design, Simple Lotus Rangoli, Easy Flower Kolam, Daily Morning Lotus Muggulu."
        hashtags = "#AKKolam #LotusKolam #LotusRangoli #KamalRangoli #FridayKolam #MahalakshmiKolam #Kolam #Rangoli #Shorts #Muggulu #TamilKolam #கோலம் #தாமரைகோலம்"
        tags_list = [channel_name, "தாமரை கோலம்", "மலர் கோலம்", "lotus kolam", "lotus rangoli", "kamal rangoli", "friday kolam", "mahalakshmi kolam", "flower rangoli", "kolam", "rangoli", "muggulu", "shorts"]

    elif motif == "sikku":
        title_ta = f"{construct_ta} சுலபமான சிக்கு கோலம் ✨"
        title_en = f"Easy {construct_en} Sikku Kolam"
        hook_en = speed_en
        seo_title = build_safe_title(channel_name, title_ta, title_en, hook_en)

        desc_intro = f"""🌀 {channel_name} - Traditional Sikku Kolam / சுலபமான சிக்கு சுழி கோலம்

புள்ளிகளை இணைத்து சிக்கல் இல்லாமல் மிக எளிதாக போடக்கூடிய பாரம்பரிய சிக்கு கோலம்! {construct_ta} அமைப்பில் {speed_ta} எளிதாக கற்றுக்கொள்ளலாம்.
Traditional South Indian Sikku / Suzhi Kolam tutorial. Master the smooth interlocking curves with clear step-by-step guidance."""

        significance = """✨ சிக்கு கோலம் மனதை ஒருமுகப்படுத்தவும் வீட்டின் வாசலுக்கு நேர்மறை ஆற்றலை ஈர்க்கவும் உதவும்!
✨ Interlocking Sikku patterns enhance mental focus and represent harmony and positive vibrations."""

        queries = f"{channel_name}, சிக்கு கோலம், சுழி கோலம், சிக்கல் இல்லா சிக்கு கோலம், {construct_ta} சிக்கு கோலம், Sikku Kolam with dots, Easy Sikku Kolam for Beginners, Suzhi Kolam Designs, Daily Morning Sikku Muggulu, Traditional Tamil Sikku Kolam, Simple Chukkala Muggulu."
        hashtags = "#AKKolam #SikkuKolam #SuzhiKolam #DotKolam #Kolam #Rangoli #Shorts #Muggulu #TraditionalKolam #DailyKolam #ChukkalaMuggulu #TrendingShorts #சிக்குகோலம் #கோலம்"
        tags_list = [channel_name, "சிக்கு கோலம்", "சுழி கோலம்", "புள்ளி கோலம்", "sikku kolam", "suzhi kolam", "dot kolam", "easy sikku kolam", "traditional kolam", "muggulu", "kolam", "rangoli", "shorts"]

    elif motif == "pulli":
        title_ta = f"{construct_ta} நேர் புள்ளி கோலம் 🌾"
        title_en = f"Simple {construct_en} Pulli Kolam"
        hook_en = "Daily Kolam"
        seo_title = build_safe_title(channel_name, title_ta, title_en, hook_en)

        desc_intro = f"""🌾 {channel_name} - Daily Dot Kolam / எளிய புள்ளி கோலம்

தினமும் காலையில் வீட்டு வாசலில் போடக்கூடிய சுலபமான {construct_ta} கோலம்! ஆரம்பநிலை கற்பவர்கள் கூட {speed_ta} எளிதாக போடலாம்.
Simple and clean Pulli Kolam with {construct_en.lower()} for daily morning practice. Perfect for beginners and busy mornings."""

        significance = """🌾 வாசலில் அரிசி மாவு புள்ளி கோலம் இடுவது மங்களகரமான நாள் தொடக்கத்திற்கு வழிவகுக்கும்!
🌾 Drawing early morning pulli kolam with rice powder welcomes prosperity and joy into the household."""

        queries = f"{channel_name}, புள்ளி கோலம், நேர் புள்ளி கோலம், எளிய புள்ளி கோலம், {construct_ta} கோலம், Pulli Kolam with dots, Daily Morning Dot Kolam, Simple Pulli Kolam for Beginners, Small Muggulu with dots, Easy Friday Dot Kolam, Traditional Doorstep Kolam."
        hashtags = "#AKKolam #PulliKolam #DotKolam #DailyKolam #Kolam #Rangoli #Shorts #Muggulu #SimpleKolam #BeginnersKolam #TamilKolam #கோலம் #புள்ளிகோலம்"
        tags_list = [channel_name, "புள்ளி கோலம்", "நேர் புள்ளி கோலம்", "pulli kolam", "dot kolam", "daily kolam", "simple kolam", "morning kolam", "muggulu", "kolam", "rangoli", "shorts"]

    elif motif == "mandala":
        title_ta = f"வட்ட வடிவ வண்ண மண்டலா கோலம் 🎨"
        title_en = f"Circular Mandala Rangoli"
        hook_en = construct_en
        seo_title = build_safe_title(channel_name, title_ta, title_en, hook_en)

        desc_intro = f"""🎨 {channel_name} - Circular Mandala Rangoli / வண்ணமயமான மண்டலா கோலம்

மையத்திலிருந்து விரிந்து செல்லும் வட்ட வடிவ வண்ண மண்டலா ரங்கோலி! பண்டிகை காலத்திற்கு ஏற்ற {speed_ta} நேர்த்தியான வடிவமைப்பு.
Vibrant concentric circular Mandala Rangoli design for festive occasions and celebrations. Step-by-step powder art tutorial."""

        significance = """🎨 மண்டலா கோலம் மன அமைதியையும் கலை நேர்த்தியையும் வெளிப்படுத்தும் ஆன்மீக வடிவம்!
🎨 Concentric mandala art represents cosmic balance, harmony, and creative beauty."""

        queries = f"{channel_name}, மண்டலா கோலம், வண்ண ரங்கோலி, Mandala Rangoli Design, Circular Mandala Kolam, Freehand Mandala Art, Festival Color Rangoli, Easy Mandala for Beginners, Round Rangoli Designs, Creative Kolam Art."
        hashtags = "#AKKolam #MandalaKolam #MandalaRangoli #ColorRangoli #Kolam #Rangoli #Shorts #Muggulu #FestivalRangoli #CreativeRangoli #TrendingShorts #மண்டலாகோலம் #ரங்கோலி"
        tags_list = [channel_name, "மண்டலா கோலம்", "வண்ண ரங்கோலி", "mandala kolam", "mandala rangoli", "color rangoli", "circular rangoli", "festival rangoli", "creative kolam", "kolam", "rangoli", "shorts"]

    else:
        title_ta = f"அழகான வண்ண ரங்கோலி கோலம் 🌸"
        title_en = f"Beautiful Color Rangoli Design"
        hook_en = construct_en
        seo_title = build_safe_title(channel_name, title_ta, title_en, hook_en)

        desc_intro = f"""🌸 {channel_name} - Beautiful Daily Rangoli / அழகான வண்ண ரங்கோலி கோலம்

வீட்டு வாசலை அலங்கரிக்கும் வண்ணமயமான ரங்கோலி கோலம்! {speed_ta} மிக எளிதாக வரையக்கூடிய எளிய வடிவம்.
Beautiful and vibrant freehand Rangoli design for daily morning doorstep and pooja decoration."""

        significance = """✨ வண்ண கோலம் வீட்டின் முகப்பிற்கு தனி அழகையும் மங்களகரமான தோற்றத்தையும் தரும்!
✨ Vibrant color rangolis brighten up the entrance and create a warm, welcoming festive atmosphere."""

        queries = f"{channel_name}, ரங்கோலி கோலம், வண்ண கோலம், Color Rangoli, Easy Daily Kolam, Freehand Rangoli Design, Simple Doorstep Kolam, Morning Pooja Rangoli, Easy Muggulu, Tamil Kolam Art."
        hashtags = "#AKKolam #Rangoli #Kolam #Shorts #ColorRangoli #Muggulu #DailyKolam #SimpleRangoli #TamilKolam #TrendingShorts #ரங்கோலி #கோலம்"
        tags_list = [channel_name, "ரங்கோலி கோலம்", "வண்ண கோலம்", "rangoli", "color rangoli", "daily kolam", "simple kolam", "muggulu", "kolam", "shorts"]

    # --- Assemble Full Rich Description ---
    seo_desc = f"""{desc_intro}

{significance}

⏱️ Quick Video Highlights:
• Style: {motif.title()} Design ({construct_en})
• Estimated Drawing Time: {duration_seconds}s
• Technique: Powder Line Art with Natural Colors

✨ Subscribe to @AKKolam for daily fresh Kolam & Rangoli tutorials!
🔔 Like, Share & Subscribe for more beautiful Kolam shorts!

🔍 Search Queries / தொடர்புடைய தேடல்கள்:
{queries}

🏷️ Hashtags:
{hashtags}"""

    tags_csv = ", ".join(tags_list)

    return {
        "title": seo_title,
        "description": seo_desc,
        "tags": tags_csv,
        "motif": motif,
        "analysis": analysis
    }


def save_metadata_to_file(meta_dict, output_video_path, thumbnail_path=None, channel_name="AK Kolam"):
    """
    Saves the dynamic bilingual SEO metadata to a UTF-8 encoded text file
    alongside the generated video and thumbnail.
    """
    meta_path = os.path.splitext(output_video_path)[0] + "_metadata.txt"
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(f"YOUTUBE SHORTS METADATA (TAMIL + ENGLISH) - {channel_name.upper()}\n")
            f.write(f"Detected Motif: {meta_dict.get('motif', 'general').upper()}\n")
            f.write("=" * 60 + "\n\n")
            f.write("📌 TITLE (Copy-paste to YouTube Title):\n")
            f.write(meta_dict["title"] + "\n\n")
            f.write("-" * 60 + "\n")
            f.write("📝 DESCRIPTION (Copy-paste to YouTube Description):\n")
            f.write(meta_dict["description"] + "\n\n")
            f.write("-" * 60 + "\n")
            f.write("🏷️ TAGS (Copy-paste to YouTube Studio Tags):\n")
            f.write(meta_dict["tags"] + "\n\n")
            f.write("-" * 60 + "\n")
            f.write("📁 GENERATED FILES:\n")
            f.write(f"Video:     {os.path.abspath(output_video_path)}\n")
            if thumbnail_path:
                f.write(f"Thumbnail: {os.path.abspath(thumbnail_path)}\n")
            f.write(f"Metadata:  {os.path.abspath(meta_path)}\n")
            f.write("=" * 60 + "\n")
        return meta_path
    except Exception as e:
        print(f"  -> Warning: Failed to write metadata file: {e}")
        return None
