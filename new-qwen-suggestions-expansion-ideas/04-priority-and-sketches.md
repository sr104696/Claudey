# 04 — Priority table & implementation sketches

## Ranked action table

| # | Idea (doc §) | Expected lift | Effort | Risk/notes |
|---|---|---|---|---|
| 1 | Query-matrix expansion, 14→~140 rows (03 §1) | High | Low (CSV only) | none — reuses websearch channel |
| 2 | Title-synonym families in keywords.py (03 §7) | High | Low | watch precision; gate with _FINANCE/_LEGAL ctx |
| 3 | Board-registration from every verified posting (03 §2) | High over time | Low–Med | compounding; pure bookkeeping |
| 4 | Sitemap/feed harvesting for Breezy/JazzHR/BambooHR/Teamtailor/Recruitee/iCIMS/RMK (02 §1) | High | Med | all keyless; verify robots per host at impl |
| 5 | datePosted persistence + `--since` filter + RSS pubDate (03 §4, 02 §9) | Med (freshness) | Low–Med | schema field already parsed in most ATS |
| 6 | New-sector firm seeds: disputes analytics, risk consulting, insurance coverage, arbitration, legal media (01 A,B,D,F,I) | Med–High | Low (companies.csv rows) | Phase 2 detection does the work |
| 7 | Public-sector batch: Fed districts, FDIC/OCC/FinCEN static pages, uscourts, GovernmentJobs RSS, NYC SF portal (01 G, 02 §5) | Med | Med | several bespoke parsers but tiny hosts |
| 8 | HN Algolia upgrade (02 §4) | Low–Med | Low | replaces fragile HTML parse; adds timestamps |
| 9 | CDX first-seen recency + new platform patterns (02 §2) | Med | Low | inherits existing exempt-host approval |
| 10 | Firm-graph seeders: FINRA CSV, ALFA/LFMA lists, VC portfolios, awesome-lists (02 §6) | Med over time | Med | one-time ingestion scripts |
| 11 | Wayback diff-and-alert + blocked-host fallback tables (02 §3) | Low | Low | never marks fallback as verified-open |
| 12 | Near-miss bucket + text-hash judgment reuse (03 §8,§9) | Quality | Low | rubric-learning loop |
| 13 | Mon/Thu cadence with `--light` (03 §10) | Med (freshness) | Low | workflow cron change |
| 14 | KM/practice-attorney carve-out from law-firm poor-match rule (01 C) | Med | Low | scoring rule edit; keep "associate attorney" excluded |
| 15 | Newsletter/inbox bridge reuse (02 §8) | Unknown | Low | user-driven volume; zero crawl |

## New seed-file sketches

### `seeds/platform_feeds.csv`
```csv
platform,pattern,format,robots_note
breezy,https://{tenant}.breezy.hr/xml-feeds,rss,tenant list from CDX *.breezy.hr
jazzhr,https://{tenant}.applytojob.com/feed,rss,tenant list from CDX *.applytojob.com
bamboohr,https://{tenant}.bamboohr.com/careers/list,json,probe after careers-page detect
teamtailor,https://{tenant}.teamtailor.com/jobs,html_jsonld,
recruitee,https://{tenant}.recruitee.com/api/offers/,json,
icims,https://careers-{corp}.icims.com/en-us/search-jobs?rss=true,rss,verify path per corp
rmk,https://{tenant}.sapsf.com/rss,xml,Burford/Fitch pattern generalized
govjobs,https://www.governmentjobs.com/rss/listing.aspx?kw={kw}&loc={loc},rss,kw=attorney;policy
```

### `radar/discover/sitemaps.py` stub shape
```python
"""Public board feeds for smaller ATS platforms. See new-qwen-suggestions doc 02 §1."""
from ..leads import add_leads
from ..models import Lead
from ..runlog import record_channel
from .common import keep_location

def run() -> dict:
    stats = {"queried": 0, "leads": 0, "failures": []}
    for row in load_platform_feeds():          # seeds/platform_feeds.csv
        for tenant in tenants_for(row.platform):   # cc state + discovered_boards.csv
            r = client().get(row.url(tenant))      # politeness client handles rate/robots
            ...
    return stats
```

### `radar/discover/open_feeds.py` (keyless aggregators, 02 §5)
Start with three endpoints only — Arbeitnow, RemoteOK, WoWR RSS — behind a shared
`Lead(source="open_feeds:<name>")` writer, so each can be disabled by env flag if it ever
starts 429-ing or changes ToS.

## Keyword additions
See doc 03 §7 for the full regex block; also add DESC_PHRASES:
```python
("practice attorney", r"practice attorney|knowledge (management|center)"),
("coverage opinion", r"coverage (opinion|position)|duty to defend"),
("ofac/bis", r"\bofac\b|export control|sanctions compliance"),
("bid protest", r"bid protest|gaob protest|gao protest"),
("arbitration rules", r"uncitral|icc rules|faa chapter"),
("freedom of information", r"freedom of information|\bfoia\b"),
```

## Explicit non-goals carried forward
(also stated in the earlier review, restated so nobody re-litigates)
- LinkedIn/Indeed/Glassdoor/Wellfound scraping — no.
- Login-gated alumni portals scripted directly — no (inbox bridge only).
- Captcha/Cloudflare defeat — no.
- Paywalled Am Law data — use public mirrors only.

## How to validate each addition
Per project rules: every new channel must (a) log per-request into out/run_log.md, (b) emit Leads
only — never rows straight into open_positions_*.md, (c) pass Phase 4 live verification, and
(d) report a yield line in the run summary (`channel, leads, verified, fit`) so dead channels are
retired the same way zero-result queries are (03 §1).
