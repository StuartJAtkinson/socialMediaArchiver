"""Checkpoint/resume state, keyed by globally-unique item uid (``source:id``).

Ported from the original ``scraper.py`` Checkpoint, generalized so a single
checkpoint file spans every source. Legacy checkpoints (bare YouTube post ids)
are migrated on load by prefixing ``youtube_community:``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LEGACY_SOURCE = "youtube_community"


class Checkpoint:
    """Tracks which items/targets have been processed so runs can resume."""

    def __init__(self, path: str, logger: logging.Logger):
        self.path = Path(path)
        self.logger = logger
        self.data: dict = {
            "scraped_items": {},
            "targets_done": [],
            "last_item": None,
            "start_time": None,
        }
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.loads(f.read())
                self._migrate_legacy()
                self.logger.info(
                    "Checkpoint loaded: %d items already scraped",
                    len(self.data.get("scraped_items", {})),
                )
            except Exception as e:
                self.logger.warning(
                    "Could not load checkpoint from %s: %s. Starting fresh.",
                    self.path,
                    e,
                )

    def _migrate_legacy(self) -> None:
        """Upgrade an old YouTube-only checkpoint to the multi-source schema."""
        if "scraped_items" in self.data:
            # Already new-schema; ensure required keys exist.
            self.data.setdefault("scraped_items", {})
            self.data.setdefault("targets_done", self.data.get("channels_done", []))
            return

        legacy_posts = self.data.get("scraped_posts", {})
        migrated = {
            (pid if ":" in pid else f"{LEGACY_SOURCE}:{pid}"): meta
            for pid, meta in legacy_posts.items()
        }
        legacy_channels = self.data.get("channels_done", [])
        self.data = {
            "scraped_items": migrated,
            "targets_done": list(legacy_channels),
            "last_item": self.data.get("last_post"),
            "start_time": self.data.get("start_time"),
        }
        if migrated:
            self.logger.info(
                "Migrated %d legacy YouTube checkpoint entries.", len(migrated)
            )

    # --- item-level ---
    def is_scraped(self, uid: str) -> bool:
        return uid in self.data.get("scraped_items", {})

    def mark_scraped(
        self,
        uid: str,
        media_paths: Optional[list[str]] = None,
        comments_saved: bool = False,
    ) -> None:
        self.data["scraped_items"][uid] = {
            "scrape_time": datetime.now(timezone.utc).isoformat(),
            "media_paths": media_paths or [],
            "comments_saved": comments_saved,
        }
        self.data["last_item"] = uid

    # --- target-level ---
    def mark_target_done(self, target_key: str) -> None:
        if target_key not in self.data.get("targets_done", []):
            self.data["targets_done"].append(target_key)

    def is_target_done(self, target_key: str) -> bool:
        return target_key in self.data.get("targets_done", [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            self.logger.debug("Checkpoint saved to %s", self.path)
        except Exception as e:
            self.logger.error("Failed to save checkpoint to %s: %s", self.path, e)
