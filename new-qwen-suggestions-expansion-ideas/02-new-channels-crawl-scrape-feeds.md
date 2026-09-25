# 02 — New discovery channels: crawling, scraping, feeds, keyless/public APIs

Each idea is a proposed `radar/discover/<name>.py` module (or an extension of an existing one),
runnable via `python -m radar discover <channel>`, obeying the politeness client in `radar/http.py`
(1 req/s/host, robots.txt, UA with contact email, everything logged). Rate-limit and CORS notes are
inline. **CORS is irrelevant server-side** — it only binds browser JS; every channel here is
Python/CI-side so no CORS block applies; the real constraints are robots.txt, 429/403 edge rules,
and API quotas, each noted below.

## 1. Sitemap-first ATS harvesting (`discover/sitemaps.py`) — highest yield/effort ratio

Instead of guessing board tokens (CDX) or probing subdomains, fetch `sitemap.xml` /
`robots.txt#Sitemap:` lines for a fixed registry of career-platform hosts and enumerate all
posting URLs found there:

| Platform | Public listing pattern | robots/rate notes |
|---|---|---|
| Greenhouse | already CDX-covered; add `boards-api.greenhouse.io/v1/boards/<token>/jobs` per token found anywhere (already used by ats/greenhouse.py) | generous, documented |
| SmartRecruiters | `smartrecruiters.com/api/companies/<company>/jobs?format=json` — public JSON per company; api.smartrecruiters.com is robots-blocked but the **cdn.smartrecruiters.com** sitemap index lists all companies' job JSONs; test which path robots allows; fallback: employer-hosted JSON-LD pages | robots conflict → keep exempt list user-approved only |
| Breezy | `breezy.hr/xml-feeds` per tenant: `<tenant>.breezy.hr/xml-feeds` full RSS of all postings | keyless, no rate doc, be polite |
| JazzHR | `<tenant>.applytojob.com` + `/feed` RSS on each board | keyless |
| Personio | `<company>.jobs.personio.de/xml` public XML feed (some US cos use it) | keyless |
| Teamtailor | `<company>.teamtailor.com/jobs` HTML + JSON-LD JobPosting on each page | keyless |
| BambooHR | `<company>.bamboohr.com/careers/list` JSON endpoint (public) | keyless |
| Workable | `apply.workable.com/api/v3/accounts/<acct>/jobs` POST-search + public JSON-LD | light throttling observed |
| Recruitee | `<co>.recruitee.com/api/offers/` JSON | keyless |
| Joinrs/Homerun/Postings/Potentia/Rippling/Employ | each has a public JSON or JSON-LD board | low volume |
| Workday | `<tenant>.wdN.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs` POST JSON (already used); harvest tenant slugs from CDX `%2Fwday%2F` hits and from sitemap entries ending in `/careers/<site>` | 429 at >~1 rps — the 1/s limiter already handles |
| iCIMS | `search-careers<N>.icims.com/jobs/en-us/?q=...` public search pages + per-corp `feed` RSS (`careers-<corp>.icims.com/feed`) | keyless |
| SuccessFactors RMK | `<tenant>.sapsf.com/.../jobs` JSON + `sitemap.xml` per RMK site (Burford/Fitch pattern generalized) | keyless |

Implementation sketch: `seeds/platform_feeds.csv` with columns
`platform,url_template,format(json|rss|xml|html),notes`; loop with the shared client; every posting
becomes a `Lead(source="sitemaps:<platform>")` and goes through Phase 4 verification as usual.

## 2. CDX expansions (`commoncrawl.py` edits)

- Add patterns for new platforms: `*.breezy.hr/*`, `*.applytojob.com/*`, `*.jobs.personio.*/*`,
  `*.teamtailor.com/jobs/*`, `*.bamboohr.com/careers/*`, `*.myworkdayjobs.com/*`,
  `*.sapfico.com/*` + `*.sapsf.com/*` (RMK tenants).
- **First-seen recency query**: CDX supports `from=YYYYMM&to=YYYYMM` + `resultType=identity` to
  list URLs *newly captured this crawl* — turn "recently posted" into a first-class filter without
  any date parsing: anything whose earliest snapshot is within 30 days is a fresh lead.
- Use `fl=url,timestamp` and dedupe against `data/cc_boards.json` state (already done).
- Keep the user-approved robots exemption scoped to `index.commoncrawl.org` only.

## 3. Wayback-as-a-channel upgrades (`wayback.py`)

- Current use = recurrence check. Extend to **diff-and-alert**: for each watchlist URL, compare
  latest two snapshots' extracted pay/title text; emit leads when a *closed* seat reopens or pay
  changes mid-flight (cdx JSON API `https://web.archive.org/cdx/search/cdx?url=...&output=json`
  is keyless; throttle ~1/s per host rule; occasional 5xx → retry/backoff already in client).
- Snapshot-fallback for blocked hosts: where citadel.com/jobleads.com return 403 live, Wayback's
  copy can populate the *outside-location/not-open* tables marked `source=wayback_fallback` —
  never listed as verified-open (rule preserved: verify means live fetch).

## 4. HN Algolia API (`hn.py` upgrade)

Replace HTML thread-parsing with `http://hn.algolia.com/api/v1/search_by_date?query=...&tags=comment`
against monthly "Who is hiring" story IDs discovered via `tags=story,author_whoishiring`. Keyless,
documented 10k/min quota (far above our 1/s). Gives exact timestamps → true "posted in last N days"
HN leads, plus back-to-Work (Ask HN) legal-tech hiring posts. Free lunch: also search
`tags=story` for "is hiring" launch posts from YC startups (YC's own `ycombinator.com/jobs` is
Cloudflare-guarded → skip; Algolia mirrors most of its signal).

## 5. Keyless aggregator & niche APIs (new `discover/open_feeds.py`)

| Source | Endpoint | Auth | Notes |
|---|---|---|---|
| Arbeitnow | `www.arbeitnow.com/api/job-board-api` (page param) | none | filter `category in [legal, financial]`; 1/s fine |
| Remotive | documented public API `remotive.com/api/free-jobs?category=legal` (free tier of their partner API) | none | remote-only |
| RemoteOK | `remoteok.com/api` JSON, `?tag=legal` | none | soft 429 if >1rps — covered |
| WoWR | `weworkremotely.com/categories/remote-legal-jobs.rss` | none | RSS |
| The Muse | already wired; expand categories: add "Consulting" and "Science and Research" to capture research-analyst classes | optional key | 1200/hr keyed; unkeyed works today |
| Hacker News | §4 | none | |
| EURES (EU public job portal) | session-token flow — ToS-gray, note only | | |
| USAJOBS | `api.usajobs.gov/Search?keyword=attorney&resultsPerPage=100&formatted=true` | free key (email signup) | put key in `.env`; already gated |
| Adzuna | already gated; add category=`law-legal` AND `consulting` loops over NYC metro | key | |
| Jooble | key required, ToS forbids storing results | key | skip — do not chase |
| ATS board directories | none exist publicly for Greenhouse/Lever/Ashby — that is exactly why §1/§2 matter | | |
| Wellfound (AngelList Talent) / workatastartup | login-gated search, ToS bars scraping → **do not**; rely on HN + YC launch-post signal instead | | |
| BuiltInNYC | public HTML search pages + possible RSS (`builtinnyc.com/jobs/feed` — verify path and robots at impl time) | none | prior review flagged aggregators; BuiltIn is the cleanest of them |
| Idealist (nonprofit incl. legal-aid/integrity orgs like MuckRock) | `idealist.org/api` requires key; public search HTML is robots-ok for listings pages | optional | low pay floor → mostly filtered by rubric anyway |
| GovernmentJobs.com | `governmentjobs.com/rss/listing.aspx?kw=attorney&loc=New+York` RSS | none | big public-sector recall beyond statejobs.ny.gov |
| uscourts.gov | per-district careers HTML pages, static, robots-ok | none | see doc 01 §G |
| Federal Reserve Board | `federalreserve.gov/careers` + district-bank iCIMS feeds | none | |
| NY Courts / NYC government | nyc.gov careers uses SuccessFactors RMK → detectable by phase 2 | none | |
| CourtListener RPC/REST | `courtlistener.com/api/rest/4/` keyless reads for RECAP dockets — not jobs, but lets Phase 4 *verify litigation-claims in postings* (e.g., "active portfolio includes X") — optional enrichment | free token | |

## 6. Employer-graph seeders (new `discover/firm_graph.py`)

Firms-begetting-firms expansion feeding `seeds/companies.csv`:
- **FINRA Member Firm Directory CSV** (finra.org/membersfsd — downloadable, public domain-ish)
  → every broker-dealer with an NYC office ≥N employees becomes a candidate row (ATS-detect them).
- **NY DFS regulated-entity lists** (licensed mortgage/lender/crypto trust companies).
- **LFMA/ALFA member lists** (litigation finance trade assocs) — ALFA's directory is public.
- **Am Law 100/200** (law.com paywalled; use the public Wikipedia mirror + NLJ archive PDFs on
  archive.org) → KM/practice-attorney boards at firms (§C of doc 01).
- **VC portfolio pages**: keyless HTML of regtech/fintech funds' portfolios (Outpost VC, Ribit,
  Compound, FinCapital, BOND's public list, a16z speedrun companies) → startup ATS boards.
- **awesome-list mining**: raw README.md files on GitHub (lawtech/regtech/ai-safety curated
  lists, e.g. awesome-lawtech-style repos) — parse company URLs as firm seeds.
- **OpenCorporates API** (keyless tier, 50/day) — narrow use: confirm entity name→country for
  foreign-named litigation funders; probably not worth budget. Note only.

## 7. Google-Jobs-shaped recall *without* Google scraping

Google Search itself is off-limits to script (ToS + captcha walls). Two compliant substitutes:
- **DuckDuckGo HTML endpoint** (`html.duckduckgo.com/html/?q=site:jobs.lever.co ...`) — ToS-gray;
  prefer Claude Code WebSearch (already the `websearch` channel) and just *grow the query matrix*
  (doc 03).
- **Public Bing API?** deprecated/requires key → fold into SerpAPI gate (already exists).

## 8. Email/newsletter ingestion (passive, zero-crawl)

- Litigation-finance and legal-ai newsletters (Lawfare Jobs, Legal Tech Now's weekly roundup,
  Above the Law's lateral-hire posts) publish postings links in plain HTML. If the user forwards
  emails to a dedicated address, an `import-leads` variant could parse saved `.eml`/markdown drops
  in `data/inbox/` — same inbox-bridge pattern the alumni doc proposed, reused. Zero bot surface.

## 9. RSS/Atom registry (complements prior review's Task 2 — kept short)

`seeds/feeds.csv` should additionally register: per-employer Greenhouse feeds
(`boards.greenhouse.io/<token>/feed.rss`), Lever (`jobs.lever.co/<token>?utm=rss`), Ashby
(`jobs.ashbyhq.com/<token>/feed.xml` — verify path), Breezy xml-feeds, JazzHR `/feed`,
GovernmentJobs RSS, Workable per-account RSS, plus each newsletter from §8 that exposes RSS.
Feeds carry pubDate → free freshness signal for the † "new since last run" marker.

## 10. What NOT to do (guardrails, restating project rules concretely)

- No LinkedIn/Indeed/Glassdoor/Zippia scraping (ToS + bot walls; Zippia moved to walling too).
- No SmartRecruiters `api.` host without explicit user robots-exemption (their robots disallows;
  their *company JSON under smartrecruiters.com/api/companies/...* is served from the main host —
  check robots there before use; if disallowed, stay on JSON-LD page copies).
- No Solving captchas / Cloudflare JS challenges (Citadel stays blocked).
- No `workatastartup.com`, no Wellfound authed data.
- Respect 429 Retry-After with exponential backoff (client already does; keep new channels inside it).
- All new exempted hosts require a `RADAR_ROBOTS_EXEMPT_HOSTS` entry = explicit user choice.
