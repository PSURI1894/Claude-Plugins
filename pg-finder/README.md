# pg-finder

A Claude Code plugin that finds and ranks **PG (paying guest) accommodation in any city**
using maps, live listing research, and your preferences — gender, budget, AC/non-AC,
sharing type, food, and amenities.

**The location rule:** searching alone? You get a **5 km radius** around your anchor
(office / college / any spot). Searching as a group of 2–3? Each person's anchor is
geocoded and **clustered to the midpoint**, and the 5 km circle is centred there — with
per-member commute distances reported for every PG, and a clear warning when the anchors
are too far apart (> 10 km) for any single spot to suit everyone.

All maps functionality is **free and key-less**: geocoding via OpenStreetMap Nominatim,
output as an interactive Leaflet map.

## What you get

| Component | Name | Purpose |
|---|---|---|
| Command | `/pg-finder:find-pg <brief>` | Full search: zone → discover listings → extract → filter → rank → map. |
| Command | `/pg-finder:pg-zone <anchors>` | Just the geometry: geocode 1–3 anchors, cluster, map the 5 km zone, name target localities. |
| Skill | `pg-search` | Auto-triggers in normal conversation about finding PGs; holds the full methodology. |
| Script | `scripts/geo.py` | `zone`: geocode anchors + centroid + search circle + map links. `fill`: batch-geocode listing addresses. Zero dependencies. |
| Script | `scripts/rank.py` | Hard filters (gender, rent, AC, sharing, food, amenities, distance) + weighted 0–100 score; ranked table, `--chart` for ASCII bars, `--json` for piping. |
| Script | `scripts/map.py` | Interactive **HTML map** (Leaflet + OSM): anchors, 5 km circle, score-colored PG pins with popups. Zero build dependencies. |
| Fixtures | `scripts/sample-pgs.json`, `scripts/sample-zone.json` | Synthetic demo data to try the pipeline offline. |

## Install

```
/plugin marketplace add PSURI1894/Claude-Plugins
/plugin install pg-finder@parth-claude-plugins
```

No Python dependencies — the scripts are pure standard library.

## Usage

```
/pg-finder:find-pg 2 girls, PG near Christ University Bengaluru, budget ₹12k each, AC, veg food
/pg-finder:find-pg single sharing PG for a working professional near Hinjewadi Phase 2 Pune, non-AC ok, under ₹10k
/pg-finder:pg-zone Embassy Tech Village Bengaluru; Christ University Bengaluru
```

Plugin commands are namespaced — type `/pg-finder` and tab-complete. Be specific with
anchor locations ("Thomson Reuters, EPIP Zone Whitefield" beats "Thomson Reuters Bangalore",
which can resolve to the wrong campus).

Or just talk naturally — "we're 3 friends moving to Hyderabad, need a boys PG near
Hitec City under 9k" — and the `pg-search` skill activates on its own.

## How it works

1. **Brief** — your request is parsed into structured filters (anchors, group size, gender, budget, sharing, AC, food, amenities, priorities).
2. **Zone** — `geo.py zone` geocodes each person's anchor (free OSM Nominatim, self-throttled to its 1 req/sec policy) and emits the 5 km search circle: solo anchor or group midpoint, pairwise distances, and a `guaranteed_radius_km` inside which a PG suits *every* member.
3. **Discover** — WebSearch sweeps NoBroker, MagicBricks, 99acres, Housing.com, Sulekha, JustDial, co-living brands (Zolo, Stanza Living, Colive, Settl…), and Google Maps for listings inside the zone's localities.
4. **Extract** — listings are normalized into JSON records (rent, deposit, gender, sharing, AC, food, amenities, curfew, rating, coordinates); `geo.py fill` geocodes any missing coordinates from addresses. Unknown fields stay null — never guessed.
5. **Rank** — `rank.py` drops anything failing your hard filters, then scores survivors on worst-member distance, rent, rating, and amenity match with weights set from your priorities.
6. **Present** — a shortlist table plus a top pick, budget pick, and comfort pick — and an interactive map with the circle, anchors, and score-colored pins.

### Using the scripts directly

```bash
# 1. Build the search zone (1-3 anchors; 5 km default radius)
python scripts/geo.py zone --anchor "Rahul=Embassy Tech Village, Bengaluru" \
  --anchor "Priya=Christ University, Bengaluru" --output zone.json

# 2. Geocode any listing records that lack coordinates
python scripts/geo.py fill --input pgs.json --city Bengaluru

# 3. Filter + rank (try it now with the bundled sample data)
python scripts/rank.py --input scripts/sample-pgs.json --zone scripts/sample-zone.json \
  --gender male --max-rent 12000 --food veg --chart

# 4. Render the interactive map (opens in your browser)
python scripts/rank.py --input scripts/sample-pgs.json --zone scripts/sample-zone.json --json \
  | python scripts/map.py --zone scripts/sample-zone.json --title "Demo PG search" --open
```

## The group-clustering math

- Midpoint = arithmetic centroid of the members' geocoded anchors.
- A PG within `radius − max(anchor→midpoint)` km of the midpoint is **guaranteed** within
  the radius of every member (reported as `guaranteed_radius_km`).
- If any two anchors are more than `2 × radius` apart, **no point** can be within the
  radius of both — the plugin says so instead of pretending, and suggests a bigger radius
  or a corridor search.
- Ranking uses the **worst member's distance**, so results are fair to everyone, and the
  `--worst-within 5` flag enforces "every member within 5 km of the PG itself".

## Notes & limits

- **Straight-line distances** — not road or transit time; check real commute times for finalists.
- **Honest data only** — rents, deposits, and ratings are never invented; unknown fields are reported as unknown. The bundled `sample-*.json` files are clearly synthetic demo fixtures.
- **Freshness** — PG listings go stale fast and rents are negotiable; always confirm on a call or visit.
- **Coverage** — some listing sites are JS-only or bot-walled; the shortlist says which sources couldn't be read.
- **Gender filter is hard** — a mismatched-gender PG is never recommended.

## License

MIT © Parth Suri
