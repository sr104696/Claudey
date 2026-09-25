"""Alumni-board bridge: job-alert emails you save turn into leads.

Penn Carey Law's alumni board (12twenty) and Penn's Handshake are login-gated and their robots.txt
disallows all crawling, so the radar never connects to them. Both send saved-search alert emails,
and your own email is yours to read. Save alerts (.eml from your mail client, or .html/.txt) into
data/inbox/ (git-ignored) and run `python -m radar import-inbox`.

Each job in an email becomes a lead. The alumni-board link itself is never fetched: Phase 4 looks
for the same role on the employer's own board by company and title. Jobs that can't be found there
are listed in out/alumni_leads.md for you to check by hand, never in the verified lists.
"""
from __future__ import annotations

import email
import html as htmllib
import re
from email import policy
from pathlib import Path

from . import config
from .leads import add_leads
from .models import Lead

INBOX = config.DATA / "inbox"
BOARD_HOSTS = {"12twenty.com": "alumni:12twenty", "joinhandshake.com": "alumni:handshake"}
_A = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
_NOT_JOB = re.compile(r"unsubscribe|preferences|privacy|view (in|all)|log ?in|sign ?in|help|terms|manage|settings|see more", re.I)


def _html_of(path: Path) -> str:
    raw = path.read_bytes()
    if path.suffix.lower() == ".eml":
        msg = email.message_from_bytes(raw, policy=policy.default)
        part = msg.get_body(preferencelist=("html", "plain"))
        return part.get_content() if part else ""
    return raw.decode("utf-8", errors="replace")


def _source_for(url: str, text: str) -> str:
    for host, src in BOARD_HOSTS.items():
        if host in url or host in text:
            return src
    return "alumni:email"


def parse(path: Path) -> list[Lead]:
    body = _html_of(path)
    leads = []
    for href, inner in _A.findall(body):
        title = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
        if not title or len(title) < 4 or _NOT_JOB.search(title) or not href.startswith("http"):
            continue
        # alert emails put "Company · Location" in the lines right after the job link
        tail = htmllib.unescape(re.sub(r"<[^>]+>", "\n", body[body.find(href) + len(href): body.find(href) + len(href) + 600]))
        lines = [l.strip(" ·|-") for l in tail.split("\n") if l.strip(" ·|-")][1:4]
        company = lines[0] if lines else ""
        location = next((l for l in lines[1:] if re.search(r",|remote|new york|nyc|hybrid", l, re.I)), "")
        leads.append(Lead(source=_source_for(href, body), url=htmllib.unescape(href), company=company, title=title,
                          location=location, note=f"from saved alert email {path.name}"))
    return leads


def import_inbox() -> dict:
    INBOX.mkdir(parents=True, exist_ok=True)
    files = [p for p in INBOX.iterdir() if p.suffix.lower() in (".eml", ".html", ".htm", ".txt")]
    leads = [l for f in files for l in parse(f)]
    return {"files": len(files), "leads_found": len(leads), "leads_added": add_leads(leads)}


def write_unresolved(unresolved: list[dict]) -> str:
    lines = ["# Alumni-board leads to check by hand", "",
             "These came from your saved alert emails but couldn't be matched to a posting on the employer's own "
             "site this run, so they are not in the verified lists. Open them from the email while logged in.", "",
             "| Title | Company | Location | Source |", "|---|---|---|---|"]
    lines += [f"| {l.get('title', '')} | {l.get('company', '')} | {l.get('location') or ''} | {l['source']} |" for l in unresolved]
    path = config.OUT / "alumni_leads.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)
