#!/usr/bin/env python3
"""
rank.py - Filter and rank normalized shoe products by weighted criteria.

Input: a JSON array (as produced by scrape.py) on stdin or via --input.
Applies hard filters, then scores each surviving product 0-100 using configurable
weights, and prints a ranked comparison table (or JSON with --json).

Usage:
  python rank.py --input products.json
  cat products.json | python rank.py --max-price 130 --min-rating 4.2 \
      --brand brooks,asics --weights price=0.4,rating=0.4,reviews=0.2
"""
import argparse
import json
import math
import sys

DEFAULT_WEIGHTS = {"price": 0.40, "rating": 0.35, "reviews": 0.25}
OUT_OF_STOCK = {"outofstock", "soldout", "discontinued", "out of stock", "sold out"}


def load(args):
    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            return json.load(fh)
    return json.load(sys.stdin)


def parse_weights(spec):
    if not spec:
        return dict(DEFAULT_WEIGHTS)
    weights = {}
    for part in spec.split(","):
        key, _, val = part.partition("=")
        try:
            weights[key.strip()] = float(val)
        except ValueError:
            sys.exit(f"Bad --weights term: {part!r} (use e.g. price=0.4,rating=0.4,reviews=0.2)")
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}  # normalize to sum 1


def passes_filters(p, args):
    if "error" in p:
        return False
    price = p.get("price")
    if args.max_price is not None and (price is None or price > args.max_price):
        return False
    if args.min_price is not None and (price is None or price < args.min_price):
        return False
    if args.min_rating is not None and (p.get("rating") is None or p["rating"] < args.min_rating):
        return False
    if args.brand:
        brands = [b.strip().lower() for b in args.brand.split(",") if b.strip()]
        hay = f"{p.get('brand', '')} {p.get('title', '')}".lower()
        if not any(b in hay for b in brands):
            return False
    if args.keywords:
        kws = [k.strip().lower() for k in args.keywords.split(",") if k.strip()]
        hay = (p.get("title") or "").lower()
        if not all(k in hay for k in kws):
            return False
    if args.in_stock and (p.get("availability") or "").strip().lower() in OUT_OF_STOCK:
        return False
    return True


def normalizer(values, invert=False):
    vals = [v for v in values if v is not None]
    if not vals:
        return lambda v: 0.5  # nothing to compare on -> neutral
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return lambda v: 1.0 if v is not None else 0.0

    def f(v):
        if v is None:
            return 0.0
        n = (v - lo) / (hi - lo)
        return 1.0 - n if invert else n

    return f


def score_all(products, weights):
    review_conf = [
        math.log10(p["review_count"] + 1) if p.get("review_count") else None
        for p in products
    ]
    price_n = normalizer([p.get("price") for p in products], invert=True)
    rating_n = normalizer([p.get("rating") for p in products])
    reviews_n = normalizer(review_conf)
    for p, rc in zip(products, review_conf):
        s = (
            weights.get("price", 0) * price_n(p.get("price"))
            + weights.get("rating", 0) * rating_n(p.get("rating"))
            + weights.get("reviews", 0) * reviews_n(rc)
        )
        p["_score"] = round(100 * s, 1)
    return sorted(products, key=lambda p: p["_score"], reverse=True)


def fmt_table(ranked):
    header = (
        f"{'#':>2}  {'SCORE':>5}  {'PRICE':>8}  {'RATING':>6}  "
        f"{'REVIEWS':>7}  {'RETAILER':<16}  TITLE"
    )
    lines = [header, "-" * len(header)]
    for i, p in enumerate(ranked, 1):
        price = f"${p['price']:.0f}" if p.get("price") is not None else "-"
        rating = f"{p['rating']:.1f}*" if p.get("rating") is not None else "-"
        revs = str(p.get("review_count") or "-")
        retailer = (p.get("retailer") or "-")[:16]
        title = (p.get("title") or "-")[:48]
        lines.append(
            f"{i:>2}  {p['_score']:>5}  {price:>8}  {rating:>6}  "
            f"{revs:>7}  {retailer:<16}  {title}"
        )
    return "\n".join(lines)


def fmt_chart(ranked, width=34):
    """ASCII horizontal bar chart of scores - zero-dependency, terminal-friendly."""
    if not ranked:
        return "No products to chart."
    bar_char = "█"  # full block, falls back to '#' if the console can't encode it
    try:
        bar_char.encode(sys.stdout.encoding or "utf-8")
    except (UnicodeEncodeError, LookupError, TypeError):
        bar_char = "#"
    top = max((p["_score"] for p in ranked), default=1) or 1
    lines = ["", "SCORE COMPARISON  (bar length proportional to score)", ""]
    for i, p in enumerate(ranked, 1):
        filled = max(1, round(width * p["_score"] / top))
        bar = bar_char * filled + " " * (width - filled)
        price = f"${p['price']:.0f}" if p.get("price") is not None else "-"
        rating = f"{p['rating']:.1f}*" if p.get("rating") is not None else "-"
        name = (p.get("title") or "-")[:34]
        lines.append(f"{i:>2}. {name:<34} |{bar}| {p['_score']:>5}  {price:>6}  {rating:>5}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Filter and rank normalized shoe products.")
    ap.add_argument("--input", help="products JSON file (default: read stdin)")
    ap.add_argument("--max-price", type=float, help="drop items priced above this")
    ap.add_argument("--min-price", type=float, help="drop items priced below this")
    ap.add_argument("--min-rating", type=float, help="drop items rated below this (0-5)")
    ap.add_argument("--brand", help="comma-separated brand allowlist (matched in brand+title)")
    ap.add_argument("--keywords", help="comma-separated terms that must all appear in the title")
    ap.add_argument("--in-stock", action="store_true", help="drop out-of-stock items")
    ap.add_argument("--weights", help="e.g. price=0.4,rating=0.4,reviews=0.2 (auto-normalized)")
    ap.add_argument("--top", type=int, default=0, help="limit output to the top N")
    ap.add_argument("--json", action="store_true", help="emit ranked JSON instead of a table")
    ap.add_argument("--chart", action="store_true", help="also print an ASCII score bar chart")
    args = ap.parse_args()

    products = load(args)
    if not isinstance(products, list):
        sys.exit("Input must be a JSON array of product objects.")
    weights = parse_weights(args.weights)
    kept = [p for p in products if passes_filters(p, args)]
    ranked = score_all(kept, weights)
    if args.top:
        ranked = ranked[: args.top]

    if args.json:
        print(json.dumps(ranked, indent=2, ensure_ascii=False))
    elif ranked:
        print(fmt_table(ranked))
        if args.chart:
            print(fmt_chart(ranked))
    else:
        print("No products passed the filters.")
    print(
        f"\n# {len(ranked)} of {len(products)} products passed filters | weights: {weights}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
