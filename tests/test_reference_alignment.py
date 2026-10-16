"""
Unit and integration tests for engine/reference_alignment.py
Validates reference preprocessing, stroke matching, geometric correction,
endpoint preservation, confidence gating, format handling, and regression safety.
"""

import os
import shutil
import tempfile
import unittest
import numpy as np
import cv2

from engine.reference_alignment import (
    CorrectionConfig,
    ReferencePath,
    ReferenceGeometry,
    preprocess_reference_image,
    match_stroke_to_reference,
    align_stroke_to_reference,
    correct_stroke_sequence,
    validate_corrected_path,
    render_corrected_sketch,
    save_alignment_diagnostics
)
from engine.manual_drawing import strokes_to_renderer_path


class TestReferenceAlignment(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_a_slightly_displaced_straight_line(self):
        """Test A: Human stroke slightly offset from straight reference line moves closer while preserving direction."""
        # 1. Create reference image with horizontal line at y=960, x in [200, 880]
        ref = np.full((1920, 1080, 3), 255, dtype=np.uint8)
        cv2.line(ref, (200, 960), (880, 960), (0, 0, 0), 6)
        ref_path = os.path.join(self.temp_dir, "ref_straight.png")
        cv2.imwrite(ref_path, ref)

        ref_geom = preprocess_reference_image(ref_path)
        self.assertGreater(len(ref_geom.paths), 0)

        # 2. Human stroke offset by 15px downwards at y=975 from x=210 to x=870
        N = 60
        hx = np.linspace(210, 870, N)
        hy = np.full(N, 975.0)
        human_pts = [{"x": int(round(x)), "y": int(round(y)), "t": i * 20.0} for i, (x, y) in enumerate(zip(hx, hy))]
        stroke = {
            "id": "stroke_straight",
            "color_bgr": (255, 255, 255),
            "width": 6,
            "points": human_pts
        }

        # Measure distance before correction
        dists_before, _ = ref_geom.skel_tree.query(np.column_stack([hx, hy]))
        med_before = np.median(dists_before)
        self.assertGreater(med_before, 10.0)

        # 3. Align stroke
        corr_stroke, diag = align_stroke_to_reference(stroke, ref_geom)
        self.assertEqual(diag["status"], "aligned")
        self.assertGreaterEqual(diag["confidence"], 0.65)

        corr_pts = np.array([[p["x"], p["y"]] for p in corr_stroke["points"]])
        dists_after, _ = ref_geom.skel_tree.query(corr_pts)
        med_after = np.median(dists_after)

        # Quantitative verification: median distance decreased significantly
        self.assertLess(med_after, med_before / 3.0)

        # Direction preservation: x increases monotonically from left to right
        self.assertGreater(corr_pts[-1, 0], corr_pts[0, 0])
        # Start and end endpoints are preserved close to human start and end
        self.assertLess(abs(corr_pts[0, 0] - 210), 15.0)
        self.assertLess(abs(corr_pts[-1, 0] - 870), 15.0)

    def test_b_wobbly_curved_line(self):
        """Test B: Human stroke with wobbly deviations around a curve follows reference and becomes smoother."""
        # 1. Reference image containing circular arc
        ref = np.full((1920, 1080, 3), 255, dtype=np.uint8)
        center = (540, 960)
        radius = 250
        cv2.circle(ref, center, radius, (0, 0, 0), 6)
        ref_path = os.path.join(self.temp_dir, "ref_circle.png")
        cv2.imwrite(ref_path, ref)

        ref_geom = preprocess_reference_image(ref_path)

        # 2. Human stroke tracing top half from angle pi (left) to 0 (right) with sinusoidal wobble
        N = 70
        angles = np.linspace(np.pi, 2 * np.pi, N)
        wobble = 10.0 * np.sin(angles * 8.0)
        hx = center[0] + (radius + wobble) * np.cos(angles)
        hy = center[1] + (radius + wobble) * np.sin(angles)
        human_pts = [{"x": int(round(x)), "y": int(round(y)), "t": i * 15.0} for i, (x, y) in enumerate(zip(hx, hy))]

        stroke = {
            "id": "stroke_wobbly_arc",
            "color_bgr": (255, 255, 255),
            "width": 6,
            "points": human_pts
        }

        dists_before, _ = ref_geom.skel_tree.query(np.column_stack([hx, hy]))
        med_before = np.median(dists_before)

        corr_stroke, diag = align_stroke_to_reference(stroke, ref_geom)
        self.assertEqual(diag["status"], "aligned")

        corr_pts = np.array([[p["x"], p["y"]] for p in corr_stroke["points"]])
        dists_after, _ = ref_geom.skel_tree.query(corr_pts)
        med_after = np.median(dists_after)

        # Verification: median distance reduced and stays on correct radius
        self.assertLess(med_after, med_before / 2.0)
        rad_deviations = np.abs(np.linalg.norm(corr_pts - center, axis=1) - radius)
        self.assertLess(np.median(rad_deviations), 4.0)

    def test_c_two_nearby_contours_no_switching(self):
        """Test C: Reference image with two distinct nearby parallel lines does NOT jump/switch lines."""
        # 1. Two horizontal lines: Line 1 at y=900, Line 2 at y=930 (30px apart)
        ref = np.full((1920, 1080, 3), 255, dtype=np.uint8)
        cv2.line(ref, (200, 900), (880, 900), (0, 0, 0), 4)
        cv2.line(ref, (200, 930), (880, 930), (0, 0, 0), 4)
        ref_path = os.path.join(self.temp_dir, "ref_two_lines.png")
        cv2.imwrite(ref_path, ref)

        ref_geom = preprocess_reference_image(ref_path)

        # 2. Human stroke traces Line 1 at y=905 (5px from Line 1, 25px from Line 2)
        N = 50
        hx = np.linspace(250, 850, N)
        hy = np.full(N, 905.0)
        human_pts = [{"x": int(round(x)), "y": int(round(y)), "t": i * 10.0} for i, (x, y) in enumerate(zip(hx, hy))]
        stroke = {"id": "stroke_line1", "color_bgr": (255, 255, 255), "width": 6, "points": human_pts}

        corr_stroke, diag = align_stroke_to_reference(stroke, ref_geom)
        self.assertEqual(diag["status"], "aligned")

        corr_pts = np.array([[p["x"], p["y"]] for p in corr_stroke["points"]])
        # Verify that all corrected y coordinates stay on Line 1 (~900) and NEVER switch to Line 2 (~930)
        self.assertLess(np.max(np.abs(corr_pts[:, 1] - 900.0)), 6.0)
        self.assertFalse((corr_pts[:, 1] > 915.0).any())

    def test_d_multiple_independent_strokes(self):
        """Test D: Multiple independent strokes preserve original order, direction, and pen-up delimiters."""
        ref = np.full((1920, 1080, 3), 255, dtype=np.uint8)
        cv2.line(ref, (200, 500), (800, 500), (0, 0, 0), 6)
        cv2.line(ref, (200, 1200), (800, 1200), (0, 0, 0), 6)
        ref_path = os.path.join(self.temp_dir, "ref_multi.png")
        cv2.imwrite(ref_path, ref)

        ref_geom = preprocess_reference_image(ref_path)

        s1_pts = [{"x": int(x), "y": 510, "t": i * 10} for i, x in enumerate(np.linspace(200, 500, 20))]
        s2_pts = [{"x": int(x), "y": 1210, "t": 300 + i * 10} for i, x in enumerate(np.linspace(200, 700, 30))]

        strokes = [
            {"id": "stroke_first", "color_bgr": (255, 255, 255), "width": 6, "points": s1_pts},
            {"id": "stroke_second", "color_bgr": (0, 215, 255), "width": 8, "points": s2_pts}
        ]

        corr_strokes, diag = correct_stroke_sequence(strokes, ref_geom)
        self.assertEqual(len(corr_strokes), 2)
        self.assertEqual(corr_strokes[0]["id"], "stroke_first")
        self.assertEqual(corr_strokes[1]["id"], "stroke_second")
        self.assertEqual(corr_strokes[0]["color_bgr"], (255, 255, 255))
        self.assertEqual(corr_strokes[1]["color_bgr"], (0, 215, 255))

        # Check renderer path contains None pen-up delimiter between strokes
        path, colors, widths = strokes_to_renderer_path(corr_strokes)
        self.assertIn(None, path)
        none_idx = path.index(None)
        # First stroke points are near y=500, second stroke points near y=1200
        self.assertLess(abs(path[0][1] - 500), 10)
        self.assertLess(abs(path[none_idx + 1][1] - 1200), 10)

    def test_e_low_confidence_stroke_not_warped(self):
        """Test E: A stroke drawn far from all reference contours is preserved without unjustified warping."""
        ref = np.full((1920, 1080, 3), 255, dtype=np.uint8)
        # Reference line only in top region (y=200)
        cv2.line(ref, (200, 200), (800, 200), (0, 0, 0), 6)
        ref_path = os.path.join(self.temp_dir, "ref_far.png")
        cv2.imwrite(ref_path, ref)

        ref_geom = preprocess_reference_image(ref_path)

        # Human stroke drawn at y=1700 (1500px away from reference!)
        pts = [{"x": int(x), "y": 1700, "t": i * 10} for i, x in enumerate(np.linspace(300, 700, 30))]
        stroke = {"id": "freehand_stroke", "color_bgr": (255, 255, 255), "width": 6, "points": pts}

        corr_stroke, diag = align_stroke_to_reference(stroke, ref_geom)
        self.assertEqual(diag["status"], "low_confidence_retained")
        self.assertLess(diag["confidence"], 0.35)

        # Points remain at y=1700 and are NOT warped up to y=200
        for p in corr_stroke["points"]:
            self.assertEqual(p["y"], 1700)

    def test_f_endpoint_and_direction_preservation(self):
        """Test F: Corrected strokes preserve original drawing direction even if reference contour extracted in reverse."""
        ref = np.full((1920, 1080, 3), 255, dtype=np.uint8)
        cv2.line(ref, (200, 600), (800, 600), (0, 0, 0), 6)
        ref_path = os.path.join(self.temp_dir, "ref_dir.png")
        cv2.imwrite(ref_path, ref)

        ref_geom = preprocess_reference_image(ref_path)

        # Human drew from RIGHT to LEFT: x from 780 down to 220
        N = 40
        hx = np.linspace(780, 220, N)
        hy = np.full(N, 608.0)
        pts = [{"x": int(round(x)), "y": int(round(y)), "t": i * 10} for i, (x, y) in enumerate(zip(hx, hy))]
        stroke = {"id": "reverse_stroke", "color_bgr": (255, 255, 255), "width": 6, "points": pts}

        corr_stroke, diag = align_stroke_to_reference(stroke, ref_geom)
        self.assertEqual(diag["status"], "aligned")

        corr_pts = np.array([[p["x"], p["y"]] for p in corr_stroke["points"]])
        # Start should be near 780, end near 220
        self.assertGreater(corr_pts[0, 0], 700)
        self.assertLess(corr_pts[-1, 0], 300)
        # Drawing direction preserved: strictly right-to-left
        self.assertGreater(corr_pts[0, 0], corr_pts[-1, 0])

    def test_g_reference_image_formats(self):
        """Test G: Handles grayscale, RGB, RGBA, and noisy colored reference images safely."""
        # 1. Grayscale
        gray = np.full((800, 600), 255, dtype=np.uint8)
        cv2.circle(gray, (300, 400), 100, 0, 4)
        geom_gray = preprocess_reference_image(gray)
        self.assertEqual(geom_gray.fitted_image.shape, (1920, 1080, 3))
        self.assertGreater(len(geom_gray.paths), 0)

        # 2. RGBA with transparency
        rgba = np.full((500, 500, 4), 255, dtype=np.uint8)
        cv2.line(rgba, (50, 50), (450, 450), (0, 0, 0, 255), 5)
        rgba[0:50, 0:50, 3] = 0 # Transparent corner
        geom_rgba = preprocess_reference_image(rgba)
        self.assertEqual(geom_rgba.fitted_image.shape, (1920, 1080, 3))
        self.assertGreater(len(geom_rgba.paths), 0)

        # 3. Colored Rangoli with Gaussian noise
        colored = np.full((600, 600, 3), (40, 30, 20), dtype=np.uint8) # Dark floor
        cv2.circle(colored, (300, 300), 150, (0, 215, 255), 8)         # Yellow powder circle
        noise = np.random.randint(-15, 15, colored.shape, dtype=np.int16)
        noisy = np.clip(colored.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        geom_noisy = preprocess_reference_image(noisy)
        self.assertEqual(geom_noisy.fitted_image.shape, (1920, 1080, 3))
        self.assertGreater(len(geom_noisy.paths), 0)

    def test_h_empty_drawing_and_missing_reference(self):
        """Test H: Gracefully handles empty drawings, empty references, and missing files."""
        # Non-existent reference file raises FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            preprocess_reference_image("non_existent_file.png")

        # Empty strokes list returns empty results gracefully
        strokes, diag = correct_stroke_sequence([], None)
        self.assertEqual(strokes, [])
        self.assertEqual(diag["total_strokes"], 0)

        # Path validator bounds checking
        raw_path = [(-50, 2000), (540, 960), None, None, (1200, -10), None]
        validated = validate_corrected_path(raw_path, 1080, 1920)
        self.assertEqual(validated[0], (0, 1919))
        self.assertEqual(validated[1], (540, 960))
        self.assertIsNone(validated[2])
        self.assertEqual(validated[3], (1079, 0))
        self.assertNotEqual(validated[-1], None) # Trailing None stripped

    def test_diagnostics_export(self):
        """Verify optional debug diagnostics output artifacts."""
        ref = np.full((1920, 1080, 3), 255, dtype=np.uint8)
        cv2.line(ref, (200, 500), (800, 500), (0, 0, 0), 6)
        ref_geom = preprocess_reference_image(ref)

        pts = [{"x": int(x), "y": 510, "t": i * 10} for i, x in enumerate(np.linspace(200, 800, 30))]
        stroke = {"id": "s1", "color_bgr": (255, 255, 255), "width": 6, "points": pts}

        corr_strokes, diag = correct_stroke_sequence([stroke], ref_geom)
        debug_out = os.path.join(self.temp_dir, "debug_run")
        save_alignment_diagnostics(debug_out, ref_geom, [stroke], corr_strokes, diag)

        self.assertTrue(os.path.exists(os.path.join(debug_out, "01_reference_fitted.png")))
        self.assertTrue(os.path.exists(os.path.join(debug_out, "02_reference_mask.png")))
        self.assertTrue(os.path.exists(os.path.join(debug_out, "03_reference_skeleton.png")))
        self.assertTrue(os.path.exists(os.path.join(debug_out, "04_original_strokes.png")))
        self.assertTrue(os.path.exists(os.path.join(debug_out, "05_corrected_strokes.png")))
        self.assertTrue(os.path.exists(os.path.join(debug_out, "06_alignment_comparison.png")))
        self.assertTrue(os.path.exists(os.path.join(debug_out, "alignment_summary.json")))


if __name__ == "__main__":
    unittest.main()
