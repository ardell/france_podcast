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
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

# The pipeline makes many small requests (foreign-word routing splits an episode
# into dozens of chunks). A single transient network stall would otherwise abort
# the whole multi-minute build after most chunks already succeeded, so transient
# failures are retried with backoff. See synthesize_chunk.
MAX_RETRIES = 4
RETRY_BACKOFF = [3, 8, 20]  # seconds before retries 2, 3, 4

ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
MAX_BYTES = 4800  # stay safely under the 5000-byte hard limit

VOICE = os.environ.get("GOOGLE_TTS_VOICE", "en-US-Chirp3-HD-Aoede")
LANG = os.environ.get("GOOGLE_TTS_LANG", "en-US")
RATE = float(os.environ.get("GOOGLE_TTS_RATE", "1.0"))
# Final MP3 bitrate for the single, high-quality encode at the end.
BITRATE = os.environ.get("GOOGLE_TTS_BITRATE", "128k")

# --- Foreign-word voice routing --------------------------------------------
# The show is narrated by one persona (Aoede). Foreign words are pronounced
# correctly by routing each to the RIGHT voice instead of making the en-US
# voice guess. The same Aoede persona exists in fr-FR / it-IT / es-ES, so a
# spliced foreign word blends seamlessly with the English narration.
#
# Mark foreign words in the .txt with a custom <fw> tag (which Google never
# sees — we strip/route it here):
#     <fw lang="it">notte</fw>                     native voice, spoken as-is
#     <fw lang="oc" ipa="ˈnɥɛtʃ">nuèch</fw>        no native voice -> IPA on a
#                                                  close Romance voice
#
# VOICE_PERSONA lets every language reuse the show's persona. LANG_VOICE maps a
# short lang code to (languageCode, native?). Languages WITHOUT a native
# Chirp3-HD voice (Occitan, Catalan, Latin, Nissart, Ligurian…) fall back to a
# close Romance voice AND require an ipa="" attribute so the word is synthesized
# via <phoneme> rather than mis-read as English. Critically the fallback voice
# is Romance, not English, so vowels like [ɔ] render correctly.
VOICE_PERSONA = os.environ.get("GOOGLE_TTS_VOICE", "en-US-Chirp3-HD-Aoede").split("-")[-1]


def _voice(language_code):
    return f"{language_code}-Chirp3-HD-{VOICE_PERSONA}"


# short code -> (languageCode for the request, has a native Chirp3-HD voice?)
# For non-native langs the languageCode is the FALLBACK Romance voice to carry
# the IPA (fr for Occitan/Catalan/Nissart; it for Latin/Ligurian).
LANG_ROUTES = {
    "fr": ("fr-FR", True),
    "it": ("it-IT", True),
    "es": ("es-ES", True),
    "en": ("en-US", True),
    # no native Chirp3-HD voice -> IPA on the nearest Romance voice:
    "oc": ("fr-FR", False),   # Occitan / Provençal
    "ca": ("es-ES", False),   # Catalan (Spanish vowels are closer than French)
    "nis": ("fr-FR", False),  # Nissart (Niçard) — Occitan-Italian
    "lig": ("it-IT", False),  # Ligurian
    "la": ("it-IT", False),   # Latin — ecclesiastical/Italianate reading
}

FW_RE = re.compile(
    r'<fw\s+lang="(?P<lang>[a-z]+)"'
    r'(?:\s+ipa="(?P<ipa>[^"]*)")?\s*>'
    r'(?P<word>.*?)</fw>',
    re.IGNORECASE | re.DOTALL,
)


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


def segment_by_voice(text):
    """Split the body into runs, each tagged with the voice that speaks it.

    Returns a list of dicts: {"voice", "lang_code", "text", "ssml"}.
    - Narration between <fw> tags -> the show voice (en-US persona), plain text.
    - <fw lang="it">notte</fw>     -> native it voice, plain word.
    - <fw lang="oc" ipa="…">…</fw> -> fallback Romance voice, SSML <phoneme>.

    Adjacent narration is emitted as-is; each <fw> is its own run so it can use
    a different voice. Runs are later chunked and synthesized independently and
    concatenated, so the persona stays constant and only the language shifts.
    """
    runs = []
    pos = 0
    for m in FW_RE.finditer(text):
        # narration before this tag
        if m.start() > pos:
            narr = text[pos:m.start()]
            if narr.strip():
                runs.append({"voice": VOICE, "lang_code": LANG,
                             "text": narr, "ssml": is_ssml(narr)})
        lang = m.group("lang").lower()
        ipa = m.group("ipa")
        word = m.group("word").strip()
        route = LANG_ROUTES.get(lang)
        if route is None:
            sys.exit(f"ERROR: <fw> unknown lang '{lang}'. Known: "
                     f"{', '.join(sorted(LANG_ROUTES))}.")
        lang_code, native = route
        if native:
            # native voice speaks the word directly (plain text is best here)
            runs.append({"voice": _voice(lang_code), "lang_code": lang_code,
                         "text": word, "ssml": False})
        else:
            if not ipa:
                sys.exit(f"ERROR: <fw lang=\"{lang}\"> needs an ipa=\"…\" "
                         f"attribute (no native voice for '{lang}'): {word!r}")
            phon = f'<phoneme alphabet="ipa" ph="{ipa}">{word}</phoneme>'
            runs.append({"voice": _voice(lang_code), "lang_code": lang_code,
                         "text": phon, "ssml": True})
        pos = m.end()
    # trailing narration
    if pos < len(text):
        tail = text[pos:]
        if tail.strip():
            runs.append({"voice": VOICE, "lang_code": LANG,
                         "text": tail, "ssml": is_ssml(tail)})
    # if there were no <fw> tags at all, one run for the whole body
    if not runs:
        runs.append({"voice": VOICE, "lang_code": LANG,
                     "text": text, "ssml": is_ssml(text)})
    return _merge_adjacent(runs)


def _merge_adjacent(runs):
    """Coalesce consecutive runs that use the same voice, to cut API calls.

    A dense episode splits narration around every <fw> word, yielding many tiny
    same-voice runs (and thus one API call each). Merging neighbours that share
    a voice collapses those back together. When either side is SSML the merged
    run is SSML — the plain-text side is then escaped as SSML prose at synthesis
    time (escape_ssml_prose leaves real tags intact), so a native word and the
    narration around it can share one request. Chunking still keeps each request
    under the byte limit. Only merges within the SAME voice, so a language
    switch always remains its own request (correct pronunciation preserved).
    """
    merged = []
    for r in runs:
        if merged and merged[-1]["voice"] == r["voice"]:
            prev = merged[-1]
            prev["text"] = prev["text"] + " " + r["text"]
            prev["ssml"] = prev["ssml"] or r["ssml"]
        else:
            merged.append(dict(r))
    return merged


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


def synthesize_chunk(text, api_key, ssml=False, voice=VOICE, lang_code=LANG):
    """Call the REST endpoint; return raw LINEAR16 WAV bytes.

    We request LINEAR16 (uncompressed PCM in a WAV container) rather than MP3,
    because Google's MP3 output is a low ~32 kbps that produces audible
    'sparkly'/'gurgly' compression artifacts on sibilants and breaths. Taking
    lossless audio and encoding to MP3 ONCE at the end (see main) avoids both
    those artifacts and any per-segment MP3 boundary blips.

    When ssml=True the chunk is XML-escaped (prose only, tags preserved) and
    wrapped in <speak>…</speak>, and sent via the ssml input field so <phoneme>
    IPA and other SSML tags take effect. voice/lang_code select which Chirp
    persona+language speaks this chunk (foreign-word routing).
    """
    if ssml:
        inner = escape_ssml_prose(text)
        ssml_doc = f"<speak>{inner}</speak>"
        input_field = {"ssml": ssml_doc}
    else:
        input_field = {"text": text}
    payload = {
        "input": input_field,
        "voice": {"languageCode": lang_code, "name": voice},
        "audioConfig": {"audioEncoding": "LINEAR16", "speakingRate": RATE},
    }
    data = json.dumps(payload).encode("utf-8")

    last_err = None
    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(
            f"{ENDPOINT}?key={api_key}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return base64.b64decode(body["audioContent"])
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            # 429 (rate limit) and 5xx are transient; other 4xx are our fault
            # (bad IPA, bad voice name) and will never succeed — fail fast.
            if e.code != 429 and e.code < 500:
                sys.exit(f"Google TTS HTTP {e.code}: {detail}")
            last_err = f"HTTP {e.code}: {detail}"
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            # network stall / DNS blip / read timeout — all worth retrying
            last_err = getattr(e, "reason", None) or str(e) or "read timeout"
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            print(f"      … transient error ({last_err}); retrying in {delay}s "
                  f"(attempt {attempt + 2}/{MAX_RETRIES})", flush=True)
            time.sleep(delay)
    sys.exit(f"Google TTS failed after {MAX_RETRIES} attempts: {last_err}")


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

    # Split the body into voice runs (narration + foreign-word segments), then
    # chunk each run to the byte limit. Every chunk carries its own voice/lang.
    runs = segment_by_voice(text)
    fw_runs = [r for r in runs if r["voice"] != VOICE]
    if fw_runs:
        langs = sorted({r["voice"].split("-", 2)[0] + "-" + r["voice"].split("-")[1]
                        for r in fw_runs})
        print(f"    Foreign-word routing: {len(fw_runs)} segment(s) -> "
              f"{', '.join(langs)}", flush=True)

    work = []  # ordered list of (chunk_text, ssml, voice, lang_code)
    for r in runs:
        budget = 4200 if r["ssml"] else MAX_BYTES
        for ch in chunk_text(r["text"], max_bytes=budget):
            work.append((ch, r["ssml"], r["voice"], r["lang_code"]))

    print(f"    Google Chirp 3 HD ({VOICE_PERSONA} persona): "
          f"{len(work)} chunk(s)", flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        raw_parts = []
        for i, (chunk, ssml, voice, lang_code) in enumerate(work):
            audio = synthesize_chunk(chunk, api_key, ssml=ssml,
                                     voice=voice, lang_code=lang_code)
            part = os.path.join(tmp, f"part-{i:03d}.wav")
            with open(part, "wb") as fh:
                fh.write(audio)
            raw_parts.append(part)
            tag = "" if voice == VOICE else f" [{lang_code}]"
            print(f"      chunk {i + 1}/{len(work)} ok{tag}", flush=True)

        # Foreign-word runs may come back at a different sample rate than the
        # narration; the ffmpeg concat DEMUXER requires identical params or the
        # output is garbled. Re-encode every part to a common PCM format first,
        # so concatenation is safe regardless of the source voice.
        norm_parts = []
        for i, p in enumerate(raw_parts):
            npart = os.path.join(tmp, f"norm-{i:03d}.wav")
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", p,
                 "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", npart],
                check=True,
            )
            norm_parts.append(npart)

        # Concatenate the normalized WAV segments, then encode to MP3 ONCE.
        listfile = os.path.join(tmp, "list.txt")
        with open(listfile, "w") as fh:
            for p in norm_parts:
                fh.write(f"file '{p}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", listfile,
             "-codec:a", "libmp3lame", "-b:a", BITRATE, out_path],
            check=True,
        )


if __name__ == "__main__":
    main()
