## What

Adds a new docs-only folder **`new-qwen-suggestions-expansion-ideas/`** — a second-wave idea set for pulling **more roles, more postings, and whole industries not yet on the radar**, including tangential/orthogonal sectors that look unrelated but share the same "investigate → synthesize → decide → write" job DNA, plus new crawling/scraping/feed/keyless-API channels.

Complementary to (not a repeat of) `Qwen Coder's Code Review Results/`, which already covered Common Crawl ATS gaps, an RSS feeds registry, Reddit `.json`, legal-ops boards, and the alumni inbox bridge.

## Contents

| File | What it is |
|---|---|
| `00-README.md` | Index + 10 headline ideas |
| `01-tangential-sector-map.md` | 11 adjacent/orthogonal sectors (disputes analytics, country-risk/integrity consulting, KM & competitive-intelligence desks, insurance coverage, sanctions/trade, arbitration, forecasting/evals, legal media, deep public sector…) with named firm pools and drop-in search-query rows |
| `02-new-channels-crawl-scrape-feeds.md` | Sitemap/feed harvesting across ~12 ATS platforms, CDX first-seen recency, Wayback diffing, HN Algolia, keyless aggregator API table, FINRA/ALFA/VC/awesome-list firm seeders — with explicit rate-limit/CORS/robots/ToS guardrails |
| `03-more-of-the-same-faster.md` | Query-matrix expansion (14 → ~140 rows), board-token compounding, deeper per-board pulls, `datePosted`/RSS freshness filters, ~18 new title-family regexes, near-miss bucket, judgment-cache reuse, run cadence |
| `04-priority-and-sketches.md` | Ranked 15-action table (effort/lift) + paste-ready implementation stubs |

## Rules compliance

Docs only — no code, seeds, or data touched. All proposals respect project rules: robots.txt honored, ≤1 req/s/host, no LinkedIn/Indeed/Glassdoor scraping, no login/captcha/paywall bypass, verify-before-list, keys via `.env`. Includes the verified SmartRecruiters correction (its API host is robots-disallowed).

## Note on branch provenance

This branch was rebuilt cleanly on top of current `origin/main` (`36911ab`) so the PR shows **only the 5 new files (565 insertions)** — the sandbox checkout's base predated several merged PRs, which would otherwise have made this diff appear to revert them. The previous PR attempt for this content was #4 (see `out/run_log.md`).
