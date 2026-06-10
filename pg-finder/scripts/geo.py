#!/usr/bin/env python3
"""
geo.py - Geocoding and search-zone geometry for PG hunting.

Zero external dependencies (pure standard library). Geocoding uses the free
OpenStreetMap Nominatim service - no API key needed. Nominatim's usage policy
allows ~1 request/second; this script throttles itself to respect that.

Subcommands:
  zone   Geocode 1-3 anchor locations (one per person: their office, college,
         or preferred spot), compute the group midpoint, and emit a search
         circle (default 5 km) as zone JSON with map links.
  fill   Batch-geocode missing "lat"/"lon" fields in a PG listings JSON file
         from each record's "address".

Usage:
  python geo.py zone --anchor "Infosys Gate 4, Electronic City, Bengaluru" --output zone.json
  python geo.py zone --anchor "Rahul=Embassy Tech Village, Bengaluru" \
      --anchor "Priya=Christ University, Hosur Road, Bengaluru" --radius 5 --output zone.json
  python geo.py fill --input pgs.json --city Bengaluru
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "pg-finder-claude-plugin/1.0 (https://github.com/PSURI1894/Claude-Plugins)"
EARTH_RADIUS_KM = 6371.0088
DEFAULT_RADIUS_KM = 5.0

_last_request = 0.0


def _throttle(min_interval=1.1):
    """Nominatim usage policy: at most 1 request per second."""
    global _last_request
    wait = _last_request + min_interval - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def geocode(query, timeout=20):
    """Resolve free-text location to {lat, lon, display_name}, or None."""
    _throttle()
    params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "limit": 1})
    req = urllib.request.Request(NOMINATIM_URL + "?" + params,
                                 headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            hits = json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(safe(f"  ! geocoding error for {query!r}: {exc}"), file=sys.stderr)
        return None
    if not hits:
        return None
    hit = hits[0]
    return {"lat": float(hit["lat"]), "lon": float(hit["lon"]),
            "display_name": hit.get("display_name", "")}


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def safe(text):
    """Make any string printable on the current console (Windows cp1252 etc.)."""
    enc = sys.stdout.encoding or "utf-8"
    return str(text).encode(enc, errors="replace").decode(enc)


def map_links(lat, lon):
    return {
        "openstreetmap": f"https://www.openstreetmap.org/?mlat={lat:.5f}&mlon={lon:.5f}#map=13/{lat:.5f}/{lon:.5f}",
        "google_maps_pg_search": f"https://www.google.com/maps/search/pg+paying+guest/@{lat:.5f},{lon:.5f},13z",
    }


# ---------------------------------------------------------------- zone


def cmd_zone(args):
    anchors = []
    for i, raw in enumerate(args.anchor, 1):
        label, sep, query = raw.partition("=")
        if not sep:
            label, query = f"Person {i}", raw
        label, query = label.strip(), query.strip()
        hit = geocode(query)
        if hit is None:
            sys.exit(f"Could not geocode anchor {i}: {query!r}. "
                     "Use a more specific address or append the city name.")
        anchors.append({"label": label, "query": query, **hit})

    if len(anchors) > 3:
        print("note: more than 3 anchors given; the midpoint math still works, "
              "but satisfying every commute gets harder.", file=sys.stderr)

    lat_c = sum(a["lat"] for a in anchors) / len(anchors)
    lon_c = sum(a["lon"] for a in anchors) / len(anchors)
    for a in anchors:
        a["centroid_km"] = round(haversine_km(a["lat"], a["lon"], lat_c, lon_c), 2)

    pairwise = []
    for i in range(len(anchors)):
        for j in range(i + 1, len(anchors)):
            pairwise.append({
                "a": anchors[i]["label"], "b": anchors[j]["label"],
                "km": round(haversine_km(anchors[i]["lat"], anchors[i]["lon"],
                                         anchors[j]["lat"], anchors[j]["lon"]), 2),
            })

    radius = args.radius
    worst_centroid = max(a["centroid_km"] for a in anchors)
    guaranteed = round(max(0.0, radius - worst_centroid), 2)
    all_reachable = all(p["km"] <= 2 * radius for p in pairwise)

    notes = []
    if len(anchors) == 1:
        notes.append(f"Solo search: every PG within {radius:g} km of the anchor qualifies.")
    elif all_reachable:
        notes.append(f"Group search: the {radius:g} km circle is centred on the group "
                     "midpoint; check each member's distance per listing.")
        if guaranteed > 0:
            notes.append(f"Any PG within {guaranteed:g} km of the midpoint is automatically "
                         f"within {radius:g} km of every member.")
    else:
        bad = ", ".join(f"{p['a']} <-> {p['b']} = {p['km']:g} km"
                        for p in pairwise if p["km"] > 2 * radius)
        notes.append(f"Heads-up: no single point can be within {radius:g} km of everyone "
                     f"({bad}). The midpoint minimises the worst commute; consider a "
                     "bigger --radius or searching along the corridor between anchors.")

    zone = {
        "radius_km": radius,
        "anchors": anchors,
        "centroid": {"lat": round(lat_c, 6), "lon": round(lon_c, 6)},
        "pairwise_km": pairwise,
        "guaranteed_radius_km": guaranteed,
        "all_reachable": all_reachable,
        "map_links": map_links(lat_c, lon_c),
        "notes": notes,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(zone, fh, indent=2, ensure_ascii=False)
        print(f"Wrote {os.path.abspath(args.output)}")
        summarize(zone, sys.stdout)
    else:
        print(json.dumps(zone, indent=2, ensure_ascii=True))
        summarize(zone, sys.stderr)


def summarize(zone, out):
    c = zone["centroid"]
    print(safe(f"\nSearch zone: centre ({c['lat']:.5f}, {c['lon']:.5f}), "
               f"radius {zone['radius_km']:g} km"), file=out)
    for a in zone["anchors"]:
        print(safe(f"  - {a['label']}: {a['query']} -> {a['display_name'][:70]} "
                   f"({a['centroid_km']:g} km from centre)"), file=out)
    for p in zone["pairwise_km"]:
        print(safe(f"  - {p['a']} <-> {p['b']}: {p['km']:g} km apart"), file=out)
    print(safe(f"  Map: {zone['map_links']['openstreetmap']}"), file=out)
    print(safe(f"  PGs nearby: {zone['map_links']['google_maps_pg_search']}"), file=out)
    for n in zone["notes"]:
        print(safe(f"  * {n}"), file=out)


# ---------------------------------------------------------------- fill


def cmd_fill(args):
    with open(args.input, encoding="utf-8") as fh:
        records = json.load(fh)
    if not isinstance(records, list):
        sys.exit("Input must be a JSON array of PG records.")

    done = skipped = failed = 0
    for rec in records:
        lat, lon = rec.get("lat"), rec.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            skipped += 1
            continue
        address = (rec.get("address") or "").strip()
        if not address:
            failed += 1
            continue
        query = address
        if args.city and args.city.lower() not in address.lower():
            query = f"{address}, {args.city}"
        hit = geocode(query)
        if hit:
            rec["lat"], rec["lon"] = hit["lat"], hit["lon"]
            rec["geocoded_from"] = query
            done += 1
        else:
            failed += 1
            print(safe(f"  ! no match for: {query}"), file=sys.stderr)

    out_path = args.output or args.input
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    print(f"Geocoded {done}, already had coords {skipped}, failed {failed} "
          f"-> {os.path.abspath(out_path)}")
    if failed:
        print("hint: make failed records' \"address\" more specific (add locality + city), "
              "or set coordinates manually from the listing's map pin.", file=sys.stderr)


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(description="Geocoding and search-zone geometry for PG hunting.")
    sub = ap.add_subparsers(dest="command", required=True)

    zp = sub.add_parser("zone", help="build the search zone from 1-3 anchor locations")
    zp.add_argument("--anchor", action="append", required=True,
                    help='repeatable, one per person; "Label=address" or just "address"')
    zp.add_argument("--radius", type=float, default=DEFAULT_RADIUS_KM,
                    help=f"search radius in km (default {DEFAULT_RADIUS_KM:g})")
    zp.add_argument("--output", help="write zone JSON here (default: print to stdout)")
    zp.set_defaults(func=cmd_zone)

    fp = sub.add_parser("fill", help="geocode missing lat/lon in a PG listings JSON")
    fp.add_argument("--input", required=True, help="PG listings JSON array")
    fp.add_argument("--city", help="city name appended to addresses that lack it")
    fp.add_argument("--output", help="output path (default: overwrite --input)")
    fp.set_defaults(func=cmd_fill)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
