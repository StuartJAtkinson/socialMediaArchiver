# Development

## Repository layout

```text
connectors/             source-specific providers and normalization
core/                   models, registry, orchestrator, checkpoint, storage
config/config.yaml      runtime and per-source settings
config/targets.yaml     crawl targets
templates/              compact dark dashboard
tests/                  pytest regression suite
main.py                 CLI
web.py                  Flask dashboard and archive API
```

There is one runtime generation. The former `src/`/JSON-config implementation
was removed after its Twitter path and dashboard were absorbed into the
connector/orchestrator architecture.

## Add a source

1. Create `connectors/<source>.py`.
2. Implement one or more `Provider` classes.
3. Map each native record to `core.models.Item`.
4. Return providers in fallback order from a `Connector`.
5. Register the connector in `core/registry.py`.
6. Add focused tests and configuration documentation.

Providers should raise `ProviderUnavailable`, `AuthError`, or `RateLimitError`
for expected fallback conditions. Unexpected failures should retain enough
context to diagnose the target and provider.

## Storage backends

`core.storage.create_storage()` selects the backend. Filesystem storage is the
local source of truth for the dashboard. `S3Storage` and `GCSStorage` extend it
by uploading each successful local write. New backends must preserve
`write_item`, `write_comments`, and `download_media` behavior.

## Tests

```powershell
python -m pytest tests -q
python main.py --help
python -m connectors.twitter
```

Tests must not require live social services. Inject fake HTTP/cloud clients and
use temporary output directories.

## Style and safety

- Keep connector dependencies optional where a fallback exists.
- Never commit tokens, cookies, output archives, or `.env`.
- Use `Item.uid` for cross-source deduplication.
- Write records atomically enough that a corrupt file cannot break dashboard
  enumeration; the dashboard skips malformed JSON.
- Preserve the local cache when adding remote storage so offline browsing works.
