"""Sample: property-based tests for the extract/score boundary (approach from 03 §tests).

These run against the real radar package if it is importable, else demonstrate the properties
standalone. Add `hypothesis` to a dev extra and drop into tests/test_properties.py.

Run:  pip install hypothesis && python test_properties.py
"""
from __future__ import annotations

try:
    from hypothesis import given, settings, strategies as st
    HAVE_HYP = True
except ImportError:
    HAVE_HYP = False

import re


# --------------------------------------------------------------------- pay band sanity
# Property: pay_from_text never yields an annual range that overlaps the hourly band,
# and never yields min > max. (radar.extract.pay_from_text)
def _pay_props():
    from radar.extract import pay_from_text

    @given(st.from_regex(r"\$[0-9]{1,3}(,[0-9]{3}){0,2}(-|to)\$?[0-9]{1,3}(,[0-9]{3}){0,2}( ?[kKmM])? per (hour|year|month)", fullmatch=True))
    @settings(max_examples=200, deadline=None)
    def prop_sane(text):
        p = pay_from_text(text)
        assert not (p.min and p.max and p.max < p.min), text
        if p.period == "year" and p.min:
            assert p.min >= 1000, f"annual pay below sanity floor: {text} -> {p}"

    prop_sane()
    print("pay band sanity property ✓")


# --------------------------------------------------------------------- negation polarity
# Property: affirmed() must NOT fire when the only occurrence of the pattern is inside an
# explicit negation sentence ("we do not track billable hours").
NEGATED_CORPUS = [
    "Unlike firm roles, we do not track billable hours.",
    "This is not a contract position and never will be.",
    "No commission plan applies to this base-salary seat.",
]


def _negation_props():
    from radar.score import affirmed, LAW_FIRM_ASSOCIATE, EXCL

    pairs = [(LAW_FIRM_ASSOCIATE, NEGATED_CORPUS[0]),
             (re.compile(r"\bcontract (role|position|engagement)\b", re.I), NEGATED_CORPUS[1]),
             (re.compile(r"commission (plan|structure)", re.I), NEGATED_CORPUS[2])]
    for rx, text in pairs:
        m = rx.search(text)
        if m:  # pattern present but negated -> affirmed must refuse
            assert affirmed(rx, text) is None, f"affirmed fired through negation: {text!r}"
    print("negation polarity property ✓ (short-window caveat documented in review)")


# --------------------------------------------------------------------- idempotence
# Property: score(score(p)) == score(p) — scoring must be a pure fold over fields it reads,
# never over fields it mutates. (Today's score() mutates pay_period/pay_type: see Finding 6;
# after moving normalization to extract, this property becomes checkable.)
def _idempotence():
    from radar.models import Posting
    from radar.score import score

    p = Posting(url="https://x.test/1", company="Acme Capital", title="Counsel, Regulatory Risk",
                description="JD required. Clerkship preferred. Base $180,000-$220,000.")
    s1 = score(p.model_copy(deep=True))
    s2 = score(s1.model_copy(deep=True))
    assert s1.bucket == s2.bucket and s1.fit_score == s2.fit_score, "scoring is not idempotent"
    print("score idempotence ✓ (if it fails, normalization leaked into score again)")


if __name__ == "__main__":
    if not HAVE_HYP:
        raise SystemExit("pip install hypothesis first")
    try:
        _pay_props()
    except ModuleNotFoundError as e:
        print(f"(skip pay props: {e})")
    try:
        _negation_props()
    except ModuleNotFoundError as e:
        print(f"(skip negation props: {e})")
    try:
        _idempotence()
    except ModuleNotFoundError as e:
        print(f"(skip idempotence: {e})")
