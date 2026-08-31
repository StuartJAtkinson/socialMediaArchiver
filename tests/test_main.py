import argparse
import logging

import main


def test_cmd_search_prints_matches(tmp_path, capsys):
    main.logger = logging.getLogger("test-search")
    from core.index import PostIndex, index_path
    from core.models import Item

    idx = PostIndex(index_path(tmp_path))
    idx.record(Item(id="one", source="twitter", target="@ex", timestamp="2026-01-01",
                     text="the rocket launched today"))
    idx.close()

    args = argparse.Namespace(query="rocket", platform=None, account=None, since=None, until=None)
    main.cmd_search({"output_dir": str(tmp_path)}, args)

    out = capsys.readouterr().out
    assert "1 match" in out
    assert "@ex" in out


def test_cmd_search_requires_query(tmp_path):
    main.logger = logging.getLogger("test-search")
    args = argparse.Namespace(query="", platform=None, account=None, since=None, until=None)
    try:
        main.cmd_search({"output_dir": str(tmp_path)}, args)
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert e.code == 1
