# France Podcast — project instructions

A series of short spoken-word audio essays for the listener to hear while
traveling through France: a few days in Paris, then the AmaWaterways
**Colors of Provence** river cruise on the *AmaKristina*, sailing the Rhône
**upriver from Arles to Lyon**. Each episode is a single focused topic; the
recurring themes below are woven through as relevant. Episodes are written
one at a time on request, converted to audio via text-to-speech, and published
to Dropbox for phone listening.

This is a **framework**: the listener asks for an episode (a place or a topic),
Claude writes it, builds the audio, and publishes it. Then they listen.

## The listener (who I'm writing for)

American; curious and well-read — does **not** need oversimplification. A
serious home cook with a deep love of Italian and Mediterranean food (very
relevant in Provence and Lyon). Cares about art — **Impressionism especially**
— and jazz. Getting around: TGV from Paris Gare de Lyon to Arles, then the
river cruise. Has been walking Paris (Saint-Germain-des-Prés, Le Marais)
thinking about royalty/aristocracy, the Revolution, and France's relationship
to the United States.

**Write FOR this listener, but do not AIM the episodes AT them.** These profile
details shape *what topics to choose and what to emphasize* — lean into food,
art, Impressionism, the France–US thread — but the episodes are published to a
public feed with other listeners. So **never address the listener's personal
interests in the second person.** Avoid lines like "given your love of jazz" or
"as a home cook, you'll…". Keep the narration written for a general, intelligent
audience; let the listener's interests guide selection and framing, not direct
address. (Physical "you are standing here / you'll see this at the next stop"
travel framing is still fine — that's about the place, not the person.)

## The angle

Local **history, politics, culture, and food** — always drawing **connections
between France and the United States** where they genuinely exist. The favorite
mode: a specific physical place (a market, a square, a mansion, a cathedral, an
amphitheater) becomes the doorway into a larger idea. Prize intellectual
through-lines that tie a physical place to a big idea. Love a good story — a
vivid historical episode (a duel, an execution, a festival, a papal conclave)
used to illuminate a bigger point. Weave history, politics, culture, and food
**together** rather than siloing them.

## Recurring themes (return to these across episodes, as relevant)

- **Legitimacy is downstream of belief** — authority holds only as long as
  people believe in it.
- **The absolutist project** of absorbing rival centers of power (the
  aristocracy, the Church, the regions) into the crown — and its long-term
  fragility.
- **France vs. America as two answers to the same Enlightenment question**:
  where does authority come from? Two revolutions, two outcomes.
- **French laïcité vs. American disestablishment** — two different settlements
  of the church-and-state question.
- **Centralized vs. distributed power** — Paris/Versailles/the crown vs.
  regions, provinces, and localities.
- **The fate of aristocracies** — how ruling classes rise, entrench, and fall.
- **The endurance of everyday life** — the humble daily fabric of a place
  (food, markets, ritual, craft) outlasts its kings and its revolutions.

## Tone & format

- A **flowing spoken-word essay meant to be heard, not read.** Narrative, warm,
  intellectually substantive but conversational. Paced for listening.
- **No bullet points, no headers, no lists** in the spoken body. Continuous
  prose. Avoid anything that only makes sense on a page (parentheticals with
  citations, "see above", numbered items).
- **Length: ~1,100–1,400 words** (~8–10 minutes narrated). Medium.
- Where natural, connect to **what the listener is physically seeing** at that
  stop, and to the **American parallel**.
- **Bring food in as a way into culture** — ingredients, dishes, culinary
  history — especially in Provence and Lyon.
- **Flag interpretation vs. settled fact.** When something is a reading or an
  argument rather than established history, say so in the narration ("the way I
  read it…", "historians disagree, but…").
- **Search for current or specific facts** (dates, names, what's on view, what a
  site currently looks like) rather than relying on memory. Verify before
  asserting specifics.
- Write for the **ear**: spell out things TTS mangles. Avoid symbols; write
  "and" not "&", "1789" is fine but write "the fourteenth of July" where it
  reads better aloud. Expand abbreviations. Keep sentences speakable. For
  **foreign words**, pronounce them right with SSML/IPA `<phoneme>` tags — see
  "Foreign-word pronunciation" under the writing conventions below.

## The route (episode ordering follows the trip)

Paris (pre-trip) → **TGV** Paris Gare de Lyon → **Arles** (embark; 2 days) →
**Avignon** → **Viviers** → **Tournon** → **Vienne** → **Lyon** (disembark).
Sailing **upriver, south to north.** Use **four-digit filename prefixes**
(`0000`–`9999`) to keep episodes in listening order, **spaced by ~100** so a new
episode can always be inserted between two existing ones without renumbering
(e.g. an episode that belongs between `0700` and `0800` becomes `0750`). Current
prefixes: Paris cluster `0200`–`0500`, TGV departure `0600`, Arles `0700`–`0900`,
Avignon `1000`–`1100`, then later stops from `1200` upward. `0100` is left free
for a Paris opener.

### Seeded episode ideas (write on request; not yet written)

- Paris/Enlightenment thread — Café Procope, Lafayette & Jefferson, the two
  revolutions (Saint-Germain / Le Marais tie-in).
- Arles as Roman Gaul — the amphitheater, Constantine, Provence's Roman founding.
- Van Gogh in Arles — the Post-Impressionist connection, art and place.
- The Avignon Papacy — popes on French soil (church-vs-state thread, direct).
- The Rhône as a trade and cultural artery.
- Lyon, capital of French gastronomy — plus its Roman and silk-weaving history.
- A dedicated food episode — how Provençal and Lyonnais cooking differ, and why.

## Technical workflow — how to create and publish an episode

Project root: `/Users/ardell/src/france_podcast/`

Episode files use a **four-digit prefix**, `NNNN-slug` (see "The route" above
for the numbering scheme: spaced by ~100 to allow mid-sequence inserts).

1. **Write the text** to `episodes/text/NNNN-slug.txt`. Begin the file with a
   metadata header delimited by `---` lines; the build script strips it before
   narration, so only the spoken body is read aloud:

   ```
   ---
   title: The City of Popes
   place: Avignon
   themes: church-vs-state, legitimacy
   words: ~1300
   ---
   <spoken body starts here — continuous prose, no headers or lists>
   ```

2. **Build the audio**: always
   `TTS=google BUMPER=1 bin/build.sh NNNN-slug` (or `... bin/build.sh` for all).

   **IMPORTANT — always pass `TTS=google BUMPER=1`.** The script's bare defaults
   (`TTS=say`, `BUMPER=0`) are WRONG for this podcast: they produce a robotic OS
   voice with no intro/outro. Every published episode uses the Google Chirp 3 HD
   voice (`en-US-Chirp3-HD-Aoede`, the default in `bin/tts_google.py`) AND the
   music-plus-spoken bumper (`bin/bumper.py`, `assets/bumper-music.mp3`). A bare
   `bin/build.sh` silently does neither — never build without both env vars.
   - Requires `GOOGLE_TTS_API_KEY` from `.envrc`. If direnv hasn't loaded it in
     the shell, prefix with `set -a; source .envrc; set +a &&`.
   - Google path chunks the text and stitches MP3s; then `BUMPER=1` wraps the
     narration with music + a spoken title greeting and outro.
   - The build **skips when the mp3 is newer than the text**, so to force a
     rebuild (e.g. after fixing a bad build) delete the stale outputs first:
     `rm -f episodes/audio/NNNN-slug.mp3 episodes/bodies/NNNN-slug.mp3`.
   - `episodes/bodies/NNNN-slug.mp3` is the un-bumpered narration, persisted so
     re-wrapping never doubles the bumper. Its presence confirms `BUMPER=1` ran.
   - **Bumper mastering (applies to NEW builds only; existing episodes were not
     re-rendered):** the bumper now uses podcast best-practice leveling — a
     gentle sidechain duck (slow attack/long release so the music doesn't pump),
     the music high-passed and kept clearly under the voice, slow multi-second
     fades, a beat of silence before the outro, an outro that samples the END of
     the track (fading in) so it lands on the song's natural ending, and a final
     normalize to -16 LUFS. The intro/outro voice lines are cached in
     `assets/.tts-cache/` so re-rendering for level tweaks doesn't re-bill TTS.
   - **Rendered audio is no longer tracked in git** (build artifact; hosted on
     Dropbox). Scripts are the source of truth — regenerate audio with
     `bin/build.sh`. The bumper music (`assets/bumper-music*.mp3`) IS tracked.

3. **Publish to Dropbox**: `bin/publish.sh NNNN-slug` (or `bin/publish.sh` for
   all). Copies mp3s to `~/Dropbox/France Podcast/` and regenerates an
   `.m3u` playlist in filename order. Dropbox syncs to the phone automatically.

4. **Publish to GitHub Pages** (the public RSS feed + episode pages):
   `bin/publish_feed.sh`. Regenerates `docs/feed.xml`, `docs/index.html`, and
   the per-episode pages, copies mp3s into `docs/episodes/`, then commits and
   pushes to `origin/main`. This is a separate publish path from Dropbox:
   `publish.sh` feeds the phone, `publish_feed.sh` feeds the public site at
   `https://ardell.github.io/france_podcast/feed.xml`.

**Git convention — commit directly to `main` for THIS repo only.** This
overrides the usual `jason/`-branch-per-change workflow: `bin/publish_feed.sh`
commits and pushes straight to `main`, and the repo's history follows suit. So
for france_podcast, commit and push to `main` directly rather than opening a
branch/PR.

Typical one-episode flow after writing the text (note the required env vars):
`TTS=google BUMPER=1 bin/build.sh 1000-city-of-popes && bin/publish.sh 1000-city-of-popes && bin/publish_feed.sh`

If you rename or renumber episodes, delete the old-named mp3s from
`~/Dropbox/France Podcast/` before republishing, so no stale files linger:
`rm -f ~/Dropbox/"France Podcast"/OLDPREFIX-*.mp3` then `bin/publish.sh`.

### TTS configuration

**The standard engine is Google Chirp 3 HD** — every episode uses it. Always
build with `TTS=google BUMPER=1` (see step 2 above); this is not optional.

    TTS=google BUMPER=1 bin/build.sh 1100-pont-du-gard

- Requires `GOOGLE_TTS_API_KEY` in the environment (the listener keeps it in
  `.envrc` via direnv; never commit it). It's a restricted Google Cloud API key
  scoped to the Text-to-Speech API.

The `say` engine (`TTS=say`, the script's built-in default) is a **fallback
only** — offline, robotic, and NOT what gets published. Its knobs, if ever
needed: `VOICE` (default **Daniel**, en_GB male; `Samantha` is the best en_US
alternative), `RATE` (**170** wpm), `BITRATE` (**128k**). Do not publish `say`
output.
- **Preferred voice: `en-US-Chirp3-HD-Aoede`** (female) — chosen by the listener
  from a 7-voice sample reel. This is the default in `bin/tts_google.py`.
  Override with `GOOGLE_TTS_VOICE` if needed (other candidates auditioned:
  Charon, Iapetus, Enceladus, Orus, Kore, Vindemiatrix). Speed via
  `GOOGLE_TTS_RATE` (default 1.0).
- `bin/tts_google.py` does the work: the v1 `text:synthesize` endpoint caps
  input at 5000 bytes, so it chunks each episode on paragraph/sentence bounds,
  synthesizes each chunk to MP3, and concatenates with ffmpeg. Output is MP3
  directly (no `say`/aiff step).
- Free tier ~1M characters/month; a full ~25-episode series (~195k chars) fits
  free. Google requires a billing account on file even for free-tier use.
- The `.txt` files and `bin/publish.sh` are unchanged regardless of engine.
- Other premium options considered and priced (not wired): OpenAI
  gpt-4o-mini-tts (~$0.12/episode), ElevenLabs (most human, ~$0.78/episode).
  Note: Anthropic/Claude has NO TTS API — the Claude app's read-aloud is just
  the OS voice, so it can't be used here.

### Writing conventions for the .txt body

- Continuous prose only. The header (between `---` lines) is the ONLY place for
  metadata; it is never spoken.
- Everything after the closing `---` is narrated verbatim, so it must be clean,
  speakable English with no stage directions or notes to self.

### Foreign-word pronunciation — SSML / IPA (use it; the trip is multilingual)

The Google engine (`TTS=google`) understands **IPA via SSML**, so foreign words
(French, Occitan, Italian, Catalan, Latin…) can be pronounced correctly instead
of guessed by the en-US model. Wrap the word in a `<phoneme>` tag with IPA:

    the <phoneme alphabet="ipa" ph="lɑ̃ɡ dɔk">langue d'oc</phoneme>

- **How it works:** `bin/tts_google.py` auto-detects SSML — if the body contains
  ANY SSML tag (`<phoneme>`, `<break>`, `<sub>`, `<say-as>`, `<prosody>`, …) the
  whole body is sent as SSML; otherwise it stays plain text. The build log prints
  `text` or `SSML/IPA` so you can confirm which path ran. Surrounding prose is
  XML-escaped automatically and each chunk is wrapped in `<speak>`. Plain-text
  episodes and the bumper greeting are unaffected. Chirp 3 HD supports SSML on
  synchronous requests (which is what we use); `<phoneme alphabet="ipa">` works.
- **`&`, `<`, `>` in an SSML body** are escaped for you, but still prefer writing
  "and" — the show is written for the ear regardless.
- **DEMONSTRATE contrasts, don't just describe them.** For a language episode,
  the point is to *hear* the difference. Instead of "a Parisian clips it and a
  southerner sings it," voice both: `<phoneme … ph="pɛ̃">pain</phoneme>` then
  `<phoneme … ph="ˈpɛ.ŋə">pain</phoneme>`. Same trick for Latin fracturing into
  its daughter languages, oc vs oïl, etc. The SSML support exists precisely so
  these A/B moments land in the audio.
- **Audition tricky IPA cheaply** before committing to a full rebuild: pipe a
  one-line SSML snippet straight through `python3 bin/tts_google.py out.mp3` and
  listen. (Loose `.mp3`s dropped into `~/Dropbox/France Podcast/` leak into the
  `.m3u` playlist — park audition clips in a subfolder like `_demos/` instead.)
- See `0675-tongues-of-the-south.txt` for a worked example (the French-vs-Occitan
  episode). IPA I author is a best-effort broad transcription — worth an ear-check.
