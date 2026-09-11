"""Relative timestamps must never survive ingest.

Standing rule (2026-09-11): absolute dates only. YouTube renders community-post
dates as human text; anything that reaches core/index.py must be ISO 8601, or
empty. These tests fail if a relative string ever gets through again.
"""

from datetime import datetime, timezone

import pytest

from connectors.youtube_community import _resolve_relative_timestamp

# A fixed anchor so the expected values are exact, not "about now".
NOW = datetime(2026, 9, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1 day ago", "2026-09-10T12:00:00Z"),
        ("2 days ago", "2026-09-09T12:00:00Z"),
        ("1 week ago", "2026-09-04T12:00:00Z"),
        ("3 hours ago", "2026-09-11T09:00:00Z"),
        ("30 minutes ago", "2026-09-11T11:30:00Z"),
        # Word forms YouTube uses instead of "1".
        ("a minute ago", "2026-09-11T11:59:00Z"),
        ("an hour ago", "2026-09-11T11:00:00Z"),
        # Case and the "Edited" prefix must not defeat the match.
        ("2 DAYS AGO", "2026-09-09T12:00:00Z"),
        ("Edited 1 day ago", "2026-09-10T12:00:00Z"),
    ],
)
def test_relative_becomes_absolute(text: str, expected: str) -> None:
    iso, estimated = _resolve_relative_timestamp(text, now=NOW)
    assert iso == expected
    assert estimated is True, "anything derived from a relative string is an estimate"


def test_months_and_years_are_approximate_but_absolute() -> None:
    """A month-wide claim still has to land on a real date."""
    iso, estimated = _resolve_relative_timestamp("1 month ago", now=NOW)
    assert estimated is True
    parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    # ~30.4 days back: August, and comfortably inside a month of the anchor.
    assert parsed.year == 2026 and parsed.month == 8
    assert 28 <= (NOW - parsed).days <= 32


def test_already_absolute_is_untouched() -> None:
    """An ISO input passes through and is NOT downgraded to an estimate."""
    iso, estimated = _resolve_relative_timestamp("2026-07-01T10:30:00Z", now=NOW)
    assert iso == "2026-07-01T10:30:00Z"
    assert estimated is False


def test_unparseable_returns_empty_not_a_guess() -> None:
    """An empty timestamp is honest; an invented one is not."""
    for junk in ("", "yesterday", "last Tuesday", "streamed 3 days ago", None):
        iso, estimated = _resolve_relative_timestamp(junk, now=NOW)  # type: ignore[arg-type]
        assert iso == ""
        assert estimated is False


def test_output_is_sortable_and_filterable() -> None:
    """The two things the raw string broke: ORDER BY, and the date filter.

    core/index.py sorts on posted_at as text, and core/orchestrator.py parses it
    with datetime.fromisoformat(). Both work only if the format is ISO.
    """
    older, _ = _resolve_relative_timestamp("2 months ago", now=NOW)
    newer, _ = _resolve_relative_timestamp("1 day ago", now=NOW)

    # Lexicographic order matches chronological order for ISO 8601.
    assert older < newer
    # And the orchestrator's parse succeeds, so date filters apply.
    datetime.fromisoformat(older.replace("Z", "+00:00"))
    datetime.fromisoformat(newer.replace("Z", "+00:00"))
