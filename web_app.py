"""
Web Application Server for Headless Kolam Video Generator V2 - Interactive Drawing Studio
Exposes a LAN-accessible Flask REST API and responsive web frontend for freehand drawing,
semi-transparent reference image tracing, and progressive video generation.
"""

import os
import sys
import time
import socket
import logging
import threading
import argparse
from pathlib import Path
from uuid import uuid4
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from werkzeug.utils import secure_filename

# Reconfigure stdout/stderr for UTF-8 on Windows
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

# Ensure repo root is in python path
ROOT_DIR = Path(__file__).parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engine.manual_drawing import (
    validate_and_normalize_drawing_payload,
    strokes_to_renderer_path,
    render_strokes_to_sketch_image,
)
from engine.reference_alignment import (
    preprocess_reference_image,
    correct_stroke_sequence,
    serialize_reference_geometry,
    refine_live_aligned_strokes,
    save_alignment_diagnostics,
)
from engine.dot_generator import generate_custom_dots
from engine.renderer import render_kolam_video
from engine.renderer_3d import render_kolam_video_3d
from engine.thumbnail_generator import generate_kolam_thumbnail
from engine.audio_processor import merge_instrumental_bgm, get_video_duration
from engine.seo_generator import generate_dynamic_seo_metadata, save_metadata_to_file
from engine.comfyui_bridge import discover_comfyui, get_enhancement_report

# Initialize Flask application
app = Flask(
    __name__,
    template_folder=str(ROOT_DIR / "web" / "templates"),
    static_folder=str(ROOT_DIR / "web" / "static")
)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB max upload

# Paths
UPLOADS_DIR = ROOT_DIR / "inputs" / "uploads"
OUTPUTS_DIR = ROOT_DIR / "outputs"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

# Job State Management
jobs_lock = threading.Lock()
jobs: Dict[str, Dict[str, Any]] = {}
job_queue: "list[str]" = []
worker_condition = threading.Condition(jobs_lock)


def get_lan_ip() -> str:
    """Discovers the primary local IPv4 address connected to the LAN/Wi-Fi router."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a public DNS IP (no packet is actually sent)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def background_job_worker():
    """Background worker thread executing one video rendering job at a time."""
    while True:
        with jobs_lock:
            while not job_queue:
                worker_condition.wait()
            job_id = job_queue.pop(0)
            job = jobs.get(job_id)
            if not job:
                continue
            job["status"] = "running"
            job["stage"] = "Preparing drawing"
            job["progress"] = 5

        # Execute generation outside the lock
        try:
            payload = job["payload"]
            normalized = validate_and_normalize_drawing_payload(payload)
            title = normalized.get("title", "AK Kolam")
            grid_type = normalized.get("dot_grid", "none")
            
            # 1. Dot Grid
            dots = []
            if grid_type and grid_type != "none":
                dots = generate_custom_dots(grid_type, width=1080, height=1920)
                
            # 2. Reference Alignment & Path Synthesis
            ref_filename = normalized.get("reference_image") or payload.get("reference_image")
            correction_enabled = normalized.get("correction_enabled", True)
            live_aligned = normalized.get("live_aligned", False) or payload.get("live_aligned", False)
            aligned_strokes = normalized["strokes"]
            ref_geom = None

            if ref_filename and correction_enabled:
                safe_name = secure_filename(os.path.basename(str(ref_filename)))
                ref_path = UPLOADS_DIR / safe_name
                if not ref_path.exists() or not ref_path.is_file():
                    raise ValueError("The selected blueprint reference is missing or invalid. Upload it again before generating.")
                with jobs_lock:
                    job["stage"] = "Validating live-aligned strokes" if live_aligned else "Aligning strokes to reference"
                    job["progress"] = 10
                try:
                    ref_geom = preprocess_reference_image(str(ref_path))
                    if live_aligned:
                        # Browser snapping improves acquisition; the server still checks every point and segment.
                        corrected, diag = refine_live_aligned_strokes(normalized["strokes"], ref_geom)
                        aligned_strokes = corrected
                        print(
                            f"[JOB {job_id}] Blueprint validation retained {diag.get('refined_count', 0)} strokes; "
                            f"rejected {diag.get('rejected_samples', 0)} off-line samples; "
                            f"p99 deviation {diag.get('geometry_error_p99', 0):.2f}px."
                        )
                    else:
                        # Legacy browser payloads still align first, then pass the same strict geometry check.
                        corrected, align_diag = correct_stroke_sequence(normalized["strokes"], ref_geom)
                        aligned_strokes, strict_diag = refine_live_aligned_strokes(corrected, ref_geom)
                        diag = {**align_diag, **strict_diag}
                        print(
                            f"[JOB {job_id}] Reference alignment retained {strict_diag.get('refined_count', 0)} strokes; "
                            f"rejected {strict_diag.get('rejected_samples', 0)} off-line samples."
                        )

                    if os.environ.get("KOLAM_DEBUG", "0") == "1" or payload.get("debug"):
                        debug_dir = OUTPUTS_DIR / f"debug_{job_id[:8]}"
                        save_alignment_diagnostics(debug_dir, ref_geom, normalized["strokes"], aligned_strokes, diag)
                except Exception as e:
                    # Blueprint mode must never fall back to drawing unvalidated coordinates.
                    raise ValueError(f"Blueprint validation failed: {e}") from e
            elif live_aligned:
                raise ValueError("Live blueprint tracing requires a valid reference image and correction mode.")

            with jobs_lock:
                job["stage"] = "Synthesizing drawing path"
                job["progress"] = 18
                
            path, point_colors, point_widths = strokes_to_renderer_path(aligned_strokes)
            
            # 3. Output filenames
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            video_filename = f"manual_{timestamp}_{job_id[:8]}.mp4"
            thumb_filename = f"manual_{timestamp}_{job_id[:8]}_thumbnail.jpg"
            meta_filename = f"manual_{timestamp}_{job_id[:8]}_metadata.txt"
            temp_sketch_name = f"temp_sketch_{timestamp}_{job_id[:8]}.png"
            
            video_path = str(OUTPUTS_DIR / video_filename)
            thumb_path = str(OUTPUTS_DIR / thumb_filename)
            temp_sketch_path = str(OUTPUTS_DIR / temp_sketch_name)
            
            # 4. Thumbnail & Opening Teaser Cover (Derived from Corrected Strokes)
            with jobs_lock:
                job["stage"] = "Generating thumbnail"
                job["progress"] = 25
                
            render_strokes_to_sketch_image(aligned_strokes, temp_sketch_path)
            
            wood_path = str(ROOT_DIR / "engine" / "assets" / "wood.jpg")
            hand_path = str(ROOT_DIR / "engine" / "assets" / "hand_raw.png")
            
            thumbnail_generated = None
            try:
                thumbnail_generated = generate_kolam_thumbnail(
                    input_image_path=temp_sketch_path,
                    output_thumbnail_path=thumb_path,
                    kolam_type="rangoli",
                    grid=grid_type,
                    wood_path=wood_path,
                    dots=dots,
                    title=title
                )
            except Exception as e:
                print(f"[JOB {job_id}] Thumbnail generation warning: {e}")
            finally:
                if os.path.exists(temp_sketch_path):
                    try:
                        os.remove(temp_sketch_path)
                    except Exception:
                        pass
                        
            # 5. Progressive Video Rendering
            with jobs_lock:
                job["stage"] = "Rendering video"
                job["progress"] = 35
                
            def on_render_progress(percent, curr_f, total_f):
                mapped = 35 + int(percent * 0.50)
                with jobs_lock:
                    job["progress"] = min(85, mapped)
                    job["stage"] = f"Rendering video ({int(percent)}%)"

            render_kolam_video(
                dots=dots,
                path=path,
                wood_path=wood_path,
                hand_path=hand_path,
                output_path=video_path,
                fps=25,
                line_thickness=6,
                show_watermark=True,
                title=title,
                cover_image_path=thumbnail_generated,
                point_colors=point_colors,
                point_widths=point_widths,
                progress_callback=on_render_progress,
                drawing_speed=float(payload.get("drawing_speed", 1.2))
            )
            
            # 6. Audio Processing (Vocal Removal + BGM Muxing)
            with jobs_lock:
                job["stage"] = "Processing background music"
                job["progress"] = 88
                
            music_dir = r"D:\ncs music"
            if os.path.exists(music_dir):
                try:
                    merge_instrumental_bgm(video_path=video_path, music_dir=music_dir, volume=1.3)
                except Exception as e:
                    print(f"[JOB {job_id}] Audio processing warning: {e}")

            # 6b. 3D Video Rendering (same geometry and timeline, raised-powder style)
            video_3d_filename = f"manual_{timestamp}_{job_id[:8]}_3d.mp4"
            video_3d_path = str(OUTPUTS_DIR / video_3d_filename)
            video_3d_success = False
            rendering_mode = "deterministic_local"

            with jobs_lock:
                job["stage"] = "Rendering 3D video"
                job["progress"] = 68
                job["video_3d_status"] = "rendering"

            # Check ComfyUI availability
            comfyui_status = discover_comfyui()
            enhancement_report = get_enhancement_report(comfyui_status)
            if comfyui_status.usable:
                rendering_mode = "comfyui_enhanced"
                print(f"[JOB {job_id}] ComfyUI detected at {comfyui_status.server_url} with {len(comfyui_status.models_available)} models")
            else:
                print(f"[JOB {job_id}] ComfyUI not available: {comfyui_status.error_message}. Using deterministic 3D renderer.")

            def on_3d_progress(percent, curr_f, total_f):
                mapped_3d = 68 + int(percent * 0.18)
                with jobs_lock:
                    job["progress"] = min(86, mapped_3d)
                    job["stage"] = f"Rendering 3D video ({int(percent)}%)"

            try:
                render_kolam_video_3d(
                    dots=dots,
                    path=path,
                    wood_path=wood_path,
                    hand_path=hand_path,
                    output_path=video_3d_path,
                    fps=25,
                    line_thickness=6,
                    show_watermark=True,
                    title=title,
                    cover_image_path=thumbnail_generated,
                    point_colors=point_colors,
                    point_widths=point_widths,
                    progress_callback=on_3d_progress,
                    drawing_speed=float(payload.get("drawing_speed", 1.2))
                )
                # Mux audio into 3D video too
                if os.path.exists(music_dir):
                    try:
                        merge_instrumental_bgm(video_path=video_3d_path, music_dir=music_dir, volume=1.3)
                    except Exception as e:
                        print(f"[JOB {job_id}] 3D audio processing warning: {e}")
                video_3d_success = True
                print(f"[JOB {job_id}] 3D video rendered successfully: {video_3d_filename}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[JOB {job_id}] 3D rendering failed: {e}. 2D video is still valid.")
                with jobs_lock:
                    job["video_3d_status"] = "failed"
                    job["video_3d_error"] = str(e)
                    
            # 7. Dynamic SEO Metadata Generation
            with jobs_lock:
                job["stage"] = "Generating SEO metadata"
                job["progress"] = 95
                
            probed_dur = get_video_duration(video_path)
            duration_sec = max(15, int(round(probed_dur))) if probed_dur > 0 else max(15, int(len([p for p in path if p is not None]) / 2.5 / 25))
            
            meta_dict = generate_dynamic_seo_metadata(
                image_path=None,
                kolam_type="rangoli",
                grid=grid_type,
                dots=dots,
                path=path,
                duration_seconds=duration_sec,
                channel_name=title
            )
            if not meta_dict:
                meta_dict = {
                    "title": f"{title} | அழகான ரங்கோலி கோலம் 🌸 Easy Kolam Design #shorts",
                    "description": f"🌸 {title} - Daily Simple & Beautiful Kolam Designs.\n\nSubscribe to @AKKolam for more daily fresh tutorials!\n\n#AKKolam #Kolam #Rangoli #Shorts",
                    "tags": f"{title}, kolam, rangoli, muggulu, shorts",
                    "motif": "kolam"
                }
                
            meta_path = save_metadata_to_file(
                meta_dict=meta_dict,
                output_video_path=video_path,
                thumbnail_path=thumbnail_generated,
                channel_name=title
            )
            
            # 8. Mark Complete
            with jobs_lock:
                job["status"] = "completed"
                job["stage"] = "Completed"
                job["progress"] = 100
                job["video_filename"] = video_filename
                job["thumbnail_filename"] = thumb_filename if thumbnail_generated else None
                job["meta_dict"] = meta_dict
                job["video_url"] = f"/api/jobs/{job_id}/video"
                job["thumbnail_url"] = f"/api/jobs/{job_id}/thumbnail" if thumbnail_generated else None
                # 3D video fields
                job["video_3d_filename"] = video_3d_filename if video_3d_success else None
                job["video_3d_url"] = f"/api/jobs/{job_id}/video3d" if video_3d_success else None
                job["video_3d_status"] = "completed" if video_3d_success else job.get("video_3d_status", "failed")
                job["rendering_mode"] = rendering_mode
                job["enhancement_report"] = enhancement_report
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            with jobs_lock:
                job["status"] = "failed"
                job["stage"] = "Failed"
                job["error"] = str(e)


# Start background worker daemon
worker_thread = threading.Thread(target=background_job_worker, daemon=True)
worker_thread.start()


@app.route("/")
def index():
    """Serves the isolated interactive drawing studio frontend."""
    return render_template("studio.html")


@app.route("/api/system-info", methods=["GET"])
def system_info():
    """Provides host LAN IP, port, and system status."""
    lan_ip = get_lan_ip()
    return jsonify({
        "status": "online",
        "lan_ip": lan_ip,
        "port": app.config.get("PORT", 8000),
        "canvas_size": {"width": 1080, "height": 1920}
    })


@app.route("/api/upload-reference", methods=["POST"])
def upload_reference():
    """Accepts and validates reference image uploads."""
    if "reference_image" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded under key 'reference_image'"}), 400
        
    file = request.files["reference_image"]
    if not file or not file.filename:
        return jsonify({"success": False, "error": "Empty file received"}), 400
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            "success": False,
            "error": f"Unsupported file type '{ext}'. Allowed formats: PNG, JPG, JPEG, WebP."
        }), 400
        
    safe_name = secure_filename(file.filename)
    unique_name = f"{uuid4().hex[:10]}_{safe_name}"
    save_path = UPLOADS_DIR / unique_name
    
    file.save(str(save_path))

    geometry_data = None
    try:
        ref_geom = preprocess_reference_image(str(save_path))
        if len(ref_geom.paths) == 0 or len(ref_geom.skel_points) < 8:
            if save_path.exists():
                save_path.unlink()
            return jsonify({
                "success": False,
                "error": "No valid black linework or Kolam patterns detected on the blueprint. Please upload a clear sketch with dark lines."
            }), 400
        geometry_data = serialize_reference_geometry(ref_geom)
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        return jsonify({
            "success": False,
            "error": f"Failed to extract blueprint geometry: {str(e)}"
        }), 400

    return jsonify({
        "success": True,
        "filename": unique_name,
        "image_url": f"/api/uploads/{unique_name}",
        "geometry": geometry_data
    })


@app.route("/api/uploads/<path:filename>")
def serve_upload(filename: str):
    """Safely serves uploaded reference images from the uploads folder."""
    return send_from_directory(str(UPLOADS_DIR), filename)


@app.route("/api/generate", methods=["POST"])
def create_generation_job():
    """Receives structured drawing strokes and enqueues video rendering."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid or missing JSON payload"}), 400
        
    try:
        validate_and_normalize_drawing_payload(data)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
        
    job_id = f"job_{time.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    
    with jobs_lock:
        jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "stage": "Queued",
            "progress": 0,
            "error": None,
            "payload": data,
            "created_at": time.time()
        }
        job_queue.append(job_id)
        worker_condition.notify()
        
    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "poll_url": f"/api/jobs/{job_id}"
    })


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Returns real-time status, stage, and progress for the rendering job."""
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify({"success": False, "error": "Job not found"}), 404
            
        return jsonify({
            "success": True,
            "job_id": job["id"],
            "status": job["status"],
            "stage": job["stage"],
            "progress": job["progress"],
            "error": job.get("error"),
            "video_url": job.get("video_url"),
            "thumbnail_url": job.get("thumbnail_url"),
            "meta_dict": job.get("meta_dict"),
            # 3D video fields
            "video_3d_url": job.get("video_3d_url"),
            "video_3d_status": job.get("video_3d_status"),
            "video_3d_error": job.get("video_3d_error"),
            "rendering_mode": job.get("rendering_mode"),
        })


@app.route("/api/jobs/<job_id>/video", methods=["GET"])
def get_job_video(job_id: str):
    """Streams the completed MP4 video."""
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job.get("status") != "completed":
            return jsonify({"error": "Video not ready or job not found"}), 404
        video_filename = job.get("video_filename")
        
    target = OUTPUTS_DIR / video_filename
    if not target.exists():
        return jsonify({"error": "Video file not found on disk"}), 404
        
    return send_file(str(target), mimetype="video/mp4", as_attachment=False)


@app.route("/api/jobs/<job_id>/thumbnail", methods=["GET"])
def get_job_thumbnail(job_id: str):
    """Streams the generated YouTube Short thumbnail."""
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job.get("status") != "completed":
            return jsonify({"error": "Thumbnail not ready or job not found"}), 404
        thumb_filename = job.get("thumbnail_filename")
        if not thumb_filename:
            return jsonify({"error": "Thumbnail was not created"}), 404
            
    target = OUTPUTS_DIR / thumb_filename
    if not target.exists():
        return jsonify({"error": "Thumbnail file not found on disk"}), 404
        
    return send_file(str(target), mimetype="image/jpeg", as_attachment=False)


@app.route("/api/jobs/<job_id>/video3d", methods=["GET"])
def get_job_video_3d(job_id: str):
    """Streams the completed 3D-enhanced MP4 video."""
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job.get("status") != "completed":
            return jsonify({"error": "Video not ready or job not found"}), 404
        video_3d_filename = job.get("video_3d_filename")
        if not video_3d_filename:
            return jsonify({"error": "3D video not available for this job"}), 404

    target = OUTPUTS_DIR / video_3d_filename
    if not target.exists():
        return jsonify({"error": "3D video file not found on disk"}), 404

    return send_file(str(target), mimetype="video/mp4", as_attachment=False)


def run_server(host: str = "0.0.0.0", port: int = 8000, drawing_speed: float = 1.2):
    """Prints network URLs and launches the web server."""
    lan_ip = get_lan_ip()
    app.config["PORT"] = port
    app.config["DRAWING_SPEED"] = drawing_speed
    
    print("\n" + "=" * 68)
    print(" 🎨  KOLAM VIDEO GENERATOR V2 - INTERACTIVE DRAWING STUDIO")
    print("=" * 68)
    print(f" 💻  Local Host Access:      http://localhost:{port}")
    print(f"                            http://127.0.0.1:{port}")
    print(f" 📱  LAN / Wi-Fi Access:     http://{lan_ip}:{port}")
    print(f" ⚡  Drawing Speed:          {drawing_speed}x (smooth natural hand)")
    print("=" * 68)
    print(" 💡  Connect any smartphone, tablet, or laptop on your local Wi-Fi")
    print(f"     by opening: http://{lan_ip}:{port}")
    print(" 🛡️  Windows Firewall Note: If other devices cannot connect, allow")
    print(f"     TCP port {port} in Windows Defender Firewall for Private Networks.")
    print("=" * 68 + "\n")
    
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start Kolam Interactive Drawing Studio")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0 for LAN)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--drawing-speed", type=float, default=1.2, help="Default drawing speed multiplier (default: 1.2)")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, drawing_speed=args.drawing_speed)
