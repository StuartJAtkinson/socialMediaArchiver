"""
Web Dashboard for Social Media Archiver.

Provides a user-friendly interface for:
- Starting/stopping archiving operations
- Viewing archived posts by account
- Monitoring progress and statistics
"""

import json
import math
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify

import main as crawler_cli
from core.run_history import RunHistory, run_history_path

app = Flask(__name__)
app.config['SECRET_KEY'] = 'social-media-archiver-key'

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

def get_accounts():
    """Get accounts discovered in normalized orchestrator output."""
    return get_output_accounts()

def get_account_stats(platform, account):
    """Get statistics for a normalized-output account."""
    posts = _output_posts(platform, account)
    dates = sorted(p['created_at'] for p in posts if p['created_at'])
    return {
        'post_count': len(posts),
        'image_count': sum(len(p['image_urls']) for p in posts),
        'video_count': 0,
        'latest_post': dates[-1] if dates else '',
        'earliest_post': dates[0] if dates else '',
    }

def get_posts(platform, account, limit=50, offset=0):
    """Get normalized posts for an account with pagination."""
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
    """Start one crawl if another one is not already running."""
    global archive_thread, is_archiving
    with archive_lock:
        if is_archiving:
            return False
        is_archiving = True
        archive_thread = threading.Thread(
            target=run_archiver_background, args=(trigger,), daemon=True
        )
        archive_thread.start()
    return True


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
    """Main dashboard page."""
    accounts = get_accounts()
    return render_template('index.html', accounts=accounts, is_archiving=is_archiving)

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
