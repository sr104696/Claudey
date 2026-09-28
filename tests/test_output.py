import csv

from helpers import posting

from radar import config, output, score
from radar.models import Posting
from radar.output import _post_key, _row_key, fit_order, near_misses
from radar.score import LAW_FIRM_NONBILLABLE_REASON


def _p(**kw) -> Posting:
    base = dict(key=kw.get("key", "k"), company="Acme", title="Counsel", url="https://x.test/" + kw.get("key", "k"))
    return Posting(**{**base, **kw})


def test_fit_order_thesis_then_pay_then_freshness():
    thesis = _p(key="a", fit_signals=["seat family: legal-AI research/build seat"], fit_score=3)
    rich_old = _p(key="b", fit_score=5, pay_min=200_000, pay_max=250_000, posted_date="2026-08-01")
    rich_new = _p(key="c", fit_score=5, pay_min=200_000, pay_max=250_000, posted_date="2026-09-20", company="Zeta")
    undated = _p(key="d", fit_score=5, pay_min=200_000, pay_max=250_000, company="Aardvark")
    cheap = _p(key="e", fit_score=9, pay_min=120_000, pay_max=140_000)
    got = [p.key for p in sorted([cheap, undated, rich_old, rich_new, thesis], key=fit_order)]
    assert got == ["a", "c", "b", "d", "e"]


def test_near_misses_selection():
    km = _p(key="km", bucket="poor", fit_score=5, poor_reason=f"{LAW_FIRM_NONBILLABLE_REASON}: still a law firm")
    firm = _p(key="firm", bucket="poor", fit_score=6, poor_reason="Law-firm seat (lifestyle)")
    gov = _p(key="gov", bucket="poor", fit_score=6, poor_reason="Government seat (pay ceiling below his target)")
    soft = _p(key="soft", bucket="poor", fit_score=4, poor_reason="Weak fit")
    hard4 = _p(key="hard4", bucket="poor", fit_score=4, hard_exclude_reason="OTE", poor_reason="OTE")
    km_and_pay = _p(key="kmpay", bucket="poor", fit_score=6,
                    poor_reason=f"{LAW_FIRM_NONBILLABLE_REASON}: x; Listed pay tops out below $150K ($120K)")
    fit = _p(key="fit", bucket="fit", fit_score=8)
    got = {p.key for p in near_misses([km, firm, gov, soft, hard4, km_and_pay, fit])}
    assert got == {"km", "soft"}


def test_match_key_identity():
    a = posting(job_id="101", title="Counsel")
    b = posting(job_id="202", title="Counsel")
    assert _post_key(a) != _post_key(b)
    assert _post_key(a) == "greenhouse:acme:101"
    row = {"ats": "greenhouse", "board": "acme", "job_id": "101", "url": "https://elsewhere.test/old", "company": "Acme", "title": "Counsel"}
    assert _row_key(row) == _post_key(a)
    assert _row_key({"ats": "", "job_id": "", "url": "https://u.test/1", "company": "A", "title": "T"}) == "https://u.test/1"
    assert _row_key({"company": "Acme Payments Inc.", "title": "Sr. Counsel"}) == "acmepayments|senior counsel"


def test_write_diff_and_sections(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    snaps = tmp_path / "snapshots"
    snaps.mkdir()
    monkeypatch.setattr(output, "SNAP_DIR", snaps)
    # last run: one req "Counsel" (job 101) on the Acme board
    with open(snaps / "2000-01-01.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=output.CSV_FIELDS)
        w.writeheader()
        w.writerow({"bucket": "fit", "company": "Acme Payments", "title": "Counsel", "url": "https://old-url.test/101",
                    "ats": "greenhouse", "board": "acme", "job_id": "101", "pay_display": "Not listed"})
    posts = [score.score(p) for p in (
        posting(job_id="101", title="Counsel"),                      # same req, URL changed: not new
        posting(job_id="202", title="Counsel"),                      # same title, different req: new
        posting(job_id="303", title="Payments Counsel", location="Jersey City, NJ"),
        posting(job_id="404", title="Credit Counsel", location="Chicago, IL", body=__import__("helpers").BODY + " Salary $300,000 - $400,000 base."),
        posting(job_id="505", title="Risk Counsel", location="Stamford, CT"),
    )]
    summary = output.write(posts, [], {})
    assert summary["closed"] == 0
    with open(tmp_path / "jobs.csv", newline="", encoding="utf-8") as f:
        new = {r["job_id"]: r["is_new"] for r in csv.DictReader(f)}
    assert new["101"] == "0" and new["202"] == "1"
    md = open(summary["open_positions"], encoding="utf-8").read()
    assert "Jersey City, NJ (commutable)" in md
    outside = md.split("## Outside NYC / US-remote")[1]
    assert outside.index("Stamford, CT (Metro-North ~1 hr, hybrid only)") < outside.index("Chicago, IL")


def test_write_reports_gone_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUT", tmp_path)
    snaps = tmp_path / "snapshots"
    snaps.mkdir()
    monkeypatch.setattr(output, "SNAP_DIR", snaps)
    with open(snaps / "2000-01-01.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=output.CSV_FIELDS)
        w.writeheader()
        for jid in ("101", "999"):  # two same-title reqs; only 101 is still open
            w.writerow({"bucket": "fit", "company": "Acme Payments", "title": "Counsel", "url": f"https://boards.greenhouse.io/acme/jobs/{jid}",
                        "ats": "greenhouse", "board": "acme", "job_id": jid})
    summary = output.write([score.score(posting(job_id="101", title="Counsel"))], [], {})
    assert summary["closed"] == 1
    assert "jobs/999" in open(summary["diff"], encoding="utf-8").read()
