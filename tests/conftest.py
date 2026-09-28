import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _no_judgment_db(monkeypatch):
    """score.judgments() would read data/judgments.jsonl and the SQLite DB; tests start from an empty cache."""
    from radar import score

    monkeypatch.setattr(score, "_judg", {})
