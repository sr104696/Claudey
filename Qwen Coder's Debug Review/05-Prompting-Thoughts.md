# 05 — Prompting Thoughts: a question bank to provoke the next improvements

These are deliberately *not* answers. Each question targets something observable in this repo. Use them as
review prompts, Claude-Code session openers, or journaling seeds before the weekly `/refresh-jobs`.

## On failure polarity (the project's own best instinct, generalized)

1. `janestreet_jobs()` raises so an outage can't read as "all closed." **Where else does absence of data
   currently masquerade as a negative finding?** Enumerate every place that returns `[]`/`None` and ask: if
   this source died silently tomorrow, would any output change from "unknown" to "no"?
2. A board that returns valid-but-empty JSON after a format change is indistinguishable today from an
   employer who froze hiring. **What is the minimum evidence that a source is still *alive*, separate from
   the evidence that it has *jobs*?** (Probe an endpoint you know never empties?)
3. If the seen-ledger were corrupted right now, would the next run *look normal*? **Design for loud
   corruption:** what invariant, checked at startup, would make silent loss impossible? (Row count can only
   grow between runs? Every snapshot key must exist in ledger?)

## On the rubric as a living document

4. CLAUDE.md's rubric and `score.py` are two copies of one truth, kept in sync by hand. **Which sentence in
   CLAUDE.md is currently *not* enforced anywhere in code — and which rule in code is not stated in
   CLAUDE.md?** Diff the two documents; the delta is your next spec drift incident.
5. Every dated comment ("Seth, 2026-09-28") is a policy revision. **If each revision were a row in a rules
   changelog with the triggering misfire attached, could you replay history** — score last month's corpus
   under today's rules and vice versa? What would that diff tell you about whether recent changes netted an
   improvement or just moved errors around?
6. The judge subagent sees a batch excerpt; the regexes see different fields; Seth sees the markdown table.
   **Three observers, three views of one posting.** Which disagreements between them are most informative —
   and could the pipeline *route exactly those* rows to the cheapest resolving authority?
7. `override_regex_exclude` is a veto without a target. **What would break if vetoes had to name the rule id
   they suppress?** (Answer: almost nothing, and you'd gain per-rule false-positive rates. Why hasn't it
   happened? Because the flag was one line and ids require structure — is that trade still worth it at ~40
   rules?)
8. FIT_MIN=3: ten signals, unweighted. **"JD required" and "AI subject matter" are worth exactly each other.**
   Which signal, if removed, would change the fit list most? Have you ever measured that? Would Seth trust a
   weighted rubric more or less than a flat count he can recompute in his head?

## On the seen/identity model

9. Identity ladder: ATS id → URL → company+title+text-hash → company+title+pay. The loosest rung can mark a
   genuinely new req as seen. **What's the cost asymmetry between showing a duplicate (annoyance, one row)
   versus hiding a new opportunity (potentially *the* job)?** Should loose identities only *demote* a row to
   "probably seen — say 'new to me' to promote," instead of hiding it outright?
10. Decisions are keyed by whatever string Seth types into `decisions.csv`. **What happens when he renames a
    company informally ("MS" vs "Morgan Stanley") or the same role exists at two boards?** Is there a
    feedback loop where dismissed-but-reposted roles should resurface after N months (they often reopen —
    `out/recurrence.md` already knows this!)? Why doesn't recurrence data feed the seen policy?

## On operations & economics

11. A full sweep costs 60–120 min of GitHub runner time plus Claude judgment tokens weekly. **What's the
    marginal yield of the Common Crawl channel specifically** (the expensive one)? If `run_log` tracked
    presented-new-per-channel-month, would you cut it, and would anyone notice? Measure before deciding —
    can you compute it from existing snapshots tonight?
12. The rate limiter's promise is politeness. **Is 1 req/s actually necessary for public ATS JSON APIs,** or
    is it a blanket rule inherited from HTML scraping? Two-tier budgets (API endpoints: 5/s; HTML pages:
    1/s) would halve run time with no ethical difference. Who decides — and is that decision written down?
13. Cache TTL 20 h + weekly runs = cache never helps across runs but always helps within a re-run day.
    **What's the actual hit-rate split?** If intra-day reruns are rare, the cache mostly stores dead bytes
    and complicates Finding-5-style reasoning. Delete or justify with numbers.

## On the human in the loop

14. Outputs are markdown tables for a person. **What does Seth do with `out/jobs.csv`'s long tail — ever?**
    If not, why generate it? Conversely, the near-miss digest asks him 12 questions/week: **is question
    fatigue visible in decisions.csv timestamps?** Fewer, higher-value questions might improve both his week
    and your rubric.
15. His profile changed once mid-project (Morgan Stanley, Dec 2025). **Which rubric assumptions are
    personal-state-dependent** (credit-risk domain counts as experience; NYC hybrid acceptable) and how
    many files would need editing if he moved cities or switched domains? Could candidate profile be one
    data file consumed everywhere, instead of prose distributed through CLAUDE.md + regexes + prompts?
16. The system's north star is unstated: verified postings? new opportunities surfaced? applications sent?
    offers? **If you had to print one number on the dashboard that tells him the radar is working — which,
    computable from data already committed?** Then work backward: which module would change first if you
    optimized that number instead of "rows in out/open_positions.md"?

## On architecture crossroads (ask before the next big feature)

17. Eight subprocesses share state through files because threads can't share the gate cheaply. **At what
    point does one async event loop become simpler than the file-based inter-process coordination you have
    built?** Count the coordination mechanisms (lock files, .ts stamps, per-PID logs merged later, pending/
    results directories as queues): that count is your complexity tax, compounding per new channel.
18. SQLite mirrors JSONL mirrors CSVs mirror markdown. Four serializations of one domain. **Pick the one
    that is authoritative and derive the rest mechanically.** Which layer would you defend in a fire, and
    does the code actually treat it that way?
19. Judgment batches travel as committed files between Claude sessions — a message queue made of git.
    Clever and auditable. **What breaks first when throughput rises 10×** (more seeds, daily runs)? Is that
    future real? If yes, which component moves off files first?
20. Finally: the whole design assumes *one candidate, one rubric*. **What is the smallest refactor that
    would make it two-candidate-capable** (a friend's radar sharing channels but not scoring)? Not because
    you'll ship it — because doing the thought experiment exposes which logic is data (seeds, profile) vs.
    which is accidentally welded into code (regexes full of this candidate's biography: clerkship, JD,
    BigLaw tenure). That welding is where portability dies, and also where the rubric-as-data refactor (04 §A)
    pays twice.

---

### How to use this file

Pick 2–3 questions per weekly refresh session; write answers into `docs/DECISIONS.md` (which already exists
and is cited by phase2 SPECIAL entries — keep that habit). A DRAM-log culture ("Decision, Rationale,
Alternatives, Milestone") turns this question bank into institutional memory instead of guilt.
