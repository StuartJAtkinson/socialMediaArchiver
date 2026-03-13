"""
Storage module for archiving posts to local filesystem/database.

Handles the folder structure:
  archives/
    └── {platform}/
        └── {account}/
            ├── posts.jsonl (text DB - one JSON per line)
            ├── metadata.json (account info, timestamps, scrape status)
            ├── images/
            │   └── {post_id}_{index}.{ext}
            └── videos/
                └── {post_id}_{index}.{ext}
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


class StorageManager:
    def __init__(self, root_path: str = "./archives"):
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)

    def get_account_dir(self, platform: str, account: str) -> Path:
        """Get or create the account directory structure."""
        account_dir = self.root_path / platform / account
        account_dir.mkdir(parents=True, exist_ok=True)
        (account_dir / "images").mkdir(exist_ok=True)
        (account_dir / "videos").mkdir(exist_ok=True)
        return account_dir

    def save_post(self, platform: str, account: str, post_data: Dict[str, Any]) -> None:
        """
        Save post to posts.jsonl (append-only).
        
        Expected post_data structure:
        {
            "post_id": "...",
            "created_at": "2024-01-01T00:00:00Z",
            "text": "...",
            "image_urls": [...],
            "video_urls": [...],
            "author": {...},
            "metrics": {...}
        }
        """
        account_dir = self.get_account_dir(platform, account)
        posts_file = account_dir / "posts.jsonl"
        
        with open(posts_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(post_data) + "\n")

    def get_posts(self, platform: str, account: str, limit: Optional[int] = None) -> List[Dict]:
        """Load all posts from JSONL file."""
        account_dir = self.get_account_dir(platform, account)
        posts_file = account_dir / "posts.jsonl"
        
        if not posts_file.exists():
            return []
        
        posts = []
        with open(posts_file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit and i >= limit:
                    break
                try:
                    posts.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse line {i+1} in {posts_file}")
        
        return posts

    def get_last_post_date(self, platform: str, account: str) -> Optional[str]:
        """Get the creation date of the most recent post."""
        posts = self.get_posts(platform, account, limit=1)
        if posts:
            return posts[0].get("created_at")
        return None

    def save_metadata(self, platform: str, account: str, metadata: Dict[str, Any]) -> None:
        """Save account metadata and scrape status."""
        account_dir = self.get_account_dir(platform, account)
        metadata_file = account_dir / "metadata.json"
        
        # Merge with existing metadata
        existing = {}
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        
        existing.update(metadata)
        
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

    def get_metadata(self, platform: str, account: str) -> Dict[str, Any]:
        """Get account metadata."""
        account_dir = self.get_account_dir(platform, account)
        metadata_file = account_dir / "metadata.json"
        
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_media(self, platform: str, account: str, media_type: str, 
                   post_id: str, filename: str, content: bytes) -> str:
        """
        Save media file (image/video).
        Returns the relative path to the saved file.
        """
        account_dir = self.get_account_dir(platform, account)
        media_dir = account_dir / media_type  # "images" or "videos"
        
        # Create filename like: {post_id}_{filename}
        safe_filename = f"{post_id}_{filename}"
        media_path = media_dir / safe_filename
        
        with open(media_path, "wb") as f:
            f.write(content)
        
        return str(media_path.relative_to(self.root_path))

    def post_exists(self, platform: str, account: str, post_id: str) -> bool:
        """Check if a post has already been archived."""
        posts = self.get_posts(platform, account)
        return any(p.get("post_id") == post_id for p in posts)

    def get_post_count(self, platform: str, account: str) -> int:
        """Get total number of archived posts."""
        posts = self.get_posts(platform, account)
        return len(posts)

    def get_stats(self, platform: str, account: str) -> Dict[str, Any]:
        """Get storage statistics for an account."""
        account_dir = self.get_account_dir(platform, account)
        posts = self.get_posts(platform, account)
        
        images_dir = account_dir / "images"
        videos_dir = account_dir / "videos"
        
        image_count = len(list(images_dir.glob("*"))) if images_dir.exists() else 0
        video_count = len(list(videos_dir.glob("*"))) if videos_dir.exists() else 0
        
        return {
            "post_count": len(posts),
            "image_count": image_count,
            "video_count": video_count,
            "earliest_post": posts[-1].get("created_at") if posts else None,
            "latest_post": posts[0].get("created_at") if posts else None,
            "path": str(account_dir)
        }
