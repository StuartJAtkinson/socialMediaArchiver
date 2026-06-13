"""Normalized, source-agnostic record model.

Every connector maps its native payload onto :class:`Item` so that records from
YouTube, Reddit, RSS, Facebook, etc. share one shape and can be queried together.
The original payload is preserved verbatim under ``Item.raw`` so nothing is lost
in normalization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ItemAuthor:
    """Author/source of an item, normalized across platforms."""

    id: str = ""
    name: str = ""
    url: str = ""
    thumbnail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "thumbnail": self.thumbnail,
        }


@dataclass
class MediaItem:
    """A media attachment (image/video/audio/file)."""

    url: str = ""
    local_path: str | None = None
    media_type: str = "image"  # image | video | audio | file
    width: int | None = None
    height: int | None = None
    file_size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "local_path": self.local_path,
            "media_type": self.media_type,
            "width": self.width,
            "height": self.height,
            "file_size": self.file_size,
        }


@dataclass
class Item:
    """A single normalized record from any source.

    ``id`` is unique within a source; ``uid`` (``source:id``) is globally unique
    and is what the checkpoint dedups on, so ids never collide across sources.
    """

    id: str
    source: str
    target: str = ""
    url: str = ""
    timestamp: str = ""  # ISO 8601 where available
    timestamp_estimated: bool = False
    title: str = ""
    text: str = ""
    author: ItemAuthor = field(default_factory=ItemAuthor)
    media: list[MediaItem] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)  # {text, url}
    metrics: dict[str, Any] = field(default_factory=dict)  # likes/score/comments...
    comments: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def uid(self) -> str:
        """Globally unique id, ``source:id``."""
        return f"{self.source}:{self.id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "url": self.url,
            "timestamp": self.timestamp,
            "timestamp_estimated": self.timestamp_estimated,
            "title": self.title,
            "text": self.text,
            "author": self.author.to_dict(),
            "media": [m.to_dict() for m in self.media],
            "links": self.links,
            "metrics": self.metrics,
            "comments": self.comments,
            "raw": self.raw,
        }
