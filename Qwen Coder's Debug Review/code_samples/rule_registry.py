"""Sample: rule-registry scoring core — the shape suggested in 04-Architecture §A.

Self-contained (no radar imports). Shows:
  - rules as data with ids, effects, gates, precedence
  - judgment overrides expressed as targeted VETOs keyed by rule id (not a blunt flag)
  - attribution: every verdict carries the rule ids that produced it (feeds golden replay & telemetry)

Run:  python rule_registry.py       (prints scored examples incl. two known misfire strings)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Effect(Enum):
    HARD_EXCLUDE = "hard_exclude"
    POOR = "poor"
    SIGNAL = "signal"
    VETO = "veto"          # suppresses other rules by id


@dataclass(frozen=True)
class Rule:
    id: str
    effect: Effect
    fire: Callable[["Ctx"], str | None]           # returns evidence string or None
    when: Callable[["Ctx"], bool] = lambda c: True
    message: str = "{evidence}"
    suppresses: tuple[str, ...] = ()              # only meaningful for VETO


@dataclass
class Posting:
    title: str
    company: str
    description: str
    pay_min: float | None = None
    pay_max: float | None = None
    pay_type: str = "base"
    years_required: int | None = None


@dataclass
class Ctx:
    p: Posting
    judgment: dict | None = None

    @property
    def lawyer(self) -> bool:
        return bool(re.search(r"counsel|attorney|lawyer|legal", self.p.title, re.I))

    @property
    def text(self) -> str:
        return self.p.title + "\n" + self.p.description


# ------------------------------------------------------------------ the registry
LAWYER = lambda c: c.lawyer
NOT_LAWYER = lambda c: not c.lawyer

RULES: list[Rule] = [
    # --- hard excludes (mirroring radar/score.py EXCL, each now addressable) ---
    Rule("ote_pay", Effect.HARD_EXCLUDE,
         lambda c: "OTE" if (c.p.pay_type == "OTE" or re.search(r"\bOTE\b|on[- ]target earnings", c.text)) else None),
    Rule("sales_title", Effect.HARD_EXCLUDE,
         lambda c: m.group(0) if (m := re.search(r"account executive|\bsales\b|pre-?sales|business development rep", c.p.title, re.I)) else None,
         when=NOT_LAWYER),
    Rule("demo_led", Effect.HARD_EXCLUDE,
         lambda c: snippet(c.text, r"(run|deliver|lead)[^\n]{0,30}demos?|close deals|quota"),
         when=lambda c: bool(re.search(r"legal engineer|solutions", c.p.title, re.I))),
    Rule("python_required", Effect.HARD_EXCLUDE,
         lambda c: m.group(0) if (m := re.search(r"python[^\n]{0,60}(required|must|proficien)", c.text, re.I))
         and not re.search(r"plus|preferred|nice[- ]to[- ]have", c.text[m.end():m.end()+40], re.I) else None),
    Rule("ten_years_ask", Effect.HARD_EXCLUDE,
         lambda c: m.group(0) if (m := re.search(r"\b(?:1\d|[1-9]\d?)\+\s*years?\b[^\n]{0,40}experience", c.text, re.I))
         and int(m.group(0).split()[0].rstrip("+")) >= 10 else None),

    # --- carveouts become first-class VETO rules, evaluated with priority ---
    Rule("lawyer_supports_sales_veto", Effect.VETO,
         lambda c: "in-house legal seat; sales mention is who they support, not what they do"
         if c.lawyer and re.search(r"\bsales\b", c.text, re.I) else None,
         suppresses=("sales_title", "demo_led")),
    Rule("judge_veto", Effect.VETO,
         lambda c: f"human judge vetoed {sorted(c.judgment['vetoes'])}: {c.judgment.get('reason','')}"
         if c.judgment and c.judgment.get("vetoes") else None,
         suppresses=()),   # dynamic suppression handled in fold via judgment["vetoes"]

    # --- poor-match rules ---
    Rule("pay_floor", Effect.POOR,
         lambda c: f"top ${c.p.pay_max:,.0f} < $150K" if c.p.pay_type == "base" and c.p.pay_max and c.p.pay_max < 150_000 else None),
    Rule("domain_years_floor", Effect.POOR,
         lambda c: f"asks {c.p.years_required}+ yrs domain" if not c.lawyer and (c.p.years_required or 0) >= 6 else None),

    # --- fit signals ---
    Rule("jd_signal", Effect.SIGNAL,
         lambda c: "JD required/preferred" if re.search(r"\bJ\.?D\.?\b", c.text, re.I) else None),
    Rule("clerkship_signal", Effect.SIGNAL,
         lambda c: "clerkship valued" if re.search(r"clerkship|judicial clerk", c.text, re.I) else None),
    Rule("credit_signal", Effect.SIGNAL,
         lambda c: "credit/distressed subject" if re.search(r"\bcredit\b|bankruptcy|restructuring|distressed", c.text, re.I) else None),
    Rule("pay_signal", Effect.SIGNAL,
         lambda c: "base ≥ $150K" if c.p.pay_type == "base" and c.p.pay_min and c.p.pay_min >= 150_000 else None),
]

ORDER = {Effect.VETO: 0, Effect.HARD_EXCLUDE: 1, Effect.POOR: 2, Effect.SIGNAL: 3}


def snippet(text: str, rx: str) -> str | None:
    m = re.search(rx, text, re.I)
    return m.group(0)[:80] if m else None


@dataclass
class Verdict:
    bucket: str
    reasons: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    fired_ids: list[str] = field(default_factory=list)


def score(p: Posting, judgment: dict | None = None, fit_min: int = 3) -> Verdict:
    ctx = Ctx(p, judgment)
    fired: dict[str, str] = {}
    vetoes: set[str] = set()
    for rule in sorted(RULES, key=lambda r: ORDER[r.effect]):
        if not rule.when(ctx):
            continue
        ev = rule.fire(ctx)
        if ev is None:
            continue
        if rule.effect is Effect.VETO:
            vetoes.update(rule.suppresses)
            if judgment and rule.id == "judge_veto":
                vetoes.update(judgment["vetoes"])     # targeted, named vetoes — the key upgrade
        else:
            fired[rule.id] = rule.message.format(evidence=ev)

    excluded = {k: v for k, v in fired.items() if k not in vetoes and k in
                {r.id for r in RULES if r.effect is Effect.HARD_EXCLUDE}}
    poor = {k: v for k, v in fired.items() if k not in vetoes and k in
            {r.id for r in RULES if r.effect is Effect.POOR}}
    sig = {k: v for k, v in fired.items() if k not in vetoes and k in
           {r.id for r in RULES if r.effect is Effect.SIGNAL}}

    if excluded:
        bucket, reasons = "hard-exclude", list(excluded.values())
    elif poor:
        bucket, reasons = "poor", list(poor.values())
    elif len(sig) < fit_min:
        bucket, reasons = "low", [f"weak fit: {len(sig)} signals"]
    else:
        bucket, reasons = "fit", []
    return Verdict(bucket, reasons, list(sig.values()), sorted(fired))


if __name__ == "__main__":
    cases = [
        ("Sales Counsel, Growth", "Stripe", "In-house counsel supporting the sales org. No quota. JD required.", 200_000, 260_000),
        ("Account Executive", "LegalAI Co", "JD preferred! Carry quota, run demos, close deals.", 90_000, 300_000),
        ("Senior Counsel — Restructuring", "Moelis", "Bankruptcy and credit restructuring advisory; clerkship preferred; JD required.", 210_000, 300_000),
        ("Credit Risk Manager", "SomeFund", "Requires Python proficiency and 8+ years experience in leveraged finance.", None, None),
    ]
    for title, company, desc, lo, hi in cases:
        p = Posting(title, company, desc, lo, hi)
        v = score(p)
        print(f"{title!r:45} -> {v.bucket:12} {v.reasons or v.signals}  fired={v.fired_ids}")

    # the blunt old flag vs the new targeted veto
    tricky = Posting("Solutions Engineer (Legal AI)", "Harvey", "Runs demos for prospects; JD preferred; AI subject matter.", 160_000, 220_000)
    print("\nno judgment :", score(tricky).bucket)
    judged = score(tricky, {"vetoes": ["demo_led"], "reason": "post-sales SE, no quota in posting"})
    print("judge veto  :", judged.bucket, judged.fired_ids)
