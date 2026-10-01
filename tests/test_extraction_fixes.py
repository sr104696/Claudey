"""Regression tests for the extraction / paging / verification fixes (false OTE, hourly, locations, dedupe, partial pulls...)."""
import csv
import json
import os

import pytest
from helpers import posting

from radar import config, phase2, phase4
from radar.ats import greenhouse, lever, nyag, smallats, workday
from radar.ats import html as htmlats
from radar.ats.base import build_posting, url_key
from radar.extract import classify_location, pay_extras, pay_from_text
from radar.http import Result
from radar.score import score
from radar.textutil import jsonld_jobposting, names_match, norm_title


def _json(obj, status=200):
    return Result(url="https://example.test", status=status, headers={"content-type": "application/json"},
                  content=json.dumps(obj).encode())


def _html(text, status=200, **kw):
    return Result(url="https://example.test", status=status, headers={"content-type": "text/html"},
                  content=text.encode(), **kw)


# ----------------------------------------------------------------- 1. false OTE
SEC = ("advising on Securities and Exchange Commission and FINRA matters. "
       "The base salary range for this role is $180,000 - $220,000 per year.")


@pytest.mark.parametrize("agency", [
    "Securities and Exchange Commission", "Equal Employment Opportunity Commission", "Federal Trade Commission",
    "Commodity Futures Trading Commission", "the Commission",
])
def test_agency_names_do_not_make_ote(agency):
    pay = pay_from_text(f"You will work with the {agency} on investigations. The base salary range is $180,000 - $220,000.")
    assert (pay.type, pay.min, pay.max) == ("base", 180_000, 220_000)
    assert "commission" not in pay.extras


def test_sec_boilerplate_posting_is_not_an_ote_exclude():
    p = posting(body=SEC + " J.D. required. 3-5 years of experience.")
    assert p.pay_type == "base" and p.pay_extras == ""
    assert "OTE" not in score(p).hard_exclude_reason


def test_pay_extras_ignores_agency_commission():
    assert pay_extras("We regularly appear before the Securities and Exchange Commission.") == ""
    assert pay_extras("Base salary plus uncapped commission.") == "commission"


@pytest.mark.parametrize("text", [
    "Total compensation is $200,000 - $250,000 OTE.",
    "Pay range: $200,000 - $250,000 on-target earnings.",
    "Pay range: $200,000 - $250,000 base + commission.",
    "Salary $200,000 - $250,000 with an uncapped commission plan.",
    "Salary $200,000 - $250,000, target total cash.",
])
def test_real_ote_language_is_ote(text):
    assert pay_from_text(text).type == "OTE"


def _gh_range(lo, hi, title="", blurb=""):
    return {"min_cents": lo * 100, "max_cents": hi * 100, "currency_type": "USD", "title": title, "blurb": blurb}


def test_greenhouse_range_with_sec_blurb_is_base():
    blurb = ("<p>Counsel advises on matters before the Securities and Exchange Commission and the Federal Trade "
             "Commission. Our commission-free approach rewards impact.</p>")
    pay = greenhouse._pay([_gh_range(200_000, 385_000, "US Pay Range", blurb)])
    assert pay.type == "base" and pay.period == "year"


def test_greenhouse_genuine_commission_blurb_is_ote():
    pay = greenhouse._pay([_gh_range(120_000, 180_000, "New York", "Base + commission, uncapped.")])
    assert pay.type == "OTE"
    assert greenhouse._pay([_gh_range(120_000, 180_000, "OTE range", "")]).type == "OTE"


def test_greenhouse_sec_counsel_row_survives_scoring():
    j = {"id": 7, "title": "Senior Counsel, Regulatory", "location": {"name": "New York, NY"},
         "content": "<p>J.D. required. 4 years of experience. Credit and payments regulation.</p>",
         "pay_input_ranges": [_gh_range(200_000, 260_000, "New York", "Securities and Exchange Commission work.")]}
    p = greenhouse._posting("acme", j, "Acme", "board:greenhouse")
    assert p.pay_type == "base"
    assert "OTE" not in score(p).hard_exclude_reason


def test_lever_salary_description_uses_tight_ote_test():
    j = {"id": "00000001-0000-0000-0000-000000000000", "text": "Counsel", "categories": {"location": "New York, NY"},
         "description": "Counsel role.",
         "salaryRange": {"min": 200000, "max": 250000, "interval": "per-year-salary"},
         "salaryDescriptionPlain": "Range reflects work before the Securities and Exchange Commission."}
    assert lever._posting("acme", j, "Acme", "x").pay_type == "base"
    j["salaryDescriptionPlain"] = "Base plus commission."
    assert lever._posting("acme", j, "Acme", "x").pay_type == "OTE"


# ------------------------------------------- 1b. greenhouse hourly (coordinator addition)
def test_greenhouse_annual_range_with_hours_in_blurb_stays_annual():
    pay = greenhouse._pay([_gh_range(214_200, 315_000, "US", "Hours of operation vary; working hours are flexible.")])
    assert (pay.period, pay.type, pay.min, pay.max) == ("year", "base", 214_200, 315_000)


def test_greenhouse_real_hourly_range_is_hourly():
    pay = greenhouse._pay([_gh_range(45, 60, "Hourly", "$45 - $60 per hour")])
    assert (pay.period, pay.type, pay.min, pay.max) == ("hour", "hourly", 45, 60)


def test_greenhouse_small_amounts_without_hourly_marker_are_not_read_as_pay():
    assert greenhouse._pay([_gh_range(1, 1, "", "hours vary")]) is None


# ------------------------------------------------------- 2. remote flag from the ATS only
def _run_phase4_with(monkeypatch, posts):
    monkeypatch.setattr(phase4, "gather", lambda verify_leads=True: (posts, {}))
    monkeypatch.setattr(phase4.db, "upsert_posting", lambda p: None)
    return phase4.run(verify_leads=False)[0]


def test_description_prose_does_not_make_an_sf_office_role_us_remote(monkeypatch):
    body = "Acme is a remote-first company. This role sits in our SF office five days a week. Regulatory counsel; J.D. required."
    p = posting(location="San Francisco, CA", body=body, ats="lever", board="acme")
    p.sources = ["seed"]
    assert p.workplace == "remote" and p.remote_flag is None  # workplace_of() reads the prose, the ATS flag is absent
    kept = _run_phase4_with(monkeypatch, [p])
    assert [(x.loc_bucket, x.bucket) for x in kept] == [("us_other", "outside")]  # not us_remote, so not in the main tables


def test_real_ats_remote_flag_still_makes_us_remote(monkeypatch):
    p = build_posting(ats="lever", board="acme", job_id="2", company="Acme Payments", title="Regulatory Counsel",
                      url="https://jobs.lever.co/acme/2", description_text="Regulatory counsel. J.D. required.",
                      locations=["San Francisco, CA"], remote_flag=True, source="board:lever")
    p.sources = ["seed"]
    assert p.remote_flag is True
    kept = _run_phase4_with(monkeypatch, [p])
    assert [x.loc_bucket for x in kept] == ["us_remote"]


# ------------------------------------------------------------------ 3. non-US substrings
@pytest.mark.parametrize("loc,bucket", [
    ("Indianapolis, IN", "us_other"), ("Remote - Indiana", "us_remote"), ("Santa Fe, New Mexico", "us_other"),
    ("Dublin, CA", "us_other"), ("Dublin, OH", "us_other"), ("Vienna, VA", "us_other"), ("Athens, GA", "us_other"),
    ("Rome, NY", "us_other"),
    # still foreign
    ("Dublin, Ireland", "non_us"), ("Vienna, Austria", "non_us"), ("Athens, Greece", "non_us"),
    ("Bangalore, IN", "non_us"), ("Remote - India", "non_us"), ("Mexico City, Mexico", "non_us"), ("London, UK", "non_us"),
    ("New York, NY", "nyc"),
])
def test_location_buckets_use_word_boundaries_and_state_context(loc, bucket):
    assert classify_location(loc) == bucket


# ----------------------------------------- 4. title noise and dedupe
def test_norm_title_strips_only_a_trailing_location():
    assert norm_title("Counsel, US Regulatory") != norm_title("Counsel, US Commercial")
    assert norm_title("Counsel, US Regulatory") == "counsel us regulatory"
    for t in ("Counsel - New York, NY", "Counsel (Remote, US)", "Counsel | NYC", "Counsel, New York", "Counsel - Hybrid"):
        assert norm_title(t) == "counsel", t


INTRO = "Acme is a payments company building financial infrastructure for the internet. " * 30  # > 1500 chars


def test_dedupe_keeps_reqs_with_a_long_shared_intro_and_different_tails():
    assert len(INTRO) > 1500
    a = posting(title="Counsel", body=INTRO + "You will advise the lending team on credit regulation.", job_id="1", ats="lever")
    b = posting(title="Counsel", body=INTRO + "You will advise the markets team on trading rules.", job_id="2", ats="lever")
    assert len(phase4.dedupe([a, b])) == 2


def test_dedupe_still_merges_true_duplicates():
    a = posting(title="Counsel", body=INTRO + "Same tail.", job_id="1", ats="lever", source="board:lever")
    b = posting(title="Counsel", body=INTRO + "Same tail.", job_id="2", ats="lever", source="seed")
    out = phase4.dedupe([a, b])
    assert len(out) == 1 and set(out[0].sources) == {"board:lever", "seed"}


def test_dedupe_no_longer_merges_on_empty_body_or_different_ats_alone():
    a = posting(title="Counsel", body="", job_id="1", ats="lever")
    b = posting(title="Counsel", body="Full text about credit risk.", job_id="2", ats="lever")
    assert len(phase4.dedupe([a, b])) == 2


def test_dedupe_cross_ats_merge_needs_title_company_location_and_pay():
    c = posting(title="Counsel", body="Posting text as the seed page copied it.", job_id="3", ats="page", location="New York, NY")
    d = posting(title="Counsel", body="Posting text as the API serves it.", job_id="4", ats="greenhouse", location="New York, NY")
    assert len(phase4.dedupe([c, d])) == 1
    e = posting(title="Counsel", body="A different req text, as the API serves it.", job_id="5", ats="ashby", location="Remote, US")
    assert len(phase4.dedupe([d, e])) == 2


# ---------------------------------------------------------- 5. money scale is not pay
@pytest.mark.parametrize("text", [
    "You will cover $500-$800 million portfolios.", "Our fund manages $50 to $75 billion in AUM.",
    "Coverage of $5M-$8M portfolios of loans.", "Deals of $500 - $800 mm each.",
])
def test_asset_amounts_are_not_hourly_pay(text):
    assert pay_from_text(text).min is None


def test_hourly_fallback_needs_a_pay_word_but_real_pay_still_parses():
    assert pay_from_text("Coverage spans 200 - 300 names.").min is None
    p = pay_from_text("The hourly rate is $45 - $60 per hour.")
    assert (p.type, p.min, p.max) == ("hourly", 45, 60)
    p = pay_from_text("Hiring range: $50 - $75.")  # bare small range next to a pay word
    assert p.period == "hour"
    assert pay_from_text("Salary: $150,000 - $200,000").type == "base"


# --------------------------------------------------------- 6. truncated pulls are partial
def _lever_job(i):
    return {"id": f"{i:08d}-0000-0000-0000-000000000000", "text": f"Counsel {i}", "hostedUrl": f"https://jobs.lever.co/acme/{i}",
            "categories": {"location": "New York, NY"}, "description": "Regulatory counsel role."}


class PagedLever:
    def __init__(self, pages):
        self.pages = pages  # skip -> response (list or Result)
        self.calls = []

    def get(self, url, params=None, **kw):
        self.calls.append(params["skip"])
        out = self.pages(params["skip"])
        return out if isinstance(out, Result) else _json(out)


def test_lever_failed_second_page_is_partial(monkeypatch):
    fake = PagedLever(lambda skip: [_lever_job(i) for i in range(100)] if skip == 0 else Result(url="x", status=500, error="HTTP 500"))
    monkeypatch.setattr(lever, "client", lambda: fake)
    st, ps = lever.pull("acme", "Acme")
    assert st.startswith("partial") and len(ps) == 100


def test_lever_short_filtered_batch_does_not_stop_paging(monkeypatch):
    def pages(skip):  # page 2 repeats three ids from page 1 but is full; page 3 still has jobs
        if skip == 0:
            return [_lever_job(i) for i in range(100)]
        if skip == 100:
            return [_lever_job(i) for i in range(97, 197)]
        if skip == 200:
            return [_lever_job(i) for i in range(197, 220)]
        return []

    fake = PagedLever(pages)
    monkeypatch.setattr(lever, "client", lambda: fake)
    st, ps = lever.pull("acme", "Acme")
    assert st == "ok" and len(ps) == 220 and fake.calls == [0, 100, 200]


def test_lever_page_cap_is_partial(monkeypatch):
    fake = PagedLever(lambda skip: [_lever_job(skip + i) for i in range(100)])
    monkeypatch.setattr(lever, "client", lambda: fake)
    st, ps = lever.pull("acme", "Acme")
    assert st.startswith("partial") and len(ps) == 5000


class FakeWorkday:
    def __init__(self, total, empty_after=None):
        self.total, self.empty_after = total, empty_after

    def post_json(self, url, body, **kw):
        off = body["offset"]
        if self.empty_after is not None and off >= self.empty_after:
            return _json({"total": self.total, "jobPostings": []})
        n = max(0, min(20, self.total - off))
        return _json({"total": self.total, "jobPostings": [{"title": f"Counsel {off + i}", "externalPath": f"/job/NY/Counsel_R{off + i}"} for i in range(n)]})


SPEC = {"tenant": "acme", "wd": "wd5", "site": "Careers"}


def test_workday_list_jobs_ok_partial_and_empty_page(monkeypatch):
    monkeypatch.setattr(workday, "client", lambda: FakeWorkday(45))
    st, jobs = workday.list_jobs(SPEC)
    assert st == "ok" and len(jobs) == 45
    st, jobs = workday.list_jobs(SPEC, max_pages=2)
    assert st.startswith("partial") and len(jobs) == 40
    monkeypatch.setattr(workday, "client", lambda: FakeWorkday(100, empty_after=40))
    st, jobs = workday.list_jobs(SPEC)
    assert st.startswith("partial") and len(jobs) == 40


class FakeWorkable:
    def __init__(self, pages, fail_at=None):
        self.pages, self.fail_at, self.n = pages, fail_at, 0

    def post_json(self, url, body, **kw):
        self.n += 1
        if self.fail_at == self.n:
            return Result(url=url, status=500, error="HTTP 500")
        more = self.pages is None or self.n < self.pages
        return _json({"results": [{"shortcode": f"S{self.n}", "title": "Counsel", "location": {"city": "New York", "region": "NY"}}],
                      "nextPage": "tok" if more else None})


def test_workable_pull_status(monkeypatch):
    fake = FakeWorkable(3)  # one instance per pull: it counts the pages served
    monkeypatch.setattr(smallats, "client", lambda: fake)
    st, ps = smallats.wk_pull("acme", "Acme")
    assert st == "ok" and len(ps) == 3
    fake = FakeWorkable(None)
    st, ps = smallats.wk_pull("acme", "Acme")
    assert st.startswith("partial") and len(ps) == 20
    fake = FakeWorkable(5, fail_at=3)
    st, ps = smallats.wk_pull("acme", "Acme")
    assert st.startswith("partial") and len(ps) == 2


class FakeSR:
    def __init__(self, total):
        self.total, self.calls = total, []

    def get(self, url, params=None, **kw):
        off = params.get("offset", 0)
        self.calls.append(off)
        n = max(0, min(params["limit"], self.total - off))
        return _json({"totalFound": self.total, "content": [
            {"id": str(off + i), "name": "Counsel", "location": {"city": "New York", "region": "NY", "country": "us"}} for i in range(n)]})


def test_smartrecruiters_pull_pages(monkeypatch):
    fake = FakeSR(250)
    monkeypatch.setattr(smallats, "client", lambda: fake)
    st, ps = smallats.sr_pull("acme", "Acme")
    assert st == "ok" and len(ps) == 250 and fake.calls == [0, 100, 200]
    monkeypatch.setattr(smallats, "client", lambda: FakeSR(10**6))
    st, ps = smallats.sr_pull("acme", "Acme")
    assert st.startswith("partial") and len(ps) == 5000


# ------------------------------------------------------------------ 7. url_key
def test_url_key_keeps_id_params_and_hash_routes_but_drops_tracking():
    k = lambda u: url_key(u)
    assert k("https://x.test/jobs?reference=5") != k("https://x.test/jobs?reference=6")
    assert k("https://x.test/jobs?referral_id=1") != k("https://x.test/jobs?referral_id=2")
    assert k("https://x.test/jobs?gh_jid=11") != k("https://x.test/jobs?gh_jid=12")
    assert k("https://x.test/careers#/job/123") != k("https://x.test/careers#/job/124")
    assert k("https://x.test/careers#/job/123") == "url:x.test/careers#/job/123"
    for noise in ("utm_source=a&utm_medium=b", "gh_src=zz", "src=li", "ref=abc", "source=x", "lever-source=y", "gclid=1",
                  "fbclid=2", "mc_cid=3"):
        assert k(f"https://x.test/jobs?gh_jid=11&{noise}") == k("https://x.test/jobs?gh_jid=11"), noise
    assert k("https://x.test/careers#apply") == k("https://x.test/careers")


# --------------------------------------------- 8. one detail failure keeps the board
def _light(ats, i, title="Regulatory Counsel"):
    return build_posting(ats=ats, board="acme", job_id=f"J{i}", company="Acme", title=title, url=f"https://x.test/{i}",
                         description_text="", locations=["New York, NY"], status="listed", source="board")


@pytest.mark.parametrize("ats,pull_name,detail_name", [("workable", "wk_pull", "wk_detail"), ("bamboohr", "bb_pull", "bb_detail")])
def test_one_failing_detail_call_keeps_the_board_partial(monkeypatch, ats, pull_name, detail_name):
    lights = [_light(ats, 1), _light(ats, 2)]
    monkeypatch.setattr(smallats, pull_name, lambda slug, company, src: ("ok", lights))

    def detail(slug, job_id, company, src):
        if job_id == "J1":
            raise RuntimeError("HTTP 500")
        return posting(title="Regulatory Counsel", job_id="J2", ats=ats, board="acme")

    monkeypatch.setattr(smallats, detail_name, detail)
    monkeypatch.setattr(phase2, "relevance", lambda *a, **k: (True, "t"))
    st, out = phase2.pull(ats, "acme", "Acme", "")
    assert st.startswith("partial") and len(out) == 2
    assert out[0].status == "listed"  # the failed job fell back to its light posting


def test_failing_workday_detail_and_sf_verify_are_partial(monkeypatch):
    jobs = [{"title": "Regulatory Counsel", "externalPath": "/job/NY/Counsel_R1", "bulletFields": ["R1"], "locationsText": "New York, NY"}]
    monkeypatch.setattr(workday, "list_jobs", lambda spec: ("ok", jobs))
    monkeypatch.setattr(workday, "detail", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad json")))
    monkeypatch.setattr(phase2, "relevance", lambda *a, **k: (True, "t"))
    st, out = phase2.pull("workday", "acme|wd5|Careers", "Acme", "")
    assert st.startswith("partial") and len(out) == 1

    monkeypatch.setattr(htmlats, "rmk_sitemap", lambda host: ("ok", ["https://careers.fitch.group/job/New-York-Counsel-NY/123/"]))
    monkeypatch.setattr(htmlats, "rmk_verify", lambda *a, **k: (_ for _ in ()).throw(LookupError("layout")))
    st, out = phase2.pull("successfactors", "careers.fitch.group", "Fitch", "")
    assert st.startswith("partial") and len(out) == 1


# ------------------------------------------------------------ 9. false closed verdicts
def test_rmk_verify_missing_title_on_a_200_is_an_error_not_closed(monkeypatch):
    class C:
        def get(self, url, **kw):
            return _html("<html><body><h1>Careers</h1></body></html>")

    monkeypatch.setattr(htmlats, "client", lambda: C())
    with pytest.raises(LookupError):
        htmlats.rmk_verify("https://careers.fitch.group/job/NY-Counsel/1/")


def test_rmk_verify_still_closes_on_404_and_error_page_redirect(monkeypatch):
    class C404:
        def get(self, url, **kw):
            return _html("", status=404)

    class CErr:
        def get(self, url, **kw):
            return _html("<html></html>", redirects=["https://careers.fitch.group/errorpage"])

    monkeypatch.setattr(htmlats, "client", lambda: C404())
    assert htmlats.rmk_verify("https://careers.fitch.group/job/NY-Counsel/1/") is None
    monkeypatch.setattr(htmlats, "client", lambda: CErr())
    assert htmlats.rmk_verify("https://careers.fitch.group/job/NY-Counsel/1/") is None


def test_workday_parse_url_drops_apply_and_trailing_slash():
    base = "https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/New-York/Counsel_R123"
    for u in (base, base + "/", base + "/apply", base + "/apply/", base + "/apply/autofillWithResume?x=1"):
        assert workday.parse_url(u)["path"] == "/job/New-York/Counsel_R123", u


def _ld(obj):
    return f'<html><body><script type="application/ld+json">{json.dumps(obj)}</script></body></html>'


def test_jsonld_verify_handles_list_description_and_string_location():
    jp = {"@type": "JobPosting", "title": "Regulatory Counsel", "description": ["<p>Credit regulation.</p>", "<p>J.D. required.</p>"],
          "jobLocation": "New York, NY", "hiringOrganization": {"name": "Acme"}}
    p = htmlats.jsonld_verify("https://acme.test/jobs/1", html=_ld(jp))
    assert p.locations == ["New York, NY"] and "Credit regulation." in p.description and "J.D. required." in p.description
    jp["jobLocation"] = [{"address": {"addressLocality": "New York", "addressRegion": "NY"}}, "Remote"]
    assert htmlats.jsonld_verify("https://acme.test/jobs/1", html=_ld(jp)).locations == ["New York, NY", "Remote"]


def test_jsonld_valid_through_uses_config_today(monkeypatch):
    jp = {"@type": "JobPosting", "title": "Counsel", "description": "x", "jobLocation": "New York, NY", "validThrough": "2026-06-30"}
    monkeypatch.setattr(config, "today", lambda: "2026-06-01")
    assert htmlats.jsonld_verify("https://acme.test/1", html=_ld(jp)) is not None
    monkeypatch.setattr(config, "today", lambda: "2026-07-01")
    assert htmlats.jsonld_verify("https://acme.test/1", html=_ld(jp)) is None


# ---------------------------------------------------------- 10. employer name matching
@pytest.mark.parametrize("a,b", [("Apollo Global Management", "Apollo GraphQL"), ("Morgan Stanley", "Morgan Lewis"),
                                 ("Franklin Templeton", "Franklin Covey")])
def test_name_match_rejects_shared_first_word(a, b):
    assert not phase2._name_matches(a, b) and not names_match(a, b)


@pytest.mark.parametrize("a,b", [("Marqeta", "Marqeta, Inc."), ("Spellbook", "Spellbook Legal"), ("OpenAI", "Open AI"),
                                 ("Morgan Stanley", "Morgan Stanley & Co. LLC")])
def test_name_match_accepts_genuine_matches(a, b):
    assert phase2._name_matches(a, b)


def test_employer_board_checks_names_and_is_deterministic(monkeypatch):
    monkeypatch.setattr(phase4.greenhouse, "probe", lambda g: (g == "apollo", 4))
    monkeypatch.setattr(phase4.greenhouse, "board_name", lambda g: "Apollo GraphQL")
    monkeypatch.setattr(phase4.lever, "probe", lambda g: (g == "apollo", 4))
    monkeypatch.setattr(phase4.ashby, "probe", lambda g: (g == "apollo", 4))
    # greenhouse names the board "Apollo GraphQL"; lever and ashby only match a slug of the employer's whole name
    assert phase4._employer_board("Apollo Global Management", {}) is None
    monkeypatch.setattr(phase4.greenhouse, "probe", lambda g: (g == "marqeta", 4))
    monkeypatch.setattr(phase4.greenhouse, "board_name", lambda g: "Marqeta")
    assert phase4._employer_board("Marqeta, Inc.", {}) == ("greenhouse", "marqeta")
    monkeypatch.setattr(phase4.greenhouse, "probe", lambda g: (False, 0))
    monkeypatch.setattr(phase4.lever, "probe", lambda g: (g == "marqeta", 4))
    assert phase4._employer_board("Marqeta, Inc.", {}) == ("lever", "marqeta")


# ------------------------------------------------ 11. public-sector page: 200 is not open
class PageClient:
    def __init__(self, html):
        self.html = html

    def get(self, url, **kw):
        return _html(self.html)


def test_page_posting_closed_phrases_and_past_deadline(monkeypatch):
    monkeypatch.setattr(config, "today", lambda: "2026-10-01")
    args = ("https://agency.test/posting/1", "Agency", "Counsel", "New York, NY", "public_sector:x", "x")
    monkeypatch.setattr(phase4, "client", lambda: PageClient("<html><body><h1>Counsel</h1><p>This position has been filled.</p></body></html>"))
    p = phase4._page_posting(*args)
    assert p.status == "closed"
    monkeypatch.setattr(phase4, "client", lambda: PageClient("<html><body><p>Counsel. Application deadline: January 5, 2026</p></body></html>"))
    p = phase4._page_posting(*args)
    assert p.status == "closed" and "2026-01-05" in p.status_evidence
    monkeypatch.setattr(phase4, "client", lambda: PageClient("<html><body><p>Counsel. Application deadline: December 5, 2026</p></body></html>"))
    assert phase4._page_posting(*args).status == "open"
    st, p, ev = phase4.resolve_lead({"url": args[0], "company": "Agency", "title": "Counsel", "location": "New York, NY",
                                     "source": "public_sector:x"}, {})
    assert st == "open" and p is not None


def test_resolve_lead_reports_closed_for_an_expired_page(monkeypatch):
    monkeypatch.setattr(phase4, "client", lambda: PageClient("<html><body><p>Sorry, this job is no longer available.</p></body></html>"))
    st, p, ev = phase4.resolve_lead({"url": "https://agency.test/p/1", "company": "Agency", "title": "Counsel",
                                     "location": "New York, NY", "source": "public_sector:x"}, {})
    assert st == "closed"


# ------------------------------------------------------------------ 12. small ones
def test_nyag_location_pay_with_space_after_dollar_sign(monkeypatch):
    class C:
        def get(self, url, **kw):
            return Result(url=url, status=200, content=b"pdf")

    monkeypatch.setattr(nyag, "client", lambda: C())
    monkeypatch.setattr(nyag, "pdf_text", lambda b: "Hiring rate $90,000 - $110,000. Plus $ 12,000 location pay for NYC.")
    entry = {"pdf": "https://ag.ny.gov/x.pdf", "title": "Counsel", "ref": "R1", "category": "legal", "deadline": None,
             "location": "New York, NY"}
    p = nyag.to_posting(entry)
    assert "$12,000 location pay" in p.pay_display


def test_nyag_deadline_uses_config_today(monkeypatch):
    monkeypatch.setattr(nyag, "client", lambda: None)
    monkeypatch.setattr(config, "today", lambda: "2026-10-01")
    entry = {"pdf": "https://ag.ny.gov/x.pdf", "title": "Counsel", "ref": "R1", "category": "legal", "deadline": "2026-09-30",
             "location": "New York, NY", "deadline_text": "Sept 30"}
    assert nyag.to_posting(entry, fetch_pdf=False).status == "closed"


def test_jsonld_jobposting_returns_the_first_posting():
    def jp(t):
        return {"@type": "JobPosting", "title": t}

    page = ('<script type="application/ld+json">' + json.dumps([jp("First"), jp("Second")]) + "</script>"
            '<script type="application/ld+json">' + json.dumps({"@graph": [jp("Third"), jp("Fourth")]}) + "</script>")
    assert jsonld_jobposting(page)["title"] == "First"


ROWS = [{"company": "Acme", "segment": "x", "ats": "greenhouse", "slug": "acme"}]


@pytest.mark.parametrize("nl", [b"\r\n", b"\n"])
def test_save_registry_is_atomic_and_keeps_line_endings(tmp_path, monkeypatch, nl):
    path = tmp_path / "companies.csv"
    path.write_bytes(b"company,segment" + nl + b"Old,y" + nl)
    monkeypatch.setattr(config, "COMPANIES_CSV", path)
    phase2.save_registry(ROWS)
    data = path.read_bytes()
    assert data.count(b"\n") == 2 and (data.count(b"\r\n") == 2) == (nl == b"\r\n")
    assert [r["company"] for r in csv.DictReader(data.decode().splitlines())] == ["Acme"]
    assert os.listdir(tmp_path) == ["companies.csv"]  # no temp file left behind


def test_save_registry_failure_leaves_the_original_intact(tmp_path, monkeypatch):
    path = tmp_path / "companies.csv"
    path.write_bytes(b"company,segment\r\nOld,y\r\n")
    monkeypatch.setattr(config, "COMPANIES_CSV", path)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        phase2.save_registry(ROWS)
    assert path.read_bytes() == b"company,segment\r\nOld,y\r\n" and os.listdir(tmp_path) == ["companies.csv"]
