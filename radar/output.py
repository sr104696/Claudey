"""Phase 5: out/open_positions_<date>.md, out/jobs.csv, out/diff_<date>.md, data/snapshots/<date>.csv."""
from __future__ import annotations

import csv
import datetime as dt
import json

from . import config, seen
from .extract import is_metro_north
from .models import Posting
from .phase1 import ap_date
from .score import LAW_FIRM_NONBILLABLE_REASON
from .seeds import parse_current_list
from .textutil import norm_company, norm_title

SNAP_DIR = config.DATA / "snapshots"
CSV_FIELDS = ["bucket", "is_new", "fit_score", "company", "title", "url", "location", "loc_bucket", "workplace",
              "pay_display", "pay_min", "pay_max", "pay_type", "pay_period", "pay_source", "years_required", "years_text",
              "jd_required", "sales_attached", "litigation_accepted", "domain_floor", "hard_exclude_reason", "poor_reason",
              "fit_signals", "judgment_rationale", "posted_date", "closes_date", "status", "status_evidence", "verified_at",
              "via_aggregator", "pipeline", "sources", "ats", "board", "job_id", "key", "seen_before", "decision"]


def _match_key(ats=None, board=None, job_id=None, url=None, company: str = "", title: str = "") -> str:
    """Identity of one req across runs: the ATS job id when there is one, else the URL, else company + title.
    (A truncated company + title key merged two same-title reqs on one board into one row.)"""
    if ats and job_id:
        return f"{ats}:{board or ''}:{job_id}"
    if url:
        return url
    return f"{norm_company(company)}|{norm_title(title)}"


def _row_key(r: dict) -> str:
    return _match_key(r.get("ats"), r.get("board"), r.get("job_id"), r.get("url"), r.get("company") or "", r.get("title") or "")


def _post_key(p: Posting) -> str:
    return _match_key(p.ats, p.board, p.job_id, p.url, p.company, p.title)


def _name_key(company: str, title: str) -> str:
    return f"{norm_company(company)}|{norm_title(title)}"


def previous_rows(run: str) -> tuple[str, list[dict]]:
    """Last run's snapshot, or the hand-built seed list on the first run."""
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    prior = sorted(p for p in SNAP_DIR.glob("*.csv") if p.stem < run)
    if prior:
        with open(prior[-1], newline="", encoding="utf-8") as f:
            return prior[-1].stem, list(csv.DictReader(f))
    rows, _ = parse_current_list()
    return "seed list", [{"company": r.company, "title": r.title, "url": r.url, "pay_display": r.pay, "bucket": r.section,
                          "status": "open", "years_required": "", "jd_required": ""} for r in rows]


def _esc(s) -> str:
    return str(s or "").replace("|", "\\|").replace("\n", " ")


def _loc(p: Posting) -> str:
    locs = p.locations or [p.location]
    s = "; ".join(locs[:3]) + (f" (+{len(locs) - 3} more)" if len(locs) > 3 else "")
    if p.workplace and p.workplace not in s.lower():
        s += f", {p.workplace}"
    s = s or "Not stated"
    if p.loc_bucket == "nyc_commutable":
        s += " (commutable)"
    elif p.loc_bucket not in ("nyc", "us_remote") and is_metro_north(locs):
        s += " (Metro-North ~1 hr, hybrid only)"
    return s


def _date_desc(d: str | None) -> int:
    """Sort key for fresher-first: negative ordinal, undated rows last."""
    try:
        return -dt.date.fromisoformat((d or "")[:10]).toordinal()
    except ValueError:
        return 0


def _position(p: Posting, new: bool) -> str:
    cell = f"[{_esc(p.title)}]({p.url})"
    if p.closes_date and p.closes_date >= dt.date.today().isoformat():
        cell += f" (apply by {ap_date(p.closes_date)})"
    if new:
        cell += " †"
    if p.via_aggregator:
        cell += f" (aggregator link: {p.via_aggregator})"
    return cell


def _company(p: Posting) -> str:
    return _esc(p.company) + (" (already in your pipeline)" if p.pipeline else "")


def is_thesis(p: Posting) -> bool:
    return any(s.startswith("seat family:") for s in p.fit_signals)


def fit_order(p: Posting):
    """One table, most promising first: seat families that loosen the domain-years screen, then rows whose
    domain floor he meets, then listed pay ($200K+ first, per Seth), then rubric signals, then fresher postings."""
    top = p.pay_max or p.pay_min or 0
    mid = ((p.pay_min or top) + top) / 2 if top else 0
    tier = 2 if mid >= 200_000 else 1 if mid >= 150_000 else 0
    return (not is_thesis(p), "(meets: Y)" not in (p.domain_floor or ""), -tier, -p.fit_score, -top, _date_desc(p.posted_date), p.company)


NEAR_MISS_MAX = 12
_SETTLED = ("Government seat", "Law-firm seat", "Law-firm associate seat", "Listed pay tops out")


def near_misses(posts: list[Posting], ledger: "seen.Ledger | None" = None, decisions: "seen.Decisions | None" = None) -> list[Posting]:
    """Poor-match rows closest to the line: soft reasons with 4+ signals, or pattern excludes on 5+ signals.
    With a ledger, rows an earlier digest already asked about (or that he has ruled on) are skipped, so each run's
    digest is twelve questions he hasn't answered."""
    def close(p: Posting) -> bool:
        # the non-billable law-firm reason starts "Law-firm seat" too, but it is reviewable, not settled
        reason = p.poor_reason.replace(LAW_FIRM_NONBILLABLE_REASON, "")
        if p.bucket != "poor" or any(s in reason for s in _SETTLED):
            return False
        if ledger and ledger.seen(p, "near_miss"):
            return False
        if decisions and decisions.for_posting(p) in seen.HIDE_FROM_DIGEST:
            return False
        return (not p.hard_exclude_reason and p.fit_score >= 4) or p.fit_score >= 5
    return sorted([p for p in posts if close(p)], key=lambda p: (-p.fit_score, -(p.pay_max or p.pay_min or 0), p.company))[:NEAR_MISS_MAX]


def write_near_miss(posts: list[Posting], today: dt.date, ledger: "seen.Ledger | None" = None,
                    decisions: "seen.Decisions | None" = None) -> tuple[str, list[Posting]]:
    rows = near_misses(posts, ledger, decisions)
    L = ["# Near misses", "", f"Run {ap_date(today)}. The {len(rows)} poor-match rows closest to the fit line that you haven't been asked about. "
         "Reply per row with **fit** (the rule was wrong), **right call**, or a one-line reason; "
         "those replies become rubric and keyword changes.", "",
         "| # | Position | Company | Listed pay | Signals | Why it missed |", "|---|---|---|---|---|---|"]
    L += [f"| {i} | [{_esc(p.title)}]({p.url}) | {_company(p)} | {_esc(p.pay_display)} | {p.fit_score} | {_esc(p.poor_reason)[:220]} |"
          for i, p in enumerate(rows, 1)] or ["", "None new this run."]
    path = config.OUT / f"near_miss_{today.isoformat()}.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(path), rows


def write(posts: list[Posting], closed_notes: list[str], stats: dict) -> dict:
    run = config.today()
    base_label, prev = previous_rows(run)
    # key -> every prior row with it, so a collision can't silently drop a row from the diff
    prev_by_url: dict[str, list[dict]] = {}
    prev_by_key: dict[str, list[dict]] = {}
    prev_by_name: dict[str, list[dict]] = {}  # rows without a job id (seed list, page postings)
    for r in prev:
        if r.get("url"):
            prev_by_url.setdefault(r["url"], []).append(r)
        prev_by_key.setdefault(_row_key(r), []).append(r)
        if not r.get("job_id"):
            prev_by_name.setdefault(_name_key(r.get("company") or "", r.get("title") or ""), []).append(r)

    def prior(p: Posting) -> dict | None:
        hit = prev_by_url.get(p.url) or prev_by_key.get(_post_key(p))
        if not hit:
            # a seed-list or page row matches by name only when that name is unambiguous on both sides
            hit = prev_by_name.get(_name_key(p.company, p.title))
            if hit and (len(hit) > 1 or name_count.get(_name_key(p.company, p.title), 0) > 1):
                hit = None
        return hit[0] if hit else None

    name_count: dict[str, int] = {}
    for p in posts:
        name_count[_name_key(p.company, p.title)] = name_count.get(_name_key(p.company, p.title), 0) + 1

    # "new" means no earlier run presented this posting on this surface (see radar/seen.py), not merely "absent from
    # last run's snapshot": a posting that closed and came back, or a near miss that became a fit, is judged on
    # what Seth has actually been shown. Rows he applied to or dismissed are never new.
    ledger = seen.Ledger.load(run, SNAP_DIR, config.OUT)
    decisions = seen.Decisions.load()
    decided = {p.key: decisions.for_posting(p) for p in posts}
    handled = {k for k, d in decided.items() if d in seen.HIDE_EVERYWHERE}
    already = {p.key: ledger.seen(p, seen.BUCKET_SURFACE.get(p.bucket, "poor")) for p in posts}
    new = {p.key: not p.pipeline and not already[p.key] and p.key not in handled for p in posts}
    order = lambda p: (-p.fit_score, -(p.pay_max or p.pay_min or 0), p.company)
    fit = sorted([p for p in posts if p.bucket == "fit"], key=fit_order)
    poor = sorted([p for p in posts if p.bucket == "poor"], key=order)
    # Metro-North towns (Stamford, Greenwich, ...) first: out of area, but reachable for a hybrid seat
    outside = sorted([p for p in posts if p.bucket == "outside" and not p.poor_reason],
                     key=lambda p: (not is_metro_north(p.locations or [p.location]),) + order(p))
    # what this run presents: only postings he hasn't seen, plus his pipeline companies (tracked every run)
    fit_show = [p for p in fit if new[p.key] or (p.pipeline and p.key not in handled)]
    poor_show = [p for p in poor if new[p.key]]
    outside_show = [p for p in outside if new[p.key]]
    n_seen = sum(1 for p in posts if p.bucket in ("fit", "poor", "outside") and already[p.key] and p.key not in handled)
    n_handled = sum(1 for p in posts if p.key in handled)
    today = dt.date.today()

    L = ["# Open positions", "",
         f"Checked on {ap_date(today)}. Links go straight to each posting. This list holds only postings no earlier run "
         f"has shown you (plus your pipeline companies); {n_seen} already presented are still open and {n_handled} you "
         "have applied to or dismissed. The full running list is out/all_positions.md.", "",
         f"## New postings that fit your profile ({len(fit_show)})", "",
         "Best first: ★ marks the seat families where your background clears the domain-years screen, then roles whose "
         "experience bar you meet, then listed pay ($200K+ ahead of $150K+).", "",
         "| Position | Company | Location | Listed pay |", "|---|---|---|---|"]
    L += [f"| {'★ ' if is_thesis(p) else ''}{_position(p, False)} | {_company(p)} | {_esc(_loc(p))} | {_esc(p.pay_display)} |" for p in fit_show]
    L += ["", f"## New, but a poor match ({len(poor_show)})", "", "| Position | Company | Location | Listed pay | Why it's a poor match |", "|---|---|---|---|---|"]
    L += [f"| {_position(p, False)} | {_company(p)} | {_esc(_loc(p))} | {_esc(p.pay_display)} | {_esc(p.poor_reason)} |" for p in poor_show]
    L += ["", f"## New outside NYC / US-remote ({len(outside_show)})", "", "Roles elsewhere in the US that would otherwise fit. Weaker out-of-area matches are in jobs.csv.", "",
          "| Position | Company | Location | Listed pay | Fit |", "|---|---|---|---|---|"]
    L += [f"| {_position(p, False)} | {_company(p)} | {_esc(_loc(p))} | {_esc(p.pay_display)} | "
          f"Fit ({p.fit_score} signals) |" for p in outside_show]
    hidden = sum(1 for p in posts if p.bucket == "outside" and p.poor_reason) + sum(1 for p in posts if p.bucket == "low")
    L += ["", f"{hidden} weaker matches (out-of-area poor matches and the long tail) are in jobs.csv only."]
    L += ["", "## Checked, not open", ""]
    L += [f"- {n}" for n in closed_notes] or ["None."]
    md = config.OUT / f"open_positions_{today.isoformat()}.md"
    md.write_text("\n".join(L) + "\n", encoding="utf-8")

    rows = []
    for p in sorted(posts, key=lambda p: ({"fit": 0, "poor": 1, "outside": 2}.get(p.bucket, 3),) + order(p)):
        d = p.model_dump()
        d.update(is_new=int(new[p.key]), seen_before=int(already[p.key]), decision=decided[p.key],
                 fit_signals="; ".join(p.fit_signals), sources="; ".join(p.sources))
        rows.append({k: d.get(k, "") for k in CSV_FIELDS})
    for path in (config.OUT / "jobs.csv", SNAP_DIR / f"{run}.csv"):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            w.writeheader()
            w.writerows(rows)

    # ------------------------------------------------------------------- diff
    cur_keys = {_post_key(p) for p in posts} | {p.url for p in posts}
    matched = {id(r) for p in posts if (r := prior(p)) is not None}
    gone = [r for r in prev if id(r) not in matched and _row_key(r) not in cur_keys and r.get("url") not in cur_keys]
    changes = []
    for p in posts:
        r = prior(p)
        if not r:
            continue
        bits = []
        if r.get("pay_display") and r["pay_display"] != p.pay_display and not (r["pay_display"].startswith("$") is False and p.pay_display == "Not listed"):
            bits.append(f"pay {r['pay_display']} → {p.pay_display}")
        if r.get("years_required") not in (None, "") and str(r["years_required"]) != str(p.years_required or ""):
            bits.append(f"years required {r['years_required']} → {p.years_required}")
        if r.get("jd_required") and r["jd_required"] != p.jd_required:
            bits.append(f"JD {r['jd_required']} → {p.jd_required}")
        if r.get("bucket") and r["bucket"] != p.bucket:
            bits.append(f"moved {r['bucket']} → {p.bucket}")
        if bits:
            changes.append(f"- [{_esc(p.title)}]({p.url}), {_esc(p.company)}: " + "; ".join(bits))
    D = [f"# Changes since the last run ({base_label})", "", f"Run {run}.", "",
         f"## New ({sum(1 for p in posts if new[p.key] and p.bucket in ('fit', 'poor', 'outside'))})", "",
         "New means no earlier run has shown you the posting; reposts and rows you applied to or dismissed don't count.", ""]
    for b in ("fit", "poor", "outside"):
        ns = [p for p in posts if new[p.key] and p.bucket == b]
        if ns:
            D += [f"**{b}** ({len(ns)})", ""] + [f"- [{_esc(p.title)}]({p.url}), {_esc(p.company)}, {_esc(_loc(p))}, {p.pay_display}"
                                                 + (f", fit {p.fit_score}" if b != "poor" else f": {_esc(p.poor_reason)}") for p in sorted(ns, key=order)] + [""]
    D += [f"## Closed or no longer verifiable ({len(gone)})", ""] + [f"- {_esc(r['title'])}, {_esc(r['company'])} ({r['url']})" for r in gone]
    D += ["", f"## Pay or requirement changes ({len(changes)})", ""] + (changes or ["None."])
    diff = config.OUT / f"diff_{today.isoformat()}.md"
    diff.write_text("\n".join(D) + "\n", encoding="utf-8")

    near, near_rows = write_near_miss(posts, today, ledger, decisions)

    # remember what this run put in front of him; the next run won't present any of it again
    for p in fit_show:
        ledger.present(p, "fit")
    for p in poor_show:
        ledger.present(p, "poor")
    for p in outside_show:
        ledger.present(p, "outside")
    for p in near_rows:
        ledger.present(p, "near_miss")
    ledger.save()

    new_fit = [p for p in fit if new[p.key]]
    return {"open_positions": str(md), "diff": str(diff), "near_miss": near, "fit": len(fit), "poor": len(poor), "outside": len(outside),
            "already_seen": n_seen, "handled": n_handled,
            "new_fit": len(new_fit), "new_poor": sum(new[p.key] for p in poor), "new_outside": sum(new[p.key] for p in outside),
            "closed": len(gone), "top_new_fits": [f"{p.title} | {p.company} | {p.pay_display} | fit {p.fit_score} | {p.url}" for p in new_fit[:5]],
            "baseline": base_label}


def dump_stats(stats: dict) -> None:
    (config.run_dir() / "phase4_stats.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
