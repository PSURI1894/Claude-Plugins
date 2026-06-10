#!/usr/bin/env python3
"""
rank.py - Filter and rank normalized PG listings by weighted criteria.

Input: a JSON array of PG records (schema in the pg-search skill) via --input
or stdin, plus optionally the zone JSON produced by `geo.py zone` for
distance-aware filtering and scoring. Applies hard filters, scores each
surviving PG 0-100 with configurable weights, and prints a ranked table
(or JSON with --json).

Usage:
  python rank.py --input pgs.json --zone zone.json --gender male --ac \
      --max-rent 12000 --food veg --chart
  cat pgs.json | python rank.py --zone zone.json --sharing single,double \
      --weights distance=0.5,rent=0.3,rating=0.1,amenities=0.1
"""
import argparse
import json
import math
import sys

EARTH_RADIUS_KM = 6371.0088
DEFAULT_WEIGHTS = {"distance": 0.35, "rent": 0.30, "rating": 0.20, "amenities": 0.15,
                   "reviews": 0.0}

GENDER_MAP = {}
for _g, _alts in {
    "male": ("male", "boys", "boy", "men", "gents", "m"),
    "female": ("female", "girls", "girl", "women", "ladies", "f"),
    "coed": ("coed", "co-ed", "unisex", "any", "both", "mixed", "co-living", "coliving"),
}.items():
    for _a in _alts:
        GENDER_MAP[_a] = _g

SHARE_MAP = {}
for _s, _alts in {
    "single": ("single", "1", "1x", "private", "1-sharing", "one"),
    "double": ("double", "2", "2x", "twin", "2-sharing", "two"),
    "triple": ("triple", "3", "3x", "3-sharing", "three"),
    "quad": ("quad", "4", "4x", "4-sharing", "four"),
    "dorm": ("dorm", "dormitory", "5+"),
}.items():
    for _a in _alts:
        SHARE_MAP[_a] = _s


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def safe(text):
    enc = sys.stdout.encoding or "utf-8"
    return str(text).encode(enc, errors="replace").decode(enc)


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
            sys.exit(f"Bad --weights term: {part!r} "
                     "(use e.g. distance=0.4,rent=0.3,rating=0.2,amenities=0.1)")
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}  # normalize to sum 1


# ------------------------------------------------------------ normalizers


def norm_token(value):
    return str(value).strip().lower().replace("_", "-").replace(" ", "-")


def norm_gender(value):
    if value is None:
        return None
    return GENDER_MAP.get(str(value).strip().lower())


def norm_ac(value):
    if value is True:
        return "ac"
    if value is False:
        return "non-ac"
    if value is None:
        return None
    s = norm_token(value)
    if s in ("ac", "a-c", "a/c", "air-conditioned", "yes"):
        return "ac"
    if s in ("non-ac", "nonac", "no-ac", "no", "fan"):
        return "non-ac"
    if s in ("both", "ac+non-ac", "ac-and-non-ac", "mixed"):
        return "both"
    return None


def norm_sharing(value):
    """Accepts a string or a list; returns a set like {'single','double'}."""
    if value is None:
        return set()
    items = value if isinstance(value, (list, tuple)) else [value]
    out = set()
    for item in items:
        mapped = SHARE_MAP.get(norm_token(item).replace("-sharing", "") or "")
        if mapped is None:
            mapped = SHARE_MAP.get(norm_token(item))
        if mapped:
            out.add(mapped)
    return out


def norm_amenities(value):
    if not value:
        return []
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    return [norm_token(i) for i in items if str(i).strip()]


def food_flags(value):
    """Returns (veg, nonveg, none_ok) or None when the field is unknown."""
    if value is None or str(value).strip() == "":
        return None
    s = str(value).strip().lower()
    none_ok = s in ("none", "no", "no-food", "no food", "self-cooking",
                    "kitchen-only", "kitchen only", "self")
    nonveg = any(t in s for t in ("non-veg", "nonveg", "non veg"))
    stripped = s.replace("non-veg", "").replace("nonveg", "").replace("non veg", "")
    veg = "veg" in stripped or "meals" in s or "food included" in s
    return (veg, nonveg, none_ok)


# ------------------------------------------------------------ distances


def annotate_distances(pgs, zone):
    if not zone:
        return
    c = zone["centroid"]
    anchors = zone.get("anchors", [])
    for p in pgs:
        lat, lon = p.get("lat"), p.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            p["_dist_centroid_km"] = None
            p["_dist_worst_km"] = None
            continue
        p["_dist_centroid_km"] = round(haversine_km(lat, lon, c["lat"], c["lon"]), 2)
        per = {a["label"]: round(haversine_km(lat, lon, a["lat"], a["lon"]), 2)
               for a in anchors}
        if per:
            p["_dist_km"] = per
            p["_dist_worst_km"] = max(per.values())
        else:
            p["_dist_worst_km"] = p["_dist_centroid_km"]


# ------------------------------------------------------------ filtering


def passes_filters(p, args, zone):
    if "error" in p:
        return False
    if args.gender:
        g = norm_gender(p.get("gender"))
        if g is None or (g != args.gender and g != "coed"):
            return False
    rent = p.get("rent")
    if args.max_rent is not None and (rent is None or rent > args.max_rent):
        return False
    if args.min_rent is not None and (rent is None or rent < args.min_rent):
        return False
    if args.ac_pref:
        a = norm_ac(p.get("ac"))
        if a is None or (a != args.ac_pref and a != "both"):
            return False
    if args.sharing:
        wanted = {SHARE_MAP.get(norm_token(t)) for t in args.sharing.split(",") if t.strip()}
        wanted.discard(None)
        if not wanted & norm_sharing(p.get("sharing")):
            return False
    if args.food:
        flags = food_flags(p.get("food"))
        if flags is None:
            return False
        veg, nonveg, none_ok = flags
        if args.food == "veg" and not veg:
            return False
        if args.food == "nonveg" and not nonveg:
            return False
        if args.food == "any" and not (veg or nonveg):
            return False
        if args.food == "none" and not none_ok:
            return False
    if args.amenities:
        have = norm_amenities(p.get("amenities"))
        for req in (norm_token(t) for t in args.amenities.split(",") if t.strip()):
            if not any(req in h or h in req for h in have):
                return False
    if args.min_rating is not None and (p.get("rating") is None or p["rating"] < args.min_rating):
        return False
    if zone:
        dc = p.get("_dist_centroid_km")
        if dc is None:
            if not args.keep_unlocated:
                return False
        else:
            if args.max_distance is not None and dc > args.max_distance:
                return False
            if args.worst_within is not None and (p.get("_dist_worst_km") or dc) > args.worst_within:
                return False
    return True


# ------------------------------------------------------------ scoring


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


def score_all(pgs, weights, prefer):
    dist_n = normalizer([p.get("_dist_worst_km") for p in pgs], invert=True)
    rent_n = normalizer([p.get("rent") for p in pgs], invert=True)
    rating_n = normalizer([p.get("rating") for p in pgs])
    review_conf = [math.log10(p["review_count"] + 1) if p.get("review_count") else None
                   for p in pgs]
    reviews_n = normalizer(review_conf)
    prefer_tokens = [norm_token(t) for t in prefer.split(",") if t.strip()] if prefer else None
    amen_counts = [len(norm_amenities(p.get("amenities"))) or None for p in pgs]
    amen_n = normalizer(amen_counts)

    for p, rc, ac_count in zip(pgs, review_conf, amen_counts):
        if prefer_tokens:
            have = norm_amenities(p.get("amenities"))
            amen_score = sum(1 for t in prefer_tokens
                             if any(t in h or h in t for h in have)) / len(prefer_tokens)
        else:
            amen_score = amen_n(ac_count)
        s = (weights.get("distance", 0) * dist_n(p.get("_dist_worst_km"))
             + weights.get("rent", 0) * rent_n(p.get("rent"))
             + weights.get("rating", 0) * rating_n(p.get("rating"))
             + weights.get("reviews", 0) * reviews_n(rc)
             + weights.get("amenities", 0) * amen_score)
        p["_score"] = round(100 * s, 1)
    return sorted(pgs, key=lambda p: p["_score"], reverse=True)


# ------------------------------------------------------------ output


def money(value, currency):
    if value is None:
        return "-"
    sym = {"INR": "₹", "USD": "$", "EUR": "€"}.get((currency or "INR").upper())
    txt = f"{sym}{value:,.0f}" if sym else f"{value:,.0f} {currency}"
    try:
        txt.encode(sys.stdout.encoding or "utf-8")
    except (UnicodeEncodeError, LookupError):
        txt = f"Rs {value:,.0f}" if (currency or "INR").upper() == "INR" else f"{value:,.0f} {currency}"
    return txt


def fmt_share(p):
    order = ("single", "double", "triple", "quad", "dorm")
    abbrev = {"single": "1x", "double": "2x", "triple": "3x", "quad": "4x", "dorm": "dorm"}
    have = norm_sharing(p.get("sharing"))
    return "/".join(abbrev[s] for s in order if s in have) or "-"


def fmt_table(ranked, group):
    dist_hdr = "KM*" if group else "KM"
    header = (f"{'#':>2}  {'SCORE':>5}  {'RENT':>9}  {'SHARE':<6}  {'AC':<4}  "
              f"{'G':<3}  {dist_hdr:>5}  {'RATING':>10}  NAME / AREA")
    lines = [header, "-" * len(header)]
    gender_abbrev = {"male": "M", "female": "F", "coed": "Co"}
    for i, p in enumerate(ranked, 1):
        rent = money(p.get("rent"), p.get("currency"))
        ac = {"ac": "AC", "non-ac": "non", "both": "both"}.get(norm_ac(p.get("ac")), "-")
        g = gender_abbrev.get(norm_gender(p.get("gender")), "-")
        d = p.get("_dist_worst_km")
        dist = f"{d:.1f}" if d is not None else "?"
        rating = (f"{p['rating']:.1f} ({p.get('review_count') or 0})"
                  if p.get("rating") is not None else "-")
        area = (p.get("address") or "").split(",")[0].strip()
        name = (p.get("name") or "-")[:34]
        label = f"{name} - {area[:22]}" if area else name
        lines.append(f"{i:>2}  {p['_score']:>5}  {rent:>9}  {fmt_share(p):<6}  {ac:<4}  "
                     f"{g:<3}  {dist:>5}  {rating:>10}  {label}")
    if group:
        lines.append("")
        lines.append("* KM = worst member's straight-line distance "
                     "(per-member breakdown in --json output)")
    return "\n".join(lines)


def fmt_chart(ranked, width=32):
    """ASCII horizontal bar chart of scores - zero-dependency, terminal-friendly."""
    if not ranked:
        return "No PGs to chart."
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
        rent = money(p.get("rent"), p.get("currency"))
        d = p.get("_dist_worst_km")
        dist = f"{d:.1f}km" if d is not None else "?km"
        name = (p.get("name") or "-")[:30]
        lines.append(f"{i:>2}. {name:<30} |{bar}| {p['_score']:>5}  {rent:>9}  {dist:>7}")
    return "\n".join(lines)


# ------------------------------------------------------------ main


def main():
    ap = argparse.ArgumentParser(description="Filter and rank normalized PG listings.")
    ap.add_argument("--input", help="PG listings JSON file (default: read stdin)")
    ap.add_argument("--zone", help="zone JSON from `geo.py zone` (enables distance logic)")
    ap.add_argument("--gender", choices=["male", "female", "coed"],
                    help="seeker's gender; keeps matching + coed PGs")
    ap.add_argument("--max-rent", type=float, help="drop PGs above this monthly rent")
    ap.add_argument("--min-rent", type=float, help="drop PGs below this monthly rent")
    acg = ap.add_mutually_exclusive_group()
    acg.add_argument("--ac", dest="ac_pref", action="store_const", const="ac",
                     help="require AC rooms (PGs offering both also pass)")
    acg.add_argument("--non-ac", dest="ac_pref", action="store_const", const="non-ac",
                     help="require non-AC rooms (PGs offering both also pass)")
    ap.add_argument("--sharing", help="comma list to keep: single,double,triple,quad,dorm")
    ap.add_argument("--food", choices=["veg", "nonveg", "any", "none"],
                    help="meal requirement (unknown food info fails the filter)")
    ap.add_argument("--amenities", help="comma list that must ALL be present, e.g. wifi,laundry")
    ap.add_argument("--prefer", help="comma list of nice-to-have amenities (scored, not filtered)")
    ap.add_argument("--min-rating", type=float, help="drop PGs rated below this (0-5)")
    ap.add_argument("--max-distance", type=float,
                    help="km from zone centre (default: the zone's radius)")
    ap.add_argument("--worst-within", type=float,
                    help="km that EVERY member's anchor must be within (strict group mode)")
    ap.add_argument("--keep-unlocated", action="store_true",
                    help="keep records without lat/lon despite distance filters")
    ap.add_argument("--weights",
                    help="e.g. distance=0.4,rent=0.3,rating=0.2,amenities=0.1 (auto-normalized)")
    ap.add_argument("--top", type=int, default=0, help="limit output to the top N")
    ap.add_argument("--json", action="store_true", help="emit ranked JSON instead of a table")
    ap.add_argument("--chart", action="store_true", help="also print an ASCII score bar chart")
    args = ap.parse_args()

    pgs = load(args)
    if not isinstance(pgs, list):
        sys.exit("Input must be a JSON array of PG records.")

    zone = None
    if args.zone:
        with open(args.zone, encoding="utf-8") as fh:
            zone = json.load(fh)
        if args.max_distance is None:
            args.max_distance = zone.get("radius_km")

    annotate_distances(pgs, zone)
    weights = parse_weights(args.weights)
    kept = [p for p in pgs if passes_filters(p, args, zone)]
    ranked = score_all(kept, weights, args.prefer)
    if args.top:
        ranked = ranked[: args.top]

    group = bool(zone and len(zone.get("anchors", [])) > 1)
    if args.json:
        print(json.dumps(ranked, indent=2, ensure_ascii=True))
    elif ranked:
        print(safe(fmt_table(ranked, group)))
        if args.chart:
            print(safe(fmt_chart(ranked)))
    else:
        print("No PGs passed the filters.")
    shown = f"; showing top {len(ranked)}" if args.top and len(ranked) < len(kept) else ""
    print(f"\n# {len(kept)} of {len(pgs)} PGs passed filters{shown} | weights: {weights}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
