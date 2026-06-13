"""Exceptions used to drive the connector fallback chain.

A provider raises one of these to signal that the orchestrator should stop using
it and advance to the next (lower) tier. Anything else propagating out of a
provider is treated as a hard error for that target.
"""


class ConnectorError(Exception):
    """Base class for connector/provider errors."""


class ProviderUnavailable(ConnectorError):
    """The provider cannot run at all (missing dependency, creds, or session).

    Distinct from ``available()`` returning False in that it can be raised mid-run
    when a precondition is only discovered late.
    """


class AuthError(ConnectorError):
    """Authentication/authorization failed — fall back to a lower tier."""


class RateLimitError(ConnectorError):
    """The source rate-limited us. Carries an optional retry hint (seconds)."""

    def __init__(self, message: str = "", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after
