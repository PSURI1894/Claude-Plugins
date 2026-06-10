---
name: pg-search
description: Find and rank PG (paying guest) accommodation in any city using maps, live listing research, and preference filters — gender (male/female/coed), budget, AC/non-AC, sharing type, food, and amenities. Use whenever the user wants to find, compare, or shortlist PGs, hostels, or co-living rooms — solo or as a group of 2-3 sharing — near an office, college, or locality. Searches a 5 km radius around the person's anchor (or the group's clustered midpoint).
allowed-tools: WebSearch, WebFetch, Bash, Read, Write, Glob
---

# PG Search & Ranking

A repeatable methodology for turning a fuzzy PG request ("AC PG for 2 girls near Christ
University under ₹12k") into a ranked, map-verified shortlist with honest per-listing data.

## When to use
Trigger this when the user wants to find, compare, or shortlist **PG / paying guest /
hostel / co-living** accommodation and cares about location plus one or more filters:
gender, budget, AC/non-AC, sharing type, food, amenities, curfew. Works for any city.
If they only want the search area mapped (no listings yet), the `/pg-zone` command is
the faster path.

---

## Step 1 — Turn the request into a structured brief
Extract these fields (ask **one** concise round of questions only for the critical gaps —
anchor location(s), gender, and budget):

| Field | Examples | Notes |
|---|---|---|
| City | Bengaluru, Pune, Delhi NCR, Hyderabad | Any city works |
| Anchor location(s) | each person's office / college / metro stop | **Critical** — one per person, as specific as possible |
| Group size | alone, 2 friends, 3 friends | Drives the clustering in Step 2 |
| Gender | male / female / coed | **Hard filter** — never relax it silently |
| Budget | rent ceiling per person; deposit tolerance | Becomes `--max-rent` |
| Sharing | single / double / triple / quad | Group of 2 often wants a double room |
| AC | AC / non-AC / either | Becomes `--ac` / `--non-ac` |
| Food | veg / non-veg / no food needed | Becomes `--food` |
| Amenities | WiFi, laundry, attached bathroom, power backup, parking, gym | Must-have vs nice-to-have (`--amenities` vs `--prefer`) |
| Constraints | curfew tolerance, move-in date, tenant type (student/professional) | Note and check per listing |
| Priorities | "cheapest" vs "shortest commute" vs "comfort" | Sets ranking **weights** |

Echo the brief back in one line before researching, so the user can correct it.

---

## Step 2 — Build the search zone (maps, no API key)
Geocode each person's anchor and compute the search circle with `geo.py`
(free OpenStreetMap Nominatim — the script self-throttles to its 1 req/sec policy):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/geo.py" zone \
  --anchor "Rahul=Embassy Tech Village, Bengaluru" \
  --anchor "Priya=Christ University, Hosur Road, Bengaluru" \
  --radius 5 --output zone.json
```

**The radius rule:** 5 km by default, both solo and group.
- **Alone** → the circle is centred on the person's single anchor.
- **2–3 people** → their anchors are clustered to the **midpoint (centroid)** and the
  5 km circle is centred there. The zone JSON also reports:
  - `pairwise_km` — how far the members' anchors are from each other;
  - `guaranteed_radius_km` — PGs within this distance of the midpoint are automatically
    within 5 km of *every* member;
  - `all_reachable: false` + a warning when any two anchors are **> 10 km apart**
    (then no point on earth is within 5 km of both — tell the user plainly and suggest
    a larger `--radius` or searching the corridor between anchors).

Show the user the zone summary and the `map_links` so they can eyeball the area.
If an anchor geocodes to the wrong place (check `display_name`!), retry with a more
specific query before proceeding.

---

## Step 3 — Discover candidate PGs in the zone
Identify 2–4 locality names inside the circle (from the zone's `display_name`s, the map,
or a quick WebSearch like `localities within 5 km of <anchor>`), then **WebSearch** across
these source tiers and collect **10–20 candidate listing URLs**:

- **Listing aggregators:** NoBroker, MagicBricks, 99acres, Housing.com, Sulekha, JustDial.
- **Managed co-living brands:** Zolo, Stanza Living, Colive, Settl, CoHo, YourSpace, Hello World.
- **Maps:** Google Maps results for `PG near <locality>` (names, ratings, review counts, phone numbers).

Search patterns that work well:
- `PG for <gender> in <locality> <city> AC single sharing`
- `site:nobroker.in PG <locality>` · `site:magicbricks.com PG <locality>`
- `<co-living brand> <locality> rent`
- `"paying guest" <locality> <budget>`

Prefer **direct listing pages** over index pages — they carry rent, sharing, and amenity detail.

---

## Step 4 — Extract structured, normalized records
Read each candidate with **WebFetch** and build one JSON record per PG (use one record
per *sharing tier* when rents differ — e.g. separate records for single and double
occupancy at the same PG). Schema:

```json
{ "name": "Sunshine Comfort PG", "url": "https://...", "source": "NoBroker",
  "address": "5th Block, Koramangala, Bengaluru", "lat": 12.934, "lon": 77.616,
  "gender": "male|female|coed", "rent": 9500, "currency": "INR", "deposit": 19000,
  "sharing": "single|double|triple|quad" , "ac": true, "food": "veg|veg+nonveg|none",
  "amenities": ["wifi", "laundry", "attached-bathroom", "power-backup"],
  "curfew": "11pm|none", "rating": 4.2, "review_count": 87, "notes": "..." }
```

- Unknown fields = `null` — **never guess** rent, deposit, or ratings.
- Many PG sites are JS-heavy or bot-walled; when a page won't load, keep the listing
  with whatever the search snippet gave you and note the gap.
- Coordinates: take them from the listing's map pin when shown; otherwise batch-geocode
  from addresses:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/geo.py" fill --input pgs.json --city "Bengaluru"
```

---

## Step 5 — Filter and rank
Run the ranking engine with the user's hard filters and priority weights:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/rank.py" --input pgs.json --zone zone.json \
  --gender female --ac --max-rent 12000 --food veg --sharing single,double \
  --amenities wifi --prefer laundry,attached-bathroom \
  --weights distance=0.35,rent=0.30,rating=0.20,amenities=0.15 --chart
```

How it works (all scores normalized **within the candidate set**, 0–100 final):
- **distance** — *worst member's* straight-line km to the PG (fair for groups; equals the
  solo distance when alone). Lower is better.
- **rent** — lower is better. **rating** — higher is better (add `reviews=` weight for
  log-scaled review-count confidence). **amenities** — fraction of `--prefer` items present.
- Hard filters drop non-matches **before** scoring: `--gender` (coed PGs also pass),
  `--max-rent`, `--ac`/`--non-ac` ("both"-type PGs pass either), `--sharing`, `--food`,
  `--amenities`, `--min-rating`, and the zone's radius as `--max-distance`.
- `--worst-within 5` = strict group mode: **every** member within 5 km of the PG itself.
- Records without coordinates are dropped by distance filters unless `--keep-unlocated`.

Weight presets by stated priority:
- "Cheapest livable" → `rent=0.55,distance=0.20,rating=0.15,amenities=0.10`
- "Shortest commute" → `distance=0.55,rent=0.20,rating=0.15,amenities=0.10`
- "Comfort first" → `rating=0.35,amenities=0.30,distance=0.20,rent=0.15`
- Balanced (default) → `distance=0.35,rent=0.30,rating=0.20,amenities=0.15`

---

## Step 6 — Present the shortlist
Lead with a compact table, then narrative picks.

| Rank | PG | Rent (sharing) | Deposit | Gender | AC | Food | Distance* | Rating (n) | Source |
|------|----|----------------|---------|--------|----|------|-----------|------------|--------|

\* solo: km from the anchor; group: **each member's km** (from `_dist_km` in `--json` output).

**Then:**
- 🏆 **Top pick** — why it wins for *this* brief.
- 💰 **Budget pick** — best value under the ceiling.
- ⭐ **Comfort pick** — if they can stretch.
- ⚠️ **Caveats** — unverified fields, thin review counts, curfew/visitor rules, food-quality
  variance, deposit & notice-period terms, brokerage.

**Map it** — generate the interactive map (anchors, 5 km circle, score-colored pins):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/rank.py" --input pgs.json --zone zone.json --json <filters...> \
  | python "${CLAUDE_PLUGIN_ROOT}/scripts/map.py" --zone zone.json --title "PGs near <area>" --open
```

Every listing must carry its source + URL (or phone number) and an "as of now — confirm
on call/visit" note.

---

## Guardrails
- **Gender is a hard filter** — never include a mismatched-gender PG, even if it scores well.
- **Never fabricate** rents, deposits, ratings, review counts, or amenities. Unknown = "unknown".
- **Distances are straight-line**, not road/commute distance — say so; suggest the user
  check Google Maps travel time for the finalists.
- **Be honest about freshness** — listings go stale fast; rents are negotiable; beds fill up.
- **Coverage transparency** — if a major source couldn't be read (bot walls, JS-only pages),
  say which, so the shortlist's limits are clear.
- **Respect Nominatim** — the scripts already throttle to 1 request/sec; don't hammer it
  with bulk loops beyond what's needed.
- **Stay neutral** — no platform or brand favoritism; rank purely on the brief + data.
