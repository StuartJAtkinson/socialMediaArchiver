"""Maps a source name to its Connector class.

Connectors are imported lazily so that a missing optional dependency for one
source (e.g. praw, playwright) never blocks the others from loading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from connectors.base import Connector

# source name -> "module:ClassName"
_REGISTRY: dict[str, str] = {
    "youtube_community": "connectors.youtube_community:YouTubeCommunityConnector",
    "reddit": "connectors.reddit:RedditConnector",
    "rss": "connectors.rss:RssConnector",
    "facebook": "connectors.facebook:FacebookConnector",
}


def available_sources() -> list[str]:
    return sorted(_REGISTRY)


def get_connector_class(source: str) -> "Type[Connector]":
    """Import and return the Connector class for ``source``."""
    import importlib

    try:
        spec = _REGISTRY[source]
    except KeyError:
        raise ValueError(
            f"Unknown source '{source}'. Known: {', '.join(available_sources())}"
        ) from None
    module_path, class_name = spec.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
