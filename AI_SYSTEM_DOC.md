# Headless Kolam Video Generator V2 - AI Agent System Specification & Architecture Reference

> **Document Type:** Master AI Agent Operational & Architectural Specification  
> **Target Audience:** Autonomous AI Coding Agents, Pair Programmers, Multimodal LLMs, and Human Engineers  
> **Last Updated:** October 2026  
> **Repository Root:** `D:\kolam video generation v2`

---

## 1. Executive Summary & System Mission

The **Headless Kolam Video Generator V2** is an automated, end-to-end multimedia generative pipeline designed to turn hand-drawn sketches, traditional Kolam patterns, and Rangoli drawings into high-retention, YouTube Shorts-compliant vertical videos (`1080x1920`, `25 FPS`, H.264, vertical 9:16 aspect ratio, duration < 60s).

The system supports two complementary workflows:
1. **Automated Headless CLI Workflow:** Turn static sketch images into progressively drawn videos with zero manual human intervention.
2. **Interactive Drawing Studio Workflow:** Web-based freehand drawing studio accessible locally and over Wi-Fi/LAN, allowing real-time tracing over semi-transparent reference sketches with touch/mouse/stylus.

Core generative subsystems:
1. **Multimodal Visual Classification** (Local LLM via Ollama LLaVA-7B with deterministic OpenCV geometric/HSV fallbacks).
2. **Parametric Dot Grid Generation** (Standard pulli diamond/matrix grids).
3. **Continuous Path Vectorization** (Bezier loop weaving for Sikku, radial concentric contour tracing for Mandalas/Rangolis).
4. **Hardware-Accelerated Frame Compositing** (NVIDIA NVENC H.264 rendering with realistic pen/hand overlay, wooden background, and animated branding badges).
5. **Procedural Auspicious Coloring Thumbnail Generation** (Connected-component color filling, 3D powder depth distance transforms, drop shadows, and high-CTR badges).
6. **Acoustic Vocal-Removed BGM Processing** (Center-channel vocal attenuation with punchy low-frequency bass preservation, looped seamlessly and muxed via FFmpeg).
7. **Dynamic Bilingual SEO & Metadata Engine** (Tamil + English click-worthy titles, descriptions, and motif-aware tags).
8. **YouTube Data API v3 Automated Publishing** (Direct OAuth2 upload with custom thumbnail attachment and automated categorization).
9. **LAN-Accessible Interactive Drawing Studio** (Lightweight Flask backend, responsive HTML5/Canvas frontend, structured vector stroke recording, and real-time generation polling).

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
1. **Native IPv6 & Dual-Stack Networking:** Full IPv6 connectivity is active on the host system. Standard Python dual-stack socket resolution functions natively without artificial IPv4 overrides.
2. **Tamil Unicode Output Encoding:** To prevent Windows console crashes (`cp1252` encoding errors) when printing Tamil characters (e.g., `ரங்கோலி கோலம்`), `sys.stdout` and `sys.stderr` are reconfigured to `utf-8` with `errors="replace"`.
3. **Piping via Subprocess to FFmpeg:** Video frames are streamed via standard input (`stdin.write(frame.tobytes())`) into a persistent FFmpeg NVENC process to avoid disk I/O bottlenecks.

---

## 3. Repository Directory Structure

```text
D:\kolam video generation v2\
│
├── generate.py                     # [CLI Entrypoint] Automated image-to-video orchestrator
├── web_app.py                      # [Web Entrypoint] Interactive Drawing Studio server & REST API
├── upload_to_youtube.py            # [CLI Tool] Standalone YouTube Shorts uploader
├── requirements.txt                # Core Python package dependencies (Flask, OpenCV, etc.)
├── README.md                       # High-level project documentation
├── AI_SYSTEM_DOC.md                # [This File] Master specification for AI agents
│
├── generate.bat                    # One-click batch runner (drag-and-drop input image)
├── start.bat                       # Automated server launcher (LAN discovery, port conflict check, auto-browser)
├── stop.bat                        # Graceful server shutdown & port 8000 cleanup script
├── start_drawing_studio.bat        # Legacy launcher for Drawing Studio
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
│   ├── manual_drawing.py           # Freehand vector stroke normalization & path synthesis
│   ├── reference_alignment.py      # Reference-guided stroke correction & Viterbi path alignment
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
├── web/                            # Interactive Drawing Studio Web Frontend
│   ├── templates/                  # Jinja2 HTML templates
│   │   └── studio.html             # Responsive 9:16 drawing studio interface with floating controls
│   └── static/                     # Frontend static assets
│       ├── studio.css              # Dark-mode styling, responsive multi-breakpoint layout & touch protection
│       └── studio.js               # Pointer event drawing, stroke recorder, undo/redo, floating buttons & API polling
│
├── inputs/                         # Input sketches and reference materials
│   ├── uploads/                    # Reference images uploaded via Drawing Studio
│   ├── 77d59084...-sketch (1).jpg  # Sample input sketch
│   └── reference.mp4               # Golden reference target video
│
├── tests/                          # Automated unit and integration test suite
│   ├── test_manual_drawing.py      # Tests stroke clamping, pen-up signals & sketch creation
│   ├── test_web_api.py             # Integration tests for Flask endpoints & uploads
│   ├── test_reference_alignment.py # Tests skeleton thinning, line extraction & geometry matching
│   ├── test_end_to_end_alignment_render.py # E2E alignment to GPU NVENC video rendering test
│   ├── test_end_to_end_render.py   # Complete vector-to-video NVENC rendering test
│   ├── test_live_snapping.py       # Geometry serialization & live residual refinement tests
│   └── test_browser_snapping.js    # Node.js test suite for browser ReferenceSnapper engine
│
└── outputs/                        # Generated output artifacts (*.mp4, *_thumbnail.jpg, *_metadata.txt)
```

---

## 4. End-to-End Pipeline Workflows

### 4.1 Automated Headless CLI Workflow (`generate.py`)

The automated execution flow turns an existing image file into a video via 8 sequential phases:

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

### 4.2 Interactive Drawing Studio Workflow (`web_app.py`)

The interactive workflow records human drawing strokes in real-time over an optional semi-transparent reference sketch, applies live in-browser reference snapping onto preprocessed skeletons, provides non-destructive residual refinement on the backend, and renders the exact stroke sequence into the identical video composition:

```mermaid
flowchart TD
    subgraph Browser ["Web Client (Phone / Tablet / PC Browser)"]
        UI["Drawing Studio UI (1080x1920 Logical Canvas)"]
        Ref["Uploaded Reference Sketch (Adjustable Opacity 0-100%)"]
        Grid["In-Memory Spatial Grid Index (ReferenceSnapper, 25px cells)"]
        Pointer["Pointer Movement (Mouse, Touch, Stylus)"]
        LiveSnap["Real-Time Attraction & Canvas Draw (lineTo corrected point)"]
        Float["Floating Canvas Quick Controls (Undo / Redo)"]
        Payload["Structured Vector Stroke Payload (live_aligned=true, ref_image, ref_correction)"]

        Ref --> UI
        Ref -.->|Skeleton Geometry JSON| Grid
        Pointer --> LiveSnap
        Grid -.-> LiveSnap
        LiveSnap --> UI
        Float --> UI
        UI --> Payload
    end

    subgraph Backend ["Server & Processing Pipeline (web_app.py)"]
        API["Flask REST API: POST /api/generate"]
        Queue["Background Async Job Queue (1 GPU Job at a Time)"]
        Route{"live_aligned == true?"}
        Residual["refine_live_aligned_strokes (Boundary clamping, loop closure, gentle smoothing)"]
        FullCorr["correct_stroke_sequence (Full multi-cue skeleton & Viterbi deformation)"]
        ManualEng["engine/manual_drawing.py (Validation & Path Synthesis)"]
        SketchGen["Monochrome Sketch Synthesis (temp_sketch.png)"]
        ThumbGen["engine/thumbnail_generator.py (Colorized Short Cover)"]
        Render["engine/renderer.py (NVENC 1080x1920 @ 25 FPS + Hand Animation)"]
        Audio["engine/audio_processor.py (Vocal Removal + BGM Muxing)"]
        SEO["engine/seo_generator.py (Dynamic Tamil + English Metadata)"]
        Complete["Output Artifacts (*.mp4, *_thumbnail.jpg, *_metadata.txt)"]

        Payload --> API
        API --> Queue
        Queue --> Route
        Route -->|Yes: Client already snapped live| Residual
        Route -->|No: Legacy / CLI freehand tracing| FullCorr
        Residual --> ManualEng
        FullCorr --> ManualEng
        ManualEng -->|Ordered Path with None Delimiters| Render
        ManualEng -->|Black Strokes on White| SketchGen
        SketchGen --> ThumbGen
        ThumbGen -->|Cover Teaser (15 frames)| Render
        Render --> Audio
        Audio --> SEO
        SEO --> Complete
        Complete -->|Status Polling & Video Stream| UI
    end
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
- `start_drawing_studio.bat`: One-click launcher for the Drawing Studio. Discovers host LAN IP, opens local browser to port 8000, and starts the server on `0.0.0.0:8000`.
- `upload_to_youtube.bat`: Automatically scans `outputs/` for the most recent metadata or `.mp4` file and initiates upload.
- `reset_youtube_account.bat`: Clears `youtube_token.pickle` to force re-authentication with a different Google account.

---

### 5.11 Interactive Drawing Studio Server (`web_app.py`)
- **Module Purpose:** Provides a LAN-accessible Flask REST API and job worker for interactive drawing, reference sketch upload, and background rendering.
- **Network Binding:** Binds to `0.0.0.0:<port>` (default 8000) for local and Wi-Fi access. Automatically resolves the primary LAN IPv4 address (e.g. `192.168.1.10`) via UDP socket probing and prints local and network access links.
- **Asynchronous GPU Job Worker:** Manages an in-memory job queue with a dedicated worker thread (`worker_thread`), ensuring only one GPU NVENC rendering job executes at any given time to protect VRAM.
- **REST Endpoints:**
  - `GET /` — Serves the interactive drawing studio HTML.
  - `GET /api/system-info` — Returns network address, port, and online status.
  - `POST /api/upload-reference` — Validates and stores reference images in `inputs/uploads/`. Extracts and returns precomputed `geometry` JSON payload (paths, tangents, scale, ROI) for immediate client-side spatial grid construction. **Strict Blueprint Validation:** Requires detectable black linework (`len(paths) > 0` and `len(skel_points) >= 8`). Rejects blank or unrecognizable images with HTTP 400 (`"No valid black linework or Kolam patterns detected on the blueprint. Please upload a clear sketch with dark lines."`).
  - `GET /api/uploads/<filename>` — Serves uploaded reference images safely.
  - `POST /api/generate` — Validates drawing strokes (including `live_aligned` flag) and enqueues video rendering.
  - `GET /api/jobs/<job_id>` — Returns real-time stage, progress percentage (0-100%), and artifact URLs.
  - `GET /api/jobs/<job_id>/video` — Streams rendered MP4 video.
  - `GET /api/jobs/<job_id>/thumbnail` — Streams generated YouTube Short thumbnail.
- **Dual-Mode Stroke Routing:**
  - If payload contains `live_aligned: true`, the worker invokes `refine_live_aligned_strokes` in `engine/reference_alignment.py` for conservative boundary clamping, loop gap closure, sub-stroke gap splitting, and gentle moving-average smoothing.
  - If `live_aligned: false` or omitted, it executes full `correct_stroke_sequence` (Viterbi deformation).


---

### 5.12 Manual Drawing Vector Synthesis (`engine/manual_drawing.py`)
- **Module Purpose:** Validates client-submitted vector stroke data, clamps coordinates to $0 \le x < 1080$ and $0 \le y < 1920$, and synthesizes renderer-compatible ordered paths.
- **Stroke Delimiter Translation:** Injects `None` pen-up signals between independent strokes so separate artistic strokes are never accidentally connected.
- **Gap Detection & Discontinuous Jump Splitting:** Checks Euclidean distance between successive stroke points. If $\Delta > 40\text{px}$, the engine automatically splits the path with a `None` pen-up delimiter so the renderer and NVENC hand animation never interpolate or draw across white gaps.
- **Dense Path Interpolation:** Steps along user segments (max step 4 px) so quick swipes and touches produce smooth, uninterrupted line trajectories for the hand sprite and NVENC encoder.
- **Sketch Image Synthesis (`render_strokes_to_sketch_image`):** Draws vector strokes as crisp black lines on a 1080x1920 white canvas (`temp_sketch.png`). Automatically skips drawing line segments across gaps $> 40\text{px}$. This temporary sketch is passed directly to `generate_kolam_thumbnail()` so the existing auspicious colorization and 3D powder depth engine can produce high-CTR thumbnails for manually drawn patterns.

---

### 5.13 Studio Frontend Interface (`web/`)
- **Module Purpose:** Fully responsive, touch-protected digital drawing canvas running seamlessly across desktop, tablet, and smartphone browsers.
- **Stack:** HTML5, CSS3, Vanilla ES6 JavaScript (zero external node/bundler dependencies).
- **Responsive Multi-Breakpoint Layout:**
  - **Desktop (>1080px):** 290px left sidebar dock, spacious controls, centered 9:16 vertical canvas.
  - **Laptops & Tablets in Landscape (769px - 1080px):** 250px left dock with compact padding, maximizing drawing canvas visibility.
  - **Tablets in Portrait & Smartphones (<=768px):** Transformed into a bottom horizontal scroll dock (`height: 86px`, `flex-wrap: nowrap`, `overflow-x: auto`) with a custom golden scrollbar. Leaves over 80% of vertical screen height exclusively for the drawing canvas instead of stacking rows vertically.
  - **Two-Tier Mobile Header:** Compact two-row header with logo and primary `Generate Video` action on top, and Channel Title and Dot Grid selector side-by-side on row two.
  - **Small Phones (<=480px):** Scaled badges and icons, optimized margins, and compact button sizing.
  - **Mobile Landscape Mode (`max-height: 520px` & `orientation: landscape`):** Shifts to an ultra-slim 180px left dock with 40px slim header to maximize canvas height on rotated devices.
- **Floating Canvas Quick Controls:**
  - Glassmorphism Undo (`↩️`) and Redo (`↪️`) buttons (`.floating-controls`, `.btn-float`) positioned directly on the top-left canvas viewport.
  - Allows one-tap thumb undo/redo on mobile and touch devices without needing to scroll the bottom toolbar dock to the history card.
  - Fully synchronized with keyboard shortcuts (`Ctrl+Z`, `Ctrl+Y`) and toolbar buttons.
- **Touch & Gesture Protections:**
  - Configured `overscroll-behavior: none; touch-action: manipulation;` on `html, body` and `touch-action: none;` on canvas layers.
  - Completely eliminates elastic bounce, pull-to-refresh collisions, and gesture interference during drawing sessions.
- **Dynamic Coordinate Transformation:**
  - Uses `getBoundingClientRect()` with dynamic scale factors (`scaleX = 1080 / rect.width`, `scaleY = 1920 / rect.height`) to map physical screen pixels to the 1080x1920 logical canvas coordinates with pixel-perfect precision regardless of device pixel ratio (DPR), viewport zoom, or screen size.
- **Strict Blueprint-Only Tracing Engine (`ReferenceSnapper`):**
  - **Non-Negotiable Constraint:** Tracing is strictly constrained to the extracted blueprint centerline geometry. Freehand drawing in white areas is completely prohibited.
  - **Strict Blocking on Pointer Down:** Clicking or touching in white space ($> 26\text{px}$ from the centerline) is blocked immediately (`accepted: false, blocked: true`), showing an unobtrusive toast notification: *"⚠️ Tracing restricted to blueprint lines. Click directly on a black line to start tracing."* No stroke is created.
  - **Departure & Pause Behavior:** If the pointer leaves the permitted line geometry (moves $> 26\text{px}$ away from centerline or steps $> 35\text{px}$), tracing pauses at the last valid centerline point. Raw pointer coordinates in white space are strictly rejected.
  - **Continuity & Gap Jump Prevention:** Moving across white gaps ($> 35\text{px}$ step) or jumping to disconnected/parallel lines ($> 14\text{px}$ perpendicular offset while path is active) is rejected. No bridging segments or straight connecting lines are ever fabricated.
  - **Resume Behavior:** Tracing resumes seamlessly only if the pointer returns to a valid continuation of the active path ($\le 35\text{px}$). If the user moves to a disconnected line, they must lift their pen/finger and start a new stroke directly on that line.
  - **Centerline Conformance & Intermediate Curve Extraction:** All recorded points lie exactly on the extracted 1px skeleton path. Rapid movements dynamically interpolate intermediate centerline points along the curve.
  - **Closed-Loop Endpoint Recovery:** When pen lifts within $20\text{px}$ of the stroke start point, the loop is closed cleanly to the first point.
  - **Blueprint Replacement & Invalidation:** Replacing or removing the blueprint immediately wipes all canvas strokes, invalidates the spatial index, and resets drawing state.
  - **Spatial Grid Index:** Reconstructs a $20\text{px}$ spatial hash grid (`cellSize = 20`, dense 4-6px point sampling) from preprocessed reference polylines and tangents, enabling sub-millisecond neighbor queries.
  - **Preserved Vector Hierarchy:** Stores exact centerline coordinates in `activeStroke.points` and raw pointer samples in `activeStroke.rawPoints`. Preserves stroke sequence, drawing direction, timing, and brush attributes.
  - **Explicit Backend Contract:** Sets `live_aligned: true` in the generation payload. The backend detects this and applies conservative residual refinement (`refine_live_aligned_strokes`) instead of duplicate aggressive Viterbi re-warping.

---

### 5.14 Reference-Guided Stroke Alignment Engine (`engine/reference_alignment.py`)
- **Module Purpose:** Corrects human drawing inaccuracies using uploaded reference Kolam/Rangoli sketches without altering the human's stroke order, direction, or style.
- **Fundamental Principle:** Human tracing determines *WHAT* to draw and the *ORDER* to draw it; the reference image determines *WHERE* the corrected strokes should go.
- **Core Algorithms:**
  1. **Aspect-Ratio Canvas Fitting:** Scales and centers arbitrary-sized reference images into the logical $1080 \times 1920$ canvas using CSS `object-fit: contain` geometry so that pixel coordinates match the drawing canvas identically.
  2. **Multi-Cue Line Extraction:** Combines CLAHE contrast enhancement, adaptive thresholding, Otsu binarization, and Canny edge gradients to extract lines from black-and-white sketches, colored Rangolis, and photos with dark or light backgrounds.
  3. **Golay Morphological Thinning & Topology Decomposition:** Extracts an exact 1-pixel-wide skeleton using morphological hit-or-miss operations, segments non-branching simple curves (`ReferencePath`), and builds a spatial `cKDTree`.
  4. **Orientation Field Estimation:** Computes continuous line orientation angles $\theta \in [0, \pi)$ via the structure tensor ($J_{xx}, J_{yy}, J_{xy}$).
  5. **Dual-Tier Geometric Correction:**
     - **Tier 1 (High Confidence):** Maps strokes to corresponding reference subsegments, preserving endpoints and drawing direction.
     - **Tier 2 (Multi-Branch / Crossing):** Employs Viterbi dynamic programming map-matching across skeleton points with orientation and step penalties to navigate complex intersections without switching lines.
     - **Tier 3 (Low Confidence / Freehand):** Preserves original human strokes without unjustified warping.
  6. **Geometry Serialization for Client-Side Snapping (`serialize_reference_geometry`):**
     - Extracts reference skeleton polylines, unit tangents $(t_x, t_y)$, canvas ROI offsets, and scaling ratios into an ultra-compact JSON object (< 50 KB).
     - Bundled directly in `POST /api/upload-reference` responses to hydrate the frontend spatial grid index.
  7. **Residual Refinement for Live-Snapped Strokes (`refine_live_aligned_strokes`):**
     - When `live_aligned: true` is received, avoids re-running heavy Viterbi deformation.
     - **Sub-Stroke Gap Splitting:** If distance between consecutive points in a stroke exceeds $35\text{px}$, the stroke is automatically split into independent sub-strokes, guaranteeing no straight lines across gaps.
     - Applies conservative residual polish: strict coordinate clamping ($[0, 1079] \times [0, 1919]$), closed-loop endpoint recovery ($\le 20\text{px}$), and subtle moving-average smoothing ($w=3$).
  8. **Thumbnail & Video Flow:** Outputs corrected vector strokes to `render_strokes_to_sketch_image` and `strokes_to_renderer_path` so both the thumbnail and progressive video reflect the corrected art while keeping the reference image off the final video canvas.

---

### 5.15 Automation & Server Control Scripts (`start.bat` & `stop.bat`)
- **`start.bat` Production Server Launcher:**
  - **Syntax:** `start.bat [port] [--no-browser | /nobrowser | -n] [--foreground | /foreground | -f]` (default port: `8000`).
  - Performs pre-flight validation on Python 3.10 and PATH availability.
  - Inspects target port via `netstat -aon` to detect active server instances and prevent duplicate binding collisions.
  - Dynamically discovers the host machine's primary LAN IPv4 address via non-blocking UDP probe (`socket.connect(('8.8.8.8', 80))`).
  - Displays formatted Localhost and Wi-Fi LAN access URLs with clear instructions and Windows Defender Firewall commands for phone/tablet connectivity.
  - **Foreground Mode (`--foreground` / `-f`):** Executes `python web_app.py` directly inside the current terminal window with standard Ctrl+C interrupt handling.
  - **Background Mode (Default):** Spawns `python web_app.py --host 0.0.0.0 --port <PORT>` in a dedicated console window titled `"Kolam Studio Server (Port <PORT>)"` with working directory set via `/D "%~dp0"`.
  - Records the active process ID into `server.pid` for clean shutdown.
  - Automatically launches the default web browser to `http://localhost:<PORT>` (suppressible via `--no-browser`).
- **`stop.bat` Production Server Terminator:**
  - **Syntax:** `stop.bat [port]` (default port: `8000`).
  - Reads `server.pid` and executes `taskkill /f /t /pid <PID>` to recursively terminate the Python server and its entire process tree.
  - Sweeps the target port with `netstat -aon` to terminate any lingering listeners and removes `server.pid`.
  - Automatically closes any orphaned dedicated console windows via `taskkill /f /fi "WINDOWTITLE eq Kolam Studio Server*"`.
- **Batch Script Robustness:**
  - Formatted in pure 7-bit ASCII with strict Windows CRLF line endings (`\r\n`) to prevent CMD seek-pointer offset misalignments.


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

### 6.3 Structured Vector Stroke Schema (JSON)
The payload submitted by the Drawing Studio to `/api/generate` matches this schema:
```json
{
  "canvas": {
    "width": 1080,
    "height": 1920
  },
  "title": "AK Kolam",
  "dot_grid": "none",
  "reference_image": "inputs/uploads/abc123_sketch.jpg",
  "ref_correction": true,
  "live_aligned": true,
  "strokes": [
    {
      "id": "stroke_1729068000_abcde",
      "color": "#FFFFFF",
      "width": 6,
      "points": [
        {"x": 540, "y": 480, "t": 0},
        {"x": 542, "y": 486, "t": 45},
        {"x": 548, "y": 495, "t": 90}
      ]
    }
  ]
}
```
- `canvas.width` / `canvas.height`: Fixed logical resolution (1080x1920).
- `dot_grid`: `"none"`, `"8x2"`, or `"6x2"`.
- `reference_image`: Optional filename of uploaded reference guide stored in `inputs/uploads/`.
- `ref_correction`: Optional boolean (`true` by default when reference image is present); triggers `reference_alignment.py`.
- `live_aligned`: Optional boolean (`true` when client-side `ReferenceSnapper` already aligned points in real time; instructs backend to run `refine_live_aligned_strokes` residual refinement instead of full Viterbi deformation).
- `strokes[].points`: Ordered array of `{x, y, t}` where `x` and `y` are integers ($0 \le x < 1080$, $0 \le y < 1920$) and `t` is elapsed time in milliseconds.


---

## 7. Operational Guidelines for Future AI Agents

When interacting with or extending this codebase, all AI agents **must strictly adhere** to these rules:

1. **Preserve Headless Execution:**
   - **Never** add blocking GUI dialogs (e.g., `cv2.imshow()`, `plt.show()`, or Tkinter windows) to core pipelines.
   - All status, progress, and warnings must be routed through `print()` or standard logging.

2. **Console Encoding Safety:**
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

7. **Preserve Generated Video UI:**
   - Do not redesign or alter the existing generated video UI, badges, branding, or wood background. The Interactive Drawing Studio is an isolated workflow and must not alter the appearance of final rendered videos.

---

## 8. Troubleshooting & Common Pitfalls

| Symptom | Root Cause | AI Agent Remediation |
| :--- | :--- | :--- |
| `UnicodeEncodeError: 'charmap' codec can't encode characters` | Windows default console (`cp1252`) attempted to print Tamil Unicode characters | Check that `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` executed before printing. |
| Hand sprite flickers or jumps erratically | Path contains consecutive `None` values or invalid coordinate jumps | Ensure path interpolation cleans adjacent `None` values and maintains continuous trajectories. |
| Thumbnail custom upload fails with HTTP 403 | YouTube channel is not phone-verified for custom thumbnails | Normal YouTube policy for new accounts. Video still publishes successfully; thumbnail is already baked into opening video frames as a teaser. |
| Rendering is unusually slow (< 5 FPS) | FFmpeg failed to initialize NVENC and fell back to CPU `cv2.VideoWriter` | Run `nvidia-smi` to ensure GPU is accessible; check that FFmpeg in PATH supports `h264_nvenc`. |
| Audio track is trimmed or video ends abruptly | `-shortest` flag passed to FFmpeg | Ensure `-stream_loop -1` is used for audio and `-t <duration>` is set strictly to the video length. |
| Phone / tablet cannot reach Studio URL on LAN | Windows Defender Firewall blocking port 8000 on private profile | Run `New-NetFirewallRule -DisplayName "Kolam Studio Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private`. |

---

## 9. Verification & Quick Test Commands

To verify the entire environment and pipeline functionality, an AI agent can execute:

```powershell
# 1. Verify Python & GPU Encoder
python -c "import cv2, torch; print('OpenCV:', cv2.__version__, '| CUDA Available:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0))"

# 2. Test FFmpeg NVENC Availability
ffmpeg -f lavfi -i testsrc=size=1080x1920:rate=25 -vcodec h264_nvenc -t 1 -f null -

# 3. Run Reference-Guided Stroke Alignment Tests
python -m unittest tests/test_reference_alignment.py

# 4. Run End-to-End Alignment GPU NVENC Video Rendering Test
python -m unittest tests/test_end_to_end_alignment_render.py

# 5. Run Live Reference Snapping Backend Tests
python -m unittest tests/test_live_snapping.py

# 6. Run Browser Real-Time Reference Snapping Tests (Node.js Test Suite)
node tests/test_browser_snapping.js

# 7. Run the Entire Automated Test Suite (30 Unit & Regression Tests)
python -m unittest discover tests

# 8. Run a Fast End-to-End Test Video Generation (CLI Workflow)
python generate.py --input "inputs/77d590840016a86bc06d5770114539a4-sketch (1).jpg" --type mandala --no-upload

# 9. Start the Production Interactive Drawing Studio (Auto LAN Discovery & Browser Open)
cmd /c start.bat
# Or run on custom port without opening browser: cmd /c "start.bat 8080 --no-browser"
# Or run in foreground inside current terminal: cmd /c "start.bat --foreground --no-browser"

# 10. Stop the Drawing Studio Server Cleanly (Recursive Process Tree & Port Release)
cmd /c stop.bat
# Or stop a custom port instance: cmd /c "stop.bat 8080"
```

