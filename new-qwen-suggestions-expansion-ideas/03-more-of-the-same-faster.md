# 03 — More volume of the *existing* posting types

Ways to multiply current yield without new sectors or new platforms. Ordered by expected lift.

## 1. Query-matrix expansion for the `websearch` channel (free, biggest lift)

`seeds/search_queries.csv` has 14 rows, all Greenhouse/Ashby/Lever site-scoped with ~6 title
phrases. Cross-multiply three axes that today only partially combine:

- **Title axis** — add the synonym families from §7 below (~25 new phrases).
- **Platform axis** — same queries against `site:jobs.lever.co`, `site:breezy.hr`,
  `site:applytojob.com`, `site:teamtailor.com`, `site:recruitee.com`, `site:myworkdayjobs.com`,
  `site:smartrecruiters.com`, `site:jobs.sapsf.com`.
- **Domain-context axis** — append qualifiers that encode the five seat families from CLAUDE.md:
  `"litigation finance" | "legal assets"`, `"credit risk" | "distressed" | "bankruptcy"`,
  `"AI governance" | "model policy"`, `"clerkship preferred"`, `"no finance experience required"`,
  `"regulatory examinations" | "exam support"`, plus city scoping `"New York OR NYC OR remote"`.

~14 → 120–150 rows is still trivial for a weekly Claude WebSearch sweep if batched by platform.
Also rotate a `results_used` review each run: rows stuck at 0 results for 3 runs get retired, and
the retirements log which phrasings are dead so query budget stays productive.

## 2. Grow board tokens through *non-CDX* enumerators

The CDX sweep caps at 1,500 unseen boards/ATS/run. Cheaper token sources to feed the same pullers:
- Every ATS board URL that ever appears in **any** lead/snapshot/run-log gets upserted into
  `data/cc_boards.json` state automatically (leads already contain e.g. careers-page URLs whose
  redirect lands on an ATS host — parse the final host/token after Phase 4 verification and
  register the whole board, not just the one posting). This turns every verified posting into a
  *board discovery event*. Expect compounding growth of `discovered_boards.csv` per run.
- Public directories of companies-by-ATS built by vendors' own marketing pages: greenhouse.io/
  customers, leverhq.com/customers? (paywalled), ashbyhq.com/customers (public logo wall + some
  slugs), workable.com/customers — HTML lists of tenant names = ready-made token seeds that skip
  CDX entirely. Respect robots; these are shallow page fetches.
- Common Crawl CDX for the *employer side*: pattern `*.com/careers*` first-seen this crawl →
  run ATS-detect (Phase 2 logic) on new careers pages rather than waiting for platform-side hits.

## 3. Pull deeper per board

- Greenhouse API returns all jobs already; but many employers keep roles only on
  `boards.greenhouse.io/embed/*` iframe params — harmless duplicates, dedupe handles.
- Workday tenants: current probe pulls one site per tenant; enumerate sites via
  `/wday/cxs/v1/network/sites`? (undocumented) — safer: fetch the tenant's careers landing page
  and regex all `/<site>/jobs` links (multiple hiring sites per company is common at banks).
- Ashby: `/api/a/job-posts/list/<org>?published=true&includeMasked=false` gives more than the
  public page (masked-but-open seats at some funds). Keyless today; note it may auth-gate later.

## 4. Freshness ("recently posted") as a first-class filter

- Extract `datePosted` from JSON-LD on every verified posting (already parsing JobPosting schema —
  persist the field), then: `--since 14d` flag on refresh marks † rows AND can *prioritize* judgment
  subagent batches toward fresh postings (stale-but-open ones re-judge last, hash-cached anyway).
- RSS pubDate (§9 of doc 02) gives freshness pre-verification, letting the run skip verifying
  postings older than, say, 90 days unless they're watchlist recurrence candidates — saves request
  budget for genuinely new inventory.
- CDX first-seen windows (doc 02 §2) catch postings that never appear in any crawl until they're
  weeks old — use as backfill, not freshness.

## 5. Recurrence & closed-seat mining (extends wayback.py + watchlist.csv)

- Auto-promote any posting that flipped open→closed between snapshots into `seeds/watchlist.csv`
  with a Wayback re-check cadence; litigation-finance and legal-AI seats reopen on 3–9 month cycles
  (out/recurrence.md already proves the method on 6 firms).
- For each *fit* posting that closed, mine its description for the hiring team's name ("Legal Ops",
  "CPGR-equivalents") and issue one targeted websearch query per team per quarter — teams re-post
  under near-identical titles that generic queries miss.

## 6. Multi-location widening inside existing boards

`keep_location()` gates NYC/US-remote. Cheap recall win: keep pulling other-location postings from
already-pulled boards (zero extra requests — the board JSON already contains them) into the
outside-location table with a `relocated?` flag; occasionally those seats convert to hybrid-NYC
and the diff catches the move (a real signal: funds rotating legal seats into NYC).

## 7. Title-synonym explosion for `keywords.py` (precision-safe because relevance() still gates)

Add TITLE_FAMILIES (regex sketches):
```python
("research counsel", r"research counsel|senior counsel.*research"),
("knowledge management", r"knowledge (management|manager)|practice attorney|research attorney"),
("litigation support/e-discovery analysis", r"litigation (support|technology) (analyst|manager)|e[- ]?discovery (analyst|manager)"),
("claims/coverage", r"coverage (counsel|attorney|analyst)|claims counsel|complex claims"),
("underwriting counsel", r"underwriting (counsel|attorney)"),
("trust & safety counsel", r"trust\s*&\s*safety (counsel|policy)|content policy counsel"),
("escalations", r"escalation(s)? (counsel|attorney|analyst)"),
("government affairs/legislative", r"government (affairs|relations) (analyst|associate)|legislative (aide|analyst|attorney)"),
("examining attorney / hearings", r"examining attorney|hearings (officer|attorney)|administrative law judge|alj"),
("rulemaking/policy analyst fed", r"rulemaking|regulatory analysis|economist.*(regulat|policy)|financial (policy|market) analyst"),
("ombuds/monitor", r"ombuds|monitor(ship)? (attorney|counsel)|compliance monitor"),
("specialist counsel family", r"\b(staff|senior|associate)\s+(attorney|counsel)\b.*(regulat|financ|crypto|ai|payments)"),
("fellowships", r"(legal|policy|economics).*fellow|fellow.*(law|policy)"),
("arbitration/ADR", r"arbitrat\w+ (counsel|manager|associate)|case manager.*(arbitrat|adr)"),
("due diligence/integrity", r"integrity (services|diligence)|due diligence (analyst|associate)|osint"),
("political/country risk", r"(political|country|geopolitical) risk (analyst|associate)"),
("bid protest", r"bid protest|government contracts (analyst|attorney)"),
("forecasting", r"forecast(er|ing) (analyst|consultant|researcher)"),
```
Guardrails: `_NOT_KNOWLEDGE` and `_OPS` filters stay in front; new families mostly need
`_FINANCE_CTX` or `_LEGAL_CTX` gating (add to `_NEEDS_FINANCE`/`_NEEDS_LEGAL` accordingly) so
"Claims Adjuster Trainee" style noise dies at relevance(), not at scoring.

## 8. Score-recall knob

Currently a posting needs 3/10 fit signals for the fit table; everything else falls to `bucket=low`
in jobs.csv. Proposal: emit a `near-miss` bucket (score 2) into the diff file only — two signals
captured on novel titles (KM lawyers, coverage counsel) often mean "rubric doesn't know this job
shape yet"; reviewing near-misses weekly is how the rubric learns new families without flooding
the main table.

## 9. Judgment-cache reuse across identical descriptions

Multi-board employers post the same req on Greenhouse + their site + Muse + BuiltIn. Judgments are
keyed by posting+hash today; key the *text* hash separately so one judgment serves all mirrors of
the same seat — frees subagent budget for genuinely new seats each run.

## 10. Cadence trick

Two half-week runs (Mon/Thu) instead of one weekly doubles freshness capture at ~same request
volume for boards (they're pulled fully anyway); gate the expensive channels (CDX, Wayback) to
weekly via a `--light` flag. GitHub Actions workflow already supports manual trigger; add cron
`0 12 * * 1,4` with `--light` on Thursdays.
