#!/usr/bin/env bash
#
# build.sh — convert episode text scripts to audio (mp3).
#
# Usage:
#   bin/build.sh                 # build every .txt in episodes/text/ that is
#                                #   missing or out-of-date in episodes/audio/
#   bin/build.sh 03-avignon      # build a single episode by slug (no extension)
#   bin/build.sh episodes/text/03-avignon.txt   # or by path
#
# Pipeline: episodes/text/<slug>.txt --(say)--> .aiff --(ffmpeg)--> episodes/audio/<slug>.mp3
#
# Configuration via environment variables:
#   TTS     engine: "say" (default, free/offline) or "google" (Chirp 3 HD)
#   VOICE   `say` voice              (default: Daniel — warm en_GB male)
#   RATE    `say` words per minute   (default: 170)
#   BITRATE mp3 bitrate for `say`    (default: 128k)
#
# For TTS=google (Google Cloud Text-to-Speech, Chirp 3 HD):
#   GOOGLE_TTS_API_KEY   required — API key (put in .envrc)
#   GOOGLE_TTS_VOICE     default en-US-Chirp3-HD-Charon (warm male)
#   GOOGLE_TTS_RATE      speakingRate, default 1.0
#   The google path chunks long episodes (5000-byte request limit) and
#   stitches the segments with ffmpeg. Output is MP3 directly.
#
# The .txt files may begin with a metadata header block delimited by lines of
# "---". That header is stripped before narration, so only the spoken body is
# read aloud. Everything after the closing "---" is narrated verbatim.

set -euo pipefail

cd "$(dirname "$0")/.."   # project root

TTS="${TTS:-say}"
VOICE="${VOICE:-Daniel}"
RATE="${RATE:-170}"
BITRATE="${BITRATE:-128k}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

TEXT_DIR="episodes/text"
AUDIO_DIR="episodes/audio"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$AUDIO_DIR"

# Strip a leading "--- ... ---" metadata header, leaving only the spoken body.
strip_header() {
  awk '
    NR==1 && $0=="---" { inhdr=1; next }
    inhdr && $0=="---" { inhdr=0; next }
    inhdr { next }
    { print }
  ' "$1"
}

build_one() {
  local txt="$1"
  local slug base aiff mp3
  base="$(basename "$txt" .txt)"
  aiff="$TMP_DIR/$base.aiff"
  mp3="$AUDIO_DIR/$base.mp3"

  # Skip if mp3 exists and is newer than the source text.
  if [[ -f "$mp3" && "$mp3" -nt "$txt" ]]; then
    echo "  ✓ up-to-date: $base.mp3"
    return
  fi

  case "$TTS" in
    google)
      echo "  → synthesizing $base via Google Chirp 3 HD ..."
      strip_header "$txt" | python3 "$SCRIPT_DIR/tts_google.py" "$mp3"
      ;;
    say)
      echo "  → narrating $base (say, voice=$VOICE, rate=$RATE) ..."
      strip_header "$txt" | say -v "$VOICE" -r "$RATE" -o "$aiff"
      echo "  → encoding   $base.mp3 (bitrate=$BITRATE) ..."
      ffmpeg -y -loglevel error -i "$aiff" -codec:a libmp3lame -b:a "$BITRATE" "$mp3"
      ;;
    *)
      echo "ERROR: unknown TTS engine '$TTS' (use 'say' or 'google')" >&2
      exit 1
      ;;
  esac

  echo "  ✓ built: $mp3"
}

resolve() {
  # Accept a slug, a bare filename, or a full/relative path.
  local arg="$1"
  if [[ -f "$arg" ]]; then echo "$arg"; return; fi
  if [[ -f "$TEXT_DIR/$arg" ]]; then echo "$TEXT_DIR/$arg"; return; fi
  if [[ -f "$TEXT_DIR/$arg.txt" ]]; then echo "$TEXT_DIR/$arg.txt"; return; fi
  echo "ERROR: cannot find episode for '$arg'" >&2
  exit 1
}

echo "France Podcast — build"
if [[ $# -gt 0 ]]; then
  for a in "$@"; do build_one "$(resolve "$a")"; done
else
  shopt -s nullglob
  files=("$TEXT_DIR"/*.txt)
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "  (no episodes in $TEXT_DIR yet)"
    exit 0
  fi
  for txt in "${files[@]}"; do build_one "$txt"; done
fi
echo "Done."
