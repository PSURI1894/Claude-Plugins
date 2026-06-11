#!/usr/bin/env python3
"""
queue.py - Turn a songs JSON (from music.py) into a playable queue.

Key-less, zero dependencies. What each service gets:
  youtube     A true one-click queue: each song is resolved to its top YouTube
              video (search-page scrape, throttled), then chained into an
              anonymous playlist via youtube.com/watch_videos?video_ids=...
  ytmusic     Same resolution; emits a music.youtube.com variant of the queue
              link (best-effort - the YouTube link is the verified fallback).
  spotify     No key-less queue API (OAuth only), so this writes a clean
  applemusic  "Artist - Title" tracklist you can import as a playlist in one
              paste via TuneMyMusic / Soundiiz, plus the per-song links already
              in the playlist HTML.

Resolved video ids are written back into the songs JSON (--save) so
playlist.py can render direct YouTube links and a "Play all" button,
and re-runs skip already-resolved songs.

Usage:
  python queue.py --input songs.json --service youtube --save songs.json --open
  python queue.py --input songs.json --service spotify --export tracklist.txt
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

SEARCH_URL = "https://www.youtube.com/results"
WATCH_VIDEOS_URL = "https://www.youtube.com/watch_videos?video_ids="
QUEUE_CAP = 50  # watch_videos silently truncates beyond ~50 ids
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) song-finder-claude-plugin/1.1"
VIDEO_ID_RE = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')

_last_request = 0.0


def safe(text):
    """Make any string printable on the current console (Windows cp1252 etc.)."""
    enc = sys.stdout.encoding or "utf-8"
    return str(text).encode(enc, errors="replace").decode(enc)


def _throttle(min_interval=1.1):
    """Be polite to YouTube: one search per second is plenty."""
    global _last_request
    wait = _last_request + min_interval - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def resolve_video_id(title, artist):
    """Top YouTube result's video id for 'title artist', or None."""
    _throttle()
    params = urllib.parse.urlencode({
        "search_query": f"{title} {artist}", "gl": "US", "hl": "en"})
    req = urllib.request.Request(
        SEARCH_URL + "?" + params,
        headers={"User-Agent": USER_AGENT, "Cookie": "CONSENT=YES+; SOCS=CAI"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(safe(f"  ! youtube search failed for {title!r}: {exc}"), file=sys.stderr)
        return None
    match = VIDEO_ID_RE.search(page)
    return match.group(1) if match else None


def resolve_all(songs):
    """Fill youtube_id/youtube_url on each song (skips already-resolved ones)."""
    todo = [s for s in songs if not s.get("youtube_id")]
    if todo:
        print(safe(f"resolving {len(todo)} song(s) on YouTube "
                   f"(~{len(todo)} sec, throttled)..."))
    for song in todo:
        vid = resolve_video_id(song.get("title", ""), song.get("artist", ""))
        if vid:
            song["youtube_id"] = vid
            song["youtube_url"] = f"https://www.youtube.com/watch?v={vid}"
            print(safe(f"  + {song.get('title')} -> {vid}"))
        else:
            print(safe(f"  ? no video found for {song.get('title')}"), file=sys.stderr)
    return songs


def queue_url(songs, domain="www.youtube.com"):
    ids = [s["youtube_id"] for s in songs if s.get("youtube_id")][:QUEUE_CAP]
    if not ids:
        return None
    return f"https://{domain}/watch_videos?video_ids=" + ",".join(ids)


def write_tracklist(songs, path):
    """One 'Artist - Title' per line - the format playlist importers accept."""
    with open(path, "w", encoding="utf-8") as f:
        for s in songs:
            f.write(f"{s.get('artist', '?')} - {s.get('title', '?')}\n")
    print(safe(f"-> wrote {path} ({len(songs)} lines)"))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", help="songs JSON file (default: stdin)")
    parser.add_argument("--service", default="youtube",
                        choices=["youtube", "ytmusic", "spotify", "applemusic"],
                        help="where the user wants to play the list")
    parser.add_argument("--save", metavar="FILE",
                        help="write songs JSON back with youtube_id/youtube_url "
                             "filled in (lets playlist.py render a Play-all button)")
    parser.add_argument("--export", metavar="FILE",
                        help="write an 'Artist - Title' tracklist (default on for "
                             "spotify/applemusic)")
    parser.add_argument("--open", action="store_true", help="open the queue link")
    args = parser.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            songs = json.load(f)
    else:
        songs = json.load(sys.stdin)
    if isinstance(songs, dict):
        songs = songs.get("songs") or songs.get("data") or []
    if not songs:
        sys.exit("queue: no songs in input")

    link = None
    if args.service in ("youtube", "ytmusic"):
        songs = resolve_all(songs)
        if args.save:
            with open(args.save, "w", encoding="utf-8") as f:
                json.dump(songs, f, ensure_ascii=False, indent=2)
            print(safe(f"-> saved resolved ids to {args.save}"))
        link = queue_url(songs)
        if not link:
            sys.exit("queue: no songs could be resolved on YouTube")
        resolved = sum(1 for s in songs if s.get("youtube_id"))
        print(safe(f"\nQueue ({resolved}/{len(songs)} songs, plays in order):"))
        print(safe(f"  {link}"))
        if args.service == "ytmusic":
            print(safe("YouTube Music variant (best-effort - use the link above "
                       "if it doesn't autoplay):"))
            print(safe(f"  {queue_url(songs, domain='music.youtube.com')}"))
    else:
        export = args.export or f"{args.service}-tracklist.txt"
        write_tracklist(songs, export)
        service_name = "Spotify" if args.service == "spotify" else "Apple Music"
        print(safe(f"\n{service_name} has no key-less queue API. To get this as a "
                   f"playlist there in one paste:"))
        print(safe("  1. Open https://www.tunemymusic.com/transfer (or soundiiz.com)"))
        print(safe(f"  2. Source: 'Any text' / 'File' -> paste or upload {export}"))
        print(safe(f"  3. Destination: {service_name} -> it matches the tracks and "
                   f"creates the playlist"))

    if args.export and args.service in ("youtube", "ytmusic"):
        write_tracklist(songs, args.export)
    if args.open and link:
        webbrowser.open(link)


if __name__ == "__main__":
    main()
