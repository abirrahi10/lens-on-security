#!/usr/bin/env bash
set -euo pipefail

RELEASES_DIR="${RELEASES_DIR:-$HOME/www/lens-on-security/releases}"
CURRENT_LINK="${CURRENT_LINK:-$HOME/www/lens-on-security/current}"

mapfile -t releases < <(find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2-)
if ((${#releases[@]} < 2)); then
  echo "No previous release is available." >&2
  exit 1
fi

ln -sfn "${releases[1]}" "$CURRENT_LINK.next"
mv -Tf "$CURRENT_LINK.next" "$CURRENT_LINK"
echo "Rolled back to $(basename "${releases[1]}")"
