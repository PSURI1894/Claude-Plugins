# Parth's Claude Code Plugins

A personal [Claude Code](https://claude.com/claude-code) plugin marketplace.

## Add this marketplace

```
/plugin marketplace add C:\Users\parth\Claude-Plugins
```

(Or, once pushed to GitHub: `/plugin marketplace add PSURI1894/Claude-Plugins`.)

## Plugins

| Plugin | Description |
|---|---|
| [**shoe-shopping-analyzer**](./shoe-shopping-analyzer) | Compare shoes across every available shopping site with deep filters — price/deals, brand/model, size/fit/width, activity, specs, reviews. Live web research + scraping + weighted ranking. |

Install one with:

```
/plugin install shoe-shopping-analyzer@parth-claude-plugins
```

## Repository layout

```
Claude-Plugins/
├── .claude-plugin/
│   └── marketplace.json          # marketplace manifest (lists all plugins)
└── shoe-shopping-analyzer/       # a plugin
    ├── .claude-plugin/plugin.json
    ├── commands/                 # /compare-shoes, /shoe-deals
    ├── skills/                   # shoe-comparison methodology
    ├── scripts/                  # scrape.py, rank.py
    └── README.md
```

To add another plugin later: create a new top-level folder with its own `.claude-plugin/plugin.json`,
then add an entry to `.claude-plugin/marketplace.json`.
