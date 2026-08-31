"""Mastodon connector.

Single-tier: the public REST API (``/api/v1/accounts/:id/statuses``). Public
timelines need no auth; an optional bearer token (``MASTODON_TOKEN`` env or
``token`` config) raises the rate limit and allows followers-only accounts.

Mastodon is federated, so a target must carry both the instance host and the
account handle: ``mastodon.social/@Gargron``, a full profile URL, or
``@Gargron@mastodon.social``.
"""

from __future__ import annotations

import os
from typing import Iterator
from urllib.parse import urlparse

from connectors.base import Provider, SingleProviderConnector
from core.errors import AuthError, ProviderUnavailable, RateLimitError
from core.models import Item, ItemAuthor, MediaItem

SOURCE = "mastodon"


def _parse_target(target: str) -> tuple[str, str]:
    """Return ``(instance_host, acct)`` from a target.

    Accepts ``instance/@user``, a full profile URL, or ``@user@instance``.
    """
    t = target.strip()
    if t.startswith("http"):
        parsed = urlparse(t)
        return parsed.netloc, parsed.path.strip("/").lstrip("@")
    if t.startswith("@") and t.count("@") == 2:
        _, user, host = t.split("@")
        return host, user
    if "/" in t:
        host, acct = t.split("/", 1)
        return host, acct.lstrip("@")
    raise ValueError(f"Cannot parse Mastodon target '{target}'; expected 'instance/@user'")


def _next_link(link_header: str) -> str | None:
    """Extract the 'next' URL from a Mastodon ``Link`` pagination header."""
    for part in link_header.split(","):
        segments = [s.strip() for s in part.split(";")]
        if len(segments) >= 2 and segments[1] == 'rel="next"':
            return segments[0].strip("<>")
    return None


class ApiProvider(Provider):
    name = "api"

    def _token(self) -> str:
        return os.environ.get("MASTODON_TOKEN") or self.config.get("token", "")

    def available(self) -> bool:
        try:
            import requests  # noqa: F401
        except ImportError:
            self.logger.info("requests not installed; Mastodon connector disabled.")
            return False
        return True

    def _headers(self) -> dict:
        token = self._token()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def fetch(self, target: str) -> Iterator[Item]:
        import requests

        host, acct = _parse_target(target)
        base = f"https://{host}/api/v1"
        headers = self._headers()

        lookup = requests.get(
            f"{base}/accounts/lookup", params={"acct": acct}, headers=headers, timeout=30
        )
        self._raise_for_status(lookup, f"looking up {acct}")
        account_id = lookup.json().get("id")
        if not account_id:
            raise ProviderUnavailable(f"Mastodon account '{acct}' not found on {host}")

        limit = int(self.config.get("max_posts", 40) or 40)
        url = f"{base}/accounts/{account_id}/statuses"
        params = {
            "limit": min(limit, 40),
            "exclude_replies": "true" if self.config.get("exclude_replies", True) else "false",
        }
        fetched = 0

        while url and fetched < limit:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
            params = None  # subsequent 'next' urls are fully-formed
            self._raise_for_status(resp, "fetching statuses")

            statuses = resp.json()
            if not statuses:
                break
            for status in statuses:
                fetched += 1
                yield self._status_to_item(status, target)
                if fetched >= limit:
                    break

            url = _next_link(resp.headers.get("Link", ""))

    def _raise_for_status(self, resp, what: str) -> None:
        if resp.status_code == 429:
            raise RateLimitError(f"Mastodon rate limit {what}")
        if resp.status_code in (401, 403):
            raise AuthError(f"Mastodon auth error {what}: {resp.status_code}")
        if resp.status_code != 200:
            raise ProviderUnavailable(f"Mastodon request failed ({resp.status_code}) {what}")

    def _status_to_item(self, status: dict, target: str) -> Item:
        content = status.get("reblog") or status
        author = content.get("account", {}) or {}
        media = [
            MediaItem(
                url=a.get("url", ""),
                media_type=a.get("type", "image") if a.get("type") in ("image", "video", "audio") else "file",
                width=(a.get("meta", {}) or {}).get("original", {}).get("width"),
                height=(a.get("meta", {}) or {}).get("original", {}).get("height"),
            )
            for a in content.get("media_attachments", [])
        ]
        return Item(
            id=str(status.get("id", "")),
            source=SOURCE,
            target=target,
            url=status.get("url", "") or status.get("uri", ""),
            timestamp=status.get("created_at", ""),
            text=content.get("content", ""),
            author=ItemAuthor(
                id=str(author.get("id", "")),
                name=author.get("display_name") or author.get("username", ""),
                url=author.get("url", ""),
                thumbnail=author.get("avatar", ""),
            ),
            media=media,
            metrics={
                "favourites": content.get("favourites_count", 0),
                "reblogs": content.get("reblogs_count", 0),
                "replies": content.get("replies_count", 0),
            },
            raw=status,
        )


class MastodonConnector(SingleProviderConnector):
    name = SOURCE

    def make_provider(self) -> Provider:
        return ApiProvider(self.config, self.logger)
