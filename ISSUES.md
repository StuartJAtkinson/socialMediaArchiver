# Issues

## Open

- [ ] **Secondary-link styling disagrees between templates** — decided: neutral is correct, `account.html` is right. Drop "View Posts" (`templates/index.html:311-321`) from the indigo/primary treatment to the neutral/transparent style `account.html:319-323` uses, so "Start Archiving" is the only filled button on the page. *(answered 2026-08-23)*
- [ ] **Two "key stats" layouts for the same counts** — decided: borderless row everywhere. `templates/index.html:261-268`'s bordered `.stats-grid` becomes the `.stats-bar` flex row from `account.html:353-359`; the counts sit in the page rather than in a box. *(answered 2026-08-23)*
- [ ] **Decorative emoji in `templates/index.html` headings** (📚/🚀/📁, lines 427/451/458) — decided: drop them. Plain headings on both templates; the archiver is a utility and the headings say what the section is without decoration. *(answered 2026-08-23)*


## Resolved
- [x] **Dead legacy light-theme CSS block retained in both templates** — `templates/account.html:8-261` and `templates/index.html:8-203` are a full original light-theme stylesheet, entirely superseded by the dark-theme block appended after each (from ~line 263/205 onward). This is the likely source of the stale error colours above; delete the superseded block from both files. — auto-continue *(resolved 2026-08-03)*
- [x] **`loadAccountStats()` is a half-wired stub that duplicates info already shown** — `templates/index.html:515-522` contains the comment `// This would need a new API endpoint, for now just show basic info` and just writes `Platform: ${platform}`, which duplicates the platform badge already rendered at line 503. Either wire it to real stats or remove the stub and its call site. — auto-continue *(resolved 2026-08-02)*
- [x] **Controls-bar margin/radius differ between the two templates** — `templates/account.html:375,377`: `.controls { margin-bottom: 10px; border-radius: 6px; }` vs `templates/index.html:296,300`: `.control-panel { margin-bottom: 12px; border-radius: 7px; }`. Same "action bar" role, unify the values. — auto-continue *(resolved 2026-08-02)*
- [x] **`.header` padding/min-height differ between `account.html` and `index.html` for the same component** — `templates/account.html:307,309`: `min-height: 46px; padding: 8px 12px;` vs `templates/index.html:240-241`: `min-height: 48px; padding: 8px 14px;`. Same page-header bar, unify the values. — auto-continue *(resolved 2026-08-02)*
- [x] **`templates/index.html` error status uses stale light-theme colours against a dark UI** — `startArchiving()`'s catch block (`templates/index.html:551-552`) hardcodes `status.style.background = '#f8d7da'; status.style.color = '#721c24';`, the old light-theme error palette. The rest of the app has moved to a dark theme with `.error` styled via dark tokens (`templates/account.html:446-450`: `rgba(127,29,29,.25)` / `#fca5a5`). `index.html` has no dark-theme error/status class at all, so this fallback path renders a light pink/maroon box against the dark UI. Replace with the same dark-theme error styling `account.html` uses. — auto-continue *(resolved 2026-08-01)*

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

## Needs input (Auto Continue)
*Left by Auto Continue 2026-08-17 — decide these, then clear CONSIDERATIONS.md.*
- Secondary nav link styling disagreements exist between `templates/account.html:319-323` (neutral/transparent "← Back to Dashboard") and `templates/index.html:311-221` (indigo/primary "View Posts"). Two different "key stats" layouts for the same content are used in `templates/account.html:353-359` (`stats-bar`, borderless flex row) and `templates/index.html:261-268` (`stats-grid`, bordered grid). Decorative emoji used in headings on `templates/index.html` (📚/🚀/📁, lines 427/451/458) are not present in `templates/account.html`. A decision is needed on which secondary-link style is correct and whether to keep or remove the decorative emoji.
