import os
import sys
import argparse
from pathlib import Path

# Reconfigure stdout and stderr for UTF-8 on Windows
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

from engine.youtube_uploader import (
    upload_from_metadata_file,
    upload_video_to_youtube,
    parse_metadata_file,
    get_authenticated_service
)


def find_latest_metadata_or_video():
    """Finds the most recently created metadata text file or mp4 in outputs/"""
    outputs_dir = Path("outputs")
    if not outputs_dir.exists():
        return None, None

    # First check for metadata files
    meta_files = list(outputs_dir.glob("*_metadata.txt"))
    if meta_files:
        meta_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return "metadata", str(meta_files[0])

    # Fallback to mp4 files
    mp4_files = list(outputs_dir.glob("*.mp4"))
    if mp4_files:
        mp4_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return "video", str(mp4_files[0])

    return None, None


def main():
    parser = argparse.ArgumentParser(description="Upload Kolam Videos & Thumbnails to YouTube (Shorts Ready)")
    parser.add_argument("--metadata", "-m", help="Path to _metadata.txt file (contains title, desc, tags, paths)")
    parser.add_argument("--video", "-v", help="Path to video file (.mp4)")
    parser.add_argument("--thumbnail", "-t", help="Path to thumbnail image (.jpg/.png)")
    parser.add_argument("--title", help="Custom video title")
    parser.add_argument("--desc", help="Custom video description")
    parser.add_argument("--privacy", "-p", default="public", choices=["public", "unlisted", "private"], help="Privacy status (default: public)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    print("=" * 60)
    print("      AK KOLAM - YOUTUBE UPLOADER TOOL")
    print("=" * 60)

    target_meta = args.metadata
    target_video = args.video

    # If neither specified, auto-detect latest from outputs/
    if not target_meta and not target_video:
        mode, detected_path = find_latest_metadata_or_video()
        if not detected_path:
            print("[ERROR] No generated files found in outputs/ folder.")
            print("Please specify a metadata file with --metadata or generate a video first.")
            sys.exit(1)

        if mode == "metadata":
            target_meta = detected_path
            print(f"[AUTO-DETECT] Selected latest metadata: {target_meta}")
        else:
            target_video = detected_path
            print(f"[AUTO-DETECT] Selected latest video: {target_video}")

    # Case 1: Uploading from metadata file (Recommended)
    if target_meta:
        if not os.path.exists(target_meta):
            print(f"[ERROR] Metadata file not found: {target_meta}")
            sys.exit(1)

        try:
            parsed = parse_metadata_file(target_meta)
        except Exception as e:
            print(f"[ERROR] Failed to read metadata: {e}")
            sys.exit(1)

        print("\n📋 YOUTUBE STUDIO SETTINGS BREAKDOWN:")
        print(f"  • Video:                {parsed.get('video_path', 'N/A')}")
        print(f"  • Custom Thumbnail:     {parsed.get('thumbnail_path', 'N/A')}")
        print(f"  • Title:                {parsed.get('title', 'N/A')}")
        print(f"  • Category:             Howto & Style (26)")
        print(f"  • Made for Kids:        NO (Not made for children)")
        print(f"  • Altered / AI Media:   NO (Standard authentic art video)")
        print(f"  • Paid Promotion:       NO (None)")
        print(f"  • License:              Standard YouTube License")
        print(f"  • Privacy:              {args.privacy.upper()}")
        print(f"  • Tags:                 {len(parsed.get('tags', []))} tags detected")

        if not args.yes:
            try:
                confirm = input("\nProceed with upload to YouTube? (y/n) [default: y]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = "n"

            if confirm and confirm not in ["y", "yes"]:
                print("Upload cancelled by user.")
                sys.exit(0)

        result = upload_from_metadata_file(target_meta, privacy_status=args.privacy)
        if not result:
            sys.exit(1)

    # Case 2: Uploading direct video file
    elif target_video:
        if not os.path.exists(target_video):
            print(f"[ERROR] Video file not found: {target_video}")
            sys.exit(1)

        # Check for matching thumbnail and metadata if available
        base = os.path.splitext(target_video)[0]
        thumb = args.thumbnail or (f"{base}_thumbnail.jpg" if os.path.exists(f"{base}_thumbnail.jpg") else None)
        title = args.title or f"AK Kolam | Beautiful Rangoli Design #shorts"
        desc = args.desc or f"Daily Beautiful Kolam & Rangoli Design tutorial.\n\nSubscribe to @AKKolam for more daily designs!\n\n#AKKolam #Kolam #Rangoli #Shorts"

        print("\n📋 UPLOAD SUMMARY:")
        print(f"  • Video:     {target_video}")
        print(f"  • Thumbnail: {thumb or 'None'}")
        print(f"  • Title:     {title}")
        print(f"  • Privacy:   {args.privacy.upper()}")

        if not args.yes:
            try:
                confirm = input("\nProceed with upload to YouTube? (y/n) [default: y]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = "n"

            if confirm and confirm not in ["y", "yes"]:
                print("Upload cancelled by user.")
                sys.exit(0)

        result = upload_video_to_youtube(
            video_path=target_video,
            title=title,
            description=desc,
            tags=["AK Kolam", "Kolam", "Rangoli", "Shorts", "Muggulu"],
            thumbnail_path=thumb,
            privacy_status=args.privacy
        )
        if not result:
            sys.exit(1)


if __name__ == "__main__":
    main()
