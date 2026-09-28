import datetime as dt
import json

from helpers import posting

from radar import phase4
from radar.leads import read_recent_leads
from radar.robots import Rules


def test_apply_judgments_skips_results_without_hash(tmp_path, monkeypatch, capsys):
    pending, results, out = tmp_path / "pending", tmp_path / "results", tmp_path / "judgments.jsonl"
    pending.mkdir()
    results.mkdir()
    monkeypatch.setattr(phase4, "PENDING", pending)
    monkeypatch.setattr(phase4, "RESULTS", results)
    monkeypatch.setattr(phase4, "JUDGMENTS", out)
    (pending / "batch_01.json").write_text(json.dumps([{"key": "k-pending", "desc_hash": "h1"}]), encoding="utf-8")
    (results / "r1.json").write_text(json.dumps([
        {"key": "k-pending", "meets_floor": "Y"},             # hash from the pending batch
        {"key": "k-own", "desc_hash": "h2", "meets_floor": "N"},  # hash in the result itself
        {"key": "k-orphan", "meets_floor": "Y"},              # no hash anywhere: skipped
    ]), encoding="utf-8")
    assert phase4.apply_judgments() == 2
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert {r["key"]: r["desc_hash"] for r in rows} == {"k-pending": "h1", "k-own": "h2"}
    assert "k-orphan" in capsys.readouterr().err
    assert not list(results.glob("*.json"))


def test_lead_window(tmp_path):
    path = tmp_path / "leads.jsonl"
    today = dt.date(2026, 9, 28)
    d = lambda n: (today - dt.timedelta(days=n)).isoformat()
    rows = [
        {"source": "hn", "url": "https://a.test/1", "run": d(8), "title": "too old"},
        {"source": "hn", "url": "https://a.test/2", "run": d(6), "title": "in window"},
        {"source": "hn", "url": "https://a.test/3", "run": d(3), "title": "older copy"},
        {"source": "feeds", "url": "https://a.test/3", "run": d(0), "title": "newest copy"},
        {"source": "hn", "url": "https://a.test/4", "run": d(0), "title": "today"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8")
    got = {l["url"]: l["title"] for l in read_recent_leads(today.isoformat(), 7, path)}
    assert got == {"https://a.test/2": "in window", "https://a.test/3": "newest copy", "https://a.test/4": "today"}


def test_registry_segment_for_lead_postings():
    p = posting(company="Acme Payments", ats="lever", board="acmepay")
    segs = {("lever", "acmepay"): "payments", "acmepayments": "other"}
    assert phase4.registry_segment(p, segs) == "payments"
    assert phase4.registry_segment(posting(company="Acme Payments", ats="page", board="x"), {"acmepayments": "fintech"}) == "fintech"
    assert phase4.registry_segment(posting(company="Unlisted Co"), {}) is None


def test_robots_percent_encoded_star_is_literal():
    r = Rules(disallow=["/a%2Ab"])
    assert not r.allowed("https://x.test/a*b")
    assert r.allowed("https://x.test/aXYZb")
    wild = Rules(disallow=["/a*b"])
    assert not wild.allowed("https://x.test/aXYZb")


def test_watchlist_resolve_is_exact_name():
    from radar.phase1 import _resolve_entry
    from radar.seeds import Watch

    watch = [Watch("a", "Citi", "workday", "", "", kind="resolve"), Watch("b", "Citadel Securities", "none", "", "", kind="resolve"),
             Watch("c", "Citadel Securities LLC", "none", "", "", kind="resolve")]
    assert _resolve_entry(watch, "Citadel") is None
    assert _resolve_entry(watch, "Citi").label == "a"
    assert _resolve_entry(watch, "Citadel Securities").label == "c"  # longest of the equal names


def test_raw_json_truncation_stays_valid():
    from radar.db import RAW_MAX, _raw_json

    assert json.loads(_raw_json({"a": 1})) == {"a": 1}
    big = json.loads(_raw_json({"x": "y" * (RAW_MAX + 10)}))
    assert big["_truncated"] is True and big["original_size"] > RAW_MAX


def test_cache_served_for_blocked_host(monkeypatch):
    from radar.http import PoliteClient, Result

    c = PoliteClient()
    monkeypatch.setattr(c, "_log", lambda res, **kw: None)
    cached = Result(url="https://x.test/job", status=200, content=b"ok", from_cache=True)
    monkeypatch.setattr(c, "_cache_get", lambda path: cached)
    c._blocked_hosts["x.test"] = "bot wall"
    assert c._one("GET", "https://x.test/job", None, {}, None, True) is cached
    monkeypatch.setattr(c, "_cache_get", lambda path: None)
    assert c._one("GET", "https://x.test/job", None, {}, None, True).blocked == "host-blocked"
