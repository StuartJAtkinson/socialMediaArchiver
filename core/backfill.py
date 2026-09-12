"""Backfill absolute dates onto posts archived before the absolute-dates fix.

Those rows still hold the source's relative text ("8 months ago") in
``timestamp``, so ``core/index.py``'s ``ORDER BY posted_at`` sorts them
alphabetically and ``core/orchestrator.py``'s date filter can't read them.

Two signals recover a real date, and neither needs the run history:

1. **The file's mtime is that row's crawl time.** Resolving "8 months ago"
   against *now* would be wrong by however long ago the crawl was; resolving it
   against the mtime is right by construction, and it's per-row, so an archive
   built over many crawls backfills correctly in one pass.
2. **Order and neighbours refine the month buckets.** Step 1 lands every post
   in a month on a single instant, so 34 posts tie and the sort order within
   them is arbitrary. Each run of tied rows is instead spread evenly across the
   gap between the nearest confirmed dates either side, divided by the number of
   rows in the run — so order is preserved and no two posts collide.

The original string is never lost: connectors keep it verbatim under
``Item.raw``, which this leaves untouched. Everything written here is marked
``timestamp_estimated=True`` — a month bucket is a month-wide claim, and
interpolation inside it doesn't make it a narrower one.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from connectors.youtube_community import _resolve_relative_timestamp

logger = logging.getLogger("bytebytego")

_ISO = "%Y-%m-%dT%H:%M:%SZ"


def _parse_iso(value: str) -> datetime | None:
    """Parse an ISO 8601 timestamp, or return None if it isn't one."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _records(output_dir: Path):
    """Yield (path, record) for every normalized post JSON under output_dir."""
    for path in sorted(output_dir.glob("*/*.json")):
        if path.name.endswith("_comments.json"):
            continue
        try:
            yield path, json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("backfill: skipping unreadable %s (%s)", path, exc)


def _interpolate(group: list[dict]) -> None:
    """Spread each run of identically-dated rows across the gap around it.

    ``group`` is one account's rows, already sorted oldest-first, each carrying
    a ``coarse`` datetime and a ``crawled`` datetime. Sets ``resolved`` on every
    row. Runs are walked as blocks, so the arithmetic is over the whole tie at
    once rather than one row at a time.

    A row whose date no other row shares is left where it is: it is a confirmed
    anchor, and moving it would lose information rather than add it.
    """
    i = 0
    while i < len(group):
        j = i
        while j + 1 < len(group) and group[j + 1]["coarse"] == group[i]["coarse"]:
            j += 1
        run = group[i:j + 1]

        if len(run) == 1:
            # A date nothing else collides with is as confirmed as this archive
            # gets. Leave it exactly where it resolved — it is the anchor the
            # tied runs either side of it are spread against.
            run[0]["resolved"] = run[0]["coarse"]
            i = j + 1
            continue

        # Lower bound: the last date already assigned, else the run's own bucket
        # (nothing older is known, so the bucket instant is the honest floor).
        lo = group[i - 1]["resolved"] if i > 0 else run[0]["coarse"]
        # Upper bound: the next distinct bucket, else the crawl time — a post
        # cannot be newer than the moment it was scraped.
        hi = group[j + 1]["coarse"] if j + 1 < len(group) else max(r["crawled"] for r in run)
        if hi <= lo:
            hi = lo + timedelta(seconds=len(run))

        step = (hi - lo) / (len(run) + 1)
        for n, row in enumerate(run, start=1):
            row["resolved"] = lo + step * n
        i = j + 1


def backfill_relative_dates(output_dir, dry_run: bool = False) -> dict:
    """Rewrite relative ``timestamp`` values in the archive as ISO 8601.

    Returns a summary dict. With ``dry_run`` nothing is written, so the counts
    can be inspected before committing to a rewrite of the archive.
    """
    output_dir = Path(output_dir)
    pending: dict[tuple[str, str], list[dict]] = {}
    unresolved = 0

    for path, record in _records(output_dir):
        value = record.get("timestamp", "")
        if _parse_iso(value):
            continue  # already absolute; leave it alone
        crawled = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        iso, estimated = _resolve_relative_timestamp(value, now=crawled)
        if not iso:
            unresolved += 1
            logger.warning("backfill: cannot resolve %r in %s", value, path.name)
            continue
        key = (record.get("source", ""), record.get("target", ""))
        pending.setdefault(key, []).append({
            "path": path,
            "record": record,
            "coarse": _parse_iso(iso),
            "crawled": crawled,
            "estimated": estimated,
        })

    updated = 0
    for key, rows in sorted(pending.items()):
        # Within one crawl the connector writes newest-first, so among rows that
        # resolved to the same instant, a later mtime means an older post.
        rows.sort(key=lambda r: (r["coarse"], -r["crawled"].timestamp()))
        _interpolate(rows)
        for row in rows:
            row["record"]["timestamp"] = row["resolved"].strftime(_ISO)
            row["record"]["timestamp_estimated"] = True
            if not dry_run:
                row["path"].write_text(
                    json.dumps(row["record"], ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            updated += 1
        logger.info("backfill: %s/%s — %d posts dated", key[0], key[1], len(rows))

    return {"updated": updated, "unresolved": unresolved, "accounts": len(pending)}
