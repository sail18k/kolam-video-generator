
import argparse
import os
import sys
from pathlib import Path

# Add engine to path
sys.path.append(str(Path(__file__).parent))

from engine.classifier import classify_kolam_local_llm, classify_heuristic
from engine.dot_generator import generate_custom_dots, generate_8x2_dots
from engine.path_generator import generate_path_for_type
from engine.renderer import render_kolam_video

def main():
    parser = argparse.ArgumentParser(description="Headless Kolam Video Generator - YouTube Shorts Ready")
    parser.add_argument("--input", "-i", required=True, help="Input sketch image (mandala/rangoli/pulli/sikku)")
    parser.add_argument("--output", "-o", default="outputs/kolam_shorts.mp4", help="Output video path")
    parser.add_argument("--type", "-t", default="auto", choices=["auto","pulli_kolam","sikku_kolam","rangoli","mandala"], help="Kolam type, auto detects")
    parser.add_argument("--grid", "-g", default="8x2", help="Dot grid: 8x2, 6x2, etc")
    parser.add_argument("--fps", type=int, default=25, help="FPS (25 for YouTube Shorts)")
    parser.add_argument("--no-hand", action="store_true", help="Disable hand overlay")
    
    args = parser.parse_args()
    
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
    
    # Ensure output dir exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    output = render_kolam_video(
        dots=dots,
        path=path,
        wood_path=wood_path,
        hand_path=hand_path if not args.no_hand else "engine/assets/hand_raw.png",
        output_path=args.output,
        fps=args.fps
    )
    
    print("\n=== DONE ===")
    print(f"Video: {output}")
    print(f"Ready to upload to YouTube Shorts!")
    print(f"Specs: 1080x1920, {args.fps}fps, H.264, <60s, vertical")
    print("\nYouTube metadata suggestion:")
    title_grid = f" | {grid} Dots Kolam" if grid and grid != "none" else ""
    print(f"Title: {kolam_type.replace('_',' ').title()}{title_grid} | Easy Rangoli Shorts")
    print(f"Description: Beautiful {kolam_type} generated from sketch. #kolam #rangoli #muggulu #shorts")
    print("Hashtags: #kolam #rangoli #muggulu #sikkuKolam #pulliKolam #rangoliDesign #youtubeShorts")

if __name__ == "__main__":
    main()
