"""The CLAUDE.md rubric: hard excludes, fit signals, bucket.

Rules run on every posting. Judgment calls (sales-attached, domain-years floor, litigation
accepted) come from subagent judgments cached in data/judgments.jsonl when available, and
from conservative regex approximations otherwise.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import config
from .extract import IN_AREA, years_mentions
from .keywords import flags
from .models import Posting
from .textutil import snippet

PIPELINE = ("marqeta", "harvey", "hebbia", "norm ai", "normai", "general legal")
JUDGMENTS = config.DATA / "judgments.jsonl"
FIT_MIN = 3  # signals needed for the fit table

RX = {
    "clerkship": re.compile(r"clerkship|judicial clerk", re.I),
    "litigation": re.compile(r"litigat(ion|or|ing)[^.\n]{0,60}(experience|background|practice|skills)|(experience|background)[^.\n]{0,60}litigat|former litigators?|litigators?", re.I),
    "fs_background": re.compile(r"financial services|financial institution|broker[- ]dealer|bank(ing)? (experience|background|regulat)|capital markets experience", re.I),
    "research_for_decisions": re.compile(r"(research|analy[sz]|memo|advis|interpret|assess)[^.\n]{0,80}(regulat|legal|law|polic|rule)|(regulat|legal|polic)[^.\n]{0,80}(research|analysis|memo|advice|advis|guidance)", re.I),
    "teaches_finance": re.compile(r"no (prior |previous )?(finance|financial|investing) (experience|background|knowledge)|no previous finance|we(’|')?ll teach|we will teach|training program|\bacademy\b|rotational program|no prior experience (in|with) (finance|investing)", re.I),
    "credit": re.compile(r"\bcredit\b|distressed|bankruptcy|restructuring|covenant|leveraged loan|high[- ]yield|special situations|\bLME\b|liability management|chapter 11", re.I),
    "fintech": re.compile(r"fintech|payments?\b|crypto|digital assets?|stablecoin|blockchain|\bAI\b|artificial intelligence|machine learning|\bLLMs?\b|market structure|prediction markets?|exchange|trading", re.I),
}
EXCL = {
    "sales_title": re.compile(r"account executive|\bsales\b|pre-?sales|solutions (engineer|consultant)|business development rep", re.I),
    "demo": re.compile(r"(run|deliver|lead|conduct)[^.\n]{0,30}demos?|pre-?sales|prospects?\b|sales (cycle|team|process|pipeline)|close deals|quota", re.I),
    "quant_title": re.compile(r"\bquant|quantitative research|data scien|statistician|machine learning", re.I),
    "python": re.compile(r"python[^.\n]{0,60}(required|must|proficien)|(proficien|fluen|expert|strong)[^.\n]{0,40}(python|statistic|econometric)", re.I),
    "er_banking": re.compile(r"\b([5-9]|1\d)(?:\s*(?:-|–|—|to)\s*\d{1,2})?\s*\+?\s*(\+|or more)?\s*years?[^.\n]{0,90}(equity research|investment banking|\bbanking\b|buy[- ]side|hedge fund|private equity|investment (research|experience|analyst)|fundamental (equity|investing))", re.I),
    "comp_ops_title": re.compile(r"paralegal|document review|compliance (analyst|specialist|associate|officer|operations)|\bkyc\b|\baml\b|surveillance|legal (assistant|secretary)|docketing", re.I),
    "contract": re.compile(r"\bcontract(or)?\b[^.\n]{0,40}(role|position|basis|engagement)|part[- ]time|\bfreelance\b|\b\d+[- ]week\b", re.I),
}
LAWYER_TITLE = re.compile(r"counsel|attorney|lawyer|legal", re.I)
# in-house practice areas outside what he wants (CLAUDE.md: no generic transactional/admin seats)
OFF_TARGET_PRACTICE = re.compile(
    r"employment|labor|real estate|commercial|corporate|securities|\bM&A\b|mergers|transactions?\b|\bIP\b|intellectual property|"
    r"patent|trademark|\btax\b|benefits|immigration|procurement|contracts?\b|privacy(?! ?& ?regulatory| and regulatory)|"
    r"capital markets|venture|emerging companies|investment funds|funds? formation|real assets|energy|healthcare|entertainment",
    re.I,
)
TARGET_PRACTICE = re.compile(r"regulat|policy|risk|payments|credit|litigation|investigat|enforcement|compliance counsel|product counsel|governance|crypto|digital asset|stablecoin|derivatives|market", re.I)
LAW_FIRM_ASSOCIATE = re.compile(r"\bbillable|our (attorneys|lawyers|clients)|law firm associate|join our [\w ]*(practice|group)|am ?law", re.I)
# Seth, 2026-09-25: law firms are out for lifestyle reasons, government is out on pay; listed pay must clear $150K
# no \b after the suffix: "Smith, P.C." ends in a dot, so a trailing word boundary never matched
LAW_FIRM_NAME = re.compile(r"(?<![\w.])(LLP|L\.L\.P\.|PLLC|P\.C\.|P\.A\.|LPA)(?!\w)|\blaw (firm|group|offices?)\b|\battorneys at law\b", re.I)
# Seth, 2026-09-28: knowledge-management / practice-support lawyers at firms are non-billable. Still a law-firm seat
# (poor match), but a reviewable one: output.near_misses() lets these through instead of treating them as settled.
LAW_FIRM_NONBILLABLE_TITLE = re.compile(
    r"knowledge management|\bKM (lawyer|attorney|counsel)\b|practice support|professional support (lawyer|attorney)|"
    r"practice (attorney|lawyer)|research (attorney|lawyer|counsel)|legal research counsel",
    re.I,
)
LAW_FIRM_NONBILLABLE_REASON = "Law-firm seat, non-billable (knowledge/practice support)"
LAW_FIRM_TEXT = re.compile(r"\bbillable hours?\b|\bam ?law\b|\bour (law )?firm(’|')?s? (attorneys|lawyers|partners|clients)\b", re.I)
GOVERNMENT_NAME = re.compile(
    r"\bdepartment of\b|\boffice of the\b|attorney general|comptroller|\bstate of\b|\bcity of\b|\bcounty\b|"
    r"\bNYS\b|new york state|\bU\.?S\.? (securities|department|attorney)|\bsecurities and exchange commission\b|"
    r"\bcommodity futures trading commission\b|\bFDIC\b|comptroller of the currency|\bCFPB\b|consumer financial protection bureau|"
    r"\bFinCEN\b|district attorney|public defender|\bcourts?\b.*\b(unified|judiciary)\b|"
    r"\blaw department\b|\bcorporation counsel\b|\bnew york city\b.*\b(department|office|agency|commission)\b",
    re.I,
)
QUASI_PUBLIC_OK = ("public_sector:finra", "public_sector:ny_fed")  # SRO and the NY Fed pay private-sector ranges; the pay floor decides
PAY_FLOOR = 150_000
ANNUALIZE = {"hour": 2080, "month": 12}  # monthly and hourly figures are compared to the floor as annual pay
FUND_LIKE = re.compile(r"capital|funding|partners|assets|finance", re.I)
# "Unlike firm roles, we do not track billable hours", "not a contract position": a negated mention is not the thing
NEGATION = re.compile(r"\b(not|no|never|without|unlike|don[’']t|doesn[’']t)\b|\bnon-", re.I)


def affirmed(rx: re.Pattern, text: str) -> re.Match | None:
    """First match of rx not negated within ~30 characters before it in the same sentence."""
    for m in rx.finditer(text or ""):
        pre = re.split(r"[.;!?\n]", text[max(0, m.start() - 30) : m.start()])[-1]
        if not NEGATION.search(pre):
            return m
    return None
CONTRACT_PLATFORM = re.compile(r"^axiom\b|talent platform", re.I)  # Axiom places lawyers on engagements
NOT_A_SEAT = re.compile(r"coffee chat|case competition|talent (network|community|pool)|expression of interest|"
                        r"general interest|future opportunit|open application", re.I)


def is_government(p: Posting) -> bool:
    src = [s for s in p.sources if s.startswith(("public_sector:", "official_apis:usajobs"))]
    if src and not all(s in QUASI_PUBLIC_OK for s in src):
        return True
    return p.ats == "nyag" or bool(GOVERNMENT_NAME.search(p.company or ""))


def is_law_firm(p: Posting) -> bool:
    return bool(LAW_FIRM_NAME.search(p.company or "") or affirmed(LAW_FIRM_TEXT, p.description or ""))


def law_firm_title_carveout(p: Posting) -> bool:
    """An underwriting/research/analyst title at an LLP-named fund ("Longford Capital Fund LLP") is not a law-firm seat.
    Only a name-only firm signal on a fund-like name qualifies; billable-hours text in the posting means a real firm."""
    return bool(re.search(r"underwrit|research|analyst", p.title, re.I) and LAW_FIRM_NAME.search(p.company or "")
                and FUND_LIKE.search(p.company or "") and not affirmed(LAW_FIRM_TEXT, p.description or ""))


def desc_hash(p: Posting) -> str:
    return hashlib.sha1((p.title + "\n" + p.description[:20000]).encode("utf-8", "ignore")).hexdigest()[:16]


_judg: dict[str, dict] | None = None


def _role_key(company: str, title: str) -> str:
    from .textutil import norm_company, norm_title

    return f"role:{norm_company(company)}|{norm_title(title)}"


def judgments() -> dict[str, dict]:
    """Latest judgment per posting key, plus a company+title index so re-posted roles reuse it. The company+title
    entries apply only to a posting with the same desc_hash (see role_judgment); a direct key match always applies."""
    global _judg
    if _judg is None:
        _judg = {}
        if JUDGMENTS.exists():
            from .db import get_posting

            for line in JUDGMENTS.read_text(encoding="utf-8").split("\n"):
                if line.strip():
                    d = json.loads(line)
                    _judg[d["key"]] = d
                    if (p := get_posting(d["key"])):
                        _judg[_role_key(p.company, p.title)] = d
    return _judg


def role_judgment(p: Posting) -> dict | None:
    """The company+title judgment, only when it was made on this exact text (same desc_hash)."""
    j = judgments().get(_role_key(p.company, p.title))
    return j if j and j.get("desc_hash") and j.get("desc_hash") == desc_hash(p) else None


def judgment_for(p: Posting) -> dict | None:
    return judgments().get(p.key) or role_judgment(p)


SEAT_FAMILIES = [  # CLAUDE.md: the seat families that loosen the Stage 2 domain-years screen
    ("litigation-finance underwriting", r"underwrit", r"litigation_finance|legal assets|litigation financ"),
    ("legal-AI research/build seat", r"applied legal research|legal research|legal engineer|r&d attorney|legal fellow", r"legal_ai|legal ai|\bai\b"),
    ("business-side regulatory risk", r"regulatory (risk|exam|engagement|relations)|regulatory risk", r""),
    # context required: "RBT Academy" (behavior technicians) and "Rotational Project Associate" (construction) matched before
    ("employer-run finance academy", r"academy|rotational|investment analyst program|client investment research",
     r"invest|financ|fund|trading|capital markets|hedge|asset manage|portfolio"),
    ("embedded qualitative research", r"fundamental research|market intelligence|\bcanvas\b", r""),
]


def seat_family(p: Posting) -> str:
    ctx = f"{p.company} {p.segment or ''} {p.description[:3000]}"
    for name, title_rx, ctx_rx in SEAT_FAMILIES:
        if re.search(title_rx, p.title, re.I) and (not ctx_rx or re.search(ctx_rx, ctx, re.I)):
            return name
    return ""


def is_pipeline(company: str) -> bool:
    c = company.lower()
    return any(c.startswith(x) for x in PIPELINE)


def score(p: Posting) -> Posting:
    text = p.description or ""
    title = p.title
    both = title + "\n" + text
    j = judgment_for(p)
    sig: list[str] = []
    excl: list[str] = []
    poor: list[str] = []

    # ------------------------------------------------------------ hard excludes
    if p.pay_type == "OTE" or re.search(r"\bOTE\b|on[- ]target earnings", both):
        excl.append("Pay is quoted as OTE (variable-heavy)")
    sales = (j or {}).get("sales_attached")
    if sales is None:
        sales = "Y" if (EXCL["sales_title"].search(title) or (re.search(r"legal engineer|solutions", title, re.I) and EXCL["demo"].search(text))) else "N"
    p.sales_attached = sales
    if sales == "Y":
        q = (j or {}).get("rationale") or snippet(text, EXCL["demo"]) or title
        excl.append(f"Sales-attached / demo-led role: {q}")
    if "6+ years leveraged finance" in flags(text):
        excl.append("Asks for 6+ years of leveraged-finance or transactional practice: " + snippet(text, r"\b([6-9]|1\d)\+?[^.\n]{0,80}(leveraged finance|transactional|finance practice)"))
    if EXCL["quant_title"].search(title) or EXCL["python"].search(text):
        excl.append("Requires Python, statistics or quant work: " + (snippet(text, EXCL["python"]) or title))
    if EXCL["er_banking"].search(text):
        excl.append("Asks for 5+ years of equity research, banking or buy-side: " + snippet(text, EXCL["er_banking"]))
    ym = years_mentions(text)
    if any(y.lo >= 10 for y in ym):
        y = next(y for y in ym if y.lo >= 10)
        excl.append(f"Asks for 10+ years: “{y.context}”")
    if EXCL["comp_ops_title"].search(title) and not re.search(r"counsel|attorney", title, re.I):
        excl.append("Paralegal, document review or compliance-operations role")
    if j and j.get("override_regex_exclude"):
        # a judge read the posting and found the pattern misfired ("not a commission role", "statistics a plus");
        # structured OTE pay from the ATS is data, not a pattern, so it stands
        excl = [e for e in excl if e.startswith("Pay is quoted as OTE") and p.pay_type == "OTE"]
    if j and j.get("hard_exclude"):
        excl.append(j["hard_exclude"])

    # --------------------------------------------------------------- fit signals
    if p.jd_required in ("Y", "pref") or (j or {}).get("jd") in ("Y", "pref"):
        sig.append("JD required/preferred")
    if RX["clerkship"].search(text):
        sig.append("clerkship valued")
    lit = (j or {}).get("litigation_accepted")
    p.litigation_accepted = lit or ("Y" if RX["litigation"].search(text) else "unclear")
    if p.litigation_accepted == "Y":
        sig.append("litigation experience accepted")
    if RX["fs_background"].search(text):
        sig.append("financial-services background a plus")
    if RX["research_for_decisions"].search(both):
        sig.append("regulatory/legal/policy research for decisions")
    if RX["teaches_finance"].search(both):
        sig.append("employer teaches the finance")
    if RX["credit"].search(both):
        sig.append("credit/distressed/bankruptcy subject")
    if RX["fintech"].search(both):
        sig.append("fintech/crypto/AI/market-structure subject")
    per = ANNUALIZE.get(p.pay_period or "year", 1)
    if p.pay_type == "base" and p.pay_min and ((p.pay_min + (p.pay_max or p.pay_min)) / 2) * per >= 150_000:
        sig.append("base pay midpoint ≥ $150K")
    if p.years_required is not None and 2 <= p.years_required <= 5:
        sig.append(f"{p.years_required} years required (2–5 band)")

    # ------------------------------------------------------ poor-match (not hard)
    # employer-level and pay reasons first: they settle the row whatever else the posting says
    if is_government(p):
        poor.append("Government seat (pay ceiling below his target)")
    elif is_law_firm(p) and not law_firm_title_carveout(p):
        if LAW_FIRM_NONBILLABLE_TITLE.search(title):
            poor.append(f"{LAW_FIRM_NONBILLABLE_REASON}: still a law firm, but no billable hours or court time")
        else:
            poor.append("Law-firm seat (lifestyle)")
    top = p.pay_max or p.pay_min
    if p.pay_type == "base" and top and (p.pay_period or "year") in ("year", "annual", "", "month", "hour") and top * per < PAY_FLOOR:
        poor.append(f"Listed pay tops out below $150K ({p.pay_display})")
    floor = (j or {}).get("meets_floor")
    fy = (j or {}).get("domain_floor_years")
    dom = (j or {}).get("domain") or ""
    if floor == "N" or (isinstance(fy, int) and fy >= 6):
        poor.append((f"Asks for {fy}+ years of {dom}" if fy else f"Wants {dom} experience he doesn't have")
                    + (f": {j['rationale']}" if j.get("rationale") else ""))
    elif dom and OFF_TARGET_PRACTICE.search(dom) and not TARGET_PRACTICE.search(dom):
        poor.append(f"Generalist or off-target practice seat (wants {dom})")
    elif not j and p.years_required is not None and p.years_required >= 6:
        poor.append(f"Asks for {p.years_required}+ years: “{p.years_text}”")
    if ym and max((y.hi or y.lo) for y in ym) <= 2 and p.years_required is not None and p.years_required <= 1:
        poor.append(f"Pitched at {p.years_required}–{max((y.hi or y.lo) for y in ym)} years of experience")
    t_core = re.sub(r"\s*@.*$", "", title)  # "Counsel @ Riskified": the employer name isn't the practice area
    if (LAWYER_TITLE.search(t_core) or re.search(r"\bassociate\b", t_core, re.I)) and OFF_TARGET_PRACTICE.search(t_core) and not TARGET_PRACTICE.search(t_core):
        poor.append(f"Practice area outside the target seats ({OFF_TARGET_PRACTICE.search(t_core).group(0).lower()} work)")
    if re.search(r"\bassociate\b", title, re.I) and LAW_FIRM_ASSOCIATE.search(text) and not re.search(r"underwrit|research|analyst", title, re.I):
        poor.append("Law-firm associate seat (billable practice, court time)")
    if CONTRACT_PLATFORM.search(p.company or ""):
        poor.append("Contract-lawyer platform (engagements, not an employee seat)")
    if NOT_A_SEAT.search(title):
        poor.append("Event, talent pool or open application, not a seat")
    if p.pay_type == "hourly" or affirmed(EXCL["contract"], title + " " + text[:1500]):
        poor.append("Contract, hourly or part-time engagement" + (f" ({p.pay_display})" if p.pay_type == "hourly" else ""))

    p.fit_signals = sig
    p.fit_score = len(sig)
    p.hard_exclude_reason = excl[0] if excl else ""
    family = seat_family(p)
    if family:
        p.fit_signals = sig + [f"seat family: {family}"]  # shown in jobs.csv; not counted as a rubric signal
    if not p.hard_exclude_reason and not poor and p.fit_score < FIT_MIN and not family:
        poor.append(f"Weak fit: {p.fit_score} of 10 signals" + (f" ({', '.join(sig)})" if sig else ""))
    p.poor_reason = p.hard_exclude_reason or "; ".join(poor)
    p.domain_floor = ((f"{fy}+ yrs " if fy is not None else "") + f"{dom} (meets: {floor})") if dom else ""
    p.judgment_rationale = (j or {}).get("rationale", "")
    p.pipeline = is_pipeline(p.company)

    if p.status != "open":
        p.bucket = "closed"
    elif p.loc_bucket not in IN_AREA:
        p.bucket = "outside" if p.loc_bucket in ("us_other", "unknown") else "irrelevant"
    elif p.poor_reason:
        # the markdown poor-match table keeps target-family seats and near-fits; the long tail stays in jobs.csv
        from .keywords import title_families

        strong = [f for f in title_families(title) if f not in ("counsel/attorney", "regulatory (other)", "policy (other)", "litigation")]
        p.bucket = "poor" if (p.fit_score >= 3 or strong or "seed" in p.sources) else "low"
    else:
        p.bucket = "fit"
    return p
