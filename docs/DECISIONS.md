# Decisions

Standing rulings for the radar: what Seth decided, which sources are in or out and why, and what was fixed
after review. Check here before re-proposing anything. The full review and suggestion folders, `PLAN.md` and
`docs/REVIEW_RESPONSE.md` were removed on 2026-09-28; they are in git history at commit `a673b7b`.

## Seth's rulings

| Date | Ruling | Where it lives |
|---|---|---|
| 2026-09-24 | User-Agent contact: `sethnrosenberg@gmail.com` (`RADAR_CONTACT_EMAIL`) | `.github/workflows/refresh.yml`, `.env` |
| 2026-09-24 | Common Crawl's index server is robots-exempted (it publishes the CDX API for programs) | `RADAR_ROBOTS_EXEMPT_HOSTS` |
| 2026-09-24 | No schedule; runs are started by hand (Actions tab or `/refresh-jobs`) | workflow has no `schedule:` |
| 2026-09-25 | Listed base pay must clear $150K; $200K+ preferred. No job at $100K. | `score.PAY_FLOOR`, `output.fit_order` |
| 2026-09-25 | Government seats are out (pay ceiling). FINRA and the NY Fed are left to the pay floor. | `score.is_government` |
| 2026-09-25 | Law-firm seats are out (lifestyle), whatever the salary. Non-billable knowledge/practice-support seats stay out of the fit table but go to the near-miss digest so Seth can rule on real examples. | `score.is_law_firm`, `output.near_misses` |
| 2026-09-25 | One fit table, best first: ★ seat families, then domain floor met, then pay tier, then signals, then newest | `output.fit_order` |
| 2026-09-25 | Seth reviews a near-miss digest (reply **fit** or **right call** per row) | `out/near_miss_<date>.md` |
| 2026-09-25 | Nothing further is required of Seth: Google Alerts, recruiter subscriptions and a Brave Search key are parked until he opts in | `docs/ROADMAP.md` |
| 2026-09-27 | Jersey City and Hoboken (PATH) count as NYC, labeled "commutable". Stamford, Greenwich, Westport, Rye and White Plains stay outside but sort first, labeled "Metro-North ~1 hr, hybrid only". | `extract.py`, `output.py` |
| 2026-09-27 | Judgments are made from committed batch files (no network needed) and applied at the start of the next run | workflow, `pipeline.py` |
| 2026-10-01 | Each run presents only postings no earlier run has shown, and never ones he applied to or dismissed. Ledger: `data/seen.jsonl` (per surface: a near miss that becomes a fit is new again). Decisions: `data/decisions.csv` via `python -m radar decide`. Full history stays in `out/all_positions.md` and `jobs.csv`. | `radar/seen.py`, `output.write` |
| 2026-09-28 | Every in-house legal seat is in scope, long shots and off-interest practice areas included -- he applies to those anyway. A counsel/attorney/lawyer/legal-titled seat is never poor-matched for practice area or an unmet domain-years floor; rank it on fit signals instead. The domain-years floor still screens the five non-legal seat families. | `score.score` (`inhouse_legal` gate) |

## Sources: in, out, and why

Robots and terms were read from the live files on the dates shown. Re-check before building anything on "hold".

| Source | Status | Evidence |
|---|---|---|
| Arbeitnow API | **In** (feeds.csv) | robots.txt allows all except `/*?__hstc` (2026-09-27). Mostly European listings: 0 of 325 kept on its first run (2026-09-28); the yield rule retires it if that holds. |
| Himalayas `/jobs/api` | **In** | robots.txt allows `/`; only `?page=` variants disallowed (2026-09-27) |
| Jobicy `/api/v2/remote-jobs` | **In** | `/job-listings/`, `/search/` and `/feed` are disallowed, `/api/` is not; `Content-Signal: ai-input=yes` (2026-09-27) |
| findwork.dev API | **Out for now** | robots.txt allows all (2026-09-27), but the API returned HTTP 401 on 2026-09-28: it needs a key. Re-add with a key in `.env` if wanted. |
| HireLegalOps `jobs.json` | **In** | robots.txt welcomes the feed (Kimi review, live) |
| eFinancialCareers | **Hold** | `/search`, `/v1`, `/v3` disallowed; job sitemaps allowed; `crawl-delay: 10`. Terms of use not yet read. |
| PRMIA | **Hold** | robots.txt allows; the job board's address is unknown |
| ACC job board (`jobs.acc.com`) | **Out** | TLS too old for a modern client (2026-09-27); its XML feeds were already robots-disallowed |
| GARP careers (`careers.garp.org`) | **Out** | domain does not resolve (2026-09-27) |
| Philanthropy News Digest jobs | **Out** | site now redirects to candid.org/blogs; the jobs feed is gone |
| HigherEdJobs | **Out** | university counsel offices sit mostly under the pay floor |
| LinkedIn, Indeed, Glassdoor | **Out** | CLAUDE.md. This includes JSearch and any API that resells their listings. |
| Reddit r/legaltech | **Out** | `robots.txt` is `Disallow: /`; anonymous JSON returns 403 |
| aistartupjobs.com | **Out** | Cloudflare challenge; web-search leads only |
| Penn Law 12twenty / Handshake / Symplicity | **Out** | login-gated and robots-disallowed; the email-alert bridge (`import-inbox`) is the route |
| Craigslist RSS | **Out** | terms prohibit automated access |
| GoInhouse, SimplyHired, Talent.com, Monster, ZipRecruiter, FlexJobs | **Out** | rejected sources, bot walls or paywalls |
| X/Twitter, Telegram, SearXNG, DuckDuckGo HTML, r.jina.ai readers | **Out** | API gone or terms-gray |
| User-Agent rotation, CORS proxies, "blocked-site workarounds", rotating queries "to avoid detection" | **Out** | evasion; conflicts with the contact-UA rule and robots.txt |
| Government job portals and regulator career pages (USAJobs, statejobs, DFS, Fed districts, OCC…) | **Out as targets** | government seats are out; the existing public-sector channel stays for FINRA and the NY Fed |

## Employers checked by hand (2026-09-27)

| Employer | Finding | Registry |
|---|---|---|
| Parabellum Capital | No careers page at all; hires via network and recruiters | team page on weekly change watch |
| Elliott Management | No public job board | web-search queries only |
| Litigation Capital Management | No US office (Sydney, Melbourne, Brisbane, London, Singapore) | removed |
| Longford Capital | TLS certificate expired in September 2026 | retried each run, never bypassed |
| Hunterbrook | Recruits reporters by email only | weekly change watch |
| LSTA | Runs a loan-market job board for member firms | weekly change watch; postings imported as leads |
| MLex | Part of LexisNexis (RELX): Workday tenant `relx` | Workday |
| DTCC | Oracle Cloud HCM site `CX_1` | Oracle adapter on the roadmap |
| Millennium | Eightfold, with Legal, Compliance and Risk departments | Eightfold adapter on the roadmap |
| Moody's | Radancy-style careers site | sitemap route on the roadmap |
| Eurasia Group | Rippling | Rippling adapter on the roadmap |
| The Capitol Forum, ISDA, Balyasny | Own CMS / Salesforce portals | weekly change watch |

Short names collide: searches for "Parabellum", "LCM", "Longford" and "GLS" first returned a cybersecurity firm,
a children's museum, a machinery maker and a parcel carrier. Board guessing for short or generic names therefore
requires the board's name to match the registry company (`phase2.detect`).

## Review findings

The September reviews (Codex, Kimi, Qwen, Vibe, GitHub CLI, and two later forensic reviews) were checked against
the code before anything changed. The pattern behind most real bugs: **a failure that looks exactly like "no jobs
today"** (a renamed API category returning 200 with zero results, an unreachable robots.txt, a crashed channel, an
empty sitemap, a 429 logged as "no board"). The silence alarm (`radar/health.py`, `data/source_health.csv`, the
"Silence check" at the top of `out/run_log.md`) exists for that pattern.

Declined, with evidence:

| Suggestion | Why not |
|---|---|
| Boost scores for niche sources | Where a lead came from shouldn't change how well the job fits |
| Company-size 100–500 filter | Not in CLAUDE.md; conflicts with fits at Morgan Stanley, Citi, Blackstone, Mastercard |
| Thesis/counsel two-table split | Seth chose one ranked table |
| Regulator career-page mining | Government is out |
| GitHub/PublicWWW/urlscan token miners, CT logs, DNS brute force | Feed the generic end of the funnel; DNS brute force reads as reconnaissance |
| Wikidata / NYS Open Data bulk seeding | Detection already fails on a third of the registry; revisit when that rate falls |
| Chambers / Legal 500 / CourtListener firm seeding | Seeds law firms, which are out |

Lever pagination: the Kimi review said boards truncate at 100; a later review showed `veeva` returning 916 jobs
in one call. The adapter pages anyway and stops when a page adds nothing, so it's correct either way at the cost
of one extra request per board of 100+ jobs.
