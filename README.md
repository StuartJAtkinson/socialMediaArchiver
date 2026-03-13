# socialMediaArchiver

A Python-based tool to archive social media posts locally with intelligent batch scraping, metadata tracking, and support for media downloads.

**Current Status**: Core local archiving ✅ | Cloud/Mirror features 🔄 (Roadmap)

## Features

### ✅ Implemented (Phase 1)

- **RSS/Nitter-based scraping** - No API keys needed, scrapes via Nitter RSS feeds
- **Local storage** with organized folder structure:
  ```
  archives/
  └── twitter/
      └── {account}/
          ├── posts.jsonl (text DB)
          ├── metadata.json (account info, scrape status)
          ├── images/ (optional)
          └── videos/ (optional)
  ```
- **Smart batch processing**:
  - Automatically calculates date-based scrape batches
  - Tracks account creation date
  - Prevents re-scraping existing posts
  - Customizable batch size & interval
  
- **Media download** (optional):
  - Download images and videos from posts
  - Organized by post ID
  - Back-fillable (can download later)
  
- **Progress tracking**:
  - Metadata stored per account
  - Scrape history and timestamps
  - Estimated time to completion
  - Post counts and statistics

### 🔄 Roadmap (Phase 2+)

- **Cloud storage output** - Save to S3, GCS, Azure Blob
- **Mirror posting to social media** - Cross-post to other platforms via APIs
- **Slow mirror posting** - Rate-limit friendly posting without API spam
- **Configuration presets** - Save and reload configurations
- **Web dashboard** - Visualize archiving progress

## Installation

### Requirements
- Python 3.8+
- pip (Python package manager)

### Setup

1. **Clone/navigate to the project**:
   ```bash
   cd socialMediaArchiver
   ```

2. **Create virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure (CLI)

Copy the example config:
```bash
cp config/config.example.json config/config.json
```

Edit `config/config.json` with your accounts.

### 3. Run CLI Archiver

```bash
python archiver.py
```

### 4. Run Web Dashboard (New!)

```bash
python web.py
```

Then open http://localhost:5000 in your browser.

**Web Dashboard Features:**
- 📊 Real-time statistics dashboard
- 🚀 One-click archiving from the browser
- 📱 View posts in desktop-optimized wide format
- 📄 Infinite scroll with "Get More" button
- 👀 Post details with images and metrics

## Configuration Reference

```json
{
  "sources": [
    {
      "id": "unique_id",
      "platform": "twitter",
      "account": "twitter_handle",
      
      // Scraping method
      "scrape_method": "nitter|api|html",  // Currently "nitter" recommended
      "nitter_instance": "https://nitter.net",  // Use this Nitter instance
      
      // Batch settings (smart incremental scraping)
      "batch_config": {
        "batch_size": 50,              // Posts per batch
        "scrape_interval_days": 7      // Go back N days per batch
      },
      
      // Media download options
      "media_download": {
        "images": true,
        "videos": false
      },
      
      // Output configurations
      "outputs": {
        "local": {
          "enabled": true,
          "path": "./archives"
        },
        "cloud": {
          "enabled": false,
          "provider": "s3|gcs|azure"  // ROADMAP
        },
        "mirror_post": {
          "enabled": false,
          "platforms": []  // ROADMAP
        },
        "slow_mirror_post": {
          "enabled": false  // ROADMAP
        }
      }
    }
  ]
}
```

## Project Structure

```
socialMediaArchiver/
├── src/
│   ├── main.py              # Entry point, orchestrator
│   ├── scraper.py           # Twitter/RSS scraping logic
│   ├── storage.py           # Local storage management
│   └── batch_processor.py   # Smart batch date calculation
├── templates/               # Web dashboard HTML templates
│   ├── index.html          # Main dashboard
│   └── account.html        # Account post viewer
├── config/
│   └── config.example.json  # Configuration template
├── archives/                # Output folder (created on first run)
├── web.py                  # Web dashboard (Flask app)
├── archiver.py            # CLI entry point
├── requirements.txt        # Python dependencies
└── README.md
```

## How It Works

### 1. Account Detection & Batch Planning
- Determines account creation date (fallback: 2006)
- Divides timeline into date-based batches
- Avoids re-scraping existing posts with deduplication

### 2. Smart Scraping
- Uses Nitter RSS for rate-limit friendly access
- Fetches in configured batches (e.g., 50 posts per run)
- Supports running repeatedly to catch new posts

### 3. Local Storage
- **posts.jsonl**: Append-only JSON Lines format (efficient, queryable)
- **metadata.json**: Account info, last scrape timestamp, stats
- **images/ & videos/**: Optional media files organized by post_id

### 4. Media Back-filling
- Run with media downloads disabled first to archive text quickly
- Enable media downloads later to download via post URLs
- Can re-run to fill in missing media

## Advanced Usage

### Archive Multiple Accounts

Add multiple sources in `config.json`:
```json
{
  "sources": [
    {"account": "user1", ...},
    {"account": "user2", ...},
    {"account": "user3", ...}
  ]
}
```

Then run:
```bash
python main.py
```

All accounts will be archived sequentially.

### Incremental Scraping (Running Repeatedly)

The tool tracks `last_scrape_at` in metadata, so running it again:
```bash
python main.py
```

Will:
- Only scrape posts newer than the last run
- Skip posts already archived
- Update metadata with new timestamps

**Frequency**: Safe to run every hour, day, or week depending on account activity.

### Back-fill Media

Originally run without media:
```json
"media_download": {"images": false, "videos": false}
```

Later, enable downloads:
```json
"media_download": {"images": true, "videos": false}
```

Re-run `main.py` to download images for all posts.

### Estimate Scrape Time

The tool prints estimates before scraping:
```
Estimated posts to scrape: 5000
Estimated time: 2.78 hours
```

This helps plan when to run the archiver.

## Roadmap

### Phase 2: Cloud Storage
- [  ] Save posts to S3, GCS, or Azure Blob
- [  ] Configuration for cloud credentials
- [  ] Parallel uploads for media files
- [  ] Backup strategy

### Phase 3: Mirror Posting
- [  ] Post to Mastodon instances
- [  ] Post to Bluesky
- [  ] Post to Facebook (via API)
- [  ] Custom webhook posting

### Phase 4: Slow Mirroring
- [  ] Browser automation for slow posting (avoids API limits)
- [  ] Scheduling engine (post at specific times)
- [  ] Status tracking (which posts posted where)
- [  ] Retry mechanism for failed posts

### Phase 5+: Polish & Scale
- [  ] Web dashboard for management
- [  ] Database alternative to JSONL (SQLite, PostgreSQL)
- [  ] Batch processing on schedule (cron/systemd)
- [  ] Duplicate detection across platforms
- [  ] Full-text search of archived posts

## Troubleshooting

### Config file not found
```
Config file not found: ./config/config.json
```
Run: `cp config/config.example.json config/config.json`

### No posts found
```
No posts found for {account}
```
- Account doesn't exist or is private
- Nitter instance is down → try different instance in config
- Account may be suspended

### Nitter instance unreliable?
Try these alternatives:
- `https://nitter.net` (primary)
- `https://nitter.1d4.us`
- `https://nitter.nixnet.services`
- `https://nitter.fdn.fr`

Set in config: `"nitter_instance": "https://nitter.1d4.us"`

### Media downloads failing
Check:
- Network connectivity
- URL format in posts (may be shortened via t.co)
- Disk space available
- File permissions in `archives/`

## Performance Notes

- **Nitter RSS**: ~50 posts per request, 1-2 seconds per batch
- **Full-timeline archiving**: Typically 2-5 hours for active accounts
- **Incremental updates**: ~30 seconds to fetch latest posts
- **Media downloads**: Depends on file size (100MB+ for video-heavy accounts)

## Limitations

- **Nitter-based**: Limited to public data that Nitter can access
- **No deleted posts**: Only archive what's currently public
- **No replies context**: Tweets may not include full thread context
- **Media URLs**: Some shortened URLs (t.co) may not be retrievable

## Contributing

Planned features welcome! Areas for contribution:
- [ ] Database backends (SQLite, PostgreSQL)
- [ ] Additional scraping methods (API, HTML)
- [ ] Cloud storage integration
- [ ] Mirror posting platforms
- [ ] Web UI dashboard
- [ ] Performance optimizations

## License

MIT License - See LICENSE file (if created)

## Disclaimer

This tool is for personal archiving and backup purposes. Always respect:
- Platform terms of service
- User privacy and copyright
- Local laws regarding data collection
- Rate limits and responsible scraping practices

Use at your own risk.
