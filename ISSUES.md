# Issues — socialMediaArchiver

> Project naming: the local working dir was historically `bytebytego-grabber`.
> The GitHub remote is `socialMediaArchiver`. After the combine the canonical
> name is `socialMediaArchiver`; the orchestrator code added in the merge is
> the new spine, with the legacy `src/` Phase 1 code preserved alongside.

## Open
- [ ] **Facebook browser tiers are brittle** — `auth-browser`/`public-browser` scrape an obfuscated, frequently-changing DOM (`div[role='article']`). Extraction is best-effort and may yield little or break when FB changes markup. Graph API tier is the only stable path. *(found 2026-06-06)*
- [ ] **Port the Nitter Twitter path to a `connectors/twitter.py`** — `src/scraper.py` holds the working Nitter-RSS implementation that `archiver.py` and `web.py` depend on. Refactor it into a `TwitterNitterProvider` (or two tiers: nitter-rss → host-meta-fallback), register it in `core/registry.py`, and have `archiver.py` delegate to the orchestrator for that source. Lets Twitter users benefit from the same checkpoint/proxy/storage the other connectors get. *(found 2026-06-14)*
- [ ] **Wire `web.py` to the new orchestrator's output** — the Flask dashboard reads `archives/twitter/{account}/posts.jsonl`. After the Twitter port it should also browse the orchestrator's `output/` (YouTube, Reddit, RSS, Facebook) so the multi-source archive is browsable from one place. Define a shared post-render adapter in `web.py` rather than rewriting the dashboard. *(found 2026-06-14)*
- [ ] **Nitter reliability** — the public Nitter instances listed in the legacy `README.md` are largely dead. The new `connectors/rss.py` already covers public RSS/Atom feeds; if the Twitter port needs to stay viable, the connector should ship with a small, recently-verified instance list and a probe step that disables itself when all are down. *(found 2026-06-14)*

## Resolved
- [x] **Combine bytebytego-grabber into socialMediaArchiver** — `git fetch` + `git merge --allow-unrelated-histories` brought the multi-source orchestrator (core/, connectors/, main.py, config, setup, run scripts) into the socialMediaArchiver working tree. Resolved 3 file conflicts: `.gitignore` (union), `requirements.txt` (union, organised by role), `README.md` (rewritten as a single overview that documents both the legacy Phase 1 stack and the new orchestrator). Both commit histories preserved. *(resolved 2026-06-14)*
- [x] **Reddit praw fallback was silent** — without `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` (or praw installed) the connector fell back to public `.rss` feeds with only `logger.info` messages, invisible at the default WARNING console level. Both paths in `PrawProvider.available()` now log at WARNING, naming what's lost (scores, comment trees) and the exact fix (install praw / set the env vars). Getting full data still requires the user to create a free Reddit script app and set the credentials. *(resolved 2026-06-12)*
- [x] **Monolith refactor to plugin architecture** — split `scraper.py` into `core/` (models, checkpoint, ratelimit, storage, feeds, registry, orchestrator) + `connectors/` (base, youtube_community, reddit, rss, facebook) behind a normalized `Item` schema with tiered fallback providers. *(resolved 2026-06-06)*
- [x] **Legacy scraper.py retired but not deleted** — deleted `scraper.py` plus the debug/hang-repro scripts (`debug_hang.py`, `test_exit*.py`, `test_scraper.py`, `test_standalone.py`, `test_yaml_hang.py`). Updated `run.bat`, `run.sh`, `setup.py`, `setup.bat`, and `README.md` to point at the new `main.py` entry point. Removed the ScrapingBee config block (only consumed by the retired script). *(resolved 2026-06-07)*

