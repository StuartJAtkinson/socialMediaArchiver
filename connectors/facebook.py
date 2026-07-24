"""Facebook Page connector using the official Graph API.

Browser scraping was deliberately removed. Facebook's obfuscated DOM is not a
stable interface and saved browser sessions add credential and Terms-of-Service
risk. A configured ``FB_GRAPH_TOKEN`` (or ``graph_token`` setting) is therefore
required; without one the provider is reported as unavailable and the
orchestrator continues with the remaining targets.
"""

from __future__ import annotations

import os
from typing import Iterator
from urllib.parse import urlparse

from connectors.base import Connector, Provider
from core.errors import AuthError, ProviderUnavailable, RateLimitError
from core.models import Item, ItemAuthor, MediaItem

SOURCE = "facebook"
DEFAULT_GRAPH_VERSION = "v25.0"
_RATE_LIMIT_CODES = {4, 17, 32, 613}
_AUTH_CODES = {102, 190, 200, 10, 459, 464}


def _page_slug(target: str) -> str:
    """Extract a page name/id from a slug or a facebook URL."""
    t = target.strip()
    if t.startswith("http"):
        path = urlparse(t).path.strip("/")
        return path.split("/")[0] if path else t
    return t.strip("/")


class GraphApiProvider(Provider):
    name = "graph-api"

    def _token(self) -> str:
        return os.environ.get("FB_GRAPH_TOKEN") or self.config.get("graph_token", "")

    def _version(self) -> str:
        version = (
            os.environ.get("FB_GRAPH_VERSION")
            or self.config.get("graph_version")
            or DEFAULT_GRAPH_VERSION
        )
        return str(version).lstrip("v")

    def available(self) -> bool:
        try:
            import requests  # noqa: F401
        except ImportError:
            self.logger.info("requests not installed; Graph API tier disabled.")
            return False
        if not self._token():
            self.logger.info("No Facebook Graph token; skipping Graph API tier.")
            return False
        return True

    def fetch(self, target: str) -> Iterator[Item]:
        import requests

        token = self._token()
        if not token:
            raise ProviderUnavailable("no Graph token")

        page = _page_slug(target)
        limit = int(self.config.get("max_posts", 50) or 50)
        fields = (
            "id,message,story,created_time,permalink_url,full_picture,"
            "from{name,id},attachments{media,url,type,subattachments}"
        )
        url = f"https://graph.facebook.com/v{self._version()}/{page}/posts"
        params = {"fields": fields, "limit": min(limit, 100), "access_token": token}
        fetched = 0

        while url and fetched < limit:
            resp = requests.get(url, params=params, timeout=30)
            params = None  # subsequent 'next' urls are fully-formed
            payload = resp.json()

            if "error" in payload:
                err = payload["error"]
                code = err.get("code")
                msg = err.get("message", "")
                if code in _RATE_LIMIT_CODES:
                    raise RateLimitError(f"Graph rate limit (code {code}): {msg}")
                if code in _AUTH_CODES:
                    raise AuthError(f"Graph auth error (code {code}): {msg}")
                raise RuntimeError(f"Graph API error (code {code}): {msg}")

            for node in payload.get("data", []):
                fetched += 1
                yield self._node_to_item(node, target)
                if fetched >= limit:
                    break

            url = payload.get("paging", {}).get("next")

    def _node_to_item(self, node: dict, target: str) -> Item:
        media: list[MediaItem] = []
        if node.get("full_picture"):
            media.append(MediaItem(url=node["full_picture"], media_type="image"))
        for att in (node.get("attachments", {}) or {}).get("data", []):
            m = (att.get("media") or {}).get("image", {})
            if m.get("src"):
                media.append(MediaItem(url=m["src"], media_type="image"))

        frm = node.get("from", {}) or {}
        return Item(
            id=str(node.get("id", "")),
            source=SOURCE,
            target=target,
            url=node.get("permalink_url", ""),
            timestamp=node.get("created_time", ""),
            text=node.get("message", "") or node.get("story", ""),
            author=ItemAuthor(id=frm.get("id", ""), name=frm.get("name", "")),
            media=media,
            metrics={},
            raw=node,
        )

class FacebookConnector(Connector):
    name = SOURCE

    def build_providers(self) -> list[Provider]:
        return [GraphApiProvider(self.config, self.logger)]
