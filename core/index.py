"""SQLite index over the normalized archive — one ``index.db`` beside it.

Holds ``(post_id, account, platform, posted_at, text, media_count, path)`` per
post so Browse and the account page can page and count without walking the
filesystem. It's a derived convenience index, not a second source of truth:
``python main.py reindex`` rebuilds it from the normalized JSON alone.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Item

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    account TEXT NOT NULL,
    posted_at TEXT,
    text TEXT,
    media_count INTEGER NOT NULL DEFAULT 0,
    path TEXT,
    PRIMARY KEY (platform, post_id)
);
CREATE INDEX IF NOT EXISTS idx_posts_account ON posts(platform, account, posted_at);
"""


def index_path(output_dir) -> Path:
    """Where the index lives for a given output directory — beside the archive."""
    return Path(output_dir) / "index.db"


class PostIndex:
    """Thin wrapper around the ``index.db`` SQLite file."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def _upsert(self, platform, post_id, account, posted_at, text, media_count, path) -> None:
        self.conn.execute(
            "INSERT INTO posts (platform, post_id, account, posted_at, text, media_count, path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(platform, post_id) DO UPDATE SET "
            "account=excluded.account, posted_at=excluded.posted_at, text=excluded.text, "
            "media_count=excluded.media_count, path=excluded.path",
            (platform, post_id, account, posted_at, text, media_count, str(path)),
        )
        self.conn.commit()

    def record(self, item: Item, path: str = "") -> None:
        """Upsert one item's row, keyed on ``(platform, post_id)``."""
        self._upsert(
            item.source,
            item.id,
            item.target or item.source,
            item.timestamp,
            item.text or item.title,
            len(item.media),
            path,
        )

    def accounts(self) -> list[dict]:
        """List ``(platform, account)`` pairs with post counts."""
        rows = self.conn.execute(
            "SELECT platform, account, COUNT(*) FROM posts GROUP BY platform, account"
        ).fetchall()
        return [{"platform": p, "account": a, "post_count": n} for p, a, n in rows]

    def account_stats(self, platform: str, account: str) -> dict:
        count, earliest, latest, media = self.conn.execute(
            "SELECT COUNT(*), MIN(posted_at), MAX(posted_at), SUM(media_count) "
            "FROM posts WHERE platform=? AND account=?",
            (platform, account),
        ).fetchone()
        return {
            "post_count": count or 0,
            "image_count": media or 0,
            "video_count": 0,
            "earliest_post": earliest or "",
            "latest_post": latest or "",
        }

    def list_posts(self, platform: str, account: str, limit: int = 50, offset: int = 0) -> dict:
        total = self.conn.execute(
            "SELECT COUNT(*) FROM posts WHERE platform=? AND account=?", (platform, account)
        ).fetchone()[0]
        rows = self.conn.execute(
            "SELECT post_id, posted_at, text, path FROM posts WHERE platform=? AND account=? "
            "ORDER BY posted_at ASC LIMIT ? OFFSET ?",
            (platform, account, limit, offset),
        ).fetchall()
        posts = [
            {"post_id": pid, "created_at": ts or "", "text": text or "", "path": path}
            for pid, ts, text, path in rows
        ]
        return {
            "posts": posts,
            "total": total,
            "has_more": offset + limit < total,
            "offset": offset,
            "limit": limit,
        }

    def close(self) -> None:
        self.conn.close()


def rebuild(output_dir) -> PostIndex:
    """Rebuild ``index.db`` from the normalized JSON records under ``output_dir``.

    Clears the table first so the index always matches what's on disk, then
    walks every ``<output_dir>/<source>/*.json`` that isn't a comment sidecar.
    """
    out = Path(output_dir)
    idx = PostIndex(index_path(out))
    idx.conn.execute("DELETE FROM posts")
    idx.conn.commit()
    if out.is_dir():
        for source_dir in out.iterdir():
            if not source_dir.is_dir() or source_dir.name == "images":
                continue
            for f in source_dir.glob("*.json"):
                if f.name.endswith("_comments.json"):
                    continue
                try:
                    with open(f, encoding="utf-8") as fh:
                        data = json.load(fh)
                except (OSError, json.JSONDecodeError):
                    continue
                idx._upsert(
                    data.get("source", source_dir.name),
                    data.get("id", ""),
                    data.get("target") or data.get("source", source_dir.name),
                    data.get("timestamp", ""),
                    data.get("text") or data.get("title", ""),
                    len(data.get("media") or []),
                    str(f),
                )
    return idx
