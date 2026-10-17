import math
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from engine.path_generator import generate_rangoli_path


class TestPathGenerator(unittest.TestCase):
    def test_thick_line_art_circle_is_traced_once_on_its_centerline(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "thick_circle.png"
            image = np.full((600, 600), 255, dtype=np.uint8)
            cv2.circle(image, (300, 300), 150, 0, 18, lineType=cv2.LINE_AA)
            self.assertTrue(cv2.imwrite(str(image_path), image))

            path = generate_rangoli_path([], str(image_path))
            strokes = []
            current = []
            for point in path:
                if point is None:
                    if current:
                        strokes.append(current)
                        current = []
                else:
                    current.append(point)
            if current:
                strokes.append(current)

            self.assertEqual(len(strokes), 1, "The two ink edges must not become two drawing paths")
            length = sum(math.dist(a, b) for a, b in zip(strokes[0], strokes[0][1:]))
            self.assertGreater(length, 2400)
            self.assertLess(length, 3100)
            self.assertGreater(len(strokes[0]), 300)


if __name__ == "__main__":
    unittest.main()
