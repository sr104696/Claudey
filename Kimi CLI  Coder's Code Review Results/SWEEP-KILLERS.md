# SWEEP-KILLERS — bugs that silently lose jobs every run

Ranked by jobs lost per run. Every entry cites code at commit `f492964`. Most fixes are
one-liners to ~10 lines. These are the highest-value findings of this review: the user asked
for comprehensiveness, and nothing hurts comprehensiveness like a sweep that reports success
while dropping sources.

---

## K1. The Muse channel returns almost nothing — category names are dead (verified live)

`radar/discover/official_apis.py:14`

`MUSE_CATEGORIES` lists `"Legal"`, `"Compliance"`, `"Finance"`, `"Government and Public Policy"`.
Queried against the live API during this review: **all four return `total: 0`** — The Muse
renamed its categories. The current legal category is **"Legal Services"**: 4,527 jobs total,
153 in "New York, NY", 103 in "Flexible / Remote" (verified live). "Accounting and Finance"
(3,276) and "Data and Analytics" (18,028) also still exist.

Because an unknown category returns HTTP 200 with an empty result set, **no failure is ever
logged** — the textbook silent miss.

Fix (2 lines + a guard):
```python
MUSE_CATEGORIES = ["Legal Services", "Accounting and Finance", "Data and Analytics"]
```
and treat `total == 0` for any category as a logged warning so the next rename surfaces in the
run log instead of vanishing.

## K2. Lever boards are truncated at 100 jobs — ~1,000 known postings already dropped

`radar/ats/lever.py:54-62` (`pull`), `:19-27` (`probe`)

The Lever v0 postings API returns at most 100 postings per request and paginates with `skip`;
the adapter never paginates. This is not theoretical: `data/discovered_boards.csv` already lists
Lever board `veeva` with 916 jobs and `sunsrce` with 283 — **816 and 183 jobs dropped with
status "ok"**. `probe` (`phase2.py:171`) also records misleading counts from the capped first page.

Fix: loop `params={"mode": "json", "skip": offset, "limit": 100}` until a short page returns.

## K3. A crashed discovery channel leaves zero trace in the run log

`radar/pipeline.py:17-29` collects each discovery subprocess's exit code; `pipeline.py:117`
**discards the return value**. If a channel module raises (import error, API schema change),
the sweep proceeds with zero leads from that channel and `out/run_log.md` says nothing. The
user's single biggest fear — "did it actually check?" — is unanswerable for a dead channel.

Fix: capture `codes = run_discovery(...)`; for every non-zero code call
`runlog.record_channel(f"discover:{ch}", failures=[...], notes="channel crashed")`, and flag it
in the digest/summary.

## K4. Transient robots.txt failure blacks out a whole board for the run

`radar/http.py:281-282, 291-292` + `radar/robots.py:26-27`

Any robots fetch error maps to `Rules(state="error")` → `allowed()` is `False` → memoized for
the process lifetime. One flaky DNS window on the runner and **every posting on that host is
skipped as `blocked: robots` for the entire weekly run**. Worse, the six parallel discovery
subprocesses each keep their own `_robots` cache, so the same host can be swept by one channel
and skipped by another — nondeterministic coverage.

Fix: don't memoize error states (or memoize with a few-minute TTL); add a host-level summary of
error-state hosts to the run log so a wiped board is visible at a glance.

## K5. "Legal Engineer" recurrence family is dead code — the regex can never match

`radar/discover/wayback.py:38` + `:86`

`NOISE` contains `engineer(?!.*legal)` — a negative lookahead that only inspects text *after*
"engineer". In the title "Legal Engineer", "Legal" comes *before*, so `NOISE` matches and the
family is set to `None`. The `("legal engineer", ...)` family at `:23` — precisely the
Harvey/Legora legal-AI build seats the recurrence report exists to track — **can never match
any normal title**.

Fix: use a lookbehind as well: `(?<!legal )engineer(?! legal)`, or drop `engineer` from `NOISE`.

## K6. Relevant postings with unparseable locations are dropped before scoring

`radar/phase2.py:26,274` and `radar/discover/common.py:10,23`

`keep = [p for p in ps if p.relevant and p.loc_bucket in KEEP]` where `KEEP` excludes
`"unknown"`. A relevant posting whose location is missing or unclassifiable — common for
SuccessFactors/JSON-LD pages with empty `addressLocality`, Workday rows with empty
`locationsText`, or a bare `"NY"` string — never reaches Phase 4. Note the inconsistency:
`phase4.py:204` *keeps* unknown-location postings at scoring time, so the discovery path is
stricter than the scoring path for the same data.

Fix: keep `unknown`-bucket relevant postings as candidates (or route them to a review file).

## K7. Dedupe collapses genuinely different open reqs at the same company

`radar/models.py:62-66` via `radar/phase4.py:155-165`

`dedupe_key` = normalized company + title + location bucket — no job id, no URL. Two different
open reqs with the same generic title at one company ("Counsel" on two teams; "Regulatory
Counsel" posted for two NYC offices) collapse into one row and one URL is silently discarded.
Separately, `us_other` postings in *different cities* with the same title also merge
(SF + Chicago = one row).

Fix: when two postings share a key but have different ATS `job_id`s/`url_key`s, keep both —
use the merge to prefer the employer-ATS *version of the same req*, not to collapse different
reqs.

## K8. Feed/API failure modes are indistinguishable from "closed" / "no jobs"

Three instances of the same shape:

- **Jane Street** (`radar/verify.py:42-61`): a failed feed fetch caches `[]`; every seed row
  then falls through to a Greenhouse 404 → marked **closed**. One transient outage mass-closes
  all Jane Street rows for the run. Don't cache failures; return "unverified" instead.
- **SuccessFactors sitemap** (`radar/ats/html.py:36-42`): sitemap-index files, gzipped
  sitemaps, or a URL-format change return an empty list with status `"ok"` — Burford/Fitch
  silently report 0 jobs. Empty URL list should be its own status.
- **SmartRecruiters** (`radar/phase2.py:237-238`): `return smallats.sr_pull(slug, company, src)[0], []`
  **discards every posting even on success**. Two-line fix (currently masked by the robots
  block, but a landmine).

---

## Honorable mentions (not silent, but bleeding value)

- **Outside-NYC poor matches vanish from all markdown** — `output.py:78` filters
  `bucket=="outside" and not p.poor_reason`, but `score.py` sets `poor_reason` independent of
  bucket, so those rows appear nowhere (line 91 has unreachable rendering code for them —
  proof the filter is wrong). Remove `and not p.poor_reason`.
- **Hard-exclude regexes can't match ranged years** — `score.py:37`, `keywords.py:118,121`:
  `([5-9]|1\d)\+?\s*(\+|or more)?\s*years?` misses "**6–8 years** of leveraged finance" and
  "**5–8 years** in equity research" (the exact phrasing on the seed list's Octus/AlphaSense
  poor rows). Allow `[-–—]\s*\d{1,2}` between number and `years?`.
- **No poor-bucket row is ever sent for judgment** — `phase4.py:229-235`'s docstring promises
  near-fit poor rows get exported for subagent judgment; the filter only admits fit/outside.
  A regex false-positive hard-exclude can therefore never be reviewed or reversed. Include
  poor rows with `fit_score >= 2`, matching the docstring.
- **Cross-process rate limit breaks for crawl-delay > 60s** — `http.py:155-165` sleeps *inside*
  the lock; `http.py:137` deletes locks older than 60s as stale. A host with `Crawl-delay: 120`
  gets concurrent requests from two processes — a politeness violation on exactly the hosts
  that asked for the longest delay. Heartbeat the lock mtime while sleeping.
