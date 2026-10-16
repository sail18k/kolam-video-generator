"""
Integration tests for web_app.py Flask REST API.
Tests routes, image uploads, payload validations, and job status polling.
"""

import io
import os
import unittest
import numpy as np
import cv2
from web_app import app


def _create_synthetic_blueprint_bytes():
    img = np.full((600, 600, 3), 255, dtype=np.uint8)
    cv2.circle(img, (300, 300), 150, (0, 0, 0), 4)
    cv2.line(img, (150, 300), (450, 300), (0, 0, 0), 4)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


class TestWebApi(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_index_route(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("Kolam Studio", html)
        self.assertIn("drawingCanvas", html)
        self.assertIn("referenceLayer", html)

    def test_system_info(self):
        res = self.client.get("/api/system-info")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "online")
        self.assertIn("lan_ip", data)
        self.assertEqual(data["canvas_size"]["width"], 1080)
        self.assertEqual(data["canvas_size"]["height"], 1920)

    def test_upload_reference_image(self):
        png_bytes = _create_synthetic_blueprint_bytes()
        data = {
            "reference_image": (io.BytesIO(png_bytes), "test_pattern.png")
        }
        res = self.client.post("/api/upload-reference", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        self.assertIn("image_url", json_data)

    def test_upload_invalid_extension(self):
        data = {
            "reference_image": (io.BytesIO(b"malicious script"), "test.exe")
        }
        res = self.client.post("/api/upload-reference", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn("Unsupported file type", json_data["error"])

    def test_generate_job_submission(self):
        payload = {
            "canvas": {"width": 1080, "height": 1920},
            "title": "API Test Kolam",
            "dot_grid": "none",
            "strokes": [
                {
                    "id": "s1",
                    "color": "#FFFFFF",
                    "width": 6,
                    "points": [{"x": 500, "y": 600, "t": 0}, {"x": 520, "y": 620, "t": 50}]
                }
            ]
        }
        res = self.client.post("/api/generate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("job_id", data)

        job_id = data["job_id"]
        status_res = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.get_json()
        self.assertIn(status_data["status"], ["queued", "running", "completed"])

    def test_upload_empty_reference_image_rejected(self):
        # Empty white image without any blueprint linework should be rejected with 400
        img = np.full((200, 200, 3), 255, dtype=np.uint8)
        _, buf = cv2.imencode(".png", img)
        data = {
            "reference_image": (io.BytesIO(buf.tobytes()), "empty_white.png")
        }
        res = self.client.post("/api/upload-reference", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertFalse(json_data["success"])
        self.assertIn("No valid black linework", json_data["error"])

    def test_generate_job_with_reference_image(self):
        # 1. Upload valid reference blueprint
        png_bytes = _create_synthetic_blueprint_bytes()
        upload_data = {
            "reference_image": (io.BytesIO(png_bytes), "ref_test.png")
        }
        upload_res = self.client.post("/api/upload-reference", data=upload_data, content_type="multipart/form-data")
        self.assertEqual(upload_res.status_code, 200)
        uploaded_json = upload_res.get_json()
        self.assertTrue(uploaded_json["success"])
        ref_filename = uploaded_json["filename"]

        # 2. Submit generation payload referencing this uploaded guide
        payload = {
            "canvas": {"width": 1080, "height": 1920},
            "title": "Reference Guided Kolam",
            "dot_grid": "none",
            "reference_image": ref_filename,
            "correction_enabled": True,
            "strokes": [
                {
                    "id": "s1",
                    "color": "#FFFFFF",
                    "width": 6,
                    "points": [{"x": 540, "y": 960, "t": 0}, {"x": 550, "y": 970, "t": 50}]
                }
            ]
        }
        res = self.client.post("/api/generate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("job_id", data)

    def test_generate_empty_strokes_error(self):
        payload = {
            "canvas": {"width": 1080, "height": 1920},
            "title": "API Test",
            "strokes": []
        }
        res = self.client.post("/api/generate", json=payload)
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])


if __name__ == "__main__":
    unittest.main()
