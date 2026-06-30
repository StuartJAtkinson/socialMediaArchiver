# Roadmap — socialMediaArchiver

Multi-source social-media archiver behind a normalised `Item` model. Legacy
phase checklist is in [`STATUS.md`](STATUS.md).

## Phase 1 — Twitter/Nitter core ✅
- [x] Twitter/Nitter CLI archiver
- [x] Flask dashboard over the local archive

## Phase 2 — Multi-source orchestrator ✅
- [x] Connector model (`connectors/base.py`) + registry
- [x] YouTube Community, Reddit, RSS/Atom, Facebook connectors
- [x] Orchestrator, checkpointing, rate-limiting, normalised storage
- [x] Twitter path preserved as one connector

## Phase 3 — Consolidation (current)
- [ ] Collapse legacy `src/` layer into `connectors/`+`core/` (one generation)
- [ ] Absorb the duplicate bytebytego-grabber snapshot (identical engine) and retire it

## Phase 4 — Cloud storage
- [ ] Pluggable storage backends (S3 / B2 / GCS)
- [ ] Scheduled crawls

## Later
- [ ] More connectors (Mastodon, Bluesky, Instagram)
- [ ] Full-text search over the archive
