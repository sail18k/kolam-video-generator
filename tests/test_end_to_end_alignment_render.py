"""
End-to-end integration test for reference-guided stroke correction rendering pipeline.
Tests full flow: Reference image + Wobbly strokes -> Correction -> Sketch -> Thumbnail -> NVENC Video.
"""

import os
import time
import unittest
import numpy as np
import cv2
from pathlib import Path

from engine.reference_alignment import (
    preprocess_reference_image,
    correct_stroke_sequence,
    render_corrected_sketch
)
from engine.manual_drawing import strokes_to_renderer_path
from engine.renderer import render_kolam_video
from engine.thumbnail_generator import generate_kolam_thumbnail


class TestEndToEndAlignmentRender(unittest.TestCase):

    def test_e2e_reference_corrected_video_render(self):
        """End-to-end test verifying that corrected paths produce a valid video with all branding and assets."""
        root_dir = Path(__file__).parent.parent.resolve()
        outputs_dir = root_dir / "outputs"
        uploads_dir = root_dir / "inputs" / "uploads"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # 1. Create a synthetic Kolam reference image (circular flower/mandala motif)
        ref_img = np.full((1920, 1080, 3), 255, dtype=np.uint8)
        center = (540, 960)
        radius = 220
        cv2.circle(ref_img, center, radius, (0, 0, 0), 6)
        cv2.line(ref_img, (300, 960), (780, 960), (0, 0, 0), 6)

        test_ref_name = f"test_e2e_ref_{int(time.time())}.png"
        test_ref_path = str(uploads_dir / test_ref_name)
        cv2.imwrite(test_ref_path, ref_img)

        # 2. Create wobbly human strokes
        # Stroke 1: wobbly horizontal line
        hx1 = np.linspace(310, 770, 40)
        hy1 = 960.0 + 8.0 * np.sin(np.linspace(0, 12, 40))
        s1_pts = [{"x": int(round(x)), "y": int(round(y)), "t": i * 15.0} for i, (x, y) in enumerate(zip(hx1, hy1))]

        # Stroke 2: wobbly top half circle
        angles = np.linspace(np.pi, 2 * np.pi, 50)
        wobble = 10.0 * np.sin(angles * 6.0)
        hx2 = center[0] + (radius + wobble) * np.cos(angles)
        hy2 = center[1] + (radius + wobble) * np.sin(angles)
        s2_pts = [{"x": int(round(x)), "y": int(round(y)), "t": 600.0 + i * 15.0} for i, (x, y) in enumerate(zip(hx2, hy2))]

        strokes = [
            {"id": "stroke_line", "color_bgr": (255, 255, 255), "width": 6, "points": s1_pts},
            {"id": "stroke_arc", "color_bgr": (0, 215, 255), "width": 6, "points": s2_pts}
        ]

        # 3. Preprocess & Align
        ref_geom = preprocess_reference_image(test_ref_path)
        corr_strokes, diag = correct_stroke_sequence(strokes, ref_geom)

        self.assertEqual(len(corr_strokes), 2)
        self.assertEqual(diag["corrected_count"], 2)

        # 4. Generate paths and temporary sketch
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        test_video_path = str(outputs_dir / f"test_e2e_{timestamp}.mp4")
        test_thumb_path = str(outputs_dir / f"test_e2e_{timestamp}_thumbnail.jpg")
        test_sketch_path = str(outputs_dir / f"test_e2e_{timestamp}_sketch.png")

        path, point_colors, point_widths = strokes_to_renderer_path(corr_strokes)
        self.assertIn(None, path)  # Pen-up delimiter between strokes preserved

        render_corrected_sketch(corr_strokes, test_sketch_path)
        self.assertTrue(os.path.exists(test_sketch_path))

        # 5. Generate thumbnail from corrected sketch
        wood_path = str(root_dir / "engine" / "assets" / "wood.jpg")
        hand_path = str(root_dir / "engine" / "assets" / "hand_raw.png")

        thumb_res = generate_kolam_thumbnail(
            input_image_path=test_sketch_path,
            output_thumbnail_path=test_thumb_path,
            kolam_type="rangoli",
            grid="none",
            wood_path=wood_path,
            dots=[],
            title="AK Kolam"
        )
        self.assertTrue(os.path.exists(test_thumb_path))
        self.assertGreater(os.path.getsize(test_thumb_path), 5000)

        # 6. Render video with existing renderer (short 25 fps run)
        # Use a subset of points for fast test execution
        render_path = path[::2]  # Subsample to keep test under a few seconds
        # Keep None delimiters intact
        for idx in range(len(path)):
            if path[idx] is None and idx // 2 < len(render_path):
                render_path[idx // 2] = None

        render_kolam_video(
            dots=[],
            path=render_path,
            wood_path=wood_path,
            hand_path=hand_path,
            output_path=test_video_path,
            fps=25,
            line_thickness=6,
            show_watermark=True,
            title="AK Kolam",
            cover_image_path=test_thumb_path,
            point_colors=point_colors[::2] if point_colors else None,
            point_widths=point_widths[::2] if point_widths else None
        )

        self.assertTrue(os.path.exists(test_video_path))
        self.assertGreater(os.path.getsize(test_video_path), 50000)

        # Verify video frames with OpenCV
        cap = cv2.VideoCapture(test_video_path)
        self.assertTrue(cap.isOpened())
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        self.assertGreater(frame_count, 15)
        self.assertEqual(w, 1080)
        self.assertEqual(h, 1920)

        # Clean up temporary test files
        for f in [test_ref_path, test_sketch_path, test_thumb_path, test_video_path]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
