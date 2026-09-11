"""YouTube community-post connector.

Wraps ``post-archiver-improved`` (the original engine of this project) as a single
provider and maps its ``Post`` objects onto the normalized :class:`Item`. Targets
are channel handles (``@ByteByteGo``), channel ids, or channel URLs.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta, timezone
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

# Matches the project's logger name (main.py:34, core/ratelimit.py:37).
logger = logging.getLogger("bytebytego")


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


# ---------------------------------------------------------------------------
# Relative timestamps
#
# YouTube renders community-post dates as human text ("1 month ago"), and the
# upstream scraper stores whatever it read. That string is useless downstream:
# core/index.py does ORDER BY posted_at, so relative strings sort
# alphabetically, and core/orchestrator.py's date filter calls
# datetime.fromisoformat() and KEEPS the item on ValueError -- so a date range
# silently matched every YouTube post.
#
# Standing instruction (Stuart, 2026-09-11): absolute dates only, never
# relative. So we resolve the string at ingest against the scrape time and
# store ISO 8601. The result is only as precise as the source -- "1 month ago"
# is a month-wide claim -- so anything resolved this way is flagged
# timestamp_estimated=True. The raw string stays in Item.raw, untouched.
# ---------------------------------------------------------------------------

# YouTube writes "a minute ago" / "an hour ago" as well as numeric counts.
_WORD_ONE = {"a": 1, "an": 1, "one": 1}

# Days per unit. Months and years are the calendar's nominal averages; they are
# approximations by nature, which is what timestamp_estimated records.
_UNIT_DAYS = {
    "second": 1 / 86400,
    "minute": 1 / 1440,
    "hour": 1 / 24,
    "day": 1,
    "week": 7,
    "month": 30.436875,
    "year": 365.2425,
}

_RELATIVE_RE = re.compile(
    r"^\s*(?:edited\s+)?(\d+|a|an|one)\s+"
    r"(second|minute|hour|day|week|month|year)s?\s+ago\s*$",
    re.IGNORECASE,
)


def _resolve_relative_timestamp(
    value: str, now: datetime | None = None
) -> tuple[str, bool]:
    """Turn a YouTube relative date into an absolute ISO 8601 timestamp.

    Returns ``(iso_string, estimated)``. An input that is already ISO 8601 is
    returned unchanged with ``estimated=False``. An input we cannot read at all
    returns ``("", False)`` rather than a guess -- an empty timestamp is honest,
    a wrong one is not.
    """
    if not value or not isinstance(value, str):
        return "", False

    text = value.strip()

    # Already absolute? Keep it, and don't mark it estimated.
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return text, False
    except ValueError:
        pass

    m = _RELATIVE_RE.match(text)
    if not m:
        # Unparseable. Refuse to invent a date.
        logger.warning("youtube_community: unrecognised timestamp %r", value)
        return "", False

    count_raw, unit = m.group(1).lower(), m.group(2).lower()
    count = _WORD_ONE.get(count_raw, None)
    if count is None:
        count = int(count_raw)

    anchor = now or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)

    resolved = anchor - timedelta(days=_UNIT_DAYS[unit] * count)
    return resolved.strftime("%Y-%m-%dT%H:%M:%SZ"), True


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

    # Absolute only: resolve YouTube's "1 month ago" against now, or drop it.
    timestamp, resolved_estimate = _resolve_relative_timestamp(d.get("timestamp", ""))

    return Item(
        id=d.get("post_id", ""),
        source=SOURCE,
        target=target,
        url=f"https://www.youtube.com/post/{d.get('post_id', '')}" if d.get("post_id") else "",
        timestamp=timestamp,
        timestamp_estimated=bool(d.get("timestamp_estimated", False)) or resolved_estimate,
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
