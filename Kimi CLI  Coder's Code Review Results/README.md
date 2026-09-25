# Kimi CLI Coder's Code Review Results

Independent review of the job radar by Kimi CLI (third pass, after Qwen Coder's and Codex's
reviews — see their folders in this repo). Read-only review: **no files in `radar/` were modified.**
The only non-document change on this branch is restoring `.gitignore`, which Qwen's merged PR #1
accidentally emptied (see "Repo hygiene" below).

## How this review differs from the prior two

| | Qwen Coder | Codex | This review (Kimi CLI) |
|---|---|---|---|
| Emphasis | Architecture gaps (CC patterns, no feed channel) | Coverage measurability + provenance | **Empirically verified bugs that silently lose jobs**, plus live-tested new sources |
| Method | Code reading | Code reading + design analysis | Code reading + **live HTTP verification** of every headline claim (Muse API, HireLegalOps feed, Reddit robots.txt, legal-tech ATS endpoints — all fetched during the review) |
| New sources | Proposed feed channel + query rows | Proposed niche adapters | Adds sources neither found: **HireLegalOps `jobs.json`** (purpose-built machine feed), **direct ATS endpoints of 6 legal-tech employers** (verified live), **Arbeitnow** keyless API |
| r/legaltech verdict | "feasible via public .json" | not covered | **Correction: not feasible** — Reddit's robots.txt is now a blanket `Disallow: /` and anonymous `.json` returns 403 (both verified live) |
| Alumni | Inbox-bridge design | User export/import | Same conclusion, but with **verified robots.txt evidence** for both Penn platforms and concrete saved-search/email-alert setup steps |

## Documents

| File | Contents |
|---|---|
| [SWEEP-KILLERS.md](SWEEP-KILLERS.md) | The 8 bugs that silently lose jobs every run, ranked. Start here. |
| [FULL-BUG-LIST.md](FULL-BUG-LIST.md) | All ~40 findings with file:line, severity, and concrete fixes. |
| [NEW-SOURCES.md](NEW-SOURCES.md) | Niche/tailored sources, each live-tested: verdicts, endpoints, integration sketches. |
| [ALUMNI-PIPELINE.md](ALUMNI-PIPELINE.md) | Penn Law 12twenty + Penn Handshake: verified feasibility and the compliant email-alert pipeline. |
| [CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md) | Ordered, paste-ready implementation tasks for a Claude Code session, with acceptance criteria. |

## Headline takeaways

1. **The sweep loses jobs every run to at least 8 distinct silent-failure bugs** — dead Muse
   category names (~4,500 listings invisible, verified live), Lever boards truncated at 100
   (~1,000 already-discovered postings dropped), crashed discovery channels leaving no trace,
   a dead regex that disables the "legal engineer" recurrence family, and more. These are in
   SWEEP-KILLERS.md; most fixes are under 10 lines.
2. **The best new source costs almost nothing**: `https://hirelegalops.com/jobs.json` is a
   purpose-built legal-ops JSON feed whose robots.txt *explicitly welcomes automated reading*
   (verified: HTTP 200, 125 KB structured JSON). Neither prior review found it.
3. **Six legal-tech employers' own ATS endpoints are live and keyless right now** (Harvey,
   Ironclad, Relativity, Everlaw, DISCO, Clio — all fetched successfully during this review)
   and can be added to `seeds/companies.csv` today.
4. **r/legaltech is off the table** — Reddit blanket-disallows all crawlers in robots.txt and
   403s anonymous JSON. This corrects the prior review's suggestion.
5. **No Penn alumni board can be connected directly** — both Penn Carey Law's 12twenty and
   Penn's Handshake are login-gated *and* carry blanket robots.txt disallows (both verified).
   The compliant path is saved-search **email alerts → parse → `import-leads`**, detailed in
   ALUMNI-PIPELINE.md.

## Repo hygiene: `.gitignore` was gutted by PR #1

Commit `e78afb3` (Qwen's review) emptied `.gitignore` — a side effect Qwen's own log flags as
unintended. Nothing sensitive has been committed yet (checked: no `.sqlite`, `.env`, cache, or
`.pyc` files are tracked), but the next commit from a working directory could add them.
**This branch restores `.gitignore` from `510a37f`.** Recommend merging this promptly.

## Verification standard used in this review

Every claim marked **(verified live)** was fetched over HTTP during this review session on
2026-09-24, using the project's own polite user-agent. Claims that could not be confirmed are
marked **(unverified)**. Bug findings cite `file:line` against commit `f492964` (current main).
