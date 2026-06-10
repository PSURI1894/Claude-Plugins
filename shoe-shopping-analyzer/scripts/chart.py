#!/usr/bin/env python3
"""
chart.py - Render a visual shoe comparison as a self-contained HTML page.

Zero external dependencies (pure standard library). Input is a JSON array,
ideally the ranked output of rank.py (which adds a "_score"), but raw scrape.py
output works too - it falls back to rating, then price.

Usage:
  python rank.py --input shoes.json --json | python chart.py --output comparison.html
  python chart.py --input ranked.json --output comparison.html --title "Trail runners under $130" --open

The page shows one horizontal bar per shoe (length = overall score, color = rating)
with price / rating / reviews / retailer, each linking to its product page.
"""
import argparse
import html
import json
import os
import sys
import webbrowser


def load(args):
    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            return json.load(fh)
    return json.load(sys.stdin)


def bar_metric(p):
    """Value that drives bar length, plus a label for what it represents."""
    if p.get("_score") is not None:
        return float(p["_score"]), "score"
    if p.get("rating") is not None:
        return float(p["rating"]) * 20.0, "rating"
    return 50.0, "n/a"


def rating_color(rating):
    if rating is None:
        return "#9aa0a6"
    if rating >= 4.5:
        return "#2e7d32"
    if rating >= 4.0:
        return "#689f38"
    if rating >= 3.5:
        return "#f9a825"
    return "#c0392b"


def esc(x):
    return html.escape(str(x)) if x is not None else ""


def build_html(products, title):
    ranked = sorted(products, key=lambda p: bar_metric(p)[0], reverse=True)
    max_m = max((bar_metric(p)[0] for p in ranked), default=1.0) or 1.0

    rows = []
    for i, p in enumerate(ranked, 1):
        m, mlabel = bar_metric(p)
        pct = max(4.0, round(100.0 * m / max_m, 1))
        name = esc(p.get("title") or "Unknown shoe")
        url = p.get("url")
        name_html = f'<a href="{esc(url)}" target="_blank" rel="noopener">{name}</a>' if url else name
        price = f"${p['price']:.0f}" if p.get("price") is not None else "&mdash;"
        rating_val = p.get("rating")
        rating = f"{rating_val:.1f}&#9733;" if rating_val is not None else "&mdash;"
        revs = f"{p['review_count']:,}" if p.get("review_count") else "&mdash;"
        retailer = esc(p.get("retailer") or "&mdash;")
        score_txt = f"{m:.0f}" if mlabel != "n/a" else "&mdash;"
        color = rating_color(rating_val)
        rows.append(f"""
      <div class="row">
        <div class="rank">{i}</div>
        <div class="body">
          <div class="name">{name_html}</div>
          <div class="track">
            <div class="bar" style="width:{pct}%;background:{color}"></div>
            <span class="score">{score_txt}</span>
          </div>
          <div class="meta">
            <span class="price">{price}</span>
            <span class="pill">{rating}</span>
            <span class="pill">{revs} reviews</span>
            <span class="pill retailer">{retailer}</span>
          </div>
        </div>
      </div>""")

    metric_label = bar_metric(ranked[0])[1] if ranked else "score"
    body = "".join(rows) if rows else '<p class="empty">No products to chart.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         margin: 0; padding: 32px; background: #0f1115; color: #e8eaed; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  .sub {{ color: #9aa0a6; font-size: 13px; margin-bottom: 24px; }}
  .row {{ display: flex; align-items: stretch; gap: 14px; padding: 14px 0;
          border-bottom: 1px solid #23262e; }}
  .rank {{ font-size: 20px; font-weight: 700; color: #5f6368; width: 34px;
           text-align: right; padding-top: 2px; }}
  .body {{ flex: 1; min-width: 0; }}
  .name {{ font-size: 15px; font-weight: 600; margin-bottom: 8px; }}
  .name a {{ color: #8ab4f8; text-decoration: none; }}
  .name a:hover {{ text-decoration: underline; }}
  .track {{ position: relative; background: #1c1f27; border-radius: 6px;
            height: 26px; overflow: hidden; }}
  .bar {{ height: 100%; border-radius: 6px 0 0 6px; transition: width .3s; }}
  .score {{ position: absolute; right: 10px; top: 0; line-height: 26px;
            font-size: 12px; font-weight: 700; color: #e8eaed; }}
  .meta {{ margin-top: 8px; font-size: 12.5px; color: #bdc1c6;
           display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
  .price {{ font-weight: 700; color: #81c995; font-size: 14px; }}
  .pill {{ background: #23262e; border-radius: 999px; padding: 2px 9px; }}
  .retailer {{ color: #fdd663; }}
  .empty {{ color: #9aa0a6; }}
  footer {{ margin-top: 24px; color: #5f6368; font-size: 12px; }}
</style>
</head>
<body>
  <h1>{esc(title)}</h1>
  <div class="sub">Bar length = {metric_label} &middot; bar color = review rating &middot; sorted best &rarr; worst</div>
  {body}
  <footer>Prices &amp; stock are a snapshot from when this was generated &mdash; verify at checkout. Generated by shoe-shopping-analyzer.</footer>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="Render a visual HTML shoe comparison chart.")
    ap.add_argument("--input", help="products/ranked JSON file (default: read stdin)")
    ap.add_argument("--output", default="shoe-comparison.html", help="HTML output path")
    ap.add_argument("--title", default="Shoe Comparison", help="page title / heading")
    ap.add_argument("--open", action="store_true", help="open the chart in the default browser")
    args = ap.parse_args()

    products = load(args)
    if not isinstance(products, list):
        sys.exit("Input must be a JSON array of product objects.")

    page = build_html(products, args.title)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(page)

    abspath = os.path.abspath(args.output)
    print(f"Wrote {abspath} ({len(products)} shoes)")
    if args.open:
        webbrowser.open("file://" + abspath.replace(os.sep, "/"))


if __name__ == "__main__":
    main()
