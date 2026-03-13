"""
Batch processor for smart, rate-limit-aware scraping.

Uses account age and date increments to scrape efficiently:
- Determines account creation date
- Divides timeline into batches based on date increments
- Tracks scrape progress to avoid re-scraping
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import json


class BatchProcessor:
    """Manages intelligent batch scraping with date-based increments."""
    
    def __init__(self, batch_size: int = 50, scrape_interval_days: int = 7):
        """
        Args:
            batch_size: Number of posts per scrape request
            scrape_interval_days: How many days back to scrape per batch
        """
        self.batch_size = batch_size
        self.scrape_interval_days = scrape_interval_days

    def calculate_scrape_batches(self, account_created_at: str, 
                                 last_scraped_at: Optional[str] = None) -> List[Tuple[datetime, datetime]]:
        """
        Calculate date ranges for batch scraping.
        
        Returns list of (start_date, end_date) tuples to scrape.
        """
        # Parse dates
        account_created = datetime.fromisoformat(account_created_at.replace('Z', '+00:00')).replace(tzinfo=None)
        
        if last_scraped_at:
            last_scraped = datetime.fromisoformat(last_scraped_at.replace('Z', '+00:00')).replace(tzinfo=None)
            scrape_start = last_scraped
        else:
            scrape_start = datetime.now()
        
        batches = []
        current_end = scrape_start
        
        # Go backwards in time from last scraped to account creation
        while current_end > account_created:
            current_start = max(
                current_end - timedelta(days=self.scrape_interval_days),
                account_created
            )
            batches.append((current_start, current_end))
            current_end = current_start
        
        return batches

    def get_next_batch_dates(self, account_created_at: str,
                            last_scraped_at: Optional[str] = None) -> Optional[Tuple[datetime, datetime]]:
        """Get the next batch date range to scrape."""
        batches = self.calculate_scrape_batches(account_created_at, last_scraped_at)
        if batches:
            return batches[0]  # Return the oldest batch first (working backwards)
        return None

    def estimate_scrape_time(self, account_created_at: str, 
                            last_scraped_at: Optional[str] = None) -> Dict[str, Any]:
        """Estimate how long it will take to scrape all posts."""
        batches = self.calculate_scrape_batches(account_created_at, last_scraped_at)
        
        total_batches = len(batches)
        estimated_posts = total_batches * self.batch_size
        
        # Assuming ~2 seconds per batch (with rate limiting)
        estimated_hours = (total_batches * 2) / 3600
        
        return {
            "total_batches": total_batches,
            "estimated_posts": estimated_posts,
            "batch_size": self.batch_size,
            "estimated_hours": round(estimated_hours, 2),
            "scrape_interval_days": self.scrape_interval_days
        }

    def get_progress(self, account_created_at: str, last_scraped_at: Optional[str],
                    posts_archived: int) -> Dict[str, Any]:
        """Get progress of current scraping operation."""
        batches = self.calculate_scrape_batches(account_created_at, last_scraped_at)
        estimate = self.estimate_scrape_time(account_created_at, last_scraped_at)
        
        return {
            "posts_archived": posts_archived,
            "posts_per_batch": self.batch_size,
            "estimated_total": estimate["estimated_posts"],
            "coverage_percentage": round((posts_archived / estimate["estimated_posts"] * 100), 2) if estimate["estimated_posts"] > 0 else 0,
            "remaining_batches": len(batches),
            "estimated_hours_remaining": round((len(batches) * 2) / 3600, 2)
        }
