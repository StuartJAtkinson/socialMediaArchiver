# MCP — socialMediaArchiver

**Design spec.** No MCP server exists yet. This is the surface this repo should
expose, mapped to the routes and modules that already implement it.

- **Proposed server:** `social-archiver`
- **Transport:** stdio
- **Backs onto:** the Flask app's `/api/*` routes in `web.py` and the
  orchestrator in `core/`

## Why this repo wants one

The archive is a local corpus that grows over time — thousands of posts across
several platforms, on disk, with no query surface beyond the Browse page. The
value of an MCP server here is **reading** that corpus: "what did I save from
this account in 2024", "find the posts mentioning X". Archiving itself is a
long-running crawl with credentials attached, and is a much worse fit for a
tool call.

So this spec is read-heavy on purpose, and puts the crawl behind a start/status
pair rather than a blocking tool.

## Tools — reading the archive

| Tool | Params | Returns | Backs onto |
|---|---|---|---|
| `list_accounts` | `platform?` | archived accounts with counts | `GET /api/stats`, `web.py:555` |
| `get_stats` | — | totals: accounts, posts, images, videos | `GET /api/stats` |
| `list_posts` | `platform`, `account`, `limit?`, `offset?` | normalised posts | `GET /api/posts/<platform>/<account>`, `web.py:266` |
| `search_posts` | `query`, `platform?`, `account?`, `since?`, `until?` | matching posts | **not yet backed** — see below |
| `get_run_history` | `limit?` | past crawl runs with status | `GET /api/run/history`, `web.py:302` |

`search_posts` is the one tool with nothing behind it today: browsing walks the
filesystem. It should wait on the **SQLite index** roadmap item — that item
exists precisely because filesystem walking stops scaling past a few thousand
posts, and an MCP search tool would hit that wall immediately.

## Tools — running a crawl

| Tool | Params | Returns | Backs onto |
|---|---|---|---|
| `start_run` | `targets?` | run id | `POST /api/run/start`, `web.py:319` |
| `run_status` | — | current run's progress | `GET /api/run/status`, `web.py:328` |
| `list_targets` | — | configured archive targets | `GET /api/config/targets`, `web.py:389` |

**Start/poll, never block.** A crawl runs for minutes to hours; a tool that
waits for it will time out and leave the run orphaned. `start_run` returns
immediately and `run_status` is the poll.

## Resources

| URI | Contents |
|---|---|
| `archive://stats` | the same totals `get_stats` returns, as a cheap read |
| `archive://targets` | configured accounts per platform |
| `archive://runs/recent` | recent run history |

## What must NOT be a tool

- **Credential entry.** `POST /api/config/sources` (`web.py:524`) takes
  connector credentials. Those are entered by a human on the Connect stage at
  `http://localhost:5000/connect`. No MCP tool should accept a token.
- **Storage reconfiguration.** `POST /api/config/storage` (`web.py:464`) can
  repoint where the archive lives, including at an S3/GCS/Azure backend. An
  agent repointing storage mid-corpus is a data-loss shape, not a feature.
- **Target removal.** `POST /api/config/targets/remove` (`web.py:424`) — adding
  a target is cheap and reversible; removing one silently drops an account from
  future crawls. Leave it to the UI.

## Security note the spec has to carry

The server binds `0.0.0.0:5000` today, so the dashboard and everything behind
it is reachable from the LAN with no authentication — that is a live roadmap
item ("Dashboard authentication for non-local deployment"). An MCP server
talking to `localhost` inherits the same exposure. **Do the auth item before
this one**, or at minimum bind the MCP-facing app to `127.0.0.1`.

## Implementation note

`core/orchestrator` already normalises every connector to one post shape, which
is what makes a single `list_posts` tool possible across platforms rather than
one per source. Keep that boundary: the MCP layer should never import a
connector directly.
