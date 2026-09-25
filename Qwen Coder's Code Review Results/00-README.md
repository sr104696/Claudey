# Qwen Coder's Code Review Results

Code review of the **JD-to-investing job radar** (`/workspace`), delivered 2026-09-25, focused on:
sweep comprehensiveness, tailored/niche sources (aistartupjobs.com, r/legaltech,
legaloperationsjobboard.com), the aggregation/feed layer other job boards use, and connecting
Claude Code to Penn Law / Penn Grad alumni job boards.

## Contents

| Doc | What it is |
|---|---|
| [01-code-review.md](01-code-review.md) | Full review: strengths, then prioritized gaps (A1–A7 sweep, B scoring, C alumni summary) with a ranked action table |
| [02-niche-sources-and-aggregations.md](02-niche-sources-and-aggregations.md) | Catalog of niche/tailored sources and feeds, verdict per source for this profile, drop-in expanded `search_queries.csv` rows, keyword additions, and a "do not add" list |
| [03-alumni-job-board-integration.md](03-alumni-job-board-integration.md) | Feasibility study + ToS-safe design for Penn Law OCS / Penn Alumni connectivity: inbox-bridge architecture, `import-alumni`, `/alumni-map`, guardrails |
| [04-claude-code-implementation-plan.md](04-claude-code-implementation-plan.md) | Paste-ready ordered task brief (Tasks 0–8) with acceptance criteria for Claude Code to implement everything above |

## Headline takeaways

1. **Biggest recall gap:** the Common Crawl sweep only covers Greenhouse/Lever/Ashby; Workday, SmartRecruiters (via JSON-LD, its API is robots-blocked), Breezy, JazzHR and Rippling boards are invisible today. Fix in Task 3.
2. **The "feeds other boards use" answer:** add an RSS/Atom/JSON feed channel backed by a `seeds/feeds.csv` registry — including aistartupjobs.com's feed, HN who-is-hiring RSS, and per-board ATS JSON endpoints auto-registered from the discovered-board list. This mirrors how commercial aggregators scale, using only public documented endpoints. Task 2.
3. **r/legaltech & legal-ops boards:** Reddit's public `.json` endpoints deserve a first-class channel (stale posts are harmless because Phase 4 re-verifies every lead); legaloperationsjobboard.com is cheap to poll but expect many poor-match rows — the rubric already handles that. Task 4.
4. **Alumni boards:** Penn Law's OCS portal and Penn Alumni listings are login-gated with no public API, so scripted connection violates both project rules and platform ToS. The compliant, genuinely useful design is a user-export **inbox bridge** (`data/alumni_inbox/` → `python -m radar import-alumni` → verified leads) plus a `/alumni-map` research command for the referral network — the part of alumni value no scraper can reach anyway. Tasks 6–7, doc 03.
5. **Precision machinery is already good** (rubric, hard excludes, judgment caching, politeness client). No changes recommended there beyond small regression guards.
