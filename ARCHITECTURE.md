# Architecture Overview

## Data Flow

```
Twitter/X Account
        ↓
   Nitter Instance (RSS Feed)
        ↓
   scraper.py (TwitterScraper)
        ↓
   Parsed Post Objects
        ↓
   ┌─────────────────────────────────────────┐
   │     main.py (SocialMediaArchiver)       │
   │  Orchestrates the entire workflow       │
   └─────────────────────────────────────────┘
        ↓
   batch_processor.py
   Determines scrape windows
        ↓
   storage.py (StorageManager)
        ↓
   ┌──────────────────────────────────────────────┐
   │  Local Filesystem Structure                  │
   │                                              │
   │  archives/twitter/account/                  │
   │  ├── posts.jsonl (text & URLs)             │
   │  ├── metadata.json (scrape status)         │
   │  ├── images/ (optional downloads)          │
   │  └── videos/ (optional downloads)          │
   └──────────────────────────────────────────────┘
        ↓
   [ROADMAP] Cloud Outputs (S3, GCS, Azure)
        ↓
   [ROADMAP] Mirror Posting (API-based)
        ↓
   [ROADMAP] Slow Mirroring (Rate-limit friendly)
```

## Module Dependency Graph

```
archiver.py (CLI entry point)
    │
    └─→ main.py (SocialMediaArchiver)
            │
            ├─→ scraper.py (TwitterScraper)
            │   └─→ MediaDownloader
            │
            ├─→ storage.py (StorageManager)
            │
            └─→ batch_processor.py (BatchProcessor)
```

## Configuration Flow

```
config/config.example.json (template)
                ↓
        cp → config/config.json (actual)
                ↓
        parsed by main.py
                ↓
        for each source:
            ├─→ create scraper
            ├─→ check batch processor
            ├─→ fetch posts
            ├─→ save via storage
            ├─→ download media
            └─→ update metadata
```

## Storage Schema

### Directory Structure
```
archives/
├── twitter/
│   ├── account_1/
│   │   ├── posts.jsonl           ← All posts (append-only)
│   │   ├── metadata.json         ← Account info & status
│   │   ├── images/
│   │   │   ├── 123_0.jpg
│   │   │   └── 123_1.png
│   │   └── videos/
│   │       └── 456_0.mp4
│   │
│   └── account_2/
│       ├── posts.jsonl
│       ├── metadata.json
│       └── ...
│
├── mastodon/                     ← Future: other platforms
│   ├── instance_1/
│   │   └── ...
│   └── ...
│
└── bluesky/                      ← Future: other platforms
    └── ...
```

### posts.jsonl Format
```
{"post_id": "1", "created_at": "2024-01-01T00:00:00Z", ...}\n
{"post_id": "2", "created_at": "2024-01-01T01:00:00Z", ...}\n
{"post_id": "3", "created_at": "2024-01-01T02:00:00Z", ...}\n
```

### metadata.json Format
```json
{
  "account_created_at": "2016-05-01T00:00:00Z",
  "last_scrape_at": "2024-03-12T12:00:00Z",
  "total_posts_archived": 5000,
  "last_scrape_posts": 50,
  "followers": null,
  "description": null
}
```

## Execution Flow

```
1. CLI: archiver.py
         ↓
2. Load config from config.json
         ↓
3. For each source in config:
         ↓
4. Initialize scraper (Nitter RSS)
         ↓
5. Load existing metadata
         ↓
6. Calculate batch windows (batch_processor)
         ↓
7. Show estimate (posts, time)
         ↓
8. Scrape posts (scraper.py)
         ↓
9. For each post:
    ├─→ Check if already archived (dedup)
    ├─→ Save post text to JSONL (storage.py)
    ├─→ If media enabled:
    │   ├─→ Download images
    │   └─→ Download videos
    └─→ Increment counter
         ↓
10. Update metadata with:
    ├─→ last_scrape_at (timestamp)
    ├─→ total_posts_archived (count)
    └─→ last_scrape_posts (count)
         ↓
11. Print summary
         ↓
12. Next source (or exit if none)
```

## Batch Processing Logic

```
Inputs:
  • account_created_at = "2016-05-01"
  • last_scraped_at = "2024-03-11T12:00:00Z"
  • scrape_interval_days = 7
  • batch_size = 50

Process:
  Current date: 2024-03-12
  
  Working backwards from last_scraped_at:
  
  Batch 1: 2024-03-05 to 2024-03-12 (7 days, ~50 posts)
  Batch 2: 2024-02-26 to 2024-03-05 (7 days, ~50 posts)
  Batch 3: 2024-02-19 to 2024-02-26 (7 days, ~50 posts)
  ...
  Last Batch: 2016-05-01 to ~2016-05-08 (account creation date)

Output:
  Estimated total batches: 627
  Estimated total posts: 31,350
  Estimated hours to scrape: ~4.36 hours
```

## Feature Phases

### Phase 1: ✅ LOCAL ARCHIVING (IMPLEMENTED)
- [x] Nitter RSS scraping
- [x] Local storage (JSONL + metadata)
- [x] Smart batch processing
- [x] Media downloading (optional)
- [x] Deduplication
- [x] Progress tracking

### Phase 2: 🔄 CLOUD STORAGE (ROADMAP)
- [ ] AWS S3 output
- [ ] Google Cloud Storage (GCS)
- [ ] Azure Blob Storage
- [ ] Configuration for credentials
- [ ] Parallel uploads

### Phase 3: 🔄 MIRROR POSTING (ROADMAP)
- [ ] Mastodon API posting
- [ ] Bluesky posting
- [ ] Facebook API posting
- [ ] Custom webhooks
- [ ] Attribution/credits

### Phase 4: 🔄 SLOW MIRRORING (ROADMAP)
- [ ] Browser automation (Selenium/Playwright)
- [ ] Rate-limit aware scheduling
- [ ] Status tracking (posted/pending)
- [ ] Retry mechanism
- [ ] Log posting history

### Phase 5: 🔄 POLISH & SCALE (ROADMAP)
- [ ] Web dashboard UI
- [ ] Database backends (SQLite, PostgreSQL)
- [ ] Full-text search
- [ ] Duplicate detection across platforms
- [ ] Scheduled archiving (cron/systemd)
- [ ] Performance optimization

## Technology Stack

### Current
- **Python 3.8+** - Core language
- **feedparser** - RSS feed parsing
- **requests** - HTTP requests

### Phase 2+
- **boto3** - AWS SDK
- **google-cloud-storage** - GCS SDK
- **azure-storage-blob** - Azure SDK
- **mastodon.py** - Mastodon API
- **atproto** - Bluesky API

### Future Considerations
- **asyncio** - Async I/O for performance
- **SQLAlchemy** - ORM for database abstraction
- **Flask/FastAPI** - Web dashboard
- **Selenium/Playwright** - Browser automation
- **APScheduler** - Task scheduling
- **PostgreSQL/SQLite** - Data persistence

## Configuration Hierarchy

```
Defaults (hard-coded)
    ↓
System Environment Variables (.env file)
    ↓
config/config.json
    ↓
CLI Arguments
```

## Error Handling Strategy

```
Network Errors
├─→ Nitter instance unreachable: Suggest alternative instances
├─→ Timeout: Show guidance (might be overloaded)
└─→ Connection refused: Check Nitter URL in config

Storage Errors
├─→ Permission denied: Check folder permissions
├─→ Disk full: Suggest cleanup
└─→ Invalid path: Show valid paths

Config Errors
├─→ Missing config file: Offer to create from example
├─→ Invalid JSON: Show parse error with line number
└─→ Missing required fields: List missing fields

Post Parsing Errors
├─→ Malformed entry: Log and skip
└─→ Missing post_id: Log and skip

Media Download Errors
├─→ Failed URL download: Log and continue
└─→ Unsupported format: Log and skip
```

## Performance Characteristics

### Nitter RSS Scraping
- Single request: ~1-2 seconds
- Bandwidth: ~50KB per batch
- Posts per request: ~50
- Rate: ~1 request per 2 seconds with delays

### Local Storage (JSONL)
- Write: O(1) append operation
- Media files: Depends on size (1-100MB per video)
- Deduplication: O(n) linear scan (faster: hash table in Phase 5)

### Full Timeline Archive
- 10,000 tweets: ~3 hours
- 100,000 tweets: ~30 hours
- 1,000,000 tweets: ~300 hours (~12.5 days)

### Recommended Approaches
- **Active accounts**: Archive overnight, check daily for new posts
- **Historical accounts**: Run in background, can take days
- **Media-heavy**: Skip videos first, download text only
