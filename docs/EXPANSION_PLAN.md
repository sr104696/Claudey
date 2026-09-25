# Job radar expansion plan

Date: 2026-09-25. Input: the master expansion doc (2026-09-26, pasted in session; not yet committed. It
supersedes `claudey-sourcing-expansion-ideas.md`). Section references (§, A1–A25, B1–B17, C1–C12, G1–G5)
point to it. I read it against the prior folders (`new_vibe_suggestions/`, `New Job Radar Expansion Suggestions/`,
`new-qwen-suggestions-expansion-ideas/`, Kimi `NEW-SOURCES.md`, Codex sweep review) and against the repo as it
stands: `radar/`, `seeds/`, `out/run_log.md` (run 36169782966) and `out/jobs.csv` (969 rows).

---

## 1. What the repo says today

These numbers drive every call below. All come from files in the repo.

| Fact | Evidence | So what |
|---|---|---|
| 57 fit rows. 26 are from registry employers. 23 are from boards outside the registry, and those are almost all Common Crawl boards (Brex, Fivetran, Bumble, Samsara, Automattic, Delinea, Hims…). | `out/jobs.csv` joined to `seeds/companies.csv` | The broad sweep already produces plenty of fit rows. Almost all of them are generic in-house product, privacy or regulatory counsel. |
| Registry detection is dark exactly where the thesis lives. Litigation finance: 10 of 13 `none`. Policy research: 9 of 10. Trade associations: 4 of 4. Funds: 8 of 19. Plus Moody's, DTCC, ICE, Marqeta, Klarna. | `board_status` by segment in `seeds/companies.csv` | Seat families 1, 3 and 5 are the least-covered part of the pipeline. That is a coverage failure, not a recall ceiling. |
| About 40 Workable probes in one run returned **HTTP 429**. Each company was then logged as "no probe hit". Only 3 Workable calls returned 200. | `out/run_log.md` Failures section | "Searched, no result" and "blocked" were merged, against §15(e). Many of the dark employers above were never actually checked. **Fixed in this commit** (see §7). |
| 55 Axiom rows and 14 "at least 18 years of age" rows were hard-excluded as "Asks for 10+ years". | `hard_exclude_reason` in `out/jobs.csv` | A regex bug in `extract.years_mentions`. **Fixed in this commit.** |
| `fit_score`: 260 rows at 4, 211 at 3, 169 at 5. The fit bar is 3 of 10. | `out/jobs.csv` | The score doesn't discriminate. JD, base ≥ $150K, fintech and 2–5 years co-occur in every product-counsel posting. |
| 7 of 57 fit rows are NY AG or state litigation seats (appellate, civil litigation, prosecution). | `out/open_positions_2026-09-25.md` | CLAUDE.md says he doesn't want court time. The rubric only enforces that for law-firm associate seats. |
| 35 of 57 fit rows have domain floor "meets: stretch" or no judgment. | `domain_floor` column | Stage 2 is still binding on most "fit" rows. The table overstates actionable fit. |
| Channel yield: HN 0 of 750 comments. Wayback 0 leads. The Muse 113 leads, 3 verified. hirelegalops 23 → 14 kept. Public sector 20 → 20 verified, **12 fit**. Web search 41 leads (09-24), 0 when Claude isn't in the loop. | run_log Channels table | Public sector is the highest-precision channel. Web search is the only channel that reaches thesis seats outside the registry, and it depends on Claude being in the loop. |
| `posted_date` is present on 943 of 969 rows. | `out/jobs.csv` | Priority item #14 (datePosted) is mostly already done. Only the `--since` filter remains. |
| No ETag or If-None-Match anywhere in `radar/http.py`. Phase 4 re-fetches every posting at 1 req/s (the Greenhouse boards-api host dominates). | grep; the run log's "Requests by host" | Conditional requests and list-API `updatedAt` are both unbuilt. Together they are the biggest request saving available. |

---

## 2. The five positions, steel-manned

| Position | Strongest argument | What it would cut |
|---|---|---|
| **Breadth-maximalism** | You can't score a posting you never saw. Seats in thesis families open once or twice a year per employer, so the registry has to be huge to catch any one week's openings. The token miners (B8–B11) and firm-graph pools (B1–B5) are cheap per employer. | Rubric tinkering, since precision can be fixed later, and any throttling of new channels. |
| **Freshness-first** | Litigation-finance and credit-intel seats get filled from the first 2–3 weeks of applicants and through recruiters. A seat found on day 30 is worth little. Events like funding rounds, new GCs and CT-log subdomains predict seats before they post. | Bulk seeding (B1, B2) and low-frequency channels. Every run should go to the watchlist and events. |
| **Precision / vocabulary** | The table already has 57 "fits" and most aren't what he asked for. Every added channel multiplies near-miss review, and Seth's attention is the scarcest resource. Fix the rubric, seat-family tagging and keyword families first. | Most new channels and sectors (A12–A25), and every mass seeder. |
| **Infrastructure-first** | Greenhouse is one host for hundreds of boards, and Phase 4 re-fetches everything. Seeding 3–5× more employers makes each run slower, not richer. The Workable 429 storm has already shown that growth breaks detection silently. Shards, conditional requests and 3-state tracking come before any growth. | Anything that grows the registry before the plumbing exists. |
| **Skeptic** | 4 of 7 current discovery channels produced 0 or ~0 fit rows (HN, Wayback, Muse, CC for thesis families). Most of the doc's 60+ channels will die at zero yield. The validation contract and per-origin yield reporting are the only durable parts. | Everything without a cheapest-test-first gate. |

## 3. Where they conflict

1. **Breadth vs precision is a real conflict, not just a sequencing question.** Breadth adds generic tech employers (GitHub token miner, CC, Wikidata). The data shows those produce generic in-house counsel, and precision would have to throw them away. They can live together only if the output separates thesis-family seats from generic counsel. That separation is the decision point (item P2 below). Without it, breadth wins recall and loses Seth's attention.
2. **Freshness vs infrastructure is sequencing.** A daily watchlist poll is only polite and cheap once conditional requests exist. Infrastructure has to come first. Freshness then gets most of its value at almost no cost.
3. **The skeptic vs breadth, on seeding.** Breadth says seed thousands of firms. The skeptic points out that detection already fails on 45 of 128 employers, 35%. Seeding more firms into a detector that can't see custom career sites mostly adds `none` rows. The skeptic wins on sequencing: fix detection on the dark 45 before adding firm number 129.
4. **Precision vs freshness, on alerts.** Google Alerts and wires are fresh but noisy. Precision accepts them only if they are keyed to thesis-family vocabulary, not generic "counsel hiring".
5. **What each gives up.** Breadth gives up Seth's review time. Freshness gives up coverage of rarely-posting employers, which events never fire for. Precision risks overfitting to five families and missing the "unusual work" he also wants (the near-miss loop is the hedge). Infrastructure delays visible yield by about a week. The skeptic risks killing sparse, high-value channels too early. §15(d)'s "retire at zero" rule is wrong for channels that post twice a year (see N5).

## 4. Sequenced plan of action

**Phase P: precision and honesty (week 1, mostly config and small code).**

1. **P1. Done in this commit:** fix the years-regex false excludes, and make Workable 429 a "not checked" state instead of "no board". Rows change on the next `score` run.
2. **P2. Split the fit table into two.** First, "Thesis seats": rows matching `score.SEAT_FAMILIES` or the credit-intel family, ranked by domain floor `meets: Y`. Second, "Other in-house counsel fits". `SEAT_FAMILIES` already exists in `radar/score.py`, so this is an `output.py` change plus a `seat_family` column in `jobs.csv`. It lets breadth and precision coexist. **Blocker:** the table headings are Seth's call (Q1).
3. **P3. Court-time rule.** Poor-match government and nonprofit litigator seats: appellate or trial litigation, prosecution, "Assistant Attorney General: Civil Litigation". Keep investigation-titled seats (Investor Protection, white-collar investigations). This mirrors the existing law-firm associate rule and CLAUDE.md. **Blocker:** Q2.
4. **P4. Evergreen and talent-pool flag.** Flag a posting when its close date is more than 6 months out, `posted_date` is more than 120 days old, or the text says "talent pool", "general interest" or "future opportunities". Flagged rows sink to the bottom of the tables (the NY AG row with an Aug. 2027 close date, Axiom's talent-platform listings).
5. **P5. Per-origin yield, including a thesis-fit column.** Extend the run_log Channels table with an origin per board (`registry`, `cc`, `feed`, `lead`) and a `thesis_fit` count. This is the measurement for every later item (priority item #21, moved to the front).

**Phase I: infrastructure before growth (weeks 1–2).**

6. **I1. Skip Phase 4 detail fetches using list-API `updatedAt` and a description hash.** Greenhouse (`updated_at`), Ashby and Lever list JSON already carry these. When a posting's `updatedAt` matches the last snapshot, reuse the stored detail. Being on this run's board listing is itself current evidence the posting is open. This saves most of the ~1,000 per-posting GETs. It's a better first move than general conditional requests.
7. **I2. Conditional requests** (If-None-Match / If-Modified-Since, validators in SQLite) on feeds and board list endpoints. **Cheapest test first:** one HEAD-equivalent GET to `boards-api.greenhouse.io`, Ashby and Lever to see whether they return ETag or Last-Modified at all. Build only for hosts that do.
8. **I3. Per-host politeness overrides.** A `seeds/host_delays.csv` (or config) for hosts that want more than 1 s: `apply.workable.com` at 3–5 s for probes only, `legal.io` at 3 s (Crawl-Delay), and iCIMS/Phenom when they're built. Then re-run Workable detection over the dark 45.
9. **I4. Shard scheduling.** Only once the registry passes about 300 employers, which P, D1 and D2 won't hit. Defer. The trigger is Phase 2 time above 45 min in CI.

**Phase D: light up the dark registry (weeks 2–3). This is where the yield is.**

10. **D1. Careers-page watch adapter** (new idea N1). For every `none` row, fetch `careers_url` weekly. Extract JSON-LD `JobPosting` if present, otherwise hash the visible text of the jobs section and emit a lead when it changes. This covers custom sites, email-to-apply pages and PDF postings: Parabellum, LCM, Therium, Eurasia, Capitol Forum, MLex, Hunterbrook, LSTA, ISDA. One request per employer per week.
11. **D2. Sitemap and JSON-LD sweep for ATS misses** (master doc §6 bullet). Run it before D1's hashing fallback. Same 3-state tracking.
12. **D3. iCIMS and Phenom adapters, only for named dark employers.** First confirm which of Moody's, DTCC, ICE, Millennium, Balyasny, Elliott and SIG sit on each platform: one careers-page fetch each, done inside D2. Don't build Eightfold, Taleo or Kenexa until a dark thesis employer needs them.

**Phase S: targeted seeding (weeks 3–4). Rows only; Phase 2 does the work.**

13. **S1. Seed the thesis-dense sectors only.** A23 ratings (KBRA, DBRS Morningstar, AM Best, Moody's), A7 claims trading (Xclaim, Claims Market, Reorg), A6 restructuring advisory (AlixPartners, Ankura, Stout, M3, PJT restructuring), A1 IP litigation finance (RPX, Unified Patents, Ocean Tomo, Docket Navigator), A9 index governance (MSCI, S&P DJI, FTSE Russell), A14 Expert Institute, A13 PLI and LexisNexis Practical Guidance. About 30 rows. Tag `origin=master_doc_A*` so P5 measures them.
14. **S2. Add the G3 keyword families only for the sectors seeded in S1**, plus "claims trading" and "rating surveillance". Gate each on `_LEGAL_CTX` or `_FINANCE_CTX` as the doc says. Leave the rest of G3 out (see the kill list).
15. **S3. Add feeds.csv rows for keyless, policy-checked feeds:** Arbeitnow, findwork, Jobicy, Himalayas, PND, and HigherEdJobs "counsel". Each with a tight `title_allowlist`. They cost nothing and retire themselves under the yield rule. Check each host's robots.txt at add time.

**Phase F: freshness and recall without Claude in the loop (weeks 4–6).**

16. **F1. One keyed search API: Brave (2,000 queries/month free).** It turns `seeds/search_queries.csv` from a Claude-only channel into a CI channel. Retire the DDG-HTML gray path when it lands. Add a second provider only if the Brave quota binds.
17. **F2. Rotate queries instead of running ~140 every time.** Keep about 40 queries per run. Retire rows with 0 leads over 4 runs. Promote rows from G1, and from phrases in thesis-fit postings, 5–10 per run. This gets the recall of a 140-row matrix at about 30% of the search spend.
18. **F3. Google Alerts RSS, about 15 alerts keyed to thesis vocabulary** ("litigation finance" associate, "legal analyst" restructuring, "claims trading", "credit policy" counsel…). Stored in `seeds/alerts.csv`, polled by `feeds.py`. **Blocker:** Seth creates the alerts in a browser (Q3).
19. **F4. Hot watchlist.** Poll about 25 thesis employers (Burford, Omni, Legalist, Octus, 9fin, Fitch/CreditSights, Point72, D. E. Shaw via leads, Bridgewater, Harvey, Norm AI, Hebbia, Jane Street, Capstone…) on Mon/Wed/Fri with conditional requests (I2). Everything else stays weekly.
20. **F5. BarkerGilmore and other recruiter alerts through `import-inbox`.** No code change beyond sender patterns. **Blocker:** Seth subscribes (Q4).

**Phase L: learning loop (continuous from week 2).**

21. **L1. Near-miss digest.** Put score-2 rows, and fit rows with domain floor "stretch", into a weekly `out/near_miss.md` with one line on why each missed. Seth's reactions (Q5) become rubric and keyword changes.
22. **L2. Miss audit** (new idea N3). Monthly, check thesis-family hires that became public against the snapshots. That is the only direct recall measure available.

---

## 5. Kill list

| Item | Reason |
|---|---|
| **JSearch (RapidAPI)** | It returns scraped LinkedIn, Indeed and Glassdoor listings. Buying another party's scrape still breaks CLAUDE.md's "don't scrape LinkedIn, Indeed or Glassdoor". Killed on principle, not on yield. |
| **Company-size 100–500 filter** (v2 §12) | That filter isn't in CLAUDE.md, and it conflicts with current fit rows (Morgan Stanley, Citi, Blackstone, Mastercard). Drop it. |
| **Craigslist RSS (C5)** | Craigslist's terms prohibit automated access, and it has litigated over that (3Taps). It's also a known scam-posting vector with almost no thesis-family volume. |
| **Query matrix 14→140 as written** | This spends Claude tokens on every refresh. Replaced by F1 plus F2 (API plus rotation). |
| **GitHub code-search token miner (B10)** | Duplicates the Common Crawl sweep, which already found 281 boards. Its marginal board is a generic tech startup, adding to the in-house-counsel pile P2 has to hold back. Reopen only if P5 shows CC boards producing thesis fits. |
| **CT logs, DNS brute force, urlscan, PublicWWW, .jobs (B6–B9, B11)** | Low yield, weekly-cadence plumbing. DNS brute force against employer domains also looks like reconnaissance, which conflicts with the transparent-client posture. |
| **Wikidata and NYS Open Data bulk pools (B1, B2)** | They produce thousands of firms. Detection already fails on 35% of 128. Revisit after D1 and D2 lower the `none` rate. |
| **Chambers/Legal 500 (B12), CourtListener attorney→firm (B17)** | They seed law firms, whose seats the rubric already marks poor (law-firm associate rule). |
| **USASpending (B5)** | Govcon consultancies: cleared work, pay below the floor, far from the thesis. |
| **Kagi, Exa, Tavily, Mojeek pool** | One provider (Brave) is enough until its quota binds. Five adapters is infrastructure without a proven need. |
| **Mastodon, Lemmy, Discourse (C9, C10)** | Near-zero volume in legal-finance hiring. |
| **Typo-variant queries** ("General Council") | Mostly return junk pages and misspelled blog posts. Keep at most one query row as a probe. |
| **Fractional/interim-as-signal (A15, §3c)** | A weak, unmeasurable signal, and the engagements themselves are rubric-excluded. |
| **Long-tail sectors A12 (except RAND), A16, A18–A22, A24, A25** | Off-thesis or pay-floor risk. A18's NYC desks rarely post publicly. Add individual employers only if a web-search lead surfaces them. |
| **Sector-specific trade-association parsers (A8)** | ISDA and LSTA are already in the registry and dark. D1 covers them with one generic adapter. |
| **Legacy ATS adapters (Taleo, Kenexa, SilkRoad, Dayforce, UKG, ADP)** | Build only when D2 names a dark thesis employer on one. |
| **Funding-event, GDELT and wire triggers (B13, B14) for now** | Medium effort. The thesis employers (funds, rating agencies, funders) don't hire off funding rounds. Revisit for legal-AI startups after F4 exists. |
| **Bluesky (C8) for now** | Needs an app password and a new module, and yield is unknown. Cheapest test: one manual search for `#hiring counsel` over 2 weeks. Build only if it finds something the other channels missed. |

---

## 6. Gestalt read and what it changed

**What the pipeline is becoming.** The pipeline already pulls 42K jobs from 352 boards and turns them into 57 "fits". It is becoming a firehose of generic in-house counsel seats with verification attached. The thesis instrument (the five seat families) sits on a dark 35% of the registry. Nearly every idea in the master doc widens the funnel's mouth. The data says the bottleneck is at the other end: whether the table is *about* what Seth wants.

**What it should be.** For the thesis families it should be a slow, high-precision monitoring instrument: a known and growing set of about 150 employers, watched reliably and frequently, where every fetch counts. For everything else it should be a cheap breadth sweep, reported separately and never allowed to crowd out the thesis table. It is a monitoring machine at the core with a discovery machine at the edge, and the edge's job is to promote employers into the core.

**What that changed:**

1. Measurement (P5) and the split table (P2) moved from last to first. Without them, nothing afterwards can be judged.
2. "Light up the dark registry" (D1–D3) ranks above every new-channel idea. It wasn't in the master priority table at all, apart from a sitemap-sweep bullet.
3. The token miners, which the doc ranks #4, were killed. They feed the wrong end.
4. Freshness became a tiered watchlist (F4), not event plumbing.
5. A new rule: **discovery promotes employers, not just postings.** A thesis-fit posting from any origin adds its employer to the registry with `origin` and puts it on the hot watchlist. The pipeline gets better every week as a monitor, which a sweep alone never does.

---

## 7. New ideas

Confidence: H/M/L. Each has its cheapest test.

| # | Idea | Conf. | Cheapest test |
|---|---|---|---|
| N1 | **Careers-page change watch** (D1): hash the jobs section of every `none` employer's careers page weekly, emit a lead on change. This covers the "dark matter" of custom pages, email-to-apply and PDF postings that no ATS, feed or aggregator touches. | H | Fetch the 10 dark litigation-finance `careers_url`s once. Count how many have a stable, extractable jobs section. |
| N2 | **Evergreen and talent-pool detector** (P4). The validation contract treats "listed" as "open", but rolling pools and 2027 close dates aren't seats. | H | Grep `jobs.csv` for talent-pool phrases and closes_date > 180 days. One pass shows the count. |
| N3 | **Miss audit**, the only honest recall metric. When a thesis employer's new hire becomes public (press, lateral news, Seth's network), check whether the radar ever saw the seat. | M | Take the last 3 publicly announced litigation-finance or credit-intel hires. Search the snapshots for the employer and title. |
| N4 | **Discovery promotes employers** (gestalt rule 5). A thesis fit from CC, a feed, or a lead auto-adds `companies.csv` with `origin` and watchlist tier. | H | Count thesis fits in the last 2 runs whose employer isn't in the registry. |
| N5 | **Retire on seat-family-aware thresholds.** §15(d)'s zero-yield retirement would kill the Burford and Octus watch, whose seats open twice a year. Never auto-retire hot-watchlist employers. Broad channels retire at 0 *leads* over 8 weeks, not 0 fits over 3 runs. | H | Compute each registry employer's 12-month posting rate from Wayback captures in `out/recurrence.md`. |
| N6 | **Adversarial failure modes for token and board miners.** Forked repos copy example tokens (for example `boards.greenhouse.io/example`). Agencies host boards under client names. Stale tokens get reclaimed by a different company. Mitigation: require the employer name to match the board's `name` field (already done for Greenhouse only). Extend that to Ashby and Lever CC boards. | M | Sample 30 CC-discovered Ashby and Lever boards and check the name against the slug. |
| N7 | **Scam and phish postings on keyless feeds.** Remote-only boards (Jobicy, Himalayas, Craigslist) carry fake "legal assistant" postings that ask for personal data. Phase 4's employer-domain verification is the defense. Add a rule that a feed lead whose apply URL isn't on an employer domain or a known ATS is never promoted. | M | Review the next S3 feed batch by hand. |
| N8 | **Rank the fit table by "ask-to-offer" asymmetry.** Rows whose `domain_floor` is `meets: Y` and whose employer is in a Stage-2-loosening family go first. Show the rest in rubric-score order. The near-miss bucket's lesson is that *domain floor*, not fit_score, is the discriminating variable. | M | Re-sort today's 57 rows and have Seth rate the top 10 against the bottom 10. |
| N9 | **Fit-signal decorrelation.** JD, pay ≥ $150K, fintech subject matter and 2–5 years co-occur in almost every product-counsel posting and together make a 4. Count them as one "generic in-house" signal so 3 of 10 means something. | M | Recompute fit_score with the four merged. Measure how many of the 57 drop out and whether any thesis row does. |
| N10 | **Public-sector deepening before private breadth.** Public sector is 12 of 57 fits at 100% verification. The NY Fed Workday link is currently broken ("no Workday link"). Add the NY Fed direct Workday tenant, SEC NY regional office, FRBNY and OCC NY (§9 public-sector batch). This has the highest measured precision of any channel. | H | Fix the NY Fed tenant (one careers-page fetch to find the current link). |

---

## 8. Seth's answers (2026-09-25) and what changed

1. **Q1: one table.** Built. It is ordered best-first: ★ seat-family roles, then roles whose experience bar he meets, then listed pay ($200K+ ahead of $150K+), then rubric signals (`output.fit_order`). This replaces P2's two-table split.
2. **Q2: government is out; law firms are out; pay must clear $150K, ideally $200K+.** Built in `score.py` as poor-match rules:
   - `is_government`: public-sector sources, the NY AG adapter, and agency names. FINRA and the NY Fed are left to the pay floor.
   - `is_law_firm`: LLP/PLLC/P.C. names, and "billable hours" or "Am Law" in the text. Underwriting, research and analyst titles are kept.
   - Listed annual base topping out below $150K is poor-match. Rows without listed pay stay in, because the rubric forbids estimating.

   This replaces P3 and is recorded in CLAUDE.md.
3. **Q5: near-miss review, yes if useful.** Built. `out/near_miss_<date>.md` lists up to 12 rows each run. Rows already settled by the government, law-firm or pay rules are left out. Reply **fit** or **right call** per row.
4. **Nothing further required of Seth.** Google Alerts (Q3), recruiter subscriptions (Q4) and the Brave key (Q6) each need a step from him, so they're parked. F1 and F3 stay unbuilt unless he opts in. F2 (query rotation) runs through `/refresh-jobs` as it does today.

Impact on the 2026-09-25 data (a replay of the new rules over `out/jobs.csv`): the fit table goes from 57 to 38 rows.
- Out as government: all 12 NY AG, DFS and State Comptroller rows.
- Out on pay: 7 rows, among them Point72 Canvas (both seats, $81K–$100K), ACLU, Guggenheim's restructuring attorney ($145K top), Palantir and Coinbase.
- The top 8 are now all ★ seat-family rows, led by Burford, Harvey, Citi Regulatory Engagement and Bridgewater.

---

## Closing report

- **Done.** Read the master doc against the prior folders and the live repo state (run log, jobs.csv, registry). Wrote this plan (synthesis, kill list, gestalt read, new ideas, questions).
- **Fixed** 2 bugs found while grounding the plan:
  - (a) `radar/extract.py` `years_mentions` no longer reads "at least 18 years of age" or "for over 25 years, Axiom…" as 10+-year experience asks. It had wrongly hard-excluded 69 rows.
  - (b) `radar/ats/smallats.py` and `radar/phase2.py`: the first Workable 429 now stops Workable probing for the rest of the run, and affected employers are logged as "workable not checked (HTTP 429)". Previously about 40 were logged as "no probe hit", which merged "blocked" with "searched, no result".
- **Verified** with Python 3.12 (the CI version) in a venv:
  - `years_required` on the 3 failing snippets now returns None, and real asks (10+, 7, "over 5", 3–5) are still caught.
  - `wk_probe` trips on the first 429 and short-circuits after that.
  - `detect()` returns the new note under a mocked 429.
  - The package imports cleanly.
  - A full refresh was not run, because it takes 60–120 min in CI. Excluded rows update on the next `python -m radar score` or refresh.
- **Remains.** Everything from P2 on, per §4. The master doc itself isn't committed yet, so § references point outside the repo. Open questions are in §8.
