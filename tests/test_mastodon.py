import logging

import pytest

from connectors.mastodon import ApiProvider, MastodonConnector, _next_link, _parse_target


@pytest.mark.parametrize(
    "target,expected",
    [
        ("mastodon.social/@Gargron", ("mastodon.social", "Gargron")),
        ("https://mastodon.social/@Gargron", ("mastodon.social", "Gargron")),
        ("@Gargron@mastodon.social", ("mastodon.social", "Gargron")),
    ],
)
def test_parse_target_accepts_common_forms(target, expected):
    assert _parse_target(target) == expected


def test_parse_target_rejects_bare_handle():
    with pytest.raises(ValueError):
        _parse_target("Gargron")


def test_next_link_extracts_next_url():
    header = (
        '<https://mastodon.social/api/v1/accounts/1/statuses?max_id=5>; rel="next", '
        '<https://mastodon.social/api/v1/accounts/1/statuses?min_id=10>; rel="prev"'
    )
    assert _next_link(header) == "https://mastodon.social/api/v1/accounts/1/statuses?max_id=5"


def test_next_link_returns_none_when_absent():
    assert _next_link("") is None


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._json


def test_fetch_looks_up_account_then_paginates_statuses(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/accounts/lookup"):
            return _FakeResponse(json_data={"id": "42"})
        if len(calls) == 2:
            return _FakeResponse(
                json_data=[{"id": "1", "content": "hi", "account": {}, "created_at": ""}],
                headers={"Link": '<https://x/next>; rel="next"'},
            )
        return _FakeResponse(json_data=[])

    import connectors.mastodon as mastodon_mod

    monkeypatch.setattr(mastodon_mod, "requests", None, raising=False)
    monkeypatch.setitem(
        __import__("sys").modules, "requests", type("R", (), {"get": staticmethod(fake_get)})
    )

    provider = ApiProvider({}, logging.getLogger("test"))
    items = list(provider.fetch("mastodon.social/@Gargron"))

    assert len(items) == 1
    assert items[0].uid == "mastodon:1"
    assert items[0].text == "hi"
    assert calls[0].endswith("/accounts/lookup")


def test_connector_uses_single_api_provider():
    connector = MastodonConnector({}, logging.getLogger("test"))
    providers = connector.providers()
    assert len(providers) == 1
    assert providers[0].name == "api"
