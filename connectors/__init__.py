"""Source connectors.

Each connector exposes one or more ordered providers (tiers) and maps a source's
native data onto the normalized :class:`core.models.Item`. The base classes and
fallback runner live in :mod:`connectors.base`.
"""
