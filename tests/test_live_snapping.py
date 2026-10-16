"""
Unit & Integration Tests for Live Reference Snapping and Backend Refinement
Headless Kolam Video Generator V2
"""

import os
import unittest
import numpy as np
import cv2
from pathlib import Path
from io import BytesIO

from engine.reference_alignment import (
    preprocess_reference_image,
    serialize_reference_geometry,
    refine_live_aligned_strokes,
    CorrectionConfig,
)
from engine.manual_drawing import validate_and_normalize_drawing_payload
from web_app import app, UPLOADS_DIR, jobs, jobs_lock


class TestLiveSnappingBackend(unittest.TestCase):
    """Verifies backend serialization, residual refinement, and API handling for live snapping."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(__file__).parent / "test_data"
        cls.test_dir.mkdir(exist_ok=True)

        # Create a synthetic reference image: white background with black circle and cross
        cls.ref_img_path = cls.test_dir / "test_live_ref.png"
        img = np.full((1200, 800, 3), 255, dtype=np.uint8)
        # Draw clean black circle and cross
        cv2.circle(img, (400, 600), 250, (0, 0, 0), 4)
        cv2.line(img, (400, 300), (400, 900), (0, 0, 0), 4)
        cv2.line(img, (100, 600), (700, 600), (0, 0, 0), 4)
        cv2.imwrite(str(cls.ref_img_path), img)

    def test_serialize_reference_geometry(self):
        """Verifies reference geometry is serialized to lightweight JSON structure with tangents."""
        ref_geom = preprocess_reference_image(str(self.ref_img_path))
        data = serialize_reference_geometry(ref_geom)

        self.assertIn("paths", data)
        self.assertIn("roi", data)
        self.assertIn("scale", data)
        self.assertGreater(len(data["paths"]), 0)

        # Check path structure
        p0 = data["paths"][0]
        self.assertIn("id", p0)
        self.assertIn("points", p0)
        self.assertIn("tangents", p0)
        self.assertEqual(len(p0["points"]), len(p0["tangents"]))
        self.assertIsInstance(p0["points"][0][0], float)

    def test_refine_live_aligned_strokes(self):
        """Verifies conservative residual refinement on live-aligned strokes."""
        # Simulated live-aligned stroke with slightly unclosed endpoints
        stroke = {
            "id": "stroke_live_1",
            "color_bgr": (255, 255, 255),
            "width": 6,
            "points": [
                {"x": 540, "y": 480, "t": 0.0},
                {"x": 600, "y": 480, "t": 30.0},
                {"x": 650, "y": 530, "t": 60.0},
                {"x": 650, "y": 600, "t": 90.0},
                {"x": 600, "y": 650, "t": 120.0},
                {"x": 540, "y": 650, "t": 150.0},
                {"x": 548, "y": 486, "t": 180.0}, # gap = 10px from (540, 480)
            ]
        }

        refined, diag = refine_live_aligned_strokes([stroke])
        self.assertEqual(len(refined), 1)
        self.assertEqual(diag["refined_count"], 1)

        ref_pts = refined[0]["points"]
        # Closed loop should be cleanly bridged
        self.assertEqual(ref_pts[-1]["x"], ref_pts[0]["x"])
        self.assertEqual(ref_pts[-1]["y"], ref_pts[0]["y"])

    def test_validate_and_normalize_live_aligned(self):
        """Verifies that validate_and_normalize_drawing_payload passes live_aligned flag."""
        payload = {
            "title": "Live Snapped Test",
            "strokes": [
                {
                    "color": "#FFFFFF",
                    "width": 6,
                    "points": [{"x": 100, "y": 200, "t": 0}, {"x": 110, "y": 200, "t": 20}]
                }
            ],
            "live_aligned": True
        }
        normalized = validate_and_normalize_drawing_payload(payload)
        self.assertTrue(normalized.get("live_aligned"))

    def test_upload_reference_returns_geometry(self):
        """Verifies that POST /api/upload-reference returns precomputed geometry."""
        client = app.test_client()
        with open(self.ref_img_path, "rb") as f:
            img_bytes = f.read()

        data = {
            "reference_image": (BytesIO(img_bytes), "test_live_ref.png")
        }
        res = client.post("/api/upload-reference", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        res_json = res.get_json()
        self.assertTrue(res_json["success"])
        self.assertIn("geometry", res_json)

    def test_refine_live_aligned_strokes_gap_splitting(self):
        """Verifies that strokes with an internal gap > 35px are split into independent strokes."""
        stroke_with_gap = {
            "id": "stroke_gap_1",
            "color_bgr": (255, 255, 255),
            "width": 6,
            "points": [
                {"x": 100, "y": 200, "t": 0.0},
                {"x": 120, "y": 200, "t": 30.0},
                {"x": 140, "y": 200, "t": 60.0},
                # Sudden jump / gap of 110px!
                {"x": 250, "y": 200, "t": 90.0},
                {"x": 270, "y": 200, "t": 120.0},
            ]
        }
        refined, diag = refine_live_aligned_strokes([stroke_with_gap])
        # Must be split into two separate strokes
        self.assertEqual(len(refined), 2, "Stroke with 110px gap must be split into two independent strokes")
        self.assertEqual(refined[0]["points"][-1]["x"], 140)
        self.assertEqual(refined[1]["points"][0]["x"], 250)

    def test_strokes_to_renderer_path_gap_safety(self):
        """Verifies that strokes_to_renderer_path never interpolates across gaps > 40px, inserting None pen-up."""
        from engine.manual_drawing import strokes_to_renderer_path
        stroke = {
            "id": "stroke_renderer_gap",
            "color_bgr": (255, 255, 255),
            "width": 6,
            "points": [
                {"x": 100, "y": 200},
                {"x": 110, "y": 200},
                # Gap of 90px between (110, 200) and (200, 200)
                {"x": 200, "y": 200},
                {"x": 210, "y": 200},
            ]
        }
        path, colors, widths = strokes_to_renderer_path([stroke])
        # There must be a None pen-up delimiter between (110, 200) and (200, 200)
        self.assertIn(None, path, "Path must contain a None pen-up delimiter across the 90px gap")

    def test_upload_reference_rejects_blank_image(self):
        """Verifies that POST /api/upload-reference rejects images without black linework with HTTP 400."""
        client = app.test_client()
        blank_img = np.full((500, 500, 3), 255, dtype=np.uint8)
        _, buf = cv2.imencode(".png", blank_img)
        data = {
            "reference_image": (BytesIO(buf.tobytes()), "blank_test.png")
        }
        res = client.post("/api/upload-reference", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400, "Blank blueprint must be rejected with 400")
        res_json = res.get_json()
        self.assertFalse(res_json["success"])
        self.assertIn("No valid black linework", res_json["error"])


if __name__ == "__main__":
    unittest.main()
