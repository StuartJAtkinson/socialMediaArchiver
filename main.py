#!/usr/bin/env python3
"""Multi-source crawler orchestrator — CLI entry point.

Subcommands:
  crawl            Run the orchestrator over config/targets.yaml (default).
  status           Print checkpoint status and exit.
  resume           Clear the checkpoint and start fresh next run.
  reindex          Rebuild index.db from the normalized JSON output alone.
  search QUERY     Full-text search over archived post text.
  export           Export a date range as a static, self-contained HTML bundle.

Replaces the old single-purpose ``scraper.py`` main. Generic plumbing now lives in
``core/`` and each source is a connector under ``connectors/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import yaml

from core.checkpoint import Checkpoint
from core import orchestrator
from core.export import export_range
from core.index import PostIndex, index_path
from core.index import rebuild as rebuild_index
from core.run_history import RunHistory, run_history_path

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


def cmd_reindex(cfg: dict) -> None:
    """Rebuild index.db from the normalized JSON output alone."""
    output_dir = (cfg.get("storage", {}) or {}).get("output_dir", cfg.get("output_dir", "./output"))
    idx = rebuild_index(output_dir)
    count = sum(a["post_count"] for a in idx.accounts())
    idx.close()
    logger.info("Rebuilt index at %s (%d posts).", Path(output_dir) / "index.db", count)


def cmd_export(cfg: dict, args: argparse.Namespace) -> None:
    """Export a date range as a static, self-contained HTML bundle."""
    if not args.output:
        logger.error("export requires --output DIR")
        sys.exit(1)
    output_dir = (cfg.get("storage", {}) or {}).get("output_dir", cfg.get("output_dir", "./output"))
    index_file = export_range(
        output_dir,
        args.output,
        since=args.since or "",
        until=args.until or "",
        platform=args.platform or "",
        account=args.account or "",
        query=args.query or "",
    )
    logger.info("Exported archive bundle to %s", index_file)


def cmd_search(cfg: dict, args: argparse.Namespace) -> None:
    """Full-text search over archived post text via index.db's FTS5 table."""
    if not args.query:
        logger.error("search requires a query, e.g.: python main.py search \"launch\"")
        sys.exit(1)
    output_dir = (cfg.get("storage", {}) or {}).get("output_dir", cfg.get("output_dir", "./output"))
    idx = PostIndex(index_path(output_dir))
    try:
        page = idx.search(
            args.query,
            platform=args.platform or "",
            account=args.account or "",
            since=args.since or "",
            until=args.until or "",
        )
    finally:
        idx.close()

    print(f"--- {page['total']} match(es) for {args.query!r} ---")
    for r in page["results"]:
        print(f"[{r['platform']}] @{r['account']}  {r['posted_at']}  {r['post_id']}")
        print(f"    {r['snippet']}")


def cmd_crawl(cfg: dict, targets_path: str, trigger: str = "manual") -> dict[str, int]:
    targets = load_targets(targets_path)
    logger.info("Loaded %d target(s).", len(targets))

    cp = Checkpoint(_checkpoint_path(cfg), logger)
    cp.begin_run()
    logger.info("Starting new crawl session.")
    history = RunHistory(run_history_path(cfg), logger)
    run_id = history.start(trigger)
    try:
        totals = orchestrator.run(targets, logger, cp, cfg)
    except Exception as exc:
        history.finish(run_id, error=str(exc))
        raise
    history.finish(run_id, totals=totals)
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-source crawler orchestrator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("command", nargs="?", default="crawl",
                        choices=["crawl", "status", "resume", "reindex", "search", "export"],
                        help="What to do (default: crawl).")
    parser.add_argument("query", nargs="?", default="",
                        help="Search text (only used by the 'search' command).")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--targets", default="config/targets.yaml")
    parser.add_argument("--platform", help="Filter search/export results by platform.")
    parser.add_argument("--account", help="Filter search/export results by account.")
    parser.add_argument("--since", help="Filter search/export results to posted_at >= this ISO date.")
    parser.add_argument("--until", help="Filter search/export results to posted_at <= this ISO date.")
    parser.add_argument("--output", help="Destination directory for 'export' (created if missing).")
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
    elif args.command == "reindex":
        cmd_reindex(cfg)
    elif args.command == "search":
        cmd_search(cfg, args)
    elif args.command == "export":
        cmd_export(cfg, args)
    else:
        cmd_crawl(cfg, args.targets)


if __name__ == "__main__":
    main()
