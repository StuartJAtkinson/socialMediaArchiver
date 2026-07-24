import logging

from connectors.facebook import FacebookConnector, GraphApiProvider, _page_slug


def test_facebook_uses_only_official_graph_api(monkeypatch):
    monkeypatch.delenv("FB_GRAPH_TOKEN", raising=False)
    connector = FacebookConnector({}, logging.getLogger("test"))

    providers = connector.providers()

    assert len(providers) == 1
    assert isinstance(providers[0], GraphApiProvider)
    assert providers[0].name == "graph-api"
    assert providers[0].available() is False


def test_graph_token_environment_variable_enables_provider(monkeypatch):
    monkeypatch.setenv("FB_GRAPH_TOKEN", "test-token")
    provider = GraphApiProvider({}, logging.getLogger("test"))

    assert provider.available() is True


def test_graph_version_is_current_and_configurable(monkeypatch):
    monkeypatch.delenv("FB_GRAPH_VERSION", raising=False)
    assert GraphApiProvider({}, logging.getLogger("test"))._version() == "25.0"
    assert GraphApiProvider(
        {"graph_version": "v24.0"}, logging.getLogger("test")
    )._version() == "24.0"
    monkeypatch.setenv("FB_GRAPH_VERSION", "26.0")
    assert GraphApiProvider({}, logging.getLogger("test"))._version() == "26.0"


def test_page_slug_accepts_slug_and_url():
    assert _page_slug("Meta") == "Meta"
    assert _page_slug("https://www.facebook.com/Meta/posts/1") == "Meta"
