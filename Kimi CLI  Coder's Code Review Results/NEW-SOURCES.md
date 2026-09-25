# New sources — niche boards, feeds, and aggregations, each live-tested

Every source below was fetched during this review (2026-09-24) with the project's polite
user-agent. **(verified live)** = fetched successfully with the stated payload.
**(unverified)** = could not confirm; do not build on it without a re-check.

Integration contract for everything here (matches the existing architecture): new sources
produce **leads**, Phase 4 verifies on the employer's own posting. A noisy source costs
verification requests but cannot pollute output.

---

## Tier 1 — add this week (verified live, machine-readable, policy-clean)

### 1. HireLegalOps — `https://hirelegalops.com/jobs.json` ⭐ best find of this review

- Niche board exclusively for legal-ops roles (CLM admins, contract managers, legal project
  managers, legal AI enablement). ~156 live jobs.
- **Public JSON feed, explicitly sanctioned**: `jobs.json` verified live — HTTP 200, ~125 KB
  structured JSON with title/company/location/salary/posted_at/URL. Also `/roles.json`,
  `/locations.json`, per-page JSON-LD, and an `/llms.txt` documenting the machine surfaces.
- robots.txt (fetched): both the human surface and the machine surfaces are intended for
  automated reading. `Allow: /`; only `/api/` and `/thank-you` disallowed.
- **Integration**: one ~60-line `radar/discover/feeds.py`-style module polling `jobs.json`,
  emitting `Lead`s. Relevance filter should keep only the legal-tech-adjacent families
  (legal engineer, legal product, innovation counsel, AI workflow, knowledge engineering,
  legal data/research) and let routine ops titles (e-billing, CLM admin, matter management,
  coordinator) fall to poor-match — ordinary legal-ops seats are off-target for this candidate.
- No ToS concerns — the feed exists to be read by machines.

### 2. Direct ATS endpoints of legal-tech employers (all verified live, keyless, HTTP 200)

Add to `seeds/companies.csv`; the existing adapters handle them with zero new code:

| Employer | Why it fits | Endpoint (verified live) |
|---|---|---|
| **Harvey** | legal AI; lists multiple "Legal Engineer" NYC roles | `api.ashbyhq.com/posting-api/job-board/harvey` |
| **Ironclad** | CLM; counsel/legal-engineering seats | `api.ashbyhq.com/posting-api/job-board/ironcladhq` |
| **Relativity** | eDiscovery | `boards-api.greenhouse.io/v1/boards/relativity/jobs` |
| **Everlaw** | eDiscovery/litigation | `boards-api.greenhouse.io/v1/boards/everlaw/jobs` |
| **DISCO** | eDiscovery | `boards-api.greenhouse.io/v1/boards/disco/jobs` |
| **Clio** | practice mgmt; 132 open jobs | Workday CXS POST `clio.wd3.myworkdayjobs.com/wday/cxs/clio/ClioCareerSite/jobs` with `{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}` |

- **LinkSquares** (CLM): careers page confirmed to use a Greenhouse embed, but the slug is
  JS-loaded — `linksquares` 404s. **(unverified)**; one rendered look at
  `linksquares.com/careers` resolves it.
- **Evisort**: acquired by Workday; careers redirects to product pages. Dead end.

### 3. Arbeitnow — `https://www.arbeitnow.com/api/job-board-api`

- General job board with a **keyless, free JSON API** (verified live: 200, paginated).
  EU/tech-weighted but has occasional legal-ops/compliance hits.
- Near-zero cost to add alongside the Muse channel; another hedge against single-source
  failure. (Survey result: beyond The Muse and Arbeitnow there is **no** major keyless general
  job feed — Jooble, Adzuna, Careerjet, USAJobs all require keys; LinkedIn/Indeed/Glassdoor are
  excluded by policy.)

---

## Tier 2 — aggregator-lead sources (allowed paths only)

### 4. Legal Operations Job Board — `legaloperationsjobboard.com/job-board`

- "The Shortlist" — ~289 hand-picked legal-ops/legal-engineering roles, refreshed weekly, run
  by a single practitioner. Bullseye niche for this candidate.
- robots.txt (fetched): **`Allow: /job-board`, `Disallow: /api/`** — the internal JSON API the
  Next.js page uses is explicitly closed. Sitemap 404s.
- **Integration**: weekly fetch of the allowed `/job-board` page (client-rendered — needs the
  existing Playwright install or a manual pass), extract company + title, fan out to those
  companies' own ATS feeds for verification. Do **not** touch `/api/`.
- Low-friction alternative: it's a one-person operation with a weekly newsletter — subscribing
  gives the same content in a parseable email (feeds the alumni/email pipeline in
  ALUMNI-PIPELINE.md).

### 5. AI Startup Jobs — `aistartupjobs.com`

- Aggregator tracking ~34k listings across ~1,900 pre-IPO AI startups, with a "Legal &
  Compliance" facet. Highly relevant surface.
- **(verified live)** The site sits behind a Cloudflare managed challenge — `/robots.txt` and
  every other path return 403/challenge to scripted clients. That is a deliberate anti-bot
  signal.
- **Verdict (agrees with Codex, contradicts any scrape proposal): do not integrate directly.**
  It is a second-hand copy of feeds you can get first-hand. Instead: mine it **once** in a
  browser for the list of AI startups with open legal/compliance seats, add those employers to
  `seeds/companies.csv`, and monitor their Ashby/Greenhouse/Lever boards directly.

### 6. ACC Jobline / CLOC Career Center / LawJobs.com

- `jobline.acc.com`, `jobs.cloc.org`, `lawjobs.com` — all run on the same association
  career-center platform. Their XML feeds exist but robots.txt (fetched for all three)
  **explicitly disallows `/xml_feed/`, `/xml-feed/`, `/search/`**; sitemaps are allowed.
- **Integration**: aggregator-lead at low cadence via sitemap-listed posting URLs only; never
  the disallowed feeds. ACC Jobline is the most relevant of the three (in-house/JD-advantage).
  CLOC skews to the routine-ops seats the rubric excludes.

### 7. legal.io / GoInhouse

- legal.io: robots.txt fetched — `/jobs/` allowed with **`Crawl-Delay: 3`**; JS-rendered.
  Aggregator-lead at that crawl-delay, low priority. (Already sanctioned as a lead source in
  CLAUDE.md.)
- GoInhouse: sitemap index verified (millions of historical job URLs; detail pages allowed in
  robots). **But** it's in the BCG Attorney Search / LawCrossing family — aggressive
  anti-scraping ToS, litigious history, often-stale postings. **Recommend: do not integrate.**

---

## Tier 3 — do not build (with evidence)

### r/legaltech and Reddit hiring threads — **correction to Qwen's review**

Qwen's review proposed r/legaltech "via public reddit.com/r/legaltech/*.json". Verified live
during this review:

- `https://www.reddit.com/robots.txt` → **`User-agent: * Disallow: /`** (blanket disallow
  pointing at Reddit's Public Content Policy).
- Anonymous `.json` endpoints (`/r/legaltech/search.json?...`) → **HTTP 403** (Reddit killed
  anonymous JSON access in 2023).

The only compliant route is the official Reddit Data API with OAuth — which conflicts with the
project's no-login rule and is low value-per-effort for this niche. **Skip Reddit.**

### Litigation-funder automation (Burford, Omni Bridgeway, LexShares)

- Burford: careers page JS-rendered; all `burfordcapital.wdN.myworkdayjobs.com` probes returned
  422 (same as a bogus-tenant control) — **ATS unverified, likely not Workday**.
- Omni Bridgeway: `/careers` 404s. LexShares: `/careers` 422 (bot-blocked).
- These firms carry dozens of roles total, not thousands. The right tool is a **manual
  watchlist** (they're already in `seeds/watchlist.csv`'s spirit) — check them by hand monthly;
  automate only if a clean ATS endpoint is ever identified.

### BCG Attorney Search / LawCrossing / LinkedIn / Indeed / Glassdoor

Excluded by policy (login/ToS) or litigious anti-scraping posture. No change recommended.

---

## Structural recommendation: a generic feeds channel (complements Qwen's and Codex's plans)

Both prior reviews proposed feed/adapter architecture. This review confirms the gap
empirically (no feedparser-like import exists anywhere in `radar/`) and adds the concrete
payload: **one generic `radar/discover/feeds.py` reading `seeds/feeds.csv`** with columns
`url, format (json|rss|atom), label, title_allowlist` would cover Tier 1 items 1 and 3 and
every future feed-shaped source with no new code per source. Feed fetching inherits the
polite client's rate limiting, robots checks, and run-log accounting for free.

Suggested starter `seeds/feeds.csv`:

```csv
url,format,label,title_allowlist
https://hirelegalops.com/jobs.json,json,hirelegalops,"legal engineer|legal product|innovation|knowledge|AI|legal technolog|legal data|legal research"
https://www.arbeitnow.com/api/job-board-api,json,arbeitnow,"legal|compliance|counsel|regulatory"
```

## Search-query additions (cheap recall, complements prior reviews' query packs)

`seeds/search_queries.csv` (14 rows, 4 yielded 0 last run) has no rows for the sources above.
Add:

```csv
query,reason
site:hirelegalops.com legal engineer,hirelegalops coverage via websearch fallback
"legal operations" "legal engineer" (NYC OR remote),legal-ops engineer seats
site:jobline.acc.com (counsel OR "legal counsel") "New York",ACC jobline in-house
"AI governance" (counsel OR policy) (JD OR "juris doctor"),AI governance seats
"legal knowledge engineer",legal-AI build seats
site:wd1.myworkdayjobs.com OR site:wd3.myworkdayjobs.com OR site:wd5.myworkdayjobs.com "counsel" "New York",Workday-hosted counsel roles currently unqueried
site:jobs.smartrecruiters.com (counsel OR legal) "New York",SR-hosted roles currently dark
"bankruptcy clerkship preferred" (analyst OR associate),credit-intelligence niche
```

Also surface `results_used == 0` streaks in the run log so dead queries get pruned
(4 of 14 currently yield nothing).
