# Quick start

## Install

### Windows

```powershell
python setup.py
.\.venv\Scripts\Activate.ps1
```

### Linux/macOS

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

## Configure

Edit `config/targets.yaml`:

```yaml
targets:
  - { source: youtube_community, target: "@ByteByteGo" }
  - { source: twitter, target: "@ByteByteGo" }
  - { source: reddit, target: "r/programming" }
  - { source: rss, target: "https://news.ycombinator.com/rss" }
```

Tune limits and credentials in `config/config.yaml`. Keep secrets in environment
variables rather than committed YAML.

## Crawl

```powershell
python main.py crawl --verbose
python main.py status
```

To intentionally reprocess all targets:

```powershell
python main.py resume
python main.py crawl --verbose
```

If `output/index.db` (used for fast Browse paging) is ever deleted or falls
out of sync, rebuild it from the archived JSON alone:

```powershell
python main.py reindex
```

## Browse

```powershell
python web.py
```

Open <http://localhost:5000/>. The dashboard reads normalized files under
`output/`; **Start Archiving** runs the same configured crawl in a background
thread.

## Optional credentials

```powershell
$env:REDDIT_CLIENT_ID="..."
$env:REDDIT_CLIENT_SECRET="..."
$env:FB_GRAPH_TOKEN="..."
```

Reddit falls back to public RSS without credentials. Facebook does not use a
browser fallback and requires an authorized Graph API token.

## Test

```powershell
python -m pytest tests -q
```
