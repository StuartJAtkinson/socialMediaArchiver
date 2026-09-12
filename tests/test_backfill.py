import json
import os
from datetime import datetime, timezone

from core.backfill import backfill_relative_dates


def _write(tmp_path, post_id, timestamp, crawled, source="youtube_community"):
    """Write one normalized record, with its mtime set to the crawl time."""
    d = tmp_path / source
    d.mkdir(exist_ok=True)
    path = d / f"{post_id}.json"
    path.write_text(json.dumps({
        "id": post_id, "source": source, "target": "@example",
        "timestamp": timestamp, "timestamp_estimated": True,
        "text": "hi", "media": [], "raw": {"timestamp": timestamp},
    }), encoding="utf-8")
    stamp = crawled.timestamp()
    os.utime(path, (stamp, stamp))
    return path


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _crawl(day):
    return datetime(2026, 9, day, 12, 0, tzinfo=timezone.utc)


def test_resolves_against_each_row_own_crawl_time(tmp_path):
    """An archive built over several crawls dates each row against its own."""
    old = _write(tmp_path, "old", "1 month ago", _crawl(1))
    new = _write(tmp_path, "new", "1 month ago", _crawl(30))

    backfill_relative_dates(tmp_path)

    # Same relative text, crawls 29 days apart -> ~29 days apart, not identical.
    # Neither is a tie, so both keep the date they resolved to.
    a = datetime.fromisoformat(_read(old)["timestamp"].replace("Z", "+00:00"))
    b = datetime.fromisoformat(_read(new)["timestamp"].replace("Z", "+00:00"))
    assert 25 < (b - a).days < 33


def test_tied_rows_are_spread_and_keep_their_order(tmp_path):
    """Rows that collapse to one month bucket get distinct, ordered dates."""
    same = [_write(tmp_path, f"p{n}", "3 months ago", _crawl(10)) for n in range(4)]
    newer = _write(tmp_path, "recent", "1 month ago", _crawl(10))

    summary = backfill_relative_dates(tmp_path)
    assert summary["updated"] == 5 and summary["unresolved"] == 0

    dates = sorted(_read(p)["timestamp"] for p in same)
    assert len(set(dates)) == 4, "tied rows must not share a timestamp"
    # Every interpolated row stays below the next confirmed anchor.
    assert max(dates) < _read(newer)["timestamp"]
    # And every value is a real ISO 8601 instant, which is the whole point.
    for value in dates:
        datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_absolute_timestamps_are_left_alone(tmp_path):
    already = _write(tmp_path, "iso", "2026-01-01T00:00:00Z", _crawl(10))
    summary = backfill_relative_dates(tmp_path)
    assert summary["updated"] == 0
    assert _read(already)["timestamp"] == "2026-01-01T00:00:00Z"


def test_unresolvable_is_counted_not_guessed(tmp_path):
    junk = _write(tmp_path, "junk", "sometime last autumn", _crawl(10))
    summary = backfill_relative_dates(tmp_path)
    assert summary["unresolved"] == 1 and summary["updated"] == 0
    assert _read(junk)["timestamp"] == "sometime last autumn"


def test_dry_run_writes_nothing(tmp_path):
    path = _write(tmp_path, "p", "2 months ago", _crawl(10))
    summary = backfill_relative_dates(tmp_path, dry_run=True)
    assert summary["updated"] == 1
    assert _read(path)["timestamp"] == "2 months ago"


def test_raw_keeps_the_original_string(tmp_path):
    path = _write(tmp_path, "p", "5 months ago", _crawl(10))
    backfill_relative_dates(tmp_path)
    record = _read(path)
    assert record["timestamp"] != "5 months ago"
    assert record["raw"]["timestamp"] == "5 months ago"
    assert record["timestamp_estimated"] is True
