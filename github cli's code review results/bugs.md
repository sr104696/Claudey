# Bugs and correctness issues

This project is generally disciplined and thoughtful, but a few correctness bugs and false-negative patterns are worth fixing.

## 1) Discovery coverage is narrower than the codebase assumes

The Common Crawl discovery pass is explicitly hard-coded to only a few ATS families:

- `radar/discover/commoncrawl.py` sets `PATTERNS` to only Greenhouse, Lever and Ashby.
- `radar/discover/common.py`'s `ATS_URL` regex also only recognizes Greenhouse, Lever, Ashby, Workday, Workable and BambooHR.

This leaves a meaningful blind spot for the sectors this repo is trying to cover. Workday, SmartRecruiters, Recruitee, JazzHR and similar ATSes are either under-detected or never surfaced by the same path. Practical consequence: candidate-relevant roles can exist and still never reach Phase 4 because the discovery layer never saw them.

Impact: false negatives in the job sweep.

## 2) Coarse title-key matching can collapse distinct roles into one record

`radar/output.py` builds a previous-row key like this:

- `_match_key(company, title)` returns `"{norm_company(company)[:8]}|{norm_title(title)}"`

That dedupe key is consistent only if there is one role per employer-title pair. In a real firm there are often multiple legal/regulatory roles with the same normalized title (for example several counsel or analyst roles). Because that key ignores URL and board identity, a previous row can be matched to the wrong current row, causing incorrect “new/closed” diffing and stale-state substitution.

Impact: output diffs and “new fit row” counts become unreliable for duplicate titles.

## 3) Repost detection is deliberately loose and can misclassify jobs

`radar/phase1.py` contains `same_role()`, which compares word sets and accepts a role as the same one when overlap is above a threshold. It tries to be forgiving, but that means semantically different postings can be treated as the same after a board re-post or a scrambled title.

This is a useful heuristic for a crawler, but it is also a correctness risk when it decides whether a previously tracked job is still open versus a new title. The same caution applies to `find_repost()`, which matches by title keywords and board rather than by a stable external ID.

Impact: false “same posting” matches and mis-labeled reopen/closed events.

## 4) Important job families are silently filtered out before scoring

`radar/keywords.py` drops titles aggressively, and the filter is mostly string-based. For example, `TITLE_DROP` removes large classes of titles before a role ever reaches the scoring rubric.

This is intentional for a candidate-specific scraper, but it also means the system will silently exclude postings that are not obviously in the target vocabulary. A legal/market-structure role with a less common title or a title that contains a generic word like “engineer” or “operations” can get discarded before the scoring stage can ever decide whether it is a fit.

Impact: false negatives that are hard to see because they never make it into results.

## 5) The generic page verification flow is fragile when JS-heavy or partially structured employer pages are involved

`radar/verify.py` supports JSON-LD detection and many ATS-specific paths, but the fallback “generic employer page” logic depends on `jsonld_verify` and a clear `JobPosting` payload. That works for structured employer pages, but many legal/regulatory jobs are hosted on less consistent pages, or on pages that render the content client-side.

The result is an “unverified” outcome rather than a real closed/open decision. That is not just a data-quality issue; it means valid postings are left out of the output even though the repo is explicitly designed around “verify before listing.”

Impact: unverified jobs are treated as missing rather than as likely valid jobs.

## 6) The build assumes a single run-day run id, which makes replay and branching brittle

`radar/config.py` defines `run_id()` as a date string by default, and many output files live under `data/runs/<run_id>/` and `out/` markdown snapshots. That is fine for a single-day pipeline, but it creates friction when the same repo is used for multiple runs, branch experiments, or parallel replays.

If a run is re-executed or two processes share the same date but different intent, the code reuses the same directory and writes over state. The project does mitigate this with `RADAR_RUN_ID`, but the default design makes that a fragile footgun rather than an explicit process model.

Impact: stale or overwritten results across multi-run or replay workflows.

## Overall assessment

The codebase is disciplined, but the biggest correctness risks are the layered heuristics: ATS discovery, title dedupe, and relevance filtering. Those are all intentionally “best effort,” but they can quietly produce false negatives that are difficult to detect without visible output or regression tests.
