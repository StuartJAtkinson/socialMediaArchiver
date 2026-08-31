"""Bluesky connector.

Single-tier: the AT Protocol ``app.bsky.feed.getAuthorFeed`` endpoint. Public
profiles need no auth — requests go to the public AppView
(``public.api.bsky.app``). An optional app password (``BLUESKY_IDENTIFIER`` /
``BLUESKY_APP_PASSWORD`` env, or ``identifier``/``app_password`` config) logs
in via ``com.atproto.server.createSession`` and calls the authenticated PDS
endpoint instead, needed for private/blocked-to-anon accounts.
"""

from __future__ import annotations

import os
from typing import Iterator
from urllib.parse import urlparse

from connectors.base import Provider, SingleProviderConnector
from core.errors import AuthError, ProviderUnavailable, RateLimitError
from core.models import Item, ItemAuthor, MediaItem

SOURCE = "bluesky"
PUBLIC_BASE = "https://public.api.bsky.app/xrpc"
AUTH_BASE = "https://bsky.social/xrpc"


def _parse_target(target: str) -> str:
    """Return the actor (handle or DID) from a target.

    Accepts a bare handle, a DID, ``@handle``, or a full profile URL like
    ``https://bsky.app/profile/<actor>``.
    """
    t = target.strip()
    if t.startswith("http"):
        path = urlparse(t).path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "profile":
            return parts[1]
        raise ValueError(f"Cannot parse Bluesky profile URL '{target}'")
    return t.lstrip("@")


class ApiProvider(Provider):
    name = "api"

    def _creds(self) -> tuple[str, str]:
        identifier = os.environ.get("BLUESKY_IDENTIFIER") or self.config.get("identifier", "")
        password = os.environ.get("BLUESKY_APP_PASSWORD") or self.config.get("app_password", "")
        return identifier, password

    def available(self) -> bool:
        try:
            import requests  # noqa: F401
        except ImportError:
            self.logger.info("requests not installed; Bluesky connector disabled.")
            return False
        return True

    def _session(self, requests) -> tuple[str, dict]:
        """Return (base_url, headers), logging in only if credentials are set."""
        identifier, password = self._creds()
        if not (identifier and password):
            return PUBLIC_BASE, {}

        resp = requests.post(
            f"{AUTH_BASE}/com.atproto.server.createSession",
            json={"identifier": identifier, "password": password},
            timeout=30,
        )
        if resp.status_code == 429:
            raise RateLimitError("Bluesky rate limit creating session")
        if resp.status_code != 200:
            raise AuthError(f"Bluesky login failed ({resp.status_code})")
        token = resp.json().get("accessJwt", "")
        return AUTH_BASE, {"Authorization": f"Bearer {token}"}

    def fetch(self, target: str) -> Iterator[Item]:
        import requests

        actor = _parse_target(target)
        base, headers = self._session(requests)

        limit = int(self.config.get("max_posts", 50) or 50)
        url = f"{base}/app.bsky.feed.getAuthorFeed"
        cursor: str | None = None
        fetched = 0

        while fetched < limit:
            params = {"actor": actor, "limit": min(limit - fetched, 100)}
            if cursor:
                params["cursor"] = cursor
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 429:
                raise RateLimitError("Bluesky rate limit fetching author feed")
            if resp.status_code in (401, 403):
                raise AuthError(f"Bluesky auth error: {resp.status_code}")
            if resp.status_code != 200:
                raise ProviderUnavailable(f"Bluesky request failed ({resp.status_code})")

            data = resp.json()
            feed = data.get("feed", [])
            if not feed:
                break
            for entry in feed:
                fetched += 1
                yield self._entry_to_item(entry, target)
                if fetched >= limit:
                    break

            cursor = data.get("cursor")
            if not cursor:
                break

    def _entry_to_item(self, entry: dict, target: str) -> Item:
        post = entry.get("post", {}) or {}
        record = post.get("record", {}) or {}
        author = post.get("author", {}) or {}
        uri = post.get("uri", "")
        rkey = uri.rsplit("/", 1)[-1] if uri else ""
        handle = author.get("handle", "")
        web_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if handle and rkey else ""

        media = [
            MediaItem(
                url=img.get("fullsize", "") or img.get("thumb", ""),
                media_type="image",
            )
            for img in ((post.get("embed", {}) or {}).get("images", []) or [])
        ]

        return Item(
            id=uri or rkey,
            source=SOURCE,
            target=target,
            url=web_url,
            timestamp=record.get("createdAt", ""),
            text=record.get("text", ""),
            author=ItemAuthor(
                id=author.get("did", ""),
                name=author.get("displayName") or handle,
                url=f"https://bsky.app/profile/{handle}" if handle else "",
                thumbnail=author.get("avatar", ""),
            ),
            media=media,
            metrics={
                "likes": post.get("likeCount", 0),
                "reposts": post.get("repostCount", 0),
                "replies": post.get("replyCount", 0),
            },
            raw=entry,
        )


class BlueskyConnector(SingleProviderConnector):
    name = SOURCE

    def make_provider(self) -> Provider:
        return ApiProvider(self.config, self.logger)
