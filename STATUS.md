# Project status

**Current state:** consolidated multi-source archiver with local dashboard and
optional S3-compatible mirroring.

## Complete

- [x] Normalized `Item` model and connector/provider architecture
- [x] YouTube Community, Twitter/Nitter, Reddit, RSS, and Facebook Graph API
- [x] Checkpoint/resume, rate limiting, date filters, media and comments
- [x] Dashboard over normalized `output/`
- [x] Dashboard-triggered orchestrator crawl
- [x] Legacy `src/`, JSON config, and duplicate entry point removed
- [x] Facebook browser tiers removed in favor of the stable official API
- [x] Filesystem storage and optional S3-compatible mirror
- [x] Compact Homelab Designer-inspired dark dashboard
- [x] Automated regression tests
- [x] SQLite `index.db` for fast Browse/account paging, rebuildable via
      `python main.py reindex`

## Operational requirements

- Python 3.10+
- Network access for configured sources
- `FB_GRAPH_TOKEN` for Facebook
- Reddit credentials for full Reddit metadata/comments; RSS fallback otherwise
- `boto3` plus cloud credentials only when `storage.backend: s3`

## Known limitations

- Nitter public instances can disappear; configure replacement instances.
- YouTube Community exposes a finite recent backlog.
- Facebook access is limited to Pages and permissions authorized by the token.
- The Flask server is intended for local use and has no user authentication.
- S3 is a mirror; dashboard reads remain local.

## Verification

```powershell
python -m pytest tests -q
python main.py --help
python web.py
```

Last refreshed: 2026-08-31.
