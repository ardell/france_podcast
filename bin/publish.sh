#!/usr/bin/env bash
#
# publish.sh — copy built mp3s (and a playlist) into Dropbox for phone sync.
#
# Usage:
#   bin/publish.sh              # publish all built episodes
#   bin/publish.sh 03-avignon   # publish a single episode by slug
#
# Destination: ~/Dropbox/France Podcast/
# Also writes a France Podcast.m3u playlist ordered by filename (the NN- prefix
# gives the intended listening order).

set -euo pipefail

cd "$(dirname "$0")/.."   # project root

AUDIO_DIR="episodes/audio"
DEST="${DROPBOX_DEST:-$HOME/Dropbox/France Podcast}"

mkdir -p "$DEST"

echo "France Podcast — publish → $DEST"

if [[ $# -gt 0 ]]; then
  for a in "$@"; do
    slug="$(basename "$a" .mp3)"
    src="$AUDIO_DIR/$slug.mp3"
    [[ -f "$src" ]] || { echo "  ! missing $src (build it first)"; exit 1; }
    cp "$src" "$DEST/"
    echo "  ✓ copied $slug.mp3"
  done
else
  shopt -s nullglob
  files=("$AUDIO_DIR"/*.mp3)
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "  (nothing built yet — run bin/build.sh first)"
    exit 0
  fi
  for src in "${files[@]}"; do
    cp "$src" "$DEST/"
    echo "  ✓ copied $(basename "$src")"
  done
fi

# Regenerate a simple playlist in listening order.
playlist="$DEST/France Podcast.m3u"
{
  echo "#EXTM3U"
  for f in "$DEST"/*.mp3; do
    [[ -e "$f" ]] || continue
    echo "$(basename "$f")"
  done
} > "$playlist"
echo "  ✓ playlist: $playlist"
echo "Done. Dropbox will sync automatically."
