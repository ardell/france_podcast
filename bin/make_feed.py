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
    for i, mp3 in enumerate(mp3s):
        slug = os.path.splitext(os.path.basename(mp3))[0]
        title = read_title(slug)
        size = os.path.getsize(mp3)
        dur = duration_seconds(mp3)
        # copy audio into docs/episodes/ for static hosting
        shutil.copy2(mp3, os.path.join(DOCS_EP, slug + ".mp3"))
        # pubDate: base + i days, so filename order == podcast order
        pub = base_dt + timedelta(days=i)
        pub_rfc = formatdate(pub.timestamp(), usegmt=True)
        ep_url = f"{BASE_URL}/episodes/{slug}.mp3" if BASE_URL else f"episodes/{slug}.mp3"
        guid = ep_url if BASE_URL else slug
        items.append(f"""    <item>
      <title>{escape(title)}</title>
      <itunes:title>{escape(title)}</itunes:title>
      <guid isPermaLink="false">{escape(guid)}</guid>
      <pubDate>{pub_rfc}</pubDate>
      <enclosure url="{escape(ep_url)}" length="{size}" type="audio/mpeg"/>
      <itunes:duration>{hhmmss(dur)}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")

    self_link = f"{BASE_URL}/feed.xml" if BASE_URL else "feed.xml"
    cover = f"{BASE_URL}/cover.jpg" if BASE_URL else "cover.jpg"
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

    print(f"Wrote docs/feed.xml with {len(items)} episode(s).")
    print(f"Copied {len(items)} mp3(s) into docs/episodes/.")
    if BASE_URL:
        print(f"Feed URL: {self_link}")
    else:
        print("Set FEED_BASE_URL and re-run to make the feed subscribable.")


if __name__ == "__main__":
    main()
