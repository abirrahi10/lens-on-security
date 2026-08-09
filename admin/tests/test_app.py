import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

os.environ.setdefault("LENS_SECRET_KEY", "test-secret")

import app as publisher


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        publisher.DRAFT_DIR = Path(self.temporary.name) / "drafts"
        publisher.REPO_DIR = Path(self.temporary.name) / "repository"
        publisher.ABOUT_DATA_FILE = publisher.REPO_DIR / "src" / "data" / "about.json"
        publisher.ABOUT_PORTRAIT_FILE = publisher.REPO_DIR / "public" / "images" / "about" / "abir-rahi.jpg"
        publisher.ABOUT_RESUME_FILE = publisher.REPO_DIR / "public" / "resume" / "abir-rahi-resume.pdf"
        (publisher.REPO_DIR / "src" / "content" / "blog").mkdir(parents=True)
        (publisher.REPO_DIR / "public" / "images").mkdir(parents=True)
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

    def valid_about_form(self):
        portrait = io.BytesIO()
        Image.new("RGB", (1200, 1600), "green").save(portrait, format="PNG")
        portrait.seek(0)
        resume = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")
        return {
            "csrf_token": self.csrf(),
            "name": "Abir Rahi",
            "certifications": "CompTIA A+\nCompTIA Network+",
            "link_label": ["LinkedIn", "GitHub"],
            "link_url": ["https://www.linkedin.com/in/abir-rahi", "https://github.com/abirrahi10"],
            "summary": "A concise updated profile.",
            "why_title": "A clearer reason for the site.",
            "why_body": "First paragraph.\n\nSecond paragraph.",
            "resume_title": "Experience and projects.",
            "portrait_alt": "Abir Rahi outdoors",
            "crop_x": "0.45",
            "crop_y": "0.4",
            "crop_zoom": "1.4",
            "portrait_file": (portrait, "portrait.png"),
            "resume_file": (resume, "resume.pdf"),
        }

    def add_published_post(self):
        content = publisher.REPO_DIR / "src" / "content" / "blog" / "live-article.md"
        content.write_text(
            """---
title: Live Article
dek: Already on the public website.
date: August 1, 2026
readTime: 2 min read
tags: [identity]
images:
  - src: /images/live-article/photo.png
    alt: A green square
sources: []
draft: false
---

The published article body.
""",
            encoding="utf-8",
        )
        image_dir = publisher.REPO_DIR / "public" / "images" / "live-article"
        image_dir.mkdir(parents=True)
        Image.new("RGB", (40, 40), "green").save(image_dir / "photo.png", format="PNG")
        return content

    def test_dashboard_is_available_from_private_address(self):
        response = self.client.get("/admin/", environ_base={"REMOTE_ADDR": "10.47.12.20"})
        self.assertEqual(response.status_code, 200)

    def test_dashboard_lists_articles_from_publishing_repository(self):
        self.add_published_post()

        response = self.client.get("/admin/", environ_base={"REMOTE_ADDR": "10.47.12.20"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Live Article", response.data)
        self.assertIn(b"Unpublish", response.data)

    def test_dashboard_ignores_repository_drafts(self):
        content = publisher.REPO_DIR / "src" / "content" / "blog" / "hidden.md"
        content.write_text("---\ntitle: Hidden\ndraft: true\n---\n\nNot public.\n", encoding="utf-8")

        response = self.client.get("/admin/", environ_base={"REMOTE_ADDR": "10.47.12.20"})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Hidden", response.data)

    def test_public_address_is_denied(self):
        response = self.client.get("/admin/", environ_base={"REMOTE_ADDR": "203.0.113.4"})
        self.assertEqual(response.status_code, 403)

    def test_write_requires_csrf(self):
        response = self.client.post("/admin/new", data={"title": "No token"})
        self.assertEqual(response.status_code, 400)

    def test_about_editor_is_available_from_private_address(self):
        response = self.client.get("/admin/about", environ_base={"REMOTE_ADDR": "10.47.12.20"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Edit About", response.data)
        self.assertIn(b"Headshot", response.data)
        self.assertIn(b"Upload a new r", response.data)

    def test_about_editor_publishes_text_portrait_and_resume(self):
        def git_result(*args):
            if args == ("diff", "--cached", "--name-only"):
                return "src/data/about.json\npublic/images/about/abir-rahi.jpg\npublic/resume/abir-rahi-resume.pdf"
            if args == ("rev-parse", "HEAD"):
                return "abc123"
            return ""

        with patch.object(publisher, "run_git", side_effect=git_result) as run_git:
            response = self.client.post(
                "/admin/about",
                data=self.valid_about_form(),
                content_type="multipart/form-data",
                environ_base={"REMOTE_ADDR": "192.168.4.20"},
            )

        self.assertEqual(response.status_code, 302)
        about = json.loads(publisher.ABOUT_DATA_FILE.read_text(encoding="utf-8"))
        self.assertEqual(about["certifications"], ["CompTIA A+", "CompTIA Network+"])
        self.assertEqual(about["links"][0]["label"], "LinkedIn")
        self.assertEqual(about["links"][1]["url"], "https://github.com/abirrahi10")
        self.assertEqual(about["whyBody"], ["First paragraph.", "Second paragraph."])
        self.assertEqual(about["resumeTitle"], "Experience and projects.")
        with Image.open(publisher.ABOUT_PORTRAIT_FILE) as result:
            self.assertEqual(result.size, (1200, 1500))
            self.assertEqual(result.format, "JPEG")
            self.assertFalse(result.getexif())
        self.assertTrue(publisher.ABOUT_RESUME_FILE.read_bytes().startswith(b"%PDF-"))
        self.assertTrue(any(call.args[:1] == ("push",) for call in run_git.call_args_list))

    def test_about_editor_rejects_non_pdf_resume(self):
        data = self.valid_about_form()
        data.pop("portrait_file")
        data["resume_file"] = (io.BytesIO(b"not a pdf"), "resume.pdf")

        with patch.object(publisher, "run_git") as run_git:
            response = self.client.post(
                "/admin/about",
                data=data,
                content_type="multipart/form-data",
                environ_base={"REMOTE_ADDR": "192.168.4.20"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"valid PDF", response.data)
        run_git.assert_not_called()

    def test_about_editor_rejects_incomplete_profile_link(self):
        data = self.valid_about_form()
        data.pop("portrait_file")
        data.pop("resume_file")
        data["link_label"] = ["LinkedIn"]
        data["link_url"] = [""]

        with patch.object(publisher, "run_git") as run_git:
            response = self.client.post(
                "/admin/about",
                data=data,
                content_type="multipart/form-data",
                environ_base={"REMOTE_ADDR": "192.168.4.20"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Complete both fields", response.data)
        run_git.assert_not_called()

    def test_about_text_update_keeps_existing_portrait_and_resume(self):
        publisher.ABOUT_PORTRAIT_FILE.parent.mkdir(parents=True)
        publisher.ABOUT_RESUME_FILE.parent.mkdir(parents=True)
        publisher.ABOUT_PORTRAIT_FILE.write_bytes(b"existing portrait")
        publisher.ABOUT_RESUME_FILE.write_bytes(b"existing resume")
        data = self.valid_about_form()
        data.pop("portrait_file")
        data.pop("resume_file")

        def git_result(*args):
            if args == ("diff", "--cached", "--name-only"):
                return "src/data/about.json"
            if args == ("rev-parse", "HEAD"):
                return "abc123"
            return ""

        with patch.object(publisher, "run_git", side_effect=git_result):
            response = self.client.post(
                "/admin/about",
                data=data,
                content_type="multipart/form-data",
                environ_base={"REMOTE_ADDR": "192.168.4.20"},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(publisher.ABOUT_PORTRAIT_FILE.read_bytes(), b"existing portrait")
        self.assertEqual(publisher.ABOUT_RESUME_FILE.read_bytes(), b"existing resume")

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

    def test_private_draft_and_images_can_be_deleted(self):
        self.client.post(
            "/admin/new",
            data=self.valid_form(),
            content_type="multipart/form-data",
            environ_base={"REMOTE_ADDR": "192.168.4.20"},
        )
        draft = publisher.list_drafts()[0]
        directory = publisher.draft_path(draft["id"])

        response = self.client.post(
            f'/admin/drafts/{draft["id"]}/delete',
            data={"csrf_token": self.csrf()},
            environ_base={"REMOTE_ADDR": "192.168.4.20"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/admin/")
        self.assertFalse(directory.exists())
        self.assertEqual(publisher.list_drafts(), [])

    def test_published_article_record_cannot_be_deleted(self):
        self.client.post(
            "/admin/new",
            data=self.valid_form(),
            content_type="multipart/form-data",
            environ_base={"REMOTE_ADDR": "192.168.4.20"},
        )
        draft = publisher.list_drafts()[0]
        draft["published_commit"] = "abc123"
        publisher.save_draft_file(draft)

        response = self.client.post(
            f'/admin/drafts/{draft["id"]}/delete',
            data={"csrf_token": self.csrf()},
            environ_base={"REMOTE_ADDR": "192.168.4.20"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, f'/admin/drafts/{draft["id"]}')
        self.assertTrue(publisher.draft_path(draft["id"]).is_dir())

    def test_published_article_can_be_unpublished_to_private_draft(self):
        self.add_published_post()

        def git_result(*args):
            return "abc123" if args == ("rev-parse", "HEAD") else ""

        with patch.object(publisher, "run_git", side_effect=git_result) as run_git:
            response = self.client.post(
                "/admin/posts/live-article/unpublish",
                data={"csrf_token": self.csrf()},
                environ_base={"REMOTE_ADDR": "192.168.4.20"},
            )

        self.assertEqual(response.status_code, 302)
        drafts = publisher.list_drafts()
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["slug"], "live-article")
        self.assertEqual(drafts[0]["body"], "The published article body.")
        self.assertEqual(len(drafts[0]["images"]), 1)
        imported = publisher.draft_path(drafts[0]["id"]) / "images" / drafts[0]["images"][0]["filename"]
        self.assertTrue(imported.is_file())
        self.assertNotIn("published_commit", drafts[0])
        self.assertTrue(any(call.args[:3] == ("rm", "-r", "--") for call in run_git.call_args_list))

    def test_publish_recreates_content_directory_after_last_post_was_unpublished(self):
        self.client.post(
            "/admin/new",
            data=self.valid_form(),
            content_type="multipart/form-data",
            environ_base={"REMOTE_ADDR": "192.168.4.20"},
        )
        draft = publisher.list_drafts()[0]
        content_dir = publisher.REPO_DIR / "src" / "content" / "blog"
        content_dir.rmdir()

        def git_result(*args):
            return "abc123" if args == ("rev-parse", "HEAD") else ""

        with patch.object(publisher, "run_git", side_effect=git_result):
            commit = publisher.publish_draft(draft)

        self.assertEqual(commit, "abc123")
        self.assertTrue((content_dir / "a-new-lens.md").is_file())
        self.assertTrue((publisher.REPO_DIR / "public" / "images" / "a-new-lens").is_dir())


if __name__ == "__main__":
    unittest.main()
