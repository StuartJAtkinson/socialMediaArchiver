# socialMediaArchiver

A local-first, multi-source archive for public social content. Connectors normalize
every record into one `Item` schema, the orchestrator handles checkpointing,
media, comments and storage, and the Flask dashboard browses the resulting
archive.

## Sources

| Source | Provider |
|---|---|
| YouTube Community | `post-archiver-improved` |
| Twitter/X | Nitter RSS with instance fallback |
| Reddit | PRAW, falling back to public RSS |
| RSS/Atom | `feedparser` |
| Facebook Pages | Official Graph API; `FB_GRAPH_TOKEN` required |
| Mastodon | Public instance REST API; token optional for followers-only accounts |
| Bluesky | AT Protocol `app.bsky.feed.getAuthorFeed`; app password optional |

Facebook browser scraping is intentionally unsupported: the DOM is unstable,
saved sessions are sensitive credentials, and automated scraping can violate
platform terms.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py crawl --verbose
python web.py
```

Open <http://localhost:5000/>.

On Linux/macOS, activate with `. .venv/bin/activate`. `python setup.py`,
`setup.bat`, `run.bat`, `run.sh`, and `python run.py` are convenience wrappers.

## CLI

```text
python main.py crawl    [--config FILE] [--targets FILE] [--verbose]
python main.py status   [--config FILE]
python main.py resume   [--config FILE]
python main.py reindex  [--config FILE]
python main.py search "<query>" [--platform P] [--account A] [--since DATE] [--until DATE]
python main.py export --output DIR [--platform P] [--account A] [--since DATE] [--until DATE]
```

`resume` clears the checkpoint so the next crawl starts from the beginning.
`reindex` rebuilds `index.db` from the normalized JSON output alone — use it
if the index is ever deleted or falls out of sync.
`search` runs a full-text query over archived post text via `index.db`'s FTS5
table, with optional platform/account/date filters.
`export` writes a static, self-contained HTML bundle (`index.html` plus a
`media/` folder) of posts in a date range — no server or network access
needed to view it.
The dashboard’s **Start Archiving** button invokes the same orchestrator.

## Configuration

- `config/config.yaml`: global and per-source settings
- `config/targets.yaml`: `{source, target}` crawl list
- Environment variables: secrets such as `FB_GRAPH_TOKEN`,
  `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and standard AWS credentials
- `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`: optional HTTP Basic Auth for
  the dashboard; set both before binding it to a non-local interface

Output defaults to:

```text
output/
├── .checkpoint.json
├── .run_history.json
├── index.db
├── images/
└── <source>/
    ├── <id>.json
    └── <id>_comments.json
```

`index.db` is a SQLite index over every post (`post_id`, `account`, `platform`,
`posted_at`, `text`, `media_count`, `path`), written as each post lands. Browse
and the account page read counts and paging from it instead of walking
`output/` directly, which is what keeps them fast past a few thousand posts.
It's a derived convenience file, not a second source of truth — rebuild it any
time with `python main.py reindex`.

### Scheduled crawls and run history

To run configured targets periodically while the dashboard is running, set an
interval in `config/config.yaml` and launch `python web.py`:

```yaml
schedule:
  interval_minutes: 60
```

`0` (the default) disables scheduled crawls. Each run is appended to
`output/.run_history.json` with its trigger, timestamps, outcome, and crawl
totals; the newest entries are available at `/api/archive/history`. Every new
run revisits the configured targets but keeps item-level checkpointing, so
already archived records are not downloaded again.

### S3-compatible storage

The default `filesystem` backend is dependency-free. To mirror the local cache
to AWS S3, MinIO, Backblaze B2, Cloudflare R2, or another S3-compatible service:

```powershell
python -m pip install boto3
```

Then set:

```yaml
storage:
  backend: s3
  output_dir: "./output"
  images_dir: "./output/images"
  s3:
    bucket: "my-archive"
    prefix: "social-media"
    region: "eu-west-2"
    endpoint_url: ""  # set for non-AWS services
```

Authentication uses boto3’s standard credential chain. Files remain local for
the dashboard and are uploaded after each successful write.

### Google Cloud Storage

To mirror the local cache to a Google Cloud Storage bucket:

```powershell
python -m pip install google-cloud-storage
```

Then set:

```yaml
storage:
  backend: gcs
  output_dir: "./output"
  images_dir: "./output/images"
  gcs:
    bucket: "my-archive"
    prefix: "social-media"
    project: "my-gcp-project" # optional when credentials provide a project
```

Authentication uses the standard Google Application Default Credentials chain,
including `GOOGLE_APPLICATION_CREDENTIALS`, user ADC, and attached service
accounts. Files remain local for the dashboard and are uploaded after each
successful write.

### Azure Blob Storage

To mirror the local cache to an Azure Blob Storage container:

```powershell
python -m pip install azure-storage-blob
```

Then set:

```yaml
storage:
  backend: azure
  output_dir: "./output"
  images_dir: "./output/images"
  azure:
    container: "social-media"
    prefix: "social-media"
    connection_string: "DefaultEndpointsProtocol=https;AccountName=..."
```

Use a connection string from the Azure portal or an environment-specific,
ignored config file; do not commit it. Files remain local for the dashboard and
are uploaded after each successful write.

## Architecture

```text
config/targets.yaml
        │
        ▼
main.py → core/orchestrator.py → connectors/<source>.py
                  │
                  ├─ checkpoint / rate limiting
                  ├─ normalized Item model
                  ├─ filesystem, S3, GCS, or Azure Blob-mirrored storage
                  └─ index.db (SQLite, rebuildable via `main.py reindex`)
                                      │
                                      ▼
                                  output/
                                      │
                                      ▼
                                  web.py
```

Connectors expose ordered providers through `connectors/base.py`. Expected
availability, authentication and rate-limit failures fall through cleanly;
normalized `Item.uid` values prevent duplicates.

## Development

```powershell
python -m pytest tests -q
python -m connectors.twitter
python main.py --help
```

Add a connector by implementing `Connector.build_providers()`, mapping native
records to `core.models.Item`, and registering it in `core/registry.py`.

See [QUICKSTART.md](QUICKSTART.md), [ARCHITECTURE.md](ARCHITECTURE.md),
[DEVELOPMENT.md](DEVELOPMENT.md), [STATUS.md](STATUS.md), and
[ROADMAP.md](ROADMAP.md).

## Disclaimer

Archive only content you are permitted to access and retain. Respect platform
terms, robots policies, privacy rights, copyright, and rate limits. Public
endpoints and unofficial providers can disappear without notice.

## MCP

No MCP server yet. [MCP.md](MCP.md) specs the one this repo should have — the
tools, what backs each, and what deliberately stays out of an agent's reach.
