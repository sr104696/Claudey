# New Qwen Suggestions — Expansion Ideas (2026-09-26)

Second-wave idea set for pulling **more roles, more postings, more firms, and whole industries
not yet on the radar** — including tangential/orthogonal sectors that look unrelated but map onto
the same "investigate → synthesize → decide → write" job shape, plus new crawling/scraping/feed/
keyless-API channels. Written to be complementary to (not a repeat of)
`Qwen Coder's Code Review Results/`, which already covered: Common Crawl ATS gaps (Workday et al.),
an RSS `seeds/feeds.csv` registry, Reddit `.json`, legal-ops boards, and the alumni inbox bridge.
Everything here respects the project rules: robots.txt honored, ≤1 req/s/host, no LinkedIn/Indeed/
Glassdoor scraping, no login/captcha/paywall bypass, verify-before-list, keys in `.env`.

## Contents

| Doc | What it is |
|---|---|
| [01-tangential-sector-map.md](01-tangential-sector-map.md) | The "wide-ranging" recall doc: adjacent/orthogonal industries with the same job DNA, named firm pools per sector, and drop-in search queries |
| [02-new-channels-crawl-scrape-feeds.md](02-new-channels-crawl-scrape-feeds.md) | New discovery channels: keyless/public APIs, sitemap & JSON-LD harvesting, CDX expansions, Wayback diffing, HN Algolia, GitHub-driven employer mining, feed/aggregation layer |
| [03-more-of-the-same-faster.md](03-more-of-the-same-faster.md) | Ways to get *more volume of the existing types* of postings: query-matrix expansion, board-token growth, dedupe/recency tricks, freshness signals for "recently posted" |
| [04-priority-and-sketches.md](04-priority-and-sketches.md) | Ranked action table + paste-ready implementation sketches (new seeds CSVs, module stubs, keyword additions) |

## Headline ideas (one line each)

1. **Mine the SEC's own talent pipeline**: usajobs.gov API (needs free key) *plus* keyless
   `sec.gov/about/commission-engagement/strategy/current-employment-opportunities` and FinCEN/
   FHFA/OCC/PFB pages — regulators hiring lawyers is a direct feeder pool for the "regulatory risk
   at trading firms/banks" seat family, and ex-regulator *hiring* firms post around them.
2. **Orthogonal-but-isomorphic sectors** (doc 01): competitive-intelligence units, geopolitical/
   country-risk consultancies (Eurasia Group, Control Risks, S-RM), disputes-analytics & damages
   consultancies (Analysis Group, Cornerstone Research, Compass Lexecon, Charles River Associates),
   credit-rating agencies' legal/analytic seats (already partially via Fitch — add Moody's, S&P,
   Kroll/ISS), investigative journalism shops' legal-adjacent research desks (ICIJ, MuckRock),
   arbitration institutions (ICC, ICDR/AAA, WIPO), sanctions/export-control advisory, and
   government-contract protests (BPA/GAO bid protest teams at Baker Botts-style boutiques).
3. **Sitemap-first harvesting beats CDX for known hosts**: most ATS platforms publish full
   `/sitemap.xml` or `/jobs-sitemap.xml`; Greenhouse/Lever/Ashby boards also expose JSON-LD
   `JobPosting` on every page — crawl sitemaps of ~30 ATS/career-platform domains (SmartRecruiters
   public JSON-LD pages, Breezy, JazzHR, Personio, BambooHR, Teamtailor, Recruitee, Workable,
   Joinrs, Homerun, Postings.io, Potentia, myworkdayjobs tenant sitemaps) instead of guessing tokens.
4. **Keyless aggregation endpoints**: HN Algolia API (`hn.algolia.com/api/v1/search_by_date` —
   replaces HTML parsing of whoishiring threads and gives freshness), Google Jobs structured-data
   surfacing via `r.jina.ai`-style readers is ToS-gray — prefer the clean list in doc 02 §APIs;
   Remotive API (free tier), Arbeitnow API (keyless), Apptrio/Welcometothejungle GraphQL (EU, some
   NYC), Zippia/Scoutably feeds, `weworkremotely` feed, Emedded, RemoteOK JSON — all filterable by
   `legal`/`compliance` categories, all documented and rate-limit-friendly.
5. **"Recently posted" without any new site**: pull every board twice a week and diff against
   `data/snapshots/` (already exists) — the diff *is* the recency signal; additionally parse
   `datePosted` from JSON-LD (present on nearly all ATS pages) and lead-filter on it; use CDX
   `from=` timestamps to find URLs first-seen in the last N days across `jobs.lever.co/*` etc.
6. **Employer-graph expansion from filings and registries** (keyless): NY DFS regulated-entity
   lists, FINRA member firm directory (downloadable CSV), SIFMA/CDT membership lists, litigation-
   finance trade assoc (LFMA/ALFA) member lists, IADC/DRI committee rosters, Am Law 100/200 lists,
   VC portfolio pages of fintech/regtech funds (Outpost, Ribit, Paradigm, a16z cs-list) — each is a
   *firm seed generator* feeding Phase 2 ATS detection, exactly how companies.csv grew once.
7. **Role-title synonym explosion** (doc 03): the current TITLE_FAMILIES miss entire vocabularies —
   "Legal Operations Analyst", "Contracts Manager" (excluded anyway), but crucially: "Research
   Counsel", "Knowledge Management Lawyer", "Litigation Support Analyst", "Claims Analyst" (insurance
   coverage counsel-adjacent), "Underwriting Counsel", "Escalations Counsel", "Trust & Safety
   Counsel", "Policy Counsel", "Government Affairs Analyst", "Legislative Aide/Analyst", "Examining
   Attorney", "Staff Attorney (Ombudsman)", "Special Master", "Referee", "Hearings Officer",
   "Rulemaking Analyst", "Fellow (Legal/Econ)" — many sit in *public sector and insurance*, today's
   blind spots.
8. **Judiciary & clerkship-adjacent pipelines**: USCourats jobs API (uscourts.gov careers pages are
   static HTML per district — SDNY/EDNY/DNJ posting bankruptcy-chambers "law clerk to Chief Judge
   Bankruptcy" roles that match the bankruptcy-exposure rule), NY Courts, ICC/ICDR roster jobs,
   ITC (trade law!), Federal Reserve system-wide careers JSON (federalreserve.org careers uses an
   iCIMS public feed; NY Fed already pulled — the *other* 11 districts aren't).
9. **Conference/job-board flywheel from bar associations**: NALP Career Services Guide (public XLSX
   of law-school career sites = hundreds of keyless job boards), ABA Careering, city bar association
   job lists (NYC Bar, NY State Bar's lawyer-relations referral boards), ACC (in-house counsel
   association) job board has a public search page, AIPLA/ABA committees post unlisted lateral needs
   in newsletters — all fetchable HTML, none require auth.
10. **GitHub-as-hiring-signal channel**: firms building legal-AI tools post engineer+lawyer collab
    roles and sometimes hire through GitHub job listings (`github.com/<org>` profile "We're hiring"
    links); more robustly, watch the *company lists behind awesome-legaltech / awesome-regtech /
    awesome-ai-safety lists* (raw README markdown, keyless) as continuously-updated firm seeders.
