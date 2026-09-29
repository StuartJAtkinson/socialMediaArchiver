# Considerations

*Nothing open.*

## Open questions for Auto Continue

One line per question, `- ` prefixed — that is the only shape
`consideration_items` (atelier-harness `meta/markdown.rs:280`) recognises.
Answer them inline when atelier interviews this project.

## Open questions for Auto Continue

One line per question, `- ` prefixed — the only shape `consideration_items` recognises.
- `templates/stages/connect.html:24-32` puts the `.source-tabs` strip OUTSIDE the panel (above it, with no extra label), then a `panel p-4` per active source; `templates/stages/storage.html:23-32` puts the `.source-tabs` strip INSIDE the panel with a `<label class="field-label">Backend</label>` above it. Both selectors do the same job (pick one of N items, reveal its form). Which layout should both stages use?
- Browse's `handle()` (`static/js/browse.js:24`) prepends `@` to anything that doesn't already start with one, so a Reddit target stored as `r/programming` renders as `@r/programming` on the account card and in search results, and an RSS target stored as `https://hnrss.org/frontpage` renders as `@https://hnrss.org/frontpage`. UX.md says the `@` convention is for **handles** — Reddit subreddits and feed URLs aren't handles. Should the rendering skip `@` for non-handles, or go platform-aware (`r/programming` for Reddit, host name for RSS, `@handle` for the rest)?
- ROADMAP.md marks "Dashboard authentication for non-local deployment" as done but describes it as "Single-user password with a signed session cookie, set at first run; a `--local-only` flag to bind `127.0.0.1` instead." — what shipped is HTTP Basic Auth via `DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD` env vars (`web.py:37-49`), no first-run setup, no `--local-only` flag. Should the ROADMAP description be rewritten to match the shipped feature, or is the signed-cookie + `--local-only` shape still on the roadmap?

