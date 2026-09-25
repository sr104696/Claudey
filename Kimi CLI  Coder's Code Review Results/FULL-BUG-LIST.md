# Full bug list — all findings with file:line

Everything in [SWEEP-KILLERS.md](SWEEP-KILLERS.md) is repeated here in place, plus all
secondary findings. Severity: **P0** = loses jobs / crashes / politeness violation ·
**P1** = correctness bug, non-fatal · **P2** = robustness / hygiene.

Citations are against commit `f492964` (main at review time).

## A. Core infrastructure (http, robots, db, pipeline, seeds)

| # | Sev | Location | Finding |
|---|---|---|---|
| A1 | P0 | `pipeline.py:117,17-29` | Discovery subprocess exit codes discarded — crashed channel leaves no trace. (SWEEP-KILLERS K3) |
| A2 | P0 | `http.py:281-282,291-292`; `robots.py:26-27` | Transient robots fetch error memoized → whole host blocked all run; per-process caches make coverage nondeterministic. (K4) |
| A3 | P0 | `http.py:155-165,137` | Lock held during crawl-delay sleep but treated stale after 60s → concurrent requests to hosts with long Crawl-delay. Heartbeat lock mtime while sleeping. (K-mention) |
| A4 | P1 | `http.py:269-290` | After the 5-redirect loop, a terminal 3xx body is parsed as robots.txt → empty rules, allow-all. A redirect-looping (or honeypot) robots.txt silently disables politeness. Treat terminal 3xx as `state="error"`. |
| A5 | P1 | `http.py:310` | `Retry-After` honored only in digit form; HTTP-date form (RFC 9110) falls through to backoff. Parse with `email.utils.parsedate_to_datetime`. |
| A6 | P1 | `http.py:380-383` | Per-host blocked check runs before cache lookup — after a mid-run bot wall, already-cached pages become unreadable, discarding good data. Check cache first for GETs. |
| A7 | P1 | `http.py:412-415` | 401/403 blocks the URL but not the host — run keeps hitting a refusing host at 1 req/s for every remaining URL. Trip `_blocked_hosts` after N consecutive refusals. |
| A8 | P2 | `http.py:228-229` | Expired cache entries never deleted; `cache/http/` grows without bound. `unlink(missing_ok=True)` on expired read. |
| A9 | P1 | `robots.py:100-104` | Fallback global crawl-delay regex only fires if no `user-agent` line precedes it; a site-wide `Crawl-delay` after the last group is ignored. |
| A10 | P2 | `robots.py:53` | Pattern `unquote()`d before scanning for `*` — literal `%2A` becomes a wildcard. Unquote after splitting on literal `*`. |
| A11 | P1 | `db.py:69-78` | `tx()` uses plain `threading.Lock` — future nested `tx()` deadlocks silently. Use `RLock`. |
| A12 | P1 | `db.py:135` | Board-job raw JSON truncated at 200,000 chars → invalid JSON in the `data` column. Store a sentinel object instead. |
| A13 | P1 | `pipeline.py:74-83` | SMTP digest can raise after outputs are written, crashing `refresh` before summary; ntfy path never checks `res.ok`. Wrap both, log to run log. |
| A14 | P1 | `pipeline.py:94-100` | `runlog.load_channels()` re-read per loop iteration; fuzzy channel-name matching creates duplicate `discover:*` entries. Hoist load; key explicitly. |
| A15 | P2 | `pipeline.py:104` | "Meets the bar" check hardcodes `>= 11` fit rows; derive from parsed seed count. |
| A16 | P1 | `seeds.py:10,47,60-64` | `_cells` splits naively on `\|` (a pipe in a title/URL shifts columns); seed rows with unparseable links are dropped with no log. Validate and record failures. |
| A17 | P2 | `leads.py:21` | `add_leads` re-reads all of `leads.jsonl` per call to dedupe; O(file) per channel, grows forever. Fine now, flag for later. |
| A18 | P1 | `__main__.py:32,42-46` | `score` help says "reusing today's seed check" but calls `phase1.verify_seeds()` live — surprise HTTP traffic; a flapping seed page makes re-score disagree with the morning run. Persist Phase 1 results or fix the help text. |
| A19 | P2 | `requirements.txt` | `playwright` and `pypdf` installed every CI run, never imported in `radar/`. Drop or comment why they're kept. |
| A20 | P2 | `models.py:62-66` | `dedupe_key` buckets nyc+us_remote as "main" (intended?) but also merges `us_other` across different cities. Confirm semantics. (K7 covers the worse half.) |

## B. ATS adapters, extraction, verification

| # | Sev | Location | Finding |
|---|---|---|---|
| B1 | P0 | `lever.py:54-62,19-27` | No `skip` pagination — boards >100 jobs truncated; ~1,000 known postings already dropped (veeva 916, sunsrce 283). (K2) |
| B2 | P0 | `phase2.py:237-238` | SmartRecruiters results discarded unconditionally: `return sr_pull(...)[0], []`. (K8) |
| B3 | P0 | `phase2.py:26,274`; `discover/common.py:10,23` | Relevant postings with `loc_bucket == "unknown"` dropped before scoring; phase4 is more tolerant of the same data. (K6) |
| B4 | P1 | `ashby.py:106-115` | `verify` iterates all jobs without the `isListed` filter that `pull` applies — a delisted (closed) job verifies as open. |
| B5 | P1 | `verify.py:42-61` | Jane Street feed failure caches `[]` → all seed rows fall through to Greenhouse 404 → mass false "closed". (K8) |
| B6 | P1 | `html.py:36-42` | `rmk_sitemap`: sitemap indexes / gzipped sitemaps / URL-format change → empty list with status `"ok"`. Burford/Fitch silently report 0. (K8) |
| B7 | P1 | `phase2.py:199-216` | Workday/Workable/BambooHR detail fetch gated on title-only relevance — a relevant job with a generic title ("Analyst", "Associate – 3+ years") never gets its description pulled. Directly sacrifices comprehensiveness on the three ATSs whose listings carry no body text. |
| B8 | P1 | `extract.py:199` | `\bJ\.?D\.?\b\|bar` — `bar` has no word boundaries: matches "barista", "Barclays", "barrier". Every attorney-titled posting gets `jd_required="Y"`. Fix: `\bbar\b`. |
| B9 | P1 | `phase2.py:48-58` | `ATS_LINK` misses `jobs.eu.lever.co` (Lever EU) and Greenhouse `embed/job_app?for=...` — careers pages using either fail detection → `ats=none`. |
| B10 | P1 | `verify.py:63-67`; `phase2.py:264-265` | Greenhouse 404 = "closed", but same 404 occurs on board rename/ATS migration (the Capstone DC case in watchlist). No re-detect on "board not found" — stale slug stays broken until manual `--redetect`. |
| B11 | P1 | `phase2.py:202-224`; `html.py:56` | Workable/BambooHR detail calls and SuccessFactors `rmk_verify` not per-job guarded — one bad job aborts the whole board, discarding already-built light postings. |
| B12 | P1 | `smallats.py:22-36` | SmartRecruiters `limit=100`, no `offset` loop; Workable pull caps at 20 pages. Truncation if reused. |
| B13 | P1 | `extract.py:162,173-178` | `years_required`: context checked only *after* the number ("Experience: 5 years" missed); returns only `lo` and takes `min()` across mentions — "5–7 years required, 1-year fellowship" reports 1. |
| B14 | P1 | `extract.py:182-189` | "Admission to the New York State Bar" matches no JD alternative → downgraded to "pref". `_JD_ANY` is dead code. |
| B15 | P2 | `extract.py:264-308`; `base.py:144` | Bare "NY" → `us_other` not `nyc`; Jersey City/Hoboken/Stamford have no "commutable" tier; `workplace_of` scans only `text[:600]` — header boilerplate can mislabel remote. |
| B16 | P2 | `base.py:59,123` | `.replace("Sept","Sep")` case-sensitive (lowercase "sept 5" → `closes_date=None`); dead `isinstance` check after str coercion. |
| B17 | P2 | `nyag.py:50,98` + docstring | Deadline parses only `%B %d, %Y`; location pay can render "Not listed + $8,000 location pay"; robots limits NYAG to first page per category with no alarm if that changes. |
| B18 | P1 | `verify.py:159-161` | `search_board` Workday path: `spec_from_slug` can return `None` → `TypeError` escapes the `RuntimeError` handler. |
| B19 | P1 | `phase1.py:94` | Watchlist resolve matches company by substring — "Capstone" matches both "Capstone DC" and "Capstone Investment Advisors". |
| B20 | P1 | `verify.py:50-123` | No dispatch for Workable/BambooHR/Recruitee/SmartRecruiters URLs — they fall through to generic page fetch on JS SPAs → "unverified". The `wk_detail`/`bb_detail` adapters exist but are never wired into `verify_url`. |

## C. Discovery channels, scoring, output

| # | Sev | Location | Finding |
|---|---|---|---|
| C1 | P0 | `official_apis.py:14` | Muse category names dead — all four return `total: 0` (verified live). "Legal Services" has 4,527. (K1) |
| C2 | P0 | `wayback.py:38,86` | `engineer(?!.*legal)` lookahead kills the "legal engineer" family — dead code. (K5) |
| C3 | P0 | `output.py:78` vs `:91` | Outside-bucket poor matches filtered from every markdown output; line 91's rendering branch is unreachable. (K-mention) |
| C4 | P0 | `score.py:37`; `keywords.py:118,121` | Year-based hard excludes can't match ranges ("6–8 years"). (K-mention) |
| C5 | P0 | `models.py:62-66`; `phase4.py:155-165` | Dedupe collapses distinct same-title reqs at one company. (K7) |
| C6 | P1 | `commoncrawl.py:103-110` | Failed board pull still stamps `last_checked=today` — a transient 5xx hides the board for `RECHECK_DAYS` (28 days). Stamp only on `status=="ok"`. |
| C7 | P1 | `commoncrawl.py:100-102` | Starvation: fresh tokens always sorted first, stale tail alphabetical — once `due` > `MAX_TOKENS` (1,500), late-alphabet stale boards are never re-checked. Sort stale by `last_checked` ascending. |
| C8 | P1 | `commoncrawl.py:57,114-115` | `MAX_PAGES=40` harvests the same fixed slice of the CC index every run (boards sorting later never discovered — rotate a page offset through state); `ex.map(sweep, ...)` unguarded — one exception kills the channel with no state write. |
| C9 | P1 | `hn.py:56-59` vs `leads.py:25` | All roles from one HN comment share one lead URL; `add_leads` dedupes on `(source, url)` — of `roles[:4]` only the first ever lands in leads.jsonl. Give each role its own URL. |
| C10 | P1 | `official_apis.py:34,62,79,97`; `hn.py:25,28,34` | Unguarded `r.json()` on 200s — one malformed payload kills the whole channel (Muse + USAJobs + Adzuna + SerpAPI share one `run()`). Guard per source. |
| C11 | P1 | `official_apis.py:76-77` | Adzuna fetches page 1 only (50 results) per query. Paginate. |
| C12 | P1 | `official_apis.py:55-57` | USAJobs pins `LocationName: "New York, New York"` — telework-anywhere federal attorney/policy roles structurally missed. Add a no-location remote pass. |
| C13 | P1 | `wayback.py:37,74,80-81` | `MAX_PAGE_FETCHES=250` is one global budget in TARGETS order — later targets (Harvey) starve silently; unguarded `r.json()[1:]` on CDX kills the report on error bodies. |
| C14 | P1 | `score.py:115,117-123`; `keywords.py:109` | Rubric's "quota or variable-heavy" exclude only fires via the sales-title path; a non-sales-titled role with a quota in the body passes. The "quota" keyword flag exists but nothing consumes it as an exclude. Also `\bOTE\b` is case-sensitive. |
| C15 | P1 | `extract.py:21`; `score.py:36,131-133` | False-positive hard excludes no process can overturn: bare "commission" near a pay figure → OTE ("*not* a commission-based role" excludes the job); "strong statistical literacy preferred" triggers the Python/stats exclude (rubric says *required*); `years_mentions` can't distinguish required from preferred ("3+ required; 10+ preferred" excludes on the 10). |
| C16 | P1 | `phase4.py:229-235` | Judgment export filter contradicts its docstring — no poor-bucket row is ever sent for judgment, and judgments can only *add* excludes, never veto one. Regex false positives are irreversible. |
| C17 | P1 | `score.py:27-30,190-191` | Fit-signal inflation: bare `\bcredit\b`, `\bAI\b`, "training program", and near-universal "analyze … legal" each count — any three reach `FIT_MIN`. Require at least one *specific* signal (JD, credit/distressed, litigation finance, named seat family). |
| C18 | P1 | `phase4.py:62-94` | `_employer_board` name-checks only Greenhouse guesses — a wrong Lever/Ashby slug guess ("rain", "general", "norm") is accepted, then "no matching title" discards the lead. Sanity-check company names for all ATSs or fall through to `verify_url`. |
| C19 | P1 | `phase4.py:255-261` | `apply_judgments` writes `desc_hash: None` for unresolvable keys — such judgments still enter the company+title role index, silently applying stale judgments to reposted roles. |
| C20 | P2 | `output.py:109-110,134` | "Closed or no longer verifiable" lumps rows dropped for non-closure reasons (tightened relevance, unverified-this-run) — reported to the user as closed jobs. Filter or rename. |
| C21 | P2 | `wayback.py:26-36` | TARGETS hardcoded — the watch list can't grow without a code edit. Make it a seeds file so recurrence findings feed back into watching. |
| C22 | P2 | `score.py:205-206` | bucket=`low` rows are invisible in every markdown output and the diff — only in jobs.csv. At minimum report the low count with a pointer in the summary. |

## Coverage gaps (structural — where jobs are missed by design)

1. **No ATS support at all for**: iCIMS, Taleo, Jobvite, ADP, UKG/UltiPro, Paylocity, Paycom,
   JazzHR, Breezy, Teamtailor, Personio, Comeet, Eightfold, Phenom, Avature, BrassRing, generic
   SuccessFactors (only two hardcoded RMK hosts, `html.py:29-33`). Registry employers on these
   land at `ats=none`, indistinguishable from "no readable board". Even detect-and-flag
   ("unsupported ATS: taleo") beats "none".
2. **SmartRecruiters fully dark**: robots-blocked for this client (`smallats.py:8-11`) and
   excluded from probes — a common ATS for mid-size fintechs.
3. **Registry rows stuck at `ats=none`** that later proved detectable: Common Crawl found
   `chainalysis-careers` (Ashby, 50 jobs) and `hebbia-ai` (Ashby, 19 jobs) that registry
   detection missed — root causes: slug guesses capped at 4 (`phase2.py:108`), only 6 probe
   families (Workday absent from probes), careers-page scan fetches only the exact
   `careers_url` with no `/careers`,`/jobs` fallback or JS, plus B9's pattern gaps.
4. **Blocked marquee employers** (Citadel, Citadel Securities, Bloomberg, D. E. Shaw) are only
   covered when a lead arrives from elsewhere — and Citadel's Cloudflare wall means even those
   never verify past "unverified".
5. **Zero feed ingestion**: no RSS/Atom/JSON-feed channel exists anywhere. See NEW-SOURCES.md.
6. **`websearch.py` is a counting stub**: without a Claude session replaying
   `seeds/search_queries.csv`, `python -m radar refresh` produces zero web-search leads — a
   single point of failure. Add a "last websearch import" staleness warning, or direct
   listing-page channels for the approved aggregators (BuiltIn, legal.io, GoInhouse).

## Fix order by jobs-recovered per hour of work

1. C1 Muse categories (2 lines) — recovers ~4,500 listings/run.
2. B1 Lever pagination (~10 lines) — recovers ~1,000 known postings.
3. A1 channel-crash logging (~10 lines) — makes every other silent failure visible.
4. C2 wayback lookbehind (1 line).
5. C3 `output.py:78` filter (delete 3 words).
6. B2 SmartRecruiters discard (2 lines).
7. B8 `\bbar\b`, B13/B14 extraction micro-fixes, C4 ranged years (a few lines each).
8. C6 `last_checked` on ok-only (1 condition).
9. B3 keep unknown-location candidates (1 filter).
10. A4 terminal-3xx robots = error (3 lines).
