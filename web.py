"""
Web Dashboard for Social Media Archiver.

Provides a user-friendly interface for:
- Starting/stopping archiving operations
- Viewing archived posts by account
- Monitoring progress and statistics
"""

import json
import math
import os
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect

import main as crawler_cli
from core.index import PostIndex, index_path
from core.run_history import RunHistory, run_history_path

try:
    import yaml  # PyYAML — same loader main.load_yaml uses
except ImportError:
    yaml = None  # writes will raise at runtime if PyYAML is missing

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = 'social-media-archiver-key'

# Tab order shown on every stage page (and the landing dashboard).
TABS = [
    {'key': '',             'label': 'Dashboard'},  # '' -> /
    {'key': 'connect',      'label': 'Connect'},
    {'key': 'configure',    'label': 'Configure'},
    {'key': 'storage',      'label': 'Storage'},
    {'key': 'schedule',     'label': 'Schedule'},
    {'key': 'run',          'label': 'Run'},
    {'key': 'browse',       'label': 'Browse'},
]


def _stage_context(active, stage_actions=''):
    """Build the kwargs _nav.html needs: tabs[] (with .active) + active_label.

    `active` matches one of TABS[*]['key'] (empty string == landing dashboard).
    """
    tabs = []
    for t in TABS:
        tabs.append({**t, 'active': t['key'] == active})
    label = next(t['label'] for t in TABS if t['key'] == active)
    return {'tabs': tabs, 'active_label': label, 'stage_actions': stage_actions}

# Global variables for background tasks
archive_thread = None
is_archiving = False
archive_lock = threading.Lock()
scheduler_thread = None
scheduler_stop = threading.Event()
schedule_interval_minutes = 0.0

# ── Normalized output reader ──────────────────────────────────────────────────
# The crawler writes output/<source>/<id>.json. An account is a
# (source, target) pair.
OUTPUT_DIR = Path('./output')


def _atomic_write_yaml(path, data):
    """Write `data` to `path` as YAML via temp-file + os.replace.

    Atomic on POSIX; on Windows, atomic within the same NTFS directory
    (rename of an unlinked temp file). Same pattern as core/run_history.py:85-90.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required for config writes; pip install pyyaml")
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    os.replace(tmp, path)


def _iter_output_items(source):
    """Yield each Item dict under output/<source>/, skipping comment sidecars."""
    d = OUTPUT_DIR / source
    if not d.is_dir():
        return
    for f in d.glob('*.json'):
        if f.name.endswith('_comments.json'):
            continue
        try:
            with open(f, encoding='utf-8') as fh:
                yield json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue  # ponytail: skip a corrupt/partial file rather than 500 the page

def _item_to_post(item):
    """Map a normalized Item to the shape templates expect."""
    imgs = [m['url'] for m in item.get('media', [])
            if m.get('media_type') == 'image' and m.get('url')]
    return {
        'post_id': item.get('id', ''),
        'text': item.get('text', '') or item.get('title', ''),
        'url': item.get('url', ''),
        'created_at': item.get('timestamp', ''),
        'image_urls': imgs,
        'metrics': item.get('metrics') or {},
    }

def _output_posts(platform, account):
    return [_item_to_post(it) for it in _iter_output_items(platform)
            if (it.get('target') or platform) == account]

def get_output_accounts():
    """List (source, target) accounts discovered under output/."""
    accounts = []
    if not OUTPUT_DIR.is_dir():
        return accounts
    counts = {}
    for source_dir in OUTPUT_DIR.iterdir():
        if not source_dir.is_dir() or source_dir.name == 'images':
            continue
        for item in _iter_output_items(source_dir.name):
            key = (source_dir.name, item.get('target') or source_dir.name)
            counts[key] = counts.get(key, 0) + 1
    for (source, target), n in counts.items():
        accounts.append({'platform': source, 'account': target,
                         'path': str(OUTPUT_DIR / source), 'post_count': n})
    return accounts

def _index_if_present():
    """Open index.db beside OUTPUT_DIR if it exists, else None.

    Browse and the account page prefer the index (fast paging/counts on large
    archives); falling back to the filesystem walk keeps them working before
    the first crawl has built one, or if it's deleted (rebuild with
    ``python main.py reindex``).
    """
    path = index_path(OUTPUT_DIR)
    if not path.exists():
        return None
    return PostIndex(path)

def get_accounts():
    """Get accounts discovered in the index, or by walking normalized output."""
    idx = _index_if_present()
    if idx is not None:
        try:
            return [{**a, 'path': str(OUTPUT_DIR / a['platform'])} for a in idx.accounts()]
        finally:
            idx.close()
    return get_output_accounts()

def get_account_stats(platform, account):
    """Get statistics for an account, from the index if present."""
    idx = _index_if_present()
    if idx is not None:
        try:
            return idx.account_stats(platform, account)
        finally:
            idx.close()
    posts = _output_posts(platform, account)
    dates = sorted(p['created_at'] for p in posts if p['created_at'])
    return {
        'post_count': len(posts),
        'image_count': sum(len(p['image_urls']) for p in posts),
        'video_count': 0,
        'latest_post': dates[-1] if dates else '',
        'earliest_post': dates[0] if dates else '',
    }

def _post_from_path(path):
    """Load the full post payload the index only points to, for display."""
    try:
        with open(path, encoding='utf-8') as fh:
            return _item_to_post(json.load(fh))
    except (OSError, json.JSONDecodeError):
        return None

def get_posts(platform, account, limit=50, offset=0):
    """Get posts for an account with pagination, from the index if present.

    The index gives fast counts and paging without walking the whole
    account's directory; only the page's own JSON files are read back for
    the full post payload (image_urls, metrics, url).
    """
    idx = _index_if_present()
    if idx is not None:
        try:
            page = idx.list_posts(platform, account, limit=limit, offset=offset)
        finally:
            idx.close()
        posts = [p for p in (_post_from_path(row['path']) for row in page['posts']) if p]
        page['posts'] = posts
        return page
    try:
        posts = _output_posts(platform, account)

        # Sort by created_at descending (newest first), then reverse for oldest first display
        posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        posts.reverse()  # Oldest first for display

        end_idx = offset + limit
        return {
            'posts': posts[offset:end_idx],
            'total': len(posts),
            'has_more': end_idx < len(posts),
            'offset': offset,
            'limit': limit
        }
    except Exception as e:
        return {'error': str(e), 'posts': [], 'total': 0}

def run_archiver_background(trigger="manual"):
    """Run the normalized multi-source orchestrator in a background thread."""
    global is_archiving
    try:
        cfg = crawler_cli.load_yaml("config/config.yaml")
        crawler_cli.logger = crawler_cli.setup_logging(
            verbose=cfg.get("verbose", False),
            debug=cfg.get("debug", False),
            log_file=cfg.get("log_file"),
        )
        crawler_cli.cmd_crawl(cfg, "config/targets.yaml", trigger=trigger)
    except Exception as e:
        print(f"Archiver error: {e}")
    finally:
        with archive_lock:
            is_archiving = False


def start_archive(trigger="manual"):
    """Start one crawl if another one is not already running.

    Delegates to web_progress.start_run, which threads a call to
    crawler_cli.cmd_crawl (the same entry point the scheduler uses) and keeps
    in-memory per-target progress state for /api/run/status.
    """
    import web_progress
    return bool(web_progress.start_run(trigger))


def _schedule_seconds(config):
    """Convert the optional schedule interval to seconds; zero disables it."""
    try:
        minutes = float((config.get("schedule") or {}).get("interval_minutes", 0))
    except (TypeError, ValueError):
        return 0.0
    return minutes * 60 if math.isfinite(minutes) and minutes > 0 else 0.0


def _scheduler_loop(interval_seconds):
    while not scheduler_stop.wait(interval_seconds):
        start_archive("scheduled")


def start_scheduler():
    """Enable configured periodic crawls for this dashboard process."""
    global scheduler_thread, schedule_interval_minutes
    cfg = crawler_cli.load_yaml("config/config.yaml")
    interval_seconds = _schedule_seconds(cfg)
    schedule_interval_minutes = interval_seconds / 60
    if not interval_seconds:
        return
    if scheduler_thread and scheduler_thread.is_alive():
        return
    scheduler_stop.clear()
    scheduler_thread = threading.Thread(
        target=_scheduler_loop, args=(interval_seconds,), daemon=True
    )
    scheduler_thread.start()

@app.route('/')
def index():
    """Landing dashboard — tab strip + summary tiles + recent-runs panel."""
    ctx = _stage_context(active='')
    return render_template(
        'index.html',
        accounts=get_accounts(),
        is_archiving=is_archiving,
        tabs=ctx['tabs'],
        active_label=ctx['active_label'],
        stage_actions=ctx['stage_actions'],
    )


@app.route('/browse')
def browse():
    """Browse stage — stats grid + accounts grid."""
    ctx = _stage_context(active='browse')
    return render_template(
        'stages/browse.html',
        tabs=ctx['tabs'],
        active_label=ctx['active_label'],
        stage_actions=ctx['stage_actions'],
    )


@app.route('/dashboard')
def legacy_dashboard():
    """Backwards-compat: old /dashboard link -> /browse."""
    return redirect('/browse', code=302)

@app.route('/account/<platform>/<path:account>')
def view_account(platform, account):
    """View posts for a specific account."""
    stats = get_account_stats(platform, account)
    posts_data = get_posts(platform, account, limit=20, offset=0)
    
    return render_template('account.html', 
                         platform=platform, 
                         account=account,
                         stats=stats,
                         posts_data=posts_data)

@app.route('/api/posts/<platform>/<path:account>')
def api_get_posts(platform, account):
    """API endpoint to get more posts."""
    try:
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        posts_data = get_posts(platform, account, limit=limit, offset=offset)
        return jsonify(posts_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/archive/start', methods=['POST'])
def api_start_archive():
    """Start archiving in background."""
    if not start_archive():
        return jsonify({'status': 'already_running'})
    return jsonify({'status': 'started'})

@app.route('/api/archive/status')
def api_archive_status():
    """Get archiving status."""
    return jsonify({
        'is_archiving': is_archiving,
        'schedule_interval_minutes': schedule_interval_minutes,
        'accounts': get_accounts()
    })

@app.route('/api/archive/history')
def api_archive_history():
    """Return persisted crawl outcomes, newest first."""
    cfg = crawler_cli.load_yaml("config/config.yaml", required=False)
    history = RunHistory(run_history_path(cfg), crawler_cli.logger)
    return jsonify({'runs': history.recent()})


@app.route('/api/run/history')
def api_run_history():
    """Alias for /api/archive/history — keeps the new Run tab namespaced."""
    return api_archive_history()


@app.route('/run')
def stage_run():
    ctx = _stage_context(active='run')
    return render_template(
        'stages/run.html',
        tabs=ctx['tabs'],
        active_label=ctx['active_label'],
        stage_actions=ctx['stage_actions'],
    )


@app.route('/api/run/start', methods=['POST'])
def api_run_start():
    import web_progress
    body = request.get_json(silent=True) or {}
    trigger = body.get("trigger", "manual")
    run_id = web_progress.start_run(trigger)
    return jsonify({"ok": True, "run_id": run_id})


@app.route('/api/run/status')
def api_run_status():
    import web_progress
    return jsonify(web_progress.snapshot())


# ── Stage routes ──────────────────────────────────────────────────────────────

@app.route('/schedule')
def stage_schedule():
    ctx = _stage_context(active='schedule')
    return render_template(
        'stages/schedule.html',
        tabs=ctx['tabs'],
        active_label=ctx['active_label'],
        stage_actions=ctx['stage_actions'],
    )


@app.route('/api/config/schedule', methods=['GET', 'POST'])
def api_config_schedule():
    if request.method == 'GET':
        cfg = crawler_cli.load_yaml("config/config.yaml", required=False) or {}
        schedule_block = cfg.get("schedule") or {}
        return jsonify({
            "yaml_value": float(schedule_block.get("interval_minutes", 0) or 0),
            "active_value": schedule_interval_minutes,
        })
    # POST — write YAML.
    body = request.get_json(silent=True) or {}
    try:
        new_minutes = float(body.get("interval_minutes", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "interval_minutes must be a number"}), 400
    cfg = crawler_cli.load_yaml("config/config.yaml", required=False) or {}
    cfg["schedule"] = {"interval_minutes": new_minutes}
    _atomic_write_yaml("config/config.yaml", cfg)
    return jsonify({"ok": True, "yaml_value": new_minutes, "active_value": schedule_interval_minutes})


TARGETS_PATH = "config/targets.yaml"


def _load_targets():
    """Return the targets list from config/targets.yaml; [] if missing/empty."""
    data = crawler_cli.load_yaml(TARGETS_PATH, required=False) or {}
    rows = data.get("targets") or []
    return [r for r in rows if isinstance(r, dict) and r.get("source") and r.get("target")]


@app.route('/configure')
def stage_configure():
    ctx = _stage_context(active='configure')
    return render_template(
        'stages/configure.html',
        tabs=ctx['tabs'],
        active_label=ctx['active_label'],
        stage_actions=ctx['stage_actions'],
    )


@app.route('/api/config/targets', methods=['GET', 'POST'])
def api_config_targets():
    """GET -> list. POST -> replace full list with body['targets']."""
    if request.method == 'GET':
        return jsonify({"targets": _load_targets()})
    body = request.get_json(silent=True) or {}
    rows = body.get("targets")
    if not isinstance(rows, list):
        return jsonify({"error": "targets must be a list"}), 400
    clean = [r for r in rows
             if isinstance(r, dict) and isinstance(r.get("source"), str) and isinstance(r.get("target"), str)]
    _atomic_write_yaml(TARGETS_PATH, {"targets": clean})
    return jsonify({"ok": True, "targets": clean})


@app.route('/api/config/targets/add', methods=['POST'])
def api_config_targets_add():
    """Append a single {source, target} row; validates source against the registry."""
    from core import registry
    body = request.get_json(silent=True) or {}
    source = (body.get("source") or "").strip()
    target = (body.get("target") or "").strip()
    if not source or not target:
        return jsonify({"error": "source and target are required"}), 400
    if source not in registry.available_sources():
        return jsonify({"error": f"unknown source '{source}'",
                        "known_sources": registry.available_sources()}), 400
    rows = _load_targets()
    if any(r.get("source") == source and r.get("target") == target for r in rows):
        return jsonify({"error": "duplicate row", "targets": rows}), 409
    rows.append({"source": source, "target": target})
    _atomic_write_yaml(TARGETS_PATH, {"targets": rows})
    return jsonify({"ok": True, "targets": rows})


@app.route('/api/config/targets/remove', methods=['POST'])
def api_config_targets_remove():
    """Remove the row whose (source,target) matches body."""
    body = request.get_json(silent=True) or {}
    source = body.get("source")
    target = body.get("target")
    rows = _load_targets()
    kept = [r for r in rows if not (r.get("source") == source and r.get("target") == target)]
    if len(kept) == len(rows):
        return jsonify({"error": "row not found", "targets": rows}), 404
    _atomic_write_yaml(TARGETS_PATH, {"targets": kept})
    return jsonify({"ok": True, "targets": kept})


# Sensitive keys whose values are returned masked.
_STORAGE_SECRETS = {"s3.endpoint_url", "gcs.project", "azure.connection_string"}


def _mask_storage(block):
    """Mask sensitive values inside the storage block; leaves the rest alone."""
    out = json.loads(json.dumps(block))  # deep-copy via JSON
    for path in _STORAGE_SECRETS:
        section, key = path.split(".", 1)
        sec = out.get(section)
        if isinstance(sec, dict) and sec.get(key):
            sec[key] = "***"
    return out


@app.route('/storage')
def stage_storage():
    ctx = _stage_context(active='storage')
    return render_template(
        'stages/storage.html',
        tabs=ctx['tabs'],
        active_label=ctx['active_label'],
        stage_actions=ctx['stage_actions'],
    )


@app.route('/api/config/storage', methods=['GET', 'POST'])
def api_config_storage():
    cfg = crawler_cli.load_yaml("config/config.yaml", required=False) or {}
    block = cfg.get("storage") or {"backend": "filesystem"}
    if request.method == 'GET':
        return jsonify({"storage": _mask_storage(block)})
    body = request.get_json(silent=True) or {}
    new_block = body.get("storage")
    if not isinstance(new_block, dict):
        return jsonify({"error": "storage must be an object"}), 400
    backend = str(new_block.get("backend", "filesystem")).lower()
    if backend not in {"filesystem", "s3", "gcs", "azure"}:
        return jsonify({"error": f"unknown backend '{backend}'"}), 400
    # If a masked value ("***") was returned to the client and the client
    # posts it back unchanged, preserve the on-disk value rather than blank it.
    on_disk = json.loads(json.dumps(block))
    for path in _STORAGE_SECRETS:
        section, key = path.split(".", 1)
        sec = new_block.get(section)
        if isinstance(sec, dict) and sec.get(key) == "***":
            sec[key] = (on_disk.get(section) or {}).get(key, "")
    cfg["storage"] = new_block
    _atomic_write_yaml("config/config.yaml", cfg)
    return jsonify({"ok": True, "storage": _mask_storage(new_block)})


# Per-source secrets whose values are returned masked to the client.
# The same value is masked as `***` and substituted back to the on-disk
# value if the client posts the sentinel (avoids accidental blanking).
_SOURCE_SECRETS = {
    "reddit":   ["client_secret"],
    "twitter":  [],  # currently no secrets in twitter block
    "facebook": ["graph_token"],
}


def _mask_sources(block):
    """Return a deep copy of the sources block with secret fields masked."""
    out = json.loads(json.dumps(block))
    for source, keys in _SOURCE_SECRETS.items():
        sec = out.get(source)
        if not isinstance(sec, dict):
            continue
        for k in keys:
            if sec.get(k):
                sec[k] = "***"
    return out


@app.route('/connect')
def stage_connect():
    ctx = _stage_context(active='connect')
    return render_template(
        'stages/connect.html',
        tabs=ctx['tabs'],
        active_label=ctx['active_label'],
        stage_actions=ctx['stage_actions'],
    )


@app.route('/api/config/sources', methods=['GET', 'POST'])
def api_config_sources():
    from core import registry
    cfg = crawler_cli.load_yaml("config/config.yaml", required=False) or {}
    block = cfg.get("sources") or {}
    if request.method == 'GET':
        return jsonify({
            "sources": _mask_sources(block),
            "available": registry.available_sources(),
        })
    body = request.get_json(silent=True) or {}
    new_block = body.get("sources")
    if not isinstance(new_block, dict):
        return jsonify({"error": "sources must be an object"}), 400
    known = set(registry.available_sources())
    unknown = [k for k in new_block if k not in known]
    if unknown:
        return jsonify({"error": f"unknown source(s): {', '.join(unknown)}"}), 400
    # Preserve masked values: client posts "***" -> keep on-disk value.
    on_disk = json.loads(json.dumps(block))
    for source, keys in _SOURCE_SECRETS.items():
        sec = new_block.get(source)
        if not isinstance(sec, dict):
            continue
        for k in keys:
            if sec.get(k) == "***":
                sec[k] = (on_disk.get(source) or {}).get(k, "")
    cfg["sources"] = new_block
    _atomic_write_yaml("config/config.yaml", cfg)
    return jsonify({"ok": True, "sources": _mask_sources(new_block)})

@app.route('/api/stats')
def api_stats():
    """Get overall statistics."""
    accounts = get_accounts()
    total_posts = 0
    total_images = 0
    total_videos = 0
    
    for account in accounts:
        stats = get_account_stats(account['platform'], account['account'])
        if 'post_count' in stats:
            total_posts += stats['post_count']
        if 'image_count' in stats:
            total_images += stats['image_count']
        if 'video_count' in stats:
            total_videos += stats['video_count']
    
    return jsonify({
        'total_accounts': len(accounts),
        'total_posts': total_posts,
        'total_images': total_images,
        'total_videos': total_videos,
        'accounts': accounts
    })

if __name__ == '__main__':
    start_scheduler()
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
