# Sweep and Source Coverage Review

**Review date:** 2026-09-25
**Scope:** The discovery sweep, the employer registry, candidate-relevance filtering, source
provenance, and the possibility of using Penn alumni services. This is a design/code review;
it deliberately does **not** add a connector that would authenticate to, scrape, or circumvent
a member-only site.

## Executive assessment

The radar has a strong foundation: it verifies final postings on the employer source, preserves
rate limiting and robots checks, treats aggregators as leads rather than proof, and has broad
coverage of Greenhouse, Lever, Ashby, Workday and several smaller ATSs. Those choices reduce the
risk of reporting stale or unactionable roles.

The largest comprehensiveness gap is **lead generation before verification**, not scoring. The
current sweep is concentrated in the ATS estates it can enumerate and just 14 manually curated
web-search queries. It therefore has a structural blind spot for (1) employers using unimplemented
ATSs or custom career sites, (2) niche legal-tech and legal-operations boards, (3) trade
associations and research vendors that hire adjacent roles, and (4) authenticated alumni listings.

The recommended approach is a two-tier funnel:

1. **Broad, provenance-rich discovery:** collect light leads from permitted public feeds, public
   board pages, official newsletters/RSS, and user-exported alumni searches.
2. **Strict canonical verification:** resolve each lead to the employer's public posting, then keep
   the existing field extraction, exclusion rules, scoring, and deduplication.

This preserves the project rule that an aggregator never becomes final evidence.

---

## Findings, ordered by expected value

### P0 — Make source coverage measurable and sweep by gap, not only by keyword

**Observed implementation.** `pipeline.CHANNELS` starts six discovery modules; the web-search
module only counts leads imported from Claude, and the query file contains 14 queries. The board
puller covers a focused ATS set and marks several employers as `none`, `blocked`, or `channel`.

**Why it matters.** A run cannot currently answer: *which role family, source type, geography, or
ATS family had no fresh candidates this week?* An empty result can mean no jobs exist, a board was
not searched, a search provider did not return it, or a title was filtered before verification.
This makes coverage look stronger than it is.

**Recommendation.** Add a `source_catalog` (CSV or YAML) and a weekly `coverage.md` output.
For every source, record: `source_id`, source class, public/authenticated, terms/robots decision,
feed/landing URL, intended role families, geography, cadence, last success, leads found, leads
verified, canonical-resolve rate, duplicate rate, and explicit skip/failure reason. Define weekly
coverage targets, for example:

| Dimension | Suggested minimum |
|---|---:|
| Role families (legal AI, litigation finance, regulatory/market structure, credit research, qualitative research) | 1 successful source each |
| Source types (employer ATS, public-sector, niche board, web search, alumni export) | 1 successful source each; alumni is manual unless approved |
| ATS families | Greenhouse, Lever, Ashby, Workday, plus one "custom/other" sweep |
| Freshness | Public boards: ≤7 days; employer boards: current run; alumni export: user-selected |

Have the run log flag a target as **not covered**, distinct from "searched, no result." This is
more useful than adding many sources without a health metric.

### P0 — Preserve first-class source provenance through the entire funnel

**Observed implementation.** Leads retain a `source`, while final candidate sources are
aggregated. A board page can mix employer links and LinkedIn links, and the current link preference
is resolved later.

**Risk.** Without per-hop provenance, it is hard to audit which niche source produced a job, detect
a source that becomes stale, or distinguish an employer-direct link from a LinkedIn/aggregator
redirect. It also makes source-level precision and recall proxies impossible.

**Recommendation.** Extend the lead/posting record with:

- `discovered_at`, `source_url`, `source_published_at`, `source_job_id` (when public);
- `source_kind` (`employer`, `ats`, `niche_board`, `search`, `alumni_export`, `manual`);
- `canonical_url`, `canonical_host`, `canonical_status` (`direct`, `resolved`, `unresolved`);
- `verification_url`, `verified_at`, and `verification_method`.

Do not overwrite the discovery URL. Store a small resolution graph (lead → intermediary → employer
posting) and report the canonical-resolve rate by source. Only `verification_url` should satisfy
the final-list evidence rule.

### P1 — Add public niche-board adapters as *lead* adapters, not final sources

**Observed implementation.** The existing web-search queries include Built In, legal.io, and
GoInhouse, but no direct source adapter, feed catalog, or query coverage for AI-startup or
legal-operations boards.

**Recommendation.** Start with these sources, subject to a per-source terms/robots review at the
time of implementation:

| Priority | Source | Recommended integration | Reason / constraint |
|---|---|---|---|
| 1 | Legal Operations Job Board (`legaloperationsjobboard.com/job-board`) | Parse only the public listing page at a low cadence; emit lead URLs and metadata; prefer its occasional employer/ATS URL, otherwise mark LinkedIn links as unresolved leads. | Its public page advertises hand-picked legal-operations and legal-engineering roles, with region filters and a weekly refresh. It is especially useful for legal engineer, legal product, AI workflow, and innovation counsel roles. Most legal-operations titles remain poor fits under the current rubric, so apply a narrow allowlist before expensive verification. |
| 1 | Legal.io | Continue as an aggregator lead source, but create dedicated query variants and source metrics. Resolve to employer pages; never treat its page as verification. | Already recognized in search but not made measurable as a source. |
| 1 | AI Startup Jobs (`aistartupjobs.com`) | **Do not scrape or bypass its Cloudflare interstitial.** Use a permitted partner/API/RSS feed if the operator offers one, or use targeted web search that yields public employer ATS links. | A direct review request on 2026-09-25 returned a Cloudflare 403 challenge. That is a stop signal under the project's rules. It may still be a valuable manually browsed or officially partnered discovery surface. |
| 2 | In-house / legal-tech communities (e.g., GoInhouse, TechGC, CLOC, ACC, ILTA) | Add only publicly available job-board pages or newsletters with explicit automation permission. Give each its own connector or a manual-import template. | These are likely to expose legal-tech, AI governance, product-counsel and regulatory roles that generic ATS queries miss. Membership-only surfaces must remain manual/user-exported. |
| 2 | Credit/restructuring information vendors and trade groups (Octus, 9fin, Debtwire/ION, Fitch, Reorg, LSTA, AIRA, Turnaround Management Association, ABI) | Add their employer boards to the registry; add public career/newsletter feeds as leads. | This directly targets the credit-intelligence and restructuring niche identified in the candidate rubric. |
| 2 | Market-structure and financial-regulation institutions (FINRA, NY Fed, FRBNY-aligned groups, DTCC, OCC, CFTC, SEC, FICC, FIA, ISDA, SIFMA, MFA) | Continue official career pages; broaden registry and use public event/newsletter feeds only for leads. | This is the most tailored route to convert the candidate's second-line credit-risk work into adjacent regulatory-policy/research roles. |
| 3 | Startup ecosystems (NYC Tech, AlleyCorp, NYS/NYC innovation groups, Y Combinator/Wellfound where terms permit) | Add company discovery, then detect/pull the employers' public ATS boards. | Prefer company/ATS discovery over scraping closed startup aggregators. It compounds over time because relevant discovered employers become registry entries. |

**Narrow legal-ops allowlist.** Do *not* relax the blanket exclusion for routine legal operations.
Admit a lead for verification only when its title/description indicates one of: `legal engineer`,
`legal product`, `innovation counsel`, `AI workflow`, `knowledge engineering`, `legal data/research`,
`legal technology lawyer`, or `legal-AI implementation` **and** it lacks sales/quota signals. Keep
ordinary e-billing, CLM administration, matter management, procurement, coordinator, and support
roles excluded.

### P1 — Expand queries around the candidate's distinctive signal, not generic “counsel”

**Observed implementation.** The keyword inventory is already thoughtful, but the search query
set is compact and emphasizes title fragments. `relevance()` also requires finance context for
some broad policy/research titles, which can exclude promising roles whose body text is not present
in a search lead.

**Recommendation.** Add query packs, version them, and record results used per pack. Use
company/ATS targeting plus these candidate-specific phrases:

- **Clerkship / litigation finance:** `"judicial clerkship preferred"`, `"former clerk"`,
  `"litigation finance" (underwriting OR investment OR diligence)`, `"legal assets"`;
- **Financial-regulatory bridge:** `"credit risk" (policy OR governance OR regulatory)`,
  `"prudential regulation"`, `"regulatory examinations"`, `"market structure"`,
  `"regulatory engagement"`, `"second line"`;
- **Legal-AI build/research:** `"legal knowledge engineer"`, `"legal research" (AI OR LLM)`,
  `"AI governance" (counsel OR policy OR research)`, `"legal content" (research OR editor)`,
  `"evaluation" legal expert`;
- **Credit/distressed research:** `"distressed" (legal analyst OR research associate)`,
  `"restructuring" (research OR intelligence OR analyst)`, `"credit research" JD`,
  `"special situations" (research OR analyst)`;
- **Decision-research roles:** `"investigations" (analyst OR research)`, `"due diligence"`
  with `regulatory`, `policy research` with a finance/market-structure employer.

A query match should be a **recall mechanism**, not a relevance decision. When a result exposes
only a title, defer the finance-context decision until the canonical page is fetched. This avoids
false negatives on sparse search results while keeping final scoring strict.

### P1 — Broaden ATS/custom-site enumeration safely

**Observed implementation.** The registry detector probes Greenhouse, Lever, Ashby, Workable,
Recruitee, and BambooHR; it parses Workday and a few special/custom sites. SmartRecruiters is
detected but its API is deliberately not pulled because of robots restrictions.

**Recommendation.** Add adapters only after verifying the specific public endpoint and terms;
do not use undocumented/internal APIs. Prioritize employer career-page discovery plus public
structured data (`JobPosting` JSON-LD), sitemap job URLs, and documented feeds for common misses:

1. iCIMS, Jobvite, Avature, UKG/UltiPro, Phenom, Paylocity, Dayforce, SuccessFactors (beyond the
   existing sitemap case), and custom Next.js sites with embedded JSON-LD.
2. A generic, robots-aware `sitemap + JobPosting JSON-LD` enumerator. It should start from a
   registered career URL, restrict itself to the same employer host, cap URLs, and only fetch pages
   allowed by robots.
3. A "custom-board watch" queue: if a high-priority employer is `none`, record a manual career
   URL and re-check its careers page weekly rather than repeatedly guessing slugs.

This solves the actual gap—high-value employers not covered by known ATS—without an indiscriminate
crawl. Keep SmartRecruiters and similar blocked sources as lead-only until an explicitly permitted
public source is available.

### P2 — Improve employer targeting with a living adjacency map

**Observed implementation.** `seeds/companies.csv` has good initial segments, but these are
hand-maintained and some rows represent multiple companies or unresolved boards.

**Recommendation.** Split every multi-employer row permanently and maintain a `target_universe`
file with `employer`, `segment`, `why_tailored`, `career_url`, `source_of_discovery`,
`priority`, and `review_after`. Seed it with the following *categories*, then add named employers
only after a human/public-source check:

- litigation funders, litigation-insurance and legal-assets investors;
- legal-AI, legal research/data, e-discovery, and legal knowledge-management vendors;
- alternative data, expert networks, credit intelligence, restructuring advisory, and ratings;
- exchanges, clearinghouses, broker-dealers, market makers, payment networks, and regtech;
- financial-regulator, SRO, trade-association and policy-research employers;
- AI safety/governance and content/evaluation employers offering salaried non-sales roles.

For each segment, select 10–20 direct employers and two niche sources. That makes the sweep
intentional and creates a defensible answer to “what did we search?”

### P2 — Add feedback loops so the radar learns from what is useful

**Recommendation.** Add a simple review action to `out/jobs.csv` or a separate ignored local
file: `useful`, `not_useful`, `already_seen`, `wrong_level`, `wrong_location`, and `reason`.
Summarize feedback by source, keyword family, company segment, and title family each run.

Use this signal to change **source priority and query ranking**, not to silently change hard
exclusions. It will reveal, for example, whether legal-ops sources produce too many implementation
or coordinator roles, whether clerkship queries work, and which aggregators resolve to employers.

---

## Penn alumni-job-board feasibility

### What is publicly established

Penn Career Services states that its alumni page includes a Handshake job board with thousands of
positions posted for Penn alumni each year. It also says alumni who graduated in 1997 or later can
access their account with a PennKey. The public page links to the Penn Handshake tenant; the job
content itself is behind sign-in.

This is a promising **private source for the candidate**, but it is not a public feed that this
repository should autonomously crawl. Automated login, session reuse, reverse engineering
Handshake endpoints, or scraping a member-only board would conflict with both the repository's
no-login rule and the review's conservative permissions posture.

### Recommended supported integration: user-controlled export/import

Implement an `alumni_export` input—not a Handshake scraper:

1. The user signs in normally to Penn/Handshake and runs saved searches (NYC/hybrid/US remote,
   2–5 years, legal/regulatory/research; omit internships/new-grad listings).
2. The user exports results if the product provides an export, or creates a small CSV/JSONL from
   the links they choose to share. The repository documents the exact minimal schema:
   `title, company, location, url, posted_at, source_url, notes`.
3. A new CSV importer (or the existing JSONL `python -m radar import-leads alumni_export.jsonl
   --source alumni:penn_handshake`) validates, de-duplicates, and labels the leads as
   authenticated-source referrals.
4. The standard verifier resolves each item to a public employer ATS posting. A role without a
   publicly verifiable employer page is kept only in a separate **private lead queue** with a clear
   `requires_user_review` flag; it never enters `open_positions_*.md` as verified.
5. Store neither Penn credentials nor cookies. Keep the export outside Git by default, or retain
   only redacted/canonical URLs after user confirmation.

### Optional future route: official written authorization

If Penn Career Services and Handshake provide a documented alumni API, approved data-export
mechanism, or written authorization for a read-only integration, add a separate optional connector
that uses that documented mechanism only. Require an environment token, respect the agreement's
rate limits and retention rules, and default it off. No such authorization or public API was
established by this review.

### Claude Code workflow

Claude Code can help *implement and operate the supported import path* without accessing the
alumni account: generate saved-search instructions, validate the user-provided export, extract
employer URLs, and run canonical verification. It must not receive or use a PennKey/password,
session cookies, MFA codes, or a browser profile from the authenticated account.

---

## Suggested implementation sequence

1. **Coverage and provenance (P0):** source catalog, lead-hop fields, `coverage.md`, and unit tests
   for canonical-source precedence.
2. **Niche lead adapter (P1):** Legal Operations Job Board public-page adapter, narrow legal-tech
   allowlist, rate/robots/terms guard, fixtures, and a direct-employer resolution metric.
3. **Query packs (P1):** add candidate-specific query groups with per-query result accounting;
   defer sparse-title relevance decisions until verification.
4. **Custom employer discovery (P1):** generic employer-scoped sitemap/JSON-LD adapter and a
   high-priority unresolved-employer queue.
5. **Alumni import (P1):** CSV/JSONL schema, an `import-alumni-leads` command or documented
   `import-leads --source`, private-lead queue, and tests that credentials/cookies are rejected.
6. **Source expansion and learning (P2):** association/newsletter adapters where public and
   permitted; target-universe map; user feedback report.

For every adapter, the acceptance criteria should be: (a) no login or anti-bot bypass, (b) robots
and terms decision recorded, (c) raw source URL and retrieval time retained, (d) final listing
requires a current employer/official verification fetch, (e) a failure does not halt the run, and
(f) a source-level health row appears in `coverage.md`.

---

## Source observations made for this review

These are observations, not authorization to automate a source:

- On **2026-09-25**, a normal GET of `https://legaloperationsjobboard.com/job-board` returned
  HTTP 200. Its public text said it had 188 open roles, was refreshed weekly, and described the
  content as hand-picked legal-operations/legal-engineering roles. The page included a mixture of
  employer ATS links and LinkedIn/legal.io links. Treat it as a public, low-cadence lead source and
  prefer its direct employer links.
- On **2026-09-25**, a normal GET of `https://aistartupjobs.com/` returned HTTP 403 with a
  Cloudflare “Just a moment” page. Do not bypass that control; use a permitted feed, partnership,
  manual referral, or public web search instead.
- On **2026-09-25**, Penn Career Services' public alumni page returned HTTP 200 and stated that
  its Handshake board serves Penn alumni. The Penn Handshake tenant is sign-in based. This supports
  the user-controlled export design, not automatic authenticated collection.

## Review commands run

```bash
find .. -name AGENTS.md -print
rg --files -g '!*node_modules*' -g '!*.lock'
sed -n '1,280p' radar/keywords.py
sed -n '1,320p' radar/discover/websearch.py
sed -n '1,320p' radar/phase2.py
python - <<'PY'  # normal HTTP status/content checks for the three sites above
...
PY
```
