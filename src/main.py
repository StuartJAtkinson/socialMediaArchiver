"""
Main orchestrator for the Social Media Archiver.

Controls the workflow:
1. Load configuration
2. For each source:
   - Get account info and determine scrape batches
   - Scrape posts in batches
   - Save to local storage (with optional media download)
   - Log progress and stats
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from scraper import TwitterScraper, MediaDownloader
from storage import StorageManager
from batch_processor import BatchProcessor


class SocialMediaArchiver:
    """Main orchestrator class."""
    
    def __init__(self, config_path: str = "./config/config.json"):
        self.config = self._load_config(config_path)
        self.storage = StorageManager()
        self.scrapers = {}
        self.downloader = MediaDownloader()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file not found: {config_path}")
            print("Creating from example...")
            self._create_default_config()
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in config: {e}")
            sys.exit(1)

    def _create_default_config(self):
        """Create a default config from example."""
        example_path = Path("./config/config.example.json")
        target_path = Path("./config/config.json")
        if example_path.exists():
            import shutil
            shutil.copy(example_path, target_path)
            print(f"Created default config at {target_path}")

    def archive_source(self, source_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Archive a single source (account).
        
        Returns:
            Statistics about the archiving operation.
        """
        platform = source_config.get("platform", "twitter")
        account = source_config.get("account")
        
        if not account:
            print("Error: No account specified in source config")
            return {}
        
        print(f"\n{'='*60}")
        print(f"Archiving {platform} account: {account}")
        print(f"{'='*60}")
        
        # Initialize scraper
        scraper = TwitterScraper(
            account=account,
            method=source_config.get("scrape_method", "nitter"),
            nitter_instance=source_config.get("nitter_instance", "https://nitter.net")
        )
        
        # Get current metadata
        metadata = self.storage.get_metadata(platform, account)
        last_scraped = metadata.get("last_scrape_at")
        
        # Get account info (needed for batch calculation)
        account_info = scraper.get_account_info()
        account_created_at = metadata.get("account_created_at") or (account_info.get("created_at") if account_info else None)
        
        if not account_created_at:
            # Fallback: assume account is from 2006 (Twitter launch year)
            account_created_at = "2006-01-01T00:00:00Z"
            print(f"Warning: Could not determine account creation date. Using fallback: {account_created_at}")
        
        # Initialize batch processor
        batch_size = source_config.get("batch_config", {}).get("batch_size", 50)
        scrape_interval = source_config.get("batch_config", {}).get("scrape_interval_days", 7)
        processor = BatchProcessor(batch_size=batch_size, scrape_interval_days=scrape_interval)
        
        # Show scrape estimate
        estimate = processor.estimate_scrape_time(account_created_at, last_scraped)
        print(f"Estimated posts to scrape: {estimate['estimated_posts']}")
        print(f"Estimated time: {estimate['estimated_hours']} hours")
        
        # Scrape posts
        print(f"\nScraping {batch_size} posts...")
        posts = scraper.scrape(batch_size=batch_size)
        
        if not posts:
            print("No posts found to archive.")
            return {"posts_archived": 0}
        
        print(f"Retrieved {len(posts)} posts")
        
        # Process and save posts
        download_images = source_config.get("media_download", {}).get("images", False)
        download_videos = source_config.get("media_download", {}).get("videos", False)
        
        posts_saved = 0
        posts_skipped = 0
        
        for post in posts:
            post_id = post.get("post_id")
            
            # Skip if already archived
            if self.storage.post_exists(platform, account, post_id):
                posts_skipped += 1
                continue
            
            # Save post
            self.storage.save_post(platform, account, post)
            posts_saved += 1
            
            # Download media if enabled
            if download_images and post.get("image_urls"):
                for i, img_url in enumerate(post["image_urls"]):
                    try:
                        img_data = self.downloader.download_image(img_url)
                        if img_data:
                            ext = self._get_extension(img_url)
                            self.storage.save_media(
                                platform, account, "images",
                                post_id, f"{i}.{ext}", img_data
                            )
                    except Exception as e:
                        print(f"Error downloading image: {e}")
            
            if download_videos and post.get("video_urls"):
                for i, vid_url in enumerate(post["video_urls"]):
                    try:
                        vid_data = self.downloader.download_video(vid_url)
                        if vid_data:
                            ext = self._get_extension(vid_url)
                            self.storage.save_media(
                                platform, account, "videos",
                                post_id, f"{i}.{ext}", vid_data
                            )
                    except Exception as e:
                        print(f"Error downloading video: {e}")
        
        # Update metadata
        new_metadata = {
            "account_created_at": account_created_at,
            "last_scrape_at": datetime.now().isoformat() + "Z",
            "total_posts_archived": self.storage.get_post_count(platform, account),
            "last_scrape_posts": posts_saved
        }
        self.storage.save_metadata(platform, account, new_metadata)
        
        # Get stats
        stats = self.storage.get_stats(platform, account)
        
        print(f"\nResults:")
        print(f"  Posts saved: {posts_saved}")
        print(f"  Posts skipped (already archived): {posts_skipped}")
        print(f"  Total posts archived: {stats['post_count']}")
        print(f"  Images: {stats['image_count']}")
        print(f"  Videos: {stats['video_count']}")
        print(f"  Path: {stats['path']}")
        
        return {
            "account": account,
            "platform": platform,
            "posts_saved": posts_saved,
            "posts_skipped": posts_skipped,
            "total_posts": stats['post_count'],
            "images": stats['image_count'],
            "videos": stats['video_count']
        }

    @staticmethod
    def _get_extension(url: str) -> str:
        """Extract file extension from URL."""
        try:
            path = url.split("?")[0]  # Remove query params
            return path.split(".")[-1][:4]  # Last 4 chars max
        except:
            return "bin"

    def run_all(self):
        """Run archiving for all sources in config."""
        sources = self.config.get("sources", [])
        
        if not sources:
            print("No sources configured. Edit config/config.json to add sources.")
            return
        
        results = []
        for source in sources:
            try:
                result = self.archive_source(source)
                results.append(result)
            except Exception as e:
                print(f"Error archiving {source.get('account')}: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print(f"\n{'='*60}")
        print("ARCHIVE COMPLETE")
        print(f"{'='*60}")
        for result in results:
            if result:
                print(f"{result.get('account')}: {result.get('posts_saved')} new posts, {result.get('total_posts')} total")


def main():
    """Entry point."""
    archiver = SocialMediaArchiver()
    archiver.run_all()


if __name__ == "__main__":
    main()
