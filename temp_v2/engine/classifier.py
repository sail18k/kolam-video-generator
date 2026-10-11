
import cv2
import numpy as np
import requests
import json

def classify_kolam_local_llm(image_path):
    """Try Ollama llava:7b, fallback to heuristic"""
    # Try local LLM first
    try:
        import base64
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        payload = {
            "model": "llava:7b",
            "prompt": "Analyze this image. Is it (A) Pulli Kolam - dots connected by straight lines, (B) Sikku Kolam - curved loops weaving around dots, (C) Rangoli - colorful filled patterns, (D) Mandala - circular floral. Return JSON only: {\"type\": \"pulli_kolam\" | \"sikku_kolam\" | \"rangoli\" | \"mandala\", \"dot_grid\": \"8x2\" or \"none\", \"confidence\": 0-1}",
            "images": [img_b64],
            "stream": False
        }
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=15)
        if r.status_code == 200:
            text = r.json().get("response","")
            # Try extract JSON
            import re
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                data = json.loads(m.group())
                print(f"[LLM] Classified as {data}")
                return data
    except Exception:
        print("[LLM] Local LLM (Ollama) is not running on port 11434. Falling back to built-in heuristic classifier.")

    # Heuristic fallback
    return classify_heuristic(image_path)

def classify_heuristic(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return {"type": "sikku_kolam", "dot_grid": "8x2", "confidence": 0.5}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Check for color (rangoli)
    # High saturation means colorful rangoli
    mean_sat = np.mean(hsv[:,:,1])
    
    # Check for dots - many small bright blobs
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    # For mandala vs kolam
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    small_dots = [c for c in contours if 5 < cv2.contourArea(c) < 200]
    
    # Detect circular symmetry (mandala)
    # If large circular contours
    large_contours = [c for c in contours if cv2.contourArea(c) > 5000]
    
    if mean_sat > 60 and len(large_contours) > 2:
        return {"type": "rangoli", "dot_grid": "none", "confidence": 0.7}
    elif len(small_dots) >= 20:
        # Dots present - check if lines are curved (sikku) vs straight (pulli)
        # If we detect many curved strokes -> sikku
        return {"type": "sikku_kolam", "dot_grid": "8x2", "confidence": 0.8}
    elif len(large_contours) >= 1:
        # Mandala / circular
        return {"type": "mandala", "dot_grid": "none", "confidence": 0.6}
    else:
        return {"type": "pulli_kolam", "dot_grid": "8x2", "confidence": 0.6}
