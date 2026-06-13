"""Reddit connector with a two-tier fallback chain.

Tier 1 — ``PrawProvider``: the official API (read-only) via ``praw``. Needs a free
script-app ``client_id``/``client_secret`` (env ``REDDIT_CLIENT_ID`` /
``REDDIT_CLIENT_SECRET`` take precedence over config). Gives scores, flair, and
comment trees.

Tier 2 — ``RedditRssProvider``: the public ``.rss`` feed for the same target. Zero
setup, no auth, but limited fields and no comments. Used automatically when praw
has no credentials or gets rate-limited/blocked.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Iterator

from connectors.base import Connector, Provider
from core.errors import AuthError, ProviderUnavailable, RateLimitError
from core.feeds import feedparser_available, parse_feed
from core.models import Item, ItemAuthor, MediaItem

SOURCE = "reddit"


def _normalize_target(target: str) -> tuple[str, str]:
    """Return (kind, name) where kind is 'subreddit' or 'user'.

    Accepts 'r/python', '/r/python', 'u/spez', 'user/spez', or a bare name
    (treated as a subreddit).
    """
    t = target.strip().strip("/")
    low = t.lower()
    if low.startswith(("r/", "/r/")):
        return "subreddit", t.split("/", 1)[1]
    if low.startswith(("u/", "user/")):
        return "user", t.split("/", 1)[1]
    return "subreddit", t


def _epoch_to_iso(epoch: float) -> str:
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except Exception:
        return ""


class PrawProvider(Provider):
    name = "praw"

    def _creds(self) -> dict:
        return {
            "client_id": os.environ.get("REDDIT_CLIENT_ID") or self.config.get("client_id", ""),
            "client_secret": os.environ.get("REDDIT_CLIENT_SECRET")
            or self.config.get("client_secret", ""),
            "user_agent": self.config.get("user_agent", "bytebytego-grabber/0.5"),
        }

    def available(self) -> bool:
        try:
            import praw  # noqa: F401
        except ImportError:
            self.logger.warning(
                "praw not installed — Reddit degrading to the public RSS fallback "
                "(no scores, no comment trees). Fix: pip install praw."
            )
            return False
        creds = self._creds()
        if not (creds["client_id"] and creds["client_secret"]):
            self.logger.warning(
                "No Reddit API credentials — degrading to the public RSS fallback "
                "(no scores, no comment trees). Fix: set REDDIT_CLIENT_ID / "
                "REDDIT_CLIENT_SECRET (or client_id/client_secret in config)."
            )
            return False
        return True

    def _submission_to_item(self, sub: Any, target: str) -> Item:
        media: list[MediaItem] = []
        url = getattr(sub, "url", "") or ""
        if url and any(url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
            media.append(MediaItem(url=url, media_type="image"))
        elif getattr(sub, "is_video", False):
            try:
                media.append(
                    MediaItem(
                        url=sub.media["reddit_video"]["fallback_url"], media_type="video"
                    )
                )
            except Exception:
                pass

        author = getattr(sub, "author", None)
        author_name = getattr(author, "name", "") if author else "[deleted]"

        return Item(
            id=str(sub.id),
            source=SOURCE,
            target=target,
            url=f"https://www.reddit.com{sub.permalink}",
            timestamp=_epoch_to_iso(getattr(sub, "created_utc", 0)),
            title=getattr(sub, "title", ""),
            text=getattr(sub, "selftext", "") or "",
            author=ItemAuthor(name=author_name, url=f"https://www.reddit.com/user/{author_name}"),
            media=media,
            links=[{"text": "link", "url": url}] if url else [],
            metrics={
                "score": getattr(sub, "score", 0),
                "upvote_ratio": getattr(sub, "upvote_ratio", None),
                "num_comments": getattr(sub, "num_comments", 0),
                "flair": getattr(sub, "link_flair_text", None),
            },
            comments=self._collect_comments(sub) if self.config.get("with_comments") else [],
            raw={
                "id": sub.id,
                "permalink": sub.permalink,
                "url": url,
                "over_18": getattr(sub, "over_18", False),
                "stickied": getattr(sub, "stickied", False),
            },
        )

    def _collect_comments(self, sub: Any) -> list[dict]:
        out: list[dict] = []
        limit = int(self.config.get("max_comments_per_post", 100) or 100)
        try:
            sub.comments.replace_more(limit=0)
            for c in sub.comments.list()[:limit]:
                out.append(
                    {
                        "id": getattr(c, "id", ""),
                        "text": getattr(c, "body", ""),
                        "author": getattr(getattr(c, "author", None), "name", "[deleted]"),
                        "score": getattr(c, "score", 0),
                        "timestamp": _epoch_to_iso(getattr(c, "created_utc", 0)),
                    }
                )
        except Exception as e:
            self.logger.debug("Could not collect comments: %s", e)
        return out

    def fetch(self, target: str) -> Iterator[Item]:
        import praw
        import prawcore

        creds = self._creds()
        reddit = praw.Reddit(
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            user_agent=creds["user_agent"],
            check_for_updates=False,
        )
        reddit.read_only = True

        kind, name = _normalize_target(target)
        limit = int(self.config.get("max_posts", 50) or 50)
        sort = self.config.get("sort", "new")

        try:
            if kind == "user":
                listing = getattr(reddit.redditor(name).submissions, sort)(limit=limit)
            else:
                listing = getattr(reddit.subreddit(name), sort)(limit=limit)
            for sub in listing:
                yield self._submission_to_item(sub, target)
        except prawcore.exceptions.TooManyRequests as e:
            raise RateLimitError(str(e)) from e
        except prawcore.exceptions.ResponseException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 429:
                raise RateLimitError(str(e)) from e
            if status in (401, 403):
                raise AuthError(str(e)) from e
            raise
        except prawcore.exceptions.OAuthException as e:
            raise AuthError(str(e)) from e


class RedditRssProvider(Provider):
    name = "reddit-rss"

    def available(self) -> bool:
        if not feedparser_available():
            self.logger.info("feedparser not installed; Reddit RSS fallback disabled.")
            return False
        return True

    def fetch(self, target: str) -> Iterator[Item]:
        if not feedparser_available():
            raise ProviderUnavailable("feedparser not installed")
        kind, name = _normalize_target(target)
        prefix = "user" if kind == "user" else "r"
        feed_url = f"https://www.reddit.com/{prefix}/{name}/.rss"

        # Reddit feed entry ids look like "t3_abc123"; expose the bare id.
        def _id(entry):
            raw_id = entry.get("id", "") or entry.get("link", "")
            return raw_id.rsplit("_", 1)[-1] if "_" in raw_id else raw_id

        yield from parse_feed(
            feed_url=feed_url,
            source=SOURCE,
            target=target,
            logger=self.logger,
            max_items=self.config.get("max_posts"),
            id_fn=_id,
        )


class RedditConnector(Connector):
    name = SOURCE

    def build_providers(self) -> list[Provider]:
        return [
            PrawProvider(self.config, self.logger),
            RedditRssProvider(self.config, self.logger),
        ]
