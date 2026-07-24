# Issues

## Open

No known open project issues.

## Resolved

- [x] **Facebook browser tiers were brittle** — removed authenticated and public
  DOM scraping entirely. Facebook now uses only the official Graph API and
  requires `FB_GRAPH_TOKEN`; unavailable credentials skip the provider without
  blocking other targets. This removes unstable selectors, saved session
  cookies, and misleading best-effort behavior. *(resolved 2026-07-24)*
- [x] **Two runtime generations** — removed the legacy `src/` implementation,
  JSON configuration, channel list, and `archiver.py`; the dashboard now starts
  `core.orchestrator` through `main.py`. *(resolved 2026-07-24)*
- [x] **Storage was filesystem-only** — added a storage factory and optional
  S3-compatible mirror while preserving the local dashboard cache. *(resolved
  2026-07-24)*
- [x] **Dashboard did not browse orchestrator output** — normalized output
  adapter added. *(resolved 2026-07-07)*
- [x] **Twitter path lived outside the connector architecture** — added the
  Nitter RSS connector with instance fallback. *(resolved 2026-07-12)*
- [x] **Reddit fallback was silent** — fallback warnings now explain reduced
  metadata and credential setup. *(resolved 2026-06-12)*
- [x] **Monolith lacked provider isolation** — split source logic into
  `connectors/` and generic plumbing into `core/`. *(resolved 2026-06-06)*
