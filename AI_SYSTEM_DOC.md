# Kolam Video Generation V2 - AI System Context

This document is designed for AI agents (like GitHub Copilot, Gemini, Claude, or other coding assistants) to quickly understand the project architecture, tech stack, and workflows for "Headless Kolam Video Generator".

## 1. Project Overview
This project is a headless CLI application that generates YouTube Shorts-ready videos (1080x1920, 25fps, under 60 seconds) illustrating the drawing of Kolam/Rangoli art. 
It takes a rough input sketch (image) and outputs a progressively drawn video over a wooden background, featuring an overlaid hand holding a pen. 
It dynamically classifies the input sketch to determine the Kolam type and dot grid, generates the drawing path, and renders the final video.

## 2. Directory Structure
```text
D:\kolam video generation v2\
├── generate.py                # Main CLI entry point
├── requirements.txt           # Python dependencies
├── README.md                  # Human-readable instructions and examples
├── engine/                    # Core logic modules
│   ├── classifier.py          # Vision-based classification (LLM + OpenCV heuristics)
│   ├── dot_generator.py       # Generation of the dot grid background
│   ├── path_generator.py      # Calculates the drawing path for the kolam
│   └── renderer.py            # Video rendering engine (OpenCV / FFmpeg)
├── engine/assets/             # Static assets
│   ├── hand_raw.png           # Image of a hand holding a pen
│   └── wood.jpg               # Wood texture background
├── inputs/                    # Directory for input sketch images
└── outputs/                   # Directory for generated videos
```

## 3. Key Modules & AI Guidelines

### 3.1 CLI Entry Point (`generate.py`)
- **Role**: Parses arguments (input, output, type, grid, fps, no-hand) and orchestrates the pipeline.
- **Workflow**: 
  1. Classify image.
  2. Generate dots.
  3. Generate path.
  4. Render video.
- **AI Modification Tip**: If adding new CLI flags or steps in the pipeline, update `generate.py` first and pass the arguments down to the `engine` modules.

### 3.2 Classification (`engine/classifier.py`)
- **Role**: Determines the type of Kolam (`pulli_kolam`, `sikku_kolam`, `rangoli`, `mandala`) and the dot grid size (e.g., `8x2`, `none`).
- **Logic**: 
  - **Primary**: Uses a local LLM via Ollama (`llava:7b` on port 11434).
  - **Fallback**: Uses OpenCV heuristics (color saturation, contour size, and density of dots).
- **AI Modification Tip**: When modifying heuristics, adjust the HSV/Contour thresholds. When tweaking the prompt for LLaVA, ensure the requested JSON format remains strictly parsable.

### 3.3 Dot & Path Generation (`engine/dot_generator.py` & `engine/path_generator.py`)
- **Role**: `dot_generator.py` generates the background dot grid coordinates. `path_generator.py` calculates the sequential 2D coordinates for the drawing stroke.
- **AI Modification Tip**: If introducing a new pattern type, add the logic in `path_generator.py` and ensure the output is a continuous list of `(x, y)` tuples.

### 3.4 Video Rendering (`engine/renderer.py`)
- **Role**: Renders the video frame-by-frame. Overlays the drawing path, background, and the hand sprite.
- **Logic**:
  - Automatically handles transparency and hand positioning via `overlay_hand`.
  - Attempts to use `ffmpeg` with GPU acceleration (`h264_nvenc`) via `subprocess` for faster rendering.
  - Falls back to `cv2.VideoWriter` if `ffmpeg` fails.
- **AI Modification Tip**: Rendering is the most performance-sensitive part. If modifying the drawing speed, adjust `target_frames` and `points_per_frame`.

## 4. Execution Environment & Dependencies
- **Language**: Python 3.x
- **Core Dependencies**: `opencv-python` (cv2), `numpy`, `requests`
- **External Tools**: 
  - `ffmpeg` (expected in PATH for fast rendering)
  - `ollama` (optional, for LLM-based vision classification)
- **Standard Command**: `python generate.py --input inputs/sketch.jpg`

## 5. System Prompts & Behaviors (For AI Agents)
- **Do not break the Headless nature**: The CLI must remain fully headless without requiring GUI interactions (e.g., no `cv2.imshow` or Gradio blocks).
- **Paths**: Always use relative paths resolving from the root directory or `engine/` to avoid `FileNotFoundError`.
- **Performance**: When generating paths with many points, ensure the renderer batches line drawing correctly to maintain video duration constraints (Shorts < 60s).
