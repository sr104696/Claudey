---
description: Re-run the job radar (phases 1-5), judge new rows, and summarize what changed
---

Refresh the job radar and report what changed. Follow CLAUDE.md (rubric and site rules) throughout.

1. **Alumni alerts.** If `data/inbox/` has saved 12twenty or Handshake alert emails (.eml/.html/.txt), run
   `python -m radar import-inbox`. Never open the alumni boards themselves (login-gated, robots-disallowed).

2. **Web-search discovery.** Replay the queries in `seeds/search_queries.csv` with WebSearch. For every result that
   shows a specific posting (title and company visible; skip LinkedIn, Indeed and Glassdoor), write one JSON line
   `{"source": "websearch:<domain>", "url": ..., "company": ..., "title": ..., "location": ..., "note": "<query>"}`
   to `data/websearch_leads_<today>.jsonl`, then run `python -m radar import-leads data/websearch_leads_<today>.jsonl`.
   Don't open result pages; the radar verifies every lead itself.
   Then maintain the query file: set `results_used` for each query; increment `zero_runs` when it yielded nothing,
   reset it to 0 when it yielded something. Remove queries with `zero_runs` >= 2, and for each bucket whose queries
   all yielded nothing, write one new variant in that bucket's vocabulary (keep 30 to 45 queries overall).

3. **Run the pipeline** (discovery channels run in parallel, then board pulls, verification, scoring, output):
   `PYTHONIOENCODING=utf-8 python -m radar refresh`

4. **Judgments.** If the summary lists `judgment_batches_pending`, judge them in parallel: one subagent per batch file
   in `data/judgments/pending/`. Each subagent reads its batch and CLAUDE.md, and writes
   `data/judgments/results/<same name>.json`: a list of objects with
   `key, desc_hash, sales_attached (Y/N), domain_floor_years (int or null), domain (str), meets_floor (Y/N/stretch),
   litigation_accepted (Y/N/unclear), jd (Y/N/pref), hard_exclude ("" or reason), override_regex_exclude (true only
   when the posting's own words show the row's pattern-based exclusion misfired, e.g. "this is not a commission role"
   or "statistics a plus" read as required), rationale` (one line quoting the posting).
   Then run `python -m radar apply-judgments` and `PYTHONIOENCODING=utf-8 python -m radar score`.

5. **Summarize** for the user: start with the run log's **Silence check** (any source that crashed, went quiet,
   degraded or was skipped, and what that means for coverage). Then, from `out/diff_<today>.md` and the summary JSON:
   counts of new fit rows, new poor-match rows and closed rows, the top 5 new fits (title, company, pay, link),
   notable pay changes, and whether `out/alumni_leads.md` has alumni leads to check by hand.

6. **Commit** `out/`, `data/snapshots/`, `data/source_health.csv`, `data/leads.jsonl`, `data/judgments.jsonl`,
   `data/cc_boards.json`, `data/discovered_boards.csv` and `seeds/` with a message like `Job radar refresh <date>`.
