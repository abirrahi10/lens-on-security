#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/apps/lens-on-security}"
RELEASES_DIR="${RELEASES_DIR:-$HOME/www/lens-on-security/releases}"
CURRENT_LINK="${CURRENT_LINK:-$HOME/www/lens-on-security/current}"
SITE_URL="${SITE_URL:?Set SITE_URL to the public https URL, for example https://example.com}"
RELEASE_ID="$(date -u +%Y%m%d%H%M%S)"
RELEASE_DIR="$RELEASES_DIR/$RELEASE_ID"

cd "$APP_DIR"
git fetch --prune origin
git checkout main
git pull --ff-only origin main
npm ci
PUBLIC_SITE_URL="$SITE_URL" PUBLIC_BASE_PATH="/" npm run build

mkdir -p "$RELEASE_DIR"
cp -a dist/. "$RELEASE_DIR/"
ln -sfn "$RELEASE_DIR" "$CURRENT_LINK.next"
mv -Tf "$CURRENT_LINK.next" "$CURRENT_LINK"

# Retain the five newest releases for quick rollback.
mapfile -t old_releases < <(find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -rn | tail -n +6 | cut -d' ' -f2-)
if ((${#old_releases[@]})); then
  rm -rf -- "${old_releases[@]}"
fi

echo "Published release $RELEASE_ID"
