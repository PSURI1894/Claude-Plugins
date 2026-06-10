---
name: shoe-comparison
description: Compare and rank shoes across online retailers using live web research and structured scraping. Use whenever the user wants to shop for, compare, find deals on, or choose between shoes / sneakers / boots / cleats / sandals based on price, fit, size, width, intended activity, performance specs, brand, or reviews.
allowed-tools: WebSearch, WebFetch, Bash, Read, Write, Glob
---

# Shoe Comparison & Shopping Analysis

A repeatable methodology for turning a fuzzy shoe request ("good wide trail runners under $130")
into a ranked, well-sourced comparison across **every available shopping site**.

## When to use
Trigger this when the user wants to buy, compare, shortlist, or find deals on footwear and cares
about one or more **filters**: price/deals, brand/model, size/fit/width, activity/type, performance
specs, or reviews. If they name one specific model and just want the cheapest source, the
`/shoe-deals` command is the faster path.

---

## Step 1 — Turn the request into a structured brief
Extract these fields (ask **one** concise round of questions only for fit-critical gaps):

| Field | Examples | Notes |
|---|---|---|
| Category / activity | road running, trail, basketball, hiking, training, walking, casual, lifestyle | Drives which retailers and specs matter |
| Gender / last | men's, women's, unisex, kids | Affects sizing and model availability |
| Size & width | US 11, EU 44; narrow/standard/wide/2E/4E | **Fit-critical** — ask if missing |
| Budget | hard ceiling, target, "best value" | Becomes `--max-price` |
| Brand constraints | must-have, preferred, excluded | Becomes `--brand` allowlist |
| Key specs | cushioning, heel-toe drop, weight, stack height, stability/support, waterproof, breathability | Match to activity |
| Deal-breakers | color, no-leather, vegan, made-in, return policy | Hard filters |
| Priorities | "cheap as possible" vs "best reviews" vs "balanced" | Sets ranking **weights** |

Echo the brief back in one line before researching, so the user can correct it.

---

## Step 2 — Discover candidates across ALL sites
Use **WebSearch** to gather current listings. Cast a wide net across these tiers, then keep the
8–15 strongest candidate **product URLs** spanning multiple retailers:

- **Brand stores:** Nike, Adidas, New Balance, ASICS, HOKA, Brooks, Saucony, On, Puma, Reebok, Under Armour, Salomon, Merrell.
- **Marketplaces:** Amazon, eBay, Walmart, Target.
- **Footwear specialists:** Zappos, Foot Locker, Finish Line, Dick's Sporting Goods, Road Runner Sports, Running Warehouse, REI, Backcountry.
- **Outlet / value:** 6pm, DSW, Nordstrom Rack, Sierra.
- **Resale / hard-to-find:** StockX, GOAT, Flight Club.

Search patterns that work well:
- `<model> <gender> best price` · `<activity> shoes <year> wide` · `<brand> <model> review`
- `site:zappos.com <model>` to force a retailer.
- Add `sale`, `clearance`, or `outlet` to surface discounts.

Prefer **direct product pages** over category pages — they carry structured data the scraper can read.

---

## Step 3 — Extract structured, normalized data
Two complementary tools — use both as needed:

**A) WebFetch** for nuanced, page-specific facts (fit feedback "runs small", review themes,
spec sheets, size-specific stock). Best for reading reviews and editorial detail.

**B) The scraper** for fast, normalized fields (price, currency, rating, review count, availability,
image) across many URLs at once. It reads schema.org JSON-LD first (what most retailers embed),
then OpenGraph/meta tags, then HTML heuristics:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/scrape.py" --output shoes.json \
  "https://www.zappos.com/p/..." "https://www.brooksrunning.com/..." "https://www.amazon.com/dp/..."
```

`scrape.py` emits a JSON array of records like:
```json
{ "url": "...", "retailer": "Zappos", "title": "Brooks Ghost 16",
  "brand": "Brooks", "price": 139.95, "currency": "USD",
  "availability": "InStock", "rating": 4.6, "review_count": 2840 }
```
Records that fail carry an `"error"` field instead — keep going and note coverage gaps.
If a price/rating can't be extracted, fill it from WebFetch rather than guessing.

---

## Step 4 — Filter and rank
Run the ranking engine with the user's hard filters and priority weights:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/rank.py" --input shoes.json \
  --max-price 130 --min-rating 4.2 --brand brooks,asics,hoka --in-stock \
  --weights price=0.4,rating=0.35,reviews=0.25 --chart
```

`--chart` appends an ASCII score bar chart under the table — a fast visual read of how the candidates stack up.

How scoring works (all normalized **within the candidate set**, 0–100 final):
- **price** — lower is better (min-max inverted).
- **rating** — higher star average is better.
- **reviews** — review-count confidence on a log scale (1000 reviews shouldn't bury a great 200-review shoe, but ratings with a handful of reviews are discounted).

Pick weights from the user's stated priority:
- "Cheapest that's decent" → `price=0.6,rating=0.3,reviews=0.1`
- "Best reviewed, money no object" → `price=0.1,rating=0.6,reviews=0.3`
- Balanced (default) → `price=0.4,rating=0.35,reviews=0.25`

Hard filters (`--max-price`, `--min-rating`, `--brand`, `--keywords`, `--in-stock`) drop
non-matching shoes **before** scoring. Fit/width and activity suitability often aren't in the
structured data — apply those yourself from WebFetch findings when narrowing the list.

---

## Step 5 — Present the comparison
Lead with a compact table, then narrative picks.

**Comparison table** (one row per shoe, sorted by score):

| Rank | Shoe | Best price (retailer) | Rating (n) | Fit / width | Key specs | Best for |
|------|------|----------------------|-----------|-------------|-----------|----------|

**Then:**
- 🏆 **Top pick** — 1–2 sentences on why it wins for *this* brief.
- 💰 **Budget pick** — best value under the ceiling.
- ⭐ **Premium pick** — if money were no object.
- ⚠️ **Caveats** — price/stock volatility, thin review counts, fit warnings ("runs ~½ size small"), colorway price gaps.

**Every** price must carry its retailer + clickable URL and a "as of now — verify at checkout" note.

### Visual chart (optional but encouraged)
Offer a chart comparison — two zero-dependency ways:
- **Inline ASCII** — add `--chart` to `rank.py` (above) for score bars right in the terminal.
- **Shareable HTML** — pipe the ranked JSON into `chart.py` for a polished, self-contained page (bar length = score, bar color = rating, every shoe linked):
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/scripts/rank.py" --input shoes.json --json --weights price=0.4,rating=0.35,reviews=0.25 \
    | python "${CLAUDE_PLUGIN_ROOT}/scripts/chart.py" --title "Trail runners under $130" --open
  ```
  `--open` launches it in the browser; omit it to just write the file and print the path.

---

## Guardrails
- **Never fabricate** prices, discounts, ratings, review counts, or specs. Unknown = say "unknown".
- **Stay neutral** — no retailer or brand favoritism; rank purely on the brief + data.
- **Be honest about freshness** — you're reading a snapshot; prices and size-stock move hourly.
- **Respect the user's hard limits** — don't recommend over budget or in an excluded brand unless you flag it explicitly as an exception and explain why.
- **Coverage transparency** — if some retailers couldn't be read (bot walls, JS-only pages), say which, so the comparison's limits are clear.
