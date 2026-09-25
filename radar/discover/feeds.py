"""Generic feeds channel: any public JSON / RSS / Atom job feed listed in seeds/feeds.csv.

Columns: url, format (json|rss|atom), label, title_allowlist (regex; empty = use keywords.relevance only).
Adding a feed is one CSV row. Feed items are leads: Phase 4 still verifies each on the employer's own
system, and the feed page itself never counts as evidence (feed hosts are listed as aggregators).
"""
from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET

from .. import config
from ..http import client
from ..keywords import relevance
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from ..textutil import html_to_text
from .common import ATS_URL, keep_location

FEEDS = config.SEEDS / "feeds.csv"
_ATOM = "{http://www.w3.org/2005/Atom}"


def _json_items(d) -> list[dict]:
    items = d if isinstance(d, list) else next((d[k] for k in ("jobs", "data", "items", "results") if isinstance(d.get(k), list)), [])
    out = []
    for j in items:
        if not isinstance(j, dict):
            continue
        company = j.get("company")
        if isinstance(company, dict):
            company = company.get("name")
        out.append({
            "title": j.get("title") or j.get("name") or "",
            "company": company or j.get("company_name") or "",
            "location": j.get("location") if isinstance(j.get("location"), str) else ", ".join(j.get("location") or []) if isinstance(j.get("location"), list) else "",
            "url": j.get("url") or j.get("link") or "",
            "apply_url": j.get("apply_url") or j.get("applyUrl") or "",
            "text": html_to_text(j.get("description") or j.get("summary") or ""),
            "remote": bool(j.get("remote")),
        })
    return out


def _xml_items(text: str) -> list[dict]:
    root = ET.fromstring(text)
    out = []
    for it in root.iter("item"):  # RSS
        out.append({"title": it.findtext("title") or "", "company": it.findtext("{*}creator") or "", "location": "",
                    "url": it.findtext("link") or "", "apply_url": "", "text": html_to_text(it.findtext("description") or ""), "remote": False})
    for it in root.iter(f"{_ATOM}entry"):  # Atom
        link = it.find(f"{_ATOM}link")
        out.append({"title": it.findtext(f"{_ATOM}title") or "", "company": it.findtext(f"{_ATOM}author/{_ATOM}name") or "",
                    "location": "", "url": link.get("href") if link is not None else "", "apply_url": "",
                    "text": html_to_text(it.findtext(f"{_ATOM}summary") or it.findtext(f"{_ATOM}content") or ""), "remote": False})
    return out


def run() -> dict:
    if not FEEDS.exists():
        record_channel("discover:feeds", skipped=["no seeds/feeds.csv"])
        return {"feeds": 0}
    with open(FEEDS, newline="", encoding="utf-8") as f:
        feeds = list(csv.DictReader(f))
    leads, failures, per_feed = [], [], {}
    for fd in feeds:
        r = client().get(fd["url"])
        if not r.ok:
            failures.append(f"{fd['label']}: {r.describe()}")
            continue
        try:
            items = _json_items(r.json()) if fd["format"] == "json" else _xml_items(r.text)
        except (ValueError, ET.ParseError) as e:
            failures.append(f"{fd['label']}: unparseable {fd['format']} ({e})")
            continue
        if not items:
            failures.append(f"{fd['label']}: feed returned no items (format change?)")
        allow = re.compile(fd["title_allowlist"], re.I) if fd.get("title_allowlist") else None
        n = 0
        for it in items:
            if allow and not allow.search(it["title"]):
                continue
            ok, why = relevance(it["title"], it["text"])
            loc = it["location"] or ("Remote" if it["remote"] else "")
            if not ok or (loc and not keep_location(loc)):
                continue
            # prefer the employer's ATS link when the feed carries one
            url = it["apply_url"] if it["apply_url"] and ATS_URL.match(it["apply_url"]) else (it["url"] or it["apply_url"])
            if url:
                leads.append(Lead(source=f"feeds:{fd['label']}", url=url, company=it["company"], title=it["title"],
                                  location=loc, note=f"{fd['label']} feed; {why}"))
                n += 1
        per_feed[fd["label"]] = f"{n} of {len(items)}"
    add_leads(leads)
    record_channel("discover:feeds", queried=len(feeds), candidates=len(leads), failures=failures,
                   notes="; ".join(f"{k}: {v} kept" for k, v in per_feed.items()))
    return {"feeds": len(feeds), "leads": len(leads), "per_feed": per_feed, "failures": failures}
