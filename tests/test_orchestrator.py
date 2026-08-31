import logging

from connectors.base import Connector, Provider
from core.errors import RateLimitError
from core.models import Item


class _RateLimitedProvider(Provider):
    name = "flaky"

    def fetch(self, target):
        raise RateLimitError("rate limited", retry_after=42)
        yield  # pragma: no cover - unreachable, keeps this a generator


class _FlakyConnector(Connector):
    name = "flaky"

    def build_providers(self):
        return [_RateLimitedProvider(self.config, self.logger)]


def test_on_rate_limit_hook_fires_with_the_raised_error():
    connector = _FlakyConnector({}, logging.getLogger("test"))
    seen = []
    connector.on_rate_limit = lambda e: seen.append(e)

    list(connector.fetch("some-target"))

    assert len(seen) == 1
    assert seen[0].retry_after == 42


def test_orchestrator_skips_targets_for_sources_under_backoff(tmp_path, monkeypatch):
    from core.checkpoint import Checkpoint
    from core import orchestrator

    monkeypatch.setattr(
        orchestrator, "get_connector_class", lambda source: _FlakyConnector
    )

    cfg = {"storage": {"output_dir": str(tmp_path)}, "post_delay": 0, "channel_delay": 0}
    cp = Checkpoint(str(tmp_path / ".checkpoint.json"), logging.getLogger("test"))

    totals = orchestrator.run(
        [{"source": "flaky", "target": "@one"}], logging.getLogger("test"), cp, cfg
    )
    assert totals["items"] == 0

    from core.ratelimit import RateLimitBackoff, backoff_path
    assert RateLimitBackoff(backoff_path(tmp_path)).active("flaky") > 0

    # A second, independent run (as a scheduler would fire) must skip the
    # target outright rather than hitting the rate-limited source again.
    cp2 = Checkpoint(str(tmp_path / ".checkpoint2.json"), logging.getLogger("test"))
    calls = []
    real_fetch = _RateLimitedProvider.fetch

    def _tracking_fetch(self, target):
        calls.append(target)
        return real_fetch(self, target)

    monkeypatch.setattr(_RateLimitedProvider, "fetch", _tracking_fetch)

    orchestrator.run(
        [{"source": "flaky", "target": "@one"}], logging.getLogger("test"), cp2, cfg
    )
    assert calls == []
