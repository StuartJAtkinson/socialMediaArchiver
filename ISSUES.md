# Issues — bytebytego-grabber

## Open
- [ ] **Facebook browser tiers are brittle** — `auth-browser`/`public-browser` scrape an obfuscated, frequently-changing DOM (`div[role='article']`). Extraction is best-effort and may yield little or break when FB changes markup. Graph API tier is the only stable path. *(found 2026-06-06)*

## Resolved
- [x] **Reddit praw fallback was silent** — without `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` (or praw installed) the connector fell back to public `.rss` feeds with only `logger.info` messages, invisible at the default WARNING console level. Both paths in `PrawProvider.available()` now log at WARNING, naming what's lost (scores, comment trees) and the exact fix (install praw / set the env vars). Getting full data still requires the user to create a free Reddit script app and set the credentials. *(resolved 2026-06-12)*
- [x] **Monolith refactor to plugin architecture** — split `scraper.py` into `core/` (models, checkpoint, ratelimit, storage, feeds, registry, orchestrator) + `connectors/` (base, youtube_community, reddit, rss, facebook) behind a normalized `Item` schema with tiered fallback providers. *(resolved 2026-06-06)*
- [x] **Legacy scraper.py retired but not deleted** — deleted `scraper.py` plus the debug/hang-repro scripts (`debug_hang.py`, `test_exit*.py`, `test_scraper.py`, `test_standalone.py`, `test_yaml_hang.py`). Updated `run.bat`, `run.sh`, `setup.py`, `setup.bat`, and `README.md` to point at the new `main.py` entry point. Removed the ScrapingBee config block (only consumed by the retired script). *(resolved 2026-06-07)*
