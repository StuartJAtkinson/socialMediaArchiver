# Project status

**Current state:** consolidated multi-source archiver with local dashboard and
optional S3-compatible mirroring.

## Complete

- [x] Normalized `Item` model and connector/provider architecture
- [x] YouTube Community, Twitter/Nitter, Reddit, RSS, Facebook Graph API,
      Mastodon, and Bluesky connectors
- [x] Checkpoint/resume, rate limiting, date filters, media and comments
- [x] Dashboard over normalized `output/`
- [x] Dashboard-triggered orchestrator crawl
- [x] Legacy `src/`, JSON config, and duplicate entry point removed
- [x] Facebook browser tiers removed in favor of the stable official API
- [x] Filesystem storage, optional S3-compatible mirror, and native GCS/Azure
      Blob backends
- [x] Compact Homelab Designer-inspired dark dashboard
- [x] Automated regression tests
- [x] SQLite `index.db` for fast Browse/account paging, rebuildable via
      `python main.py reindex`
- [x] Full-text search (FTS5) over archived post text, in the dashboard and
      via `python main.py search`
- [x] Optional dashboard authentication (`DASHBOARD_USERNAME`/
      `DASHBOARD_PASSWORD`) for non-local deployment
- [x] Date-range export to a static, self-contained HTML bundle via
      `python main.py export`

## Operational requirements

- Python 3.10+
- Network access for configured sources
- `FB_GRAPH_TOKEN` for Facebook
- Reddit credentials for full Reddit metadata/comments; RSS fallback otherwise
- `MASTODON_TOKEN` optional, only needed for followers-only Mastodon accounts
- `BLUESKY_IDENTIFIER`/`BLUESKY_APP_PASSWORD` optional, only needed for
  accounts blocked to anonymous reads
- `boto3`/GCS/Azure SDKs plus cloud credentials only when `storage.backend` is
  set to that provider

## Known limitations

- Nitter public instances can disappear; configure replacement instances.
- YouTube Community exposes a finite recent backlog.
- Facebook access is limited to Pages and permissions authorized by the token.
- The Flask server has no authentication unless `DASHBOARD_USERNAME`/
  `DASHBOARD_PASSWORD` are set (optional HTTP Basic Auth).
- S3 is a mirror; dashboard reads remain local.

## Verification

```powershell
python -m pytest tests -q
python main.py --help
python web.py
```

Last refreshed: 2026-08-31.
