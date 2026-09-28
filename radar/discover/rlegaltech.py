"""r/legaltech job directory (rlegaltech.com/jobs/...): a community-maintained directory of legal-tech
vendor job postings, organized by vendor with each posting's own "Apply" link going straight to the
employer's ATS. The site's own description: "Every application leaves rlegaltech.com for the employer's
own careers site." This channel reads only the "legal" role-family page (the slice relevant to Seth) and
extracts each vendor's Apply link as a lead; the directory listing is never itself evidence a job is open,
Phase 4 verifies every lead on the employer's own system exactly as it does for every other channel.

Note on markup: this parses generically (nearest list-item ancestor of an "Apply" link matching a known
ATS URL, nearest preceding heading as the vendor name) rather than against exact CSS classes, since the
site's markup wasn't inspectable when this was written (this session's network policy blocks the domain
directly; only WebSearch snippets and a user-supplied page export were available). Treat low/zero yields
here as a signal the heuristics need adjusting against the real markup, not that the site went quiet.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

from selectolax.parser import HTMLParser

from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from .common import ATS_URL, keep_location

BASE = "https://www.rlegaltech.com"
PAGES = ["/jobs/legal/"]  # the site also breaks jobs out by sales/engineering/etc.; only "legal" is in scope
HEADINGS = {"h1", "h2", "h3", "h4", "h5"}
_MODE_MARK = re.compile(
    r"\s*(?:Remote|Hybrid|On-?site|Full time|Part time|Contract|Internship|Source checked)\b", re.I
)


def _strip_tracking(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = "&".join(
        p for p in parts.query.split("&")
        if p and not p.split("=", 1)[0].lower() in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "gh_src")
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, kept, ""))


def _block_for(anchor):
    """Nearest list-item/article/row ancestor of an Apply link, i.e. the one posting's own block."""
    node = anchor.parent
    hops = 0
    while node is not None and node.tag not in ("li", "article") and hops < 6:
        node = node.parent
        hops += 1
    return node


def _heading_before(node) -> str:
    """Nearest heading that precedes `node` in document order, climbing ancestors as needed (the vendor
    name heading sits above the postings list, not as a direct sibling of one posting's own block)."""
    n = node
    while n is not None:
        p = n.prev
        while p is not None:
            if p.tag in HEADINGS:
                return p.text(strip=True)
            h = p.css_first(",".join(HEADINGS)) if hasattr(p, "css_first") else None
            if h is not None:
                return h.text(strip=True)
            p = p.prev
        n = n.parent
    return ""


def _title_for(block) -> str:
    for sel in ("h4", "h3", "h5", "strong", "b"):
        el = block.css_first(sel)
        if el is not None:
            t = el.text(strip=True)
            if t:
                return t
    return ""


def _location_for(block, title: str) -> str:
    text = block.text(separator=" ", strip=True)
    if title:
        text = text.replace(title, "", 1)
    m = _MODE_MARK.search(text)
    return (text[: m.start()] if m else text[:120]).strip(" ·-|,")


def _parse(html: str) -> list[Lead]:
    tree = HTMLParser(html)
    leads, seen = [], set()
    for a in tree.css("a"):
        href = a.attributes.get("href") or ""
        if "apply" not in a.text(strip=True).lower() or not ATS_URL.match(href):
            continue
        url = _strip_tracking(href)
        if url in seen:
            continue
        seen.add(url)
        block = _block_for(a)
        if block is None:
            continue
        title = _title_for(block)
        if not title:
            continue
        company = _heading_before(block)
        loc = _location_for(block, title)
        ok, why = relevance(title, "")
        if not ok or (loc and not keep_location(loc)):
            continue
        leads.append(Lead(source="rlegaltech", url=url, company=company, title=title,
                          location=loc, note=f"rlegaltech legal directory; {why}"))
    return leads


def run() -> dict:
    leads: list[Lead] = []
    failures: list[str] = []
    per_page: dict[str, int] = {}
    for path in PAGES:
        r = client().get(BASE + path)
        if not r.ok:
            failures.append(f"{path}: {r.describe()}")
            continue
        page_leads = _parse(r.text)
        leads.extend(page_leads)
        per_page[path] = len(page_leads)
        if not page_leads:
            failures.append(f"{path}: no Apply links matched a known ATS pattern (markup may have changed)")
    add_leads(leads)
    record_channel("discover:rlegaltech", queried=len(PAGES), candidates=len(leads), failures=failures,
                   notes="; ".join(f"{k}: {v} kept" for k, v in per_page.items()))
    return {"pages": len(PAGES), "leads": len(leads), "failures": failures}
