#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/mnt/nas/websites/lens-on-security"
APP_DIR="$BASE_DIR/admin-app"
VENV_DIR="$BASE_DIR/admin-venv"
REPO_DIR="$BASE_DIR/repository"
DRAFT_DIR="$BASE_DIR/drafts"
CONFIG_DIR="/etc/lens-publisher"
ENV_FILE="$CONFIG_DIR/publisher.env"
DEPLOY_KEY="$CONFIG_DIR/github-deploy-key"
SERVICE_SOURCE="$APP_DIR/deploy/pi/lens-publisher.service"

sudo apt-get update
sudo apt-get install -y python3-venv

mkdir -p "$DRAFT_DIR"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/admin/requirements.txt"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone https://github.com/abirrahi10/lens-on-security.git "$REPO_DIR"
fi
git -C "$REPO_DIR" config user.name "Lens Publisher"
git -C "$REPO_DIR" config user.email "publisher@lensonsecurity.local"

sudo install -d -m 0750 -o root -g arahi10 "$CONFIG_DIR"
if [[ ! -f "$DEPLOY_KEY" ]]; then
  sudo ssh-keygen -q -t ed25519 -N "" -C "lens-on-security-publisher" -f "$DEPLOY_KEY"
fi
sudo chown root:arahi10 "$DEPLOY_KEY" "$DEPLOY_KEY.pub"
sudo chmod 0640 "$DEPLOY_KEY"
sudo chmod 0644 "$DEPLOY_KEY.pub"

if [[ ! -f "$ENV_FILE" ]]; then
  temporary_env="$(mktemp)"
  chmod 0600 "$temporary_env"
  secret="$(python3 -c 'import secrets; print(secrets.token_hex(48))')"
  {
    printf 'LENS_SECRET_KEY=%s\n' "$secret"
    printf 'LENS_REPO_DIR=%s\n' "$REPO_DIR"
    printf 'LENS_DRAFT_DIR=%s\n' "$DRAFT_DIR"
    printf 'LENS_ALLOWED_NETWORKS=10.47.12.0/24,192.168.4.0/24\n'
    printf 'LENS_GIT_BRANCH=main\n'
    printf 'LENS_GIT_REMOTE=origin\n'
    printf 'LENS_GIT_SSH_KEY=%s\n' "$DEPLOY_KEY"
  } > "$temporary_env"
  sudo install -m 0640 -o root -g arahi10 "$temporary_env" "$ENV_FILE"
  rm -f "$temporary_env"
fi

sudo install -m 0644 "$SERVICE_SOURCE" /etc/systemd/system/lens-publisher.service
sudo systemctl daemon-reload
sudo systemctl enable --now lens-publisher.service

echo
echo "GitHub deploy key (public):"
sudo cat "$DEPLOY_KEY.pub"
