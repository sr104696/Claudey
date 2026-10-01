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
def _isolated_seen(monkeypatch, tmp_path):
    """output.write() reads and writes data/seen.jsonl and data/decisions.csv; tests must never touch the real ones."""
    from radar import seen

    d = tmp_path / "_seen_data"  # a subdirectory: tests also use tmp_path itself as a snapshots dir
    d.mkdir()
    monkeypatch.setattr(seen, "LEDGER", d / "seen.jsonl")
    monkeypatch.setattr(seen, "DECISIONS", d / "decisions.csv")
