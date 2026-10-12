# Headless Kolam Video Generator V2 - AI Agent System Specification & Architecture Reference

> **Document Type:** Master AI Agent Operational & Architectural Specification  
> **Target Audience:** Autonomous AI Coding Agents, Pair Programmers, Multimodal LLMs, and Human Engineers  
> **Last Updated:** October 2026  
> **Repository Root:** `D:\kolam video generation v2`

---

## 1. Executive Summary & System Mission

The **Headless Kolam Video Generator V2** is an automated, end-to-end multimedia generative pipeline designed to turn hand-drawn sketches, traditional Kolam patterns, and Rangoli drawings into high-retention, YouTube Shorts-compliant vertical videos (`1080x1920`, `25 FPS`, H.264, vertical 9:16 aspect ratio, duration < 60s).

The pipeline operates completely **headless** (zero GUI, zero manual human intervention required for rendering) and integrates:
1. **Multimodal Visual Classification** (Local LLM via Ollama LLaVA-7B with deterministic OpenCV geometric/HSV fallbacks).
2. **Parametric Dot Grid Generation** (Standard pulli diamond/matrix grids).
3. **Continuous Path Vectorization** (Bezier loop weaving for Sikku, radial concentric contour tracing for Mandalas/Rangolis).
4. **Hardware-Accelerated Frame Compositing** (NVIDIA NVENC H.264 rendering with realistic pen/hand overlay, wooden background, and animated branding badges).
5. **Procedural Auspicious Coloring Thumbnail Generation** (Connected-component color filling, 3D powder depth distance transforms, drop shadows, and high-CTR badges).
6. **Acoustic Vocal-Removed BGM Processing** (Center-channel vocal attenuation with punchy low-frequency bass preservation, looped seamlessly and muxed via FFmpeg).
7. **Dynamic Bilingual SEO & Metadata Engine** (Tamil + English click-worthy titles, descriptions, and motif-aware tags).
8. **YouTube Data API v3 Automated Publishing** (Direct OAuth2 upload with custom thumbnail attachment and automated categorization).

---

## 2. Host System & Hardware Specifications

All AI agents executing, profiling, or debugging code on this system must account for the following host hardware environment and operating system constraints:

### 2.1 Hardware Architecture
| Component | Specification | Details / Agent Implications |
| :--- | :--- | :--- |
| **Operating System** | **Microsoft Windows 11 Pro 64-bit** | Build: `10.0.26300` (Release 2026) |
| **CPU** | **AMD Ryzen 5 5600X** | 6 Physical Cores, 12 Logical Processors (~3.70 GHz base, boost up to 4.6 GHz) |
| **System Memory (RAM)** | **32 GB DDR4** | Total Visible: ~33.45 GB (`33,452,504 KB`), Available: ~24.8 GB |
| **Dedicated GPU** | **NVIDIA GeForce RTX 3060 Ti** | 8 GB GDDR6 (`8,192 MiB` VRAM), Driver `617.42` / `32.0.16.1742` |
| **CUDA Runtime** | **CUDA 13.4 UMD / PyTorch cu130** | Supports PyTorch `2.9.1+cu130`, torchvision, torchaudio |
| **Video Hardware Encoder** | **NVIDIA NVENC (Ampere 7th Gen)** | Target codec: `h264_nvenc`, Preset: `p6`, Bitrate: `8M`, Pixel Format: `yuv420p` |

### 2.2 Software & Toolchain Specifications
| Tool / Environment | Version / Configuration | Agent Operational Notes |
| :--- | :--- | :--- |
| **Python Runtime** | `Python 3.10.6 (64-bit)` | Located in standard Windows PATH (`python.exe`) |
| **FFmpeg Binary** | `FFmpeg 7.1-full_build-www.gyan.dev` | Built with GCC 14.2.0 (MSYS2). Full NVENC, ffprobe, and complex filter graph support |
| **OpenCV** | `4.8.1.78` / `4.10.0.84-headless` | `cv2` with SIMD acceleration for contour detection, dilation, distanceTransform |
| **Pillow (PIL)** | `12.3.0` | Font rendering (`arialbd.ttf`, `seguiemj.ttf` for emojis) |
| **Local Vision LLM (Optional)** | `Ollama` running `llava:7b` | Standard REST endpoint: `http://localhost:11434/api/generate` |
| **Google APIs** | `google-api-python-client`, `google-auth-oauthlib` | YouTube Data API v3 OAuth 2.0 integration |
| **Music Library** | `D:\ncs music` | Contains royalty-free audio tracks (`.mp3`, `.wav`, `.m4a`) |

### 2.3 Windows Platform Specifics Handled in Code
1. **IPv6 WinError 10060 Timeout Bypass:** Windows IPv6 dual-stack resolution causes 20+ second delays or connection dropouts when communicating with Google OAuth/YouTube endpoints. The codebase monkey-patches `socket.getaddrinfo` to force IPv4 (`AF_INET`).
2. **Tamil Unicode Output Encoding:** To prevent Windows console crashes (`cp1252` encoding errors) when printing Tamil characters (e.g., `ரங்கோலி கோலம்`), `sys.stdout` and `sys.stderr` are reconfigured to `utf-8` with `errors="replace"`.
3. **Piping via Subprocess to FFmpeg:** Video frames are streamed via standard input (`stdin.write(frame.tobytes())`) into a persistent FFmpeg NVENC process to avoid disk I/O bottlenecks.

---

## 3. Repository Directory Structure

```text
D:\kolam video generation v2\
│
├── generate.py                     # [Entrypoint] Main orchestration CLI script
├── upload_to_youtube.py            # [CLI Tool] Standalone YouTube Shorts uploader
├── requirements.txt                # Core Python package dependencies
├── README.md                       # High-level project documentation
├── AI_SYSTEM_DOC.md                # [This File] Master specification for AI agents
│
├── generate.bat                    # One-click batch runner (drag-and-drop input image)
├── upload_to_youtube.bat           # One-click batch uploader for latest outputs
├── reset_youtube_account.bat       # Token flush script to switch Google accounts
│
├── client_secrets.json             # Google Cloud OAuth 2.0 Client credentials (Secret)
├── client_secrets.json.example     # Template for Google OAuth setup
├── youtube_token.pickle            # Cached OAuth access & refresh token session
│
├── engine/                         # Core algorithm & processing modules
│   ├── classifier.py               # Visual classification (Ollama LLaVA + CV heuristics)
│   ├── dot_generator.py            # Mathematical dot matrix & pulli grid generator
│   ├── path_generator.py           # Path calculation, Bezier interpolation & contour tracing
│   ├── renderer.py                 # NVENC/OpenCV frame renderer, hand & badge overlays
│   ├── thumbnail_generator.py      # Auspicious color filling, 3D powder & cover generator
│   ├── audio_processor.py          # Acoustic vocal removal, DSP filter graph & audio muxer
│   ├── seo_generator.py            # Visual motif analysis & Tamil-English SEO generator
│   ├── youtube_uploader.py         # YouTube Data API v3 uploader & metadata sync
│   └── assets/                     # Core static visual assets
│       ├── hand_raw.png            # Transparent hand sprite holding pen
│       ├── hand_raw22.png          # High-resolution alternative hand sprite
│       ├── wood.jpg                # 1080x1920 realistic wood background texture
│       └── wood1.jpg               # Alternative wood surface texture
│
├── inputs/                         # Input sketches and reference materials
│   ├── 77d59084...-sketch (1).jpg  # Sample input sketch
│   └── reference.mp4               # Golden reference target video
│
└── outputs/                        # Generated output artifacts (*.mp4, *_thumbnail.jpg, *_metadata.txt)
```

---

## 4. End-to-End Pipeline Workflow

The execution flow consists of 7 sequential phases coordinated by [generate.py](file:///d:/kolam%20video%20generation%20v2/generate.py):

```mermaid
flowchart TD
    A["Input Sketch (Image File)"] --> B["Phase 1: Classifier (engine/classifier.py)"]
    B -->|Kolam Type & Grid Spec| C["Phase 2: Dot Generator (engine/dot_generator.py)"]
    B -->|Type + Image Matrix| D["Phase 3: Path Generator (engine/path_generator.py)"]
    C -->|Dot Coordinates| D
    
    D -->|2D Traversal Vector| E["Phase 4: Thumbnail Generator (engine/thumbnail_generator.py)"]
    C -->|Dot Coordinates| E
    E -->|Teaser Cover Image (1080x1920)| F["Phase 5: Renderer Engine (engine/renderer.py)"]
    
    D -->|Coordinate Points| F
    C -->|Dot Positions| F
    F -->|Raw Video (1080x1920, 25 FPS)| G["Phase 6: Audio Processor (engine/audio_processor.py)"]
    
    G -->|Muxed Video with Vocal-Removed BGM| H["Phase 7: Dynamic SEO Engine (engine/seo_generator.py)"]
    H -->|Metadata File (*_metadata.txt)| I{"User / CLI Upload Flag"}
    
    I -->|--upload or Interactive Yes| J["Phase 8: YouTube Uploader (engine/youtube_uploader.py)"]
    I -->|--no-upload or Skipped| K["Finished: Ready in outputs/"]
```

---

## 5. Subsystem Deep-Dive & Module Specifications

### 5.1 CLI Orchestrator (`generate.py`)
- **Primary Function:** Parses command-line arguments, auto-discovers inputs in `inputs/`, executes phases 1 through 8 in sequential lockstep, and logs structured progress.
- **Key CLI Arguments:**
  - `--input`, `-i`: Path to the input sketch image. If omitted, auto-selects the first `.jpg`/`.png` in `inputs/`.
  - `--output`, `-o`: Target `.mp4` file path (defaults to dynamic `outputs/<basename>_<timestamp>.mp4`).
  - `--type`, `-t`: Kolam classification (`auto`, `pulli_kolam`, `sikku_kolam`, `rangoli`, `mandala`).
  - `--grid`, `-g`: Dot grid format (`8x2`, `6x2`, `none`).
  - `--fps`: Target frames per second (default: `25`).
  - `--no-hand`: Boolean switch to disable the hand/pen overlay.
  - `--no-watermark`: Disables footer watermark badge (`LIKE | SHARE | SUBSCRIBE`).
  - `--no-thumbnail`: Disables procedural colored thumbnail generation.
  - `--music-dir`: Path to background music directory (default: `D:\ncs music`).
  - `--no-music`: Skips audio processing and muxing.
  - `--music-volume`: Float volume multiplier (default: `1.3`).
  - `--title`: Channel / Series title displayed on badges (default: `AK Kolam`).
  - `--upload`: Automatically uploads to YouTube without prompting.
  - `--no-upload`: Completely skips YouTube upload prompt.
  - `--privacy`: Upload privacy state (`public`, `unlisted`, `private`).

---

### 5.2 Vision Classification (`engine/classifier.py`)
- **Module Purpose:** Detects whether an input drawing is a dot-based Kolam or a continuous contour Rangoli/Mandala, and infers the grid size.
- **Layer 1: Multimodal Local LLM (`classify_kolam_local_llm`)**
  - Sends a Base64-encoded payload to `http://localhost:11434/api/generate` with model `llava:7b`.
  - Prompt enforces strict JSON schema: `{"type": "...", "dot_grid": "...", "confidence": 0-1}`.
  - Timeout: 15 seconds.
- **Layer 2: Deterministic Heuristic Fallback (`classify_heuristic`)**
  - If Ollama is offline or times out, triggers CV-based heuristics:
    1. **Color Saturation:** Calculates mean HSV saturation (`np.mean(hsv[:,:,1])`). If `mean_sat > 60` and large contours exist, classified as `rangoli`.
    2. **Dot Blob Counting:** Inverts grayscale image and finds contours with area $5 < \text{area} < 200$. If `count >= 20`, classified as `sikku_kolam` with `8x2` grid.
    3. **Circular Symmetry:** If large contours exist without dot clusters, classified as `mandala`.
    4. **Default Fallback:** `pulli_kolam` with `8x2` grid.

---

### 5.3 Geometric Dot Grid Generator (`engine/dot_generator.py`)
- **Module Purpose:** Computes precise pixel coordinates $(x, y)$ for the traditional dot grid on a $1080 \times 1920$ canvas.
- **Grid Modes:**
  - `8x2` Diamond Grid: 40 total dots configured in rows of `[2, 4, 6, 8, 8, 6, 4, 2]`. Horizontal and vertical spacing: $110\text{ px}$. Top offset: $Y = 480$.
  - `6x2` Diamond Grid: Rows of `[2, 4, 6, 6, 4, 2]`. Spacing: $120\text{ px}$, Top offset: $Y = 550$.
  - `none`: Returns an empty list `[]` for freehand Rangoli or circular Mandalas.

---

### 5.4 Stroke Vectorization & Path Generator (`engine/path_generator.py`)
- **Module Purpose:** Converts discrete dot grids or sketch images into an ordered, continuous trajectory of 2D coordinates representing the artist's stroke.
- **Stroke Delimiter Protocol:** Uses Python `None` entries in the path list as a **Pen-Up Signal**. When the pen encounters `None`, it lifts and moves to the next coordinate without drawing an connecting line.
- **Algorithms by Style:**
  1. **Sikku Kolam (`generate_sikku_8x2_path`):** Uses quadratic Bezier curves ($\mathbf{B}(t) = (1-t)^2 P_0 + 2(1-t)t P_1 + t^2 P_2$) to route interlaced loops through cell centers around dots rather than intersecting them directly.
  2. **Pulli Kolam (`generate_pulli_path`):** Computes linear interpolations directly connecting adjacent dots across rows.
  3. **Rangoli / Mandala Sketch Tracing (`generate_rangoli_path`):**
     - Extracts contours via `cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)`.
     - Normalizes and scales contours to fit within $880 \times 1520$ canvas safe area.
     - Performs **Radial Concentric Layering (Spatial Sorting):** Computes centroid $(\bar{x}, \bar{y})$ and polar coordinates $(r, \theta)$. Bins into concentric radial tiers ($r_{\text{bin}}$) and sorts by angle ($\theta$) to replicate authentic outwards circular drawing.
     - **Overlap Elimination:** Maintains a 2D `visited_mask` (thickness 8). Skips any contour where $>50\%$ of points overlap previously drawn strokes.

---

### 5.5 Video Rendering Engine (`engine/renderer.py`)
- **Module Purpose:** Generates individual video frames, applies overlays, and streams bytes to the video encoder.
- **Frame Composition Stack (Bottom to Top):**
  1. **Background Layer:** Textured wood background ($1080 \times 1920$).
  2. **Dot Grid Layer:** Anti-aliased white circles ($r=5\text{ px}$, color `#FFFFFF`).
  3. **Progressive Stroke Layer:** Anti-aliased white line segments ($6\text{ px}$ thickness).
  4. **Animated Pen / Hand Sprite:** Hand image with transparent alpha background, rotated and translated so the pen tip aligns exactly with the current stroke head.
  5. **Header Pill Badge:** Modern glassmorphism pill displaying `--title` (e.g. `AK Kolam`) with drop shadow and gold outline ($Y=130$).
  6. **Footer Pill Badge:** High-retention subscriber badge (`👍 LIKE | ↗ SHARE | 🔔 SUBSCRIBE`) rendered in the mobile-safe zone ($Y=1730$).
- **Opening Teaser Hook:** Renders 15 frames (~0.6 seconds) of the finished, colorized thumbnail with a 3-frame crossfade into the blank canvas to ensure YouTube Shorts displays an attractive cover.
- **Video Encoding Pipeline:**
  - Primary: FFmpeg subprocess pipe streaming raw BGR24 frames directly to NVIDIA NVENC (`h264_nvenc -preset p6 -b:v 8M -pix_fmt yuv420p`).
  - Fallback: `cv2.VideoWriter(..., fourcc='mp4v')` if FFmpeg is unavailable.
- **Holding Period:** Renders 25 additional frames (1.0 second) of the completed art piece before terminating.

---

### 5.6 Auspicious Color Thumbnail Engine (`engine/thumbnail_generator.py`)
- **Module Purpose:** Transforms black-and-white input sketches into vibrantly colored, high-click-through-rate (CTR) YouTube Shorts thumbnails ($1080 \times 1920$, 9:16).
- **Core Algorithms:**
  1. **Polar Cell Segmentation:** Morphologically closes sketch lines, inverts the binary image, and segments enclosed regions via `cv2.connectedComponentsWithStats`.
  2. **Traditional Indian Color Harmonization:** Maps concentric rings and alternating sectors to a curated traditional Indian palette:
     - Kumkum Crimson Red (`#E41C2A`)
     - Turmeric Gold Yellow (`#FFDA1C`)
     - Saffron / Marigold Orange (`#FF841E`)
     - Lotus Pink / Magenta (`#F837B9`)
     - Peacock Royal Blue (`#127ADA`)
     - Parrot / Lime Green (`#30C341`)
  3. **3D Powder Depth & Texture:** Applies a distance transform (`cv2.distanceTransform(cells, cv2.DIST_L2, 3)`) combined with Gaussian noise to give the impression of physical, raised Rangoli powder piles.
  4. **White Flour Ridge Outlines:** Overlays crisp white rice-flour boundaries over all segment borders.
  5. **Banner & Badge Composition:** Overlays frosted glass category banners (`SIKKU KOLAM | 8x2`, `MANDALA KOLAM DESIGN`), gold-bordered title pills, and mobile-safe footer branding.

---

### 5.7 Audio Processing Engine (`engine/audio_processor.py`)
- **Module Purpose:** Adds background music while eliminating distracting lyrics or speech.
- **Vocal-Removal Acoustic Filter Graph:**
  Implements an active center-channel phase cancellation filter with bass preservation:
  ```text
  [1:a] asplit=2 [b][m];
  [b] lowpass=f=180 [bass];
  [m] highpass=f=180, pan=stereo|c0=c0-c1|c1=c1-c0 [mid];
  [bass][mid] amix=inputs=2, volume=1.3, afade=t=in:ss=0:d=1, afade=t=out:st=<end-2>:d=2 [aout]
  ```
  - **Bass Route (`< 180 Hz`):** Isolates kick drums and basslines in mono, preventing low-end phase cancellation.
  - **Mid/High Route (`> 180 Hz`):** Applies $L - R$ and $R - L$ center-channel cancellation to strip lead vocals.
  - **Recombination & Dynamics:** Mixes bass and stereo instrumental, applies smooth 1-second fade-in and 2-second fade-out matching video duration.
- **Audio Looping:** Uses `-stream_loop -1` so shorter tracks loop seamlessly across longer video renders.
- **Stream Copy:** Uses `-c:v copy` to mux audio into video losslessly in $<0.5$ seconds without re-encoding video frames.

---

### 5.8 Dynamic Bilingual SEO Engine (`engine/seo_generator.py`)
- **Module Purpose:** Generates high-CTR, non-generic YouTube metadata strictly respecting platform character limits.
- **Motif Detection:** Analyzes contour geometry, aspect ratios, convexity hulls, and polar FFT symmetry to classify motifs into: `sikku`, `pulli`, `lotus`, `bell`, `flower`, `mandala`, or `rangoli`.
- **Title Construction:** Creates bilingual titles under YouTube's strict 100-character limit:
  - Format: `<Channel> | <Tamil Title> | <English Title> #shorts`
  - Example: `AK Kolam | அழகான ரங்கோலி கோலம் 🌸 | Easy Rangoli Design #shorts`
- **Metadata Serialization:** Writes a structured `*_metadata.txt` file alongside the output video, containing:
  - Exact target video path
  - Thumbnail path
  - Click-worthy title
  - Formatted description with chapter tags and timestamps
  - Comma-separated YouTube search tags (< 450 characters total)

---

### 5.9 YouTube Data API v3 Publisher (`engine/youtube_uploader.py` & `upload_to_youtube.py`)
- **Module Purpose:** Uploads video and attaches custom thumbnails to YouTube.
- **Authentication Lifecycle:**
  1. Checks for cached token in `youtube_token.pickle`.
  2. If expired, attempts refresh using refresh token.
  3. If missing, looks for `client_secrets.json`, launches local OAuth server (`port=0`), and prompts user via browser.
  4. Saves token to `youtube_token.pickle` for completely headless subsequent runs.
- **YouTube Studio Parameter Standardization:**
  - `categoryId`: `"26"` (Howto & Style - standard for arts and crafts)
  - `selfDeclaredMadeForKids`: `False` (Not Made for Kids)
  - `containsSyntheticMedia`: `False` (Traditional art creation)
  - `embeddable`: `True`
  - `license`: `"youtube"` (Standard YouTube License)
  - `privacyStatus`: `public` (or overridden via CLI)
  - `defaultLanguage`: `"ta"` (Tamil)
- **Custom Thumbnail Attachment:** Automatically uploads `*_thumbnail.jpg` via `youtube.thumbnails().set(videoId=..., media_body=...)`.

---

### 5.10 Automation Batch Scripts
- `generate.bat`: Windows drag-and-drop interface. Allows dropping any image directly onto the batch file to initiate generation.
- `upload_to_youtube.bat`: Automatically scans `outputs/` for the most recent metadata or `.mp4` file and initiates upload.
- `reset_youtube_account.bat`: Clears `youtube_token.pickle` to force re-authentication with a different Google account.

---

## 6. Data Contracts & Internal Schemas

### 6.1 Path Point Delimiter Contract
The drawing path passed to `render_kolam_video` must be a list of 2D tuples or `None`:
```python
path: list[tuple[int, int] | None]
# Valid examples:
# [(540, 480), (541, 482), None, (620, 700), (622, 702)]
```
- **Coordinate System:** Origin `(0, 0)` is top-left, `(1080, 1920)` is bottom-right.
- **`None` Protocol:** Signals that the stroke has ended. The hand/pen will be lifted and repositioned to the next non-`None` point without drawing a connecting segment.

### 6.2 Metadata File Format (`*_metadata.txt`)
The uploader parses metadata files matching this format:
```text
Video: outputs/sketch_20261012_230000.mp4
Thumbnail: outputs/sketch_20261012_230000_thumbnail.jpg

📌 TITLE (Click-Worthy & Search Optimized):
AK Kolam | அழகான ரங்கோலி கோலம் 🌸 | Easy Rangoli Design #shorts

📝 DESCRIPTION:
🌸 AK Kolam - Daily Simple & Beautiful Kolam Designs.
...

🏷️ TAGS:
AK Kolam, kolam, rangoli, pulli kolam, shorts
```

---

## 7. Operational Guidelines for Future AI Agents

When interacting with or extending this codebase, all AI agents **must strictly adhere** to these rules:

1. **Preserve Headless Execution:**
   - **Never** add blocking GUI dialogs (e.g., `cv2.imshow()`, `plt.show()`, or Tkinter windows) to core pipelines.
   - All status, progress, and warnings must be routed through `print()` or standard logging.

2. **Preserve Windows System Patches:**
   - Always retain the IPv4 resolution monkey-patch (`socket.getaddrinfo = _ipv4_getaddrinfo`) in entrypoint scripts. Removing this will cause YouTube API calls to hang on Windows.
   - Always retain UTF-8 reconfigurations (`sys.stdout.reconfigure(encoding="utf-8")`) to prevent Windows console encoding crashes on Tamil text.

3. **Coordinate & Bounds Checking:**
   - All coordinates passed to `cv2.line`, `cv2.circle`, or array indexing must be explicitly clamped: $0 \le x < 1080$ and $0 \le y < 1920$.
   - Any path point conversion must cast coordinates to native integers (`int(x)`, `int(y)`).

4. **Hardware Acceleration First:**
   - When modifying `engine/renderer.py`, preserve the FFmpeg NVENC streaming implementation (`h264_nvenc`). Do not replace it with slow CPU-based encoding unless falling back after an explicit error.

5. **Audio Stream Integrity:**
   - Always use `-c:v copy` during audio muxing in `engine/audio_processor.py`. Never re-encode video packets during audio merging.

6. **YouTube Character Limits:**
   - Video titles **must never exceed 100 characters** (enforced by `smart_trim_title`).
   - Video tags **must never exceed 450 total characters** when joined.

---

## 8. Troubleshooting & Common Pitfalls

| Symptom | Root Cause | AI Agent Remediation |
| :--- | :--- | :--- |
| `WinError 10060` during YouTube upload | Windows attempted IPv6 connection to Google OAuth servers and timed out | Verify `socket.getaddrinfo` is monkey-patched to `AF_INET` at the top of the executing script. |
| `UnicodeEncodeError: 'charmap' codec can't encode characters` | Windows default console (`cp1252`) attempted to print Tamil Unicode characters | Check that `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` executed before printing. |
| Hand sprite flickers or jumps erratically | Path contains consecutive `None` values or invalid coordinate jumps | Ensure path interpolation cleans adjacent `None` values and maintains continuous trajectories. |
| Thumbnail custom upload fails with HTTP 403 | YouTube channel is not phone-verified for custom thumbnails | Normal YouTube policy for new accounts. Video still publishes successfully; thumbnail is already baked into opening video frames as a teaser. |
| Rendering is unusually slow (< 5 FPS) | FFmpeg failed to initialize NVENC and fell back to CPU `cv2.VideoWriter` | Run `nvidia-smi` to ensure GPU is accessible; check that FFmpeg in PATH supports `h264_nvenc`. |
| Audio track is trimmed or video ends abruptly | `-shortest` flag passed to FFmpeg | Ensure `-stream_loop -1` is used for audio and `-t <duration>` is set strictly to the video length. |

---

## 9. Verification & Quick Test Commands

To verify the entire environment and pipeline functionality, an AI agent can execute:

```powershell
# 1. Verify Python & GPU Encoder
python -c "import cv2, torch; print('OpenCV:', cv2.__version__, '| CUDA Available:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0))"

# 2. Test FFmpeg NVENC Availability
ffmpeg -f lavfi -i testsrc=size=1080x1920:rate=25 -vcodec h264_nvenc -t 1 -f null -

# 3. Run a Fast End-to-End Test Video Generation
python generate.py --input "inputs/77d590840016a86bc06d5770114539a4-sketch (1).jpg" --type mandala --no-upload
```
