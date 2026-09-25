# Code review — JD-to-investing job radar

**Reviewer:** Qwen Coder · **Date:** 2026-09-25 · **Branch reviewed:** current `/workspace` HEAD (post-2026-09-24 build)

**Scope of this review:** overall code quality, and specifically the questions the user asked:

1. How can the **sweep be made more comprehensive**?
2. How can it hit **more tailored / unique / niche sources** (aistartupjobs.com, r/legaltech, legaloperationsjobboard.com, …)?
3. Can it use the same **aggregations and feeds other job boards use** (RSS/JSON feeds, index APIs)?
4. Is there a way for Claude Code to **connect to a Penn Law / Penn Grad alumni job board**?

## Overall assessment

This is a well-built, unusually disciplined codebase. Highlights:

- **Politeness is genuinely engineered, not aspirational.** `radar/http.py` enforces 1 req/s/host *across processes* via lock files, checks robots.txt on every request and redirect hop, detects Cloudflare bot walls and logs them as blocked instead of working around them, and logs every request. The `RADAR_ROBOTS_EXEMPT_HOSTS` mechanism requires explicit user approval per host. This matches CLAUDE.md's rules exactly.
- **"Verify before listing" is enforced structurally**: aggregator hits are only *leads* (`data/leads.jsonl`) that Phase 4 re-verifies at the employer ATS; `ATS_URL` in `discover/common.py` restricts leads to canonical posting URLs.
- **Good incremental design**: Common Crawl board state (`cc_boards.json`) spreads work across runs; judgment caching keyed by description hash avoids re-judging unchanged postings; git history of `out/` doubles as the posting database.
- Clean separation: `ats/` adapters per system, `discover/` per channel, phases 1–5 wired through `pipeline.py`, all CLI-exposed.

The findings below are ordered by how much they move the needle on **recall** (finding seats that exist), since precision machinery (rubric, hard excludes, judgment subagents) is already strong.

---

## A. Sweep comprehensiveness — gaps found in code

### A1. (High) The ATS-wide sweep covers 3 of ~10 relevant ATS families

`radar/discover/commoncrawl.py`:

```python
PATTERNS = {
    "greenhouse": [...],
    "lever": ["jobs.lever.co/*"],
    "ashby": ["jobs.ashbyhq.com/*"],
}
```

Greenhouse/Lever/Ashby dominate startups, but the candidate's target employers skew finance/legal, where **Workday** (banks, BigLaw-crossover funds, S&P/Moody's — already in `seeds/companies.csv`), **SmartRecruiters**, **Breezy**, **JazzHR**, **Polymer/Greenhouse-EU mirrors** and **IBM Kenexy/Taleo** hosts carry many postings. Two concrete fixes:

- Add `"workday": ["*.myworkdayjobs.com/*"]` and `"smartrecruiters": ["jobs.smartrecruiters.com/*"]` to `PATTERNS` + a matching entry in `PULL`. Workday CDX token extraction needs its own regex (`([\w-]+)\.wd\d+\.myworkdayjobs\.com`) and the existing `workday.list_jobs` spec builder already handles the tenant|host|site triple, so marginal cost is low. Note SmartRecruiters' public API is robots-blocked (documented in `smallats.py`); a CC-discovered SmartRecruiters board should therefore route through the HTML page verifier (`ats/html.py` JSON-LD path), not the API.
- Add Breezy (`job-boards.europe.breezy.hr` / `breezy.hr/*`), JazzHR (`apply.jazzhr.com/*`) and Recruitee (`*.recruitee.com/*`) patterns with small pull adapters — `smallats.py` already has Recruitee; Breezy/JazzHR have clean JSON endpoints (`/{company}.breezy.hr/json`).

Also: `ATS_URL` in `discover/common.py` gates which lead URLs survive into verification. Every new ATS family added to discovery must be appended there too, or its leads get silently dropped — worth a unit test asserting `PATTERNS.keys() ⊆ ats covered by ATS_URL`.

### A2. (High) No RSS/Atom feed channel — this is the "feeds other job boards use" question

Most of the aggregation layer that powers Indeed/Google-for-Jobs-style indexing is built on public RSS/Atom/JSON feeds, and several of the niche sites in scope publish them. There is no `radar/discover/feeds.py`; adding one is the single highest-leverage new channel because it's cheap (one GET per feed per run, polite by nature, cacheable) and reaches long-tail employers no `site:` query surfaces:

| Feed | URL pattern | Why it fits Seth |
|---|---|---|
| Greenhouse per-board JSON | `https://boards-api.greenhouse.io/v1/boards/{token}/jobs` (+`?content=true`) | Already used by the adapter; expose it as a *feed registry* source |
| Lever postings API | `https://api.lever.co/v0/postings/{token}?mode=json` | ditto |
| Ashby public jobs | `https://api.ashbyhq.com/posting-api/job-board/{token}` | ditto |
| **AI Startup Jobs** | `https://aistartupjobs.com/rss.xml` (verify path at implementation time) | Legal-AI / applied-legal seats at AI companies; the exact aggregator named in the request |
| **Legal Ops Job Board** | `legaloperationsjobboard.com` publishes its board as HTML (WordPress-based); poll the job-listing page like `public_sector._nydfs` does, honoring robots | legal-tech/legal-ops niche; see caveat in doc 02 about practice-area drift |
| Idealist / DevPost / USAJobs RSS | `https://www.usajobs.gov/Feed/...`, idealist.org RSS | policy-research seats |
| Hacker News jobs RSS | `https://hnrss.org/whoishiring` | complements the existing Algolia scrape |
| Workable/Renrexx/JazzHR per-company RSS | documented per ATS | registry-driven pulls |

Design: a `seeds/feeds.csv` registry (`name, url, kind=rss|atom|json, notes`), one generic parser (stdlib `xml.etree` + the existing `Lead` model), relevance filter from `keywords.relevance`, dedupe by `(source,url)` via `add_leads`. ~120 lines including tests, reuses everything downstream (verification, scoring, diff).

### A3. (Medium) `websearch` channel is capped by seed-file rot, not by search quality

`seeds/search_queries.csv` has 14 queries, all `site:greenhouse|ashby|lever` or aggregator variants. Observations from the data itself: three queries returned `results_used=0` — those query shapes are dead weight. The bigger issue is coverage of *query space*: nothing searches for the seat-family vocabulary that actually distinguishes this candidate (see doc 02 for the full expanded set). Also add `site:` targets for the niche boards (aistartupjobs.com, legal.io, goinhouse, lawnext,Above the Law lateral-hire roundups, Financial Times eFinancialCareers jobs) — each costs one row in the CSV and flows through the existing import path.

Recommendation: grow to ~35–45 queries organized by *bucket* (litigation finance, credit intelligence, legal AI, reg-risk-at-trading-firms, academies, embedded research, legal-ops-adjacent-wildcards, prediction markets, public-sector counsel), tag each row with the bucket, and record `results_used` per run so a periodic pruning pass (a `radar prune-queries` subcommand or just a Claude step in `/refresh-jobs`) drops queries returning zero yield twice in a row and promotes variants of high-yield ones.

### A4. (Medium) Community/niche-source channels are absent (r/legaltech etc.)

Reddit's public JSON endpoints (`https://www.reddit.com/r/legaltech/new.json?limit=100`, plus `r/biglaw` career threads, `r/ArtificialIntelligence` "who's hiring", `r/FintechUK` for remote-US-friendly posts) are unauthenticated, rate-limit-friendly at 1 req/min, and return structured JSON — a natural fit for a `discover/reddit.py` channel modeled on `discover/hn.py` (same shape: fetch → regex-scan comments/posts for ATS URLs via `ATS_URL` → emit leads). The rule "snippets are leads, not evidence" already protects against stale Reddit posts: Phase 4 re-verifies every link at the employer board.

Similarly, `lawnext.com/jobs`, `abovethe-law.com` ("BigLaw to ___" exit stories occasionally list openings), and `financialit.net`/`efinancialcareers` niche sections are reachable via the websearch channel without new code; the truly *unique* ones deserve first-class channels (doc 02 ranks them).

### A5. (Medium) Wayback recurrence ≠ Wayback *discovery*

`discover/wayback.py` answers "how often do watched seats reopen." It could double as a discovery channel cheaply: CDX queries against *employer careers domains* (from `seeds/companies.csv`) for URLs matching `/job|/posting|/position` reveal roles that were live last quarter and may have reopened — feeding the same lead pipeline. Low priority but a nice reuse.

### A6. (Low) Keyless-API channels currently sleep

USAJobs/Adzuna/SerpAPI skip without keys (correctly logged). Given the profile, USAJobs matters more than it looks: SEC/CFTC/OCC/CFPB Division-of-Market-Risk-style seats are exactly the "business-side regulatory risk" family, and the free key takes two minutes. Recommend making key setup a first-run prompt in `.claude/commands/refresh-jobs.md` step 0 rather than an optional footnote.

### A7. (Low) Location filter blind spots

`keep_location` buckets NYC / US-remote / other-US. Fine per CLAUDE.md, but note some ATS feeds (notably SmartRecruiters `loc.get("remote")` and BambooHR) leave location empty for remote-by-default boards; verify `classify_location("")` doesn't silently drop those. Worth one assertion in the run log: count of postings dropped *solely* for missing location.

---

## B. Scoring & output — minor points

- **B1.** `keywords.TITLE_DROP` correctly protects "legal engineer," but relies on lookaround regexes that are fragile if titles add commas/parentheses (`engineer (legal)` would drop). Suggest a whitelist test table of real titles seen so far (cheap regression protection).
- **B2.** `score.py` requires 3/10 fit signals; the signal list gives a point for "credit/distressed/bankruptcy subject matter" and "fintech/crypto/AI" — for litigation-finance underwriting seats neither fires while "clerkship preferred" + "litigation accepted" do. That works, but consider a bucket-specific threshold (e.g., 2/10 when `segment == litigation_finance`) once `companies.csv` segments propagate to scored rows.
- **B3.** In `official_apis._muse`, pagination breaks on the first failure but continues categories — good; however `page_count` semantics differ between Muse versions; log `len(results)==0 && page==0` as a soft warning so a silent API change doesn't zero out the channel unnoticed.
- **B4.** Nice touch: `closed_notes` cross-checks closed seeds against freshly verified postings before declaring them closed. Keep that invariant tested.

---

## C. Alumni job boards — feasibility summary (full plan in doc 03)

Short version: **yes, partially, and Claude Code can drive most of it — but only through authenticated sessions the user owns, never credential-sharing with scripts.**

- **Penn Law CDO (Office of Career Services)** maintains a private job portal (Symplicity/12Twenty-class platform) for graduates. These platforms have no public API and ToS prohibit scripted scraping with shared credentials; the honest architecture is (a) Claude Code reads/export what the *user's own logged-in browser session* exposes, or (b) a local "export → parse → score" bridge: user exports/forwards listings (CSV or email digests) into `data/alumni_inbox/`, and a new `radar import-alumni` command turns them into verified leads through the same Phase 4 pipeline.
- **Penn Alumni / GAL (Graduate Alumni Network)** and **Penn Law's LinkedIn-alum directory**: LinkedIn scraping is explicitly banned by CLAUDE.md and LinkedIn ToS — do not touch. But *manual* alumni outreach tracking (which is the actual value of an alumni board — referrals, not listings) fits the repo as a lightweight `seeds/alumni_contacts.csv` + a `/alumni-map` Claude Code command that drafts *research summaries* about alumni in target roles from public info (never auto-contacting, per project rules).
- Feasibility verdict per surface, with implementation steps and guardrails: **doc 03**.

---

## D. Prioritized action list

| # | Action | Where | Effort | Recall gain |
|---|---|---|---|---|
| 1 | RSS/Atom/JSON feed channel + `seeds/feeds.csv` (incl. aistartupjobs.com) | new `radar/discover/feeds.py` | S | High |
| 2 | Expand CC sweep to Workday/SmartRecruiters/Breezy/JazzHR + sync `ATS_URL` | `commoncrawl.py`, `common.py`, `smallats.py` | M | High |
| 3 | Niche verticals channel: legal ops board, lawnext, r/legaltech, Above-the-Law | new `radar/discover/niche.py` + websearch seeds | M | High (tailored) |
| 4 | Grow + bucket + prune `search_queries.csv` (~40 rows) | seeds + refresh-jobs step | S | Medium |
| 5 | Reddit JSON channel | new `radar/discover/reddit.py` | S | Medium |
| 6 | Alumni bridge: `import-alumni` + inbox convention + `/alumni-map` | new `radar/alumni.py`, `.claude/commands/` | M | Medium (unique deals) |
| 7 | USAJobs key setup step in refresh command | docs/command | XS | Medium (reg-risk seats) |
| 8 | Keyword families for niche vocab (legal ops, litigation support vendor, fund formation analyst…) | `keywords.py` | S | Unlocks 1–6 |
| 9 | Wayback-as-discovery, location-drop audit, TITLE_DROP regression table | misc | S | Low |

Docs 02 and 03 expand items 3 and 6; `04-claude-code-implementation-plan.md` turns all of the above into an ordered, paste-ready implementation brief for Claude Code.
