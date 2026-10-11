import os
import sys
import random
import subprocess
from pathlib import Path
import cv2

# Reconfigure stdout and stderr for UTF-8 on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_random_music_file(music_dir=r"D:\ncs music"):
    """
    Randomly selects an audio file from the specified music directory.
    Supports .mp3, .wav, .m4a, .ogg, .aac, .flac formats.
    """
    dir_path = Path(music_dir)
    if not dir_path.exists() or not dir_path.is_dir():
        print(f"[AUDIO] Warning: Music directory not found: {music_dir}")
        return None

    extensions = ["*.mp3", "*.wav", "*.m4a", "*.ogg", "*.aac", "*.flac"]
    audio_files = []
    for ext in extensions:
        audio_files.extend(list(dir_path.glob(ext)))
        audio_files.extend(list(dir_path.glob(ext.upper())))

    # Deduplicate and ensure file size > 0
    valid_files = [f for f in set(audio_files) if f.is_file() and f.stat().st_size > 1024]

    if not valid_files:
        print(f"[AUDIO] Warning: No audio files found in: {music_dir}")
        return None

    chosen = random.choice(valid_files)
    return str(chosen.resolve())


def get_video_duration(video_path):
    """
    Accurately gets the video duration in seconds using ffprobe,
    with a fallback to OpenCV VideoCapture.
    """
    video_path = str(video_path)
    if not os.path.exists(video_path):
        return 0.0

    # 1. Try ffprobe first for exact stream duration
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        dur = float(res.stdout.strip())
        if dur > 0:
            return dur
    except Exception:
        pass

    # 2. Fallback to OpenCV
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        if frames > 0 and fps > 0:
            return float(frames / fps)
    except Exception:
        pass

    return 30.0


def merge_instrumental_bgm(
    video_path,
    music_dir=r"D:\ncs music",
    volume=1.3,
    fade_in_sec=1.0,
    fade_out_sec=2.0,
    output_path=None
):
    """
    Picks a random audio file from music_dir, removes vocals using center-channel
    cancellation while preserving low-end bass (< 180 Hz), loops the audio if it is
    shorter than the video, and merges it into the video without trimming the video.
    """
    video_path = str(Path(video_path).resolve())
    if not os.path.exists(video_path):
        print(f"[AUDIO] Error: Video file not found: {video_path}")
        return {"success": False, "error": "Video not found"}

    audio_file = get_random_music_file(music_dir)
    if not audio_file:
        print("[AUDIO] Skipping background music (no audio file available).")
        return {"success": False, "error": "No audio file available"}

    song_name = os.path.splitext(os.path.basename(audio_file))[0]
    duration = get_video_duration(video_path)
    if duration <= 0:
        duration = 30.0

    fade_out_start = max(0.5, duration - fade_out_sec)
    actual_fade_out = min(fade_out_sec, duration - fade_out_start)

    # High-quality Vocal Removal + Bass Preservation Filter:
    # 1. Split audio into low-frequency bass (<180Hz) and mid/highs (>180Hz)
    # 2. Preserve bass/kick drums in mono
    # 3. Apply center-cancellation (L-R) on mid/highs to eliminate center-panned vocals
    # 4. Mix bass and vocal-removed instrumental, normalize volume, and apply smooth fade-in/fade-out
    filter_complex = (
        f"[1:a]asplit=2[b][m];"
        f"[b]lowpass=f=180[bass];"
        f"[m]highpass=f=180,pan=stereo|c0=c0-c1|c1=c1-c0[mid];"
        f"[bass][mid]amix=inputs=2,volume={volume:.2f},"
        f"afade=t=in:ss=0:d={fade_in_sec:.1f},"
        f"afade=t=out:st={fade_out_start:.2f}:d={actual_fade_out:.1f}[aout]"
    )

    dest_path = str(Path(output_path).resolve()) if output_path else video_path
    temp_output = str(Path(video_path).parent / f"temp_mux_{os.path.basename(video_path)}")

    print(f"\n[AUDIO] Processing background music for: {os.path.basename(video_path)}")
    print(f"  • Selected Track:       🎵 {song_name}")
    print(f"  • Vocal Removal:        Active (Center-cancellation with punchy bass preservation)")
    print(f"  • Video Duration:       {duration:.1f}s (Video will NOT be trimmed)")
    print(f"  • Audio Looping:        Enabled (loops seamlessly if track is shorter)")

    # FFmpeg command:
    # -stream_loop -1 loops the audio indefinitely before filtering
    # -c:v copy copies video packets directly without re-encoding (instant & lossless)
    # -t {duration} stops encoding precisely when the full video finishes
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-stream_loop", "-1",
        "-i", audio_file,
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(duration),
        temp_output
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[AUDIO] Warning: FFmpeg audio muxing failed: {res.stderr[-300:]}")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return {"success": False, "error": res.stderr}

        # Verify output exists and has valid size
        if not os.path.exists(temp_output) or os.path.getsize(temp_output) < 1024:
            print("[AUDIO] Warning: Muxed video is empty or missing.")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return {"success": False, "error": "Output file empty"}

        # Replace original file with muxed file
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass

        os.replace(temp_output, dest_path)
        print(f"  • Result:               ✅ Instrumental BGM successfully merged!")
        return {
            "success": True,
            "song_name": song_name,
            "audio_file": audio_file,
            "duration": duration,
            "output_path": dest_path
        }

    except Exception as e:
        print(f"[AUDIO] Warning: Exception during audio muxing: {e}")
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except Exception:
                pass
        return {"success": False, "error": str(e)}
