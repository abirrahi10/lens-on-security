from __future__ import annotations

import hmac
import ipaddress
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import bleach
import markdown
import yaml
from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import NotFound
from werkzeug.middleware.proxy_fix import ProxyFix


APP_ROOT = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("LENS_REPO_DIR", APP_ROOT.parent)).resolve()
DRAFT_DIR = Path(os.environ.get("LENS_DRAFT_DIR", "/mnt/nas/websites/lens-on-security/drafts")).resolve()
ALLOWED_NETWORKS = tuple(
    ipaddress.ip_network(value.strip())
    for value in os.environ.get("LENS_ALLOWED_NETWORKS", "10.47.12.0/24,192.168.4.0/24").split(",")
    if value.strip()
)
GIT_BRANCH = os.environ.get("LENS_GIT_BRANCH", "main")
GIT_REMOTE = os.environ.get("LENS_GIT_REMOTE", "origin")
GIT_SSH_KEY = os.environ.get("LENS_GIT_SSH_KEY", "")
GIT_KNOWN_HOSTS = os.environ.get("LENS_GIT_KNOWN_HOSTS", "")
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_RESUME_BYTES = 10 * 1024 * 1024
MAX_IMAGE_EDGE = 2400
MAX_REQUEST_BYTES = 80 * 1024 * 1024
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DRAFT_ID_RE = re.compile(r"^[a-f0-9]{32}$")
PUBLISH_LOCK = threading.Lock()
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.DOTALL)
ABOUT_DATA_FILE = REPO_DIR / "src" / "data" / "about.json"
ABOUT_PORTRAIT_FILE = REPO_DIR / "public" / "images" / "about" / "abir-rahi.jpg"
ABOUT_RESUME_FILE = REPO_DIR / "public" / "resume" / "abir-rahi-resume.pdf"
DEFAULT_ABOUT = {
    "name": "Abir Rahi",
    "certifications": ["CompTIA A+"],
    "links": [],
    "summary": "",
    "whyTitle": "",
    "whyBody": [],
    "resumeTitle": "Experience beyond the journal.",
    "portraitAlt": "Portrait of Abir Rahi",
}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("LENS_SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=0, x_host=0)


def _client_is_allowed() -> bool:
    try:
        address = ipaddress.ip_address(request.remote_addr or "")
    except ValueError:
        return False
    return address.is_loopback or any(address in network for network in ALLOWED_NETWORKS)


@app.before_request
def restrict_to_vpn() -> None:
    if not _client_is_allowed():
        abort(403)


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


def require_csrf() -> None:
    supplied = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        abort(400, "The form expired. Reload the page and try again.")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80]


def draft_path(draft_id: str) -> Path:
    if not DRAFT_ID_RE.fullmatch(draft_id):
        abort(404)
    return DRAFT_DIR / draft_id


def load_draft(draft_id: str) -> dict:
    path = draft_path(draft_id) / "draft.json"
    if not path.is_file():
        abort(404)
    return json.loads(path.read_text(encoding="utf-8"))


def save_draft_file(draft: dict) -> None:
    path = draft_path(draft["id"])
    path.mkdir(parents=True, exist_ok=True)
    temporary = path / "draft.json.tmp"
    temporary.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path / "draft.json")


def load_about() -> dict:
    about = json.loads(json.dumps(DEFAULT_ABOUT))
    if ABOUT_DATA_FILE.is_file():
        loaded = json.loads(ABOUT_DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            about.update(loaded)
    about["certifications"] = [str(value) for value in about.get("certifications", [])]
    about["links"] = [
        {"label": str(value.get("label", "")), "url": str(value.get("url", ""))}
        for value in about.get("links", [])
        if isinstance(value, dict)
    ]
    about["whyBody"] = [str(value) for value in about.get("whyBody", [])]
    return about


def about_form_values() -> tuple[dict, list[str]]:
    certifications = [
        value.strip()
        for value in re.split(r"[,\r\n]+", request.form.get("certifications", ""))
        if value.strip()
    ]
    why_body = [
        paragraph.strip()
        for paragraph in re.split(r"\r?\n\s*\r?\n", request.form.get("why_body", "").strip())
        if paragraph.strip()
    ]
    link_labels = request.form.getlist("link_label")
    link_urls = request.form.getlist("link_url")
    links = []
    link_errors = []
    for index in range(max(len(link_labels), len(link_urls))):
        label = link_labels[index].strip() if index < len(link_labels) else ""
        url = link_urls[index].strip() if index < len(link_urls) else ""
        if not label and not url:
            continue
        links.append({"label": label, "url": url})
        if not label or not url:
            link_errors.append(f"Complete both fields for profile link {index + 1}.")
            continue
        if not validate_url(url):
            link_errors.append(f"Profile link {index + 1} must be a complete http:// or https:// URL.")
            continue
    values = {
        "name": request.form.get("name", "").strip(),
        "certifications": certifications,
        "links": links,
        "summary": request.form.get("summary", "").strip(),
        "whyTitle": request.form.get("why_title", "").strip(),
        "whyBody": why_body,
        "resumeTitle": request.form.get("resume_title", "").strip(),
        "portraitAlt": request.form.get("portrait_alt", "").strip(),
    }
    errors = link_errors
    if not values["name"]:
        errors.append("Add your name.")
    if not values["summary"]:
        errors.append("Add the short About-page description.")
    if not values["whyTitle"]:
        errors.append("Add a title for the Why this exists section.")
    if not values["whyBody"]:
        errors.append("Add text for the Why this exists section.")
    if not values["resumeTitle"]:
        errors.append("Add the résumé card title.")
    if not values["portraitAlt"]:
        errors.append("Add alternative text for the headshot.")
    return values, errors


def form_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(request.form.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def uploaded_size(upload) -> int:
    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(0)
    return size


def process_about_portrait(upload, focal_x: float, focal_y: float, zoom: float) -> bytes:
    if uploaded_size(upload) > MAX_IMAGE_BYTES:
        raise ValueError(f"{upload.filename} exceeds the 20 MB image limit.")
    try:
        with Image.open(upload.stream) as source:
            image = ImageOps.exif_transpose(source)
            if image.width < 320 or image.height < 400:
                raise ValueError("Choose a headshot that is at least 320 × 400 pixels.")
            if image.mode != "RGB":
                converted = Image.new("RGB", image.size, "white")
                if "A" in image.getbands():
                    converted.paste(image, mask=image.getchannel("A"))
                else:
                    converted.paste(image)
                image = converted

            target_ratio = 4 / 5
            if image.width / image.height > target_ratio:
                base_height = float(image.height)
                base_width = base_height * target_ratio
            else:
                base_width = float(image.width)
                base_height = base_width / target_ratio
            crop_width = base_width / zoom
            crop_height = base_height / zoom
            center_x = max(crop_width / 2, min(image.width - crop_width / 2, focal_x * image.width))
            center_y = max(crop_height / 2, min(image.height - crop_height / 2, focal_y * image.height))
            box = (
                round(center_x - crop_width / 2),
                round(center_y - crop_height / 2),
                round(center_x + crop_width / 2),
                round(center_y + crop_height / 2),
            )
            cropped = image.crop(box).resize((1200, 1500), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            cropped.save(output, format="JPEG", quality=90, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError(f"{upload.filename} is not a supported photograph.") from error


def validate_resume_upload(upload) -> bytes:
    if uploaded_size(upload) > MAX_RESUME_BYTES:
        raise ValueError(f"{upload.filename} exceeds the 10 MB résumé limit.")
    data = upload.stream.read(MAX_RESUME_BYTES + 1)
    upload.stream.seek(0)
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
        raise ValueError("The résumé must be a valid PDF file.")
    return data


def write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def list_drafts() -> list[dict]:
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    drafts = []
    for path in DRAFT_DIR.glob("*/draft.json"):
        try:
            drafts.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(drafts, key=lambda item: item.get("updated_at", ""), reverse=True)


def load_published_post(slug: str) -> dict:
    if not SLUG_RE.fullmatch(slug):
        abort(404)
    path = REPO_DIR / "src" / "content" / "blog" / f"{slug}.md"
    if not path.is_file():
        abort(404)
    match = FRONTMATTER_RE.fullmatch(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"{path.name} does not contain valid Markdown frontmatter.")
    metadata = yaml.safe_load(match.group(1)) or {}
    if metadata.get("draft", False):
        abort(404)
    return {**metadata, "slug": slug, "path": path, "body": match.group(2).strip()}


def list_published_posts() -> list[dict]:
    content_dir = REPO_DIR / "src" / "content" / "blog"
    posts = []
    for path in content_dir.glob("*.md"):
        try:
            posts.append(load_published_post(path.stem))
        except NotFound:
            continue
        except (OSError, ValueError, yaml.YAMLError):
            app.logger.exception("Could not load published article %s", path)
    return sorted(posts, key=lambda item: item.get("date", ""), reverse=True)


def private_draft_for_slug(slug: str) -> dict | None:
    return next((draft for draft in list_drafts() if draft.get("slug") == slug), None)


def import_published_images(post: dict, draft: dict) -> list[dict]:
    image_dir = draft_path(draft["id"]) / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    imported = []
    existing = {image.get("filename"): image for image in draft.get("images", [])}
    allowed_public_dir = (REPO_DIR / "public" / "images" / post["slug"]).resolve()

    for image in post.get("images", []):
        source_value = str(image.get("src", ""))
        source = (REPO_DIR / "public" / source_value.lstrip("/")).resolve()
        try:
            source.relative_to(allowed_public_dir)
        except ValueError as error:
            raise ValueError(f"The image path {source_value} is outside this article's image folder.") from error
        if not source.is_file():
            raise ValueError(f"The published image {source_value} is missing from the repository.")

        original_name = source.name
        if original_name in existing and (image_dir / original_name).is_file():
            imported.append({"filename": original_name, "alt": str(image.get("alt", ""))})
            continue

        filename = f"{uuid.uuid4().hex}.jpg"
        destination = image_dir / filename
        with Image.open(source) as opened:
            normalized = ImageOps.exif_transpose(opened)
            normalized.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
            if normalized.mode != "RGB":
                background = Image.new("RGB", normalized.size, "white")
                if "A" in normalized.getbands():
                    background.paste(normalized, mask=normalized.getchannel("A"))
                else:
                    background.paste(normalized)
                normalized = background
            normalized.save(destination, format="JPEG", quality=88, optimize=True)
        imported.append({"filename": filename, "alt": str(image.get("alt", ""))})
    return imported


def restore_as_private_draft(post: dict) -> dict:
    draft = private_draft_for_slug(post["slug"]) or {
        "id": uuid.uuid4().hex,
        "created_at": datetime.now().isoformat(),
    }
    draft.update(
        title=post.get("title", ""),
        slug=post["slug"],
        dek=post.get("dek", ""),
        date=post.get("date", ""),
        read_time=post.get("readTime", ""),
        tags=list(post.get("tags", [])),
        sources=list(post.get("sources", [])),
        body=post.get("body", ""),
        updated_at=datetime.now().isoformat(),
    )
    draft["images"] = import_published_images(post, draft)
    save_draft_file(draft)
    return draft


def validate_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def form_values(existing: dict | None = None) -> tuple[dict, list[str]]:
    current = existing or {}
    title = request.form.get("title", "").strip()
    slug = slugify(request.form.get("slug", "") or title)
    tags = [part.strip().lower() for part in request.form.get("tags", "").split(",") if part.strip()]
    sources = [line.strip() for line in request.form.get("sources", "").splitlines() if line.strip()]
    body = request.form.get("body", "").strip()
    read_time = request.form.get("read_time", "").strip()
    if not read_time and body:
        minutes = max(1, round(len(body.split()) / 220))
        read_time = f"{minutes} min read"

    values = {
        **current,
        "title": title,
        "slug": slug,
        "dek": request.form.get("dek", "").strip(),
        "date": request.form.get("date", "").strip(),
        "read_time": read_time,
        "tags": tags,
        "sources": sources,
        "body": body,
        "images": list(current.get("images", [])),
    }

    errors = []
    if not title:
        errors.append("Add a title.")
    if not slug or not SLUG_RE.fullmatch(slug):
        errors.append("The URL slug must contain lowercase letters, numbers, and hyphens only.")
    if not values["dek"]:
        errors.append("Add a short description.")
    if not values["date"]:
        errors.append("Add a publication date.")
    if not tags:
        errors.append("Add at least one tag.")
    if not body:
        errors.append("Add the article text.")
    if any(not validate_url(source) for source in sources):
        errors.append("Each source must be a complete http:// or https:// URL.")
    return values, errors


def save_uploaded_images(draft: dict) -> list[str]:
    files = request.files.getlist("image_file")
    alt_values = request.form.getlist("image_alt")
    errors = []
    image_dir = draft_path(draft["id"]) / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    for index, upload in enumerate(files):
        if not upload or not upload.filename:
            continue
        alt = alt_values[index].strip() if index < len(alt_values) else ""
        if not alt:
            errors.append(f"Add alternative text for {upload.filename}.")
            continue
        upload.stream.seek(0, os.SEEK_END)
        size = upload.stream.tell()
        upload.stream.seek(0)
        if size > MAX_IMAGE_BYTES:
            errors.append(f"{upload.filename} exceeds the 20 MB image limit.")
            continue

        filename = f"{uuid.uuid4().hex}.jpg"
        destination = image_dir / filename
        try:
            with Image.open(upload.stream) as source:
                image = ImageOps.exif_transpose(source)
                image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
                if image.mode != "RGB":
                    background = Image.new("RGB", image.size, "white")
                    if "A" in image.getbands():
                        background.paste(image, mask=image.getchannel("A"))
                    else:
                        background.paste(image)
                    image = background
                image.save(destination, format="JPEG", quality=88, optimize=True)
        except (UnidentifiedImageError, OSError, ValueError):
            destination.unlink(missing_ok=True)
            errors.append(f"{upload.filename} is not a supported photograph.")
            continue
        draft["images"].append({"filename": filename, "alt": alt})
    return errors


ARTICLE_TEXT_CLASSES = {"text-accent", "text-muted", "text-warm"}


def preview_attribute_allowed(tag: str, name: str, value: str) -> bool:
    if tag == "a" and name in {"href", "title"}:
        return True
    return tag == "span" and name == "class" and value in ARTICLE_TEXT_CLASSES


def render_preview(body: str) -> str:
    rendered = markdown.markdown(body, extensions=["extra", "sane_lists"])
    return bleach.clean(
        rendered,
        tags=["p", "h2", "h3", "h4", "strong", "em", "ul", "ol", "li", "blockquote", "code", "pre", "a", "hr", "span", "mark"],
        attributes=preview_attribute_allowed,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


def run_git(*args: str) -> str:
    environment = os.environ.copy()
    if GIT_SSH_KEY:
        ssh_options = [
            "ssh",
            "-i", GIT_SSH_KEY,
            "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes",
        ]
        if GIT_KNOWN_HOSTS:
            ssh_options.extend(["-o", f"UserKnownHostsFile={GIT_KNOWN_HOSTS}"])
        environment["GIT_SSH_COMMAND"] = " ".join(ssh_options)
    completed = subprocess.run(
        ["git", "-C", str(REPO_DIR), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
        env=environment,
    )
    return completed.stdout.strip()


def markdown_document(draft: dict) -> str:
    metadata = {
        "title": draft["title"],
        "dek": draft["dek"],
        "date": draft["date"],
        "readTime": draft["read_time"],
        "tags": draft["tags"],
        "images": [
            {"src": f"/images/{draft['slug']}/{image['filename']}", "alt": image["alt"]}
            for image in draft["images"]
        ],
        "sources": draft["sources"],
        "draft": False,
    }
    frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{frontmatter}\n---\n\n{draft['body'].strip()}\n"


def publish_draft(draft: dict) -> str:
    if not draft.get("images"):
        raise ValueError("Add at least one photograph before publishing.")
    content_file = REPO_DIR / "src" / "content" / "blog" / f"{draft['slug']}.md"
    public_dir = REPO_DIR / "public" / "images" / draft["slug"]
    if content_file.exists() and not draft.get("published_commit"):
        raise ValueError("A published article already uses this URL slug.")

    with PUBLISH_LOCK:
        status = run_git("status", "--porcelain")
        if status:
            raise RuntimeError("The publishing repository has uncommitted changes and needs attention.")
        run_git("pull", "--ff-only", GIT_REMOTE, GIT_BRANCH)
        content_file.parent.mkdir(parents=True, exist_ok=True)
        public_dir.mkdir(parents=True, exist_ok=True)
        source_dir = draft_path(draft["id"]) / "images"
        for image in draft["images"]:
            shutil.copy2(source_dir / image["filename"], public_dir / image["filename"])
        content_file.write_text(markdown_document(draft), encoding="utf-8")
        run_git("add", "--", str(content_file.relative_to(REPO_DIR)), str(public_dir.relative_to(REPO_DIR)))
        run_git("commit", "-m", f"Publish: {draft['title']}")
        run_git("push", GIT_REMOTE, GIT_BRANCH)
        return run_git("rev-parse", "HEAD")


def publish_about(about: dict, portrait: bytes | None, resume: bytes | None) -> str:
    with PUBLISH_LOCK:
        if run_git("status", "--porcelain"):
            raise RuntimeError("The publishing repository has uncommitted changes and needs attention.")
        run_git("pull", "--ff-only", GIT_REMOTE, GIT_BRANCH)

        about_json = (json.dumps(about, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        write_atomic(ABOUT_DATA_FILE, about_json)
        targets = [str(ABOUT_DATA_FILE.relative_to(REPO_DIR))]
        if portrait is not None:
            write_atomic(ABOUT_PORTRAIT_FILE, portrait)
            targets.append(str(ABOUT_PORTRAIT_FILE.relative_to(REPO_DIR)))
        if resume is not None:
            write_atomic(ABOUT_RESUME_FILE, resume)
            targets.append(str(ABOUT_RESUME_FILE.relative_to(REPO_DIR)))

        run_git("add", "--", *targets)
        if not run_git("diff", "--cached", "--name-only"):
            raise ValueError("There are no About-page changes to publish.")
        run_git("commit", "-m", "Update About page")
        run_git("push", GIT_REMOTE, GIT_BRANCH)
        return run_git("rev-parse", "HEAD")


@app.get("/")
def root():
    return redirect(url_for("dashboard"))


@app.get("/admin/")
def dashboard():
    drafts = [draft for draft in list_drafts() if not draft.get("published_commit")]
    return render_template("dashboard.html", drafts=drafts, published_posts=list_published_posts())


@app.route("/admin/about", methods=["GET", "POST"])
def edit_about():
    if request.method == "GET":
        return render_template("about-editor.html", about=load_about(), errors=[])

    require_csrf()
    about, errors = about_form_values()
    portrait = None
    resume = None
    portrait_upload = request.files.get("portrait_file")
    resume_upload = request.files.get("resume_file")

    if portrait_upload and portrait_upload.filename:
        try:
            portrait = process_about_portrait(
                portrait_upload,
                form_float("crop_x", 0.5, 0, 1),
                form_float("crop_y", 0.5, 0, 1),
                form_float("crop_zoom", 1, 1, 3),
            )
        except ValueError as error:
            errors.append(str(error))
    if resume_upload and resume_upload.filename:
        try:
            resume = validate_resume_upload(resume_upload)
        except ValueError as error:
            errors.append(str(error))

    if errors:
        return render_template("about-editor.html", about=about, errors=errors), 400
    try:
        publish_about(about, portrait, resume)
        flash("About page published to GitHub. The public site is rebuilding now.", "success")
        return redirect(url_for("edit_about"))
    except (subprocess.SubprocessError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        app.logger.exception("About-page publishing failed")
        flash(str(error), "error")
        return render_template("about-editor.html", about=about, errors=[]), 500


@app.get("/admin/about/portrait")
def about_portrait():
    if not ABOUT_PORTRAIT_FILE.is_file():
        abort(404)
    return send_from_directory(ABOUT_PORTRAIT_FILE.parent, ABOUT_PORTRAIT_FILE.name, max_age=0)


@app.get("/admin/drafts/<draft_id>/images/<filename>")
def draft_image(draft_id: str, filename: str):
    if Path(filename).name != filename or not re.fullmatch(r"[a-f0-9]{32}\.jpg", filename):
        abort(404)
    directory = draft_path(draft_id) / "images"
    return send_from_directory(directory, filename, max_age=0)


@app.route("/admin/new", methods=["GET", "POST"])
def new_draft():
    if request.method == "GET":
        now = datetime.now()
        today = f"{now.strftime('%B')} {now.day}, {now.year}"
        return render_template("editor.html", draft={"date": today, "tags": [], "sources": [], "images": []}, errors=[])

    require_csrf()
    draft_id = uuid.uuid4().hex
    draft, errors = form_values({"id": draft_id, "created_at": datetime.now().isoformat(), "images": []})
    draft["updated_at"] = datetime.now().isoformat()
    errors.extend(save_uploaded_images(draft))
    save_draft_file(draft)
    if errors:
        return render_template("editor.html", draft=draft, errors=errors), 400
    flash("Draft saved.", "success")
    return redirect(url_for("edit_draft", draft_id=draft_id))


@app.route("/admin/drafts/<draft_id>", methods=["GET", "POST"])
def edit_draft(draft_id: str):
    existing = load_draft(draft_id)
    if request.method == "GET":
        return render_template("editor.html", draft=existing, errors=[])

    require_csrf()
    draft, errors = form_values(existing)
    draft["updated_at"] = datetime.now().isoformat()
    errors.extend(save_uploaded_images(draft))
    action = request.form.get("action", "save")
    if action == "publish" and not draft.get("images"):
        errors.append("Add at least one photograph before publishing.")
    save_draft_file(draft)

    if errors:
        return render_template("editor.html", draft=draft, errors=errors), 400
    if action == "publish":
        try:
            commit = publish_draft(draft)
            draft["published_commit"] = commit
            draft["published_at"] = datetime.now().isoformat()
            save_draft_file(draft)
            flash("Published to GitHub. The public site is rebuilding now.", "success")
        except (subprocess.SubprocessError, OSError, RuntimeError, ValueError) as error:
            app.logger.exception("Publishing failed")
            flash(str(error), "error")
    else:
        flash("Draft saved privately on the Pi.", "success")
    return redirect(url_for("edit_draft", draft_id=draft_id))


@app.post("/admin/drafts/<draft_id>/images/<filename>/delete")
def delete_image(draft_id: str, filename: str):
    require_csrf()
    draft = load_draft(draft_id)
    match = next((image for image in draft.get("images", []) if image["filename"] == filename), None)
    if not match or Path(filename).name != filename:
        abort(404)
    (draft_path(draft_id) / "images" / filename).unlink(missing_ok=True)
    draft["images"].remove(match)
    draft["updated_at"] = datetime.now().isoformat()
    save_draft_file(draft)
    flash("Photograph removed.", "success")
    return redirect(url_for("edit_draft", draft_id=draft_id))


@app.post("/admin/drafts/<draft_id>/delete")
def delete_draft(draft_id: str):
    require_csrf()
    draft = load_draft(draft_id)
    if draft.get("published_commit"):
        flash("Published articles cannot be deleted from the draft manager.", "error")
        return redirect(url_for("edit_draft", draft_id=draft_id))

    title = draft.get("title") or "Untitled article"
    shutil.rmtree(draft_path(draft_id))
    flash(f'Draft "{title}" and its uploaded photographs were deleted.', "success")
    return redirect(url_for("dashboard"))


@app.post("/admin/posts/<slug>/unpublish")
def unpublish_post(slug: str):
    require_csrf()
    try:
        with PUBLISH_LOCK:
            if run_git("status", "--porcelain"):
                raise RuntimeError("The publishing repository has uncommitted changes and needs attention.")
            run_git("pull", "--ff-only", GIT_REMOTE, GIT_BRANCH)
            post = load_published_post(slug)
            draft = restore_as_private_draft(post)
            public_dir = REPO_DIR / "public" / "images" / slug
            targets = [str(post["path"].relative_to(REPO_DIR))]
            if public_dir.is_dir():
                targets.append(str(public_dir.relative_to(REPO_DIR)))
            run_git("rm", "-r", "--", *targets)
            run_git("commit", "-m", f"Unpublish: {post['title']}")
            run_git("push", GIT_REMOTE, GIT_BRANCH)
            draft.pop("published_commit", None)
            draft.pop("published_at", None)
            draft["unpublished_commit"] = run_git("rev-parse", "HEAD")
            save_draft_file(draft)
        flash("Article unpublished and restored as a private draft. The public site is rebuilding now.", "success")
        return redirect(url_for("edit_draft", draft_id=draft["id"]))
    except (subprocess.SubprocessError, OSError, RuntimeError, ValueError, yaml.YAMLError) as error:
        app.logger.exception("Unpublishing failed")
        flash(str(error), "error")
        return redirect(url_for("dashboard"))


@app.post("/admin/preview")
def preview():
    require_csrf()
    return render_template(
        "preview.html",
        title=request.form.get("title", "Untitled").strip() or "Untitled",
        dek=request.form.get("dek", "").strip(),
        body=render_preview(request.form.get("body", "")),
    )


@app.post("/admin/preview-fragment")
def preview_fragment():
    require_csrf()
    return render_preview(request.form.get("body", ""))


@app.errorhandler(413)
def request_too_large(_error):
    return "The upload exceeds the 80 MB request limit.", 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090, debug=False)
