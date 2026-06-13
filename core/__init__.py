"""Core engine for the multi-source crawler orchestrator.

Holds source-agnostic plumbing: the normalized record model, checkpointing,
rate limiting, storage/output, RSS parsing, and the orchestration loop. Anything
that is not specific to a single source lives here so connectors stay thin.
"""
