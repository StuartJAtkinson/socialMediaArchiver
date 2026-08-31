import json

from core.export import export_range
from core.index import PostIndex, index_path


def _write_item(root, source, item_id, target="@example", timestamp="2026-01-01",
                 text="hi", media=None):
    directory = root / source
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": item_id,
        "source": source,
        "target": target,
        "url": f"https://example.test/{item_id}",
        "timestamp": timestamp,
        "text": text,
        "media": media or [],
    }
    path = directory / f"{item_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_export_range_writes_self_contained_bundle(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    p1 = _write_item(out, "twitter", "one", timestamp="2026-01-01", text="in range")
    p2 = _write_item(out, "twitter", "two", timestamp="2026-06-01", text="out of range")

    idx = PostIndex(index_path(out))
    from core.models import Item
    idx.record(Item(id="one", source="twitter", target="@example", timestamp="2026-01-01",
                     text="in range"), path=str(p1))
    idx.record(Item(id="two", source="twitter", target="@example", timestamp="2026-06-01",
                     text="out of range"), path=str(p2))
    idx.close()

    dest = tmp_path / "bundle"
    index_file = export_range(out, dest, since="2026-01-01", until="2026-03-01")

    assert index_file == dest / "index.html"
    body = index_file.read_text(encoding="utf-8")
    assert "in range" in body
    assert "out of range" not in body
    assert "1 post(s)" in body
    assert "cdn." not in body  # self-contained: no external script/style requests


def test_export_range_copies_local_media_into_bundle(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    media_src = tmp_path / "source.png"
    media_src.write_bytes(b"fake-png")
    p1 = _write_item(
        out, "twitter", "one", timestamp="2026-01-01", text="has media",
        media=[{"url": "https://example.test/i.png", "local_path": str(media_src),
                "media_type": "image"}],
    )

    from core.models import Item, MediaItem
    idx = PostIndex(index_path(out))
    idx.record(
        Item(id="one", source="twitter", target="@example", timestamp="2026-01-01",
             text="has media", media=[MediaItem(local_path=str(media_src))]),
        path=str(p1),
    )
    idx.close()

    dest = tmp_path / "bundle"
    export_range(out, dest)

    copied = list((dest / "media").glob("*.png"))
    assert len(copied) == 1
    body = (dest / "index.html").read_text(encoding="utf-8")
    assert f"media/{copied[0].name}" in body


def test_export_range_rebuilds_index_when_missing(tmp_path):
    out = tmp_path / "output"
    _write_item(out, "twitter", "one", timestamp="2026-01-01", text="rebuilt")

    dest = tmp_path / "bundle"
    index_file = export_range(out, dest)

    assert "rebuilt" in index_file.read_text(encoding="utf-8")
