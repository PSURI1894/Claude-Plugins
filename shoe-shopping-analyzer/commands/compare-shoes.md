---
description: Compare shoes across all online retailers with deep filters — price, fit, size/width, activity, specs, and reviews.
argument-hint: <what you want, e.g. "men's trail running shoes under $120, wide, size 11">
allowed-tools: WebSearch, WebFetch, Bash, Read, Write, Glob
---

## Goal
Find, filter, and rank shoes that match the user's request across **every relevant retailer**, then present a clear side-by-side comparison and a recommendation.

User request: **$ARGUMENTS**

## Use the shoe-comparison methodology
Follow the full workflow defined in the `shoe-comparison` skill. In brief:

1. **Clarify the brief.** From "$ARGUMENTS" extract: shoe category/activity, gender, size & width, budget / price ceiling, must-have or excluded brands, key specs (cushioning, heel-toe drop, weight, support/stability, waterproofing), and any deal-breakers. If something fit-critical is missing (e.g. size, width, or intended use), ask **one** concise round of questions; otherwise proceed and state your assumptions.

2. **Discover candidates across all sites.** Use WebSearch to gather current listings from every relevant retailer — brand stores (Nike, Adidas, New Balance, ASICS, HOKA, Brooks, Saucony…), marketplaces (Amazon, eBay, Walmart, Target), specialists (Zappos, Foot Locker, Dick's, REI, Running Warehouse, Road Runner Sports, Backcountry), outlets (6pm, DSW), and resale (StockX, GOAT). Collect **8–15 candidate product URLs spanning multiple retailers**.

3. **Extract structured data.** Pull live details with WebFetch and/or run the scraper for normalized fields:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/scrape.py" --output shoes.json <URL1> <URL2> <URL3> ...
   ```

4. **Filter & rank.** Apply hard filters and weight the criteria:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/rank.py" --input shoes.json \
     --max-price <N> --min-rating <N> --brand <brand1,brand2> \
     --weights price=0.4,rating=0.35,reviews=0.25
   ```

5. **Present.** A comparison table (model · price & retailer · rating/reviews · fit notes · key specs · best-for), then a **top recommendation** with reasoning, plus a **budget pick** and a **premium pick**.

## Output rules
- Cite the retailer + URL for every price.
- Flag all prices as "as of now — verify at checkout"; prices and stock change fast.
- Be brand- and retailer-neutral. Never invent prices, ratings, or specs — if a field is unknown, say so.
