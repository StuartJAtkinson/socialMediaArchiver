"""Connector and Provider base classes plus the fallback runner.

A *connector* represents a source (Reddit, Facebook, ...). It owns an ordered list
of *providers* — tiers tried highest-first. The default ``fetch`` walks that list:
when a provider is unavailable, rate-limited, or hits an auth error, it logs and
advances to the next tier, never re-yielding an item it has already emitted (dedup
by ``Item.uid``). Single-tier connectors (YouTube, RSS) just return one provider.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Iterator

from core.errors import AuthError, ProviderUnavailable, RateLimitError
from core.models import Item


class Provider(ABC):
    """One tier of a connector (e.g. an API path or a browser path)."""

    name: str = "provider"

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def available(self) -> bool:
        """Whether this provider can run (deps, creds, session present)."""
        return True

    @abstractmethod
    def fetch(self, target: str) -> Iterator[Item]:
        """Yield normalized Items for ``target``.

        Raise :class:`RateLimitError`, :class:`AuthError`, or
        :class:`ProviderUnavailable` to hand off to the next tier.
        """
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - optional hook
        """Release resources (browsers, sessions). Default no-op."""


class Connector(ABC):
    """A source. Owns ordered providers and the fallback logic between them."""

    name: str = "connector"

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self._providers: list[Provider] | None = None

    @abstractmethod
    def build_providers(self) -> list[Provider]:
        """Return providers ordered highest-tier first."""
        raise NotImplementedError

    def providers(self) -> list[Provider]:
        if self._providers is None:
            self._providers = self.build_providers()
        return self._providers

    def fetch(self, target: str) -> Iterator[Item]:
        """Yield Items for ``target``, falling back across tiers as needed."""
        seen: set[str] = set()
        providers = self.providers()
        if not providers:
            self.logger.error("[%s] no providers configured.", self.name)
            return

        last_error: Exception | None = None
        for provider in providers:
            if not provider.available():
                self.logger.info(
                    "[%s] provider '%s' unavailable; trying next tier.",
                    self.name,
                    provider.name,
                )
                continue

            self.logger.info("[%s] using provider '%s'.", self.name, provider.name)
            try:
                for item in provider.fetch(target):
                    if item.uid in seen:
                        continue
                    seen.add(item.uid)
                    yield item
                # Provider finished cleanly — no need to fall back.
                return
            except RateLimitError as e:
                last_error = e
                self.logger.warning(
                    "[%s] provider '%s' rate-limited (%s); falling back.",
                    self.name,
                    provider.name,
                    e,
                )
            except AuthError as e:
                last_error = e
                self.logger.warning(
                    "[%s] provider '%s' auth failed (%s); falling back.",
                    self.name,
                    provider.name,
                    e,
                )
            except ProviderUnavailable as e:
                last_error = e
                self.logger.info(
                    "[%s] provider '%s' became unavailable (%s); falling back.",
                    self.name,
                    provider.name,
                    e,
                )

        if last_error is not None and not seen:
            self.logger.error(
                "[%s] all providers exhausted for '%s'. Last error: %s",
                self.name,
                target,
                last_error,
            )

    def close(self) -> None:
        for provider in self._providers or []:
            try:
                provider.close()
            except Exception as e:  # pragma: no cover - cleanup best-effort
                self.logger.debug("Error closing provider %s: %s", provider.name, e)


class SingleProviderConnector(Connector):
    """Convenience base for connectors that have exactly one tier."""

    def make_provider(self) -> Provider:  # pragma: no cover - overridden
        raise NotImplementedError

    def build_providers(self) -> list[Provider]:
        return [self.make_provider()]
