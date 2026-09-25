# Niche sources, aggregations and feeds — the tailored-sweep catalog

Companion to `01-code-review.md` (items A2–A4). Every source below was chosen against the candidate
profile in CLAUDE.md: Penn JD + clerkships + BigLaw exit + Morgan Stanley credit risk, targeting
litigation-finance underwriting, legal-AI research/build, business-side regulatory risk, finance
academies, embedded fund research, and credit-intelligence legal analyst seats. NYC/hybrid or US-remote.

Legend: **Feed** = machine-readable (RSS/Atom/JSON/API) → belongs in the proposed `feeds.py` channel ·
**Poll** = HTML listing page, poll politely like `public_sector.py` already does ·
**Search** = one row added to `seeds/search_queries.csv`, no code needed ·
**Manual/Claude** = gathered by Claude Code's WebSearch during `/refresh-jobs`.

## 1. The three sources named in the request

| Source | Access | Verdict for this profile |
|---|---|---|
| **aistartupjobs.com** | Feed (RSS; confirm exact path — historically `/rss.xml`, also per-category feeds) | **Worth it.** Legal-AI and "applied legal / legal engineer" seats at seed-stage AI companies appear here before they surface in `site:ashby` searches. Filter with existing keyword families (`legal engineer`, `applied legal research`, `AI governance`). Expect ~1 relevant posting/month; near-zero cost. |
| **r/legaltech** (and r/biglaw career threads, r/artificial × hiring) | Poll via public JSON: `reddit.com/r/legaltech/new.json` (unauthenticated, 60 req/min budget; stay ≤1 req/min) | **Worth it as a lead generator only.** Vendors (Everlaw, Casetext-type, Harvey, Legora…) and law firms post directly; recruiters fish in comments. Stale-post risk is handled by the project's own verify-before-list rule. Also scan r/biglaw monthly career threads for "JD to ___" exits that name hiring teams — those become *company registry* entries more often than direct leads. |
| **legaloperationsjobboard.com** | Poll (WordPress job-listing pages; check robots first) | **Marginal but cheap.** Legal-ops roles are mostly the "compliance operations / paralegal-adjacent" family that CLAUDE.md hard-excludes. Two exceptions worth keeping: (1) legal-engineering / AI-enablement seats at firms and funds, (2) "legal solutions architect / knowledge management" seats at litigation-support vendors (eDiscovery→underwriting adjacency). Add it to the feed registry but expect a high poor-match rate; let the rubric do its job. |

## 2. Legal-specific aggregators & boards (the "what other boards aggregate from" layer)

| Source | Access | Why |
|---|---|---|
| **Legal.io jobs** | Search/Poll | Already used once in queries; has structured legal-ops + counsel listings, many at fintechs. |
| **GoInHouse** | Search | In-house counsel listings; most will hit the off-target-practice poor-match rules, but regulatory-counsel-at-fintech seats slip through usefully. |
| **LawNext Jobs** (`lawnext.com/jobs`) | Poll/Search | Firm-side, but its "alternative careers" and legal-tech vendor job sections are on-target. |
| **Above the Law** | Manual/Claude | Not a board; its lateral-hire roundups ("BigLaw to hedge fund," "clerk to ___") reliably *name employers that hire this profile* → feed `seeds/companies.csv`, not `leads.jsonl`. |
| **eFinancialCareers** | Search (`site:efinancialcareers.com legal OR regulatory analyst new york`) | The canonical finance-industry job aggregator; reg-risk and market-intelligence seats at trading firms live here. Cloudflare may block direct polling — route via websearch leads only. |
| **Financial Times / Bloomberg Law / Reuters Legalnews jobs widgets** | Search | Same reasoning: treat article mentions of hiring programs as company-registry seeds. |
| **IAL (International Arbitration Lawyer) / GAR, Global Investigations Review job boards** | Poll/Search | Niche; GI Reports' board occasionally lists investigations-analyst seats at banks — matches his Quinn Emanuel investigations background. |
| **ILTA / Legal Ops Community (LOC) job channels** | Manual/Claude | LOC Slack is members-only (no scraping); its *public* weekly digest sometimes links postings. Note as user-assisted only. |
| **Clio's legal-tech job list / ClioCon sponsor lists** | Manual | Sponsor companies of legal-tech conferences ≈ the set of employers building legal-AI teams; harvest into `companies.csv`. |
| **Prediction-market & crypto-legal niche: CoinDesk jobs, The Block jobs, a16z crypto job board (jobs.a16z.com — Greenhouse-backed)** | Feed/Poll | Matches the stablecoin/prediction-markets queries already in the seed file; a16z portfolio pages list legal/policy openings across portfolio cos. |

## 3. Finance/fund-side niche feeds (higher expected yield than legal boards)

| Source | Access | Why |
|---|---|---|
| **Point72 / Citadel / Schonfeld / Millennium / Elliott etc. career-page JSON-LD** | already covered by `ats/html.py`; extend registry | Academies + embedded-research seats; note Citadel remains blocked (Cloudflare) — keep using their LinkedIn *manual* checks by the user, never scraped. |
| **OpenInvest, Replicon-style "who's hiring" pages of fund-service platforms (SS&C, Citco, Maples, Preqin, PitchBook)** | Poll via detected ATS | Credit-intelligence and LP-side research seats; several already in `companies.csv` with slugs. |
| **Wellfound (AngelList) public search API** | Feed (API, free key) | Startup legal/business roles incl. pre-Series-A legal-AI cos that later move to Ashby; wellfound.com/terms allows API access with key. |
| **Hacker News Who-is-hiring RSS (`hnrss.org/whoishiring`)** | Feed | Complements existing Algolia scrape; catches posts edited into top-level comments late in the month. |
| **US Senate/House + agency OA RSS (SEC OCIO/OEMD announcements, Federal Register hiring notices)** | Feed | Public-sector reg-risk seats beyond USAJobs keyword search. |
| **Idealist.org RSS (`idealist.org/rss/...`)** | Feed | Policy-research think-tank seats (Capstone-style) he'd score well on. |
| **Work-trending signals: Ashby/Greenhouse/Lever "new job" pings via `boards-api` polling of the discovered-board list** | Feed | The CC sweep already builds `discovered_boards.csv`; add each new board's *API feed* to `feeds.csv` automatically — this is exactly how commercial aggregators (Jobber, Joveo-style crawlers) scale, minus the ToS problems, because these endpoints are public and documented. |

## 4. Expanded `search_queries.csv` (drop-in rows, bucket-tagged)

New schema proposal: `query,channel,bucket,results_used` (bucket column feeds the pruning pass).

```csv
"site:job-boards.greenhouse.io ""litigation finance"" OR ""legal finance"" associate OR analyst",websearch:ats,litfinance
"site:jobs.lever.co ""underwriter"" OR ""underwriting"" legal OR claims OR litigation",websearch:ats,litfinance
"""pre-settlement"" OR ""post-settlement"" funding analyst job New York",websearch:aggregator,litfinance
"site:jobs.ashbyhq.com ""legal engineer"" OR ""applied AI"" OR ""legal innovation"",websearch:ats,legalai
"site:aistartupjobs.com legal OR counsel OR policy",websearch:aggregator,legalai
"site:legal.io ""regulatory counsel"" OR ""legal ops"" New York",websearch:aggregator,legalops
"reddit r/legaltech hiring ""legal engineer"" OR ""research lawyer""",websearch:community,legalops
"site:jobs.smartrecruiters.com ""credit"" ""legal analyst"" OR ""covenants"",websearch:ats,creditintel
"site:bamboohr.com ""distressed"" OR ""special situations"" analyst",websearch:ats,creditintel
"""regulatory risk"" associate OR analyst ""trading firm"" OR ""market maker"" New York 2026",websearch:aggregator,regrisk
"site:myworkdayjobs.com ""credit risk"" ""associate"" ""legal"" OR ""policy"" New York",websearch:ats,regrisk
"""investment academy"" OR ""rotational program"" ""experienced professionals"" 2026 apply",websearch:aggregator,academies
"""qualitative research"" analyst hedge fund New York ""no finance experience""",websearch:aggregator,embedded
"site:themuse.com ""regulatory counsel"" fintech New York",websearch:aggregator,fintech
"""stablecoin"" OR ""prediction market"" counsel OR policy associate greenhouse lever ashby",websearch:ats,crypto
"site:efinancialcareers.com ""market intelligence"" OR ""event driven"" analyst",websearch:aggregator,embedded
"lawnext.com ""legal tech"" OR ""innovation"" counsel jobs",websearch:aggregator,legalops
"site:wellfound.com legal counsel AI New York OR remote",websearch:aggregator,legalai
"""forensic"" OR ""investigations"" analyst bank New York FINRA OR OCC background",websearch:aggregator,regrisk
"Penn Law alumni hiring ""legal analyst"" OR ""credit"" 2026",websearch:community,alumni
```

Retire after next run if still zero-yield: the three current `results_used=0` rows
(`"legal analyst" greenhouse`, `lever litigation underwriting`, `greenhouse prediction markets`) —
keep them only if phrasing changes materially.

## 5. Keyword-family additions (`radar/keywords.py`) so new channels actually recall

New `TITLE_FAMILIES` rows:

```python
("legal ops engineering", r"legal (engineer|technology|solutions|innovation|transformation)|knowledge( |-)management (attorney|lawyer|counsel)"),
("claims/lit support underwriting", r"claim(s)? (assessor|evaluator|analyst)|litigation (support|consulting)|e-?discovery analyst"),
("fund/LP research", r"alternatives (research|analysis)|due diligence (associate|analyst)|fund (formation|reporting) analyst|LP reporting"),
("regulatory exams/surveillance", r"(surveillance|exams?| examinations?).{0,30}(counsel|analyst|specialist)|market conduct|trade practice"),
("government-affairs analyst", r"government affairs|congressional (relations|affairs)|legislative (aid|assistant|analyst)"),
```

New `DESC_PHRASES`: `"symplicity"` (alumni-board exports), `"penn law"`, `"ivy league"`,
`"top chambers"`/`"legal 500"` (lit-finance vendor quality signal), `"structured credit"`,
`"CLO"`, `"rescue financing"`. Guardrails unchanged: relevance still requires a knowledge-work title.

## 6. What NOT to add

- **LinkedIn / Indeed / Glassdoor scraping** — banned by CLAUDE.md and ToS; the alumni question (doc 03) deliberately routes around this.
- **ZipRecruiter/Jooble raw scraping** — aggressive bot walls + ToS; Jooble has a licensed API (paid) — skip unless user pays.
- **Firm career sites behind Avature/Rippling login walls** — no login bypass per project rules; Rippling-hosted boards (`*.ripplehire.com`) are public though — add to `ATS_URL` + a simple JSON pull (`/{token}/jobs` listing) as part of item 2 in doc 01.
- **Members-only Slack/Discord job channels** (LOC, Foundation Capital network) — flag as *user-forwarded* content into the alumni inbox convention (doc 03) rather than automated access.
