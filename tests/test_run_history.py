import logging

import main
from core.checkpoint import Checkpoint
from core.run_history import RunHistory, run_history_path


def test_run_history_persists_completed_run(tmp_path):
    path = tmp_path / ".run_history.json"
    history = RunHistory(path, logging.getLogger("test"))

    run_id = history.start("scheduled")
    history.finish(run_id, totals={"items": 2, "errors": 0})

    records = RunHistory(path, logging.getLogger("test")).recent()
    assert len(records) == 1
    assert records[0]["id"] == run_id
    assert records[0]["trigger"] == "scheduled"
    assert records[0]["status"] == "completed"
    assert records[0]["finished_at"]
    assert records[0]["totals"] == {"items": 2, "errors": 0}


def test_run_history_path_defaults_to_output_directory():
    assert run_history_path({"output_dir": "archive"}).as_posix() == "archive/.run_history.json"


def test_checkpoint_new_run_revisits_targets_without_losing_item_deduplication(tmp_path):
    checkpoint = Checkpoint(str(tmp_path / ".checkpoint.json"), logging.getLogger("test"))
    checkpoint.mark_scraped("rss:one")
    checkpoint.mark_target_done("rss:https://example.test/feed")

    checkpoint.begin_run()

    assert checkpoint.is_scraped("rss:one")
    assert not checkpoint.is_target_done("rss:https://example.test/feed")
    assert checkpoint.data["start_time"]


def test_cmd_crawl_records_the_run_and_resets_completed_targets(tmp_path, monkeypatch):
    cfg = {
        "checkpoint_file": str(tmp_path / ".checkpoint.json"),
        "output_dir": str(tmp_path),
    }
    monkeypatch.setattr(main, "logger", logging.getLogger("test"))
    monkeypatch.setattr(main, "load_targets", lambda path: [{"source": "rss", "target": "feed"}])

    def fake_run(targets, logger, checkpoint, config):
        assert not checkpoint.is_target_done("rss:feed")
        checkpoint.mark_target_done("rss:feed")
        return {"items": 1, "media": 0, "comments": 0, "errors": 0, "skipped": 0}

    monkeypatch.setattr(main.orchestrator, "run", fake_run)

    assert main.cmd_crawl(cfg, "targets.yaml", trigger="scheduled")["items"] == 1
    assert RunHistory(run_history_path(cfg), logging.getLogger("test")).recent()[0]["status"] == "completed"
