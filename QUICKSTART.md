# Quick Start - 5 Minute Setup

## TL;DR

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create config
cp config/config.example.json config/config.json

# 3. Edit config with your account
# (change "username_to_archive" to a real Twitter account)
# Edit with your favorite editor: config/config.json

# 4. Start web dashboard
python run_web.py
# or: python web.py

# 5. Open http://localhost:5000 in your browser
# Click "Start Archiving" then "View Posts"
```

## Detailed Steps

### Step 1: Install

```bash
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Configure

Copy example config:
```bash
cp config/config.example.json config/config.json
```

Edit `config/config.json` and change:
```json
"account": "username_to_archive"   // → Your target account name
"batch_size": 50                   // # posts per scrape
"scrape_interval_days": 7          // Go back this many days per batch
```

### Step 3: Start Web Dashboard

```bash
python run_web.py
```

Open http://localhost:5000 in your browser.

### Step 4: Use the Web Interface

1. **Dashboard**: See stats and archived accounts
2. **Start Archiving**: Click the green "Start Archiving" button
3. **View Posts**: Click "View Posts" on any account card
4. **Browse Posts**: Posts display oldest-to-newest in wide desktop format
5. **Get More**: Click "Get More Posts" to load additional posts

### Step 5: Alternative - CLI Usage

You can also use the command line:

```bash
# Run archiving
python archiver.py

# Show statistics
python archiver.py --stats
```

## What's Happening?

1. **Scraper** fetches from Nitter RSS (no API key needed)
2. **Storage** saves posts to `posts.jsonl` (one post per line)
3. **Metadata** tracks account info and scrape status
4. **Batching** prevents re-scraping the same posts

## Common Next Steps

### Run Again Later (Get New Posts)
```bash
python archiver.py
```
It will skip already-archived posts and grab new ones.

### Download Images Too
Edit `config.json`:
```json
"media_download": {
  "images": true,
  "videos": false
}
```
Then run again.

### Archive Multiple Accounts
Add more sources to `config.json`:
```json
"sources": [
  {"account": "user1", ...},
  {"account": "user2", ...}
]
```

### Switch Nitter Instance
If `nitter.net` is slow, try:
```json
"nitter_instance": "https://nitter.1d4.us"
```

Other options:
- `https://nitter.nixnet.services`
- `https://nitter.fdn.fr`
- `https://nitter.koussih.rocks`

## Troubleshooting

**"No posts found"**
- Account is private or doesn't exist
- Nitter instance is down → try another in the list above

**"ModuleNotFoundError: feedparser"**
```bash
pip install -r requirements.txt
```

**"config.json not found"**
```bash
cp config/config.example.json config/config.json
```

**"Connection timeout"**
- Nitter instance might be overloaded
- Wait a minute and try again
- Try a different Nitter instance

## Understanding the Output

### posts.jsonl Format
Each line is one tweet:
```json
{
  "post_id": "1234567890",
  "created_at": "2024-01-15T10:30:45Z",
  "text": "Content of the tweet",
  "url": "https://twitter.com/user/status/1234567890",
  "author": {"username": "user"},
  "metrics": {"likes": 100, "retweets": 50, "replies": 10}
}
```

### metadata.json
Tracks archiving progress:
```json
{
  "account_created_at": "2016-05-01T00:00:00Z",
  "last_scrape_at": "2024-03-12T12:00:00Z",
  "total_posts_archived": 5000,
  "last_scrape_posts": 50
}
```

## Advanced Topics

See [DEVELOPMENT.md](DEVELOPMENT.md) for:
- Project architecture
- Adding new features
- Performance optimization
- Rate limiting and ethics

See [README.md](README.md) for:
- Full feature list
- Roadmap (cloud, mirroring, etc.)
- Complete configuration reference
- Troubleshooting guide

## Tips

- **Start small**: Archive 50 posts first, then increase
- **Run incrementally**: Re-run every day/week to catch new posts
- **Add media later**: Start without images, enable them after text is done
- **Monitor progress**: Use `--stats` flag to see what's been archived

```bash
python archiver.py --stats
```

## Next Steps

1. ✅ Install dependencies
2. ✅ Create config
3. ✅ Run archiver
4. 📚 Read [README.md](README.md) for advanced features
5. 🛠️ Check [DEVELOPMENT.md](DEVELOPMENT.md) to contribute

Happy archiving! 📚
