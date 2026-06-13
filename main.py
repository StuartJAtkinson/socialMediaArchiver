#!/usr/bin/env python3
"""Multi-source crawler orchestrator — CLI entry point.

Subcommands:
  crawl            Run the orchestrator over config/targets.yaml (default).
  status           Print checkpoint status and exit.
  resume           Clear the checkpoint and start fresh next run.
  facebook-login   Open a browser to capture a Facebook login session.

Replaces the old single-purpose ``scraper.py`` main. Generic plumbing now lives in
``core/`` and each source is a connector under ``connectors/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from core.checkpoint import Checkpoint
from core import orchestrator

logger = logging.getLogger("bytebytego")


def setup_logging(verbose: bool, debug: bool, log_file: Optional[str] = None) -> logging.Logger:
    log = logging.getLogger("bytebytego")
    log.setLevel(logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s")
    if log.hasHandlers():
        log.handlers.clear()
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        log.addHandler(fh)
    return log


def load_yaml(path: str, required: bool = True) -> dict:
    p = Path(path)
    if not p.exists():
        if required:
            logger.error("File not found: %s", path)
            sys.exit(1)
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.error("Error parsing %s: %s", path, e)
        sys.exit(1)


def load_targets(path: str) -> list[dict]:
    data = load_yaml(path, required=True)
    targets = data.get("targets", [])
    if not targets:
        logger.error("No targets found in %s. Add at least one {source, target}.", path)
        sys.exit(1)
    return targets


def _checkpoint_path(cfg: dict) -> str:
    return cfg.get("checkpoint_file", "./output/.checkpoint.json")


def cmd_status(cfg: dict) -> None:
    cp = Checkpoint(_checkpoint_path(cfg), logger)
    print("--- Checkpoint Status ---")
    print(json.dumps(cp.data, indent=2))
    print("-------------------------")


def cmd_resume(cfg: dict) -> None:
    path = Path(_checkpoint_path(cfg))
    if path.exists():
        try:
            path.unlink()
            logger.info("Checkpoint '%s' cleared. Next run starts fresh.", path)
        except OSError as e:
            logger.error("Failed to clear checkpoint '%s': %s", path, e)
    else:
        logger.info("No checkpoint at '%s'; nothing to clear.", path)


def cmd_facebook_login(cfg: dict) -> None:
    from connectors.facebook import save_login_session

    fb_cfg = cfg.get("sources", {}).get("facebook", {}) or {}
    save_login_session(fb_cfg, logger)


def cmd_crawl(cfg: dict, targets_path: str) -> None:
    targets = load_targets(targets_path)
    logger.info("Loaded %d target(s).", len(targets))

    cp = Checkpoint(_checkpoint_path(cfg), logger)
    if not cp.data.get("start_time"):
        cp.data["start_time"] = datetime.now(timezone.utc).isoformat()
        logger.info("Starting new crawl session.")

    orchestrator.run(targets, logger, cp, cfg)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-source crawler orchestrator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("command", nargs="?", default="crawl",
                        choices=["crawl", "status", "resume", "facebook-login"],
                        help="What to do (default: crawl).")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--targets", default="config/targets.yaml")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--log-file")
    # Proxy/Tor overrides (mirror the legacy scraper flags).
    parser.add_argument("--proxy-url")
    parser.add_argument("--tor-control-port", type=int)
    parser.add_argument("--tor-password")
    args = parser.parse_args()

    cfg = load_yaml(args.config, required=True)
    global logger
    logger = setup_logging(
        verbose=args.verbose or cfg.get("verbose", False),
        debug=args.debug or cfg.get("debug", False),
        log_file=args.log_file or cfg.get("log_file"),
    )

    if args.proxy_url:
        cfg["proxy_url"] = args.proxy_url
    if args.tor_control_port:
        cfg["tor_control_port"] = args.tor_control_port
    if args.tor_password:
        cfg["tor_password"] = args.tor_password

    if args.command == "status":
        cmd_status(cfg)
    elif args.command == "resume":
        cmd_resume(cfg)
    elif args.command == "facebook-login":
        cmd_facebook_login(cfg)
    else:
        cmd_crawl(cfg, args.targets)


if __name__ == "__main__":
    main()
