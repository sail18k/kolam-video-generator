
# Headless Kolam Generator V2 - YouTube Shorts Ready

> 🤖 **AI Agents & Automated Tools:** For complete architecture, hardware specs, module breakdowns, and operational protocols, please read [AI_SYSTEM_DOC.md](file:///d:/kolam%20video%20generation%20v2/AI_SYSTEM_DOC.md).

Dynamic based on input: rangoli / pulli kolam / sikku kolam

Exactly replicates reference video: wood background, white dots, pink Suri Rangoli pen hand.

## Headless CLI

```bash
# Install
pip install -r requirements.txt
# Optional local LLM
ollama pull llava:7b
ollama serve

# Run - auto detect type
python generate.py --input inputs/mandala_sketch.jpg --output outputs/shorts.mp4

# Force type
python generate.py --input inputs/mandala_sketch.jpg --output outputs/sikku_shorts.mp4 --type sikku_kolam --grid 8x2

# Without hand (just lines)
python generate.py --input inputs/mandala_sketch.jpg --output outputs/no_hand.mp4 --no-hand
```

## Output
- 1080x1920 vertical
- 25fps (YouTube Shorts compatible)
- 40 sec duration (under 60s limit)
- H.264 mp4v, ready to upload

## For Google Antigravity Agent Mode

Paste this prompt:

```
Build a headless CLI app at /mnt/data/kolam_headless that:
1. Takes --input sketch image
2. Uses local LLM Ollama llava:7b to classify as rangoli/pulli_kolam/sikku_kolam/mandala (fallback heuristic)
3. Generates dot grid 8x2 (40 dots) like reference video 1080x1920
4. Generates continuous sikku path that weaves around dots, exactly like reference
5. Renders video with wood background, white dots, white line, and hand overlay (pink Suri Rangoli pen)
6. Headless, no Gradio, outputs YouTube Shorts ready 1080x1920 25fps mp4

Use existing assets in engine/assets/. Code is in engine/ folder. Make generate.py CLI work.
```

## Types

- pulli_kolam: straight lines connecting dots
- sikku_kolam: curved loops around dots (reference video)
- rangoli: colorful circular patterns
- mandala: traces input sketch contours

"# kolam-video-generator" 
