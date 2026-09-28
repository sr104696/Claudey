import json

from radar import phase2
from radar.ats import greenhouse, lever, smallats
from radar.http import Result


def _json(obj, status=200):
    return Result(url="https://example.test", status=status, headers={"content-type": "application/json"},
                  content=json.dumps(obj).encode())


def _lever_job(i):
    return {"id": f"{i:08d}-0000-0000-0000-000000000000", "text": f"Counsel {i}", "hostedUrl": f"https://jobs.lever.co/acme/{i}",
            "categories": {"location": "New York, NY"}, "description": "Regulatory counsel role."}


class FakeLever:
    def __init__(self, total, honor_skip=True):
        self.jobs = [_lever_job(i) for i in range(total)]
        self.honor_skip = honor_skip
        self.calls = []

    def get(self, url, params=None, **kw):
        self.calls.append(dict(params or {}))
        skip = params.get("skip", 0) if self.honor_skip else 0
        return _json(self.jobs[skip:skip + params.get("limit", 100)])


def test_lever_pull_pages_with_skip(monkeypatch):
    fake = FakeLever(150)
    monkeypatch.setattr(lever, "client", lambda: fake)
    st, ps = lever.pull("acme", "Acme")
    assert st == "ok" and len(ps) == 150
    assert [c["skip"] for c in fake.calls] == [0, 100]


def test_lever_pull_stops_when_skip_ignored(monkeypatch):
    fake = FakeLever(100, honor_skip=False)
    monkeypatch.setattr(lever, "client", lambda: fake)
    st, ps = lever.pull("acme", "Acme")
    assert st == "ok" and len(ps) == 100
    assert len(fake.calls) == 2  # the repeated page adds nothing, so paging stops


class FakeWorkable:
    def __init__(self, status):
        self.status = status
        self.calls = 0

    def post_json(self, url, body, **kw):
        self.calls += 1
        return _json({"results": [], "total": 0}, status=self.status)


def test_workable_cooldown(monkeypatch):
    fake = FakeWorkable(429)
    monkeypatch.setattr(smallats, "probe_client", lambda: fake)
    monkeypatch.setattr(smallats, "_wk_429_until", 0.0)
    smallats.wk_reset_limited()
    assert smallats.wk_probe("acme") == (False, -1)
    assert smallats.wk_cooling_down() and smallats.wk_limited_since_reset()
    assert smallats.wk_probe("other") == (False, -1)
    assert fake.calls == 1  # skipped during the cooldown
    smallats.wk_reset_limited()
    monkeypatch.setattr(smallats, "_wk_429_until", 0.0)  # cooldown over
    fake.status = 404
    assert smallats.wk_probe("acme") == (False, 0)
    assert fake.calls == 2 and not smallats.wk_limited_since_reset()


def test_detect_reports_workable_429(monkeypatch):
    fake = FakeWorkable(429)
    monkeypatch.setattr(smallats, "probe_client", lambda: fake)
    monkeypatch.setattr(smallats, "_wk_429_until", 0.0)
    monkeypatch.setattr(phase2, "PROBES", [("workable", smallats.wk_probe)])
    row = {"company": "Tower Research Capital", "careers_url": ""}
    ats, slug, note = phase2.detect(row)
    assert ats == "none" and "workable not checked (HTTP 429" in note
    # the next detect call after the cooldown gets a plain answer, not a stale 429 note
    monkeypatch.setattr(smallats, "_wk_429_until", 0.0)
    fake.status = 404
    ats, slug, note = phase2.detect(row)
    assert ats == "none" and "429" not in note


def test_name_collision_guard_skips_generic_names(monkeypatch):
    probed = []

    def hit(ats):
        def probe(slug):
            probed.append((ats, slug))
            return True, 5
        return probe

    monkeypatch.setattr(phase2, "PROBES", [("greenhouse", hit("greenhouse")), ("lever", hit("lever")), ("ashby", hit("ashby"))])
    monkeypatch.setattr(greenhouse, "board_name", lambda slug: "LCM Partners")
    ats, slug, note = phase2.detect({"company": "LCM", "careers_url": ""})
    assert ats == "none"
    assert "name-collision guard" in note
    assert all(a == "greenhouse" for a, _ in probed)  # lever/ashby guesses were not even probed

    # a distinctive multi-word name still resolves by slug guess
    probed.clear()
    ats, slug, note = phase2.detect({"company": "Tower Research Capital", "careers_url": ""})
    assert ats == "lever" and slug == "towerresearchcapital"


def test_distinctive_one_word_names_stay_guessable():
    assert not phase2._generic_name("EvenUp") and not phase2._generic_name("Spellbook") and not phase2._generic_name("Klarna")
    assert phase2._generic_name("LCM") and phase2._generic_name("ICE") and phase2._generic_name("Parabellum")


def test_name_collision_guard_allows_own_domain_label(monkeypatch):
    monkeypatch.setattr(phase2, "PROBES", [("lever", lambda slug: (slug == "parabellum", 3))])
    monkeypatch.setattr(phase2, "_scan_careers", lambda url: None)
    ats, slug, _ = phase2.detect({"company": "Parabellum", "careers_url": "https://www.parabellum.com/careers"})
    assert (ats, slug) == ("lever", "parabellum")
    ats, slug, note = phase2.detect({"company": "Parabellum", "careers_url": "https://www.parabellumcap.com/"})
    assert ats == "none" and "name-collision guard" in note


def test_non_workday_tenant_hints_are_not_read_as_workday(monkeypatch):
    called = []
    monkeypatch.setattr(phase2.workday, "list_jobs", lambda spec, max_pages=1: called.append(spec) or ("ok", [1]))
    monkeypatch.setattr(phase2, "_scan_careers", lambda url: None)
    monkeypatch.setattr(phase2, "PROBES", [])
    ats, _, _ = phase2.detect({"company": "DTCC Test Co", "careers_url": "", "ats_hint": "oraclehcm",
                               "ats_slug_or_tenant": "ebxr|us2|CX_1", "confidence": "verified_url"})
    assert ats == "none" and called == []


def _html(body, status=200):
    return Result(url="https://example.test", status=status, headers={"content-type": "text/html"},
                  content=body.encode())


def test_rlegaltech_parses_vendor_apply_blocks():
    from radar.discover import rlegaltech

    html = """
    <html><body>
    <h2>Featured</h2>
    <ol><li><strong>R&D Attorney</strong> GC AI - Remote
      <a href="https://jobs.ashbyhq.com/gc-ai/8d33e41c-f666-4178-91fc-89787931935c/application?utm_source=rlegaltech.com">Apply</a>
    </li></ol>
    <h3><a href="/vendors/abbyy/jobs/">ABBYY</a></h3>
    <span>7 open</span>
    <ul>
      <li>
        <h4>Data Engineer</h4>
        <div>Budapest, Hungary (Hybrid) Hybrid Employment type not listed <a href="/jobs/engineering/">Engineering</a></div>
        <div>Source checked 23 Sept 2026</div>
        <a href="https://job-boards.eu.greenhouse.io/abbyy/jobs/4960440101?utm_source=rlegaltech.com&gh_src=rlegaltech">Apply</a>
      </li>
    </ul>
    <h3><a href="/vendors/harvey/jobs/">Harvey</a></h3>
    <span>3 open</span>
    <ul>
      <li>
        <h4>Senior Public Sector Counsel</h4>
        <div>Remote (United States) Remote Full time <a href="/jobs/legal/">Legal</a></div>
        <div>Source checked 23 Sept 2026</div>
        <a href="https://jobs.ashbyhq.com/harvey/8bec95c8-b625-49e9-bd82-c8eb83e170ee/application?utm_source=rlegaltech.com&utm_medium=jobs_directory">Apply</a>
      </li>
    </ul>
    </body></html>
    """
    leads = rlegaltech._parse(html)
    urls = {l.url for l in leads}
    # utm_ params stripped from the kept ATS URL
    assert "https://jobs.ashbyhq.com/harvey/8bec95c8-b625-49e9-bd82-c8eb83e170ee/application" in urls
    harvey = next(l for l in leads if "harvey" in l.url)
    assert harvey.title == "Senior Public Sector Counsel"
    assert harvey.company == "Harvey"
    # the EU Greenhouse subdomain isn't in ATS_URL and Budapest isn't a kept location either way
    assert not any("abbyy" in u for u in urls)


def test_rlegaltech_run_records_channel(monkeypatch):
    from radar.discover import rlegaltech

    page = """
    <h3>Harvey</h3><span>1 open</span>
    <ul><li><h4>Senior Public Sector Counsel</h4>
    <div>Remote (United States) Remote Full time</div>
    <a href="https://jobs.ashbyhq.com/harvey/8bec95c8-b625-49e9-bd82-c8eb83e170ee/application">Apply</a>
    </li></ul>
    """
    fake = type("Fake", (), {"get": staticmethod(lambda url, **kw: _html(page))})()
    monkeypatch.setattr(rlegaltech, "client", lambda: fake)
    seen = []
    monkeypatch.setattr(rlegaltech, "add_leads", lambda leads: seen.extend(leads))
    out = rlegaltech.run()
    assert out["leads"] == 1 and len(seen) == 1


def test_rlegaltech_lead_source_matches_channel_naming_convention():
    # Lead.source must follow the "<label>[:<sub>]" convention every other discover channel uses
    # (not prefixed with "discover:" itself) -- phase4 keys stats on source.split(":")[0], and
    # pipeline.finish() matches that back to the "discover:<channel>" name via str.endswith. A
    # source of "discover:rlegaltech" broke that match and misfiled the channel's stats.
    from radar.discover import rlegaltech

    html = """
    <h3>Harvey</h3><span>1 open</span>
    <ul><li><h4>Senior Public Sector Counsel</h4>
    <div>Remote (United States) Remote Full time</div>
    <a href="https://jobs.ashbyhq.com/harvey/8bec95c8-b625-49e9-bd82-c8eb83e170ee/application">Apply</a>
    </li></ul>
    """
    leads = rlegaltech._parse(html)
    assert leads and leads[0].source == "rlegaltech"
    channel_name = "discover:rlegaltech"
    assert channel_name.endswith(leads[0].source.split(":")[0])
