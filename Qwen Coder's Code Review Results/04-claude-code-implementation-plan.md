# Implementation brief for Claude Code (paste-ready)

This file is written to be handed directly to Claude Code in the repo. It sequences the review
findings from `01`–`03` into ordered tasks with acceptance criteria. Run order matters: Task 0 and 1
unlock recall for everything downstream.

---

## TASK 0 — Guardrail amendments first (CLAUDE.md, .gitignore)

Add to CLAUDE.md "Rules":

- Alumni channel rule: "The radar never stores or uses credentials for Penn, schools, webmail or any
  login-gated site. Alumni-board content enters only through files the user exported or forwarded
  himself into `data/alumni_inbox/` (git-ignored). Portal-only listings that can't be verified on an
  employer page go to a separate clearly-marked 'unverified, school-portal only' table."
- Niche-channel rule: "Reddit access uses the public `.json` endpoints at ≤6 requests/minute with the
  standard User-Agent; honor robots; never use API keys that require OAuth of the user's account
  without a new explicit decision."

`.gitignore`: append `data/alumni_inbox/`.

**Accept:** diff shows both edits; `git check-ignore data/alumni_inbox/x.eml` succeeds.

## TASK 1 — Keyword vocabulary expansion (`radar/keywords.py`)

Apply the `TITLE_FAMILIES`, `DESC_PHRASES` additions listed in doc 02 §5. Keep every new family
subject to the existing knowledge-title guardrails (add any new families needing context to
`_NEEDS_FINANCE` where appropriate — e.g. `fund/LP research`).

**Accept:** unit-style script `python - <<'PY'` asserting: relevance() True for
("Legal Engineer, Litigation Finance", ""), ("Claims Evaluator — Pre-settlement Funding", "litigation"),
("Analyst, Alternatives Due Diligence", "private credit fund"), False for ("Legal Operations Coordinator", ""),
("Data Engineer", ""); all previously-passing seed titles still pass (regression list from out/jobs.csv fit rows).

## TASK 2 — Feed channel (`radar/discover/feeds.py`) + `seeds/feeds.csv`

New registry CSV: `name,url,kind,notes` seeded with:
```
aistartupjobs,https://aistartupjobs.com/rss.xml,rss,"AI startup jobs incl legal/AI-governance"
hnrss-whoishiring,https://hnrss.org/whoishiring?count=100,rss,"complements hn.py Algolia pull"
penn-law-public-events,https://www.law.upenn.edu/live/calendar.rss,ics,"events not jobs; optional, low priority"
```
(Implementation note: **verify each feed URL's real path with one polite GET before committing the row**;
if aistartupjobs serves no RSS, fall back to polling its listing HTML with `_links`-style extraction.)

Channel logic: fetch → parse RSS/Atom via stdlib `xml.etree.ElementTree` (tolerant of namespaces) →
for each item: title, link, pubDate; run `relevance()`; emit `Lead(source="feeds:<name>", …)`; then
apply the existing trick from `discover/common.py`: if the item *body* contains an ATS URL, prefer it
as the lead URL. Register `"feeds"` in `pipeline.CHANNELS` and `__main__.py` discover choices.

**Accept:** `python -m radar discover feeds` writes ≥0 leads without error, logs per-feed counts via
`record_channel`, respects cache TTLs, and a dry run against a fixture RSS string parses items with
weird namespaces. Feeds that 404/robots-block are logged as skipped, not failures-that-crash.

## TASK 3 — Widen the Common Crawl sweep (`radar/discover/commoncrawl.py`)

- Add patterns: `workday` (`*.myworkdayjobs.com/*`), `recruitee` (`*.recruitee.com/*`),
  `breezy` (`*.breezy.hr/*`), `jazzhr` (`[a-z0-9]+.hire.jazzhr.com/*`), `ripple` (`*.ripplehire.com/*`).
- Token regex per family; extend `SKIP_TOKENS`; reuse existing state spread (`cc_boards.json`) — the
  MAX_TOKENS cap already carries overflow forward.
- New pull adapters: breezy (`https://{co}.breezy.hr/json`), jazzhr
  (`https://{co}.hire.jazzhr.com/jobs.json` — confirm shape once, politely), ripple
  (`https://{co}.ripplehire.com/nsearch-api/v1/jobs/search?sortBy=freshness&pagedFetch=false&facet=[]`
  — verify; else JSON-LD page route), recruitee already exists. Workday: build spec from
  `{tenant}|{wd-host}|{site}` exactly like `phase2.detect` does so discovered boards flow straight
  into `workday.pull`.
- Sync `ATS_URL` in `discover/common.py` with every added host pattern.
- SmartRecruiters: do NOT hit the blocked API; route discovered `jobs.smartrecruiters.com/{co}` boards
  through the JSON-LD verifier instead.

**Accept:** `discover commoncrawl` completes within the same wall-clock budget (parallel pulls);
`discovered_boards.csv` gains a `family` column; test that ATS_URL matches sample URLs of every family.

## TASK 4 — Niche verticals channel (`radar/discover/niche.py`)

First-run behavior per host: GET `/robots.txt`; disallow ⇒ log skipped. Targets:
1. `legaloperationsjobboard.com` job index (WordPress listing pagination; extract `<a>` to single-job pages; keep titles passing `relevance`).
2. `lawnext.com/jobs` category pages (firm innovation/alt-cats + vendor jobs).
3. `reddit.com/r/legaltech/new.json` + `r/biglaw/new.json` (title filter regex for hiring intent: `hiring|looking for|opening|role|position`, then link-scan posts/comments via `ATS_URL` — mirrors `hn.py` structure; header `User-Agent` from config; 6 s sleep between subreddits).
4. `a16z crypto job board` greenhouse token auto-detected by phase2 registry addition (companies.csv row, segment `crypto_legal`).

Emit `Lead(source="niche:<host>", …)`. Register in `CHANNELS`.

**Accept:** each target independently try/except'd; run log shows per-target queried/candidates/skipped;
no target failure aborts the channel; polite-client tests (rate limit honored — assert timestamps).

## TASK 5 — Search-query expansion & pruning loop

- Replace `seeds/search_queries.csv` with schema `query,channel,bucket,results_used,last_yield_runs`
  and merge the doc-02 §4 rows (dedupe against existing 14; drop the three zero-yield ones unless reworded).
- In `.claude/commands/refresh-jobs.md` step 1: after importing websearch leads, update
  `results_used` per query; add step 1a: "Any query with two consecutive zero-yield runs gets reworded
  or removed; propose replacements from the bucket with the fewest live queries."

**Accept:** CSV loads with old code paths (`websearch.run()` still counts rows); command text updated.

## TASK 6 — Alumni inbox bridge (`radar/alumni.py`, `import-alumni`)

Implement doc 03 §3 Modes A+B. Files: `radar/alumni.py` (parse eml/html/txt/csv → Leads + portal-only
rows), CLI subcommand `import-alumni [DIR] [--dry-run]`, output section `out/alumni_only_<date>.md`,
`source_bucket=alumni` tag flowing into `out/jobs.csv` and the diff summary. Add refresh-jobs step 1b.
Ship a redacted fixture digest under `tests/fixtures/` (fake employer names, no real PII) and a parser
test against it.

**Accept:** dry-run on empty dir = clean no-op message; fixture digest yields expected lead count;
portal-only listing lands in alumni_only table marked unverified; nothing in `data/alumni_inbox/` ever committed (`git status` proof).

## TASK 7 — `/alumni-map` command + contacts seed

Per doc 03 §4. Create `seeds/alumni_contacts.csv` (header only + one placeholder row the user edits)
and `.claude/commands/alumni-map.md`. The command must: read only hand-entered contacts + public WebSearch;
write `out/alumni_map_<date>.md`; include the standing instruction "never send, submit or contact."

**Accept:** command file passes shellcheck-of-common-sense (valid frontmatter like refresh-jobs.md);
dry description of workflow reviewed by user before first real run.

## TASK 8 — Housekeeping quick wins

- USAJobs key setup prompt in refresh-jobs step 0 (doc 01 A6).
- Run-log line: postings dropped solely for empty location (A7).
- `TITLE_DROP` regression table from current fit rows (B1).
- Wayback-as-discovery CDX pass over companies.csv careers domains (A5) — behind env flag `RADAR_WAYBACK_DISCOVER=1`.

## Sequencing & risk notes

- Tasks 0→1 strictly first. 2 and 4 depend on 1 (recall). 3 is independent but largest; do it after 2
  ships so weekly value arrives early. 6→7 last (needs user's own exports to test meaningfully).
- Every new channel must go through `client()` (never raw httpx), `add_leads()` dedupe, and
  `record_channel()` — the run log is the audit trail; treat a channel without logging as broken.
- After each task: `python -m radar refresh` smoke run + commit message convention
  `radar: <task> (<channel>)`.
