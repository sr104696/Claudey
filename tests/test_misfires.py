"""Regression cases for scoring misfires found by the fixture review (IDs match the review notes)."""
import json
import time

from helpers import BODY, posting

from radar import score
from radar.extract import classify_location, pay_from_text, years_mentions


# 1. firm-history sentences are not years-of-experience asks
def test_a14_firm_history_in_our_years_is_not_an_ask():
    p = score.score(posting(body=BODY + " In our 20 years of experience advising broker-dealers, we have seen it all."))
    assert not p.hard_exclude_reason, p.hard_exclude_reason
    assert p.bucket == "fit", p.poor_reason


def test_a15_sentence_initial_over_n_years_the_firm_has_grown():
    text = "Over 10 years, the firm has grown to 200 people. Our partners bring 15 years of combined experience."
    assert years_mentions(text) == []
    assert not score.score(posting(body=BODY + " " + text)).hard_exclude_reason


def test_real_years_asks_still_read():
    los = [y.lo for y in years_mentions("You have over 5 years of experience in litigation. 10+ years of legal "
                                        "experience. Minimum of 7 years of practice.")]
    assert los == [5, 10, 7]


# 2. New York City agencies are government
def test_b9_nyc_law_department_is_government():
    for company in ("New York City Law Department", "NYC Office of the Corporation Counsel",
                    "New York City Department of Finance"):
        assert score.score(posting(company=company)).poor_reason.startswith("Government seat"), company
    for company in ("FINRA", "Federal Reserve Bank of New York"):
        assert "Government seat" not in score.score(posting(company=company)).poor_reason, company


# 3. research/analyst carve-out applies only to LLP-named funds, not firms detected from text
def test_c6_text_detected_firm_with_research_title_stays_law_firm():
    firm_body = BODY + " Our attorneys bill 1,900 billable hours a year at an Am Law 100 firm."
    p = score.score(posting(company="Smith Jones", title="Legal Research Attorney", body=firm_body))
    assert p.poor_reason.startswith(score.LAW_FIRM_NONBILLABLE_REASON), p.poor_reason
    p = score.score(posting(company="Smith Jones", title="Litigation Analyst", body=firm_body))
    assert "Law-firm seat (lifestyle)" in p.poor_reason
    # an LLP-named fund keeps the carve-out, but not when the posting text says it is a firm
    assert "Law-firm seat" not in score.score(posting(company="Longford Capital Fund LLP", title="Research Analyst")).poor_reason
    p = score.score(posting(company="Longford Capital Fund LLP", title="Research Analyst", body=firm_body))
    assert "Law-firm seat (lifestyle)" in p.poor_reason


# 4. negated mentions don't fire
def test_c7_negated_billable_hours_is_not_a_law_firm():
    p = score.score(posting(body=BODY + " Unlike firm roles, we do not track billable hours."))
    assert "Law-firm" not in p.poor_reason and p.bucket == "fit", p.poor_reason


def test_d12_not_a_contract_position():
    p = score.score(posting(body=BODY + " This is a permanent, full-time role, not a contract position."))
    assert "Contract" not in p.poor_reason and p.bucket == "fit", p.poor_reason
    p = score.score(posting(body=BODY + " This is a contract position for six months."))
    assert "Contract, hourly or part-time" in p.poor_reason


# 5. a lone hourly figure is pay
def test_d6_single_hourly_figure():
    pay = pay_from_text("Compensation: $60 per hour, paid weekly.")
    assert (pay.min, pay.max, pay.period, pay.type) == (60, 60, "hour", "hourly")
    pay = pay_from_text("The stipend is $9,500/month.")
    assert (pay.min, pay.period) == (9500, "month")
    p = score.score(posting(body=BODY + " The rate is $60 per hour."))
    assert p.pay_type == "hourly" and "Contract, hourly or part-time" in p.poor_reason


# 6. monthly and hourly pay are annualized for the floor and the midpoint signal
def test_d7_monthly_pay_annualized():
    p = score.score(posting(body=BODY + " Salary: $9,500–$11,500 per month."))
    assert p.pay_period == "month"
    assert "Listed pay tops out below $150K" in p.poor_reason
    assert "base pay midpoint ≥ $150K" not in p.fit_signals
    p = score.score(posting(body=BODY + " Salary: $14,000–$16,000 per month."))
    assert "Listed pay" not in p.poor_reason
    assert "base pay midpoint ≥ $150K" in p.fit_signals


# 7. Manhattan Beach is California
def test_e10_manhattan_beach_is_not_nyc():
    assert classify_location("Manhattan Beach, CA") == "us_other"
    assert classify_location("Manhattan, KS") == "us_other"
    assert classify_location("Manhattan, NY") == "nyc"
    assert classify_location("New York, NY") == "nyc"
    assert score.score(posting(location="Manhattan Beach, CA")).bucket == "outside"


# 8. phase4 keeps the ATS country when it recomputes the location bucket
def test_country_kept_through_phase4_recompute(monkeypatch):
    from radar import phase4

    p = posting(location="Head Office", country="GB")
    assert p.country == "GB" and p.loc_bucket == "non_us"
    monkeypatch.setattr(phase4, "gather", lambda verify_leads: ([p], {}))
    monkeypatch.setattr(phase4, "relevance", lambda *a: (True, "test"))
    monkeypatch.setattr(phase4.db, "upsert_posting", lambda p: None)
    posts, _ = phase4.run()
    assert p.loc_bucket == "non_us"
    assert posts == []


# 9. one malformed JSONL row doesn't abort import-leads
def test_import_leads_skips_bad_rows(tmp_path, monkeypatch, capsys):
    import radar.leads
    from radar.__main__ import main

    got = []
    monkeypatch.setattr(radar.leads, "add_leads", lambda leads: got.extend(leads) or len(leads))
    f = tmp_path / "leads.jsonl"
    f.write_text("\n".join([
        json.dumps({"source": "web", "url": "https://a.test/1", "title": "Counsel"}),
        "{not json",
        json.dumps(["a list"]),
        json.dumps({"source": "web"}),  # missing url
        json.dumps({"source": "web", "url": "https://a.test/2"}),
    ]) + "\n", encoding="utf-8")
    assert main(["import-leads", str(f)]) == 0
    assert [l.url for l in got] == ["https://a.test/1", "https://a.test/2"]
    err = capsys.readouterr().err
    assert err.count("skipped malformed lead") == 3 and ":2:" in err


# 10. an HTML 200 from the CDX API is a failure entry, not a crash
def test_wayback_non_json_cdx_is_recorded(tmp_path, monkeypatch):
    from radar import config
    from radar.discover import wayback
    from radar.http import Result

    class Fake:
        def get(self, url, **kw):
            return Result(url=url, status=200, headers={"content-type": "text/html"}, content=b"<html>slow down</html>")

    monkeypatch.setattr(wayback, "client", lambda: Fake())
    monkeypatch.setattr(wayback, "TARGETS", [("Octus", "boards.greenhouse.io/octus/jobs/*", "page")])
    monkeypatch.setattr(wayback, "record_channel", lambda *a, **kw: None)
    monkeypatch.setattr(config, "OUT", tmp_path)
    out = wayback.run()
    assert len(out["failures"]) == 1 and "not JSON" in out["failures"][0]


# http: 404/410 are not cached except for robots.txt
def test_http_does_not_cache_404_except_robots(tmp_path, monkeypatch):
    from radar import config
    from radar.http import PoliteClient, Result

    monkeypatch.setattr(config, "CACHE", tmp_path)
    c = PoliteClient()
    for status in (404, 410):
        job = "https://x.test/jobs/1"
        path = c._cache_path("GET", job, None)
        c._cache_put(path, Result(url=job, status=status, content=b"gone"))
        assert not path.exists() and c._cache_get(path) is None
    robots_url = "https://x.test/robots.txt"
    rpath = c._cache_path("GET", robots_url, None)
    c._cache_put(rpath, Result(url=robots_url, status=404))
    assert c._cache_get(rpath).status == 404
    ok = c._cache_path("GET", "https://x.test/jobs/2", None)
    c._cache_put(ok, Result(url="https://x.test/jobs/2", status=200, content=b"ok"))
    assert c._cache_get(ok).status == 200
    # a 404 cached by an older version is ignored rather than served
    stale = c._cache_path("GET", "https://x.test/jobs/3", None)
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text(json.dumps({"url": "https://x.test/jobs/3", "status": 404, "fetched_at": time.time(),
                                 "body_b64": ""}), encoding="utf-8")
    assert c._cache_get(stale) is None
