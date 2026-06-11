---
name: song-search
description: Find and curate songs into a playlist from singers (the primary input), mood, language, genre, era, and occasion — plus a few similar-artist discoveries matched to the user's taste. Use whenever the user wants song recommendations, a playlist, music for a mood/occasion, songs by a singer, or "songs like X / artists like Y". Real metadata and 30-second previews from the key-less iTunes catalog; similar artists from MusicBrainz + ListenBrainz listener data.
allowed-tools: WebSearch, WebFetch, Bash, Read, Write, Glob
---

# Song Search & Playlist Curation

A repeatable methodology for turning a fuzzy music request ("sad Arijit Singh type
songs for a rainy night") into a verified, curated playlist — every track confirmed
to exist via the iTunes catalog, with 30-second previews and links to full songs.

## When to use
Trigger this when the user wants **song recommendations, a playlist, or music
discovery** driven by any mix of: singers (primary), mood, language, genre, era,
occasion, or energy. If they only want the artist landscape ("who sounds like
Kishore Kumar?"), the `/similar-artists` command is the faster path.

---

## Step 1 — Turn the request into a structured brief
Extract these fields (ask **one** concise round of questions only if you have
*neither* a singer *nor* a mood/language to work from):

| Field | Examples | Notes |
|---|---|---|
| Seed singers | Arijit Singh; Diljit Dosanjh + AP Dhillon | **Primary input** — the playlist is built around them |
| Mood / occasion | sad, romantic, party, workout, road trip, wedding, focus | Drives curation and web research |
| Language(s) | Hindi, Punjabi, English, Korean, Tamil | **Hard filter** — never slip in another language silently |
| Genre | Bollywood, indie pop, punk, ghazal, lo-fi | Soft filter (`--genre`) |
| Era | 90s, 2010s, "new stuff only", Kishore-era classics | Becomes `--year-from/--year-to` |
| Count | "a few", 15, 25 | Default **15** songs |
| Discovery appetite | "only my singers" ↔ "surprise me" | Similar-artist tracks capped at **~⅓** of the list by default |
| Clean-only | family setting, kids in the car | Becomes `--clean` |
| Include / exclude | "must have Tum Hi Ho", "no remixes" | Honor exactly; remixes are excluded by default |

Echo the brief back in one line before researching, so the user can correct it.

---

## Step 2 — Pick the catalog storefront
The iTunes API is per-country; the storefront biases what surfaces, so match it
to the target language (`--country`):

| Language | `--country` | | Language | `--country` |
|---|---|---|---|---|
| Hindi / Punjabi / Tamil / Telugu / Bengali | `IN` | | Korean | `KR` |
| English | `US` (or `GB` for UK acts) | | Japanese | `JP` |
| Spanish | `MX` or `ES` | | French | `FR` |
| Portuguese | `BR` | | Arabic | `AE` |

The storefront is a *bias*, not a language filter — still verify each track's
language yourself (you know most songs; WebSearch the ones you don't).

---

## Step 3 — Gather candidates into one pool
Build `songs.json` from three sources (all merge + dedupe via `--append`):

**a. Seed singers (primary).** Pull each seed's popular originals
(remixes/sped-up/vocals-only edits are dropped by default):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/music.py" top --artist "Arijit Singh" \
  --country IN --limit 15 --output songs.json --append
```

**b. Mood research (the curation fuel).** WebSearch curated lists matching the
brief — `best <mood> <language> songs <era>`, `<singer> <mood> songs list`,
`<occasion> playlist <language>` — and collect candidate titles. Then **verify
every candidate** through the catalog before it can be recommended:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/music.py" search --query "Channa Mereya" \
  --country IN --limit 5 --output songs.json --append
```

A song that can't be found in the catalog or confirmed by a citable source
**does not go on the playlist** — this is the anti-hallucination rule.

Mood → search vocabulary that works well:
- *sad / heartbreak* → "sad", "breakup", "dard", "judaai" · *romantic* → "love",
  "romantic hits", "shaadi first dance"
- *party / dance* → "party anthems", "dance hits", "bhangra" · *workout* →
  "gym motivation", "high energy"
- *chill / focus* → "acoustic", "unplugged", "late night", "study" · *road trip* →
  "driving songs", "highway playlist"
- *devotional / festive* → "bhajan", "sufi", "garba", "Christmas"

**c. Similar artists (secondary — the "based on your taste" layer).** Expand each
seed's neighborhood and take 1–2 signature tracks per related artist:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/music.py" similar --artist "Arijit Singh" \
  --limit 8 --with-top 2 --country IN
```

Similarity scores come from real ListenBrainz listener overlap. Keep these to
**~⅓ of the final list** unless the user asked to discover more (or fewer).

---

## Step 4 — Curate the final list
Select the final N from the pool, in this priority order:

1. **Language** — hard filter; drop anything in the wrong language.
2. **Mood fit** — the song must actually match the mood, not just the artist.
   Use your own knowledge + the web research; this is judgment, apply it openly.
3. **Seed singers first** — they anchor the list; similar-artist tracks are the
   garnish, clearly separated.
4. **Originals over derivatives** — no remixes/lofi/sped-up unless asked
   (`is_derivative` already guards `top`; check `search` results yourself).
5. **Variety** — spread across albums/years; avoid three songs from one film.

Then annotate each pick in the JSON:
- `section`: `"From your singers"` · `"Mood matches"` · `"You might also like"`
- `note`: one honest line on *why this song fits this brief* (not generic praise).

---

## Step 5 — Present
Lead with a compact table per section:

| # | Song | Artist | Year | Genre | ⏱ | Listen |
|---|------|--------|------|-------|---|--------|

Then render the interactive playlist (cover art, 30-sec previews, YouTube /
Spotify / JioSaavn links per song):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/playlist.py" --input songs.json \
  --title "Rainy-night Arijit" --output playlist.html --open
```

Close with: which similar artists were surfaced and why (one line each), and
anything the user asked for that couldn't be verified in the catalog.

---

## Guardrails
- **Never invent songs** — every recommendation must come from a `music.py` hit
  or a citable web source. Never attribute a song to the wrong singer.
- **Language is hard** — a wrong-language track never makes the list, even if
  the artist matches.
- **Mood tags are judgment calls** — say so; offer to swap any track.
- **Previews are 30-second clips** — full songs are on the linked services; don't
  imply otherwise.
- **Storefront ≠ availability everywhere** — metadata and previews vary by
  country; a missing preview doesn't mean the song doesn't exist.
- **ListenBrainz similarity reflects its listeners** — it can skew Western/scrobbler
  demographics; sanity-check suggestions against what you know before presenting.
- **Respect MusicBrainz** — the script throttles to its 1 request/sec policy;
  don't loop beyond what's needed.
- **Stay neutral** — link YouTube, Spotify, and JioSaavn equally; no platform
  favoritism.
