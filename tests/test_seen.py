import csv

from helpers import posting

from radar import output, seen


def _snap(dir_, day, rows):
    dir_.mkdir(exist_ok=True)
    with open(dir_ / f"{day}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=output.CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _row(job_id, bucket="fit", **kw):
    return {"bucket": bucket, "company": "Acme Payments", "title": "Counsel", "url": f"https://boards.greenhouse.io/acme/jobs/{job_id}",
            "ats": "greenhouse", "board": "acme", "job_id": job_id, **kw}


def test_bootstrap_marks_earlier_snapshot_rows_seen(tmp_path):
    _snap(tmp_path / "snaps", "2026-09-27", [_row("101"), _row("202", "poor"), _row("303", "outside", poor_reason="weak")])
    led = seen.Ledger.load("2026-09-29", tmp_path / "snaps", tmp_path / "out", tmp_path / "seen.jsonl")
    assert led.seen(posting(job_id="101"), "fit")
    assert led.seen(posting(job_id="101"), "poor")  # shown as a fit, so also covers the lower surfaces
    assert not led.seen(posting(job_id="999"), "fit")
    # a poor-match row was listed in the poor table but never as a fit, and never asked about in the digest
    p202 = posting(job_id="202")
    assert led.seen(p202, "poor") and not led.seen(p202, "fit") and not led.seen(p202, "near_miss")
    # weaker out-of-area rows were never listed anywhere
    assert not led.seen(posting(job_id="303"), "outside")


def test_same_day_rerun_does_not_hide_its_own_rows(tmp_path):
    led = seen.Ledger.load("2026-09-29", tmp_path / "snaps", tmp_path / "out", tmp_path / "seen.jsonl")
    p = posting(job_id="101")
    assert not led.seen(p, "fit")
    led.present(p, "fit")
    led.save()
    again = seen.Ledger.load("2026-09-29", tmp_path / "snaps", tmp_path / "out", tmp_path / "seen.jsonl")
    assert not again.seen(p, "fit")  # still new: only EARLIER runs count
    again.present(p, "fit")
    again.save()
    assert len((tmp_path / "seen.jsonl").read_text().splitlines()) == 1  # re-running replaced, not duplicated
    tomorrow = seen.Ledger.load("2026-09-30", tmp_path / "snaps", tmp_path / "out", tmp_path / "seen.jsonl")
    assert tomorrow.seen(p, "fit")


def test_near_miss_that_becomes_a_fit_is_new_again(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "near_miss_2026-09-27.md").write_text("| 1 | [Counsel](https://boards.greenhouse.io/acme/jobs/101) | Acme |\n", encoding="utf-8")
    led = seen.Ledger.load("2026-09-29", tmp_path / "snaps", out, tmp_path / "seen.jsonl")
    p = posting(job_id="101")
    assert led.seen(p, "near_miss") and not led.seen(p, "fit")


def test_repost_with_new_job_id_and_same_text_stays_seen(tmp_path):
    led = seen.Ledger.load("2026-09-29", tmp_path / "snaps", tmp_path / "out", tmp_path / "seen.jsonl")
    old = posting(job_id="101")
    led.present(old, "fit")
    led.save()
    led = seen.Ledger.load("2026-09-30", tmp_path / "snaps", tmp_path / "out", tmp_path / "seen.jsonl")
    repost = posting(job_id="777")  # new id and url, identical text
    assert led.seen(repost, "fit")
    different = posting(job_id="778", body="A different role entirely, about tax.")
    assert not led.seen(different, "fit")


def test_torn_ledger_line_is_skipped(tmp_path):
    path = tmp_path / "seen.jsonl"
    path.write_text('{"ids": ["greenhouse:acme:101"], "s": "fit", "run": "2026-09-27"}\n{"ids": [\n', encoding="utf-8")
    led = seen.Ledger.load("2026-09-29", tmp_path / "snaps", tmp_path / "out", path)
    assert led.seen(posting(job_id="101"), "fit")


def test_decisions_by_url_key_or_name(tmp_path):
    path = tmp_path / "decisions.csv"
    seen.record_decision("https://boards.greenhouse.io/acme/jobs/101#x", "applied", path=path)
    seen.record_decision("greenhouse:acme:202", "dismissed", path=path)
    seen.record_decision("Acme Payments Inc.|Sr. Counsel", "right_call", path=path)
    d = seen.Decisions.load(path)
    assert d.for_posting(posting(job_id="101")) == "applied"
    assert d.for_posting(posting(job_id="202")) == "dismissed"
    assert d.for_posting(posting(job_id="303", title="Senior Counsel")) == "right_call"
    assert d.for_posting(posting(job_id="404", title="Tax Counsel")) == ""
    assert d.for_row({"company": "Acme", "title": "Counsel", "url": "https://boards.greenhouse.io/acme/jobs/101"}) == "applied"


def test_record_decision_rejects_unknown_value(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        seen.record_decision("x", "maybe", path=tmp_path / "d.csv")
