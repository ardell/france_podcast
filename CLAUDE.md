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
  reads better aloud. Expand abbreviations. Keep sentences speakable.

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

2. **Build the audio**: `bin/build.sh NNNN-slug` (or `bin/build.sh` for all).
   Pipeline: `say` → `.aiff` → `ffmpeg` → `episodes/audio/NNNN-slug.mp3`.
   Only rebuilds when the text is newer than the mp3.

3. **Publish to Dropbox**: `bin/publish.sh NNNN-slug` (or `bin/publish.sh` for
   all). Copies mp3s to `~/Dropbox/France Podcast/` and regenerates an
   `.m3u` playlist in filename order. Dropbox syncs to the phone automatically.

Typical one-episode flow after writing the text:
`bin/build.sh 1000-city-of-popes && bin/publish.sh 1000-city-of-popes`

If you rename or renumber episodes, delete the old-named mp3s from
`~/Dropbox/France Podcast/` before republishing, so no stale files linger:
`rm -f ~/Dropbox/"France Podcast"/OLDPREFIX-*.mp3` then `bin/publish.sh`.

### TTS configuration

- Voice/rate/bitrate are environment variables read by `bin/build.sh`:
  `VOICE` (default **Daniel**, a warm en_GB male — the best built-in for this
  narration), `RATE` (default **170** wpm), `BITRATE` (default **128k**).
- `Samantha` (en_US) is the best American built-in alternative.

**Premium voice — Google Chirp 3 HD (chosen upgrade path).** Set `TTS=google`
on `bin/build.sh` to use Google Cloud Text-to-Speech instead of `say`:

    TTS=google bin/build.sh 1100-pont-du-gard

- Requires `GOOGLE_TTS_API_KEY` in the environment (the listener keeps it in
  `.envrc` via direnv; never commit it). It's a restricted Google Cloud API key
  scoped to the Text-to-Speech API.
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
