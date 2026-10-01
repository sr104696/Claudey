"""Memory of what the radar has already put in front of Seth, so each run surfaces only choices he hasn't seen.

Two files, both committed:

- data/seen.jsonl      what each run presented (one line per posting per surface). Written by the run itself.
- data/decisions.csv   what Seth decided about a posting (applied, dismissed, right_call, fit). Written by
                       `python -m radar decide`; appended by hand or by Claude.

A posting is "seen" for a surface if an EARLIER run presented it there (runs on the same day don't count, so
re-running a day gives the same answer). Presenting it as a fit covers every lower surface; being asked about it in
the near-miss digest, or listed in the poor-match table, does not count as having seen it as a fit. A row that
was only ever a near miss and is now a fit is therefore new again, which is exactly when Seth wants to hear.

Identity is deliberately loose: the ATS job id, the URL, or company + title + posting text, whichever matches. A
repost of the same req under a new job id has the same text, so it stays seen.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from . import config
from .textutil import norm_company, norm_title

LEDGER = config.DATA / "seen.jsonl"
DECISIONS = config.DATA / "decisions.csv"

SURFACES = ("fit", "outside", "near_miss", "poor")
# what the user was already shown (right) that settles a question about the surface (left)
SATISFIED_BY = {
    "fit": {"fit"},
    "outside": {"outside", "fit"},
    "near_miss": {"near_miss", "fit"},
    "poor": {"poor", "near_miss", "fit"},
}
BUCKET_SURFACE = {"fit": "fit", "outside": "outside", "poor": "poor"}

DECISION_VALUES = ("applied", "dismissed", "right_call", "fit")
HIDE_EVERYWHERE = {"applied", "dismissed"}  # settled: never presented again
HIDE_FROM_DIGEST = HIDE_EVERYWHERE | {"right_call"}  # he ruled on the near-miss row: don't ask again
DECISION_FIELDS = ["id", "decision", "date", "company", "title", "note"]


def identities(r: dict, text_hash: str = "", loose: bool = False) -> list[str]:
    """Every way to recognize one req. `r` is a snapshot row or a Posting.model_dump(). `loose` also adds the bare
    company + title, which is how a person names a posting in decisions.csv."""
    out = []
    if r.get("ats") and r.get("job_id"):
        out.append(f"{r['ats']}:{r.get('board') or ''}:{r['job_id']}")
    if r.get("url"):
        out.append(str(r["url"]).split("#")[0])
    name = f"{norm_company(r.get('company') or '')}|{norm_title(r.get('title') or '')}"
    if text_hash:
        out.append(f"name:{name}|{text_hash}")
    if loose or (not text_hash and not r.get("job_id")):  # seed-list and page postings have no id: the name is all there is
        out.append(f"name:{name}")
    return out


def posting_ids(p, loose: bool = False) -> list[str]:
    from .score import desc_hash

    d = {"ats": p.ats, "board": p.board, "job_id": p.job_id, "url": p.url, "company": p.company, "title": p.title}
    return identities(d, desc_hash(p) if p.description else "", loose)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue  # a torn line must not lose the rest of the ledger
    return rows


class Ledger:
    def __init__(self, run: str, rows: list[dict], path: Path | None = None):
        self.run = run
        self.path = path or LEDGER
        self.rows = rows  # every ledger line, including this run's own from an earlier execution
        self.prior: dict[str, set[str]] = {}  # identity -> surfaces presented by an earlier run
        for r in rows:
            if r.get("run", "") < run:
                for i in r.get("ids", []):
                    self.prior.setdefault(i, set()).add(r["s"])
        self._added: list[dict] = []

    @classmethod
    def load(cls, run: str, snap_dir: Path | None = None, out_dir: Path | None = None, path: Path | None = None) -> "Ledger":
        path = path or LEDGER
        rows = _read_jsonl(path)
        if not rows:  # first run with a ledger: everything earlier runs showed counts as seen
            rows = bootstrap(run, snap_dir or config.DATA / "snapshots", out_dir or config.OUT)
        return cls(run, [r for r in rows if r.get("run", "") <= run], path)

    def surfaces(self, ids: list[str]) -> set[str]:
        got: set[str] = set()
        for i in ids:
            got |= self.prior.get(i, set())
        return got

    def seen(self, p, surface: str) -> bool:
        return bool(self.surfaces(posting_ids(p)) & SATISFIED_BY[surface])

    def seen_row(self, r: dict, surface: str) -> bool:
        return bool(self.surfaces(identities(r)) & SATISFIED_BY[surface])

    def present(self, p, surface: str) -> None:
        self._added.append({"ids": posting_ids(p), "s": surface, "run": self.run, "co": p.company, "ti": p.title})

    def save(self) -> int:
        """Rewrite the ledger: every earlier run's lines, then this run's presentations (replacing a prior
        execution of the same run, so a re-run never double counts)."""
        keep = [r for r in self.rows if r.get("run", "") < self.run]
        seen_lines, fresh = set(), []
        for r in self._added:
            k = (tuple(r["ids"]), r["s"])
            if k not in seen_lines:
                seen_lines.add(k)
                fresh.append(r)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            for r in keep + fresh:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return len(fresh)


def bootstrap(run: str, snap_dir: Path, out_dir: Path) -> list[dict]:
    """Rebuild the ledger from history: each earlier snapshot's fit, outside and poor rows were listed in that
    run's open-positions tables, and each saved near-miss digest asked about its rows."""
    rows = []
    for snap in sorted(snap_dir.glob("*.csv")):
        if snap.stem >= run:
            continue
        with open(snap, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                surface = BUCKET_SURFACE.get(r.get("bucket", ""))
                if surface == "outside" and r.get("poor_reason"):
                    surface = None  # weaker out-of-area rows were never listed
                if surface:
                    rows.append({"ids": identities(r), "s": surface, "run": snap.stem, "co": r.get("company", ""),
                                 "ti": r.get("title", "")})
    for md in sorted(out_dir.glob("near_miss_*.md")):
        day = md.stem.removeprefix("near_miss_")
        if day >= run:
            continue
        for url in re.findall(r"\]\((https?://[^)\s]+)\)", md.read_text(encoding="utf-8")):
            rows.append({"ids": [url.split("#")[0]], "s": "near_miss", "run": day})
    return rows


# --------------------------------------------------------------------------- decisions
class Decisions:
    def __init__(self, by_id: dict[str, str]):
        self.by_id = by_id

    @classmethod
    def load(cls, path: Path | None = None) -> "Decisions":
        path = path or DECISIONS
        by_id: dict[str, str] = {}
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    i = _clean_id(r.get("id", ""))
                    if i and r.get("decision"):
                        by_id[i] = r["decision"].strip().lower()  # a later row for the same id wins
        return cls(by_id)

    def _lookup(self, ids: list[str]) -> str:
        for i in ids:
            if i in self.by_id:
                return self.by_id[i]
        return ""

    def for_posting(self, p) -> str:
        return self._lookup(posting_ids(p, loose=True))

    def for_row(self, r: dict) -> str:
        return self._lookup(identities(r, loose=True))


def _clean_id(s: str) -> str:
    s = (s or "").strip()
    if s.startswith(("http://", "https://")):
        return s.split("#")[0]
    if "|" in s and not s.startswith("name:"):  # "company|title"
        c, _, t = s.partition("|")
        return f"name:{norm_company(c)}|{norm_title(t)}"
    return s


def record_decision(ident: str, decision: str, note: str = "", company: str = "", title: str = "",
                    path: Path | None = None, date: str | None = None) -> None:
    if decision not in DECISION_VALUES:
        raise ValueError(f"decision must be one of {DECISION_VALUES}, got {decision!r}")
    path = path or DECISIONS
    new = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DECISION_FIELDS)
        if new:
            w.writeheader()
        w.writerow({"id": ident.strip(), "decision": decision, "date": date or config.today(),
                    "company": company, "title": title, "note": note})
