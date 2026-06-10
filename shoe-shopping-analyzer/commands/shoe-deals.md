---
description: Find the best current price / deal for a specific shoe model across all retailers.
argument-hint: <specific model, e.g. "Brooks Ghost 16 men's size 11">
allowed-tools: WebSearch, WebFetch, Bash, Read, Write
---

## Goal
Find the lowest legitimate current price for **one specific shoe** across every retailer that stocks it.

Target: **$ARGUMENTS**

## Workflow
1. **Pin down the exact model.** Confirm brand, model, version/year, gender, size, and (if given) colorway from "$ARGUMENTS". Note that price often varies by colorway.

2. **Search every retailer** with WebSearch — the brand's own store, Amazon, Zappos, Foot Locker, Dick's, Running Warehouse, Road Runner Sports, REI, Backcountry, DSW, 6pm, Walmart, Target, eBay, StockX, and GOAT. Include each retailer's **sale / outlet / clearance** pages.

3. **Pull live prices** with WebFetch and/or the scraper, then sort by price:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/scrape.py" --output deals.json <URLs...>
   python "${CLAUDE_PLUGIN_ROOT}/scripts/rank.py" --input deals.json --weights price=1.0
   ```

4. **Present a price table** sorted low → high:
   retailer · price · original price / discount % · stock status **for the requested size** · shipping & returns notes · link.

   Then call out:
   - The single **best deal** (price + why it wins).
   - Any **coupon, cashback, or membership** angle (e.g. student/military, loyalty, card offers) — only if you can verify it.
   - **Stock-outs** for the requested size.

Always warn that prices change quickly — verify at checkout. Never fabricate a discount.
