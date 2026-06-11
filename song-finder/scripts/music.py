#!/usr/bin/env python3
"""
music.py - Key-less music data CLI for song finding.

Zero external dependencies (pure standard library) and no API keys:
  - Songs come from the iTunes Search API (per-country storefronts, so
    --country IN surfaces Hindi/Punjabi/Tamil results, KR surfaces K-pop...).
  - Similar artists come from MusicBrainz (name -> MBID, throttled to its
    1 req/sec policy) + the ListenBrainz Labs similarity endpoint.

Subcommands:
  search   Search songs by free text and/or artist, with genre/year/explicit
           filters. Merges + dedupes into a JSON candidate pool.
  top      An artist's popular songs (iTunes storefront relevance order).
  similar  Artists similar to a seed singer (listener-data based), optionally
           with 1-2 signature tracks each.

Usage:
  python music.py search --query "tum hi ho" --country IN --output songs.json
  python music.py top --artist "Arijit Singh" --country IN --limit 15 --output songs.json --append
  python music.py similar --artist "Arijit Singh" --limit 8 --with-top 2
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ITUNES_URL = "https://itunes.apple.com/search"
MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/artist/"
LISTENBRAINZ_URL = "https://labs.api.listenbrainz.org/similar-artists/json"
# ListenBrainz Labs requires naming the dataset snapshot; this one is current
# as of mid-2026 and may need updating if the endpoint starts returning [].
LISTENBRAINZ_ALGORITHM = ("session_based_days_7500_session_300_contribution_5"
                          "_threshold_10_limit_100_filter_True_skip_30")
USER_AGENT = "song-finder-claude-plugin/1.0 (https://github.com/PSURI1894/Claude-Plugins)"

_last_mb_request = 0.0


def safe(text):
    """Make any string printable on the current console (Windows cp1252 etc.)."""
    enc = sys.stdout.encoding or "utf-8"
    return str(text).encode(enc, errors="replace").decode(enc)


def _get_json(url, params, timeout=20):
    """GET url?params, parse JSON; return None on any failure (logged to stderr)."""
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(safe(f"  ! request failed ({url.split('//')[1].split('/')[0]}): {exc}"),
              file=sys.stderr)
        return None


def _throttle_musicbrainz(min_interval=1.1):
    """MusicBrainz usage policy: at most 1 request per second."""
    global _last_mb_request
    wait = _last_mb_request + min_interval - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_mb_request = time.monotonic()


# ---------------------------------------------------------------- songs

def _norm_key(title, artist):
    """Dedupe key: ignore case, punctuation, and bracketed suffixes like
    '(From "Aashiqui 2")' or '[Remastered]' that create near-duplicates."""
    t = re.sub(r"[\(\[].*?[\)\]]", "", title or "")
    t = re.sub(r"[^a-z0-9\u0080-\uffff]+", "", t.lower())
    a = re.split(r",|&| feat\.?| ft\.?| x ", (artist or "").lower())[0]
    a = re.sub(r"[^a-z0-9\u0080-\uffff]+", "", a)
    return (t, a)


def _itunes_song_record(hit, country):
    year = None
    if hit.get("releaseDate"):
        try:
            year = int(hit["releaseDate"][:4])
        except ValueError:
            pass
    duration = round(hit["trackTimeMillis"] / 1000) if hit.get("trackTimeMillis") else None
    return {
        "title": hit.get("trackName"),
        "artist": hit.get("artistName"),
        "album": hit.get("collectionName"),
        "genre": hit.get("primaryGenreName"),
        "year": year,
        "duration_s": duration,
        "explicit": hit.get("trackExplicitness") == "explicit",
        "preview_url": hit.get("previewUrl"),
        "link": hit.get("trackViewUrl"),
        "artwork": hit.get("artworkUrl100"),
        "country_store": country,
        "source": "itunes",
        "section": None,
        "note": None,
    }


def itunes_search(term, country="US", limit=25):
    """Search the iTunes catalog; returns a list of normalized song records."""
    data = _get_json(ITUNES_URL, {
        "term": term, "media": "music", "entity": "song",
        "limit": min(limit, 200), "country": country,
    })
    if not data:
        return []
    return [_itunes_song_record(h, country) for h in data.get("results", [])
            if h.get("trackName") and h.get("artistName")]


def merge_songs(existing, new):
    """Append new records to existing, deduping; later dupes fill null fields."""
    by_key = {}
    order = []
    for rec in list(existing) + list(new):
        key = _norm_key(rec.get("title"), rec.get("artist"))
        if key in by_key:
            kept = by_key[key]
            for field, value in rec.items():
                if kept.get(field) in (None, "") and value not in (None, ""):
                    kept[field] = value
        else:
            by_key[key] = dict(rec)
            order.append(key)
    return [by_key[k] for k in order]


def filter_songs(songs, genre=None, year_from=None, year_to=None,
                 exact_artist=None, clean=False):
    out = []
    for s in songs:
        if genre and genre.lower() not in (s.get("genre") or "").lower():
            continue
        if year_from and s.get("year") and s["year"] < year_from:
            continue
        if year_to and s.get("year") and s["year"] > year_to:
            continue
        if exact_artist and exact_artist.lower() not in (s.get("artist") or "").lower():
            continue
        if clean and s.get("explicit"):
            continue
        out.append(s)
    return out


_DERIVATIVE = re.compile(
    r"remix|mashup|vocals only|sped.?up|slowed|reverb|lo-?fi|unplugged|karaoke|"
    r"instrumental|cover|acoustic|live|jukebox|medley|8d audio", re.IGNORECASE)


def is_derivative(title):
    """True for remixes/edits that crowd out the original recording."""
    return bool(_DERIVATIVE.search(title or ""))


def artist_top_songs(artist, country="US", limit=10, include_remixes=False):
    """An artist's popular songs: iTunes search by artist name (storefront
    relevance order ~ popularity), filtered to that artist, deduped.
    Remixes/edits are dropped unless include_remixes."""
    raw = itunes_search(artist, country=country, limit=200)
    mine = filter_songs(raw, exact_artist=artist)
    if not include_remixes:
        mine = [s for s in mine if not is_derivative(s.get("title"))]
    return merge_songs([], mine)[:limit]


# ---------------------------------------------------------------- artists

def musicbrainz_artist(name):
    """Resolve an artist name to {name, mbid} via MusicBrainz, or None."""
    _throttle_musicbrainz()
    data = _get_json(MUSICBRAINZ_URL, {
        "query": f"artist:{name}", "fmt": "json", "limit": 1,
    })
    if not data or not data.get("artists"):
        return None
    hit = data["artists"][0]
    return {"name": hit["name"], "mbid": hit["id"],
            "disambiguation": hit.get("disambiguation", "")}


def listenbrainz_similar(mbid, limit=10):
    """Similar artists from ListenBrainz listener data: [{name, mbid, score}]."""
    data = _get_json(LISTENBRAINZ_URL, {
        "artist_mbids": mbid, "algorithm": LISTENBRAINZ_ALGORITHM,
    }, timeout=30)
    if not data:
        return []
    return [{"name": a["name"], "mbid": a["artist_mbid"], "score": a.get("score")}
            for a in data[:limit]]


# ---------------------------------------------------------------- output

def emit(payload, summary_lines, output=None, as_json=False, append=False):
    """Write JSON to --output (merging songs if --append), print a summary.
    With --json, the JSON goes to stdout and the summary to stderr (pipeable)."""
    if output:
        if append and isinstance(payload, list):
            try:
                with open(output, encoding="utf-8") as f:
                    payload = merge_songs(json.load(f), payload)
            except (FileNotFoundError, ValueError):
                pass
        with open(output, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        summary_lines.append(f"-> wrote {len(payload) if isinstance(payload, list) else 1} "
                             f"record(s) to {output}")
    stream = sys.stderr if as_json else sys.stdout
    for line in summary_lines:
        print(safe(line), file=stream)
    if as_json:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        print()


def _song_summary(songs):
    lines = []
    for i, s in enumerate(songs, 1):
        bits = [s.get("artist") or "?"]
        if s.get("year"):
            bits.append(str(s["year"]))
        if s.get("genre"):
            bits.append(s["genre"])
        preview = "preview" if s.get("preview_url") else "no preview"
        lines.append(f"{i:3}. {s.get('title')} - {' | '.join(bits)} [{preview}]")
    return lines


# ---------------------------------------------------------------- commands

def cmd_search(args):
    term = " ".join(filter(None, [args.query, args.artist]))
    if not term:
        sys.exit("search: provide --query and/or --artist")
    songs = itunes_search(term, country=args.country, limit=args.limit)
    songs = filter_songs(songs, genre=args.genre, year_from=args.year_from,
                         year_to=args.year_to,
                         exact_artist=args.artist if args.exact_artist else None,
                         clean=args.clean)
    songs = merge_songs([], songs)
    lines = [f"search {term!r} (store: {args.country}) -> {len(songs)} song(s)"]
    lines += _song_summary(songs)
    emit(songs, lines, output=args.output, as_json=args.json, append=args.append)


def cmd_top(args):
    songs = artist_top_songs(args.artist, country=args.country, limit=args.limit,
                             include_remixes=args.include_remixes)
    lines = [f"top songs for {args.artist!r} (store: {args.country}) -> {len(songs)}"]
    lines += _song_summary(songs)
    emit(songs, lines, output=args.output, as_json=args.json, append=args.append)


def cmd_similar(args):
    seed = musicbrainz_artist(args.artist)
    if not seed:
        sys.exit(f"similar: could not resolve artist {args.artist!r} on MusicBrainz")
    similar = listenbrainz_similar(seed["mbid"], limit=args.limit)
    if not similar:
        sys.exit(f"similar: no similarity data for {seed['name']!r} "
                 "(endpoint down, or the LISTENBRAINZ_ALGORITHM constant is stale)")
    lines = [f"artists similar to {seed['name']} "
             f"({seed['disambiguation'] or 'MusicBrainz'}):"]
    for i, a in enumerate(similar, 1):
        lines.append(f"{i:3}. {a['name']} (similarity score {a['score']})")
        if args.with_top:
            a["top_tracks"] = artist_top_songs(a["name"], country=args.country,
                                               limit=args.with_top)
            for t in a["top_tracks"]:
                lines.append(f"       - {t['title']}" +
                             (f" ({t['year']})" if t.get("year") else ""))
    payload = {"seed": seed, "similar": similar}
    emit(payload, lines, output=args.output, as_json=args.json)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, song_pool=True):
        p.add_argument("--country", default="US",
                       help="iTunes storefront (IN, US, GB, KR, JP, BR...) - "
                            "pick by target language")
        p.add_argument("--output", help="write JSON records to this file")
        p.add_argument("--json", action="store_true",
                       help="print JSON to stdout (summary goes to stderr)")
        if song_pool:
            p.add_argument("--append", action="store_true",
                           help="merge into --output if it exists (deduped)")

    p = sub.add_parser("search", help="search songs by text/artist")
    p.add_argument("--query", help="free text: song title, mood words, anything")
    p.add_argument("--artist", help="artist name (added to the search)")
    p.add_argument("--exact-artist", action="store_true",
                   help="keep only results actually by --artist")
    p.add_argument("--genre", help="keep only this genre (substring match)")
    p.add_argument("--year-from", type=int)
    p.add_argument("--year-to", type=int)
    p.add_argument("--clean", action="store_true", help="drop explicit tracks")
    p.add_argument("--limit", type=int, default=25)
    common(p)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("top", help="an artist's popular songs")
    p.add_argument("--artist", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--include-remixes", action="store_true",
                   help="keep remixes/sped-up/vocals-only edits (dropped by default)")
    common(p)
    p.set_defaults(func=cmd_top)

    p = sub.add_parser("similar", help="similar artists (MusicBrainz + ListenBrainz)")
    p.add_argument("--artist", required=True, help="seed singer")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--with-top", type=int, default=0, metavar="N",
                   help="also fetch N signature tracks per similar artist")
    common(p, song_pool=False)
    p.set_defaults(func=cmd_similar)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
