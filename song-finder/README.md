# song-finder

A Claude Code plugin that finds songs and builds **verified playlists** from the
singers you name (the primary input), plus mood, language, genre, era, and occasion —
and layers in a few **similar-artist discoveries** matched to your taste (clearly
separated, never the main course).

Everything is **free and key-less**: song metadata and 30-second previews come from
the iTunes Search API (per-country storefronts, so Hindi/Punjabi/Tamil/K-pop all
resolve properly), and similar artists come from MusicBrainz + ListenBrainz real
listener-overlap data. The anti-hallucination rule: **a song that can't be verified
in the catalog never makes the playlist.**

## What you get

| Component | Name | Purpose |
|---|---|---|
| Command | `/song-finder:find-song <brief>` | Full flow: brief → gather from your singers + mood research + similar artists → curate → playlist page. |
| Command | `/song-finder:similar-artists <singers>` | Just the taste map: who else you'd like, ranked by listener overlap, with a signature track each. |
| Skill | `song-search` | Auto-triggers in normal conversation about songs/playlists/music; holds the full methodology. |
| Script | `scripts/music.py` | `search`: catalog search with genre/year/clean filters. `top`: an artist's popular originals (remixes auto-dropped). `similar`: MusicBrainz + ListenBrainz similar artists. Zero dependencies, no API keys. |
| Script | `scripts/playlist.py` | Self-contained **HTML playlist**: cover art, 30-sec audio previews, per-song YouTube/Spotify/JioSaavn links, sections + "why this song" notes. |
| Fixture | `scripts/sample-songs.json` | Real catalog records (demo curation) to try the playlist renderer offline. |

## Install

```
/plugin marketplace add PSURI1894/Claude-Plugins
/plugin install song-finder@parth-claude-plugins
```

No Python dependencies — the scripts are pure standard library.

## Usage

```
/song-finder:find-song sad Arijit Singh type songs, Hindi, for a rainy night — 15 tracks
/song-finder:find-song Punjabi party playlist around Diljit Dosanjh and AP Dhillon, nothing explicit
/song-finder:similar-artists Kishore Kumar, Mohammed Rafi
```

Plugin commands are namespaced — type `/song-finder` and tab-complete.

Or just talk naturally — "I need wedding-sangeet songs, mostly Shreya Ghoshal,
some surprises welcome" — and the `song-search` skill activates on its own.

## How it works

1. **Brief** — your request is parsed into structured filters: seed singers (primary), mood/occasion, language (hard filter), genre, era, count, discovery appetite, clean-only, must-include/exclude.
2. **Storefront** — the iTunes country is picked by language (`IN` for Hindi/Punjabi/Tamil…, `KR` for K-pop, `US`/`GB` for English) so the right catalog surfaces.
3. **Gather** — three sources merge into one deduped pool: each seed singer's popular originals (`music.py top`, remixes dropped), mood research via WebSearch with **every candidate verified** through `music.py search`, and similar-artist signature tracks (`music.py similar`, capped at ~⅓ of the list).
4. **Curate** — language is hard, mood fit first, your singers anchor the list, originals over remixes, variety across albums/years. Each pick gets a section and a one-line "why it fits" note.
5. **Present** — a table per section plus an interactive playlist page: cover art, 30-second previews, and YouTube/Spotify/JioSaavn links for the full songs.

### Using the scripts directly

```bash
# An artist's popular originals (remixes/sped-up/vocals-only auto-dropped)
python scripts/music.py top --artist "Arijit Singh" --country IN --limit 15 --output songs.json

# Verify/search any song or mood phrase; --append merges + dedupes into the pool
python scripts/music.py search --query "Channa Mereya" --country IN --output songs.json --append

# Similar artists with 2 signature tracks each (MusicBrainz + ListenBrainz, no key)
python scripts/music.py similar --artist "Arijit Singh" --limit 8 --with-top 2 --country IN

# Render the playlist page (try it now with the bundled sample data)
python scripts/playlist.py --input scripts/sample-songs.json --title "Demo playlist" --open

# Or pipe straight through
python scripts/music.py top --artist "Diljit Dosanjh" --country IN --json | \
  python scripts/playlist.py --title "Top Diljit"
```

## Notes & limits

- **No invented songs** — every recommendation is a real catalog record; wrong-artist attribution is treated as a bug.
- **Previews are 30-second clips** (iTunes preview URLs); full songs are on the linked services.
- **Mood labels are judgment calls** — the plugin says so and offers swaps; language, by contrast, is a hard filter.
- **Similarity data reflects ListenBrainz listeners** — it can skew Western for regional artists; results are sanity-checked before presenting, and the similarity-dataset name pinned in `music.py` may need a refresh if the endpoint changes snapshots.
- **Storefront ≠ global availability** — metadata and previews vary by country; a missing preview doesn't mean a song doesn't exist.
- **Polite APIs** — MusicBrainz calls are throttled to its 1 request/sec policy.

## License

MIT © Parth Suri
