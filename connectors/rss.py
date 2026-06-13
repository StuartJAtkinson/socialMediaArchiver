"""RSS/Atom connector.

A single-tier connector over any feed URL. Covers blogs, Substack, news sites,
Hacker News, and the ``.rss`` endpoints exposed by YouTube and Reddit. All the
parsing lives in :mod:`core.feeds` so the Reddit fallback can reuse it.
"""

from __future__ import annotations

from typing import Iterator

from connectors.base import Provider, SingleProviderConnector
from core.errors import ProviderUnavailable
from core.feeds import feedparser_available, parse_feed
from core.models import Item

SOURCE = "rss"


class _FeedparserProvider(Provider):
    name = "feedparser"

    def available(self) -> bool:
        return feedparser_available()

    def fetch(self, target: str) -> Iterator[Item]:
        if not feedparser_available():
            raise ProviderUnavailable("feedparser not installed (pip install feedparser)")
        yield from parse_feed(
            feed_url=target,
            source=SOURCE,
            target=target,
            logger=self.logger,
            max_items=self.config.get("max_items"),
        )


class RssConnector(SingleProviderConnector):
    name = SOURCE

    def make_provider(self) -> Provider:
        return _FeedparserProvider(self.config, self.logger)
