import json

from core.index import PostIndex, index_path, rebuild
from core.models import Item, MediaItem


def _item(item_id, target="@example", timestamp="2026-01-01", text="hi"):
    return Item(
        id=item_id,
        source="twitter",
        target=target,
        timestamp=timestamp,
        text=text,
        media=[MediaItem(url="https://example.test/i.png", media_type="image")],
    )


def test_record_and_query(tmp_path):
    idx = PostIndex(index_path(tmp_path))
    idx.record(_item("one", timestamp="2026-01-01"), path="output/twitter/one.json")
    idx.record(_item("two", timestamp="2026-02-01"), path="output/twitter/two.json")

    assert idx.accounts() == [{"platform": "twitter", "account": "@example", "post_count": 2}]

    stats = idx.account_stats("twitter", "@example")
    assert stats["post_count"] == 2
    assert stats["earliest_post"] == "2026-01-01"
    assert stats["latest_post"] == "2026-02-01"

    page = idx.list_posts("twitter", "@example", limit=1, offset=0)
    assert page["total"] == 2
    assert page["has_more"] is True
    assert page["posts"][0]["post_id"] == "one"
    idx.close()


def test_record_upserts_on_same_platform_and_id(tmp_path):
    idx = PostIndex(index_path(tmp_path))
    idx.record(_item("one", text="v1"), path="a")
    idx.record(_item("one", text="v2"), path="a")
    assert idx.account_stats("twitter", "@example")["post_count"] == 1
    idx.close()


def test_rebuild_matches_filesystem(tmp_path):
    out = tmp_path / "twitter"
    out.mkdir()
    (out / "one.json").write_text(json.dumps({
        "id": "one", "source": "twitter", "target": "@example",
        "timestamp": "2026-01-01", "text": "hi", "media": [],
    }), encoding="utf-8")
    (out / "one_comments.json").write_text("[]", encoding="utf-8")

    idx = rebuild(tmp_path)
    try:
        assert idx.accounts() == [{"platform": "twitter", "account": "@example", "post_count": 1}]
    finally:
        idx.close()
