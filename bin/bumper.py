#!/usr/bin/env python3
"""
bumper.py — wrap a narrated episode body with a music-and-voice intro/outro.

Given an episode's spoken TITLE and its already-rendered body audio, produce a
finished episode:

  [music solo] -> [music ducked under spoken intro] -> [music fade out]
    -> [episode body]
    -> [outro music fade in] -> [spoken outro over music] -> [music tail]

The spoken intro/outro are synthesized with the same Google Chirp 3 HD voice as
the show (via bin/tts_google.py), so the transition is seamless. Intro text is
derived from the episode title; the outro is fixed.

Music must be a cleared/royalty-free track at assets/bumper-music.mp3 (override
with BUMPER_MUSIC). See CLAUDE.md for sourcing. If the music file is absent,
the script exits with a clear message rather than producing a silent bumper.

Usage (normally invoked by bin/build.sh when BUMPER=1):
  bumper.py --title "Arles as Rome" --body BODY.mp3 --out OUT.mp3

Timing knobs (env, seconds):
  BUMPER_INTRO_LEAD   music solo before the intro voice   (default 4.0)
  BUMPER_INTRO_TAIL   music after intro voice, into fade  (default 1.5)
  BUMPER_OUTRO_LEAD   outro music solo before outro voice (default 2.5)
  BUMPER_OUTRO_TAIL   music tail after outro voice        (default 4.0)
  BUMPER_MUSIC_DB     how far to duck music under voice    (default -15 dB)
  BUMPER_MUSIC_BED_DB steady music-bed level under voice   (default -8 dB overall gain)
"""

import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC = os.environ.get("BUMPER_MUSIC", os.path.join(ROOT, "assets", "bumper-music.mp3"))
TTS = os.path.join(ROOT, "bin", "tts_google.py")

LEAD = float(os.environ.get("BUMPER_INTRO_LEAD", "4.0"))
INTRO_TAIL = float(os.environ.get("BUMPER_INTRO_TAIL", "2.5"))
INTRO_FADE = float(os.environ.get("BUMPER_INTRO_FADE", "2.2"))  # slow fade after intro
INTRO_GAP = float(os.environ.get("BUMPER_INTRO_GAP", "0.8"))    # pause before body
OUTRO_LEAD = float(os.environ.get("BUMPER_OUTRO_LEAD", "2.5"))
OUTRO_TAIL = float(os.environ.get("BUMPER_OUTRO_TAIL", "4.0"))
OUTRO_FADE = float(os.environ.get("BUMPER_OUTRO_FADE", "2.0"))
MUSIC_BED_DB = os.environ.get("BUMPER_MUSIC_BED_DB", "-8")   # music level under speech
BITRATE = os.environ.get("GOOGLE_TTS_BITRATE", "128k")

OUTRO_TEXT = ("This has been Colors of Provence. Until the next stop.")


def intro_text(title):
    return ("Colors of Provence — a traveler's companion through the history, "
            f"culture, and food of France. Today's episode: {title}.")


def run(cmd):
    subprocess.run(cmd, check=True)


def tts(text, out_path):
    """Render a short spoken line with the show voice (Chirp 3 HD)."""
    p = subprocess.run(["python3", TTS, out_path], input=text, text=True)
    if p.returncode != 0 or not os.path.exists(out_path):
        sys.exit("bumper: TTS of intro/outro failed")


def dur(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def build_segment(voice, music, seg_out, lead, tail, fade, tmp):
    """Compose one music+voice segment (used for both intro and outro).

    Structure: music plays; voice enters after `lead`s; music ducks under the
    voice (sidechain compression); after the voice ends, `tail`s of music, then
    a `fade`-second fade to silence. Returns the path to a standalone segment.
    """
    vlen = dur(voice)
    total = lead + vlen + tail
    # Delay the voice by `lead` seconds so music opens the segment.
    # Sidechain-compress the music by the voice so it ducks automatically.
    fade = min(fade, tail)
    fade_start = max(0.0, total - fade)
    # A filter-pad label can only be consumed once, so split the voice into two
    # copies: one drives the sidechain ducking, the other is mixed in audibly.
    mlen = dur(music)
    if mlen < total:
        # The clip must never loop (it would audibly restart mid-bumper); if it
        # is somehow shorter than the segment, pad the END with silence instead.
        print(f"    bumper: WARNING music clip ({mlen:.1f}s) shorter than "
              f"segment ({total:.1f}s); padding with silence. Use a longer "
              f"assets/bumper-music.mp3.", file=sys.stderr)
    # A filter-pad label can only be consumed once, so split the voice into two
    # copies: one drives the sidechain ducking, the other is mixed in audibly.
    # Music is trimmed to the exact segment length and padded (never looped).
    filt = (
        f"[1:a]adelay={int(lead*1000)}|{int(lead*1000)},apad=pad_dur={tail},"
        f"asplit=2[vduck][vmix];"
        f"[0:a]atrim=0:{total:.2f},apad,volume={MUSIC_BED_DB}dB[m];"
        f"[m][vduck]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[mc];"
        f"[mc][vmix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix];"
        f"[mix]afade=t=out:st={fade_start:.2f}:d={fade:.2f},"
        f"atrim=0:{total:.2f}[out]"
    )
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-i", music,   # NOT looped — clip is cut long enough (see assets)
         "-i", voice,
         "-filter_complex", filt, "-map", "[out]",
         "-ac", "1", "-ar", "24000",
         "-codec:a", "libmp3lame", "-b:a", BITRATE, seg_out])
    return seg_out


def concat(parts, out_path, tmp):
    listf = os.path.join(tmp, "concat.txt")
    with open(listf, "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    # Re-encode on concat so sample params are uniform and joins are clean.
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listf, "-ac", "1", "-ar", "24000",
         "-codec:a", "libmp3lame", "-b:a", BITRATE, out_path])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not os.path.exists(MUSIC):
        sys.exit(f"bumper: music not found at {MUSIC}\n"
                 "Add a cleared/royalty-free gypsy-jazz track there "
                 "(see CLAUDE.md), or build without BUMPER=1.")

    with tempfile.TemporaryDirectory() as tmp:
        intro_v = os.path.join(tmp, "intro_v.mp3")
        outro_v = os.path.join(tmp, "outro_v.mp3")
        tts(intro_text(args.title), intro_v)
        tts(OUTRO_TEXT, outro_v)

        intro_seg = build_segment(intro_v, MUSIC, os.path.join(tmp, "intro.mp3"),
                                  LEAD, INTRO_TAIL, INTRO_FADE, tmp)
        outro_seg = build_segment(outro_v, MUSIC, os.path.join(tmp, "outro.mp3"),
                                  OUTRO_LEAD, OUTRO_TAIL, OUTRO_FADE, tmp)

        # A short beat of silence after the intro music fades, before the body.
        gap = os.path.join(tmp, "gap.mp3")
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "anullsrc=r=24000:cl=mono", "-t", f"{INTRO_GAP}",
             "-codec:a", "libmp3lame", "-b:a", BITRATE, gap])

        # Normalize the body to the same params so the concat is seamless.
        body_norm = os.path.join(tmp, "body.mp3")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", args.body,
             "-ac", "1", "-ar", "24000",
             "-codec:a", "libmp3lame", "-b:a", BITRATE, body_norm])

        concat([intro_seg, gap, body_norm, outro_seg], args.out, tmp)
    print(f"    bumper: wrapped -> {os.path.basename(args.out)}")


if __name__ == "__main__":
    main()
