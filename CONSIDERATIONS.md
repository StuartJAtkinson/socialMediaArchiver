# Considerations

*Nothing open.*

## Open questions for Auto Continue

One line per question, `- ` prefixed — that is the only shape
`consideration_items` (atelier-harness `meta/markdown.rs:280`) recognises.
Answer them inline when atelier interviews this project.

## Open questions for Auto Continue

One line per question, `- ` prefixed — the only shape `consideration_items` recognises.
- `templates/stages/connect.html:24-32` puts the `.source-tabs` strip OUTSIDE the panel (above it, with no extra label), then a `panel p-4` per active source; `templates/stages/storage.html:23-32` puts the `.source-tabs` strip INSIDE the panel with a `<label class="field-label">Backend</label>` above it. Both selectors do the same job (pick one of N items, reveal its form). Which layout should both stages use?

