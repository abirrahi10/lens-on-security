import io
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

os.environ.setdefault("LENS_SECRET_KEY", "test-secret")

import app as publisher


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        publisher.DRAFT_DIR = Path(self.temporary.name) / "drafts"
        publisher.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = publisher.app.test_client()

    def tearDown(self):
        self.temporary.cleanup()

    def csrf(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "valid-token"
        return "valid-token"

    def valid_form(self):
        image = io.BytesIO()
        Image.new("RGB", (40, 40), "green").save(image, format="PNG")
        image.seek(0)
        return {
            "csrf_token": self.csrf(),
            "title": "A New Lens",
            "slug": "a-new-lens",
            "dek": "A short description.",
            "date": "August 1, 2026",
            "read_time": "2 min read",
            "tags": "identity, access",
            "sources": "https://example.com/source",
            "body": "A useful paragraph.",
            "image_file": (image, "photo.png"),
            "image_alt": "A green test image",
            "action": "save",
        }

    def test_dashboard_is_available_from_private_address(self):
        response = self.client.get("/admin/", environ_base={"REMOTE_ADDR": "10.47.12.20"})
        self.assertEqual(response.status_code, 200)

    def test_public_address_is_denied(self):
        response = self.client.get("/admin/", environ_base={"REMOTE_ADDR": "203.0.113.4"})
        self.assertEqual(response.status_code, 403)

    def test_write_requires_csrf(self):
        response = self.client.post("/admin/new", data={"title": "No token"})
        self.assertEqual(response.status_code, 400)

    def test_draft_and_processed_image_are_saved(self):
        response = self.client.post(
            "/admin/new",
            data=self.valid_form(),
            content_type="multipart/form-data",
            environ_base={"REMOTE_ADDR": "192.168.4.20"},
        )
        self.assertEqual(response.status_code, 302)
        drafts = publisher.list_drafts()
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["slug"], "a-new-lens")
        self.assertEqual(len(drafts[0]["images"]), 1)
        saved = publisher.draft_path(drafts[0]["id"]) / "images" / drafts[0]["images"][0]["filename"]
        self.assertTrue(saved.is_file())
        with Image.open(saved) as result:
            self.assertEqual(result.format, "JPEG")
            self.assertFalse(result.getexif())


if __name__ == "__main__":
    unittest.main()
