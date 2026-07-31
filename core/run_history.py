"""Persistent, local history for completed and failed crawl runs."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def run_history_path(config: dict) -> Path:
    """Return the configured history path, defaulting beside the checkpoint."""
    configured = config.get("run_history_file")
    if configured:
        return Path(configured)
    return Path(config.get("output_dir", "./output")) / ".run_history.json"


class RunHistory:
    """Append crawl lifecycle records to a small JSON file."""

    def __init__(self, path: str | Path, logger: logging.Logger):
        self.path = Path(path)
        self.logger = logger

    def recent(self, limit: int = 20) -> list[dict]:
        """Return the newest completed or in-progress records first."""
        records = self._load()
        return list(reversed(records[-limit:]))

    def start(self, trigger: str) -> str:
        """Persist a running record and return its id."""
        records = self._load()
        run_id = uuid4().hex
        records.append(
            {
                "id": run_id,
                "trigger": trigger,
                "started_at": _now(),
                "finished_at": None,
                "status": "running",
                "totals": None,
                "error": None,
            }
        )
        self._save(records)
        return run_id

    def finish(
        self,
        run_id: str,
        totals: dict[str, int] | None = None,
        error: str | None = None,
    ) -> None:
        """Mark a previously-started run as completed or failed."""
        records = self._load()
        for record in reversed(records):
            if record.get("id") == run_id:
                record.update(
                    {
                        "finished_at": _now(),
                        "status": "failed" if error else "completed",
                        "totals": totals,
                        "error": error,
                    }
                )
                self._save(records)
                return
        self.logger.warning("Run history record %s was not found", run_id)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            with open(self.path, encoding="utf-8") as history_file:
                data = json.load(history_file)
            if isinstance(data, dict) and isinstance(data.get("runs"), list):
                return data["runs"]
            self.logger.warning("Ignoring malformed run history at %s", self.path)
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.warning("Could not read run history at %s: %s", self.path, exc)
        return []

    def _save(self, records: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f"{self.path.name}.tmp")
        with open(temporary, "w", encoding="utf-8") as history_file:
            json.dump({"runs": records}, history_file, indent=2)
        temporary.replace(self.path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
