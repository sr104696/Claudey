# Project: JD-to-investing job radar

This project finds, verifies and scores open job postings for one candidate, then writes them into the list format in `seeds/current_list.md`. Read this whole file before doing anything.

## The candidate (describe him accurately and never inflate)

- Seth ("Rosey") Rosenberg. Based in NYC. Accepts NYC in-person or hybrid, or US-remote. Other locations go in a separate "outside location" section, not the main tables.
- Penn Law JD 2022, magna cum laude. Dean's Prize (top 1L grades). Law Review senior editor.
- Tenth Circuit clerk (one year). Bankruptcy court term clerk, D.N.J. (three months only; treat it as exposure, not expertise).
- About 20 months at BigLaw: Quinn Emanuel (litigation and investigations) and Kirkland (litigation plus regulatory advisory).
- Morgan Stanley since Dec. 2025, Associate in CPGR, second-line credit risk. He administers credit approval authorities, applies credit policy to amendments and limit increases, supports OCC, Fed, SEC and FINRA exams, drafts credit-risk reporting and supports credit-risk review of AI-related transactions. This is not legal advice, underwriting, investing or trading.
- Admitted in NY only (2023). About 4 years post-JD. CFA Level I in progress. Limited modeling, statistics, programming or trading.
- Already in his pipeline (track them, but don't report them as discoveries): Marqeta, Harvey, Hebbia, Norm AI, General Legal.

## What he wants

He wants work organized around investigating, reading primary sources, synthesizing and writing a decision-useful conclusion. The questions should be bounded, with advisory judgment as the output. He doesn't want court time, discovery, sales or quota, spreadsheet production, generic strategy or admin. He's optimizing for high pay and unusual work. Listed base pay must clear $150K, and $200K+ is preferred. Government seats are out (pay ceiling), and so are law-firm seats (lifestyle), whatever the salary.

## What the prior research found (use it to score postings)

These employers screen in two stages. Stage 1 is legal and analytic caliber, which he clears. Stage 2 is years in a named domain, usually 3 to 6+ years of restructuring, leveraged finance or payments regulation. Stage 2 is the binding constraint. The seat families that loosen it:

1. Litigation-finance underwriting (litigation is the domain; clerkships preferred).
2. Legal-AI research and build seats with base pay, not OTE.
3. Business-side regulatory risk seats at trading firms and banks (his Morgan Stanley work counts as the domain).
4. Employer-run finance academies that teach the finance (Point72 Academy, D. E. Shaw rotational, Bridgewater).
5. Embedded qualitative research at funds (Point72 Canvas, market intelligence).

Credit-intelligence legal analyst seats (Octus, 9fin, Debtwire, Fitch) are a real, well-paid niche, but they want 3 to 5+ years of restructuring practice or bankruptcy clerkships.

## Scoring rubric (score every posting you keep)

Hard excludes. These go to the "poor match" table with the reason:

- Pay is OTE, quota or variable-heavy.
- The role is pre-sales, account executive or demo-led.
- 6+ years of leveraged-finance or transactional practice is required.
- Python, statistics or systematic quant work is required.
- 5+ years of equity research, banking or buy-side experience is required.
- 10+ years of experience is required.
- The role is paralegal, document review or pure compliance operations.

Fit signals, each worth a point:

- JD required or preferred.
- "Clerkship preferred."
- Litigation experience accepted.
- "Financial services background" is a plus.
- Regulatory, legal or policy research for decisions.
- "No finance experience required," or the employer teaches the finance.
- Credit, distressed or bankruptcy subject matter.
- Fintech, crypto, AI or market-structure subject matter.
- Base pay of $150K or more.
- 2 to 5 years required (flexible floor).

Record as fields: `fit_score` (count of signals), `hard_exclude_reason` (or empty), `years_required`, `pay_min`, `pay_max`, `pay_type` (base / OTE / hourly / not listed), `jd_required` (Y/N/pref), `sales_attached` (Y/N).

**Every in-house legal seat is in scope**, long shots and off-interest practice areas included — he applies to those anyway. A posting with "counsel," "attorney," "lawyer" or "legal" in its title never goes to the poor-match table for its practice area or for missing years in a named domain; it only goes there for one of the hard excludes above, the law-firm/government/pay-floor rules, or genuinely not being an employee seat (contract platform, event, talent pool). Otherwise it's ranked on fit signals like everything else — fit is broad but realistic and fair, and a low score is itself the "long shot" signal, not a reason to exclude it. The years-in-domain floor is still a real screen for the seats in the five seat families above that aren't legal-titled at all (credit risk manager, investment analyst program, litigation-finance underwriting, and so on) — there, years in the named domain is the actual ask.

## Rules

- **Verify before listing.** Every row must come from a fetch you made in this run that shows the posting is open. Snippets and aggregator titles are leads, not evidence.
- **Link to the employer posting.** Prefer the employer's own ATS URL over aggregators, and only use an aggregator link when the employer page can't be reached. Mark those rows.
- **Pay is listed pay only.** Leave it blank rather than estimate. NY, CA, CO and WA pay-transparency laws mean most postings in those states show a range, so extract it.
- **Respect sites.** Honor robots.txt and each site's terms. Send at most 1 request per second per host, with a descriptive User-Agent that includes a contact email (ask the user which one). Don't scrape LinkedIn, Indeed or Glassdoor pages. Don't log in, bypass captchas or defeat paywalls. Public ATS JSON endpoints and official APIs are fine.
- **Never present the same choice twice.** Each run lists only postings no earlier run has shown (`data/seen.jsonl`, surface by surface: fit, outside, near-miss digest, poor), and never lists one he has applied to or dismissed (`data/decisions.csv`, written with `python -m radar decide`). The cumulative record stays in `out/all_positions.md` and `out/jobs.csv`; the `seen_before` and `decision` columns say why a row wasn't presented.
- **Never apply, submit forms or contact anyone.** This project only reads.
- **Put secrets in the environment.** API keys go in `.env` (git-ignored). Never hard-code them.
