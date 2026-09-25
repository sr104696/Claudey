"""Silence alarm: tell "this source failed" apart from "this source had nothing this week".

Every bug the September code reviews found had the same shape: a failure that looks exactly like an
empty result (a renamed API category, an unreachable robots.txt, a crashed channel, an empty sitemap).
Rather than trusting each adapter to report its own failures, this module records every source's
yield per run in data/source_health.csv and compares against the previous run:

  crashed      a discovery channel process exited non-zero
  not run      an expected channel left no record this run
  went quiet   a source that produced candidates/jobs last run produced zero now
  degraded     a board whose status was "ok" last run isn't now
  skipped      a channel reported a skip (missing key, block)

Alerts go to the top of out/run_log.md and into the refresh summary.
"""
from __future__ import annotations

import csv

from . import config, runlog

PATH = config.DATA / "source_health.csv"
FIELDS = ["run", "source", "kind", "status", "queried", "candidates", "verified", "kept"]


def _rows_now(codes: dict[str, int] | None) -> list[dict]:
    run = config.today()
    rows = []
    for name, c in runlog.load_channels().items():
        status = "ok"
        if c.get("failures"):
            status = "failures"
        if codes and codes.get(name.split(":", 1)[-1], 0) != 0:
            status = "crashed"
        rows.append({"run": run, "source": name, "kind": "channel", "status": status, "queried": c.get("queried") or 0,
                     "candidates": c.get("candidates") or 0, "verified": c.get("verified_open") or "", "kept": c.get("kept") or ""})
    for name, code in (codes or {}).items():
        if code != 0 and f"discover:{name}" not in {r["source"] for r in rows}:
            rows.append({"run": run, "source": f"discover:{name}", "kind": "channel", "status": "crashed",
                         "queried": 0, "candidates": 0, "verified": "", "kept": ""})
    with open(config.COMPANIES_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("last_checked") == run and r.get("ats") not in ("none", "blocked", "channel", ""):
                rows.append({"run": run, "source": f"board:{r['company']}", "kind": "board",
                             "status": "ok" if str(r.get("board_status", "")).startswith("ok") else r.get("board_status", ""),
                             "queried": 1, "candidates": r.get("jobs_total") or 0, "verified": "",
                             "kept": r.get("jobs_relevant_us") or 0})
    return rows


def record(codes: dict[str, int] | None = None, expected_channels: list[str] | None = None) -> list[str]:
    """Append this run's rows (replacing any earlier rows for the same run) and return alert lines."""
    run = config.today()
    old = []
    if PATH.exists():
        with open(PATH, newline="", encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if r["run"] != run]
    now = _rows_now(codes)
    with open(PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(old + now)

    prev_run = max((r["run"] for r in old), default=None)
    prev = {r["source"]: r for r in old if r["run"] == prev_run}
    cur = {r["source"]: r for r in now}
    alerts = []
    for r in now:
        p = prev.get(r["source"])
        if r["status"] == "crashed":
            alerts.append(f"**crashed**: `{r['source']}` exited with an error; it contributed nothing this run")
        elif p and int(p["candidates"] or 0) > 0 and int(r["candidates"] or 0) == 0:
            alerts.append(f"**went quiet**: `{r['source']}` had {p['candidates']} last run ({prev_run}) and 0 now")
        elif p and p["status"] == "ok" and r["status"] != "ok":
            alerts.append(f"**degraded**: `{r['source']}` was ok last run, now `{r['status']}`")
    for ch in expected_channels or []:
        if f"discover:{ch}" not in cur:
            alerts.append(f"**not run**: channel `{ch}` left no record this run")
    for name, c in runlog.load_channels().items():
        for s in c.get("skipped", []):
            if name.startswith("discover:"):
                alerts.append(f"skipped: `{name}`: {s}")
    return alerts


def section(alerts: list[str]) -> tuple[str, str]:
    body = "\n".join(f"- {a}" for a in alerts) if alerts else "No source crashed, went quiet or degraded since the last run."
    return ("Silence check", body + f"\n\nHistory: `data/source_health.csv` ({config.today()}).")
