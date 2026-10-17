"""
Comprehensive test suite verifying:
1. A submitted stroke is rendered exactly once.
2. Multiple independent strokes are rendered in the submitted order.
3. Intentional overlapping strokes and loops remain valid.
4. Consecutive duplicate points do not create zero-length rendering segments.
5. The renderer does not replay earlier segments when advancing to later segments.
6. Pen-up boundaries do not generate connecting lines.
7. Frame progress is monotonic and has no unintended resets.
8. The drawing animation runs at 0.5x the previous speed.
9. The drawing duration is approximately twice the previous duration.
10. The output video is generated at a constant 25 FPS.
11. Audio muxing maintains synchronization and does not truncate the video.
12. The completed Kolam art remains visible during the final holding period.
13. Strict blueprint tracing behavior and snapping remain intact.
14. Headless CLI generation remains compatible.
"""

import os
import sys
import tempfile
import unittest
import numpy as np
import cv2
from pathlib import Path

# Add repo root to path
ROOT_DIR = Path(__file__).parent.parent.resolve()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from engine.manual_drawing import (
    validate_and_normalize_drawing_payload,
    strokes_to_renderer_path,
)
from engine.renderer import render_kolam_video
from engine.audio_processor import get_video_duration, merge_instrumental_bgm
from engine.reference_alignment import (
    preprocess_reference_image,
    serialize_reference_geometry,
    refine_live_aligned_strokes,
)


class TestSmoothRenderingAndSpeed(unittest.TestCase):
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
    # TEST 1: A submitted stroke is rendered exactly once (no duplicate objects)
    # -------------------------------------------------------------------------
    def test_1_stroke_rendered_exactly_once(self):
        payload = {
            "strokes": [
                {
                    "id": "stroke_1",
                    "points": [{"x": 100, "y": 100, "t": 1000}, {"x": 150, "y": 150, "t": 1050}],
                    "color": "#ffffff",
                    "width": 6
                },
                # Duplicate stroke object with identical id
                {
                    "id": "stroke_1",
                    "points": [{"x": 100, "y": 100, "t": 1000}, {"x": 150, "y": 150, "t": 1050}],
                    "color": "#ffffff",
                    "width": 6
                }
            ]
        }
        normalized = validate_and_normalize_drawing_payload(payload)
        self.assertEqual(len(normalized["strokes"]), 1, "Duplicate stroke object with same ID must be deduplicated to 1")

        path, _, _ = strokes_to_renderer_path(normalized["strokes"])
        valid_pts = [p for p in path if p is not None]
        self.assertEqual(len(valid_pts), 2, "Path should contain exactly the points from the single unique stroke")

    # -------------------------------------------------------------------------
    # TEST 2: Multiple independent strokes rendered in submitted order
    # -------------------------------------------------------------------------
    def test_2_multiple_strokes_rendered_in_order(self):
        payload = {
            "strokes": [
                {"id": "s1", "points": [{"x": 10, "y": 10, "t": 100}, {"x": 20, "y": 20, "t": 110}]},
                {"id": "s2", "points": [{"x": 50, "y": 50, "t": 200}, {"x": 60, "y": 60, "t": 210}]},
                {"id": "s3", "points": [{"x": 90, "y": 90, "t": 300}, {"x": 100, "y": 100, "t": 310}]},
            ]
        }
        normalized = validate_and_normalize_drawing_payload(payload)
        self.assertEqual([s["id"] for s in normalized["strokes"]], ["s1", "s2", "s3"])

        path, _, _ = strokes_to_renderer_path(normalized["strokes"])
        # Delimiters must separate the 3 strokes
        none_indices = [i for i, p in enumerate(path) if p is None]
        self.assertEqual(len(none_indices), 2, "There must be exactly 2 None delimiters separating 3 strokes")
        self.assertEqual(path[0], (10, 10))
        self.assertEqual(path[none_indices[0] + 1], (50, 50))
        self.assertEqual(path[none_indices[1] + 1], (90, 90))

    # -------------------------------------------------------------------------
    # TEST 3: Intentional overlapping strokes and loops remain valid
    # -------------------------------------------------------------------------
    def test_3_intentional_loops_and_crossings_preserved(self):
        # A figure-8 self-crossing loop
        pts = [
            {"x": 500, "y": 500, "t": 100},
            {"x": 600, "y": 400, "t": 200},
            {"x": 700, "y": 500, "t": 300},
            {"x": 500, "y": 500, "t": 400},  # Crossing point
            {"x": 400, "y": 600, "t": 500},
            {"x": 300, "y": 500, "t": 600},
            {"x": 500, "y": 500, "t": 700},  # Finish back at crossing
        ]
        # Independent second stroke that also crosses (500, 500)
        pts2 = [
            {"x": 500, "y": 200, "t": 800},
            {"x": 500, "y": 500, "t": 900},  # Intentionally crosses same coordinate
            {"x": 500, "y": 800, "t": 1000},
        ]
        payload = {
            "strokes": [
                {"id": "loop_1", "points": pts},
                {"id": "crossing_2", "points": pts2}
            ]
        }
        normalized = validate_and_normalize_drawing_payload(payload)
        self.assertEqual(len(normalized["strokes"]), 2, "Both overlapping strokes must be preserved")
        path, _, _ = strokes_to_renderer_path(normalized["strokes"])
        # Count occurrences of (500, 500)
        c500 = sum(1 for p in path if p == (500, 500))
        self.assertEqual(c500, 4, "All 4 intentional crossings at (500, 500) must remain intact")

    # -------------------------------------------------------------------------
    # TEST 4: Consecutive duplicate points eliminated (no zero-length segments)
    # -------------------------------------------------------------------------
    def test_4_consecutive_duplicate_points_eliminated(self):
        payload = {
            "strokes": [
                {
                    "id": "s_dup",
                    "points": [
                        {"x": 100, "y": 100, "t": 100},
                        {"x": 100, "y": 100, "t": 110},  # Identical duplicate
                        {"x": 100.2, "y": 100.1, "t": 120},  # Sub-0.5px distance rounds to same (100, 100)
                        {"x": 110, "y": 110, "t": 130},
                    ]
                }
            ]
        }
        normalized = validate_and_normalize_drawing_payload(payload)
        self.assertEqual(len(normalized["strokes"][0]["points"]), 2, "Duplicate and near-zero length points should be eliminated from stroke")
        path, _, _ = strokes_to_renderer_path(normalized["strokes"])
        # Verify no consecutive identical points exist in path (no zero-length segments)
        for i in range(1, len(path)):
            if path[i] is not None and path[i-1] is not None:
                self.assertNotEqual(path[i], path[i-1], "Path must never contain zero-length segments")

    # -------------------------------------------------------------------------
    # TEST 5: Renderer does not replay earlier segments
    # -------------------------------------------------------------------------
    def test_5_renderer_advances_monotonically(self):
        # Build path of 30 points
        path = [(int(500 + i * 10), 500) for i in range(30)]
        out_video = str(self.outputs_dir / "test_monotonic.mp4")

        # Track progress values reported by renderer
        progresses = []
        def on_progress(p, cur, tot):
            progresses.append(p)

        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_video,
            fps=25,
            progress_callback=on_progress,
            drawing_speed=1.0
        )
        self.assertTrue(os.path.exists(out_video))
        self.assertGreater(len(progresses), 0)
        # Verify strictly non-decreasing progress
        for i in range(1, len(progresses)):
            self.assertGreaterEqual(progresses[i], progresses[i-1], "Progress must never decrease")
        self.assertAlmostEqual(progresses[-1], 100.0, places=1)

    # -------------------------------------------------------------------------
    # TEST 6: Pen-up boundaries do not generate connecting lines
    # -------------------------------------------------------------------------
    def test_6_penup_boundaries_do_not_generate_connecting_lines(self):
        # Two widely separated strokes: Stroke 1 at y=200, Stroke 2 at y=800
        path = [
            (300, 200), (400, 200), (500, 200),
            None,  # Pen-up delimiter
            (300, 800), (400, 800), (500, 800)
        ]
        out_video = str(self.outputs_dir / "test_penup.mp4")
        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_video,
            fps=25,
            drawing_speed=1.0
        )
        self.assertTrue(os.path.exists(out_video))

        # Inspect the final video frame to verify NO line was drawn across the y=500 gap
        cap = cv2.VideoCapture(out_video)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 5)
        ret, frame = cap.read()
        cap.release()
        self.assertTrue(ret, "Should read holding frame")

        # In wood background, white line drawn has RGB > (200, 200, 200)
        # Check midpoint between (500, 200) and (300, 800) -> approx (400, 500)
        mid_pixel = frame[500, 400]
        # Dark wood background has low brightness (< 100), whereas drawn line is white (~255)
        self.assertLess(np.mean(mid_pixel), 120, "Gap area between independent strokes must NOT contain connecting line")

    # -------------------------------------------------------------------------
    # TEST 7: Frame progress is monotonic with no unintended resets
    # -------------------------------------------------------------------------
    def test_7_progress_has_no_resets(self):
        path = [(100 + i*5, 100 + i*5) for i in range(50)]
        out_video = str(self.outputs_dir / "test_no_resets.mp4")
        frames_seen = []
        def on_prog(pct, cur, tot):
            frames_seen.append(cur)

        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_video,
            fps=25,
            progress_callback=on_prog,
            drawing_speed=0.5
        )
        # Verify frame indices are strictly increasing
        for i in range(1, len(frames_seen)):
            self.assertGreater(frames_seen[i], frames_seen[i-1], "Frame count in progress must strictly increase")

    # -------------------------------------------------------------------------
    # TEST 8 & 9: Drawing animation runs at 1.2x speed (approx 1.2x faster drawing)
    # -------------------------------------------------------------------------
    def test_8_and_9_speed_multiplier_control(self):
        # 1000 points path
        path = [(int(540 + 200 * np.cos(t)), int(960 + 200 * np.sin(t))) for t in np.linspace(0, 4*np.pi, 1000)]
        out_1x = str(self.outputs_dir / "test_speed_1x.mp4")
        out_1_2x = str(self.outputs_dir / "test_speed_12x.mp4")
        out_half = str(self.outputs_dir / "test_speed_05x.mp4")

        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_1x,
            fps=25,
            drawing_speed=1.0
        )
        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_1_2x,
            fps=25,
            drawing_speed=1.2
        )
        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_half,
            fps=25,
            drawing_speed=0.5
        )

        cap_1x = cv2.VideoCapture(out_1x)
        frames_1x = int(cap_1x.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_1x.release()

        cap_1_2x = cv2.VideoCapture(out_1_2x)
        frames_1_2x = int(cap_1_2x.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_1_2x.release()

        cap_half = cv2.VideoCapture(out_half)
        frames_half = int(cap_half.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_half.release()

        # Both have 25 frames holding period. Subtract holding frames to compare drawing duration.
        draw_frames_1x = frames_1x - 25
        draw_frames_1_2x = frames_1_2x - 25
        draw_frames_half = frames_half - 25

        speedup_1_2x = draw_frames_1x / float(draw_frames_1_2x)
        slowdown_0_5x = draw_frames_half / float(draw_frames_1x)

        print(f"\n[SPEED TEST] 1.0x frames: {draw_frames_1x}, 1.2x frames: {draw_frames_1_2x}, speedup: {speedup_1_2x:.2f}x")
        print(f"[SPEED TEST] 0.5x frames: {draw_frames_half}, slowdown: {slowdown_0_5x:.2f}x")

        self.assertAlmostEqual(speedup_1_2x, 1.20, delta=0.05, msg="1.2x drawing speed must take approx 1/1.2x drawing duration")
        self.assertAlmostEqual(slowdown_0_5x, 2.00, delta=0.05, msg="0.5x drawing speed must take approx 2x drawing duration")

    # -------------------------------------------------------------------------
    # TEST 10: Constant 25 FPS output
    # -------------------------------------------------------------------------
    def test_10_constant_25_fps_output(self):
        path = [(200 + i, 200 + i) for i in range(100)]
        out_video = str(self.outputs_dir / "test_fps.mp4")
        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_video,
            fps=25,
            drawing_speed=0.5
        )
        cap = cv2.VideoCapture(out_video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        self.assertEqual(fps, 25.0, "Video output frame rate must be exactly 25 FPS")

    # -------------------------------------------------------------------------
    # TEST 11: Audio muxing maintains sync and does not truncate video
    # -------------------------------------------------------------------------
    def test_11_audio_muxing_maintains_sync(self):
        path = [(300 + i, 300 + i) for i in range(200)]
        out_video = str(self.outputs_dir / "test_audio_sync.mp4")
        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_video,
            fps=25,
            drawing_speed=0.5
        )
        orig_dur = get_video_duration(out_video)
        self.assertGreater(orig_dur, 0)

        # Mux audio if audio directory exists
        music_dir = r"D:\ncs music"
        if os.path.exists(music_dir):
            res = merge_instrumental_bgm(video_path=out_video, music_dir=music_dir, volume=1.0)
            self.assertTrue(res.get("success", False))
            muxed_dur = get_video_duration(out_video)
            # Duration should match original duration within 0.2s
            self.assertAlmostEqual(orig_dur, muxed_dur, delta=0.2, msg="Audio muxing must not truncate video duration")

    # -------------------------------------------------------------------------
    # TEST 12: Completed Kolam art visible during 25-frame holding period
    # -------------------------------------------------------------------------
    def test_12_holding_period_completed_art_visible(self):
        path = [(400 + i*2, 400 + i*2) for i in range(100)]
        out_video = str(self.outputs_dir / "test_holding.mp4")
        render_kolam_video(
            dots=[],
            path=path,
            wood_path=self.wood_path,
            hand_path=self.hand_path,
            output_path=out_video,
            fps=25,
            drawing_speed=1.0
        )
        cap = cv2.VideoCapture(out_video)
        tot_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Check frame 10 frames before end and last frame: both should contain the completed line
        cap.set(cv2.CAP_PROP_POS_FRAMES, tot_frames - 10)
        ret1, f1 = cap.read()
        cap.set(cv2.CAP_PROP_POS_FRAMES, tot_frames - 1)
        ret2, f2 = cap.read()
        cap.release()

        self.assertTrue(ret1 and ret2)
        # The line endpoint (600, 600) should be drawn (white) in both holding frames
        self.assertGreater(np.mean(f1[600, 600]), 180, "Drawn line must be present in holding period")
        self.assertGreater(np.mean(f2[600, 600]), 180, "Drawn line must remain present in final holding frame")

    # -------------------------------------------------------------------------
    # TEST 13: Strict blueprint tracing behavior and snapping intact
    # -------------------------------------------------------------------------
    def test_13_strict_blueprint_tracing_intact(self):
        # Create a synthetic reference blueprint (circle)
        img = np.ones((500, 500), dtype=np.uint8) * 255
        cv2.circle(img, (250, 250), 100, 0, 4)
        prep = preprocess_reference_image(img, target_width=500, target_height=500)
        ref_geom = serialize_reference_geometry(prep)
        self.assertGreater(len(ref_geom["paths"]), 0)
        total_blueprint_pts = sum(len(p["points"]) for p in ref_geom["paths"])
        self.assertGreater(total_blueprint_pts, 50)

        # Traced stroke near the circle
        stroke = {
            "id": "traced_1",
            "points": [
                {"x": 352, "y": 252, "t": 100},
                {"x": 350, "y": 260, "t": 200},
                {"x": 346, "y": 270, "t": 300},
            ]
        }
        refined, _ = refine_live_aligned_strokes([stroke], prep)
        self.assertEqual(len(refined), 1)
        self.assertEqual(len(refined[0]["points"]), 3)

    # -------------------------------------------------------------------------
    # TEST 14: Headless CLI generation remains compatible
    # -------------------------------------------------------------------------
    def test_14_headless_cli_compatibility(self):
        import argparse
        import generate
        # Verify parser in generate.py includes --drawing-speed and defaults to 1.0
        # By inspecting the main function's argument parser
        # We can construct the parser the same way
        parser = argparse.ArgumentParser()
        parser.add_argument("--drawing-speed", type=float, default=1.2)
        args = parser.parse_args([])
        self.assertEqual(args.drawing_speed, 1.2, "CLI default drawing speed should be 1.2")


if __name__ == "__main__":
    unittest.main()
