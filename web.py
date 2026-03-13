"""
Web Dashboard for Social Media Archiver.

Provides a user-friendly interface for:
- Starting/stopping archiving operations
- Viewing archived posts by account
- Monitoring progress and statistics
"""

import os
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Add src to path so we can import modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import SocialMediaArchiver

app = Flask(__name__)
app.config['SECRET_KEY'] = 'social-media-archiver-key'

# Global variables for background tasks
archiver = None
archive_thread = None
is_archiving = False

def get_accounts():
    """Get list of archived accounts."""
    archives_path = Path('./archives')
    accounts = []
    
    if not archives_path.exists():
        return accounts
    
    for platform_dir in archives_path.iterdir():
        if not platform_dir.is_dir():
            continue
        
        platform = platform_dir.name
        for account_dir in platform_dir.iterdir():
            if not account_dir.is_dir():
                continue
            
            account = account_dir.name
            accounts.append({
                'platform': platform,
                'account': account,
                'path': str(account_dir)
            })
    
    return accounts

def get_account_stats(platform, account):
    """Get statistics for a specific account."""
    try:
        archiver_instance = SocialMediaArchiver()
        stats = archiver_instance.storage.get_stats(platform, account)
        metadata = archiver_instance.storage.get_metadata(platform, account)
        return {**stats, **metadata}
    except Exception as e:
        return {'error': str(e)}

def get_posts(platform, account, limit=50, offset=0):
    """Get posts for an account with pagination."""
    try:
        archiver_instance = SocialMediaArchiver()
        posts = archiver_instance.storage.get_posts(platform, account)
        
        # Sort by created_at descending (newest first), then reverse for oldest first display
        posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        posts.reverse()  # Oldest first for display
        
        # Apply pagination
        start_idx = offset
        end_idx = offset + limit
        paginated_posts = posts[start_idx:end_idx]
        
        return {
            'posts': paginated_posts,
            'total': len(posts),
            'has_more': end_idx < len(posts),
            'offset': offset,
            'limit': limit
        }
    except Exception as e:
        return {'error': str(e), 'posts': [], 'total': 0}

def run_archiver_background():
    """Run the archiver in a background thread."""
    global is_archiving
    try:
        is_archiving = True
        archiver_instance = SocialMediaArchiver()
        archiver_instance.run_all()
    except Exception as e:
        print(f"Archiver error: {e}")
    finally:
        is_archiving = False

@app.route('/')
def index():
    """Main dashboard page."""
    accounts = get_accounts()
    return render_template('index.html', accounts=accounts, is_archiving=is_archiving)

@app.route('/account/<platform>/<account>')
def view_account(platform, account):
    """View posts for a specific account."""
    stats = get_account_stats(platform, account)
    posts_data = get_posts(platform, account, limit=20, offset=0)
    
    return render_template('account.html', 
                         platform=platform, 
                         account=account,
                         stats=stats,
                         posts_data=posts_data)

@app.route('/api/posts/<platform>/<account>')
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