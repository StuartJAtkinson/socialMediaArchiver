import json

import web


def _write_item(root, source, item_id, target="@example", timestamp="2026-01-01"):
    directory = root / source
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": item_id,
        "source": source,
        "target": target,
        "url": f"https://example.test/{item_id}",
        "timestamp": timestamp,
        "text": f"post {item_id}",
        "media": [{"url": "https://example.test/image.png", "media_type": "image"}],
        "metrics": {"likes": 2},
    }
    (directory / f"{item_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_reads_only_normalized_output(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "OUTPUT_DIR", tmp_path)
    _write_item(tmp_path, "twitter", "one")
    _write_item(tmp_path, "twitter", "two", timestamp="2026-02-01")

    accounts = web.get_accounts()
    stats = web.get_account_stats("twitter", "@example")
    posts = web.get_posts("twitter", "@example")

    assert accounts == [{
        "platform": "twitter",
        "account": "@example",
        "path": str(tmp_path / "twitter"),
        "post_count": 2,
    }]
    assert stats["post_count"] == 2
    assert stats["image_count"] == 2
    assert stats["earliest_post"] == "2026-01-01"
    assert stats["latest_post"] == "2026-02-01"
    assert posts["total"] == 2


def test_background_archive_runs_orchestrator(monkeypatch):
    calls = []
    monkeypatch.setattr(web.crawler_cli, "load_yaml", lambda path: {"verbose": False})
    monkeypatch.setattr(web.crawler_cli, "setup_logging", lambda **kwargs: object())
    monkeypatch.setattr(
        web.crawler_cli,
        "cmd_crawl",
        lambda config, targets, trigger="manual": calls.append((config, targets, trigger)),
    )

    web.run_archiver_background()

    assert calls == [({"verbose": False}, "config/targets.yaml", "manual")]
    assert web.is_archiving is False


def test_schedule_interval_only_accepts_positive_minutes():
    assert web._schedule_seconds({"schedule": {"interval_minutes": 5}}) == 300
    assert web._schedule_seconds({"schedule": {"interval_minutes": 0}}) == 0
    assert web._schedule_seconds({"schedule": {"interval_minutes": "nope"}}) == 0
    assert web._schedule_seconds({"schedule": {"interval_minutes": "inf"}}) == 0


def test_dashboard_routes_render():
    client = web.app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/api/stats").status_code == 200


def test_api_search_uses_index_when_present(tmp_path, monkeypatch):
    from core.index import PostIndex, index_path
    from core.models import Item

    monkeypatch.setattr(web, "OUTPUT_DIR", tmp_path)
    idx = PostIndex(index_path(tmp_path))
    idx.record(Item(id="one", source="twitter", target="@example", timestamp="2026-01-01",
                     text="the rocket launched today"))
    idx.close()

    client = web.app.test_client()
    resp = client.get("/api/search?q=rocket")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["total"] == 1
    assert data["results"][0]["account"] == "@example"


def test_api_search_without_query_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "OUTPUT_DIR", tmp_path)
    client = web.app.test_client()
    data = client.get("/api/search").get_json()
    assert data == {"results": [], "total": 0, "has_more": False}


def test_account_page_includes_shared_nav(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "OUTPUT_DIR", tmp_path)
    _write_item(tmp_path, "twitter", "one")

    client = web.app.test_client()
    resp = client.get("/account/twitter/@example")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'class="stage-nav' in body
    assert 'href="/connect"' in body


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.setattr(web, 'DASHBOARD_USERNAME', '')
    monkeypatch.setattr(web, 'DASHBOARD_PASSWORD', '')
    client = web.app.test_client()
    assert client.get('/api/stats').status_code == 200


def test_auth_required_when_credentials_set(monkeypatch):
    monkeypatch.setattr(web, 'DASHBOARD_USERNAME', 'admin')
    monkeypatch.setattr(web, 'DASHBOARD_PASSWORD', 'secret')
    client = web.app.test_client()

    assert client.get('/api/stats').status_code == 401

    import base64
    creds = base64.b64encode(b'admin:secret').decode()
    resp = client.get('/api/stats', headers={'Authorization': f'Basic {creds}'})
    assert resp.status_code == 200

    bad_creds = base64.b64encode(b'admin:wrong').decode()
    resp = client.get('/api/stats', headers={'Authorization': f'Basic {bad_creds}'})
    assert resp.status_code == 401


def test_account_page_posts_have_anchor_ids_for_search_deep_links(tmp_path, monkeypatch):
    monkeypatch.setattr(web, 'OUTPUT_DIR', tmp_path)
    _write_item(tmp_path, 'twitter', 'one')

    client = web.app.test_client()
    resp = client.get('/account/twitter/@example')

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="post-one"' in body
