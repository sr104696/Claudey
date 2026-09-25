# Penn alumni job boards — verified feasibility and the compliant pipeline

**Question**: can the radar (or Claude Code implementing on its behalf) connect to a Penn Law
or Penn alumni job board?

**Short answer**: No direct connection is possible. Both real Penn job boards are login-gated
**and** carry blanket robots.txt disallows — both facts verified live during this review. But
both platforms have a **saved-search email alert** feature, and email sent to the candidate is
his to parse. That gives a fully compliant semi-automated pipeline feeding the radar's existing
`import-leads` command.

---

## What exists (all verified live 2026-09-24)

### 1. Penn Carey Law → 12twenty (`law-upenn.12twenty.com`)

- Penn Law has fully migrated from Symplicity to **12twenty**. The law school's
  [alumni page](https://www.law.upenn.edu/careers/alumni/) (fetched) states: *"Alumni have
  access to 12twenty, our career management platform that features a jobs database updated
  daily with new opportunities."*
- Alumni access is **free**; alumni sign up with their Law School email ("Sign Up with LawKey"
  is students-only). OCS (`ocs@law.upenn.edu`) provisions alumni access.
- The employer page confirms listings are "**password-protected for Penn Carey Law student and
  alumni use only**" — no public view exists.
- `https://law-upenn.12twenty.com/robots.txt` (fetched): **`User-agent: * Disallow: /`** —
  blanket disallow. Even if login automation were in scope (it is not, per CLAUDE.md), crawling
  is explicitly prohibited.
- No RSS, no public API. **But** 12twenty has a documented **Saved Search Notifications**
  feature that emails new matching jobs automatically.

**Verdict: direct connection not feasible. Email alerts are the intended machine-readable
surface.**

### 2. University of Pennsylvania → Handshake (`upenn.joinhandshake.com`)

- [Penn Career Services' alumni page](https://careerservices.upenn.edu/channels/alumni/)
  (fetched): *"Alumni who graduated in 1997 or later automatically have an account"* (PennKey
  login); the alumni job board "lists thousands of positions posted for Penn alumni each year."
  Seth (JD 2022) is covered.
- robots.txt for both `upenn.joinhandshake.com` and `app.joinhandshake.com` (fetched): only
  login/register and share-preview paths allowed, then **`Disallow: /`** for everything else.
  Job search is disallowed and login-gated regardless (PennKey SSO + MFA).
- No public API or RSS. Handshake's only supported push mechanism is **saved-search job alerts
  by email**.
- `joinhandshake.com/find-jobs/` is a public login-free listing page, but it surfaces generic
  network jobs (hourly/entry-level), not Penn-filtered professional roles — marginal value.

**Verdict: same as 12twenty — email alerts only.**

### 3. Penn Alumni generally — nothing to connect to

- **QuakerNet is retired**, replaced by MyPenn (`mypenn.upenn.edu`) — an alumni
  directory/mentorship tool, **not a job board**, login-gated.
- Penn Alumni operates **no job board**; its career page delegates to Handshake and the
  ~45,000-member University of Pennsylvania LinkedIn group. LinkedIn scraping is out of scope
  and groups have no RSS/export — untappable except by hand.

---

## The compliant pipeline: email alerts → parse → `import-leads`

```
12twenty saved search ──┐
                        ├─► mailbox folder "job-alerts" ──► parse script ──► leads.jsonl ──► python -m radar import-leads ──► Phase 4 verify
Handshake saved search ─┘
```

Processing email sent to the candidate involves no scraping, no login automation, no robots
issues — it is exactly as compliant as the existing Claude-replayed web-search leads, and more
reliable.

### Setup (manual, one time, ~15 minutes)

1. **12twenty**: activate the alumni account per the
   [alumni page](https://www.law.upenn.edu/careers/alumni/) (email OCS if needed). Create saved
   searches with email notifications on, e.g.: location "New York" + "Remote", experience
   2–6 years, functions Legal/Compliance. Daily cadence.
2. **Handshake**: log in with PennKey; create saved searches (job function: Legal; location:
   NYC; full-time) with email alerts on. Volume is high — keep filters tight.
3. **Mailbox**: a filter/folder (e.g., `job-alerts`) collecting both senders.

### What Claude Code can implement (no credentials ever touch the tool)

A new command, `python -m radar import-alumni <mbox-or-folder>`, that:

1. Reads an **exported** mailbox folder (`.mbox`/`.eml` export — the user runs the export;
   the tool never connects to the mail server or stores credentials).
2. Parses 12twenty and Handshake alert emails (both use consistent templates: job title,
   employer, location, and a tracking/redirect link per posting).
3. Resolves redirect links to their destination URLs **without** following them into gated
   pages — emit `Lead`s with `source="alumni:12twenty"` / `"alumni:handshake"`.
4. Hands leads to the existing Phase 4 flow: most postings at this level also exist on the
   employer's public ATS, where they verify normally.
5. Postings that exist **only** inside the portal go to a separate `requires_user_review`
   table in the output (marked unverifiable, link to portal) — never into the fit/poor tables,
   preserving the "verify before listing" rule.

Guardrails to bake in:

- No PennKey, passwords, cookies, MFA codes, or browser profiles anywhere near the tool —
  add a test that rejects input files containing `Set-Cookie`/credential-shaped content.
- Raw email exports stay git-ignored (`data/alumni_inbox/`); only parsed lead rows (title,
  employer, URL) persist, matching how `data/leads.jsonl` is already handled.
- Portal-only postings are labeled as such; the radar never attempts to fetch the gated URL.

### Expected value

12twenty is the highest-value alumni channel: lateral legal roles posted *specifically for
Penn Law alumni*, updated daily, low noise. Handshake is broader and noisier — worth it only
with tight filters. A monthly manual login to both (10 minutes) catches anything the alert
filters miss and keeps the accounts active.

## Bottom line

No Penn service is "amenable to connection" in the API/feed sense — both say no in robots.txt,
verified. The email-alert bridge gets ~90% of the value with zero rule violations, and Claude
Code can implement the parser end-to-end. Task spec is in
[CLAUDE-CODE-PLAN.md](CLAUDE-CODE-PLAN.md), Task 7.
