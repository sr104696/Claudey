"""Regexes that wrongly hard-excluded or demoted in-house counsel seats (found in the 2026-10-01 review of run 9)."""
from helpers import BODY, posting

from radar import score
from radar.extract import Pay

PAY = " The base salary range is $200,000 - $250,000."


def _s(title="Regulatory Counsel", body="", company="Acme Payments", **kw):
    return score.score(posting(title=title, company=company, body=BODY + " " + body + PAY, **kw))


def test_years_range_upper_bound_is_not_the_minimum():
    for body in ("3-5 years of banking regulatory experience.", "3 to 5 years of experience at a law firm or hedge fund.",
                 "4-6 years of leveraged finance practice."):
        p = _s(body=body)
        assert not p.hard_exclude_reason, (body, p.hard_exclude_reason)


def test_real_banking_and_leveraged_finance_asks_still_exclude():
    p = _s(body="5+ years of investment banking experience required.")
    assert p.hard_exclude_reason.startswith("Asks for 5+ years of equity research")
    p = _s(body="7+ years of leveraged finance practice required.")
    assert "leveraged-finance" in p.hard_exclude_reason
    nonlegal = _s(title="Credit Analyst", body="6+ years of banking experience required.")
    assert nonlegal.hard_exclude_reason.startswith("Asks for 5+ years of equity research")


def test_legal_experience_near_finance_words_is_not_a_banking_ask():
    p = _s(body="7+ years of legal experience, preferably advising private equity sponsors on regulatory matters.")
    assert not p.hard_exclude_reason, p.hard_exclude_reason
    p = _s(title="Senior Counsel, Financial Services", body="5+ years of relevant legal experience in banking/finance.")
    assert not p.hard_exclude_reason, p.hard_exclude_reason


def test_a_decade_in_marketing_copy_is_not_a_ten_year_ask():
    for body in ("Our platform spots risk up to 10 days in advance versus 10 years in traditional clinical models of care.",
                 "Kraken has spent the last 15 years building the future of finance."):
        p = _s(body=body)
        assert "10+ years" not in p.hard_exclude_reason, (body, p.hard_exclude_reason)
    assert _s(body="At least 12 years of legal experience required.").hard_exclude_reason.startswith("Asks for 10+ years")


def test_counsel_titles_are_not_sales_or_quant_seats():
    for title in ("Sales Counsel", "Counsel, Quantum Computing", "Product Counsel, Machine Learning", "AGC, Sales & Growth"):
        p = _s(title=title)
        assert not p.hard_exclude_reason, (title, p.hard_exclude_reason)
    assert _s(title="Senior Account Executive").sales_attached == "Y"


def test_python_and_statistics_only_when_required():
    assert not _s(body="Proficiency in Python is a plus.").hard_exclude_reason
    assert not _s(body="Strong analytical skills, including statistical reasoning.").hard_exclude_reason
    assert _s(body="Python is required for this role.").hard_exclude_reason.startswith("Requires Python")


def test_contract_prose_is_not_a_contract_seat():
    for body in ("You will review each vendor contract on a daily basis.", "A 12-week onboarding program."):
        assert "Contract, hourly" not in _s(body=body).poor_reason, body
    assert "Contract, hourly" in _s(body="This is a contract position for 6 months.").poor_reason
    assert "Contract-lawyer platform" not in _s(company="Axiom Space").poor_reason
    assert "Contract-lawyer platform" in _s(company="Axiom Talent Platform").poor_reason


def test_am_law_background_and_our_clients_do_not_make_an_in_house_seat_a_law_firm():
    p = _s(body="3+ years at an Am Law 200 firm preferred. You will advise our clients across the business and join our legal group.")
    assert p.bucket == "fit", p.poor_reason
    p = _s(title="Associate General Counsel", body="You will advise our clients (our business teams).")
    assert "Law-firm" not in p.poor_reason
    firm = _s(body="Our firm's attorneys bill billable hours to clients.", company="Smith & Jones")
    assert "Law-firm seat" in firm.poor_reason


def test_fund_underwriting_seat_is_not_a_law_firm_seat_on_text_alone():
    p = _s(title="Vice President, Commercial Underwriting", company="Burford Capital",
           body="Experience at an Am Law 100 firm; our firm's attorneys and billable hours are not part of this role.")
    assert "Law-firm" not in p.poor_reason


def test_annual_salary_mistyped_as_hourly_is_repaired():
    p = posting(title="Regulatory Counsel", body=BODY, pay=Pay(214_200, 315_000, "hourly", "hour", "USD", "test"))
    p.pay_display = "$214,200–$315,000/hr"
    p = score.score(p)
    assert p.pay_period == "year" and p.pay_type == "base" and "/hr" not in p.pay_display
    assert "Contract, hourly" not in p.poor_reason
    real = posting(title="Paralegal Counsel", body=BODY, pay=Pay(45, 60, "hourly", "hour", "USD", "test"))
    assert "Contract, hourly" in score.score(real).poor_reason


def test_judge_override_clears_scraper_ote_on_a_counsel_seat_without_commission_text(monkeypatch):
    p = posting(title="Privacy Counsel", body=BODY, pay=Pay(265_000, 335_000, "OTE", "year", "USD", "test"))
    assert score.score(p).hard_exclude_reason.startswith("Pay is quoted as OTE")
    monkeypatch.setattr(score, "judgment_for", lambda _p: {"override_regex_exclude": True, "meets_floor": "N"})
    assert not score.score(p).hard_exclude_reason
    sales = posting(title="Counsel", body=BODY + " Compensation is base plus uncapped commission.",
                    pay=Pay(200_000, 250_000, "OTE", "year", "USD", "test"))
    assert score.score(sales).hard_exclude_reason.startswith("Pay is quoted as OTE")
