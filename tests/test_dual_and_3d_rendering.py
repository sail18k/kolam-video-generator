"""
Test Suite for Dual-Video 2D/3D Rendering, Timeline Parity, and ComfyUI Fallback
Headless Kolam Video Generator V2/V3
"""

import os
import sys
import tempfile
import unittest
import numpy as np
import cv2
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engine.manual_drawing import (
    validate_and_normalize_drawing_payload,
    strokes_to_renderer_path,
    _trim_closed_loop_overshoot,
    _StrokeCoverageIndex,
)
from engine.renderer import render_kolam_video
from engine.renderer_3d import render_kolam_video_3d, _compute_height_field, _compute_normals, _apply_lighting
from engine.comfyui_bridge import discover_comfyui, get_enhancement_report, ComfyUIStatus
from engine.audio_processor import get_video_duration


class TestDualAnd3DRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.outputs_dir = Path(cls.temp_dir.name)
        cls.wood_path = str(ROOT_DIR / "engine" / "assets" / "wood.jpg")
        cls.hand_path = str(ROOT_DIR / "engine" / "assets" / "hand_raw.png")

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Closed-Loop Overshoot Trimming
    # -------------------------------------------------------------------------
    def test_loop_overshoot_trimming(self):
        # Create a circle that closes back to (500, 500) and overshoots by 4 points
        center = (500, 500)
        radius = 80.0
        loop_points = []
        # Full circle 16 points
        for i in range(16):
            theta = 2.0 * np.pi * i / 16.0
            x = int(round(center[0] + radius * np.cos(theta)))
            y = int(round(center[1] + radius * np.sin(theta)))
            loop_points.append({"x": x, "y": y, "t": i * 50})

        # Add closure point back to start
        loop_points.append({"x": loop_points[0]["x"], "y": loop_points[0]["y"], "t": 16 * 50})

        # Add 4 overshoot points retracing the start
        for i in range(1, 5):
            loop_points.append({"x": loop_points[i]["x"], "y": loop_points[i]["y"], "t": (16 + i) * 50})

        self.assertEqual(len(loop_points), 21)
        trimmed = _trim_closed_loop_overshoot(loop_points, tolerance=10.0)
        # Should be trimmed back to 17 points (first 16 + closure to start)
        self.assertEqual(len(trimmed), 17, "Overshoot tail retracing start of loop must be trimmed")
        self.assertEqual((trimmed[-1]["x"], trimmed[-1]["y"]), (trimmed[0]["x"], trimmed[0]["y"]))

    # -------------------------------------------------------------------------
    # 2. Coverage Index Tremor Deduplication
    # -------------------------------------------------------------------------
    def test_stroke_coverage_tremor_deduplication(self):
        index = _StrokeCoverageIndex(tolerance=3.0)
        pts1 = [{"x": 100, "y": y, "t": y} for y in range(200, 300, 10)]
        index.add(pts1)

        # Second stroke with 2px natural hand tremor in the same direction
        pts2 = [{"x": 102, "y": y, "t": y + 500} for y in range(200, 300, 10)]
        from engine.manual_drawing import _uncovered_runs
        runs, ratio = _uncovered_runs(pts2, index)
        self.assertGreaterEqual(ratio, 0.85, "Natural tremor overlapping stroke must be detected as duplicate")
        self.assertEqual(len(runs), 0, "Duplicate stroke should have 0 runs accepted")

    # -------------------------------------------------------------------------
    # 3. Clean None Delimiters (No Consecutive or Trailing Nones)
    # -------------------------------------------------------------------------
    def test_clean_delimiters(self):
        strokes = [
            {"points": [{"x": 100, "y": 100}, {"x": 200, "y": 200}], "color_bgr": (255, 255, 255), "width": 6},
            {"points": [{"x": 300, "y": 300}, {"x": 400, "y": 400}], "color_bgr": (255, 255, 255), "width": 6},
        ]
        path, _, _ = strokes_to_renderer_path(strokes)
        # Count consecutive Nones
        has_consecutive_nones = any(path[i] is None and path[i+1] is None for i in range(len(path)-1))
        self.assertFalse(has_consecutive_nones, "Path must not contain consecutive None delimiters")
        self.assertIsNotNone(path[0], "Path must not start with None")
        self.assertIsNotNone(path[-1], "Path must not end with None")

    # -------------------------------------------------------------------------
    # 4. 2D vs 3D Frame Count and Duration Parity
    # -------------------------------------------------------------------------
    def test_2d_and_3d_frame_parity(self):
        dots = [(540, 960)]
        # Two simple strokes with a gap
        path = [(400, 800), (500, 800), (600, 800), None, (400, 900), (500, 900), (600, 900)]
        out_2d = str(self.outputs_dir / "test_parity_2d.mp4")
        out_3d = str(self.outputs_dir / "test_parity_3d.mp4")

        render_kolam_video(
            dots=dots,
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_2d,
            fps=25,
            show_watermark=False,
            title="AK Kolam",
            drawing_speed=1.5
        )

        render_kolam_video_3d(
            dots=dots,
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_3d,
            fps=25,
            show_watermark=False,
            title="AK Kolam",
            drawing_speed=1.5
        )

        cap_2d = cv2.VideoCapture(out_2d)
        frames_2d = int(cap_2d.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_2d = cap_2d.get(cv2.CAP_PROP_FPS)
        cap_2d.release()

        cap_3d = cv2.VideoCapture(out_3d)
        frames_3d = int(cap_3d.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_3d = cap_3d.get(cv2.CAP_PROP_FPS)
        cap_3d.release()

        self.assertEqual(fps_2d, 25.0)
        self.assertEqual(fps_3d, 25.0)
        self.assertEqual(frames_2d, frames_3d,
                         f"2D and 3D videos must have identical frame counts: 2D={frames_2d}, 3D={frames_3d}")

    # -------------------------------------------------------------------------
    # 5. 3D Raised Powder Height-Field & Normal Map Generation
    # -------------------------------------------------------------------------
    def test_3d_height_field_and_lighting(self):
        mask = np.zeros((1920, 1080), dtype=np.uint8)
        cv2.line(mask, (500, 900), (600, 900), 255, 8)

        hf = _compute_height_field(mask, bevel_radius=8.0, max_height=5.0)
        self.assertEqual(hf.shape, (1920, 1080))
        # Center of stroke should be raised
        self.assertGreater(hf[900, 550], 2.0, "Center of powder line must have positive height")
        # Far outside should have 0 height
        self.assertEqual(hf[100, 100], 0.0, "Background should have zero height")

        normals = _compute_normals(hf)
        self.assertEqual(normals.shape, (1920, 1080, 3))
        # Normals must have unit length
        lengths = np.linalg.norm(normals[900, 550])
        self.assertAlmostEqual(lengths, 1.0, places=4, msg="Surface normals must be unit vectors")

    # -------------------------------------------------------------------------
    # 6. ComfyUI Discovery and Graceful Fallback
    # -------------------------------------------------------------------------
    def test_comfyui_discovery_and_fallback(self):
        status = discover_comfyui()
        self.assertIsInstance(status, ComfyUIStatus)
        report = get_enhancement_report(status)
        self.assertIn("enhancement_mode", report)
        if not status.usable:
            self.assertEqual(report["enhancement_mode"], "deterministic_local")
            self.assertIsNotNone(report["fallback_reason"])
        else:
            self.assertEqual(report["enhancement_mode"], "comfyui")

    # -------------------------------------------------------------------------
    # 7. No Zero-Length Segments Cause Duplicate-Frame Freezes
    # -------------------------------------------------------------------------
    def test_zero_length_segments_filtered(self):
        payload = {
            "strokes": [
                {
                    "id": "s_zero",
                    "points": [
                        {"x": 200, "y": 200, "t": 100},
                        {"x": 200, "y": 200, "t": 110},  # Duplicate point
                        {"x": 200, "y": 200, "t": 120},  # Duplicate point
                        {"x": 250, "y": 250, "t": 200},
                    ],
                    "color": "#ffffff",
                    "width": 6
                }
            ]
        }
        normalized = validate_and_normalize_drawing_payload(payload)
        self.assertEqual(len(normalized["strokes"][0]["points"]), 2,
                         "Consecutive identical points must be collapsed to 1")


if __name__ == "__main__":
    unittest.main()
