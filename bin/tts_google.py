#!/usr/bin/env python3
"""
tts_google.py — synthesize an episode body to MP3 using Google Cloud
Text-to-Speech, Chirp 3 HD voices.

Reads the spoken text on stdin, writes an MP3 to the path given as argv[1].

The Google v1 `text:synthesize` endpoint caps input at 5000 BYTES per request,
so long episodes (~7-8k chars) are split into chunks on paragraph/sentence
boundaries and each is synthesized separately as LINEAR16 (lossless PCM/WAV).
The segments are concatenated losslessly and encoded to MP3 exactly once at the
end. Requesting lossless audio (not Google's low ~32 kbps MP3) avoids the
watery/sparkly compression artifacts that low-bitrate MP3 produces on voice.

Auth: an API key in the environment variable GOOGLE_TTS_API_KEY.
Voice: override with env var GOOGLE_TTS_VOICE (default en-US-Chirp3-HD-Aoede).
RATE via GOOGLE_TTS_RATE (speakingRate, default 1.0).

Pronunciation of foreign words (SSML / IPA):
    If the input contains any SSML tag (e.g. a <phoneme> tag), the whole body is
    treated as SSML rather than plain text. This lets episode scripts spell out
    the pronunciation of Occitan / French / Italian / Catalan words with IPA:

        the <phoneme alphabet="ipa" ph="lɑ̃ɡ dɔk">langue d'oc</phoneme>

    Chirp 3 HD supports SSML on synchronous requests, including <phoneme> with
    alphabet="ipa". When SSML mode is active the surrounding prose is
    XML-escaped automatically and each chunk is wrapped in <speak>…</speak>;
    the existing tags are preserved untouched. Plain-text input (no tags) keeps
    the original {"input": {"text": …}} path unchanged, so the bumper greeting
    and every existing episode are unaffected.

Usage (normally invoked by bin/build.sh):
    tts_google.py OUTPUT.mp3   < body.txt
"""

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
MAX_BYTES = 4800  # stay safely under the 5000-byte hard limit

VOICE = os.environ.get("GOOGLE_TTS_VOICE", "en-US-Chirp3-HD-Aoede")
LANG = os.environ.get("GOOGLE_TTS_LANG", "en-US")
RATE = float(os.environ.get("GOOGLE_TTS_RATE", "1.0"))
# Final MP3 bitrate for the single, high-quality encode at the end.
BITRATE = os.environ.get("GOOGLE_TTS_BITRATE", "128k")


# A body is treated as SSML if it contains any tag we support. We look for an
# opening angle bracket followed by a known SSML element name.
SSML_TAG_RE = re.compile(
    r"<\s*/?\s*(speak|phoneme|sub|say-as|s|p|break|prosody|voice|audio)\b",
    re.IGNORECASE,
)


def is_ssml(text):
    """True if the body uses SSML markup (so it must be sent as ssml, not text)."""
    return bool(SSML_TAG_RE.search(text))


def escape_ssml_prose(text):
    """XML-escape the bare prose while leaving existing SSML tags intact.

    The body is a mix of plain narration and inline tags like
    <phoneme ...>word</phoneme>. We must escape &, <, > in the prose (or the
    request is rejected / mangled) but NOT touch the real tags. Strategy: split
    on tag boundaries, escape only the non-tag segments, reassemble.
    """
    parts = re.split(r"(<[^>]+>)", text)
    out = []
    for i, seg in enumerate(parts):
        if i % 2 == 1:  # a captured <...> tag — leave verbatim
            out.append(seg)
        else:           # prose between tags — escape XML metachars
            seg = seg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            out.append(seg)
    return "".join(out)


def chunk_text(text, max_bytes=MAX_BYTES):
    """Split text into <=max_bytes chunks on paragraph, then sentence, bounds."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""

    def flush():
        nonlocal cur
        if cur.strip():
            chunks.append(cur.strip())
        cur = ""

    for para in paras:
        candidate = (cur + "\n\n" + para) if cur else para
        if len(candidate.encode("utf-8")) <= max_bytes:
            cur = candidate
            continue
        # paragraph won't fit onto current chunk; flush and start fresh
        flush()
        if len(para.encode("utf-8")) <= max_bytes:
            cur = para
            continue
        # single paragraph too big: split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", para)
        for s in sentences:
            cand = (cur + " " + s) if cur else s
            if len(cand.encode("utf-8")) <= max_bytes:
                cur = cand
            else:
                flush()
                # a lone sentence over the limit is unlikely; hard-split if so
                while len(s.encode("utf-8")) > max_bytes:
                    cut = s[:max_bytes]
                    chunks.append(cut)
                    s = s[len(cut):]
                cur = s
    flush()
    return chunks


def synthesize_chunk(text, api_key, ssml=False):
    """Call the REST endpoint; return raw LINEAR16 WAV bytes.

    We request LINEAR16 (uncompressed PCM in a WAV container) rather than MP3,
    because Google's MP3 output is a low ~32 kbps that produces audible
    'sparkly'/'gurgly' compression artifacts on sibilants and breaths. Taking
    lossless audio and encoding to MP3 ONCE at the end (see main) avoids both
    those artifacts and any per-segment MP3 boundary blips.

    When ssml=True the chunk is XML-escaped (prose only, tags preserved) and
    wrapped in <speak>…</speak>, and sent via the ssml input field so <phoneme>
    IPA and other SSML tags take effect.
    """
    if ssml:
        inner = escape_ssml_prose(text)
        ssml_doc = f"<speak>{inner}</speak>"
        input_field = {"ssml": ssml_doc}
    else:
        input_field = {"text": text}
    payload = {
        "input": input_field,
        "voice": {"languageCode": LANG, "name": VOICE},
        "audioConfig": {"audioEncoding": "LINEAR16", "speakingRate": RATE},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{ENDPOINT}?key={api_key}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        sys.exit(f"Google TTS HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"Google TTS network error: {e.reason}")
    return base64.b64decode(body["audioContent"])


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: tts_google.py OUTPUT.mp3  < body.txt")
    out_path = sys.argv[1]

    api_key = os.environ.get("GOOGLE_TTS_API_KEY")
    if not api_key:
        sys.exit("ERROR: GOOGLE_TTS_API_KEY is not set (add it to .envrc).")

    text = sys.stdin.read().strip()
    if not text:
        sys.exit("ERROR: no input text on stdin.")

    ssml = is_ssml(text)
    # SSML adds bytes the raw text doesn't have: the <speak></speak> wrapper and
    # &-escaping of prose. Chunk with extra headroom so the wrapped, escaped
    # request still clears the 5000-byte hard limit.
    budget = 4200 if ssml else MAX_BYTES
    chunks = chunk_text(text, max_bytes=budget)
    mode = "SSML/IPA" if ssml else "text"
    print(f"    Google Chirp 3 HD ({VOICE}, {mode}): {len(chunks)} chunk(s)",
          flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, chunk in enumerate(chunks):
            audio = synthesize_chunk(chunk, api_key, ssml=ssml)  # LINEAR16 WAV
            part = os.path.join(tmp, f"part-{i:03d}.wav")
            with open(part, "wb") as fh:
                fh.write(audio)
            parts.append(part)
            print(f"      chunk {i + 1}/{len(chunks)} ok", flush=True)

        # Concatenate the raw WAV segments losslessly, then encode to MP3 ONCE.
        listfile = os.path.join(tmp, "list.txt")
        with open(listfile, "w") as fh:
            for p in parts:
                fh.write(f"file '{p}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", listfile,
             "-codec:a", "libmp3lame", "-b:a", BITRATE, out_path],
            check=True,
        )


if __name__ == "__main__":
    main()
