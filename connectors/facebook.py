"""Facebook connector — tiered fallback chain.

Tiers, tried highest-first; the base runner advances on rate-limit/auth/unavailable
and dedups by ``Item.uid`` so items already pulled by a higher tier are not
re-emitted by a lower one:

1. ``GraphApiProvider`` — official Graph API with an access token. The only stable
   tier, but only reaches Pages/Groups the token is authorised for.
2. ``AuthBrowserProvider`` — Playwright Chromium replaying a saved login session
   (``storage_state``). Create it once with ``python main.py facebook-login``.
3. ``PublicBrowserProvider`` — same browser path, logged out; only sees what a
   public visitor sees.

IMPORTANT: the browser tiers scrape a heavily-obfuscated, frequently-changing DOM
and are ToS-sensitive. They are best-effort and will break; treat the Graph tier as
the reliable path. Extraction here degrades gracefully (yields nothing) rather than
crashing the whole run.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any, Iterator
from urllib.parse import urlparse

from connectors.base import Connector, Provider
from core.errors import AuthError, ProviderUnavailable, RateLimitError
from core.models import Item, ItemAuthor, MediaItem

SOURCE = "facebook"
GRAPH_VERSION = "v19.0"
_RATE_LIMIT_CODES = {4, 17, 32, 613}
_AUTH_CODES = {102, 190, 200, 10, 459, 464}


def _page_slug(target: str) -> str:
    """Extract a page name/id from a slug or a facebook URL."""
    t = target.strip()
    if t.startswith("http"):
        path = urlparse(t).path.strip("/")
        return path.split("/")[0] if path else t
    return t.strip("/")


def _hash_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Tier 1: Graph API
# --------------------------------------------------------------------------- #
class GraphApiProvider(Provider):
    name = "graph-api"

    def _token(self) -> str:
        return os.environ.get("FB_GRAPH_TOKEN") or self.config.get("graph_token", "")

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
        url = f"https://graph.facebook.com/{GRAPH_VERSION}/{page}/posts"
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


# --------------------------------------------------------------------------- #
# Tiers 2 & 3: browser scraping (best-effort)
# --------------------------------------------------------------------------- #
def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return True
    except ImportError:
        return False


class _BrowserProvider(Provider):
    """Shared Playwright scrape; subclasses decide whether to load a session."""

    use_session = False

    def available(self) -> bool:
        if not _playwright_available():
            self.logger.info("playwright not installed; %s tier disabled.", self.name)
            return False
        if self.use_session and not self._session_path():
            self.logger.info(
                "No saved Facebook session; skipping authenticated browser tier."
            )
            return False
        return True

    def _session_path(self) -> str | None:
        path = self.config.get("storage_state", "./config/fb_state.json")
        return path if path and os.path.isfile(path) else None

    def fetch(self, target: str) -> Iterator[Item]:
        from playwright.sync_api import sync_playwright

        page_url = target if target.startswith("http") else f"https://www.facebook.com/{_page_slug(target)}"
        headless = self.config.get("headless", True)
        max_posts = int(self.config.get("max_posts", 50) or 50)
        scroll_rounds = int(self.config.get("scroll_rounds", 8) or 8)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            ctx_args: dict[str, Any] = {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
            if self.use_session and self._session_path():
                ctx_args["storage_state"] = self._session_path()
            context = browser.new_context(**ctx_args)
            page = context.new_page()
            page.set_default_timeout(self.config.get("timeout", 30) * 1000)

            try:
                page.goto(page_url, wait_until="domcontentloaded")
            except Exception as e:
                browser.close()
                raise ProviderUnavailable(f"could not load {page_url}: {e}") from e

            if not self.use_session and self._hit_login_wall(page):
                browser.close()
                raise AuthError("public browser hit a login wall")

            seen_ids: set[str] = set()
            yielded = 0
            for _ in range(scroll_rounds):
                for rec in self._extract_articles(page):
                    if rec["id"] in seen_ids:
                        continue
                    seen_ids.add(rec["id"])
                    yielded += 1
                    yield self._record_to_item(rec, target)
                    if yielded >= max_posts:
                        browser.close()
                        return
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(1500)

            browser.close()

    def _hit_login_wall(self, page) -> bool:
        try:
            url = page.url.lower()
            if "login" in url or "/checkpoint" in url:
                return True
            return page.locator("input[name='email']").count() > 0
        except Exception:
            return False

    def _extract_articles(self, page) -> list[dict]:
        """Best-effort extraction of post text/permalink/time from the feed.

        Facebook's DOM is obfuscated and changes often; this targets the stable-ish
        ``div[role='article']`` containers and is intentionally defensive.
        """
        js = r"""
        () => {
          const out = [];
          const arts = document.querySelectorAll("div[role='article']");
          for (const a of arts) {
            const text = (a.innerText || "").trim();
            if (!text) continue;
            let permalink = "";
            const link = a.querySelector(
              "a[href*='/posts/'], a[href*='/permalink/'], a[href*='story_fbid'], a[href*='/videos/']"
            );
            if (link) permalink = link.href;
            let ts = "";
            const t = a.querySelector("abbr[data-utime], time");
            if (t) ts = t.getAttribute("datetime") || t.getAttribute("title") || "";
            out.push({ text, permalink, ts });
          }
          return out;
        }
        """
        try:
            records = page.evaluate(js) or []
        except Exception as e:
            self.logger.debug("Article extraction failed: %s", e)
            return []

        cleaned = []
        for r in records:
            permalink = r.get("permalink", "")
            m = re.search(r"(?:/posts/|story_fbid=|/permalink/|/videos/)(\d+)", permalink)
            rec_id = m.group(1) if m else _hash_id(r.get("text", ""))
            cleaned.append(
                {
                    "id": rec_id,
                    "text": r.get("text", ""),
                    "permalink": permalink,
                    "ts": r.get("ts", ""),
                }
            )
        return cleaned

    def _record_to_item(self, rec: dict, target: str) -> Item:
        return Item(
            id=rec["id"],
            source=SOURCE,
            target=target,
            url=rec.get("permalink", ""),
            timestamp=rec.get("ts", ""),
            timestamp_estimated=bool(rec.get("ts")) is False,
            text=rec.get("text", ""),
            author=ItemAuthor(name=_page_slug(target)),
            metrics={},
            raw={"via": self.name, **rec},
        )


class AuthBrowserProvider(_BrowserProvider):
    name = "auth-browser"
    use_session = True


class PublicBrowserProvider(_BrowserProvider):
    name = "public-browser"
    use_session = False


class FacebookConnector(Connector):
    name = SOURCE

    def build_providers(self) -> list[Provider]:
        return [
            GraphApiProvider(self.config, self.logger),
            AuthBrowserProvider(self.config, self.logger),
            PublicBrowserProvider(self.config, self.logger),
        ]


def save_login_session(config: dict, logger: logging.Logger) -> bool:
    """Open a headed browser for a one-time manual login, then save storage_state.

    Invoked by ``python main.py facebook-login``. The user logs in by hand; nothing
    is automated and no password is stored — only the resulting session cookies.
    """
    if not _playwright_available():
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    from pathlib import Path

    from playwright.sync_api import sync_playwright

    state_path = config.get("storage_state", "./config/fb_state.json")
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com/login")
        logger.info(
            "A browser window has opened. Log in to Facebook, then return here and "
            "press Enter to save the session."
        )
        try:
            input("Press Enter once you are logged in... ")
        except EOFError:
            logger.warning("No interactive stdin; waiting 60s for manual login instead.")
            page.wait_for_timeout(60_000)
        context.storage_state(path=state_path)
        browser.close()

    logger.info("Saved Facebook session to %s", state_path)
    return True
