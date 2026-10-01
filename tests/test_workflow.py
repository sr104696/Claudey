from pathlib import Path

from radar import pipeline

WORKFLOW = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "refresh.yml").read_text(encoding="utf-8")


def test_skipping_commoncrawl_keeps_every_other_channel():
    # a hard-coded channel list once dropped rlegaltech from skip_commoncrawl runs without any alert
    assert "refresh --skip commoncrawl" in WORKFLOW and "--channels" not in WORKFLOW
    assert "commoncrawl" in pipeline.CHANNELS and "rlegaltech" in pipeline.CHANNELS


def test_every_data_file_the_run_writes_is_committed():
    for f in ("data/seen.jsonl", "data/decisions.csv", "data/judgments.jsonl", "data/leads.jsonl", "data/snapshots/", "out/"):
        assert f in WORKFLOW, f
    assert "data/judgments/**" in WORKFLOW  # diagnostics keep the batches if the push fails


def test_failed_rebase_is_aborted_before_retrying():
    assert "git rebase --abort" in WORKFLOW
