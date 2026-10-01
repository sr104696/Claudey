import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _no_judgment_db(monkeypatch):
    """score.judgments() would read data/judgments.jsonl and the SQLite DB; tests start from an empty cache."""
    from radar import score

    monkeypatch.setattr(score, "_judg", {})


@pytest.fixture(autouse=True)
def _isolated_seen(monkeypatch, tmp_path_factory):
    """output.write() reads and writes data/seen.jsonl and data/decisions.csv; tests must never touch the real ones."""
    from radar import seen

    d = tmp_path_factory.mktemp("seen_data")  # not under tmp_path: tests use that as a snapshots/registry dir
    monkeypatch.setattr(seen, "LEDGER", d / "seen.jsonl")
    monkeypatch.setattr(seen, "DECISIONS", d / "decisions.csv")
