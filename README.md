# bytebytego-grabber

Multi-source crawler orchestrator. Pulls community posts and feeds from
YouTube, Reddit, RSS/Atom, and Facebook behind one normalized record model,
with tiered fallback (e.g. Reddit `praw` → public `.rss`, Facebook
Graph API → auth browser → public browser) and a single checkpoint that
dedupes across every source.

## Architecture

- `core/` — source-agnostic plumbing
  - `models.py` — normalized `Item` (every record has `uid = source:id`)
  - `checkpoint.py` — resume state with a legacy-YouTube migration path
  - `ratelimit.py` — inter-request jitter and Tor/proxy rotation
  - `storage.py` — filesystem writer and media downloader
  - `feeds.py` — shared RSS/Atom parsing
  - `registry.py` — `source name → connector class`
  - `orchestrator.py` — the generic crawl loop
  - `errors.py` — `RateLimitError`, `AuthError`, `ProviderUnavailable`
- `connectors/` — one module per source
  - `youtube_community.py` — wraps `post-archiver-improved`
  - `reddit.py` — `praw` → public `.rss` fallback
  - `rss.py` — generic RSS/Atom over `feedparser`
  - `facebook.py` — Graph API → auth browser → public browser
- `main.py` — CLI entry point. Subcommands: `crawl`, `status`, `resume`,
  `facebook-login`.
- `config/config.yaml` — global knobs + per-source options.
- `config/targets.yaml` — `{source, target}` entries to crawl.
- `config/channels.txt` — legacy YouTube channels file (kept for history;
  `targets.yaml` is the source of truth now).

### Add a new source

Write `connectors/<name>.py` exposing a `Connector` + `Provider`(s) that
yield `Item`s, then register `"<name>": "module:Class"` in
`core/registry.py`. No core changes needed.

## Setup (Windows)

1. Prereqs: Python 3.11+, Windows, working internet.
2. `python setup.py` — creates `.venv`, installs deps, installs Playwright
   Chromium. (On Linux/WSL run the same file; it auto-detects the platform.)
3. `run.bat` (or `python run.py` / `python main.py crawl ...`).

## Setup (Linux / WSL)

```bash
python setup.py
./run.sh
```

## Configuration

Edit `config/config.yaml`. Major knobs:

- `post_delay`, `channel_delay`, `date_after`, `date_before`
- `proxy_url`, `proxy_rotation_every`
- `tor_control_port`, `tor_password`
- `download_images`, `download_comments`
- `sources.<name>.*` — per-connector options

Per-source secrets: read environment variables first, then the YAML, so
you can keep credentials out of the file (e.g. `REDDIT_CLIENT_ID`,
`REDDIT_CLIENT_SECRET`, `FB_GRAPH_TOKEN`).

## Targets

`config/targets.yaml` lists `{source, target}` pairs. Supported sources:

| source               | target                                             |
| -------------------- | -------------------------------------------------- |
| `youtube_community`  | `@handle`, channel id, or channel URL              |
| `reddit`             | `r/<subreddit>` or `u/<user>`                      |
| `rss`                | any RSS/Atom feed URL                              |
| `facebook`           | page slug or URL                                   |

## CLI

```
python main.py crawl                  # run the orchestrator
python main.py status                 # print checkpoint state
python main.py resume                 # clear the checkpoint, start fresh next run
python main.py facebook-login         # open a browser, save FB session
python main.py crawl --verbose        # more logs
python main.py crawl --proxy-url ...  # override config at runtime
```

## Notes

- The Facebook browser tiers scrape an obfuscated, frequently-changing DOM
  and degrade gracefully — Graph API is the only stable path. See
  `ISSUES.md`.
- Reddit's `praw` provider needs credentials or the connector silently
  falls back to public `.rss` feeds (no scores / comment trees).
- `post-archiver-improved` is required for the YouTube connector.

## Project status

See `ISSUES.md` for the running issue list.

## Roadmap

Roughly in priority order. Items shift as the open issue list moves.

1. **Stabilize the Facebook browser tiers** *(open in ISSUES.md)* — the
   `auth-browser` / `public-browser` providers scrape an obfuscated, frequently
   changing DOM. Either commit to maintaining them against FB's changes, swap
   to a more stable unofficial path, or document the Graph API tier as the
   only supported route and demote the browser tiers behind a `best_effort`
   flag.
2. **Add a 5th source connector** — Mastodon, Bluesky, or HackerNews are the
   natural fits (public, no auth, or trivial auth). The plugin boundary in
   `core/registry.py` was designed for this — drop in `connectors/<name>.py`
   plus a `targets.yaml` entry.
3. **Live-test the YouTube connector** — the connector wraps
   `post-archiver-improved`, which the project README still treats as
   required. Verify the install path on a clean machine and capture the
   first run in the issue log.
4. **Connector-level tests** — `core/models.py`, `core/registry.py`, and
   `connectors/base.py` are pure and easy to cover. Connector-internal
   network calls should be faked, not skipped.
5. **CI** — GitHub Actions: ruff + pyflakes on every push, run the
   connector-level tests. Cheap, catches the regression class that broke
   the old monolith.
