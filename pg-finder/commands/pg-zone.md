---
description: Map the 5 km PG search zone for 1-3 people — geocode each person's anchor, cluster to the midpoint, and list the localities to target.
argument-hint: <one location per person, ';'-separated, e.g. "Embassy Tech Village; Christ University Bengaluru">
allowed-tools: WebSearch, WebFetch, Bash, Read, Write
---

## Goal
Compute and explain the **PG search zone** before any listing research: geocode each
person's anchor location, cluster a group's anchors to their midpoint, and return the
5 km circle with map links and target localities.

Anchors: **$ARGUMENTS**

## Workflow
1. **Parse the anchors.** Split "$ARGUMENTS" on `;` — one anchor per person (1–3 people).
   If an anchor is ambiguous (no city), add the city from context or ask once.

2. **Build the zone** (5 km default; honor any radius the user stated):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/geo.py" zone \
     --anchor "Person 1=<first anchor>" [--anchor "Person 2=<second>"] [--anchor "Person 3=<third>"] \
     --radius 5 --output zone.json
   ```
   Check every anchor's resolved `display_name` — if Nominatim picked the wrong place,
   retry that anchor with a more specific query before presenting anything.

3. **Present the zone:**
   - Centre coordinates + radius, and each anchor's distance from the centre.
   - **Groups:** the pairwise distances between members, the `guaranteed_radius_km`
     ("PGs within X km of the midpoint suit everyone"), and — if `all_reachable` is
     false — a plain warning that the anchors are > 10 km apart so no point is within
     5 km of both, with options (bigger radius, corridor search, or splitting up).
   - The `map_links` (OpenStreetMap view + a Google Maps "PG near here" search).

4. **Name the target localities.** Use WebSearch (e.g. `localities within 5 km of
   <anchor>`, `<area> neighbourhoods PG`) to list 3–6 neighbourhood names inside the
   circle, ordered by closeness to the centre — these become the search terms for
   listing sites.

5. **Offer the next step:** running `/find-pg` with their gender / budget / AC / food
   filters to fill the zone with ranked listings.
