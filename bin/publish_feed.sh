#!/usr/bin/env bash
#
# publish_feed.sh — regenerate the RSS feed + docs/ and push to GitHub Pages.
#
# Serves at:  https://ardell.github.io/france_podcast/feed.xml
# Subscribe in Apple Podcasts: Library → ··· → "Follow a Show by URL".
#
# Run after building new episodes. Idempotent: re-copies all mp3s into docs/,
# regenerates feed.xml, commits, and pushes.

set -euo pipefail
cd "$(dirname "$0")/.."

export FEED_BASE_URL="${FEED_BASE_URL:-https://ardell.github.io/france_podcast}"

echo "France Podcast — publish feed → $FEED_BASE_URL/feed.xml"
python3 bin/make_feed.py

git add -A
if git diff --cached --quiet; then
  echo "No changes to publish."
  exit 0
fi
git commit -m "Publish podcast feed and episodes."
git push origin main
echo "Pushed. GitHub Pages will update in a minute or two."
