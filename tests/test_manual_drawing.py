"""
Unit tests for engine/manual_drawing.py
Tests validation, coordinate clamping, stroke order, pen-up delimiters, and sketch generation.
"""

import os
import unittest
import numpy as np
import cv2

from engine.manual_drawing import (
    hex_to_bgr,
    validate_and_normalize_drawing_payload,
    strokes_to_renderer_path,
    render_strokes_to_sketch_image
)


class TestManualDrawing(unittest.TestCase):

    def test_hex_to_bgr(self):
        self.assertEqual(hex_to_bgr("#FFFFFF"), (255, 255, 255))
        self.assertEqual(hex_to_bgr("#000000"), (0, 0, 0))
        self.assertEqual(hex_to_bgr("#FF0000"), (0, 0, 255))
        self.assertEqual(hex_to_bgr("#00FF00"), (0, 255, 0))
        self.assertEqual(hex_to_bgr("#0000FF"), (255, 0, 0))
        self.assertEqual(hex_to_bgr("invalid", default=(1, 2, 3)), (1, 2, 3))

    def test_validate_and_normalize_drawing_payload(self):
        payload = {
            "canvas": {"width": 1080, "height": 1920},
            "title": "Test Title",
            "dot_grid": "none",
            "strokes": [
                {
                    "id": "s1",
                    "color": "#FFFFFF",
                    "width": 6,
                    "points": [
                        {"x": -10, "y": 2000, "t": 0},
                        {"x": 540, "y": 960, "t": 50},
                        {"x": 540, "y": 960, "t": 60},
                        {"x": 800, "y": 1200, "t": 100}
                    ]
                },
                {
                    "id": "s2",
                    "color": "#FFD700",
                    "width": 8,
                    "points": [
                        {"x": 500, "y": 500, "t": 150}
                    ]
                }
            ]
        }

        normalized = validate_and_normalize_drawing_payload(payload)
        self.assertEqual(len(normalized["strokes"]), 2)
        s1 = normalized["strokes"][0]
        self.assertEqual(s1["points"][0]["x"], 0)
        self.assertEqual(s1["points"][0]["y"], 1919)
        self.assertEqual(len(s1["points"]), 3)

        s2 = normalized["strokes"][1]
        self.assertEqual(len(s2["points"]), 2)

    def test_empty_or_malformed_payload(self):
        with self.assertRaises(ValueError):
            validate_and_normalize_drawing_payload({})

        with self.assertRaises(ValueError):
            validate_and_normalize_drawing_payload({"strokes": []})

        with self.assertRaises(ValueError):
            validate_and_normalize_drawing_payload({"strokes": [{"points": []}]})

    def test_stroke_order_and_pen_up_delimiters(self):
        strokes = [
            {
                "id": "stroke_1",
                "color_bgr": (255, 255, 255),
                "width": 6,
                "points": [{"x": 100, "y": 100, "t": 0}, {"x": 105, "y": 105, "t": 10}]
            },
            {
                "id": "stroke_2",
                "color_bgr": (0, 215, 255),
                "width": 8,
                "points": [{"x": 300, "y": 300, "t": 20}, {"x": 310, "y": 310, "t": 30}]
            }
        ]

        path, colors, widths = strokes_to_renderer_path(strokes)
        self.assertIn(None, path)
        none_idx = path.index(None)
        self.assertGreater(none_idx, 0)
        self.assertLess(none_idx, len(path) - 1)

        self.assertEqual(path[0], (100, 100))
        self.assertEqual(path[none_idx + 1], (300, 300))
        self.assertEqual(colors[0], (255, 255, 255))
        self.assertEqual(colors[none_idx + 1], (0, 215, 255))

    def test_render_strokes_to_sketch_image(self):
        strokes = [
            {
                "id": "s1",
                "color_bgr": (255, 255, 255),
                "width": 6,
                "points": [{"x": 200, "y": 400, "t": 0}, {"x": 800, "y": 1400, "t": 100}]
            }
        ]
        out_path = "outputs/test_sketch_unit.png"
        saved = render_strokes_to_sketch_image(strokes, out_path, 1080, 1920)
        self.assertTrue(os.path.exists(saved))

        img = cv2.imread(saved)
        self.assertEqual(img.shape, (1920, 1080, 3))
        self.assertGreater(img.mean(), 240)
        self.assertTrue((img < 50).any())

        if os.path.exists(saved):
            os.remove(saved)


if __name__ == "__main__":
    unittest.main()
