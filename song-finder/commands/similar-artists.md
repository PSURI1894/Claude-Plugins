---
description: Map a singer's taste neighborhood — similar artists from real listener data, with a signature track each.
argument-hint: <1-3 singers, e.g. "Arijit Singh, Kishore Kumar">
allowed-tools: WebSearch, Bash, Read, Write, Glob
---

## Goal
Given 1–3 seed singers, show **who else the user is likely to enjoy** — similar
artists ranked by real ListenBrainz listener overlap, each with a signature track —
so they can expand their taste before (or instead of) building a full playlist.

Seed singers: **$ARGUMENTS**

## Steps

1. **Parse the seeds** from "$ARGUMENTS" (split on commas/"and"). If a name is
   ambiguous (e.g. just "KK"), confirm via the MusicBrainz disambiguation the
   script prints rather than guessing.

2. **Pull the neighborhood for each seed** (pick `--country` by the seed's main
   language — `IN` for Indian artists, `US` default):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/music.py" similar --artist "<singer>" \
     --limit 10 --with-top 2 --country <CC>
   ```

3. **Sanity-check** the results against what you know — listener data can skew
   Western; drop anything that's plainly a bad fit and say you did.

4. **Present per seed:** a table — similar artist · similarity score · signature
   track (year) · one-line "why you'd like them" grounded in actual style overlap
   (era, language, vocal style, film vs indie).

5. **If 2–3 seeds were given,** call out artists that appear in *multiple*
   neighborhoods first — those are the strongest taste matches.

6. **Offer the next step:** building a playlist from any of these via
   `/song-finder:find-song`.

## Output rules
- Similarity scores come from listener co-listening data — present them as
  "people who listen to X also listen to Y", not as objective ranking.
- Signature tracks must be real catalog hits from the script output — never
  invented, never misattributed.
- Stay neutral across platforms; the playlist links cover YouTube/Spotify/JioSaavn.
