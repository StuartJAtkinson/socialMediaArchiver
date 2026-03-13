# Development Guide for Social Media Archiver

## Project Architecture

```
socialMediaArchiver/
├── src/
│   ├── __init__.py
│   ├── main.py           # Main orchestrator (entry point)
│   ├── scraper.py        # Scraping logic (Nitter, API, HTML)
│   ├── storage.py        # Local filesystem storage management
│   └── batch_processor.py # Intelligent batch date calculation
├── config/
│   └── config.example.json
├── test/                 # Unit tests (future)
├── archiver.py          # CLI entry point
├── requirements.txt     # Python dependencies
└── README.md           # User documentation
```

## Module Responsibilities

### `main.py` - SocialMediaArchiver Orchestrator
- Loads configuration
- Coordinates scraping, storage, and processing
- Handles error management
- Provides progress reporting

**Key Classes:**
- `SocialMediaArchiver`: Main controller

### `scraper.py` - Social Media Scraping
- Implements scraping strategies (Nitter RSS, API, HTML)
- Parses posts into standard format
- Handles media discovery and downloading

**Key Classes:**
- `TwitterScraper`: Handles Twitter/Nitter scraping
- `MediaDownloader`: Downloads images and videos

**Supported Methods:**
- `nitter` (RSS) - IMPLEMENTED
- `api` (Twitter API v2) - ROADMAP
- `html_scrape` (HTML parsing) - ROADMAP

### `storage.py` - Storage Management
- Manages local filesystem structure
- Implements JSONL-based post storage
- Handles metadata tracking
- Media file organization

**Key Classes:**
- `StorageManager`: Filesystem operations

**Storage Structure:**
```
archives/
└── {platform}/
    └── {account}/
        ├── posts.jsonl      # All posts (append-only)
        ├── metadata.json    # Account info & scrape status
        ├── images/          # Downloaded images
        └── videos/          # Downloaded videos
```

### `batch_processor.py` - Intelligent Batch Processing
- Calculates date-based scrape batches
- Estimates scrape time and coverage
- Prevents duplicate scraping
- Supports incremental updates

**Key Classes:**
- `BatchProcessor`: Batch scheduling logic

## Adding New Features

### Adding a New Scraping Method

Edit `src/scraper.py`:

```python
class TwitterScraper:
    def scrape(self, batch_size=50):
        if self.method == "nitter":
            return self._scrape_nitter(batch_size)
        elif self.method == "my_new_method":
            return self._scrape_my_new_method(batch_size)
        
    def _scrape_my_new_method(self, batch_size):
        # Your scraping logic here
        posts = []
        # ... scrape posts ...
        return posts
```

### Adding a New Output (Cloud, Mirror, etc.)

1. Create new module: `src/outputs/{output_type}.py`
2. Implement handler class
3. Add to config options
4. Call from `main.py` in `archive_source()` method

Example structure:
```python
class S3Output:
    def __init__(self, bucket, region, credentials):
        self.bucket = bucket
        self.region = region
    
    def save_post(self, post_data):
        # Upload to S3
        pass
```

### Adding Configuration Options

1. Update `config/config.example.json` with new option
2. Document in README.md Configuration Reference
3. Handle in `main.py` or relevant module

## Testing

Currently no automated tests. Add to `test/test_*.py`:

```python
import unittest
from src.storage import StorageManager

class TestStorage(unittest.TestCase):
    def test_save_post(self):
        storage = StorageManager('/tmp/test')
        storage.save_post('twitter', 'testuser', {'post_id': '123'})
        # Assert...
```

Run tests:
```bash
python -m unittest discover -s test -p 'test_*.py'
```

## Performance Considerations

### JSONL vs Database
Currently using JSONL (JSON Lines) because:
- ✅ Simple, human-readable
- ✅ Append-only (fast writes)
- ✅ Queryable with simple iteration
- ❌ Not efficient for complex queries across millions of posts

**Future**: Consider SQLite or PostgreSQL for:
- 10M+ posts
- Full-text search
- Complex filtering

### Batch Processing
- Smaller batches = lower memory, more requests
- Larger batches = higher memory, fewer requests
- Default (50 posts) is optimal for Nitter

### Media Downloading
- Image downloads: ~1-2 seconds per image
- Video downloads: ~5-30 seconds per video (size dependent)
- Use `media_download: false` initially, then enable later

## Rate Limiting & Ethics

### Nitter RSS
- No official rate limits (it's a privacy-respecting instance)
- Be respectful: don't hammer with requests
- Recommended: 5-30 second delays between requests
- 1 request per account per batch is fine

### Twitter API (Future)
- 450 requests/15 minutes (research quota)
- 2 million tweets/month (lab quota)
- Never use API for scraping without consent

### Scraping Ethics
- Only archive public posts
- Respect `robots.txt`
- Don't disable Nitter's rate limiting
- Consider user privacy

## Common Development Tasks

### Running locally with config
```bash
cd src
python main.py
```

### Testing with a single account
Edit config.json to have one source, then run

### Checking archived posts
```bash
cat archives/twitter/username/posts.jsonl | python -m json.tool | head -50
```

### Clearing archives (be careful!)
```bash
rm -rf archives/
```

## Debugging Tips

### Add print statements
```python
print(f"DEBUG: post_id={post_id}, saved={saved}")
```

### Log to file
```python
import logging
logging.basicConfig(filename='archiver.log', level=logging.DEBUG)
logging.debug(f"Message: {value}")
```

### Check Nitter instance health
```bash
curl https://nitter.net/twitter
```

### Inspect JSON
```bash
cat archives/twitter/user/posts.jsonl | jq '.[0]'  # First post only
```

## Contributing Checklist

Before submitting changes:
- [ ] Code follows Python PEP 8 style guide
- [ ] Docstrings added for new functions
- [ ] Config.example.json updated if needed
- [ ] README updated for new features
- [ ] No hardcoded credentials
- [ ] Error handling for network issues
- [ ] Progress messages are informative

## Future Architecture Improvements

### Multi-threading
Current: Sequential account processing
Potential: Parallel account scraping with thread pool

### Async I/O
Current: Blocking requests
Potential: `asyncio` + `aiohttp` for faster downloads

### Plugin System
Current: Module-based extensibility
Potential: Plugin loader for third-party scrapers/outputs

### Database Backend
Current: JSONL files
Potential: Pluggable storage (SQLite, PostgreSQL, MongoDB)

### Web UI
Current: CLI only
Potential: Flask/FastAPI web interface for configuration and monitoring

## Questions?

Refer to:
- README.md - User documentation
- Config reference - configuration options
- Code comments - implementation details
- main.py - entry point and workflow
