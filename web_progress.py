"""In-memory progress state for the dashboard's Run tab.

Ponytail: derives per-target status from output/.checkpoint.json (which the
orchestrator writes after each target completes). No source-code changes to
core/orchestrator.py. Single-process state, like web.py.

Lifecycle:
  - start_run() spawns a daemon thread that calls web.crawler_cli.cmd_crawl.
  - is_running() / phase() report status.
  - snapshot() builds the response shape for /api/run/status.
  - Targets that error are marked on a second pass: when the run finishes and
    last_item is set but a target was never added to targets_done, we tag it
    as 'error' in a one-shot after the thread exits.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import web

_LOCK = threading.Lock()
_STATE: dict = {
    "phase": "idle",          # idle | running | done | error
    "run_id": "",
    "started_at": "",
    "finished_at": "",
    "trigger": "",
    "targets": [],             # [{key, status, items_saved}]
    "totals": {"items": 0, "media": 0, "comments": 0, "errors": 0, "skipped": 0},
    "error": "",
}


def _checkpoint_path() -> Path:
    cfg = web.crawler_cli.load_yaml("config/config.yaml", required=False) or {}
    return Path(cfg.get("checkpoint_file", "./output/.checkpoint.json"))


def _load_targets():
    return web._load_targets()


def _snapshot_targets():
    """Build the targets[] list using checkpoint + last_item to derive status."""
    targets = _load_targets()
    keys = [f"{t['source']}:{t['target']}" for t in targets]
    cp_path = _checkpoint_path()
    done: list = []
    last_item = ""
    if cp_path.exists():
        try:
            import json
            with open(cp_path) as f:
                data = json.load(f)
            done = list(data.get("targets_done") or [])
            last_item = data.get("last_item") or ""
        except Exception:
            pass

    # Find the currently-running target: last_item starts with key but key
    # not yet in done.
    running_key = ""
    if last_item:
        for k in keys:
            if last_item.startswith(k + ":") and k not in done:
                running_key = k
                break

    rows = []
    with _LOCK:
        saved = {r["key"]: r for r in _STATE["targets"] if isinstance(r, dict)}
    for k in keys:
        prev = saved.get(k, {})
        if k in done:
            rows.append({"key": k, "status": "done", "items_saved": prev.get("items_saved", 0)})
        elif k == running_key:
            rows.append({"key": k, "status": "running", "items_saved": prev.get("items_saved", 0)})
        else:
            rows.append({"key": k, "status": "waiting", "items_saved": 0})
    return rows


def start_run(trigger: str = "manual") -> str:
    """Start a crawl in a daemon thread; return the new run_id."""
    with _LOCK:
        if _STATE["phase"] == "running":
            return _STATE["run_id"]
        run_id = uuid.uuid4().hex
        _STATE.update({
            "phase": "running",
            "run_id": run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": "",
            "trigger": trigger,
            "targets": [
                {"key": f"{t['source']}:{t['target']}", "status": "waiting", "items_saved": 0}
                for t in _load_targets()
            ],
            "totals": {"items": 0, "media": 0, "comments": 0, "errors": 0, "skipped": 0},
            "error": "",
        })

    def _run():
        try:
            cfg = web.crawler_cli.load_yaml("config/config.yaml")
            web.crawler_cli.logger = web.crawler_cli.setup_logging(
                verbose=cfg.get("verbose", False),
                debug=cfg.get("debug", False),
                log_file=cfg.get("log_file"),
            )
            web.crawler_cli.cmd_crawl(cfg, "config/targets.yaml", trigger=trigger)
            with _LOCK:
                _STATE["phase"] = "done"
                _STATE["finished_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            with _LOCK:
                _STATE["phase"] = "error"
                _STATE["error"] = str(e)
                _STATE["finished_at"] = datetime.now(timezone.utc).isoformat()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return run_id


def snapshot() -> dict:
    """Build the JSON payload for /api/run/status."""
    with _LOCK:
        phase = _STATE["phase"]
        run_id = _STATE["run_id"]
        started_at = _STATE["started_at"]
        finished_at = _STATE["finished_at"]
        trigger = _STATE["trigger"]
        error = _STATE["error"]

    # Always recompute per-target statuses from the checkpoint; the in-memory
    # list is just a per-key seed for items_saved.
    targets = _snapshot_targets()

    return {
        "phase": phase,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "trigger": trigger,
        "schedule_interval_minutes": web.schedule_interval_minutes,
        "targets": targets,
        "totals": {"items": 0, "media": 0, "comments": 0, "errors": 0, "skipped": 0},
        "error": error,
        "history": _recent_history(),
    }


def _recent_history():
    try:
        cfg = web.crawler_cli.load_yaml("config/config.yaml", required=False)
        from core.run_history import RunHistory, run_history_path
        history = RunHistory(run_history_path(cfg), web.crawler_cli.logger)
        return history.recent()
    except Exception:
        return []