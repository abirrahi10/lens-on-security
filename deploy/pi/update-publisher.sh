#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${BASE_DIR:-/mnt/nas/websites/lens-on-security}"
APP_DIR="$BASE_DIR/admin-app"
VENV_DIR="$BASE_DIR/admin-venv"
REPO_DIR="$BASE_DIR/repository"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "Publishing repository not found at $REPO_DIR" >&2
  exit 1
fi
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Publisher virtual environment not found at $VENV_DIR" >&2
  exit 1
fi

git -C "$REPO_DIR" remote set-url origin https://github.com/abirrahi10/lens-on-security.git
git -C "$REPO_DIR" remote set-url --push origin git@github.com:abirrahi10/lens-on-security.git
git -C "$REPO_DIR" pull --ff-only origin main
mkdir -p "$APP_DIR/admin" "$APP_DIR/deploy/pi"
cp -a "$REPO_DIR/admin/." "$APP_DIR/admin/"
cp "$REPO_DIR/deploy/pi/lens-publisher.service" "$APP_DIR/deploy/pi/lens-publisher.service"
"$VENV_DIR/bin/pip" install -r "$APP_DIR/admin/requirements.txt"

sudo install -m 0644 "$APP_DIR/deploy/pi/lens-publisher.service" /etc/systemd/system/lens-publisher.service
sudo systemctl daemon-reload
sudo systemctl restart lens-publisher.service
sudo systemctl is-active --quiet lens-publisher.service

echo "Lens Publisher updated and running."
