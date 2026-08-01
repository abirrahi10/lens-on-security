from __future__ import annotations

import hmac
import ipaddress
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
MAX_IMAGE_EDGE = 2400
MAX_REQUEST_BYTES = 80 * 1024 * 1024
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DRAFT_ID_RE = re.compile(r"^[a-f0-9]{32}$")
PUBLISH_LOCK = threading.Lock()

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


def list_drafts() -> list[dict]:
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    drafts = []
    for path in DRAFT_DIR.glob("*/draft.json"):
        try:
            drafts.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(drafts, key=lambda item: item.get("updated_at", ""), reverse=True)


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


def render_preview(body: str) -> str:
    rendered = markdown.markdown(body, extensions=["extra", "sane_lists"])
    return bleach.clean(
        rendered,
        tags=["p", "h2", "h3", "h4", "strong", "em", "ul", "ol", "li", "blockquote", "code", "pre", "a", "hr"],
        attributes={"a": ["href", "title"]},
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
        public_dir.mkdir(parents=True, exist_ok=True)
        source_dir = draft_path(draft["id"]) / "images"
        for image in draft["images"]:
            shutil.copy2(source_dir / image["filename"], public_dir / image["filename"])
        content_file.write_text(markdown_document(draft), encoding="utf-8")
        run_git("add", "--", str(content_file.relative_to(REPO_DIR)), str(public_dir.relative_to(REPO_DIR)))
        run_git("commit", "-m", f"Publish: {draft['title']}")
        run_git("push", GIT_REMOTE, GIT_BRANCH)
        return run_git("rev-parse", "HEAD")


@app.get("/")
def root():
    return redirect(url_for("dashboard"))


@app.get("/admin/")
def dashboard():
    return render_template("dashboard.html", drafts=list_drafts())


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


@app.post("/admin/preview")
def preview():
    require_csrf()
    return render_template(
        "preview.html",
        title=request.form.get("title", "Untitled").strip() or "Untitled",
        dek=request.form.get("dek", "").strip(),
        body=render_preview(request.form.get("body", "")),
    )


@app.errorhandler(413)
def request_too_large(_error):
    return "The upload exceeds the 80 MB request limit.", 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090, debug=False)
