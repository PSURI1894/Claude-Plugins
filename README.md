# Parth's Claude Code Plugins

A personal [Claude Code](https://claude.com/claude-code) plugin marketplace.

## Add this marketplace

```
/plugin marketplace add PSURI1894/Claude-Plugins
```

(Or from a local clone: `/plugin marketplace add C:\Users\parth\Claude-Plugins`.)

## Plugins

| Plugin | Description |
|---|---|
| [**shoe-shopping-analyzer**](./shoe-shopping-analyzer) | Compare shoes across every available shopping site with deep filters — price/deals, brand/model, size/fit/width, activity, specs, reviews. Live web research + scraping + weighted ranking. |
| [**pg-finder**](./pg-finder) | Find and rank PG (paying guest) accommodation in any city — maps-based 5 km search around your office/college (or the clustered midpoint for a group of 2–3), with gender, budget, AC/non-AC, sharing, food, and amenity filters. Free OSM geocoding + interactive map. |
| [**song-finder**](./song-finder) | Find songs and build playlists from singers (primary), mood, language, genre, and era — plus similar-artist discoveries matched to your taste. Key-less iTunes catalog (verified metadata + 30-sec previews), MusicBrainz + ListenBrainz similarity, interactive HTML playlist. |

Install one with:

```
/plugin install shoe-shopping-analyzer@parth-claude-plugins
/plugin install pg-finder@parth-claude-plugins
/plugin install song-finder@parth-claude-plugins
```

## Repository layout

```
Claude-Plugins/
├── .claude-plugin/
│   └── marketplace.json          # marketplace manifest (lists all plugins)
├── shoe-shopping-analyzer/       # a plugin
│   ├── .claude-plugin/plugin.json
│   ├── commands/                 # /compare-shoes, /shoe-deals
│   ├── skills/                   # shoe-comparison methodology
│   ├── scripts/                  # scrape.py, rank.py, chart.py
│   └── README.md
├── pg-finder/                    # a plugin
│   ├── .claude-plugin/plugin.json
│   ├── commands/                 # /find-pg, /pg-zone
│   ├── skills/                   # pg-search methodology
│   ├── scripts/                  # geo.py, rank.py, map.py (+ sample fixtures)
│   └── README.md
└── song-finder/                  # a plugin
    ├── .claude-plugin/plugin.json
    ├── commands/                 # /find-song, /similar-artists
    ├── skills/                   # song-search methodology
    ├── scripts/                  # music.py, playlist.py (+ sample fixture)
    └── README.md
```

To add another plugin later: create a new top-level folder with its own `.claude-plugin/plugin.json`,
then add an entry to `.claude-plugin/marketplace.json`.
