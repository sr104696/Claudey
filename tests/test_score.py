from helpers import BODY, posting

from radar import score
from radar.score import LAW_FIRM_NONBILLABLE_REASON, _role_key, desc_hash


def test_baseline_fit():
    p = score.score(posting(body=BODY + " Salary range: $180,000 - $220,000 base."))
    assert p.bucket == "fit", p.poor_reason
    assert "base pay midpoint ≥ $150K" in p.fit_signals


def test_government_seat():
    p = score.score(posting(company="New York State Department of Financial Services", ats="page", job_id=None))
    assert p.bucket == "poor" and p.poor_reason.startswith("Government seat")


def test_government_source_but_finra_exception():
    p = score.score(posting(company="FINRA", source="public_sector:finra", ats="page", job_id=None))
    assert "Government seat" not in p.poor_reason
    p2 = score.score(posting(company="Some Agency", source="public_sector:nydfs", ats="page", job_id=None))
    assert "Government seat" in p2.poor_reason


def test_law_firm_seat():
    p = score.score(posting(company="Cravath, Swaine & Moore LLP", title="Litigation Counsel"))
    assert "Law-firm seat (lifestyle)" in p.poor_reason


def test_llp_named_fund_with_underwriting_title_is_not_a_law_firm_seat():
    p = score.score(posting(company="Longford Capital Fund LLP", title="Underwriting Counsel"))
    assert "Law-firm seat" not in p.poor_reason


def test_law_firm_nonbillable_km_seat():
    for title in ("Knowledge Management Lawyer", "Practice Support Attorney", "Research Attorney", "Legal Research Counsel",
                  "Professional Support Lawyer"):
        p = score.score(posting(company="Davis Polk & Wardwell LLP", title=title))
        assert p.bucket == "poor", title
        assert p.poor_reason.startswith(LAW_FIRM_NONBILLABLE_REASON), (title, p.poor_reason)


def test_pay_floor():
    p = score.score(posting(body=BODY + " The base salary range is $120,000 - $140,000."))
    assert "Listed pay tops out below $150K" in p.poor_reason


def test_no_pay_listed_is_not_a_pay_reason():
    p = score.score(posting())
    assert p.pay_display == "Not listed"
    assert "Listed pay" not in p.poor_reason
    assert "base pay midpoint ≥ $150K" not in p.fit_signals


def test_jersey_city_scores_in_area_and_stamford_outside():
    assert score.score(posting(location="Jersey City, NJ")).bucket == "fit"
    assert score.score(posting(location="Stamford, CT")).bucket == "outside"


def test_role_key_judgment_reused_only_on_same_text(monkeypatch):
    p = posting(job_id="new-req")
    j = {"key": "greenhouse:acme:old-req", "desc_hash": desc_hash(p), "hard_exclude": "Judge: sales seat"}
    monkeypatch.setattr(score, "_judg", {_role_key(p.company, p.title): j})
    assert score.score(p).hard_exclude_reason == "Judge: sales seat"

    monkeypatch.setattr(score, "_judg", {_role_key(p.company, p.title): {**j, "desc_hash": "0000000000000000"}})
    assert score.score(posting(job_id="new-req")).hard_exclude_reason == ""


def test_direct_key_judgment_applies_whatever_the_hash(monkeypatch):
    p = posting(job_id="7")
    monkeypatch.setattr(score, "_judg", {p.key: {"key": p.key, "desc_hash": "stale", "hard_exclude": "Judge: no"}})
    assert score.score(p).hard_exclude_reason == "Judge: no"


def test_contract_platform_and_non_seat_listings_are_poor():

    p = score.score(posting(company="Axiom Talent Platform", title="Capital Markets Attorney"))
    assert p.bucket == "poor" and "Contract-lawyer platform" in p.poor_reason
    p = score.score(posting(company="Point72", title="Point72 Academy Coffee Chats — Class of 2029 (US)"))
    assert p.bucket == "poor" and "not a seat" in p.poor_reason
