"""Shared RSS/Atom parsing.

Used directly by the RSS connector and reused by the Reddit ``.rss`` fallback
provider. Maps a feed entry onto a normalized :class:`Item`. ``feedparser`` is
imported lazily so the rest of the app runs without it installed.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

from .models import Item, ItemAuthor, MediaItem


def feedparser_available() -> bool:
    try:
        import feedparser  # noqa: F401

        return True
    except ImportError:
        return False


def _entry_timestamp(entry: Any) -> tuple[str, bool]:
    """Return (ISO timestamp, estimated). Empty string if unavailable."""
    import time as _time

    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return (
                    _time.strftime("%Y-%m-%dT%H:%M:%SZ", parsed),
                    False,
                )
            except Exception:
                continue
    # Fall back to the raw string forms if present.
    for key in ("published", "updated", "created"):
        if entry.get(key):
            return entry.get(key), True
    return "", False


def _entry_media(entry: Any) -> list[MediaItem]:
    media: list[MediaItem] = []
    for enc in entry.get("enclosures", []) or []:
        url = enc.get("href") or enc.get("url")
        if url:
            mime = (enc.get("type") or "").split("/")[0] or "file"
            kind = mime if mime in ("image", "video", "audio") else "file"
            media.append(MediaItem(url=url, media_type=kind))
    for mc in entry.get("media_content", []) or []:
        url = mc.get("url")
        if url:
            medium = mc.get("medium") or "image"
            media.append(MediaItem(url=url, media_type=medium))
    return media


def _entry_text(entry: Any) -> str:
    if entry.get("content"):
        try:
            return entry["content"][0].get("value", "")
        except Exception:
            pass
    return entry.get("summary", "") or entry.get("description", "")


def parse_feed(
    feed_url: str,
    source: str,
    target: str,
    logger: logging.Logger,
    max_items: Optional[int] = None,
    id_fn=None,
) -> Iterator[Item]:
    """Parse a feed URL and yield normalized Items.

    ``source`` lets the Reddit fallback label items "reddit" rather than "rss".
    ``id_fn(entry) -> str`` customizes id extraction (defaults to entry id/link).
    """
    import feedparser

    logger.debug("Fetching feed: %s", feed_url)
    parsed = feedparser.parse(feed_url)
    if parsed.bozo and not parsed.entries:
        logger.warning("Feed parse error for %s: %s", feed_url, parsed.get("bozo_exception"))
        return

    entries = parsed.entries
    if max_items:
        entries = entries[:max_items]

    for entry in entries:
        if id_fn:
            item_id = id_fn(entry)
        else:
            item_id = entry.get("id") or entry.get("link") or entry.get("title", "")
        if not item_id:
            continue

        ts, estimated = _entry_timestamp(entry)
        author = ItemAuthor(
            name=entry.get("author", "") or parsed.feed.get("title", ""),
            url=entry.get("author_detail", {}).get("href", "") if entry.get("author_detail") else "",
        )
        links = [{"text": entry.get("title", ""), "url": entry.get("link", "")}] if entry.get("link") else []

        yield Item(
            id=str(item_id),
            source=source,
            target=target,
            url=entry.get("link", ""),
            timestamp=ts,
            timestamp_estimated=estimated,
            title=entry.get("title", ""),
            text=_entry_text(entry),
            author=author,
            media=_entry_media(entry),
            links=links,
            metrics={},
            raw=dict(entry),
        )
