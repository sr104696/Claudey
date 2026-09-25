# Implementation plan for a Claude Code session

Paste-ready, ordered task list. Tasks 0–2 restore correctness (do them before adding any new
source — new sources built on a silently-dropping pipeline inherit the drops). Tasks 3–7 expand
the sweep. Every task has acceptance criteria; run `python -m compileall -q radar` and
`git diff --check` before each commit. All file:line citations are against commit `f492964`.

Rule reminders for the session (from CLAUDE.md): no logins, no captcha/paywall bypass, no
LinkedIn/Indeed/Glassdoor, robots.txt and 1 req/s per host are hard constraints, aggregators
are leads not evidence, every listed row needs a this-run fetch showing the posting is open.

---

## Task 0 — Sweep-killer fixes (all small; one commit per fix group)

1. `radar/discover/official_apis.py:14` — replace `MUSE_CATEGORIES` with
   `["Legal Services", "Accounting and Finance", "Data and Analytics"]`; log a warning when a
   category returns `total == 0`.
2. `radar/ats/lever.py:54-62` — paginate with `skip` in steps of 100 until a short page; apply
   the same total to `probe`.
3. `radar/pipeline.py:117` — capture `run_discovery`'s exit codes; record any non-zero channel
   in `out/run_log.md` via `runlog.record_channel(...)` and flag it in the summary.
4. `radar/discover/wayback.py:38` — change `engineer(?!.*legal)` to `(?<!legal )engineer(?! legal)`.
5. `radar/output.py:78` — delete `and not p.poor_reason`.
6. `radar/phase2.py:237-238` — keep SmartRecruiters postings: `st, ps = smallats.sr_pull(...);
   return st, [_relevant(p, segment) for p in ps]`.
7. `radar/discover/commoncrawl.py:103-110` — stamp `last_checked` only when the pull status is
   `"ok"`.

**Acceptance**: a `refresh` run shows Lever boards veeva/sunsrce with >100 jobs in
`data/discovered_boards.csv` re-checks; the run log shows Muse leads from "Legal Services";
`out/recurrence.md` can produce "legal engineer" family rows.

## Task 1 — Verification honesty (stop false "closed" / false "open")

1. `radar/verify.py:42-61` — never cache a failed Jane Street feed fetch; feed failure →
   `unverified`, feed loaded + id absent → `closed`.
2. `radar/ats/ashby.py:106-115` — in `verify`, skip jobs with `isListed is False` (return a
   closed stub).
3. `radar/ats/html.py:36-42` — `rmk_sitemap` returning zero URLs is its own status
   (`"empty_sitemap"`), not `"ok"`; follow sitemap-index files.
4. `radar/phase2.py:264-273` — on "board not found", re-run `detect(row)` before recording the
   status.
5. `radar/http.py:269-290` — after the redirect loop, a terminal 3xx →
   `Rules(state="error", note="robots.txt redirect loop")`, never `parse()` the body.

**Acceptance**: fixture tests: delisted Ashby job → closed; dead Jane Street feed → unverified
(not closed); empty sitemap → distinct status in run log.

## Task 2 — Extraction and scoring correctness

1. `radar/extract.py:199` — `\bbar\b` (word boundaries).
2. `radar/extract.py:162,173-178` — check context on both sides of a year mention; return the
   full `(lo, hi)` of the requirement mention, not `min()` across all mentions.
3. `radar/extract.py:182-188` — add `admission to (the|a) … bar` phrasing; delete dead `_JD_ANY`.
4. `radar/score.py:37`, `radar/keywords.py:118,121` — allow `[-–—]\s*\d{1,2}` ranges in
   year-based excludes.
5. `radar/phase4.py:229-235` — include poor-bucket rows with `fit_score >= 2` in judgment
   batches (matches the docstring); add a judgment `veto` field that can reverse a regex
   hard-exclude.
6. `radar/phase2.py:274` + `radar/discover/common.py:10,23` — keep `unknown`-bucket relevant
   postings; render them under a "Location not stated" heading instead of "Outside NYC"
   (`radar/output.py:88-91`).
7. `radar/models.py:62-66` — when two postings share a dedupe key but differ in ATS `job_id`
   or `url_key`, keep both.

**Acceptance**: "Admission to the New York State Bar required" → `jd_required=Y`; "6–8 years of
leveraged finance" → hard exclude; "3+ required, 10+ preferred" → not excluded; same-title
two-req postings both appear in `out/jobs.csv`.

## Task 3 — Generic feeds channel + `seeds/feeds.csv`

New `radar/discover/feeds.py` (mirror `websearch.py`'s CSV-driven shape) reading
`seeds/feeds.csv` (`url, format, label, title_allowlist`): fetch each feed through the polite
client, parse JSON feeds and RSS/Atom (stdlib `xml.etree` is fine — no new dependency needed
for the two starter feeds), emit `Lead`s through `add_leads`, record per-feed counts and
failures via `runlog.record_channel`. Register `"feeds"` in `pipeline.CHANNELS`.

Seed it with:

```csv
url,format,label,title_allowlist
https://hirelegalops.com/jobs.json,json,hirelegalops,"legal engineer|legal product|innovation|knowledge|AI|legal technolog|legal data|legal research"
https://www.arbeitnow.com/api/job-board-api,json,arbeitnow,"legal|compliance|counsel|regulatory"
```

**Acceptance**: `python -m radar discover feeds` writes leads from both feeds to
`data/leads.jsonl` and a channel row to the run log; a feed 404 is recorded as a failure, not
silence. Both feed URLs were verified live during this review (2026-09-24).

## Task 4 — Registry expansion with verified endpoints

Add rows to `seeds/companies.csv` for: Harvey (ashby: `harvey`), Ironclad (ashby:
`ironcladhq`), Relativity / Everlaw / DISCO (greenhouse: `relativity` / `everlaw` / `disco`),
Clio (workday CXS: `clio.wd3.myworkdayjobs.com/wday/cxs/clio/ClioCareerSite`). All verified
live during this review. Also fix the detection gaps so future employers self-register:

1. `radar/phase2.py:48-58` — add `jobs.eu.lever.co`, Greenhouse `embed/job_app`, and
   detect-only patterns for iCIMS/Taleo/Jobvite/SuccessFactors/UKG (record "unsupported ATS:
   X" instead of `none`).
2. Wire the existing `wk_detail`/`bb_detail` adapters into `verify_url`
   (`radar/verify.py:50-123`).
3. `radar/verify.py:14-18` adjacency: mine aistartupjobs.com **once, in a browser**, for AI
   startups with open Legal & Compliance seats and add those employers — never scrape the site
   (Cloudflare-challenged, verified).

**Acceptance**: `python -m radar boards` pulls live job counts for all six new employers; a
careers page on Lever-EU detects as lever.

## Task 5 — Robustness of existing channels

1. `radar/official_apis.py:34,62,79,97` + `radar/discover/hn.py:25,28,34` — guard every
   `r.json()`; one bad payload must not zero a channel.
2. `radar/discover/hn.py:56-59` — give each parsed role its own lead URL.
3. `radar/official_apis.py:76` — paginate Adzuna; `:55-57` — add a no-location telework
   USAJobs pass.
4. `radar/discover/commoncrawl.py:100-102` — sort stale boards by `last_checked` ascending;
   rotate the `MAX_PAGES` harvest offset through state.
5. `radar/http.py:137,155-165` — heartbeat the host-gate lock mtime during crawl-delay sleeps.

**Acceptance**: kill -9 a discovery subprocess mid-run → run log shows the channel crashed;
two concurrent `refresh` processes never overlap requests to a `Crawl-delay: 120` host.

## Task 6 — Search-query pack and pruning

Add the eight query rows from NEW-SOURCES.md to `seeds/search_queries.csv`, and add a
`results_used == 0` streak report to the run log so dead queries get pruned after N runs.

**Acceptance**: next `/refresh-jobs` run log lists per-query yield including the new rows.

## Task 7 — Alumni email-alert importer

Per ALUMNI-PIPELINE.md: new `python -m radar import-alumni <path>` parsing exported
`.mbox`/`.eml` files from `data/alumni_inbox/` (git-ignored) into leads with
`source="alumni:12twenty"` / `"alumni:handshake"`; portal-only postings render in a separate
`requires_user_review` output table, never in fit/poor. Add a test that rejects input files
containing credential/cookie-shaped content. The tool must never connect to a mail server or
hold credentials — the user exports the mailbox folder by hand.

**Acceptance**: a synthetic 12twenty alert `.eml` fixture produces a lead row; a fixture with
`Set-Cookie` content is rejected; portal-only links land in `requires_user_review`.

---

## Sequencing notes and risks

- Tasks 0–2 are independent of 3–7 and of each other within a task; land them first so new
  sources aren't evaluated by a broken scorer.
- Task 4's new employers will immediately exercise Task 0's Lever fix if any are Lever-hosted
  — good regression signal.
- The Muse fix (Task 0.1) will add ~150–250 new leads on the first run; judgment batches
  (Task 2.5) should land first or that run's judging will be manual-heavy.
- Do **not** attempt Reddit/r-legaltech ingestion (robots.txt blanket disallow — verified) or
  aistartupjobs scraping (Cloudflare challenge — verified). Both are covered in NEW-SOURCES.md.
- This review modified no `radar/` code; if Claude Code implements tasks from this plan, it
  should do so on its own branch and reference this folder's findings per commit.
