# UX conventions

What the dashboard actually does today, read off `static/base.css` and
`templates/`. A reference, not a queue — open questions live in
`CONSIDERATIONS.md`, fixable inconsistencies in `ISSUES.md`.

## Stack

Dark-only (`color-scheme: dark`, no light theme and no toggle). Tailwind from
`cdn.tailwindcss.com` for layout utilities, `static/base.css` for every named
component and every colour, Alpine 3 from jsDelivr for behaviour. No build step.

Tailwind is used for layout and spacing only (`flex`, `grid`, `gap-*`, `p-*`,
`mb-*`, `text-xs`). Colour never comes from a Tailwind palette class — it comes
from a CSS variable, either through a component class or an inline
`style="color:var(--…)"`.

## Colour tokens

All defined in `:root` at `static/base.css:4-28`. Nothing outside this list is
a sanctioned colour.

| Token | Value | Used for |
|---|---|---|
| `--canvas` | `#0f1117` | page background; focused input background |
| `--band` | `#13151f` | recessed strips — stats bar, inputs, post headers |
| `--panel` | `#1a1d27` | raised surfaces — cards, panels, the nav |
| `--border` | `#2d3148` | standard 1px border |
| `--border-soft` | `#1e2030` | internal dividers inside a panel |
| `--text` | `#e2e8f0` | body text |
| `--muted` | `#94a3b8` | labels, secondary text |
| `--faint` | `#64748b` | hints, timestamps, empty-state text |
| `--accent` | `#818cf8` | inline links |
| `--accent-fg` / `--accent-bg` / `--accent-bg-hover` / `--accent-border` | indigo set | buttons and the "View Posts" CTA |
| `--status-{running,error,done}-{bg,fg,border}` | amber / red / green triples | status pills, `.field-error`, `.field-success`, `.banner-warn` |

Every status colour is a three-part set (background, foreground, border) so a
pill reads at a glance without relying on hue alone.

## Spacing and type

Body is 14px Inter. Scale in use, smallest to largest: 10px (uppercase stat
labels, platform badges), 11px (hints, metrics, card stats), 12px (buttons,
status pills, sub-headers), 13px (inputs, target keys), 14px (body, card
titles, post text), 15px (stat values), 18px (page `h1`).

Radii: 4px badges, 6px buttons / inputs / pills / rows, 8px panels and cards.

Page shell is fixed: `body.flex.flex-col.h-screen.overflow-hidden`, nav pinned
at the top, one scrolling region below it with `px-4 pt-6 pb-8`. Blocks inside
that region are separated by `mb-5`; panels sit at `p-4`, empty-state panels at
`p-5`.

## Components

- **`.stage-nav`** (`_nav.html`) — identical on all seven pages: tab links left,
  the active stage's label absolutely centred, an action slot right.
- **`.stats-bar` / `.stat-item`** — one borderless row of counts, uppercase
  `.label` above a tabular-nums `.value`. This is the *only* stats presentation
  in the app; it appears on Dashboard, Browse and the account page. Decided
  2026-08-23, see `ISSUES.md`.
- **`.stage-header`** — every page opens with an 18px white `h1` and a 12px
  faint one-line description of what the stage is for.
- **`.panel` / `.panel-band`** — raised and recessed card surfaces.
- **`.status`** with `.running` / `.error` / `.done` / `.idle` — pills. Also
  reused as non-status chips: the source label on a Configure row, and the
  selector pills on Connect and Storage.
- **`.stage-actions`** — the primary-action button. Works both as a wrapper
  class (the nav slot) and directly on the button (every stage page).
- **`.field-label` / `.field-input` / `.field-hint` / `.field-error` /
  `.field-success`** — the whole form vocabulary.

## Control placement

Primary action bottom-left of its panel, secondary next to it, then the
`.field-success` and `.field-error` messages on the same row to the right —
Connect, Configure, Schedule and Storage all follow this. Run is the exception:
its "Run now" button sits top-right of the status panel, beside the state it
acts on.

Long lists page two ways, deliberately. The account page's post list uses an
explicit `Get more posts` button; Browse's search results use infinite scroll
(decided 2026-09-11) — an `IntersectionObserver` on a sentinel below the list,
rooted on the stage's own scrolling region rather than the window, since the
shell is `h-screen overflow-hidden`. Both walk the same `limit`/`offset`/
`has_more` shape the API returns.

Destructive actions are inline on the row they affect (Configure's per-target
`Remove`). Save-style buttons swap their label while busy ("Save" → "Saving…",
"Run now" → "Running…") rather than showing a spinner.

## Terminology

Six stages, always in this order and always these names: Dashboard, Connect,
Configure, Storage, Schedule, Run, Browse. Titles read `<Page> — Social Media
Archiver` with an em dash. A crawl is a "crawl", never a scrape or a fetch; a
configured `{source, target}` pair is a "target"; a completed crawl is a "run".
"Source" is the platform connector, "account" is the thing being archived.

Account handles are rendered with exactly one leading `@` — some connectors
store it and some don't, so `handle()` in `static/js/browse.js` and the
`lstrip('@')` in `account.html` normalise it.

Emoji appear in exactly one place: the ❤️/🔄/💬 metric glyphs on post cards,
kept deliberately because they are the only label those counts carry. Decorative
emoji were removed everywhere else, 2026-08-23.

Dates are **absolute, never relative** (standing rule, 2026-09-11). No surface
shows "1 month ago"; every timestamp is ISO 8601 and is rendered as a date.
Connectors resolve relative source text at ingest — see
`_resolve_relative_timestamp` in `connectors/youtube_community.py`, which YouTube
forces because it renders community-post dates as human text. A timestamp
derived that way carries `timestamp_estimated=True`, because "1 month ago" is a
month-wide claim; an unparseable one is stored empty rather than guessed. The
raw source string is kept in `Item.raw`.
