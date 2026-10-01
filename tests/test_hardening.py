"""Regression tests for the hardening pass: secret redaction, error isolation, silent-empty channels."""
import json
import warnings

import httpx
import pytest

from radar import config, health, inbox, phase1, robots, runlog, seeds, verify
from radar.discover import hn, official_apis, public_sector, wayback
from radar.http import PoliteClient, Result, redact_text, redact_url


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point data, output and cache directories at a temp dir so nothing touches the repo."""
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(config, "OUT", tmp_path / "out")
    monkeypatch.setattr(config, "CACHE", tmp_path / "cache")
    for d in (config.DATA, config.OUT, config.CACHE):
        d.mkdir(parents=True)
    monkeypatch.setenv("RADAR_RUN_ID", "test-run")
    return tmp_path


def _json(obj, status=200):
    return Result(url="https://example.test", status=status, headers={"content-type": "application/json"},
                  content=json.dumps(obj).encode())


def _err(status, error=None):
    return Result(url="https://example.test", status=status, error=error)


# ------------------------------------------------------------------ 1. secret redaction
def test_redact_url_blanks_credential_values_only():
    u = "https://api.adzuna.com/v1/api/jobs/us/search/1?app_id=12345&app_key=SECRETKEY&what=legal+analyst&page=2"
    out = redact_url(u)
    assert "12345" not in out and "SECRETKEY" not in out
    assert "what=legal+analyst" in out and "page=2" in out
    assert out.startswith("https://api.adzuna.com/v1/api/jobs/us/search/1?app_id=")


@pytest.mark.parametrize("name", ["api_key", "API_KEY", "token", "access_token", "client_secret", "Authorization", "password", "signature", "sig"])
def test_redact_url_param_names(name):
    assert "hunter2" not in redact_url(f"https://x.test/p?a=1&{name}=hunter2&b=2")
    assert "a=1" in redact_url(f"https://x.test/p?a=1&{name}=hunter2&b=2")


def test_redact_url_leaves_plain_urls_alone():
    for u in ("https://x.test/jobs/1", "https://x.test/jobs?category=Legal+Services&page=3", None, ""):
        assert redact_url(u) == u


def test_redact_text_inside_error_message():
    msg = "ConnectError: failed to reach https://serpapi.test/search?api_key=ABC123&q=legal (timeout)"
    out = redact_text(msg)
    assert "ABC123" not in out and "q=legal" in out


def test_http_log_never_writes_the_key(sandbox):
    c = PoliteClient(use_cache=False)
    res = Result(url="https://api.adzuna.com/x?app_id=APPID9&app_key=KEY9&what=counsel", status=200,
                 error="boom https://api.adzuna.com/x?app_key=KEY9")
    c._log(res)
    text = c._log_path.read_text(encoding="utf-8")
    assert "APPID9" not in text and "KEY9" not in text and "what=counsel" in text
    c.close()


def test_result_describe_redacts_url_in_error():
    r = Result(url="u", error="gave up (ReadTimeout: https://x.test/?api_key=K1)")
    assert "K1" not in r.describe()


def test_run_log_redacts_old_log_lines(sandbox):
    rec = {"ts": "2026-10-01T00:00:00", "channel": "c", "method": "GET", "url": "https://x.test/?app_key=LEAK1&q=a",
           "status": 200, "cache": False, "ms": 1, "error": None, "blocked": None}
    (config.run_dir() / "http-1.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    path = runlog.write_run_log()
    assert "LEAK1" not in open(path, encoding="utf-8").read()


# ------------------------------------------------------------------ 2. verify_url / phase1 isolation
def test_verify_url_turns_json_decode_error_into_unverified(monkeypatch):
    def boom(*a, **k):
        raise json.JSONDecodeError("Expecting value", "<html>maintenance</html>", 0)

    monkeypatch.setattr(verify.greenhouse, "verify", boom)
    o = verify.verify_url("https://boards.greenhouse.io/acme/jobs/123", "Acme")
    assert o.status == "unverified" and o.method == "error" and "JSONDecodeError" in o.evidence


@pytest.mark.parametrize("exc", [KeyError("id"), TypeError("x"), httpx.ConnectError("down"), ValueError("bad")])
def test_verify_url_other_adapter_errors(monkeypatch, exc):
    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(verify.greenhouse, "verify", boom)
    assert verify.verify_url("https://boards.greenhouse.io/acme/jobs/123", "Acme").status == "unverified"


def test_verify_seeds_isolates_a_bad_row(monkeypatch):
    rows = [seeds.SeedRow("fit", "Bad Row", "https://bad.example/1", "BadCo", "NYC", ""),
            seeds.SeedRow("fit", "Good Row", "https://good.example/1", "GoodCo", "NYC", "")]
    monkeypatch.setattr(phase1, "parse_current_list", lambda: (rows, []))
    monkeypatch.setattr(phase1, "load_watchlist", lambda: [])
    monkeypatch.setattr(phase1, "_save", lambda *a: None)
    recorded = {}
    monkeypatch.setattr(phase1, "record_channel", lambda name, **kw: recorded.update(kw))

    def fake_verify(url, company, source="verify"):
        if "bad" in url:
            raise ValueError("Expecting value")
        return verify.Outcome("closed", None, "gone", "page")

    monkeypatch.setattr(phase1, "verify_url", fake_verify)
    results, _ = phase1.verify_seeds()
    assert [r.status for r in results] == ["unverified", "closed"]
    assert "crashed" in results[0].evidence and "Expecting value" in results[0].evidence
    assert any("BadCo" in f for f in recorded["failures"])


# ------------------------------------------------------------------ 3. robots.txt transient statuses
@pytest.mark.parametrize("status", [408, 425, 429, 500, 503])
def test_robots_transient_status_is_error_not_allow_all(sandbox, monkeypatch, status):
    c = PoliteClient(use_cache=False)
    calls = []

    def fake_raw(method, url, body, headers, delay):
        calls.append(url)
        return Result(url=url, status=status)

    monkeypatch.setattr(c, "_raw", fake_raw)
    rules = c.robots_for("https://careers.example/jobs/1")
    assert rules.state == "error" and not rules.allowed("https://careers.example/jobs/1")
    c.robots_for("https://careers.example/jobs/2")  # inside the 10-minute window: no refetch
    assert len(calls) == 1
    c.close()


@pytest.mark.parametrize("status", [404, 410, 403])
def test_robots_other_4xx_still_allow_all(sandbox, monkeypatch, status):
    c = PoliteClient(use_cache=False)
    monkeypatch.setattr(c, "_raw", lambda m, u, b, h, delay: Result(url=u, status=status))
    rules = c.robots_for("https://careers.example/jobs/1")
    assert rules.state == "missing" and rules.allowed("https://careers.example/jobs/1")
    c.close()


# ------------------------------------------------------------------ 4. Crawl-delay parsing
@pytest.mark.parametrize("val", ["1.2.3", ".", "abc", "nan", "-5", ""])
def test_crawl_delay_malformed_is_ignored(val):
    r = robots.parse(f"User-agent: *\nCrawl-delay: {val}\nDisallow: /x\n", "JobRadar")
    assert r.crawl_delay is None and r.disallow == ["/x"]


@pytest.mark.parametrize("val", ["inf", "1e999", "9999", "31"])
def test_crawl_delay_clamped(val):
    r = robots.parse(f"User-agent: *\nCrawl-delay: {val}\n", "JobRadar")
    assert r.crawl_delay == robots.MAX_CRAWL_DELAY == 30.0


def test_crawl_delay_valid_and_fallback_before_user_agent():
    assert robots.parse("User-agent: *\nCrawl-delay: 2.5\n", "JobRadar").crawl_delay == 2.5
    assert robots.parse("Crawl-delay: 4\nUser-agent: other\nDisallow: /\n", "JobRadar").crawl_delay == 4.0
    assert robots.parse("Crawl-delay: 1.2.3\nUser-agent: other\nDisallow: /\n", "JobRadar").crawl_delay is None


# ------------------------------------------------------------------ 5. silence alarm against last healthy run
def _row(run, source="board:Acme", status="ok", cands=5):
    return {"run": run, "source": source, "kind": "board", "status": status, "queried": 1, "candidates": str(cands),
            "verified": "", "kept": ""}


def test_quiet_alert_repeats_with_streak():
    old = [_row("2026-09-01", cands=7), _row("2026-09-08", cands=0), _row("2026-09-15", cands=0)]
    alerts = health.silence_alerts(old, [_row("2026-09-22", cands=0)])
    assert len(alerts) == 1
    a = alerts[0]
    assert a.startswith("**went quiet**: `board:Acme` had 7") and "2026-09-01" in a and "and 0 now" in a
    assert "3 consecutive runs" in a


def test_quiet_alert_keeps_original_shape_for_one_run():
    alerts = health.silence_alerts([_row("2026-09-01", cands=7)], [_row("2026-09-08", cands=0)])
    assert alerts == ["**went quiet**: `board:Acme` had 7 last run (2026-09-01) and 0 now"]


def test_never_productive_source_does_not_alert():
    old = [_row("2026-09-01", cands=0), _row("2026-09-08", cands=0)]
    assert health.silence_alerts(old, [_row("2026-09-15", cands=0)]) == []


def test_degraded_streak_against_last_ok_run():
    old = [_row("2026-09-01", status="ok"), _row("2026-09-08", status="failures"), _row("2026-09-15", status="failures")]
    alerts = health.silence_alerts(old, [_row("2026-09-22", status="failures")])
    assert alerts == ["**degraded**: `board:Acme` was ok in its last healthy run (2026-09-01), now `failures` (3 consecutive runs not ok)"]
    one = health.silence_alerts([_row("2026-09-01", status="ok")], [_row("2026-09-08", status="failures")])
    assert one == ["**degraded**: `board:Acme` was ok last run, now `failures`"]


def test_recovered_source_is_silent_and_crash_still_alerts():
    old = [_row("2026-09-01", cands=7), _row("2026-09-08", cands=0)]
    assert health.silence_alerts(old, [_row("2026-09-15", cands=4)]) == []
    assert health.silence_alerts(old, [_row("2026-09-15", status="crashed", cands=0)])[0].startswith("**crashed**")


# ------------------------------------------------------------------ 6. inbox
def _anchor(href, text):
    return f'<p><a href="{href}">{text}</a><br>Acme Corp<br>New York, NY</p>'


def test_inbox_keeps_titles_containing_manage_or_help_but_drops_ui_links(tmp_path):
    keep = ["Credit Risk Manager", "Legal Operations Management", "Helpdesk Counsel", "Manager, Regulatory Counsel"]
    drop = ["Manage alerts", "Manage your preferences", "Help Center", "Unsubscribe", "Help", "Need help?"]
    body = "<html><body>" + "".join(_anchor(f"https://jobs.example/{i}", t) for i, t in enumerate(keep + drop)) + "</body></html>"
    f = tmp_path / "alert.html"
    f.write_text(body, encoding="utf-8")
    titles = [l.title for l in inbox.parse(f)]
    assert titles == keep


def test_import_inbox_skips_one_malformed_file(tmp_path, monkeypatch):
    monkeypatch.setattr(inbox, "INBOX", tmp_path)
    (tmp_path / "good.html").write_text(_anchor("https://jobs.example/1", "Regulatory Counsel"), encoding="utf-8")
    (tmp_path / "bad.eml").write_bytes(b"\xff\xfe garbage")
    real = inbox._html_of

    def flaky(path):
        if path.name == "bad.eml":
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad")
        return real(path)

    monkeypatch.setattr(inbox, "_html_of", flaky)
    got = []
    monkeypatch.setattr(inbox, "add_leads", lambda leads: got.extend(leads) or len(leads))
    with pytest.warns(UserWarning, match="bad.eml"):
        out = inbox.import_inbox()
    assert out["files"] == 2 and out["leads_added"] == 1 and out["files_skipped"] == ["bad.eml"]
    assert [l.title for l in got] == ["Regulatory Counsel"]


# ------------------------------------------------------------------ 7. seeds parsing
_LIST = """# List

## Postings that fit your profile

| Title | Company | Location | Pay |
|---|---|---|---|
| [Counsel](https://a.example/1) | Acme | New York | $200K |
| [Short row](https://a.example/2) | Acme |
| [Analyst](https://a.example/3) | Beta | Remote | $150K |

## Also open, but a poor match

| Title | Company | Location | Pay | Reason |
|---|---|---|---|---|
| [Sales](https://a.example/4) | Gamma | NYC | OTE | OTE pay |
"""


def test_parse_current_list_skips_short_rows_individually(tmp_path):
    p = tmp_path / "list.md"
    p.write_text(_LIST, encoding="utf-8")
    with pytest.warns(UserWarning, match="malformed row"):
        rows, closed = seeds.parse_current_list(p)
    assert [r.title for r in rows] == ["Counsel", "Analyst", "Sales"]
    assert rows[2].reason == "OTE pay"


def test_parse_current_list_raises_when_headings_renamed(tmp_path):
    p = tmp_path / "list.md"
    p.write_text(_LIST.replace("Postings that fit your profile", "Best postings").replace("Also open, but a poor match", "Others"), encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(ValueError, match="recognised"):
            seeds.parse_current_list(p)


def test_parse_current_list_genuinely_empty_is_ok(tmp_path):
    p = tmp_path / "list.md"
    p.write_text("# List\n\n## Postings that fit your profile\n\nNone this week.\n", encoding="utf-8")
    assert seeds.parse_current_list(p) == ([], [])


# ------------------------------------------------------------------ 8. silent-empty channels record failures
class FakeClient:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, **kw):
        self.calls.append((url, kw.get("params")))
        return self.handler(url, kw.get("params") or {})


def _capture(monkeypatch, module):
    got = {}
    monkeypatch.setattr(module, "record_channel", lambda name, **kw: got.update(kw, name=name))
    return got


def test_hn_non_ok_search_is_a_failure(monkeypatch):
    got = _capture(monkeypatch, hn)
    monkeypatch.setattr(hn, "add_leads", lambda leads: 0)
    monkeypatch.setattr(hn, "client", lambda: FakeClient(lambda u, p: _err(503, "gave up after 4 attempts (HTTP 503)")))
    hn.run()
    assert any("thread search" in f and "503" in f for f in got["failures"])


def test_hn_zero_threads_found_is_a_failure(monkeypatch):
    got = _capture(monkeypatch, hn)
    monkeypatch.setattr(hn, "add_leads", lambda leads: 0)
    monkeypatch.setattr(hn, "client", lambda: FakeClient(lambda u, p: _json({"hits": [{"title": "Something else", "objectID": "1"}]})))
    hn.run()
    assert any("no 'Ask HN: Who is hiring'" in f for f in got["failures"])


def test_hn_healthy_run_has_no_failures(monkeypatch):
    got = _capture(monkeypatch, hn)
    monkeypatch.setattr(hn, "add_leads", lambda leads: 0)

    def handler(url, params):
        if "search_by_date" in url:
            return _json({"hits": [{"title": "Ask HN: Who is hiring? (October 2026)", "objectID": "9"}]})
        return _json({"children": []})

    monkeypatch.setattr(hn, "client", lambda: FakeClient(handler))
    hn.run()
    assert got["failures"] == []


def test_adzuna_non_ok_is_a_failure(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    monkeypatch.setattr(official_apis, "client", lambda: FakeClient(lambda u, p: _err(401)))
    stats = {"queried": 0, "failures": [], "skipped": []}
    assert official_apis._adzuna(stats) == []
    assert len(stats["failures"]) == 5 and all(f.startswith("adzuna ") for f in stats["failures"])


def test_usajobs_and_serpapi_adapters_are_gone():
    assert not hasattr(official_apis, "_usajobs") and not hasattr(official_apis, "_serpapi")


def test_public_sector_workday_list_status_goes_to_failures(monkeypatch):
    html = '<a href="https://nyfed.wd5.myworkdayjobs.com/en-US/FRBNY_Careers/job/x">x</a>'
    monkeypatch.setattr(public_sector, "client", lambda: FakeClient(lambda u, p: Result(url=u, status=200, content=html.encode())))
    monkeypatch.setattr(public_sector.workday, "list_jobs", lambda spec, **kw: ("HTTP 500", []))
    stats = {"queried": 0, "failures": [], "skipped": [], "notes": []}
    public_sector._workday_portal("NY Fed", "https://www.newyorkfed.org/careers", stats)
    assert any("NY Fed" in f and "HTTP 500" in f for f in stats["failures"])


def _cdx(n, prefix):
    return [["timestamp", "original"]] + [[f"2024{(i % 12) + 1:02d}01000000", f"https://{prefix}/jobs/{i}"] for i in range(n)]


def _wb_handler(rows_by_pattern):
    def handler(url, params):
        if "cdx/search" in url:
            return _json(rows_by_pattern[params["url"]]) if params["url"] in rows_by_pattern else _err(503, "gave up")
        return Result(url=url, status=200, content=b"<title>Legal Analyst</title>")

    return handler


def test_wayback_failed_page_fetches_are_recorded(sandbox, monkeypatch):
    got = _capture(monkeypatch, wayback)
    monkeypatch.setattr(wayback, "TARGETS", [("A", "a.test/jobs/*", "page")])
    r403 = lambda u, p: _json(_cdx(3, "a.test")) if "cdx/search" in u else Result(url=u, blocked="robots", error="disallowed by robots.txt")
    monkeypatch.setattr(wayback, "client", lambda: FakeClient(r403))
    wayback.run()
    assert any("3 of 3 capture fetches failed" in f and "robots" in f for f in got["failures"])


# ------------------------------------------------------------------ 9. wayback budgeting and report safety
def test_wayback_budget_is_per_target_not_global(sandbox, monkeypatch):
    got = _capture(monkeypatch, wayback)
    monkeypatch.setattr(wayback, "TARGETS", [("A", "a.test/jobs/*", "page"), ("B", "b.test/jobs/*", "page"), ("C", "c.test/jobs/*", "page")])
    monkeypatch.setattr(wayback, "MAX_PAGE_FETCHES", 9)
    rows = {"a.test/jobs/*": _cdx(20, "a.test"), "b.test/jobs/*": _cdx(20, "b.test"), "c.test/jobs/*": _cdx(2, "c.test")}
    fake = FakeClient(_wb_handler(rows))
    monkeypatch.setattr(wayback, "client", lambda: fake)
    out = wayback.run()
    page_urls = [u for u, _ in fake.calls if "cdx/search" not in u]
    per = {h: sum(f"/{h}.test/" in u for u in page_urls) for h in "abc"}
    assert per["a"] == per["b"] == 3 and per["c"] == 2  # 9 // 3 = 3 per target; c only has 2 captures
    assert len(page_urls) <= 9
    assert any("a.test" in t and "budget" in t for t in out["truncated"]) and "truncated" in got["notes"]
    assert "Truncated" in (config.OUT / "recurrence.md").read_text(encoding="utf-8")


def test_wayback_cdx_limit_truncation_is_noted(sandbox, monkeypatch):
    _capture(monkeypatch, wayback)
    monkeypatch.setattr(wayback, "TARGETS", [("Burford", "b.test/job/*", "url")])
    monkeypatch.setattr(wayback, "CDX_LIMIT", 5)
    fake = FakeClient(_wb_handler({"b.test/job/*": _cdx(5, "b.test")}))
    monkeypatch.setattr(wayback, "client", lambda: fake)
    assert any("CDX limit 5" in t for t in wayback.run()["truncated"])


def test_wayback_does_not_overwrite_report_when_every_target_failed(sandbox, monkeypatch):
    got = _capture(monkeypatch, wayback)
    report = config.OUT / "recurrence.md"
    report.write_text("LAST GOOD REPORT\n", encoding="utf-8")
    monkeypatch.setattr(wayback, "TARGETS", [("A", "a.test/*", "page"), ("B", "b.test/*", "url")])
    monkeypatch.setattr(wayback, "client", lambda: FakeClient(_wb_handler({})))
    out = wayback.run()
    assert report.read_text(encoding="utf-8") == "LAST GOOD REPORT\n"
    assert out["report_written"] is False and len(got["failures"]) == 2


# ------------------------------------------------------------------ 11. channels.jsonl torn line
def test_load_channels_skips_torn_lines(sandbox):
    runlog.record_channel("discover:hn", queried=1, candidates=2)
    with open(config.run_dir() / "channels.jsonl", "a", encoding="utf-8") as f:
        f.write('{"channel": "discover:feeds", "quer\n')
        f.write('"not an object"\n')
        f.write('{"no_channel_key": 1}\n')
    runlog.record_channel("discover:wayback", queried=3)
    chans = runlog.load_channels()
    assert set(chans) == {"discover:hn", "discover:wayback"}


def test_commoncrawl_dead_board_is_remembered_not_requested_every_run(tmp_path, monkeypatch):
    import json

    from radar import config
    from radar.discover import commoncrawl

    monkeypatch.setattr(config, "today", lambda: "2026-10-01")
    monkeypatch.setattr(commoncrawl, "STATE", tmp_path / "cc.json")
    monkeypatch.setattr(commoncrawl, "BOARDS_CSV", tmp_path / "boards.csv")
    monkeypatch.setattr(commoncrawl, "_crawls", lambda: ["api"])
    monkeypatch.setattr(commoncrawl, "_tokens", lambda api, pat, failures: ({"deadco", "liveco"}, 1))
    monkeypatch.setattr(commoncrawl, "add_leads", lambda leads: len(leads))
    monkeypatch.setattr(commoncrawl, "record_channel", lambda *a, **k: None)
    asked: list[str] = []

    def pull(tok, *_):
        asked.append(tok)
        return ("board not found", []) if tok == "deadco" else ("ok", [])

    monkeypatch.setattr(commoncrawl, "PULL", {a: pull for a in commoncrawl.PATTERNS})
    commoncrawl.run()
    state = json.loads((tmp_path / "cc.json").read_text())
    assert state["greenhouse"]["deadco"]["dead"] is True and state["greenhouse"]["deadco"]["last_checked"] == "2026-10-01"
    asked.clear()
    commoncrawl.run()  # same day, then a later day inside the recheck window: neither board is asked for again
    monkeypatch.setattr(config, "today", lambda: "2026-10-05")
    commoncrawl.run()
    assert asked == []
