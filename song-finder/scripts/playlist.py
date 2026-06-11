#!/usr/bin/env python3
"""
playlist.py - Render a song list as a self-contained HTML playlist page.

Reads song records (the JSON that music.py emits) from --input or stdin and
writes a dark-themed playlist with cover art, 30-second audio previews
(iTunes preview URLs), and per-song YouTube / Spotify / JioSaavn search links.
Songs are grouped by their optional "section" field ("From your singers",
"You might also like"...) and an optional per-song "note" explains the pick.

Zero dependencies, no build step - just open the file in a browser.

Usage:
  python playlist.py --input songs.json --title "Rainy-day Arijit" --open
  python music.py top --artist "Arijit Singh" --json | python playlist.py --title "Top Arijit"
"""
import argparse
import html
import json
import sys
import urllib.parse
import webbrowser

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #121212; color: #eee; font-family: "Segoe UI", system-ui, sans-serif;
         padding: 32px 16px 64px; }}
  .wrap {{ max-width: 760px; margin: 0 auto; }}
  h1 {{ font-size: 1.7rem; margin-bottom: 4px; }}
  .meta {{ color: #999; margin-bottom: 28px; font-size: .9rem; }}
  h2 {{ font-size: 1.05rem; color: #1db954; margin: 28px 0 12px; text-transform: uppercase;
       letter-spacing: .08em; }}
  .song {{ display: flex; gap: 14px; padding: 12px; border-radius: 10px; background: #1b1b1b;
          margin-bottom: 10px; align-items: flex-start; }}
  .song:hover {{ background: #232323; }}
  .art {{ width: 72px; height: 72px; border-radius: 6px; flex: none; object-fit: cover;
         background: #2a2a2a; display: flex; align-items: center; justify-content: center;
         font-size: 1.6rem; }}
  .body {{ flex: 1; min-width: 0; }}
  .t {{ font-weight: 600; font-size: 1.02rem; }}
  .a {{ color: #bbb; font-size: .9rem; margin-top: 2px; }}
  .d {{ color: #777; font-size: .8rem; margin-top: 2px; }}
  .badge {{ display: inline-block; border: 1px solid #555; color: #999; border-radius: 3px;
           font-size: .65rem; padding: 0 4px; margin-left: 6px; vertical-align: 1px; }}
  .note {{ color: #9fd6a9; font-size: .85rem; font-style: italic; margin-top: 6px; }}
  audio {{ width: 100%; height: 30px; margin-top: 8px; }}
  .links {{ margin-top: 8px; display: flex; gap: 10px; flex-wrap: wrap; }}
  .links a {{ color: #1db954; font-size: .8rem; text-decoration: none; border: 1px solid #2c4a35;
             padding: 2px 9px; border-radius: 999px; }}
  .links a:hover {{ background: #1db954; color: #121212; }}
  footer {{ color: #666; font-size: .78rem; margin-top: 36px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>{title}</h1>
  <div class="meta">{count} songs{duration} &middot; previews are 30-second clips &middot; built by song-finder</div>
{sections}
  <footer>Metadata from the iTunes catalog; availability and previews vary by country storefront.
  Use the links to play the full song on your service of choice.</footer>
</div>
</body>
</html>
"""


def esc(value):
    return html.escape(str(value), quote=True) if value not in (None, "") else ""


def search_links(song):
    q = urllib.parse.quote_plus(f"{song.get('title', '')} {song.get('artist', '')}".strip())
    links = []
    if song.get("link"):
        links.append(("iTunes", song["link"]))
    links.append(("YouTube", f"https://www.youtube.com/results?search_query={q}"))
    links.append(("Spotify", f"https://open.spotify.com/search/{q}"))
    links.append(("JioSaavn", f"https://www.jiosaavn.com/search/{q}"))
    return "".join(f'<a href="{esc(url)}" target="_blank" rel="noopener">{name}</a>'
                   for name, url in links)


def render_song(song):
    art = (f'<img class="art" src="{esc(song["artwork"])}" alt="" loading="lazy">'
           if song.get("artwork") else '<div class="art">&#127925;</div>')
    detail_bits = [b for b in (song.get("album"),
                               str(song["year"]) if song.get("year") else None,
                               song.get("genre"),
                               f"{song['duration_s'] // 60}:{song['duration_s'] % 60:02d}"
                               if song.get("duration_s") else None) if b]
    explicit = '<span class="badge">E</span>' if song.get("explicit") else ""
    note = f'<div class="note">{esc(song["note"])}</div>' if song.get("note") else ""
    audio = (f'<audio controls preload="none" src="{esc(song["preview_url"])}"></audio>'
             if song.get("preview_url") else "")
    return f"""  <div class="song">
    {art}
    <div class="body">
      <div class="t">{esc(song.get('title'))}{explicit}</div>
      <div class="a">{esc(song.get('artist'))}</div>
      <div class="d">{esc(' &middot; '.join(detail_bits))}</div>
      {note}{audio}
      <div class="links">{search_links(song)}</div>
    </div>
  </div>"""


def render(songs, title):
    sections = {}
    order = []
    for song in songs:
        name = song.get("section") or "Playlist"
        if name not in sections:
            sections[name] = []
            order.append(name)
        sections[name].append(song)

    blocks = []
    for name in order:
        heading = "" if len(order) == 1 and name == "Playlist" else f"  <h2>{esc(name)}</h2>\n"
        blocks.append(heading + "\n".join(render_song(s) for s in sections[name]))

    total = sum(s.get("duration_s") or 0 for s in songs)
    duration = f" &middot; {total // 3600}h {total % 3600 // 60}m" if total >= 3600 else (
        f" &middot; {total // 60} min" if total else "")
    return PAGE.format(title=esc(title), count=len(songs), duration=duration,
                       sections="\n".join(blocks))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", help="songs JSON file (default: stdin)")
    parser.add_argument("--title", default="Your playlist")
    parser.add_argument("--output", default="playlist.html")
    parser.add_argument("--open", action="store_true", help="open in the browser")
    args = parser.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            songs = json.load(f)
    else:
        songs = json.load(sys.stdin)
    if isinstance(songs, dict):  # tolerate {"songs": [...]} or similar wrappers
        songs = songs.get("songs") or songs.get("data") or []
    if not songs:
        sys.exit("playlist: no songs in input")

    page = render(songs, args.title)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"-> wrote {args.output} ({len(songs)} songs)")
    if args.open:
        webbrowser.open("file://" + str(__import__("pathlib").Path(args.output).resolve()))


if __name__ == "__main__":
    main()
