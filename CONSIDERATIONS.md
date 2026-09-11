# Considerations

*Nothing open.*

## Open questions for Auto Continue

One line per question, `- ` prefixed — that is the only shape
`consideration_items` (atelier-harness `meta/markdown.rs:280`) recognises.
Answer them inline when atelier interviews this project.

## Open questions for Auto Continue

One line per question, `- ` prefixed — the only shape `consideration_items` recognises.

- Posts archived before the absolute-dates fix still hold relative strings like "1 month ago" in `posted_at`, so they sort wrongly under `core/index.py`'s ORDER BY and slip through `core/orchestrator.py`'s date filter - backfill them by resolving each against its own crawl time (check `core/run_history` first; it only works if the run timestamp is recoverable per row), backfill against a single approximate date and mark them all estimated, or leave the old rows alone and accept that only new crawls are correct?
