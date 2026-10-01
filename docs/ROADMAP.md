# Roadmap

What's next for the radar, in order. Rulings and rejected ideas are in [DECISIONS.md](DECISIONS.md). This replaces
`docs/EXPANSION_PLAN.md` (in git history at commit `a673b7b`), keeping only open work.

## The shape to build toward

The thesis seat families (litigation-finance underwriting, legal-AI research, business-side regulatory risk,
finance academies, embedded research, plus credit-intel legal analyst seats) mostly sit at employers the radar
couldn't read: custom career sites, Oracle/Eightfold/Rippling/Salesforce portals, or no public board at all. The
broad Common Crawl sweep already produces plenty of generic in-house counsel rows. So the core is a monitoring
instrument over a growing set of thesis employers, watched reliably; breadth is an edge that promotes employers
into that core. Rule: **discovery promotes employers, not just postings** — a thesis fit from any source adds its
employer to `seeds/companies.csv` with an origin tag.

## Wave 3: infrastructure and measurement

1. **Skip detail fetches that haven't changed.** Greenhouse, Ashby and Lever list JSON carry per-posting update
   times; reuse the stored detail when unchanged. Cheapest test first: check which hosts send ETag/Last-Modified,
   and add conditional requests only for those.
2. **Coverage report per seat family** in `run_log.md`: fit rows found, thesis employers checked, employers still
   dark. Add an origin per board (`registry`, `cc`, `feed`, `lead`) and a `thesis_fit` count per channel, with three
   distinct states: searched with no result, not covered, blocked.
3. **Source tiers** in `data/source_health.csv`: `watch` (thesis employers that post twice a year; never
   auto-retire), `standard` (retire after 8 weeks with no leads), `experimental` (retire after 3 weeks).
4. **Evergreen flag**: close date more than 180 days out, posted more than 120 days ago, "talent pool" / "general
   interest" wording, or unchanged across 4+ snapshots. Sorts to the bottom. (The aggregate list already drops
   events and talent pools.)
5. **Per-host politeness overrides** (`apply.workable.com` probes at 3–5 s, `legal.io` Crawl-delay 3).
6. **Hot watchlist**: about 25 thesis employers polled Mon/Wed/Fri once item 1 makes that cheap.
7. Smaller: per-ATS error counters in the silence check; content-type checks before parsing JSON; a warning when
   Greenhouse pay fields stop parsing; shard scheduling only once the registry passes ~300 employers.

## Wave 4: light up the dark registry

In order of value:

1. **Oracle Cloud HCM adapter** (DTCC `ebxr|us2|CX_1`; JPMorgan and other banks use the same system).
2. **Eightfold adapter** (Millennium: Legal, Compliance, Risk).
3. **Moody's** via its careers sitemap and job-page JSON-LD.
4. **Rippling adapter** (Eurasia Group).
5. **Careers-page change watch** for employers with no readable board (Parabellum team page, LSTA loan-market jobs,
   The Capitol Forum, ISDA, Balyasny, Hunterbrook): one fetch per employer per week, JSON-LD if present, otherwise
   a hash of the jobs section; a change becomes a lead.
6. **Small-ATS feeds**: Breezy, JazzHR, Recruitee, BambooHR, Teamtailor, iCIMS feed URLs; widen the Common Crawl
   patterns only for named dark employers.
7. **Board registration from verified postings** and **ATS-migration detection** (a board that 404s gets its
   company re-probed).
8. **Seeds for thesis-dense sectors only**: ratings (KBRA, DBRS Morningstar, AM Best), claims trading (Xclaim,
   Claims Market), restructuring advisory (AlixPartners, Ankura, Stout, M3, PJT), IP litigation finance (RPX,
   Unified Patents, Ocean Tomo), index governance (MSCI, S&P DJI, FTSE Russell), Expert Institute, PLI, LexisNexis
   Practical Guidance. About 30 rows, tagged by origin.
9. **Web-search query rotation**: about 40 queries per run; retire after 0 leads in 4 runs; promote from phrases in
   thesis-fit postings. Add query families from DISCOVERY-IDEAS: litigation-risk and ATE insurance diligence, proxy
   and governance research, political-risk intelligence, competition and market-conduct research, counterparty
   diligence. Add one `site:<domain>` query per dark employer.

## Parked until Seth opts in

- Google Alerts RSS (about 15 alerts in thesis vocabulary; created in his browser, URLs into `seeds/alerts.csv`).
- Recruiter alert emails through `import-inbox` (BarkerGilmore, Major Lindsey, Kinney, Lippman Jungers). For
  litigation funders that post nothing publicly, this is the main channel.
- A Brave Search API key, so web search runs in CI without Claude.

## Learning loop

- Seth's near-miss replies become rubric and keyword changes.
- Monthly miss audit: when a thesis employer's hire becomes public, check whether the radar ever saw the seat.
- Fit-signal decorrelation: JD, pay ≥ $150K, fintech subject and 2–5 years co-occur in almost every product-counsel
  posting; consider counting them as one signal so 3 of 10 means something.

## Left open by the 2026-10-01 code review

Three reviewers read every module; the confirmed defects were fixed (see git history for that date). These were
judged not worth changing yet:

- **Verification cache.** Responses are reused for `RADAR_CACHE_TTL_HOURS` (20), including the fetch that proves a
  posting is open. CI never keeps `cache/`, so it is only a risk for two local runs under 20 hours apart. Shorten the TTL
  for verification calls if local runs become routine.
- **`years_required` takes the smallest mention**, so "7+ years of legal experience ... 2 years with Excel" earns the
  2-5 band signal. The 10+ and 6+ excludes use the full list and are unaffected. Changing it moves many scores.
- **Growth.** `data/leads.jsonl` (about 1.2 MB, re-read under a lock on every add) and `out/run_log.md` (about 1 MB, rewritten
  every run) only grow. Prune leads past `LEAD_WINDOW_DAYS` and trim the log's http table when it matters.
- **Dead code** in `radar/db.py` (`board_jobs`, `write_snapshot`, `snapshot`, `previous_run`, `get_judgment`, `put_judgment`
  and their tables), `extract._JD_ANY`, and an unreachable branch in `textutil.html_to_text`.
- **Government portals** (`public_sector` NYDFS, NY AG, statejobs) still produce leads that score as "Government seat".
  They cost requests and add nothing; keep only FINRA and the NY Fed when that channel is next touched.
- **Repost matching** treats one company + title + listed pay as one choice; two genuinely different reqs that share all
  three are shown once. Revisit if Seth finds a missed twin.

