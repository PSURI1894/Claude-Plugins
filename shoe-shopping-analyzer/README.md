# shoe-shopping-analyzer

A Claude Code plugin that compares shoes across **every available online retailer** and ranks them
against your filters — price & deals, brand/model, size/fit/width, activity, performance specs, and
reviews. It combines live web research, structured scraping, and a weighted scoring engine.

## What you get

| Component | Name | Purpose |
|---|---|---|
| Command | `/compare-shoes <brief>` | Full comparison: discover candidates across all sites, filter, rank, recommend. |
| Command | `/shoe-deals <model>` | Best current price for one specific model across every retailer. |
| Skill | `shoe-comparison` | Auto-triggers in normal conversation about buying/comparing shoes; holds the full methodology. |
| Script | `scripts/scrape.py` | Extracts normalized product data (price, rating, reviews, stock) from any retailer URL via JSON-LD / meta / HTML. |
| Script | `scripts/rank.py` | Applies hard filters and a weighted 0–100 score, prints a ranked table. |

## Install

```
/plugin marketplace add PSURI1894/Claude-Plugins
/plugin install shoe-shopping-analyzer@parth-claude-plugins
```

Then install the Python dependencies used by the scraper:

```
pip install -r "<plugin-path>/scripts/requirements.txt"
```

## Usage

```
/compare-shoes men's trail running shoes under $130, wide (2E), size 11, great cushioning
/shoe-deals Brooks Ghost 16 men's size 11
```

Or just talk naturally — "help me find good wide-fit road running shoes under $120" — and the
`shoe-comparison` skill activates on its own.

## How it works

1. **Brief** — your request is parsed into structured filters (activity, size/width, budget, brand, specs, priorities).
2. **Discover** — WebSearch casts a wide net across brand stores, marketplaces, specialists, outlets, and resale sites to collect candidate product URLs.
3. **Extract** — `scrape.py` reads each page's schema.org JSON-LD (then OpenGraph/meta, then HTML) into normalized records; WebFetch fills in fit notes and review themes.
4. **Rank** — `rank.py` drops anything failing your hard limits, then scores survivors on price (lower better), rating, and review-count confidence (log-scaled), using weights set from your stated priorities.
5. **Present** — a comparison table plus a top pick, budget pick, and premium pick, every price linked and timestamped "verify at checkout".

### Using the scripts directly

```bash
# 1. Scrape several product pages into normalized JSON
python scripts/scrape.py --output shoes.json \
  "https://www.zappos.com/p/..." "https://www.brooksrunning.com/..." "https://www.amazon.com/dp/..."

# 2. Filter + rank with your priorities
python scripts/rank.py --input shoes.json \
  --max-price 130 --min-rating 4.2 --brand brooks,asics,hoka --in-stock \
  --weights price=0.4,rating=0.35,reviews=0.25
```

## Notes & limits

- **Honest data only** — the plugin never invents prices, discounts, ratings, or specs. Unknown fields are reported as unknown.
- **Freshness** — results are a snapshot; prices and per-size stock change quickly, so always verify at checkout.
- **Coverage** — some retailers serve product data only via JavaScript or block automated fetches; those pages may not scrape cleanly, and the comparison will say so. WebFetch covers many of these as a fallback.
- **Neutral** — no retailer or brand is favored; ranking is purely your brief + the data.

## License

MIT © Parth Suri
