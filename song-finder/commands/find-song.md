---
description: Find songs and build a playlist from singers (primary), mood, language, genre, and era — with a few similar-artist discoveries based on your taste.
argument-hint: <brief, e.g. "sad Arijit Singh type songs, Hindi, rainy night — 15 tracks">
allowed-tools: WebSearch, WebFetch, Bash, Read, Write, Glob
---

## Goal
Find, verify, and curate **songs matching the user's request** — built around their
seed singers, filtered by mood/language/genre/era, with a clearly-separated
"you might also like" layer of similar-artist tracks — and deliver a playlist
page with 30-second previews.

User request: **$ARGUMENTS**

## Use the song-search methodology
Follow the full workflow defined in the `song-search` skill. In brief:

1. **Clarify the brief.** From "$ARGUMENTS" extract: seed singers (primary),
   mood/occasion, language(s) (hard filter), genre, era, song count (default 15),
   discovery appetite (similar-artist tracks ≤ ⅓ by default), clean-only, any
   must-include/exclude songs, and their **queue preference** (YouTube / YouTube
   Music / Spotify / Apple Music). Ask **one** concise round of questions only if
   you have neither a singer nor a mood/language; otherwise state your assumptions.

2. **Pick the storefront** by language (`--country IN` for Hindi/Punjabi/Tamil…,
   `KR` for Korean, `US`/`GB` for English — table in the skill).

3. **Gather candidates** into `songs.json` (merged + deduped):
   ```bash
   # each seed singer's popular originals (remixes auto-dropped)
   python "${CLAUDE_PLUGIN_ROOT}/scripts/music.py" top --artist "<singer>" \
     --country <CC> --limit 15 --output songs.json --append

   # mood research: WebSearch curated lists, then VERIFY every title in the catalog
   python "${CLAUDE_PLUGIN_ROOT}/scripts/music.py" search --query "<title or mood terms>" \
     --country <CC> --output songs.json --append

   # taste expansion (secondary): similar artists + signature tracks
   python "${CLAUDE_PLUGIN_ROOT}/scripts/music.py" similar --artist "<singer>" \
     --limit 8 --with-top 2 --country <CC>
   ```

4. **Curate** the final list: language is hard, mood fit first, seed singers anchor
   the list, originals over remixes, variety across albums/years. Set each pick's
   `section` ("From your singers" / "Mood matches" / "You might also like") and a
   one-line `note` saying why it fits *this* brief.

5. **Queue it** (per the user's service preference, before the final render):
   ```bash
   # YouTube / YT Music: one-click watch_videos queue; --save enables the
   # "Play all" button and direct video links in the playlist HTML
   python "${CLAUDE_PLUGIN_ROOT}/scripts/queue.py" --input songs.json \
     --service youtube --save songs.json

   # Spotify / Apple Music: no key-less queue API - export the tracklist and
   # relay the printed TuneMyMusic/Soundiiz one-paste import steps
   python "${CLAUDE_PLUGIN_ROOT}/scripts/queue.py" --input songs.json --service spotify
   ```
   Spot-check a couple of resolved videos (top result can be a cover) and fix any
   miss by editing that song's `youtube_id`.

6. **Present.** A table per section (song · artist · year · genre · duration ·
   link), then the interactive playlist:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/playlist.py" --input songs.json \
     --title "<playlist name>" --output playlist.html --open
   ```

## Output rules
- **Never invent a song** — every track must come from a `music.py` catalog hit or a
  citable source, with the correct artist attribution.
- **Language is a hard filter**; mood labels are judgment calls — say so and offer swaps.
- Similar-artist tracks stay **clearly separated** ("You might also like") and capped
  at ~⅓ unless the user wants more discovery.
- Previews are 30-second clips; link YouTube/Spotify/JioSaavn equally for full songs.
- **Queueing honesty** — only YouTube gets a true one-click queue; for Spotify/Apple
  Music give the import flow, never claim something was "queued" in their account.
