"""The generic crawl loop.

Source-agnostic generalization of the original ``run_scrape_process``: walk the
targets, resolve each to a connector, stream normalized Items, then apply date
filtering, checkpoint dedup, media download, output, and politeness delays the same
way for every source.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from core.checkpoint import Checkpoint
from core.models import Item
from core.ratelimit import RotationManager, sleep_with_jitter
from core.registry import get_connector_class
from core.storage import Storage


def make_date_filter(date_after: str, date_before: str, logger: logging.Logger):
    """Return a predicate ``item -> bool`` for the configured date window."""
    after_dt = _parse_iso(date_after, "date_after", logger)
    before_dt = _parse_iso(date_before, "date_before", logger)

    def keep(item: Item) -> bool:
        ts_str = item.timestamp
        if not ts_str:
            return True
        try:
            post_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if post_dt.tzinfo is None:
                post_dt = post_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return True
        if after_dt and post_dt < after_dt:
            return False
        if before_dt and post_dt > before_dt:
            return False
        return True

    return keep


def _parse_iso(value: str, label: str, logger: logging.Logger):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Invalid %s format: %s. Ignoring.", label, value)
        return None


def _source_config(yaml_config: dict, source: str) -> dict:
    """Merge global knobs with the per-source ``sources:`` block."""
    base = {
        k: yaml_config.get(k)
        for k in (
            "timeout",
            "max_retries",
            "retry_delay",
            "output_dir",
            "images_dir",
            "log_file",
            "download_comments",
            "max_comments_per_post",
            "max_replies_per_comment",
            "proxy_url",
        )
        if k in yaml_config
    }
    base.update(yaml_config.get("sources", {}).get(source, {}) or {})
    return base


def run(
    targets: list[dict],
    logger: logging.Logger,
    checkpoint: Checkpoint,
    yaml_config: dict,
) -> dict[str, int]:
    """Run the crawl over all targets. Returns a summary dict."""
    storage = Storage(
        output_dir=yaml_config.get("output_dir", "./output"),
        media_dir=yaml_config.get("images_dir", "./output/images"),
        logger=logger,
    )
    date_filter = make_date_filter(
        yaml_config.get("date_after", ""), yaml_config.get("date_before", ""), logger
    )
    rotation = RotationManager(yaml_config, logger)
    download_media = yaml_config.get("download_images", True)
    save_comments = yaml_config.get("download_comments", False)
    post_delay = yaml_config.get("post_delay", 2.0)
    target_delay = yaml_config.get("channel_delay", 5.0)

    totals = {"items": 0, "media": 0, "comments": 0, "errors": 0, "skipped": 0}

    for idx, entry in enumerate(targets):
        source = entry.get("source", "")
        target = entry.get("target", "")
        if not source or not target:
            logger.warning("Skipping malformed target entry: %r", entry)
            continue

        target_key = f"{source}:{target}"
        if checkpoint.is_target_done(target_key):
            logger.info("Target '%s' already processed. Skipping.", target_key)
            continue

        logger.info("Processing target: %s", target_key)
        try:
            connector_cls = get_connector_class(source)
        except ValueError as e:
            logger.error("%s", e)
            totals["errors"] += 1
            continue

        connector = connector_cls(_source_config(yaml_config, source), logger)
        try:
            _process_target(
                connector,
                target,
                logger,
                checkpoint,
                storage,
                date_filter,
                rotation,
                download_media,
                save_comments,
                post_delay,
                totals,
            )
        except Exception as e:
            logger.error("Target '%s' failed: %s", target_key, e)
            totals["errors"] += 1
        finally:
            connector.close()

        checkpoint.mark_target_done(target_key)
        checkpoint.save()

        if target_delay > 0 and idx < len(targets) - 1:
            sleep_with_jitter(target_delay, logger)

    logger.info(
        "\n----------------------------------------\nSUMMARY:\n"
        "  Items saved:    %d\n  Media saved:    %d\n  Comments saved: %d\n"
        "  Skipped (dup):  %d\n  Errors:         %d\n"
        "----------------------------------------",
        totals["items"],
        totals["media"],
        totals["comments"],
        totals["skipped"],
        totals["errors"],
    )
    return totals


def _process_target(
    connector,
    target: str,
    logger: logging.Logger,
    checkpoint: Checkpoint,
    storage: Storage,
    date_filter,
    rotation: RotationManager,
    download_media: bool,
    save_comments: bool,
    post_delay: float,
    totals: dict,
) -> None:
    for item in connector.fetch(target):
        if not item.id:
            logger.debug("Skipping item without id from %s", item.source)
            continue
        if not date_filter(item):
            continue
        if checkpoint.is_scraped(item.uid):
            totals["skipped"] += 1
            continue

        media_paths: list[str] = []
        if download_media and item.media:
            for i, media in enumerate(item.media):
                if not media.url:
                    continue
                local = storage.download_media(media.url, item.uid, i)
                if local:
                    media.local_path = local
                    media_paths.append(local)
                    totals["media"] += 1

        comments_saved = False
        if save_comments and item.comments:
            if storage.write_comments(item):
                comments_saved = True
                totals["comments"] += len(item.comments)

        storage.write_item(item)
        checkpoint.mark_scraped(item.uid, media_paths=media_paths, comments_saved=comments_saved)
        totals["items"] += 1

        rotation.tick()
        sleep_with_jitter(post_delay, logger)
