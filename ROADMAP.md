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
- [ ] Native Google Cloud Storage backend
- [ ] Native Azure Blob backend

## Next

- [ ] Scheduled crawls with persisted run history
- [ ] Full-text search across normalized archives
- [ ] Mastodon connector
- [ ] Bluesky connector
- [ ] Dashboard authentication for non-local deployment
- [ ] SQLite index for large archives
