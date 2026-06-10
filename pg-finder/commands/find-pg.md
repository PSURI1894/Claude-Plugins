---
description: Find and rank PG accommodation near your office/college — solo or for a group of 2-3 — with gender, budget, AC, sharing, and food filters.
argument-hint: <brief, e.g. "2 girls, PG near Christ University Bengaluru, ₹12k each, AC, veg food">
allowed-tools: WebSearch, WebFetch, Bash, Read, Write, Glob
---

## Goal
Find, filter, and rank **PG (paying guest) accommodation** matching the user's request,
inside a 5 km search zone around their anchor (solo) or the group's clustered midpoint
(2–3 people), then present a clear shortlist with a map.

User request: **$ARGUMENTS**

## Use the pg-search methodology
Follow the full workflow defined in the `pg-search` skill. In brief:

1. **Clarify the brief.** From "$ARGUMENTS" extract: city, anchor location per person
   (office/college — as specific as possible), group size, gender (male/female/coed),
   budget per person, sharing type, AC/non-AC, food, must-have vs nice-to-have amenities,
   and priorities. If an anchor location, gender, or budget is missing, ask **one**
   concise round of questions; otherwise proceed and state your assumptions.

2. **Build the search zone** (5 km radius — solo anchor or group midpoint):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/geo.py" zone \
     --anchor "Name=office or college, city" [--anchor "Name2=..."] \
     --radius 5 --output zone.json
   ```
   Verify each anchor's `display_name` resolved to the right place. For groups, relay the
   pairwise distances — and if `all_reachable` is false (anchors > 10 km apart), tell the
   user no spot can be within 5 km of everyone and propose options before continuing.

3. **Discover candidates.** WebSearch the localities inside the zone across NoBroker,
   MagicBricks, 99acres, Housing.com, Sulekha, JustDial, and co-living brands (Zolo,
   Stanza Living, Colive, Settl…), plus Google Maps `PG near <locality>`. Collect
   **10–20 direct listing URLs**.

4. **Extract normalized records** with WebFetch into `pgs.json` (schema in the skill;
   one record per sharing tier when rents differ; unknown fields = null, never guessed).
   Fill missing coordinates:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/geo.py" fill --input pgs.json --city "<city>"
   ```

5. **Filter & rank** with the user's hard limits and priority weights (add `--chart` for
   an inline score chart):
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/rank.py" --input pgs.json --zone zone.json \
     --gender <male|female|coed> [--ac|--non-ac] --max-rent <N> --food <veg|nonveg|any|none> \
     --sharing <single,double> --amenities <wifi,...> --prefer <laundry,...> \
     --weights distance=0.35,rent=0.30,rating=0.20,amenities=0.15 --chart
   ```

6. **Present.** Shortlist table (PG · rent & sharing · deposit · gender · AC · food ·
   distance per member · rating · source link), then a **top pick**, **budget pick**, and
   **comfort pick** with reasoning, plus caveats. Generate the interactive map:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/rank.py" --input pgs.json --zone zone.json --json <same filters> \
     | python "${CLAUDE_PLUGIN_ROOT}/scripts/map.py" --zone zone.json --title "PGs near <area>" --open
   ```

## Output rules
- Cite the source + URL (or phone) for every listing; flag everything "as of now — confirm on call/visit".
- **Gender is a hard filter** — never show a mismatched-gender PG.
- Distances are straight-line; recommend checking real commute times for finalists.
- Never invent rents, deposits, ratings, or amenities — unknown means unknown.
