import argparse
import os
import sys
import socket
from pathlib import Path

# Force IPv4 resolution to prevent Windows IPv6 timeout (WinError 10060)
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

# Reconfigure stdout and stderr for UTF-8 on Windows to safely print Tamil characters
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add engine to path
sys.path.append(str(Path(__file__).parent))

from engine.classifier import classify_kolam_local_llm, classify_heuristic
from engine.dot_generator import generate_custom_dots, generate_8x2_dots
from engine.path_generator import generate_path_for_type
from engine.renderer import render_kolam_video
from engine.thumbnail_generator import generate_kolam_thumbnail
from engine.seo_generator import generate_dynamic_seo_metadata, save_metadata_to_file

def main():
    parser = argparse.ArgumentParser(description="Headless Kolam Video Generator - YouTube Shorts Ready")
    parser.add_argument("--input", "-i", default=None, help="Input sketch image (auto-detects from inputs/ if not provided)")
    parser.add_argument("--output", "-o", default="outputs/kolam_shorts.mp4", help="Output video path")
    parser.add_argument("--type", "-t", default="auto", choices=["auto","pulli_kolam","sikku_kolam","rangoli","mandala"], help="Kolam type, auto detects")
    parser.add_argument("--grid", "-g", default="8x2", help="Dot grid: 8x2, 6x2, etc")
    parser.add_argument("--fps", type=int, default=25, help="FPS (25 for YouTube Shorts)")
    parser.add_argument("--no-hand", action="store_true", help="Disable hand overlay")
    parser.add_argument("--no-watermark", action="store_true", help="Disable footer watermark (Like, Share, Subscribe)")
    parser.add_argument("--no-thumbnail", action="store_true", help="Disable YouTube Short thumbnail generation")
    parser.add_argument("--title", default="AK Kolam", help="Header title for video and thumbnail (default: AK Kolam)")
    parser.add_argument("--upload", action="store_true", help="Auto-upload video and thumbnail to YouTube after generation")
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload prompt completely")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"], help="YouTube privacy status (default: public)")
    
    args = parser.parse_args()
    
    if not args.input:
        inputs_dir = Path("inputs")
        candidate_images = list(inputs_dir.glob("*.jpg")) + list(inputs_dir.glob("*.png")) + list(inputs_dir.glob("*.jpeg"))
        if candidate_images:
            args.input = str(candidate_images[0])
            print(f"[AUTO-DETECT] Found input image: {args.input}")
        else:
            print("[ERROR] No input image provided and no image found in inputs/ folder!")
            sys.exit(1)
            
    print("=== Headless Kolam Generator ===")
    print(f"Input: {args.input}")
    
    # 1. Classify
    if args.type == "auto":
        print("[1/4] Classifying with local LLM...")
        result = classify_kolam_local_llm(args.input)
        kolam_type = result.get("type", "sikku_kolam")
        grid = result.get("dot_grid", args.grid)
        print(f"  -> Detected: {kolam_type}, grid: {grid}, confidence: {result.get('confidence')}")
    else:
        kolam_type = args.type
        grid = args.grid
        print(f"[1/4] Using manual type: {kolam_type}, grid: {grid}")
    
    # 2. Generate dots
    print(f"[2/4] Generating dots for {grid}...")
    dots = generate_custom_dots(grid, width=1080, height=1920)
    print(f"  -> {len(dots)} dots")
    
    # 3. Generate path
    print(f"[3/4] Generating {kolam_type} path...")
    path = generate_path_for_type(kolam_type, dots, input_image_path=args.input)
    print(f"  -> Path with {len(path)} points")
    
    # 4. Render video - exactly like reference
    print("[4/4] Rendering headless video (YouTube Shorts ready: 1080x1920, 25fps)...")
    wood_path = "engine/assets/wood.jpg"
    hand_path = "engine/assets/hand_raw.png" if not args.no_hand else None
    
    # Generate unique output filename
    if args.output == "outputs/kolam_shorts.mp4":
        import time
        input_basename = os.path.splitext(os.path.basename(args.input))[0]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        args.output = f"outputs/{input_basename}_{timestamp}.mp4"
        
    # Ensure output dir exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    output = render_kolam_video(
        dots=dots,
        path=path,
        wood_path=wood_path,
        hand_path=hand_path if not args.no_hand else "engine/assets/hand_raw.png",
        output_path=args.output,
        fps=args.fps,
        show_watermark=not args.no_watermark,
        title=args.title
    )
    
    # 5. Generate YouTube Short Thumbnail image
    thumbnail_path = None
    if not args.no_thumbnail:
        print("\n[5/5] Generating YouTube Short thumbnail with natural Kolam colors...")
        thumb_output = os.path.splitext(output)[0] + "_thumbnail.jpg"
        try:
            thumbnail_path = generate_kolam_thumbnail(
                input_image_path=args.input,
                output_thumbnail_path=thumb_output,
                kolam_type=kolam_type,
                grid=grid,
                wood_path=wood_path,
                dots=dots,
                title=args.title
            )
            print(f"  -> Thumbnail saved: {thumbnail_path}")
        except Exception as e:
            print(f"  -> Warning: Failed to generate thumbnail: {e}")
            
    print("\n=== DONE ===")
    print(f"Video: {output}")
    if thumbnail_path:
        print(f"Thumbnail: {thumbnail_path}")
    print(f"Ready to upload to YouTube Shorts!")
    print(f"Specs: 1080x1920, {args.fps}fps, H.264, <60s, vertical")
    # 6. Dynamic Bilingual SEO Metadata Suggestion (Tamil + English)
    print("\n[6/6] Generating Dynamic High-Engagement SEO Metadata (Tamil + English)...")
    valid_points = [p for p in path if p is not None] if path else []
    duration_sec = max(15, int(len(valid_points) / 15 / max(1, args.fps)))
    
    metadata = generate_dynamic_seo_metadata(
        image_path=args.input,
        kolam_type=kolam_type,
        grid=grid,
        dots=dots,
        path=path,
        duration_seconds=duration_sec,
        channel_name=args.title
    )
    
    if not metadata:
        metadata = {
            "title": f"{args.title} | அழகான ரங்கோலி கோலம் 🌸 Easy Kolam Design #shorts",
            "description": f"🌸 {args.title} - Daily Simple & Beautiful Kolam Designs.\n\nSubscribe to @AKKolam for more daily fresh tutorials!\n\n#AKKolam #Kolam #Rangoli #Shorts",
            "tags": f"{args.title}, kolam, rangoli, muggulu, shorts",
            "motif": "kolam"
        }
    
    meta_path = save_metadata_to_file(
        meta_dict=metadata,
        output_video_path=output,
        thumbnail_path=thumbnail_path,
        channel_name=args.title
    )

    print("\n" + "="*50)
    print(f"📺 DYNAMIC HIGH-ENGAGEMENT SEO METADATA (TAMIL + ENGLISH) - {args.title}")
    print("="*50)
    print(f"Detected Motif: {metadata['motif'].upper()} | Duration: ~{duration_sec}s")
    print(f"\n📌 TITLE (Click-Worthy & Search Optimized):\n{metadata['title']}\n")
    print(f"📝 DESCRIPTION:\n{metadata['description']}\n")
    print(f"🏷️ TAGS:\n{metadata['tags']}\n")
    if meta_path:
        print(f"📁 Saved to text file: {meta_path}")
    print("="*50)

    # 7. YouTube Upload Option
    if not args.no_upload and meta_path:
        should_upload = args.upload
        if not should_upload:
            print("\n" + "="*50)
            try:
                ans = input("📤 Do you want to upload this video to YouTube? (y/n) [default: n]: ").strip().lower()
                should_upload = ans in ["y", "yes"]
            except (EOFError, KeyboardInterrupt):
                should_upload = False

        if should_upload:
            from engine.youtube_uploader import upload_from_metadata_file
            print("\n[YOUTUBE] Starting YouTube upload...")
            upload_from_metadata_file(meta_path, privacy_status=args.privacy)
        else:
            print("\n💡 YouTube upload skipped.")
            print(f"   You can upload anytime later by running: upload_to_youtube.bat\n")

if __name__ == "__main__":
    main()
