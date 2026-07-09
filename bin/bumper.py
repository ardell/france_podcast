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
with BUMPER_MUSIC). See CLAUDE.md for sourcing. If the music file is absent, the
script exits with a clear message rather than producing a silent bumper.

Usage (normally invoked by bin/build.sh when BUMPER=1):
  bumper.py --title "Arles as Rome" --body BODY.mp3 --out OUT.mp3

Timing knobs (env, seconds):
  BUMPER_INTRO_LEAD   music solo before the intro voice   (default 4.0)
  BUMPER_INTRO_TAIL   music after intro voice, into fade  (default 2.5)
  BUMPER_OUTRO_LEAD   outro music solo before outro voice (default 2.5)
  BUMPER_OUTRO_TAIL   music tail after outro voice        (default 4.0)
  BUMPER_MUSIC_BED_DB steady music-bed level under voice   (default -8 dB)
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSIC = os.environ.get("BUMPER_MUSIC", os.path.join(ROOT, "assets", "bumper-music.mp3"))
TTS = os.path.join(ROOT, "bin", "tts_google.py")

# Timing (seconds). Defaults follow podcast best practice: a short (~6s) music
# solo before the voice, music kept running smoothly under the whole greeting,
# then a gentle multi-second fade — never an abrupt stop.
LEAD = float(os.environ.get("BUMPER_INTRO_LEAD", "6.0"))       # music solo before intro voice
INTRO_TAIL = float(os.environ.get("BUMPER_INTRO_TAIL", "6.0")) # music after intro voice, into fade
INTRO_FADE = float(os.environ.get("BUMPER_INTRO_FADE", "7.0")) # slow fade after intro
INTRO_GAP = float(os.environ.get("BUMPER_INTRO_GAP", "0.8"))   # pause before body
OUTRO_LEAD = float(os.environ.get("BUMPER_OUTRO_LEAD", "2.5")) # music solo before outro voice
OUTRO_TAIL = float(os.environ.get("BUMPER_OUTRO_TAIL", "6.0")) # music tail after outro voice
OUTRO_FADE = float(os.environ.get("BUMPER_OUTRO_FADE", "0"))   # 0: outro music ends naturally
OUTRO_FADE_IN = float(os.environ.get("BUMPER_OUTRO_FADE_IN", "3.5"))  # slow ease of outro music in
OUTRO_GAP = float(os.environ.get("BUMPER_OUTRO_GAP", "1.5"))   # silence after body, before outro music

# Levels. The music plays at its SOLO level when nothing else is going on, and
# ducks well BELOW the voice when the voice is present. Best practice: voice
# clearly louder than the music bed. Solo sits a few dB down; under speech the
# music is pulled down further both by a static bed cut and a firm sidechain.
MUSIC_SOLO_DB = os.environ.get("BUMPER_MUSIC_SOLO_DB", "-10")   # music level when playing alone
MUSIC_BED_DB = os.environ.get("BUMPER_MUSIC_BED_DB", "-18")   # static duck applied under speech
# Sidechain still eases in/out (slow attack, long release, so it doesn't pump),
# but bites firmly so the music sits clearly under the voice while it's talking.
DUCK_THRESHOLD = os.environ.get("BUMPER_DUCK_THRESHOLD", "0.02")
DUCK_RATIO = os.environ.get("BUMPER_DUCK_RATIO", "8")
DUCK_ATTACK = os.environ.get("BUMPER_DUCK_ATTACK", "300")     # ms — smooth, no clamp
DUCK_RELEASE = os.environ.get("BUMPER_DUCK_RELEASE", "1200")  # ms — slow, no pumping
# High-pass the music so its low end doesn't muddy the voice (~90 Hz).
MUSIC_HPF_HZ = os.environ.get("BUMPER_MUSIC_HPF_HZ", "90")
# Final loudness target for the whole episode (podcast standard).
LUFS_TARGET = os.environ.get("BUMPER_LUFS", "-16")
TRUE_PEAK = os.environ.get("BUMPER_TRUE_PEAK", "-1.5")
LUFS_RANGE = os.environ.get("BUMPER_LRA", "11")
BITRATE = os.environ.get("GOOGLE_TTS_BITRATE", "128k")

OUTRO_TEXT = ("This has been Colors of Provence. Until the next stop.")


def intro_text(title):
    return ("Colors of Provence — a traveler's companion through the history, "
            f"culture, and food of France. Today's episode: {title}.")


def run(cmd):
    subprocess.run(cmd, check=True)


# Cache rendered intro/outro lines so tweaking LEVELS/timing doesn't re-hit the
# paid TTS API for identical speech. Keyed on voice + rate + exact text, so any
# change to the wording or voice naturally misses and re-renders. Set
# BUMPER_TTS_NOCACHE=1 to bypass. Safe to delete assets/.tts-cache/ anytime.
TTS_CACHE = os.environ.get("BUMPER_TTS_CACHE",
                           os.path.join(ROOT, "assets", ".tts-cache"))


def tts(text, out_path):
    """Render a short spoken line with the show voice (Chirp 3 HD), using a
    local cache so identical text isn't re-synthesized (and re-billed)."""
    voice = os.environ.get("GOOGLE_TTS_VOICE", "en-US-Chirp3-HD-Aoede")
    rate = os.environ.get("GOOGLE_TTS_RATE", "1.0")
    key = hashlib.sha256(f"{voice}|{rate}|{text}".encode("utf-8")).hexdigest()
    cached = os.path.join(TTS_CACHE, key + ".mp3")

    if os.environ.get("BUMPER_TTS_NOCACHE") != "1" and os.path.exists(cached):
        print(f"    bumper: TTS cache hit ({key[:8]})", flush=True)
        shutil.copy2(cached, out_path)
        return

    p = subprocess.run(["python3", TTS, out_path], input=text, text=True)
    if p.returncode != 0 or not os.path.exists(out_path):
        sys.exit("bumper: TTS of intro/outro failed")

    if os.environ.get("BUMPER_TTS_NOCACHE") != "1":
        os.makedirs(TTS_CACHE, exist_ok=True)
        shutil.copy2(out_path, cached)


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

    `music` is whatever clip the caller hands in: the INTRO passes the head of
    the track (clean confident start, faded out at the end since we cut away
    into the body); the OUTRO passes a pre-cut clip taken from the END of the
    track with a fade-in baked in (see main), so it eases in and then rides out
    to the song's natural ending — pass fade=0 there to skip a synthetic fade.
    """
    vlen = dur(voice)
    total = lead + vlen + tail
    fade = min(fade, tail)
    fade_start = max(0.0, total - fade)
    mlen = dur(music)
    if mlen < total - 0.25:  # ignore sub-frame float rounding
        # The clip must never loop (it would audibly restart mid-bumper); if it
        # is genuinely shorter than the segment, pad the END with silence.
        print(f"    bumper: WARNING music clip ({mlen:.1f}s) shorter than "
              f"segment ({total:.1f}s); padding with silence. Use a longer "
              f"assets/bumper-music.mp3.", file=sys.stderr)
    # Build one music+voice segment following podcast best practice:
    #   * Music opens the segment at its SOLO level (near full).
    #   * Voice enters after `lead`s; a GENTLE sidechain compressor eases the
    #     music down (slow attack, long release, mild ratio) so it never pumps
    #     around individual words, and eases back up smoothly in pauses.
    #   * The music's low end is high-passed so it doesn't muddy the voice.
    #   * After the voice, `tail`s of music, then a slow `fade` to silence —
    #     never an abrupt stop.
    # A filter-pad label can only be consumed once, so the voice is split into
    # two copies: one drives the sidechain key, the other is mixed in audibly.
    # Music is trimmed to the exact segment length and padded (never looped).
    # Optional synthetic fade-out at the segment's end. The outro passes fade=0
    # because its music clip already ends naturally (the song's own ending).
    out_fade = (f"afade=t=out:st={fade_start:.2f}:d={fade:.2f},"
                if fade > 0.01 else "")
    filt = (
        f"[1:a]adelay={int(lead*1000)}|{int(lead*1000)},apad=pad_dur={tail},"
        f"asplit=2[vduck][vmix];"
        f"[0:a]atrim=0:{total:.2f},apad,"
        f"highpass=f={MUSIC_HPF_HZ},volume={MUSIC_SOLO_DB}dB[m];"
        f"[m][vduck]sidechaincompress="
        f"threshold={DUCK_THRESHOLD}:ratio={DUCK_RATIO}:"
        f"attack={DUCK_ATTACK}:release={DUCK_RELEASE}:makeup=1[mc];"
        f"[mc][vmix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix];"
        f"[mix]{out_fade}"
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
    """Concatenate the segments, then normalize the finished episode to the
    podcast loudness standard (-16 LUFS integrated, true peak <= TRUE_PEAK).
    Normalizing at the very end means voice and music land at a consistent,
    platform-friendly level regardless of the source levels."""
    listf = os.path.join(tmp, "concat.txt")
    with open(listf, "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    joined = os.path.join(tmp, "joined.mp3")
    # Re-encode on concat so sample params are uniform and joins are clean.
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listf, "-ac", "1", "-ar", "24000",
         "-codec:a", "libmp3lame", "-b:a", BITRATE, joined])
    # Final loudness normalization to the podcast standard.
    loudnorm = (f"loudnorm=I={LUFS_TARGET}:TP={TRUE_PEAK}:LRA={LUFS_RANGE}")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined,
         "-af", loudnorm, "-ac", "1", "-ar", "24000",
         "-codec:a", "libmp3lame", "-b:a", BITRATE, out_path])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not os.path.exists(MUSIC):
        sys.exit(f"bumper: music not found at {MUSIC}\n"
                 "Add a cleared/royalty-free track there "
                 "(see CLAUDE.md), or build without BUMPER=1.")

    with tempfile.TemporaryDirectory() as tmp:
        intro_v = os.path.join(tmp, "intro_v.mp3")
        outro_v = os.path.join(tmp, "outro_v.mp3")
        tts(intro_text(args.title), intro_v)
        tts(OUTRO_TEXT, outro_v)

        # Intro uses the HEAD of the track (clean confident start; build_segment
        # fades it out as we cut into the body).
        intro_seg = build_segment(intro_v, MUSIC, os.path.join(tmp, "intro.mp3"),
                                  LEAD, INTRO_TAIL, INTRO_FADE, tmp)

        # Outro uses the END of the track so it lands on the song's natural
        # ending. Cut a clip = exactly the outro segment length from the tail of
        # the track, and fade it IN at the start so it eases in after the body.
        outro_len = OUTRO_LEAD + dur(outro_v) + OUTRO_TAIL
        mlen = dur(MUSIC)
        # Cut from the tail so the clip ends exactly at the song's natural end.
        start = max(0.0, mlen - outro_len)
        outro_music = os.path.join(tmp, "outro_music.mp3")
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}",
             "-i", MUSIC, "-af", f"afade=t=in:st=0:d={OUTRO_FADE_IN:.2f}",
             "-ac", "1", "-ar", "24000",
             "-codec:a", "libmp3lame", "-b:a", BITRATE, outro_music])
        outro_seg = build_segment(outro_v, outro_music, os.path.join(tmp, "outro.mp3"),
                                  OUTRO_LEAD, OUTRO_TAIL, OUTRO_FADE, tmp)

        def silence(seconds, name):
            p = os.path.join(tmp, name)
            run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", "anullsrc=r=24000:cl=mono", "-t", f"{seconds}",
                 "-codec:a", "libmp3lame", "-b:a", BITRATE, p])
            return p

        # A short beat of silence after the intro music fades, before the body,
        # and another after the body before the outro music eases in.
        intro_gap = silence(INTRO_GAP, "intro_gap.mp3")
        outro_gap = silence(OUTRO_GAP, "outro_gap.mp3")

        # Normalize the body to the same params so the concat is seamless.
        body_norm = os.path.join(tmp, "body.mp3")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", args.body,
             "-ac", "1", "-ar", "24000",
             "-codec:a", "libmp3lame", "-b:a", BITRATE, body_norm])

        concat([intro_seg, intro_gap, body_norm, outro_gap, outro_seg],
               args.out, tmp)
    print(f"    bumper: wrapped -> {os.path.basename(args.out)}")


if __name__ == "__main__":
    main()
