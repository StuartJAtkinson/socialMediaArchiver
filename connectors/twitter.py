"""Twitter/X connector — Nitter RSS.

Provides the Twitter/X path through Nitter RSS. A Nitter
instance exposes a user's tweets at ``{instance}/{handle}/rss`` — which is just
RSS — so this reuses :func:`core.feeds.parse_feed` instead of reimplementing the
old HTML/entry parsing. One tier with a built-in instance probe: instances are
tried in order and the first that returns entries wins; if every instance is
dead the provider raises :class:`ProviderUnavailable` and the run continues.

Nitter public instances rot constantly (see ISSUES.md). Override the list via
``config.yaml`` ``sources.twitter.instances`` when the defaults go dark.
"""

from __future__ import annotations

from typing import Iterator
from urllib.parse import urlparse

from connectors.base import Provider, SingleProviderConnector
from core.errors import ProviderUnavailable
from core.feeds import feedparser_available, parse_feed
from core.models import Item

SOURCE = "twitter"

# ponytail: static default list rots — the probe skips dead ones, and
# sources.twitter.instances in config.yaml overrides this entirely.
_DEFAULT_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://xcancel.com",
]


def _handle(target: str) -> str:
    """Normalize @handle / bare / twitter.com|x.com URL -> bare handle."""
    t = target.strip()
    if "://" in t or t.startswith("www."):
        path = urlparse(t if "://" in t else "https://" + t).path
        t = path.strip("/").split("/")[0]
    return t.lstrip("@")


class _NitterProvider(Provider):
    name = "nitter-rss"

    def available(self) -> bool:
        return feedparser_available()

    def _instances(self) -> list[str]:
        return self.config.get("instances") or _DEFAULT_INSTANCES

    def fetch(self, target: str) -> Iterator[Item]:
        if not feedparser_available():
            raise ProviderUnavailable("feedparser not installed (pip install feedparser)")

        handle = _handle(target)
        if not handle:
            raise ProviderUnavailable(f"could not parse a Twitter handle from '{target}'")

        max_items = self.config.get("max_posts") or self.config.get("max_items")
        for instance in self._instances():
            feed_url = f"{instance.rstrip('/')}/{handle}/rss"
            got = False
            for item in parse_feed(
                feed_url=feed_url,
                source=SOURCE,
                target=handle,
                logger=self.logger,
                max_items=max_items,
            ):
                got = True
                yield item
            if got:
                return  # this instance worked — stop probing
            self.logger.info("[twitter] instance %s returned nothing; trying next.", instance)

        raise ProviderUnavailable(
            f"all Nitter instances failed for @{handle} "
            f"(set sources.twitter.instances in config.yaml to a live one)"
        )


class TwitterConnector(SingleProviderConnector):
    name = SOURCE

    def make_provider(self) -> Provider:
        return _NitterProvider(self.config, self.logger)


if __name__ == "__main__":
    # ponytail: self-check the one bit of real logic — handle normalization.
    cases = {
        "@jack": "jack",
        "jack": "jack",
        "https://twitter.com/jack": "jack",
        "https://x.com/jack/status/123": "jack",
        "www.x.com/Jack": "Jack",
    }
    for raw, want in cases.items():
        got = _handle(raw)
        assert got == want, f"{raw!r} -> {got!r}, wanted {want!r}"
    print("ok")
