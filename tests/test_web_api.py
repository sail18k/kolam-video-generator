"""
Integration tests for web_app.py Flask REST API.
Tests routes, image uploads, payload validations, and job status polling.
"""

import io
import os
import unittest
from web_app import app


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
        dummy_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
            b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        data = {
            "reference_image": (io.BytesIO(dummy_png), "test_pattern.png")
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
