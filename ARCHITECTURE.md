# Architecture

## Data flow

```text
targets.yaml
   │
   ▼
main.py ── loads YAML and checkpoint
   │
   ▼
core.orchestrator
   ├── resolves connector from registry
   ├── walks provider fallback chain
   ├── applies date filters and UID deduplication
   ├── downloads media and writes comments
   └── records checkpoint after each item/target
             │
             ▼
       normalized Item JSON
             │
             ├── filesystem cache
             ├── optional S3-compatible, GCS, or Azure Blob mirror
             └── index.db (SQLite, upserted per item)
                         │
                         ▼
                    Flask dashboard
```

## Core modules

- `core/models.py`: source-independent `Item`, `ItemAuthor`, and `MediaItem`
- `core/registry.py`: lazy connector lookup
- `core/orchestrator.py`: generic crawl loop
- `core/checkpoint.py`: resumable item and target state
- `core/ratelimit.py`: delay and proxy rotation
- `core/storage.py`: filesystem, S3-mirrored, GCS-mirrored, and Azure Blob-mirrored storage
- `core/index.py`: SQLite `index.db` of every post, upserted per item and
  rebuildable from the normalized JSON with `python main.py reindex`
- `core/feeds.py`: shared RSS parsing

## Connector contract

A connector owns providers ordered from preferred to fallback. The base runner
deduplicates items across tiers and advances on known availability, auth, or
rate-limit exceptions. Connectors emit normalized records only; checkpointing,
storage, media downloads, and delays remain source-agnostic.

Current connectors:

- YouTube Community
- Twitter/X through Nitter RSS
- Reddit through PRAW or public RSS
- RSS/Atom
- Facebook through the official Graph API
- Mastodon through the public instance REST API
- Bluesky through the AT Protocol `app.bsky.feed.getAuthorFeed` endpoint

## Storage schema

Each record is written to `output/<source>/<safe-id>.json`; comments use
`<safe-id>_comments.json`. Media is stored under `output/images/` and referenced
by `media[].local_path`.

The S3, GCS, and Azure Blob backends mirror these relative keys beneath an
optional prefix while retaining local files. This keeps dashboard behavior
identical across backends.

Alongside these, `output/index.db` holds one row per post — `post_id`,
`account`, `platform`, `posted_at`, `text`, `media_count`, `path` — upserted by
the orchestrator as each item lands. It's a derived index, not a second source
of truth: `python main.py reindex` rebuilds it from the JSON records alone.
The dashboard reads counts and paging from it when present, falling back to
walking `output/` if it's missing.

## Dashboard

`web.py` enumerates normalized output, groups records by `(source, target)`,
adapts `Item` fields to the post-card view, and exposes:

- `/`
- `/account/<source>/<target>`
- `/api/stats`
- `/api/posts/<source>/<target>`
- `/api/search`
- `/api/archive/start`
- `/api/archive/status`
- `/api/archive/history`

The archive route invokes the orchestrator directly; it does not use a separate
legacy implementation. When configured, the dashboard process also starts a
periodic crawl scheduler. Each run is recorded locally in
`output/.run_history.json`; item-level checkpointing remains intact between
runs while target completion resets for each new crawl.

## Security boundaries

- Secrets come from environment variables or local ignored config.
- Facebook browser sessions are not stored or supported.
- S3 authentication uses boto3’s standard credential chain.
- GCS authentication uses Google Application Default Credentials.
- Azure Blob Storage uses a connection string kept in local configuration.
- The dashboard is a local development service with no authentication; do not
  expose it publicly without adding authentication, CSRF protection, and a
  production WSGI server.
