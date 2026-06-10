#!/usr/bin/env python3
"""
scrape.py - Extract normalized shoe product data from retailer URLs.

Strategy (most reliable -> fallback):
  1. JSON-LD (schema.org Product / Offer / AggregateRating) - embedded by most retailers
  2. OpenGraph / product meta tags
  3. Lightweight HTML title/price heuristics

Usage:
  python scrape.py URL [URL ...]
  python scrape.py --input urls.json --output products.json
  echo '["https://...", "https://..."]' | python scrape.py --stdin

Output: a JSON array of normalized product dicts to stdout (and to --output if given).
Records that fail to parse include an "error" field instead of product data.
"""
import argparse
import concurrent.futures
import json
import sys
import urllib.parse
from html import unescape

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Install with: pip install requests beautifulsoup4")

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# domain fragment -> friendly retailer name
RETAILERS = {
    "amazon.": "Amazon", "nike.com": "Nike", "adidas.": "Adidas",
    "zappos.com": "Zappos", "footlocker.": "Foot Locker", "finishline.": "Finish Line",
    "dicks.com": "Dick's", "rei.com": "REI", "runningwarehouse.": "Running Warehouse",
    "roadrunnersports.": "Road Runner Sports", "ebay.": "eBay", "stockx.com": "StockX",
    "goat.com": "GOAT", "flightclub.": "Flight Club", "dsw.com": "DSW", "6pm.com": "6pm",
    "newbalance.": "New Balance", "asics.": "ASICS", "hoka.com": "HOKA",
    "brooksrunning.": "Brooks", "saucony.": "Saucony", "puma.com": "PUMA",
    "underarmour.": "Under Armour", "reebok.": "Reebok", "on-running.": "On",
    "onrunning.": "On", "salomon.": "Salomon", "merrell.": "Merrell",
    "walmart.com": "Walmart", "target.com": "Target", "backcountry.com": "Backcountry",
    "nordstromrack.": "Nordstrom Rack", "nordstrom.": "Nordstrom", "sierra.com": "Sierra",
}


def retailer_of(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    for key, name in RETAILERS.items():
        if key in host:
            return name
    parts = host.replace("www.", "").split(".")
    return parts[0].capitalize() if parts and parts[0] else host


def _num(x):
    if x is None:
        return None
    try:
        return float(str(x).replace(",", "").replace("$", "").strip())
    except (ValueError, AttributeError):
        return None


def _as_list(x):
    return x if isinstance(x, list) else [x]


def _iter_jsonld(soup):
    """Yield every JSON-LD object on the page, flattening lists and @graph."""
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # some pages wrap or append junk; try to salvage the outer object
            try:
                data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            except (ValueError, json.JSONDecodeError):
                continue
        for obj in _as_list(data):
            if not isinstance(obj, dict):
                continue
            if isinstance(obj.get("@graph"), list):
                for sub in obj["@graph"]:
                    if isinstance(sub, dict):
                        yield sub
            yield obj


def _first_offer(offers):
    """Normalize Offer / AggregateOffer / list-of-offers into a flat dict."""
    if not offers:
        return {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return {}
    if offers.get("@type") == "AggregateOffer":
        return {
            "price": offers.get("lowPrice") or offers.get("price"),
            "highPrice": offers.get("highPrice"),
            "priceCurrency": offers.get("priceCurrency"),
            "availability": offers.get("availability"),
        }
    return {
        "price": offers.get("price") or (offers.get("priceSpecification") or {}).get("price"),
        "priceCurrency": offers.get("priceCurrency"),
        "availability": offers.get("availability"),
    }


def parse_product_jsonld(soup):
    for obj in _iter_jsonld(soup):
        t = obj.get("@type")
        types = [t] if isinstance(t, str) else (t or [])
        if "Product" not in types:
            continue
        brand = obj.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        offer = _first_offer(obj.get("offers"))
        rating = obj.get("aggregateRating") or {}
        avail = offer.get("availability") or ""
        image = obj.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        elif isinstance(image, dict):
            image = image.get("url")
        return {
            "title": unescape(str(obj.get("name", ""))).strip() or None,
            "brand": brand,
            "price": _num(offer.get("price")),
            "price_high": _num(offer.get("highPrice")),
            "currency": offer.get("priceCurrency"),
            "availability": avail.rsplit("/", 1)[-1] if avail else None,
            "rating": _num(rating.get("ratingValue")),
            "review_count": int(_num(rating.get("reviewCount") or rating.get("ratingCount")) or 0) or None,
            "image": image,
            "sku": obj.get("sku") or obj.get("mpn"),
            "source": "json-ld",
        }
    return None


def parse_meta(soup):
    def meta(prop):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return tag.get("content").strip() if tag and tag.get("content") else None

    title = meta("og:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    price = _num(meta("product:price:amount") or meta("og:price:amount"))
    if not (title or price):
        return None
    return {
        "title": unescape(title) if title else None,
        "brand": meta("og:brand") or meta("product:brand"),
        "price": price,
        "currency": meta("product:price:currency") or meta("og:price:currency"),
        "availability": meta("product:availability") or meta("og:availability"),
        "rating": None,
        "review_count": None,
        "image": meta("og:image"),
        "source": "meta",
    }


def fetch(url, timeout):
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def scrape_one(url, timeout=20):
    rec = {"url": url, "retailer": retailer_of(url)}
    if BeautifulSoup is None:
        rec["error"] = "beautifulsoup4 not installed (pip install beautifulsoup4)"
        return rec
    try:
        html = fetch(url, timeout)
    except Exception as exc:  # noqa: BLE001 - report any fetch failure, keep going
        rec["error"] = f"fetch failed: {exc}"
        return rec
    soup = BeautifulSoup(html, "html.parser")
    data = parse_product_jsonld(soup) or parse_meta(soup)
    if not data:
        rec["error"] = "no structured product data found (page may be JS-only or bot-walled)"
        return rec
    rec.update({k: v for k, v in data.items() if v is not None})
    return rec


def load_urls(args):
    urls = list(args.urls)
    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            urls += json.load(fh)
    if args.stdin:
        urls += json.load(sys.stdin)
    seen, out = set(), []
    for u in urls:
        if isinstance(u, dict):
            u = u.get("url")
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main():
    ap = argparse.ArgumentParser(description="Scrape normalized shoe product data from retailer URLs.")
    ap.add_argument("urls", nargs="*", help="Product page URLs")
    ap.add_argument("--input", help="JSON file: array of URLs (or objects with a .url field)")
    ap.add_argument("--stdin", action="store_true", help="Read a JSON array of URLs from stdin")
    ap.add_argument("--output", help="Write results JSON to this path (also prints to stdout)")
    ap.add_argument("--workers", type=int, default=8, help="Concurrent fetches (default 8)")
    ap.add_argument("--timeout", type=int, default=20, help="Per-request timeout seconds (default 20)")
    args = ap.parse_args()

    urls = load_urls(args)
    if not urls:
        ap.error("No URLs provided. Pass URLs as arguments, or use --input FILE / --stdin.")

    results = [None] * len(urls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(scrape_one, u, args.timeout): i for i, u in enumerate(urls)}
        for fut in concurrent.futures.as_completed(futures):
            results[futures[fut]] = fut.result()

    payload = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(payload)
    print(payload)
    ok = sum(1 for r in results if r and "error" not in r)
    print(f"\n# scraped {ok}/{len(results)} OK", file=sys.stderr)


if __name__ == "__main__":
    main()
