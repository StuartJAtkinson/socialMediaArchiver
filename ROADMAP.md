# Roadmap

## Foundation ✅

- [x] Twitter/Nitter archive and Flask dashboard
- [x] Normalized multi-source connector architecture
- [x] YouTube Community, Reddit, RSS, Facebook, and Twitter connectors
- [x] Dashboard support for normalized orchestrator output

## Consolidation ✅

- [x] Absorb the ByteByteGo grabber engine and history
- [x] Port the legacy Twitter path into a connector
- [x] Remove the legacy `src/`, JSON config, and duplicate CLI
- [x] Run dashboard crawls through the orchestrator
- [x] Remove unsupported Facebook DOM scraping

## Storage

- [x] Pluggable storage factory
- [x] Filesystem backend
- [x] S3-compatible mirror (AWS S3, MinIO, B2, R2)
- [x] Native Google Cloud Storage backend
- [x] Native Azure Blob backend

## Next

Ordered so each item unblocks the one under it: the index is what makes search
tractable, and search is what makes a large archive worth adding sources to.

- [x] Scheduled crawls with persisted run history
- [x] SQLite index for large archives — one `index.db` beside the archive
      holding `(post_id, account, platform, posted_at, text, media_count,
      path)`, written by the orchestrator as each post lands, rebuildable from
      the normalized output alone (`python main.py reindex`). Browse and the
      account page read counts and paging from it instead of walking the
      filesystem, which is what makes them slow past a few thousand posts.
- [x] Full-text search across normalized archives — FTS5 virtual table over the
      index above, a search box on Browse, and `main.py search "<query>"` for
      the CLI. Filter by platform, account and date range; results link to the
      post in the account view. No external search service.
- [x] Mastodon connector — public timeline via the instance API
      (`/api/v1/accounts/:id/statuses`), no auth needed for public accounts;
      token optional for followers-only posts. Normalizes to the same post
      shape as the others, including boosts and media attachments. Mirrors
      `connectors/` structure; instance host is per-target config.
- [x] Bluesky connector — AT Protocol `app.bsky.feed.getAuthorFeed` via an app
      password. Handles reposts, quote posts, and the blob CDN for media.
      Credentials through the same Connect stage as every other source.
- [x] Dashboard authentication for non-local deployment — the server binds
      `0.0.0.0:5000` today, so anything on the LAN can read the archive and the
      stored credentials. Single-user password with a signed session cookie,
      set at first run; a `--local-only` flag to bind `127.0.0.1` instead.
      Do this before the dashboard is exposed anywhere beyond the machine.

## Later

- [x] Export a date range as a static, self-contained HTML bundle
- [x] Per-source rate-limit backoff shared across scheduled runs
- [x] Media deduplication by content hash across accounts
