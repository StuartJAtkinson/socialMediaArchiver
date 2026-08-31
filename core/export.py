"""Export a date range of the archive as a static, self-contained HTML bundle.

Reads matching posts from ``index.db`` (rebuilding a throwaway one in memory if
it's missing), loads each post's normalized JSON, and writes one dependency-free
``index.html`` plus a ``media/`` folder of copied attachments. No CDN scripts,
no server — the bundle opens straight from disk.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .index import PostIndex, index_path, rebuild

_STYLE = """
body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 720px;
       margin: 2rem auto; padding: 0 1rem; background: #0f1117; color: #e2e8f0; }
h1 { font-size: 1.25rem; }
.post { border: 1px solid #2d3148; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.post header { color: #94a3b8; font-size: .8rem; margin-bottom: 6px; }
.post img { max-width: 100%; border-radius: 6px; margin-top: 8px; display: block; }
.post footer { margin-top: 8px; font-size: .8rem; }
a { color: #818cf8; }
"""


def _load_item(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _post_html(row: dict, item: dict, media_dir: Path) -> str:
    media_html = ""
    for i, m in enumerate(item.get("media") or []):
        local = m.get("local_path")
        if not local or not Path(local).is_file():
            continue
        media_dir.mkdir(parents=True, exist_ok=True)
        dest_name = f"{item.get('source', row['platform'])}_{item.get('id', row['post_id'])}_{i}{Path(local).suffix}"
        shutil.copy2(local, media_dir / dest_name)
        media_html += f'<img src="media/{html.escape(dest_name)}" loading="lazy">'

    url = item.get("url", "")
    link_html = f'<a href="{html.escape(url)}">Original</a>' if url else ""
    return (
        f'<article class="post">'
        f"<header>{html.escape(row['platform'])} · @{html.escape(row['account'])} · "
        f"{html.escape(row['posted_at'])}</header>"
        f"<p>{html.escape(item.get('text', ''))}</p>"
        f"{media_html}"
        f"<footer>{link_html}</footer>"
        f"</article>"
    )


def export_range(
    output_dir,
    dest_dir,
    since: str = "",
    until: str = "",
    platform: str = "",
    account: str = "",
) -> Path:
    """Write a self-contained HTML export of posts in ``[since, until]``.

    Returns the path to the generated ``index.html``.
    """
    out = Path(output_dir)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    media_dir = dest / "media"

    path = index_path(out)
    idx = PostIndex(path) if path.exists() else rebuild(out)
    try:
        rows = idx.range_posts(since=since, until=until, platform=platform, account=account)
    finally:
        idx.close()

    cards = []
    for row in rows:
        try:
            item = _load_item(row["path"])
        except (OSError, json.JSONDecodeError, KeyError):
            continue
        cards.append(_post_html(row, item, media_dir))

    range_desc = " to ".join(p for p in (since, until) if p) or "all time"
    page = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>Archive export ({html.escape(range_desc)})</title>"
        f"<style>{_STYLE}</style></head><body>"
        f"<h1>Archive export</h1><p>{len(cards)} post(s), {html.escape(range_desc)}.</p>"
        f"{''.join(cards)}</body></html>"
    )

    index_file = dest / "index.html"
    index_file.write_text(page, encoding="utf-8")
    return index_file
