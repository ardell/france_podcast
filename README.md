# France Podcast — Colors of Provence

Personal spoken-word audio essays for a trip through Paris, Provence, and the
Rhône (Arles → Lyon). Text scripts are written one at a time, narrated via
text-to-speech, and published as a podcast RSS feed hosted on GitHub Pages.

- **Feed:** https://ardell.github.io/france_podcast/feed.xml
- **Episodes & workflow:** see `CLAUDE.md`
- **Ideas backlog:** see `IDEAS.md`

## Quick commands

```bash
# render one episode with the preferred voice (Google Chirp 3 HD, Aoede)
TTS=google bin/build.sh 0900-alyscamps

# publish everything: copy to Dropbox, regenerate feed, push to GitHub Pages
bin/publish.sh
bin/publish_feed.sh
```
