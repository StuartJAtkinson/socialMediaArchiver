"""Politeness controls: inter-request delays with jitter, and proxy/Tor rotation.

Extracted from the original ``scraper.py`` so every connector benefits from the
same throttling and rotation behavior.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional


def sleep_with_jitter(
    delay: float, logger: Optional[logging.Logger] = None, jitter_frac: float = 0.2
) -> None:
    """Sleep ``delay`` seconds +/- ``jitter_frac`` to avoid a robotic cadence."""
    if delay <= 0:
        return
    jitter = delay * jitter_frac
    sleep_time = max(0.0, delay + random.uniform(-jitter, jitter))
    if logger:
        logger.debug("Sleeping %.2fs", sleep_time)
    time.sleep(sleep_time)


def new_tor_circuit(
    tor_password: str,
    control_port: int = 9051,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Request a fresh Tor circuit via the control port. Best-effort."""
    if logger is None:
        logger = logging.getLogger("bytebytego")
    try:
        import stem.connection
        import stem.signal

        controller = stem.connection.connect(port=control_port, password=tor_password)
        if controller:
            controller.signal(stem.signal.Signal.NEWNYM)
            logger.info("New Tor circuit established via control port %d", control_port)
            return True
        logger.warning("Could not connect to Tor control port %d", control_port)
        return False
    except ImportError:
        logger.warning("stem not installed; cannot rotate Tor circuits (pip install stem).")
        return False
    except Exception as e:
        logger.warning("Could not rotate Tor circuit via port %d: %s", control_port, e)
        return False


class RotationManager:
    """Counts processed items and triggers Tor rotation at a configured cadence."""

    def __init__(self, config: dict, logger: logging.Logger):
        self.logger = logger
        self.proxy_url = config.get("proxy_url", "") or None
        self.rotate_every = int(config.get("proxy_rotation_every", 0) or 0)
        self.tor_control_port = config.get("tor_control_port") or 0
        self.tor_password = config.get("tor_password", "")
        self._since_rotation = 0

    @property
    def tor_enabled(self) -> bool:
        return bool(self.tor_control_port)

    def tick(self) -> None:
        """Call once per processed item; rotates when the cadence is reached."""
        if not self.proxy_url or self.rotate_every <= 0:
            return
        self._since_rotation += 1
        if self._since_rotation >= self.rotate_every:
            self._since_rotation = 0
            self.logger.info("Rotating proxy/Tor after %d items.", self.rotate_every)
            if self.tor_enabled:
                new_tor_circuit(
                    self.tor_password, int(self.tor_control_port), self.logger
                )
