"""
Web Dashboard for Social Media Archiver.

Provides a user-friendly interface for:
- Starting/stopping archiving operations
- Viewing archived posts by account
- Monitoring progress and statistics
"""

import json
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify

import main as crawler_cli

app = Flask(__name__)
app.config['SECRET_KEY'] = 'social-media-archiver-key'

# Global variables for background tasks
archive_thread = None
is_archiving = False

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

def run_archiver_background():
    """Run the normalized multi-source orchestrator in a background thread."""
    global is_archiving
    try:
        is_archiving = True
        cfg = crawler_cli.load_yaml("config/config.yaml")
        crawler_cli.logger = crawler_cli.setup_logging(
            verbose=cfg.get("verbose", False),
            debug=cfg.get("debug", False),
            log_file=cfg.get("log_file"),
        )
        crawler_cli.cmd_crawl(cfg, "config/targets.yaml")
    except Exception as e:
        print(f"Archiver error: {e}")
    finally:
        is_archiving = False

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
    global archive_thread, is_archiving
    
    if is_archiving:
        return jsonify({'status': 'already_running'})
    
    # Start archiving in background thread
    archive_thread = threading.Thread(target=run_archiver_background)
    archive_thread.daemon = True
    archive_thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/api/archive/status')
def api_archive_status():
    """Get archiving status."""
    return jsonify({
        'is_archiving': is_archiving,
        'accounts': get_accounts()
    })

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
    app.run(debug=True, host='0.0.0.0', port=5000)
