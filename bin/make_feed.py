#!/usr/bin/env python3
"""
make_feed.py — generate a podcast RSS feed (feed.xml) from the built episodes.

Reads every episodes/audio/*.mp3, pulls the human title from the matching
episodes/text/*.txt header (the `title:` field), computes file size and
duration, and writes docs/feed.xml plus copies the mp3s into docs/episodes/
so the whole thing can be served statically by GitHub Pages.

Episodes are ordered by their four-digit filename prefix (listening order).
pubDate is synthesized so that earlier-numbered episodes sort earlier in
podcast apps: we assign a fixed base date and space episodes one day apart in
filename order. (The trip order, not real publish time, is what we want.)

Config via env:
  FEED_BASE_URL   required for a real feed — the public base URL where the
                  docs/ folder is served, e.g.
                  https://ardell.github.io/france-podcast
  FEED_TITLE      default "Colors of Provence — A Traveler's Companion"
  FEED_AUTHOR     default "France Podcast"
  FEED_BASE_DATE  ISO date (YYYY-MM-DD) used as the pubDate anchor; default
                  2026-01-01. Episode N (by order) = base + N days.

Usage:
  FEED_BASE_URL=https://ardell.github.io/france-podcast bin/make_feed.py
"""

import glob
import os
import re
import shutil
import subprocess
import sys
from email.utils import formatdate
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT, "episodes", "audio")
TEXT_DIR = os.path.join(ROOT, "episodes", "text")
DOCS = os.path.join(ROOT, "docs")
DOCS_EP = os.path.join(DOCS, "episodes")

BASE_URL = os.environ.get("FEED_BASE_URL", "").rstrip("/")
FEED_TITLE = os.environ.get("FEED_TITLE", "Colors of Provence — A Traveler's Companion")
FEED_AUTHOR = os.environ.get("FEED_AUTHOR", "France Podcast")
FEED_DESC = os.environ.get(
    "FEED_DESC",
    "Short spoken-word essays on the history, politics, culture, and food of "
    "Paris, Provence, and the Rhône — a personal companion for the journey "
    "from Arles to Lyon.",
)
BASE_DATE = os.environ.get("FEED_BASE_DATE", "2026-01-01")

# --- Trip-based publication dates -------------------------------------------
# Each episode's pubDate is anchored to the day the listener arrives at the
# location the episode is about, at 6am Paris time. Episodes sharing a day are
# staggered a few minutes apart to preserve listening order in podcast apps.
# July 2026 is CEST (UTC+2), so 06:00 Paris == 04:00 UTC.
#
# Trip anchors: arrive Paris Jul 6; embark Arles Thu Jul 9 (cruise Day 1);
# then Arles Day 2 Jul 10, Avignon Jul 11, Viviers Jul 12, Tournon Jul 13,
# Vienne Jul 14, Lyon Jul 15 — all 2026.
PARIS_UTC_OFFSET_HOURS = 2  # CEST in July
TRIP_YEAR = 2026
# slug -> (month, day, minute-offset-after-06:00-Paris)
EPISODE_DATES = {
    # Paris cluster — arrival day, Jul 6
    "0200-cafe-two-revolutions": (7, 6, 0),
    "0250-parisian-food":        (7, 6, 2),
    "0300-guillotine-legitimacy":(7, 6, 4),
    "0275-julia-child":          (7, 8, 0),
    "0350-marie-curie":          (7, 7, 0),
    "0400-revolution-changed":   (7, 6, 6),
    "0500-laicite":              (7, 6, 8),
    # Arles Day 1 (Jul 9) — the TGV travel down, arrive Arles that day
    "0600-tgv":                  (7, 9, 0),
    "0650-the-midi":             (7, 9, 2),
    "0700-arles-as-rome":        (7, 9, 10),   # arrival day in Arles
    # Arles Day 2 (Jul 10) — exploring Van Gogh's Arles
    "0800-van-gogh-yellow":      (7, 10, 0),
    "0900-alyscamps":            (7, 10, 2),
    # Avignon (Jul 11)
    "1000-city-of-popes":        (7, 11, 0),
    "1100-pont-du-gard":         (7, 11, 2),
    # Viviers (Jul 12)
    "1200-rhone-highway":        (7, 12, 0),
    "1300-truffle-terroir":      (7, 12, 2),
    # Tournon (Jul 13)
    "1400-cotes-du-rhone":       (7, 13, 0),
    # Vienne (Jul 14)
    "1500-vienne-rome-jazz":     (7, 14, 0),
    # Lyon (Jul 15) — gastronomic capstone; food/wine thematic eps grouped here
    "1600-capital-of-eating":    (7, 15, 0),
    "1700-canuts":               (7, 15, 2),
    "1800-fourviere-two-hills":  (7, 15, 4),
    "1900-regional-cooking":     (7, 15, 6),
    "1950-wine-companion":       (7, 15, 8),
}


def episode_pubdate(slug, fallback_index):
    """Return an RFC-2822 pubDate string for an episode.

    Uses the trip-based EPISODE_DATES map (6am Paris time + stagger). Falls
    back to a spaced sequence off BASE_DATE for any slug not in the map, so
    new episodes still get sane ordering until added to the table.
    """
    if slug in EPISODE_DATES:
        mo, day, off = EPISODE_DATES[slug]
        # 06:00 Paris minus the UTC offset -> UTC hour; add stagger minutes.
        dt = datetime(TRIP_YEAR, mo, day, 6 - PARIS_UTC_OFFSET_HOURS, off,
                      tzinfo=timezone.utc)
        return formatdate(dt.timestamp(), usegmt=True)
    base = datetime.strptime(BASE_DATE, "%Y-%m-%d").replace(
        tzinfo=timezone.utc, hour=12)
    return formatdate((base + timedelta(days=fallback_index)).timestamp(),
                      usegmt=True)


def episode_display_date(slug):
    """Human-friendly date like 'Thursday, July 9, 2026' for the trip dates."""
    if slug not in EPISODE_DATES:
        return ""
    mo, day, _ = EPISODE_DATES[slug]
    dt = datetime(TRIP_YEAR, mo, day)
    return dt.strftime("%A, %B %-d, %Y")


def read_body(slug):
    """Return the spoken body of an episode as a list of paragraphs."""
    txt = os.path.join(TEXT_DIR, slug + ".txt")
    if not os.path.exists(txt):
        return []
    lines, in_hdr, seen_hdr = [], False, False
    with open(txt, encoding="utf-8") as fh:
        for line in fh:
            s = line.rstrip("\n")
            if s.strip() == "---":
                if not seen_hdr:
                    in_hdr = True
                    seen_hdr = True
                    continue
                if in_hdr:
                    in_hdr = False
                    continue
            if in_hdr:
                continue
            lines.append(s)
    text = "\n".join(lines).strip()
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def episode_excerpt(slug, limit=320):
    """A short plain-text excerpt from the start of the transcript, cut on a
    sentence boundary near `limit` characters, with an ellipsis."""
    paras = read_body(slug)
    if not paras:
        return ""
    text = " ".join(paras)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer to end at the last sentence break; else the last word.
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if end >= limit * 0.5:
        return cut[:end + 1]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > 0 else cut).rstrip() + "…"


def read_title(slug):
    """Pull `title:` from the episode's text header; fall back to the slug."""
    txt = os.path.join(TEXT_DIR, slug + ".txt")
    if os.path.exists(txt):
        with open(txt, encoding="utf-8") as fh:
            in_hdr = False
            for line in fh:
                s = line.strip()
                if s == "---":
                    in_hdr = not in_hdr
                    if not in_hdr:
                        break
                    continue
                if in_hdr and s.lower().startswith("title:"):
                    return s.split(":", 1)[1].strip()
    # fallback: prettify slug (drop numeric prefix)
    name = re.sub(r"^\d+-", "", slug).replace("-", " ")
    return name.title()


def read_field(slug, field):
    """Read an arbitrary header field (e.g. 'place') from an episode's text."""
    txt = os.path.join(TEXT_DIR, slug + ".txt")
    if not os.path.exists(txt):
        return ""
    with open(txt, encoding="utf-8") as fh:
        in_hdr = False
        for line in fh:
            s = line.strip()
            if s == "---":
                in_hdr = not in_hdr
                if not in_hdr:
                    break
                continue
            if in_hdr and s.lower().startswith(field.lower() + ":"):
                return s.split(":", 1)[1].strip()
    return ""


def duration_seconds(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return int(float(out))


def hhmmss(secs):
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return (f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}")


def write_landing_page(episodes, feed_url, cover_url):
    """Generate docs/index.html — a friendly, styled subscribe page."""
    # podcast:// deep link opens Apple Podcasts straight to add-by-URL on iOS.
    feed_bare = re.sub(r"^https?://", "", feed_url)
    apple_deep = "podcast://" + feed_bare

    ep_rows = "\n".join(
        f"""        <li class="ep">
          <span class="ep-n">{e['n']:02d}</span>
          <div class="ep-body">
            <div class="ep-title"><a href="episodes/{escape(e['slug'])}.html">{escape(e['title'])}</a></div>
            <div class="ep-meta">{escape(e['place'])} &middot; {e['dur']}
              &middot; <a href="episodes/{escape(e['slug'])}.html">Read transcript</a></div>
          </div>
          <audio class="ep-audio" preload="none" controls src="{escape(e['url'])}"></audio>
        </li>""" for e in episodes)

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(FEED_TITLE)}</title>
<meta name="description" content="{escape(FEED_DESC)}">
<meta property="og:title" content="{escape(FEED_TITLE)}">
<meta property="og:description" content="{escape(FEED_DESC)}">
<meta property="og:image" content="{escape(cover_url)}">
<meta property="og:type" content="website">
<style>
  :root {{
    --night: #10163a; --night-2: #1c2550; --gold: #e8b04b; --gold-2: #f4d98a;
    --cream: #fdf6e3; --water: #3a5a80; --ink: #1a1a20; --muted: #6b6f7a;
    --card: #ffffff; --bg: #f4f0e6; --border: #e4ddca;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --card:#171a2b; --bg:#0d1020; --ink:#ede8dc; --muted:#9aa0b0; --border:#28304f; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: Georgia, 'Times New Roman', serif; line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}
  .hero {{
    position: relative; color: var(--cream); text-align: center;
    padding: 0; overflow: hidden;
    background: linear-gradient(180deg, var(--night) 0%, var(--night-2) 100%);
  }}
  .hero-inner {{ padding: 4rem 1.5rem 3.5rem; max-width: 760px; margin: 0 auto; }}
  .cover {{
    width: 240px; height: 240px; border-radius: 12px; margin: 0 auto 1.75rem;
    display: block; box-shadow: 0 12px 40px rgba(0,0,0,.5);
  }}
  .hero h1 {{ font-size: 2.5rem; margin: 0 0 .4rem; letter-spacing: .5px; }}
  .hero .tag {{ font-style: italic; font-size: 1.2rem; opacity: .92; margin: 0 0 .3rem; }}
  .hero .route {{ font-size: .85rem; letter-spacing: 3px; opacity: .8; text-transform: uppercase; }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem; }}
  .lede {{ font-size: 1.12rem; color: var(--ink); margin: 0 0 2rem; }}
  .subscribe {{
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 1.6rem 1.5rem; margin: 0 0 2.5rem; box-shadow: 0 4px 18px rgba(0,0,0,.06);
  }}
  .subscribe h2 {{ margin: 0 0 1rem; font-size: 1.3rem; }}
  .btn {{
    display: inline-flex; align-items: center; gap: .5rem; text-decoration: none;
    background: var(--gold); color: #2a1e00; font-weight: bold; font-family: inherit;
    padding: .8rem 1.3rem; border-radius: 999px; margin: 0 .5rem .6rem 0;
    border: none; cursor: pointer; font-size: 1rem; transition: transform .08s ease;
  }}
  .btn:hover {{ transform: translateY(-1px); }}
  .btn.secondary {{ background: transparent; color: var(--ink); border: 1.5px solid var(--border); }}
  .urlbox {{
    display: flex; gap: .5rem; margin-top: 1rem; flex-wrap: wrap;
  }}
  .urlbox input {{
    flex: 1 1 260px; font-family: ui-monospace, Menlo, monospace; font-size: .85rem;
    padding: .7rem .8rem; border: 1px solid var(--border); border-radius: 8px;
    background: var(--bg); color: var(--ink);
  }}
  .hint {{ font-size: .85rem; color: var(--muted); margin: .8rem 0 0; }}
  h2.section {{ font-size: 1.4rem; margin: 0 0 1rem; }}
  ol.eps {{ list-style: none; padding: 0; margin: 0; }}
  .ep {{
    display: grid; grid-template-columns: auto 1fr; gap: .3rem 1rem;
    align-items: center; padding: 1rem 0; border-top: 1px solid var(--border);
  }}
  .ep-n {{ font-size: 1.5rem; color: var(--gold); font-weight: bold; grid-row: span 2; }}
  .ep-title {{ font-weight: bold; }}
  .ep-title a {{ color: var(--ink); text-decoration: none; }}
  .ep-title a:hover {{ color: var(--gold); }}
  .ep-meta {{ font-size: .85rem; color: var(--muted); }}
  .ep-meta a {{ color: var(--gold); text-decoration: none; }}
  .ep-meta a:hover {{ text-decoration: underline; }}
  .ep-audio {{ grid-column: 1 / -1; width: 100%; margin-top: .5rem; height: 34px; }}
  footer {{ text-align: center; color: var(--muted); font-size: .8rem; padding: 2rem 1.5rem 3rem; }}
  @media (max-width: 520px) {{ .hero h1 {{ font-size: 2rem; }} .cover {{ width: 200px; height: 200px; }} }}
</style>
</head>
<body>
  <header class="hero">
    <div class="hero-inner">
      <img class="cover" src="{escape(cover_url)}" alt="{escape(FEED_TITLE)} cover art">
      <h1>{escape(FEED_TITLE.split('—')[0].strip())}</h1>
      <p class="tag">A Traveler's Companion</p>
      <p class="route">Paris &middot; Arles &middot; Avignon &middot; Lyon</p>
    </div>
  </header>

  <main class="wrap">
    <p class="lede">{escape(FEED_DESC)}</p>

    <section class="subscribe">
      <h2>Listen &amp; subscribe</h2>
      <a class="btn" href="{escape(apple_deep)}">&#63743; Open in Apple Podcasts</a>
      <a class="btn secondary" href="https://overcast.fm/">Overcast</a>
      <a class="btn secondary" href="https://pca.st/">Pocket Casts</a>
      <div class="urlbox">
        <input id="feedurl" type="text" readonly value="{escape(feed_url)}">
        <button class="btn" onclick="copyFeed()">Copy feed URL</button>
      </div>
      <p class="hint">In any podcast app, choose &ldquo;Add a show by URL&rdquo; and paste the feed link.
        On iPhone, the Apple Podcasts button opens the app directly.</p>
    </section>

    <h2 class="section">Episodes</h2>
    <ol class="eps">
{ep_rows}
    </ol>
  </main>

  <footer>Made with care for the journey. &middot; <a href="{escape(feed_url)}">RSS feed</a><br>
    Intro and outro music: &ldquo;Gypsy Jazz Coffee Shop&rdquo; by Alex-Productions, via Pixabay.</footer>

  <script>
    function copyFeed() {{
      var el = document.getElementById('feedurl');
      el.select(); el.setSelectionRange(0, 99999);
      navigator.clipboard.writeText(el.value).then(function() {{
        var b = event.target; var t = b.textContent;
        b.textContent = 'Copied \\u2713';
        setTimeout(function(){{ b.textContent = t; }}, 1600);
      }});
    }}
  </script>
</body>
</html>
"""
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html)


def write_episode_page(ep, cover_url):
    """Generate docs/episodes/<slug>.html — episode page with full transcript."""
    paras = read_body(ep["slug"])
    transcript = "\n".join(
        f"        <p>{escape(p)}</p>" for p in paras
    ) or "        <p><em>Transcript coming soon.</em></p>"
    meta_bits = " &middot; ".join(
        b for b in [escape(ep["place"]), ep.get("date", ""), ep["dur"]] if b)

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(ep['title'])} — {escape(FEED_TITLE)}</title>
<meta name="description" content="Transcript and audio: {escape(ep['title'])}.">
<meta property="og:title" content="{escape(ep['title'])}">
<meta property="og:description" content="{escape(FEED_TITLE)}">
<meta property="og:image" content="{escape(cover_url)}">
<style>
  :root {{
    --night:#10163a; --gold:#e8b04b; --cream:#fdf6e3; --ink:#1a1a20;
    --muted:#6b6f7a; --card:#ffffff; --bg:#f4f0e6; --border:#e4ddca;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --card:#171a2b; --bg:#0d1020; --ink:#ede8dc; --muted:#9aa0b0; --border:#28304f; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:Georgia,'Times New Roman',serif; line-height:1.75;
    -webkit-font-smoothing:antialiased; }}
  .top {{ background:linear-gradient(180deg,var(--night),#1c2550); color:var(--cream);
    padding:2.5rem 1.5rem; }}
  .top-inner {{ max-width:720px; margin:0 auto; display:flex; gap:1.25rem; align-items:center; }}
  .top img {{ width:96px; height:96px; border-radius:10px; box-shadow:0 6px 20px rgba(0,0,0,.4); }}
  .back {{ color:var(--gold); text-decoration:none; font-size:.85rem; letter-spacing:1px;
    text-transform:uppercase; display:inline-block; margin-bottom:.6rem; }}
  .top h1 {{ margin:.1rem 0 .3rem; font-size:1.7rem; line-height:1.2; }}
  .top .meta {{ font-size:.85rem; opacity:.85; }}
  main {{ max-width:720px; margin:0 auto; padding:2rem 1.5rem 4rem; }}
  audio {{ width:100%; margin:0 0 2rem; }}
  .transcript p {{ margin:0 0 1.15rem; font-size:1.08rem; }}
  .transcript p:first-child::first-letter {{
    font-size:3.1rem; font-weight:bold; float:left; line-height:.8;
    padding:.05em .08em 0 0; color:var(--gold); }}
  footer {{ text-align:center; color:var(--muted); font-size:.8rem;
    padding:1rem 1.5rem 3rem; max-width:720px; margin:0 auto; }}
  footer a {{ color:var(--muted); }}
</style>
</head>
<body>
  <header class="top">
    <div class="top-inner">
      <img src="../{escape(os.path.basename(cover_url))}" alt="cover">
      <div>
        <a class="back" href="../index.html">&larr; All episodes</a>
        <h1>{escape(ep['title'])}</h1>
        <div class="meta">{meta_bits}</div>
      </div>
    </div>
  </header>
  <main>
    <audio preload="none" controls src="{escape(ep['slug'])}.mp3"></audio>
    <div class="transcript">
{transcript}
    </div>
  </main>
  <footer>
    <a href="../index.html">Colors of Provence</a> &middot;
    Music: &ldquo;Gypsy Jazz Coffee Shop&rdquo; by Alex-Productions, via Pixabay.
  </footer>
</body>
</html>
"""
    with open(os.path.join(DOCS_EP, ep["slug"] + ".html"), "w",
              encoding="utf-8") as fh:
        fh.write(html)


def main():
    if not BASE_URL:
        print("WARNING: FEED_BASE_URL not set — item/enclosure URLs will be "
              "relative and the feed will NOT work in a podcast app until you "
              "set it and regenerate.", file=sys.stderr)

    mp3s = sorted(glob.glob(os.path.join(AUDIO_DIR, "*.mp3")))
    if not mp3s:
        sys.exit("No episodes in episodes/audio/ — build some first.")

    os.makedirs(DOCS_EP, exist_ok=True)

    base_dt = datetime.strptime(BASE_DATE, "%Y-%m-%d").replace(
        tzinfo=timezone.utc, hour=12)

    items = []
    episodes = []  # for the HTML landing page
    for i, mp3 in enumerate(mp3s):
        slug = os.path.splitext(os.path.basename(mp3))[0]
        title = read_title(slug)
        place = read_field(slug, "place")
        size = os.path.getsize(mp3)
        dur = duration_seconds(mp3)
        # copy audio into docs/episodes/ for static hosting
        shutil.copy2(mp3, os.path.join(DOCS_EP, slug + ".mp3"))
        # pubDate: anchored to arrival at the episode's location, 6am Paris
        pub_rfc = episode_pubdate(slug, i)
        ep_url = f"{BASE_URL}/episodes/{slug}.mp3" if BASE_URL else f"episodes/{slug}.mp3"
        page_url = f"{BASE_URL}/episodes/{slug}.html" if BASE_URL else f"episodes/{slug}.html"
        guid = ep_url if BASE_URL else slug
        excerpt = episode_excerpt(slug)
        # Description: transcript excerpt plus a link to the full transcript page.
        desc = excerpt
        if page_url and excerpt:
            desc = f"{excerpt}\n\nFull transcript: {page_url}"
        items.append(f"""    <item>
      <title>{escape(title)}</title>
      <itunes:title>{escape(title)}</itunes:title>
      <guid isPermaLink="false">{escape(guid)}</guid>
      <link>{escape(page_url)}</link>
      <pubDate>{pub_rfc}</pubDate>
      <description>{escape(desc)}</description>
      <itunes:summary>{escape(desc)}</itunes:summary>
      <enclosure url="{escape(ep_url)}" length="{size}" type="audio/mpeg"/>
      <itunes:duration>{hhmmss(dur)}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
        episodes.append({"title": title, "place": place, "slug": slug,
                         "date": episode_display_date(slug),
                         "dur": hhmmss(dur), "url": ep_url, "n": i + 1})

    self_link = f"{BASE_URL}/feed.xml" if BASE_URL else "feed.xml"
    # Artwork filename is versioned: Apple Podcasts caches cover art per-URL
    # very aggressively, so bumping the filename forces a fresh fetch when the
    # image changes. Override with FEED_COVER if needed.
    cover_file = os.environ.get("FEED_COVER", "cover-v3.jpg")
    cover = f"{BASE_URL}/{cover_file}" if BASE_URL else cover_file
    now_rfc = formatdate(base_dt.timestamp(), usegmt=True)

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escape(FEED_TITLE)}</title>
    <link>{escape(BASE_URL or 'https://example.com')}</link>
    <language>en-us</language>
    <description>{escape(FEED_DESC)}</description>
    <itunes:author>{escape(FEED_AUTHOR)}</itunes:author>
    <itunes:summary>{escape(FEED_DESC)}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="Society &amp; Culture"/>
    <itunes:image href="{escape(cover)}"/>
    <image>
      <url>{escape(cover)}</url>
      <title>{escape(FEED_TITLE)}</title>
      <link>{escape(BASE_URL or 'https://example.com')}</link>
    </image>
    <atom:link href="{escape(self_link)}" rel="self" type="application/rss+xml"/>
    <lastBuildDate>{now_rfc}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""
    with open(os.path.join(DOCS, "feed.xml"), "w", encoding="utf-8") as fh:
        fh.write(feed)

    write_landing_page(episodes, self_link, cover)
    for ep in episodes:
        write_episode_page(ep, cover)

    print(f"Wrote docs/feed.xml with {len(items)} episode(s).")
    print(f"Wrote docs/index.html (subscribe page).")
    print(f"Wrote {len(episodes)} episode transcript page(s).")
    print(f"Copied {len(items)} mp3(s) into docs/episodes/.")
    if BASE_URL:
        print(f"Feed URL: {self_link}")
    else:
        print("Set FEED_BASE_URL and re-run to make the feed subscribable.")


if __name__ == "__main__":
    main()
