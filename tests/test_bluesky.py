import logging

import pytest

from connectors.bluesky import ApiProvider, BlueskyConnector, _parse_target


@pytest.mark.parametrize(
    "target,expected",
    [
        ("alice.bsky.social", "alice.bsky.social"),
        ("@alice.bsky.social", "alice.bsky.social"),
        ("https://bsky.app/profile/alice.bsky.social", "alice.bsky.social"),
        ("did:plc:abc123", "did:plc:abc123"),
    ],
)
def test_parse_target_accepts_common_forms(target, expected):
    assert _parse_target(target) == expected


def test_parse_target_rejects_malformed_url():
    with pytest.raises(ValueError):
        _parse_target("https://bsky.app/settings")


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


def test_fetch_uses_public_endpoint_without_credentials(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers))
        return _FakeResponse(
            json_data={
                "feed": [
                    {
                        "post": {
                            "uri": "at://did:plc:x/app.bsky.feed.post/abc",
                            "record": {"text": "hi", "createdAt": "2026-01-01T00:00:00Z"},
                            "author": {"handle": "alice.bsky.social", "did": "did:plc:x"},
                            "likeCount": 1,
                            "repostCount": 0,
                            "replyCount": 0,
                        }
                    }
                ]
            }
        )

    import connectors.bluesky as bluesky_mod

    monkeypatch.setitem(
        __import__("sys").modules,
        "requests",
        type("R", (), {"get": staticmethod(fake_get)}),
    )
    monkeypatch.delenv("BLUESKY_IDENTIFIER", raising=False)
    monkeypatch.delenv("BLUESKY_APP_PASSWORD", raising=False)

    provider = ApiProvider({}, logging.getLogger("test"))
    items = list(provider.fetch("alice.bsky.social"))

    assert len(items) == 1
    assert items[0].text == "hi"
    assert items[0].url == "https://bsky.app/profile/alice.bsky.social/post/abc"
    assert calls[0][0].startswith(bluesky_mod.PUBLIC_BASE)
    assert calls[0][2] == {}


def test_connector_uses_single_api_provider():
    connector = BlueskyConnector({}, logging.getLogger("test"))
    providers = connector.providers()
    assert len(providers) == 1
    assert providers[0].name == "api"
