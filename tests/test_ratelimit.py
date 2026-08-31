import time

from core.ratelimit import RateLimitBackoff, backoff_path


def test_record_and_active_reflect_a_running_cooldown(tmp_path):
    backoff = RateLimitBackoff(backoff_path(tmp_path))
    assert backoff.active("reddit") == 0

    backoff.record("reddit", 60)
    remaining = backoff.active("reddit")
    assert 0 < remaining <= 60


def test_cooldown_is_persisted_across_instances(tmp_path):
    path = backoff_path(tmp_path)
    RateLimitBackoff(path).record("mastodon", 120)

    reloaded = RateLimitBackoff(path)
    assert reloaded.active("mastodon") > 0
    assert reloaded.active("other-source") == 0


def test_expired_cooldown_reports_zero(tmp_path):
    backoff = RateLimitBackoff(backoff_path(tmp_path))
    backoff.record("facebook", -5)  # already in the past
    assert backoff.active("facebook") == 0
