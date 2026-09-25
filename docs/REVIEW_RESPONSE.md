# Response to the September 2026 code reviews

Four reviews (Codex, Kimi CLI, Qwen, Vibe) are in the review folders. Their claims were checked against
the code and, where possible, live before anything changed. This file records what was done and why.

## The pattern behind the bugs

Almost every real bug had the same shape: **a failure that looks exactly like "no jobs today."** A renamed
API category returns HTTP 200 with zero results; an unreachable robots.txt blocks a host silently; a crashed
channel leaves no record; an empty sitemap reports "ok". Fixing each one leaves the next one invisible, so
alongside the fixes the radar now has a **silence alarm** (`radar/health.py`): every channel's and board's
yield is recorded per run in `data/source_health.csv` and compared with the previous run. Crashed, went-quiet,
degraded, not-run and skipped sources are listed at the top of `out/run_log.md` ("Silence check") and in the
refresh summary. This is Codex's coverage-measurement idea, aimed at the failure shape the bugs actually show.

## Implemented

| Finding (source) | Verified how | Change |
|---|---|---|
| The Muse categories renamed; channel silently returned 0 (Kimi K1) | live: "Legal" 0, "Legal Services" 153 NYC | new names; a category returning 0 is logged as a failure |
| Crashed discovery channel leaves no trace (Kimi K3) | code | exit codes feed the silence alarm ("crashed") |
| Transient robots.txt error blacks out a host all run (Kimi K4) | code | error states retried after 10 minutes; redirect loops no longer read as allow-all |
| Wayback "legal engineer" family can never match (Kimi K5) | tested | lookbehind; "Legal Engineer" now classified |
| Relevant postings with unknown location dropped before scoring (Kimi K6) | code | kept as candidates; Phase 4 re-reads the posting |
| Dedupe merges distinct reqs with a generic title (Kimi K7) | tested | merge only when the text matches (reposts) or the ATS differs (same req, two systems) |
| Jane Street feed outage marks every Jane Street row closed (Kimi K8) | code | outage raises; rows become "unverified", never "closed" |
| Empty SuccessFactors sitemap reported as "ok" (Kimi K8) | code | own status: "sitemap had no /job/ URLs" |
| SmartRecruiters results discarded (Kimi B2) | code | returned (still robots-blocked at the API, so dormant) |
| Ashby verify ignores isListed (Kimi B4) | code | delisted jobs no longer verify as open |
| `bar` without word boundaries ("Barclays" → JD required) (Kimi B8) | tested | `\bbar\b` |
| Year excludes can't read ranges ("5–8 years") (Kimi C4) | tested | ranges accepted in the equity-research/banking and lev-fin excludes |
| Regex hard excludes are irreversible (Kimi C15/C16) | code | near-miss rows (fit ≥ 4) excluded only by a pattern go to judges; a judge can set `override_regex_exclude` with a quote |
| Common Crawl: failed pull hides a board 28 days; alphabetical starvation (Kimi C6/C7) | code | stamp only on success; stale boards ordered by last check |
| HN: roles 2-4 of one comment deduped away (Kimi C9) | code | per-role lead URLs |
| SMTP/ntfy failure crashes a finished run (Kimi A13) | code | digest failure is caught and reported |
| No feed channel (Qwen A2, Kimi, Codex) | live: hirelegalops.com/jobs.json, robots allows | `radar/discover/feeds.py` + `seeds/feeds.csv`; one row per new feed |
| Legal-tech employers missing; wrong slugs (Kimi) | live pulls this run | Ironclad, Relativity, Everlaw, DISCO, Clio added; Chainalysis → `chainalysis-careers`, Hebbia → `hebbia-ai` |
| Query set small, unbucketed, never pruned (Qwen A3, Codex) | — | 35 queries in 9 seat-family buckets; `/refresh-jobs` tracks yield and prunes after two empty runs |
| Penn alumni boards (all four) | Kimi, live: 12twenty and Handshake are login-gated with `Disallow: /` | email-alert bridge: `python -m radar import-inbox` reads saved alerts from `data/inbox/`; jobs are matched on the employer's own board; unmatched ones go to `out/alumni_leads.md` for manual checking |
| Out-of-area poor rows invisible (Kimi C3) | design choice, kept | dead rendering branch removed; the list now states how many weaker rows are in jobs.csv |

Also fixed while testing: a damaged `data/jobs.sqlite` (from a force-killed process) crashed the run; the store
now checks itself once per process and rebuilds, since committed CSVs hold the history.

## Declined, with the evidence

| Suggestion | Why not |
|---|---|
| Lever boards truncated at 100 jobs; add pagination (Kimi K2) | The review's own evidence refutes it: `veeva` recorded 916 jobs from one un-paginated call. Lever returns full boards. |
| Reddit r/legaltech channel (Qwen, Vibe) | `reddit.com/robots.txt` is `Disallow: /` and anonymous JSON returns 403 (Kimi, verified). |
| Scrape aistartupjobs.com (Vibe) | Cloudflare challenge; bypassing it breaks the project rules. Reachable only via web-search leads. |
| "Integrate with Symplicity" for Penn Law (Vibe) | Penn Law moved to 12twenty; both boards are login-gated and robots-disallowed. The email bridge is the compliant route. |
| Boost scores for niche sources (Vibe) | Where a lead came from shouldn't change how well the job fits; source quality is tracked in the silence alarm instead. |
| Arbeitnow feed (Kimi) | Mostly European listings; not worth the noise for an NYC/US-remote search. Add a row to `seeds/feeds.csv` to try it. |

## Deferred (worth doing, not yet done)

- More ATS families in the Common Crawl sweep (Workday, Breezy, JazzHR) and detect-and-flag for unsupported ATSs
  (iCIMS, Taleo, Phenom), so `ats=none` stops meaning both "no board" and "board we can't read" (Qwen A1, Kimi).
- Full provenance chain per lead: discovery URL → intermediary → employer posting, with resolve rates per source (Codex).
- Detail fetch for Workday/Workable/BambooHR jobs whose titles are generic (Kimi B7).
- Rate-limit lock heartbeat for hosts with Crawl-delay above 60 s (Kimi A3; no current host is affected).
- Legal Operations Job Board and ACC/CLOC listing pages as lead channels, after a per-site terms review (Codex).
