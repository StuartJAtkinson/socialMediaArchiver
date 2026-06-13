"""Output writers and the media downloader.

Records are written under ``output/<source>/<id>.json`` so sources stay tidy and
filenames never collide. The media downloader is the original ``scraper.py``
image downloader, generalized to any media type and reused by every connector.
"""

from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.request
from pathlib import Path
from typing import Optional

from .models import Item

_EXT_MAP = {
    "image/gif": "gif",
    "image/webp": "webp",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/ogg": "ogv",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(name: str) -> str:
    """Make an id safe to use as a filename component."""
    return _SAFE_NAME.sub("_", name)[:120] or "item"


class Storage:
    """Filesystem storage for normalized items and their media."""

    def __init__(self, output_dir: str, media_dir: str, logger: logging.Logger):
        self.output_dir = Path(output_dir)
        self.media_dir = Path(media_dir)
        self.logger = logger
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._opener = self._build_opener()

    def _build_opener(self):
        context = ssl._create_unverified_context()
        handler = urllib.request.HTTPSHandler(context=context)
        opener = urllib.request.build_opener(handler)
        opener.addheaders = [
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "Chrome/91.0.4472.124 Safari/537.36",
            ),
            ("Accept", "*/*"),
        ]
        return opener

    # --- media ---
    def download_media(self, url: str, item_uid: str, index: int = 0) -> Optional[str]:
        """Download ``url`` into the media dir, naming by uid + index.

        Extension is taken from the Content-Type header, falling back to the URL.
        Returns the local path, or None on failure. Existing files are reused.
        """
        try:
            try:
                req = urllib.request.Request(url, method="HEAD")
                with self._opener.open(req, timeout=15) as resp:
                    content_type = (
                        resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
                    )
            except Exception:
                content_type = ""

            ext = _EXT_MAP.get(content_type)
            if not ext:
                ext_part = url.split("?")[0].rsplit(".", 1)[-1]
                ext = ext_part[:4].lower() if len(ext_part) <= 4 and ext_part.isalnum() else "bin"

            filename = f"{_safe(item_uid)}_{index}.{ext}"
            filepath = self.media_dir / filename

            if filepath.exists():
                if filepath.suffix[1:] == ext:
                    self.logger.debug("Media already exists: %s", filename)
                    return str(filepath)
                filepath.unlink()  # extension changed; re-download

            with self._opener.open(url, timeout=30) as resp, open(filepath, "wb") as out:
                out.write(resp.read())
            self.logger.info("Downloaded media: %s", filename)
            return str(filepath)
        except Exception as e:
            self.logger.warning("Failed to download media from %s: %s", url, e)
            return None

    # --- records ---
    def write_item(self, item: Item) -> Path:
        """Write a single item's normalized JSON to output/<source>/<id>.json."""
        dest_dir = self.output_dir / _safe(item.source)
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"{_safe(item.id)}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(item.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    def write_comments(self, item: Item) -> Optional[Path]:
        """Write an item's comments to a sidecar file, if any."""
        if not item.comments:
            return None
        dest_dir = self.output_dir / _safe(item.source)
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"{_safe(item.id)}_comments.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(item.comments, f, indent=2, ensure_ascii=False)
        self.logger.info("Saved %d comments for %s", len(item.comments), item.uid)
        return path
