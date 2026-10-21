"""
ComfyUI Bridge - Optional AI Enhancement Layer
Headless Kolam Video Generator V2/V3

Provides discovery, health-check, and workflow submission for ComfyUI-based
AI visual enhancement. Falls back gracefully to deterministic 3D rendering
when ComfyUI is unavailable.

Configuration via environment variables:
  COMFYUI_URL       - ComfyUI server address (default: http://127.0.0.1:8188)
  COMFYUI_TIMEOUT   - Request timeout in seconds (default: 30)
"""

import os
import json
import time
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("kolam.comfyui_bridge")


class ComfyUIStatus:
    """Result of ComfyUI environment discovery."""
    def __init__(self):
        self.installed = False
        self.server_running = False
        self.api_reachable = False
        self.server_url = ""
        self.models_available = []
        self.custom_nodes = []
        self.error_message = ""
        self.vram_mb = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "installed": self.installed,
            "server_running": self.server_running,
            "api_reachable": self.api_reachable,
            "server_url": self.server_url,
            "models_available": self.models_available,
            "custom_nodes": self.custom_nodes,
            "error_message": self.error_message,
            "vram_mb": self.vram_mb,
        }

    @property
    def usable(self) -> bool:
        return self.installed and self.server_running and self.api_reachable


def _get_comfyui_url() -> str:
    """Get ComfyUI server URL from environment or default."""
    return os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")


def _get_timeout() -> int:
    """Get request timeout from environment or default."""
    try:
        return int(os.environ.get("COMFYUI_TIMEOUT", "30"))
    except (ValueError, TypeError):
        return 30


def discover_comfyui() -> ComfyUIStatus:
    """
    Discovers whether ComfyUI is installed, running, and API-accessible.
    
    Checks:
    1. Common installation directories
    2. Whether the server is responding on the configured URL
    3. Available models and custom nodes
    4. GPU VRAM availability
    """
    status = ComfyUIStatus()
    base_url = _get_comfyui_url()
    status.server_url = base_url
    timeout = _get_timeout()

    # 1. Check common installation paths
    common_paths = [
        Path("C:/ComfyUI"),
        Path("D:/ComfyUI"),
        Path(os.path.expanduser("~/ComfyUI")),
        Path(os.path.expanduser("~/Desktop/ComfyUI")),
    ]
    comfyui_env = os.environ.get("COMFYUI_PATH", "")
    if comfyui_env:
        common_paths.insert(0, Path(comfyui_env))

    for p in common_paths:
        if p.exists() and (p / "main.py").exists():
            status.installed = True
            break
        if p.exists() and (p / "comfy").is_dir():
            status.installed = True
            break

    # 2. Check server health
    try:
        req = urllib.request.Request(f"{base_url}/system_stats", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                status.server_running = True
                status.api_reachable = True
                data = json.loads(resp.read().decode("utf-8"))
                # Extract VRAM info if available
                devices = data.get("devices", [])
                for dev in devices:
                    vram_total = dev.get("vram_total", 0)
                    if vram_total > 0:
                        status.vram_mb = int(vram_total / (1024 * 1024))
    except urllib.error.URLError:
        status.error_message = f"ComfyUI server not reachable at {base_url}"
    except Exception as e:
        status.error_message = f"ComfyUI discovery error: {str(e)}"

    # 3. Check available models
    if status.api_reachable:
        try:
            req = urllib.request.Request(f"{base_url}/object_info", method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    node_info = json.loads(resp.read().decode("utf-8"))
                    status.custom_nodes = list(node_info.keys())[:50]
        except Exception:
            pass

        # Check checkpoint models
        try:
            req = urllib.request.Request(
                f"{base_url}/object_info/CheckpointLoaderSimple", method="GET"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    info = json.loads(resp.read().decode("utf-8"))
                    ckpt_input = info.get("CheckpointLoaderSimple", {}).get("input", {})
                    required = ckpt_input.get("required", {})
                    ckpt_names = required.get("ckpt_name", [])
                    if isinstance(ckpt_names, list) and len(ckpt_names) > 0:
                        if isinstance(ckpt_names[0], list):
                            status.models_available = ckpt_names[0][:20]
                        else:
                            status.models_available = ckpt_names[:20]
        except Exception:
            pass

    if not status.installed and not status.server_running:
        status.error_message = (
            "ComfyUI not found. Install ComfyUI and start its server, "
            "or set COMFYUI_URL environment variable."
        )

    return status


def submit_workflow(workflow: Dict[str, Any], timeout: int = 120) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Submit a workflow to ComfyUI's API queue.
    
    Returns:
        (success, prompt_id_or_error, response_data)
    """
    base_url = _get_comfyui_url()
    
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            prompt_id = data.get("prompt_id", "")
            if prompt_id:
                return True, prompt_id, data
            error = data.get("error", "Unknown error")
            return False, str(error), data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return False, f"HTTP {e.code}: {body[:500]}", {}
    except Exception as e:
        return False, str(e), {}


def poll_prompt_status(prompt_id: str, timeout: int = 300, poll_interval: float = 2.0) -> Tuple[bool, Dict[str, Any]]:
    """
    Poll ComfyUI for prompt completion status.
    
    Returns:
        (completed_successfully, status_data)
    """
    base_url = _get_comfyui_url()
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(f"{base_url}/history/{prompt_id}", method="GET")
            with urllib.request.urlopen(req, timeout=_get_timeout()) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if prompt_id in data:
                    prompt_data = data[prompt_id]
                    status = prompt_data.get("status", {})
                    completed = status.get("completed", False)
                    if status.get("status_str") == "success" or completed:
                        return True, prompt_data
                    if status.get("status_str") == "error":
                        return False, prompt_data
        except Exception:
            pass

        time.sleep(poll_interval)

    return False, {"error": f"Timeout after {timeout}s waiting for prompt {prompt_id}"}


def download_output(prompt_id: str, output_dir: str) -> list:
    """
    Download output images/videos from a completed ComfyUI prompt.
    
    Returns list of downloaded file paths.
    """
    base_url = _get_comfyui_url()
    downloaded = []

    try:
        req = urllib.request.Request(f"{base_url}/history/{prompt_id}", method="GET")
        with urllib.request.urlopen(req, timeout=_get_timeout()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            prompt_data = data.get(prompt_id, {})
            outputs = prompt_data.get("outputs", {})

            os.makedirs(output_dir, exist_ok=True)

            for node_id, node_output in outputs.items():
                for output_type in ("images", "videos"):
                    items = node_output.get(output_type, [])
                    for item in items:
                        filename = item.get("filename", "")
                        subfolder = item.get("subfolder", "")
                        item_type = item.get("type", "output")
                        if not filename:
                            continue

                        view_url = (
                            f"{base_url}/view?"
                            f"filename={filename}&subfolder={subfolder}&type={item_type}"
                        )
                        dest = os.path.join(output_dir, filename)
                        try:
                            urllib.request.urlretrieve(view_url, dest)
                            downloaded.append(dest)
                        except Exception as e:
                            logger.warning(f"Failed to download {filename}: {e}")

    except Exception as e:
        logger.warning(f"Failed to retrieve outputs for prompt {prompt_id}: {e}")

    return downloaded


def get_enhancement_report(status: ComfyUIStatus) -> Dict[str, Any]:
    """
    Generate a structured report about the ComfyUI enhancement capability.
    """
    return {
        "comfyui_available": status.usable,
        "comfyui_url": status.server_url if status.usable else None,
        "enhancement_mode": "comfyui" if status.usable else "deterministic_local",
        "fallback_reason": status.error_message if not status.usable else None,
        "gpu_vram_mb": status.vram_mb if status.vram_mb > 0 else None,
        "models_count": len(status.models_available),
    }
