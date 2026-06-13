"""YouTube community-post connector.

Wraps ``post-archiver-improved`` (the original engine of this project) as a single
provider and maps its ``Post`` objects onto the normalized :class:`Item`. Targets
are channel handles (``@ByteByteGo``), channel ids, or channel URLs.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Iterator

from connectors.base import Provider, SingleProviderConnector
from core.errors import ProviderUnavailable
from core.models import Item, ItemAuthor, MediaItem

try:
    from post_archiver_improved.config import (
        Config as PAConfig,
        OutputConfig as PAOutputConfig,
        ScrapingConfig as PAScrapingConfig,
    )
    from post_archiver_improved.scraper import CommunityPostScraper

    _PA_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when lib missing
    _PA_AVAILABLE = False


SOURCE = "youtube_community"


def _build_pa_config(cfg: dict) -> "PAConfig":
    """Build a post-archiver Config from this connector's config slice."""
    scraping = PAScrapingConfig(
        max_posts=cfg.get("max_posts") or math.inf,
        extract_comments=cfg.get("download_comments", False),
        max_comments_per_post=cfg.get("max_comments_per_post", 100),
        max_replies_per_comment=cfg.get("max_replies_per_comment", 200),
        download_images=False,  # storage layer downloads media
        request_timeout=cfg.get("timeout", 30),
        max_retries=cfg.get("max_retries", 3),
        retry_delay=cfg.get("retry_delay", 1.0),
        cookies_file=cfg.get("cookies_file"),
    )
    output = PAOutputConfig(output_dir=cfg.get("output_dir", "./output"))
    return PAConfig(scraping=scraping, output=output, log_file=cfg.get("log_file"))


def _post_to_item(post: Any, target: str) -> Item:
    """Map a post-archiver ``Post`` (or its dict) onto a normalized Item."""
    d = post.to_dict() if hasattr(post, "to_dict") else dict(post)

    author = ItemAuthor(
        id=d.get("author_id", ""),
        name=d.get("author", ""),
        url=d.get("author_url", ""),
        thumbnail=d.get("author_thumbnail", ""),
    )
    media = [
        MediaItem(
            url=img.get("src", ""),
            local_path=img.get("local_path"),
            media_type="image",
            width=img.get("width"),
            height=img.get("height"),
            file_size=img.get("file_size"),
        )
        for img in d.get("images", [])
    ]
    links = [{"text": l.get("text", ""), "url": l.get("url", "")} for l in d.get("links", [])]

    return Item(
        id=d.get("post_id", ""),
        source=SOURCE,
        target=target,
        url=f"https://www.youtube.com/post/{d.get('post_id', '')}" if d.get("post_id") else "",
        timestamp=d.get("timestamp", ""),
        timestamp_estimated=d.get("timestamp_estimated", False),
        title="",
        text=d.get("content", ""),
        author=author,
        media=media,
        links=links,
        metrics={
            "likes": d.get("likes", "0"),
            "comments_count": d.get("comments_count", "0"),
            "members_only": d.get("members_only", False),
        },
        comments=d.get("comments", []),
        raw=d,
    )


class _PostArchiverProvider(Provider):
    name = "post-archiver-improved"

    def available(self) -> bool:
        return _PA_AVAILABLE

    def fetch(self, target: str) -> Iterator[Item]:
        if not _PA_AVAILABLE:
            raise ProviderUnavailable("post-archiver-improved not installed")
        scraper = CommunityPostScraper(_build_pa_config(self.config))
        archive = scraper.scrape_posts(target)
        for post in archive.posts or []:
            yield _post_to_item(post, target)


class YouTubeCommunityConnector(SingleProviderConnector):
    name = SOURCE

    def make_provider(self) -> Provider:
        return _PostArchiverProvider(self.config, self.logger)
