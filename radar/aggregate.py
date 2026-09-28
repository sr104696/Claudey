"""out/all_positions.md: every posting the radar has seen, deduplicated across runs, in one list.

Built from data/snapshots/<date>.csv (one per run; the newest is this run's verified result). Only the newest
run's rows are presented as open. Older rows the newest run didn't confirm are listed separately with their
last-seen date, so nothing is lost when old dated files in out/ are pruned.
"""
from __future__ import annotations

import csv
import datetime as dt
import re

from . import config
from .phase1 import ap_date
from .score import GOVERNMENT_NAME, LAW_FIRM_NAME, PAY_FLOOR, QUASI_PUBLIC_OK
from .textutil import norm_company, norm_title

SNAP_DIR = config.DATA / "snapshots"
PATH_TOWNS = re.compile(r"jersey city|hoboken", re.I)
METRO_NORTH = re.compile(r"stamford|greenwich|westport|\brye\b|white plains", re.I)
# listings that aren't seats: events, talent pools, standing expressions of interest
NOT_A_SEAT = re.compile(r"coffee chat|case competition|talent (network|community|pool)|expression of interest|general interest|"
                        r"future opportunit|open application", re.I)
# contract-lawyer platforms: engagements, not employee seats (CLAUDE.md: no contract or hourly work)
CONTRACT_PLATFORMS = re.compile(r"^axiom\b|talent platform", re.I)
KEEP_RUNS = 4  # dated files kept in out/; git history holds the rest


def identity(r: dict) -> str:
    if r.get("job_id") and r.get("ats"):
        return f"{r['ats']}:{r.get('board', '')}:{r['job_id']}"
    if r.get("url"):
        return r["url"].split("#")[0]
    return f"{norm_company(r.get('company', ''))}|{norm_title(r.get('title', ''))}"


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _esc(s) -> str:
    return str(s or "").replace("|", "\\|").replace("\n", " ")


def settled_out(r: dict) -> str:
    """Current rules applied to a stored row: government, law firm, listed pay under the floor."""
    srcs = [s.strip() for s in (r.get("sources") or "").split(";") if s.strip()]
    gov_src = [s for s in srcs if s.startswith(("public_sector:", "official_apis:usajobs"))]
    if (gov_src and not all(s in QUASI_PUBLIC_OK for s in gov_src)) or r.get("ats") == "nyag" or GOVERNMENT_NAME.search(r.get("company", "")):
        return "Government seat"
    if LAW_FIRM_NAME.search(r.get("company", "")) and not re.search(r"underwrit|research|analyst", r.get("title", ""), re.I):
        return "Law-firm seat"
    top = _num(r.get("pay_max")) or _num(r.get("pay_min"))
    if r.get("pay_type") == "base" and top and (r.get("pay_period") or "year") == "year" and top < PAY_FLOOR:
        return "Listed pay under $150K"
    if CONTRACT_PLATFORMS.search(r.get("company", "")):
        return "Contract-lawyer platform"
    return ""


def not_a_seat(r: dict) -> bool:
    return bool(NOT_A_SEAT.search(r.get("title", "")))


def same_role(rows: list[dict]) -> list[dict]:
    """Merge one role posted on two boards (same title, pay and location); keep the pipeline/registry copy."""
    out, index = [], {}
    for r in rows:
        k = (norm_title(r.get("title", "")), r.get("pay_display", ""), (r.get("location") or "").lower()[:40])
        if k in index and r.get("pay_display") not in ("", "Not listed"):
            continue
        index[k] = r
        out.append(r)
    return out


def thesis(r: dict) -> bool:
    return "seat family:" in (r.get("fit_signals") or "")


def fit_key(r: dict):
    top = _num(r.get("pay_max")) or _num(r.get("pay_min"))
    mid = ((_num(r.get("pay_min")) or top) + top) / 2 if top else 0
    tier = 2 if mid >= 200_000 else 1 if mid >= 150_000 else 0
    return (not thesis(r), "(meets: Y)" not in (r.get("domain_floor") or ""), -tier, -int(_num(r.get("fit_score"))),
            _neg_date(r.get("posted_date")), r.get("company", ""))


def _neg_date(d) -> int:
    try:
        return -dt.date.fromisoformat(str(d)[:10]).toordinal()
    except ValueError:
        return 0


def _loc(r: dict) -> str:
    loc = r.get("location") or "Not stated"
    if PATH_TOWNS.search(loc):
        loc += " (commutable)"
    elif r.get("bucket") == "outside" and METRO_NORTH.search(loc):
        loc += " (Metro-North ~1 hr, hybrid only)"
    return loc


def _pos(r: dict) -> str:
    cell = f"[{_esc(r['title'])}]({r['url']})"
    if r.get("via_aggregator"):
        cell += " (aggregator link)"
    return ("★ " if thesis(r) else "") + cell


def _company(r: dict) -> str:
    return _esc(r.get("company")) + (" (already in your pipeline)" if str(r.get("pipeline")) in ("True", "1") else "")


def build() -> tuple[str, dict]:
    snaps = sorted(SNAP_DIR.glob("*.csv"))
    if not snaps:
        return "", {}
    runs: list[tuple[str, list[dict]]] = []
    for p in snaps:
        with open(p, newline="", encoding="utf-8") as f:
            runs.append((p.stem, list(csv.DictReader(f))))
    latest_date, latest = runs[-1]

    seen: dict[str, dict] = {}  # identity -> {first, last, row(latest version), pays}
    for date, rows in runs:
        for r in rows:
            k = identity(r)
            e = seen.setdefault(k, {"first": date, "last": date, "row": r, "pays": []})
            e["last"], e["row"] = date, r
            if r.get("pay_display") and (not e["pays"] or e["pays"][-1] != r["pay_display"]):
                e["pays"].append(r["pay_display"])
    current = {identity(r) for r in latest}

    fits = sorted([r for r in latest if r["bucket"] == "fit"], key=lambda r: (str(r.get("pipeline")) not in ("True", "1"),))
    fits = sorted(same_role(fits), key=fit_key)
    not_seats = [r for r in fits if not_a_seat(r)]
    dropped = [r for r in fits if not not_a_seat(r) and settled_out(r)]
    fits = [r for r in fits if not not_a_seat(r) and not settled_out(r)]
    near = [r for r in latest if r["bucket"] == "poor" and not settled_out(r) and int(_num(r.get("fit_score"))) >= 5
            and not r.get("hard_exclude_reason", "").startswith("Pay is quoted as OTE")]
    near = sorted(near, key=lambda r: (-int(_num(r.get("fit_score"))), -(_num(r.get("pay_max")) or _num(r.get("pay_min")))))[:25]
    outside = [r for r in latest if r["bucket"] == "outside" and not r.get("poor_reason") and not settled_out(r) and not not_a_seat(r)]
    outside.sort(key=lambda r: (not METRO_NORTH.search(r.get("location") or ""), not thesis(r), -int(_num(r.get("fit_score")))))
    poor = [r for r in latest if r["bucket"] == "poor"]
    gone = [e for k, e in seen.items() if k not in current and e["row"].get("bucket") == "fit" and not settled_out(e["row"])]
    gone.sort(key=lambda e: (e["last"], e["row"].get("company", "")), reverse=True)

    L = ["# All positions", "",
         f"Every posting the radar has seen across {len(runs)} runs ({ap_date(runs[0][0])} to {ap_date(latest_date)}), "
         f"deduplicated by ATS job ID, then URL. Only section 1 and 2 rows were confirmed open on {ap_date(latest_date)}; "
         "section 3 is history. ★ marks the seat families where your background clears the domain-years screen. "
         "Government seats, law-firm seats and listed pay under $150K are excluded under your current rules.", "",
         f"## 1. Open now: fits ({len(fits)})", "",
         "| Position | Company | Location | Listed pay | First seen |", "|---|---|---|---|---|"]
    L += [f"| {_pos(r)} | {_company(r)} | {_esc(_loc(r))} | {_esc(r.get('pay_display'))} | {ap_date(seen[identity(r)]['first'])} |" for r in fits]
    if not_seats or dropped:
        L += ["", "Not listed above: " + "; ".join(
            [f"{len(not_seats)} events or talent pools ({', '.join(sorted({_esc(r['company']).strip() for r in not_seats}))})"] * bool(not_seats)
            + [f"{len(dropped)} contract-platform or rule-excluded rows"] * bool(dropped)) + "."]
    L += ["", f"## 2. Open now: near misses ({len(near)})", "",
          "Poor matches with 5+ fit signals that aren't settled by the government, law-firm or pay rules.", "",
          "| Position | Company | Listed pay | Why it missed |", "|---|---|---|---|"]
    L += [f"| {_pos(r)} | {_company(r)} | {_esc(r.get('pay_display'))} | {_esc(r.get('poor_reason'))[:200]} |" for r in near]
    L += ["", f"## 3. Listed as a fit before, not confirmed on {ap_date(latest_date)} ({len(gone)})", "",
          "Closed, removed, or not reachable this run. Not evidence the role is open.", "",
          "| Position | Company | Last seen | Last listed pay |", "|---|---|---|---|"]
    L += [f"| [{_esc(e['row']['title'])}]({e['row']['url']}) | {_company(e['row'])} | {ap_date(e['last'])} | "
          f"{_esc(' → '.join(e['pays']) or 'Not listed')} |" for e in gone]
    L += ["", f"## 4. Outside NYC / US-remote ({len(outside)})", "",
          "| Position | Company | Location | Listed pay |", "|---|---|---|---|"]
    L += [f"| {_pos(r)} | {_company(r)} | {_esc(_loc(r))} | {_esc(r.get('pay_display'))} |" for r in outside]
    L += ["", f"## 5. Poor matches in NYC / US-remote ({len(poor)})", "",
          "<details><summary>One line each, with the reason</summary>", ""]
    L += [f"- [{_esc(r['title'])}]({r['url']}), {_esc(r['company'])}, {_esc(r.get('pay_display'))}: {_esc(r.get('poor_reason'))[:160]}"
          for r in sorted(poor, key=lambda r: (r.get("company", ""), r.get("title", "")))]
    L += ["", "</details>", ""]
    stats = {"not_seats": len(not_seats), "dropped": len(dropped), "runs": len(runs), "unique": len(seen), "fits": len(fits), "near": len(near), "gone_fits": len(gone),
             "outside": len(outside), "poor": len(poor), "rows_read": sum(len(r) for _, r in runs)}
    return "\n".join(L) + "\n", stats


def prune_out(keep: int = KEEP_RUNS) -> list[str]:
    """Delete dated files in out/ older than the newest `keep` runs (git history keeps them)."""
    removed = []
    for prefix in ("open_positions_", "diff_", "near_miss_", "seed_verification_"):
        files = sorted(config.OUT.glob(f"{prefix}*.md"))
        for p in files[:-keep]:
            p.unlink()
            removed.append(p.name)
    return removed


def write() -> dict:
    md, stats = build()
    if md:
        (config.OUT / "all_positions.md").write_text(md, encoding="utf-8")
    stats["pruned"] = prune_out()
    return stats
