# socialMediaArchiver

Multi-source social-media archiver. Originally a Twitter/Nitter-only CLI
with a Flask dashboard (Phase 1); now a **multi-source crawler
orchestrator** covering YouTube Community, Reddit, RSS/Atom, and
Facebook behind a normalised `Item` model, with the original Twitter
path preserved as one of the source connectors and the web dashboard
still serving the local archive.

**Status:** core local archiving ✅ · multi-source orchestrator ✅ ·
Flask web dashboard ✅ · cloud storage 🔄 (roadmap). See
[`STATUS.md`](STATUS.md) for the legacy phase checklist and
[`ISSUES.md`](ISSUES.md) for the running open/resolved list.

## Architecture

```
socialMediaArchiver/
├── core/                       source-agnostic plumbing (new)
│   ├── models.py               Item / ItemAuthor / MediaItem — every record has uid = source:id
│   ├── checkpoint.py           resume state, legacy-YouTube migration
│   ├── ratelimit.py            inter-request jitter, Tor/proxy rotation
│   ├── storage.py              filesystem writer + media downloader
│   ├── feeds.py                shared RSS/Atom parsing
│   ├── registry.py             source name → connector class
│   ├── orchestrator.py         generic crawl loop
│   └── errors.py               RateLimitError, AuthError, ProviderUnavailable
├── connectors/                 one module per source
│   ├── base.py                 Connector + tiered-fallback Provider
│   ├── youtube_community.py    wraps post-archiver-improved
│   ├── reddit.py               praw → public .rss fallback
│   ├── rss.py                  generic RSS/Atom (feedparser)
│   └── facebook.py             Graph API → auth browser → public browser
├── src/                        legacy Phase 1 code (Twitter-via-Nitter, JSONL storage)
│   ├── main.py
│   ├── scraper.py              TwitterScraper (Nitter RSS)
│   ├── storage.py              StorageManager (JSONL + filesystem)
│   └── batch_processor.py      smart date-based batch planning
├── web.py                      Flask dashboard (Phase 5, brought forward)
├── archiver.py                 legacy CLI entry point
├── main.py                     new orchestrator CLI: crawl / status / resume / facebook-login
├── run.py / run.bat / run.sh   thin wrappers
├── setup.py / setup.bat        venv + dep + Playwright installer
├── config/
│   ├── config.yaml             orchestrator config (per-source blocks)
│   ├── targets.yaml            {source, target} pairs to crawl
│   ├── channels.txt            legacy YouTube channels (kept for history)
│   └── config.example.json     legacy Twitter config
├── templates/                  Flask templates
├── output/, archives/          crawler / legacy output (gitignored)
└── ISSUES.md                   open/resolved issues
```

### Add a new source

Write `connectors/<name>.py` exposing a `Connector` + `Provider`(s) that
yield `Item`s, then register `"<name>": "module:Class"` in
`core/registry.py`. No core changes needed.

## Setup

### Windows (recommended)

```bat
python setup.py
run.bat
```

`setup.py` creates `.venv`, installs `requirements.txt`, and runs
`playwright install chromium`. `run.bat` invokes the new orchestrator.

### Linux / WSL

```bash
python setup.py
./run.sh
```

### Manual

```bash
python -m venv .venv
. .venv/Scripts/activate    # Windows
# . .venv/bin/activate      # Linux/macOS
pip install -r requirements.txt
playwright install chromium
python main.py crawl
```

## CLI

```
python main.py crawl                  # run the multi-source orchestrator
python main.py status                 # print checkpoint state
python main.py resume                 # clear the checkpoint, start fresh next run
python main.py facebook-login         # open a browser, save FB session
python main.py crawl --verbose        # more logs
python main.py crawl --proxy-url ...  # override config at runtime
```

Legacy CLI (Phase 1, still works):

```bash
python archiver.py                    # Nitter/Twitter archiver
python web.py                         # Flask dashboard on :5000
```

## Configuration

`config/config.yaml` holds the new orchestrator's global knobs:

- `post_delay`, `channel_delay`, `date_after`, `date_before`
- `proxy_url`, `proxy_rotation_every`
- `tor_control_port`, `tor_password`
- `download_images`, `download_comments`
- `sources.<name>.*` — per-connector options

Per-source secrets: env vars first, then the YAML, so credentials can
stay out of the file (`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`,
`FB_GRAPH_TOKEN`).

`config/targets.yaml` lists `{source, target}` pairs:

| source               | target                                             |
| -------------------- | -------------------------------------------------- |
| `youtube_community`  | `@handle`, channel id, or channel URL              |
| `reddit`             | `r/<subreddit>` or `u/<user>`                      |
| `rss`                | any RSS/Atom feed URL                              |
| `facebook`           | page slug or URL                                   |

The legacy `config/config.example.json` is still used by
`python archiver.py` and `python web.py`.

## Notes

- The Facebook browser tiers scrape an obfuscated, frequently-changing
  DOM and degrade gracefully — Graph API is the only stable path. See
  `ISSUES.md`.
- Reddit's `praw` provider needs credentials or the connector falls
  back to public `.rss` feeds (no scores / comment trees); the fallback
  logs at WARNING so it is visible at the default log level.
- `post-archiver-improved` is required for the YouTube connector.
- Nitter (used by the legacy `src/scraper.py`) is increasingly
  unreliable. The new `connectors/rss.py` covers the same use case for
  any public RSS/Atom feed; a `connectors/twitter.py` port of the
  Nitter logic is tracked in `ISSUES.md`.

## Roadmap

The `STATUS.md` checklist covers the legacy Phase 1–5 plan. The
forward-looking items live in the new `Roadmap` section in
`ISSUES.md`-adjacent notes (or below once we move it there):

1. Port `src/scraper.py`'s Nitter Twitter path into
   `connectors/twitter.py` so it sits behind the same registry.
2. Wire the Flask `web.py` dashboard into the new orchestrator's
   output so the multi-source archive is browsable alongside the
   legacy Twitter one.
3. Stabilise the Facebook browser tiers (see open issue).
4. Add a 5th source connector (Mastodon, Bluesky, HackerNews).
5. Connector-level tests + CI.

## Disclaimer

For personal archiving and backup. Respect platform ToS, user privacy,
copyright, local law, and rate limits. Use at your own risk.
