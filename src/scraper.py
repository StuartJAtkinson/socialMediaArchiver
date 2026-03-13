"""
Scraper module for fetching posts from various sources.

Supports:
- Nitter (RSS feed) - Main recommended method
- Twitter API (future)
- HTML scraping fallback (future)
"""

import feedparser
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin
from email.utils import parsedate_to_datetime


class TwitterScraper:
    """Base scraper for Twitter posts."""
    
    def __init__(self, account: str, method: str = "nitter", nitter_instance: str = "https://nitter.net"):
        self.account = account
        self.method = method
        self.nitter_instance = nitter_instance
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def scrape(self, batch_size: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape posts based on configured method.
        
        Returns:
            List of post dictionaries with structure:
            {
                "post_id": "...",
                "created_at": "2024-01-01T00:00:00Z",
                "text": "...",
                "image_urls": [...],
                "video_urls": [...],
                "author": {...},
                "metrics": {...},
                "url": "..."
            }
        """
        if self.method == "nitter":
            return self._scrape_nitter(batch_size)
        elif self.method == "api":
            return self._scrape_api(batch_size)
        else:
            raise ValueError(f"Unsupported scrape method: {self.method}")

    def _scrape_nitter(self, batch_size: int) -> List[Dict[str, Any]]:
        """Scrape posts from Nitter RSS feed."""
        try:
            rss_url = f"{self.nitter_instance}/{self.account}/rss"
            
            print(f"Fetching RSS from: {rss_url}")
            response = self.session.get(rss_url, timeout=10)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                print(f"No posts found for {self.account}")
                return []
            
            posts = []
            for i, entry in enumerate(feed.entries[:batch_size]):
                post = self._parse_nitter_entry(entry)
                if post:
                    posts.append(post)
            
            return posts
        
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from Nitter: {e}")
            return []

    def _parse_nitter_entry(self, entry: Dict) -> Optional[Dict[str, Any]]:
        """Parse a single Nitter RSS entry."""
        try:
            # Extract post ID from link: https://nitter.net/user/status/123456
            link = entry.get("link", "")
            post_id = link.split("/")[-1] if link else None
            
            if not post_id:
                return None
            
            # Parse timestamp
            published = entry.get("published", "")
            if published:
                try:
                    # Try ISO format first (for future compatibility)
                    created_at = datetime.fromisoformat(published.replace('Z', '+00:00')).isoformat() + 'Z'
                except ValueError:
                    try:
                        # Fall back to RFC 2822 format (Thu, 12 Mar 2026 23:40:16 GMT)
                        parsed_date = parsedate_to_datetime(published)
                        created_at = parsed_date.isoformat() + 'Z'
                    except (ValueError, TypeError):
                        print(f"Warning: Could not parse date: {published}")
                        created_at = None
            else:
                created_at = None
            
            # Extract text
            text = entry.get("summary", "")
            
            # Extract media URLs (images and video links are in summary as <img> and <a> tags)
            image_urls = []
            video_urls = []
            
            # Simple extraction - might need refinement based on Nitter HTML structure
            if "pbs.twimg.com" in text or "twitter.com/*/status" in text:
                # Would need HTML parsing for actual links
                pass
            
            return {
                "post_id": post_id,
                "created_at": created_at,
                "text": text,
                "image_urls": image_urls,
                "video_urls": video_urls,
                "author": {
                    "username": self.account
                },
                "metrics": {
                    "likes": 0,
                    "retweets": 0,
                    "replies": 0
                },
                "url": link
            }
        
        except Exception as e:
            print(f"Error parsing entry: {e}")
            return None

    def _scrape_api(self, batch_size: int) -> List[Dict[str, Any]]:
        """
        Scrape posts using Twitter API v2.
        ROADMAP: Implement with Twitter API bearer token.
        """
        raise NotImplementedError("Twitter API scraping not yet implemented. Use 'nitter' method instead.")

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get account info (creation date, followers, etc.).
        Used to determine scrape batches.
        """
        try:
            profile_url = f"{self.nitter_instance}/{self.account}"
            response = self.session.get(profile_url, timeout=10)
            response.raise_for_status()
            
            # Would need HTML parsing to extract creation date
            # For now, return minimal info
            return {
                "username": self.account,
                "created_at": None,  # TODO: Parse from HTML
                "followers": None,
                "posts_count": None
            }
        
        except Exception as e:
            print(f"Error fetching account info: {e}")
            return None


class MediaDownloader:
    """Download images and videos from posts."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def download_image(self, url: str) -> Optional[bytes]:
        """Download image and return bytes."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error downloading image {url}: {e}")
            return None

    def download_video(self, url: str) -> Optional[bytes]:
        """Download video and return bytes."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error downloading video {url}: {e}")
            return None
