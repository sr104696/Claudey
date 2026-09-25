# Connecting Claude Code to Penn Law / Penn Grad alumni job boards — feasibility & design

**Question:** "…maybe a way for Claude Code implementing the suggestions to connect to an alumni job
board — to what extent Penn Law or Penn grad alums have such a service amenable to such connection."

## 1. What Penn actually offers (as of this writing — verify before building)

| Service | Who runs it | Machine-readability | Amenable to this project? |
|---|---|---|---|
| **Penn Law Career Studio / OCS job portal** (classroom-published jobs, employer info sessions, alumni job referrals). Historically on **Symplicity Classroom** and later **12Twenty/Handshake-style platforms**; Penn Law's public page is `pennlaw.edu` → "Current Students & Graduates → Career Studio." | Penn Law OCS | Login-gated; these platforms expose **no public API** and their ToS prohibit automated access with shared credentials. Some instances offer user-facing **email digests** and **ICS/RSS-like subscription links tied to the user's session token**. | **Partially — via user-assisted export only** (see §3, Mode A/B). Never via stored-credential scraping. |
| **Penn Alumni Association (Penn Alumni)** — job board historically at `pennalumni.org` (powered in past eras by YourCrew / Wildfire-style alum networks; current status varies) | Penn Alumni | Mixed: some incarnations had browsable listings behind alumni login; no documented public API. | Same pattern as above: user-assisted export if behind login; direct polite poll *only* if a listing page is genuinely public and robots-permits. |
| **Penn GAL / Penn Grad networking groups, Penn Law Networking Group (Facebook), Wharton/alumni cross-postings** | volunteer-run | Closed platforms (Facebook, LinkedIn groups) — ToS forbid scraping, CLAUDE.md forbids it too. | **No automated access.** Value route = the `/alumni-map` research command (§4) + user-forwarded posts into the inbox. |
| **Penn Law "Job Notices" email list / OCS graduate notifications** | OCS mailing lists | Email is perfect machine-readable input once the user forwards/dumps it. | **Best first target.** Zero ToS risk (it's mail addressed to him). |
| **Public mirrors**: employers that hire Penn-law-rep talent post on public ATS boards anyway — the radar already sweeps those. The *unique* alumni value is (a) jobs posted only to the school portal, (b) referral paths. | — | — | Covered by §3(a) + §4. |

**Bottom line:** Penn's alumni/graduate career infrastructure exists and does carry exclusive
listings, but every surface we could confirm is login-gated with no official API. So the honest,
ToS-compliant architecture is an **"inbox bridge"**: anything the *user's own account* can export
(CSV downloads, emailed digests, copy-paste) becomes structured input; the radar then applies its
existing superpower — resolve each listing to the employer's public ATS page and verify there — so
the output obeys the same "verify before listing" rule as everything else.

## 2. Hard guardrails (must be encoded in CLAUDE.md alongside the code)

1. **No credential storage or scripted logins.** The radar never holds his Penn/Gmail password, never replays session cookies from a browser profile, never solves MFA. (This also rules out the tempting Playwright-login approach — one ToS violation away from account termination, and squarely against the project's "don't log in, bypass captchas or defeat paywalls" rule.)
2. **LinkedIn/Indeed/Glassdoor remain off-limits**, including alumni directories rendered through them.
3. User-exported data is **local-only**: `data/alumni_inbox/` joins `.gitignore` (it contains his personal mailbox artifacts and possibly PII of recruiters/alumni). Only *derived, verified public postings* flow into `out/`.
4. **Never auto-contact.** Consistent with CLAUDE.md ("this project only reads"), `/alumni-map` produces research briefs the human acts on; it must not send emails/InMails/forms.

## 3. Proposed implementation — `radar/alumni.py` + `python -m radar import-alumni`

### Mode A — Email-digest ingestion (recommended first build)
Penn OCS/alumni digests arrive as HTML email. Pipeline:

1. User drops `.eml`/`.html`/`.txt` files (or a forwarded PDF) into `data/alumni_inbox/` (manual IMAP fetch script optional *later*, run under his own app-password only if he explicitly approves amending CLAUDE.md — do not build unprompted).
2. `import-alumni` parses each file: extract candidate job blocks (title, employer, description snippet, any URL) using `textutil.html_to_text` + link scan (`ATS_URL` regex from `discover/common.py`, widened to any http(s) link when source is trusted-mail).
3. Emit `Lead(source="alumni:pennlaw_ocs", …)` rows → existing Phase 4 verifies each on the employer board. Listings that are portal-internal only (no external URL, apply-via-school-portal) go to a separate table `out/alumni_only_<date>.md` — visible to him, clearly marked unverified, since the project can't confirm they're still open.
4. Tag scored rows with `source_bucket=alumni` so the diff/report shows what the alumni channel uniquely contributed each week (measures whether the bridge earns its keep).

### Mode B — CSV export ingestion
Most campus platforms (Symplicity/12Twenty/Handshake family) let a logged-in user export search results or at least select-all-copy a listing table. Accept `data/alumni_inbox/*.csv` with fuzzy header mapping (`job title/title`, `employer/company`, `posted`, `link/url/details`). Same lead emission as Mode A. This mode is trivially small (~60 lines) and completely sidesteps platform ToS because *the human performs the export*.

### CLI wiring (mirrors the existing `import-leads` pattern exactly)
```
python -m radar import-alumni [DIR]   # default data/alumni_inbox/, --dry-run supported
```
Add `"alumni"` to `__main__.py` subcommands; record via `record_channel("import:alumni", …)` so it appears in `out/run_log.md`; add step **1b** to `.claude/commands/refresh-jobs.md`: "If `data/alumni_inbox/` has new files, run `python -m radar import-alumni` before refresh."

## 4. `/alumni-map` — the higher-value alumni feature (Claude Code native)

Alumni boards' real asset isn't listings; it's people who took this exact jump. A slash command that works from a curated, hand-entered seed file:

- `seeds/alumni_contacts.csv` — `name, company, role, grad_year, school, how_met, status, last_touch` (user-maintained; no scraped data ever enters this file).
- `.claude/commands/alumni-map.md` instructs Claude Code to: WebSearch **public** sources (firm bios, panel rosters, published articles, court/SEC filings mentioning the person professionally) for litigation-finance underwriting teams, legal-AI research leads, fund reg-risk heads → identify likely-Penn-affinity people → draft a *research brief* per target: what they do, which seat families their org staffs, recent hiring signals the radar already found there, and a suggested outreach angle **written for the user to send himself**. Output to `out/alumni_map_<date>.md`. Never sends anything.

This keeps 100% of the automation on the compliant side (public-page research is what the whole repo already does) while capturing the network effect the question was really after.

## 5. Stretch option (explicitly deferred, needs user sign-off)

A **personal-email IMAP reader** (`RADAR_GMAIL_APP_PASSWORD`) that auto-files OCS digest emails into `alumni_inbox/` is technically easy and arguably within spirit (mail addressed to him; Google allows app-password IMAP; no third-party ToS breached). But it touches credentials and inbox privacy, so CLAUDE.md's "never log in" rule should be amended *by the user* first. Marked `[~]` in the plan doc, not built by default.

## 6. Verification checklist before any alumni code ships

- [ ] Confirm current Penn Law OCS platform vendor and whether grad access + export exist (user logs in himself and reports; or checks `pennlaw.edu` career pages via WebSearch — public page reading is fine).
- [ ] Check `robots.txt` of any genuinely-public alumni listing pages (e.g., an open Penn Alumni job index) before polling; blocked ⇒ drop to Mode A/B only.
- [ ] Add `data/alumni_inbox/` to `.gitignore` **before** the first real file lands.
- [ ] Dry-run parse against one sample digest (redact his email address from fixtures).
