# 03 — Code Review (module by module)

Format: **Keep** = what's well done and should survive future refactors. **Watch** = fragility worth
tracking. **Change** = concrete review comments a PR would carry.

---

## `radar/http.py` (488 lines) — the crown jewel, with two cracks

**Keep.** A single polite client for the whole system is the right architecture. The details show
incident-driven maturity: hand-followed redirects so every hop gets a robots check; challenge-page sniffing
that *skips* rather than bypasses; per-PID JSONL request logs joined later by `runlog`; negative caching
only for robots.txt "missing" answers; contextvar-based channel tagging that survives the subprocess model.

**Watch.**
- The file mixes five responsibilities behind one class: gating, retry policy, robots policy, cache
  serialization, log shaping. Each is independently interesting and independently testable — they'd each be
  ~100 clean lines alone. The current shape works but slows reasoning about interactions (e.g., Finding 5:
  gate staleness vs. crawl-delay lives three abstractions apart from where delay is computed).
- `_blocked_hosts` is per-process. Two subagent processes can disagree on whether a host is walled; the
  second pays for the discovery again. Cheap fix: persist blocked hosts in `data/runs/<run>/blocked.json`.
- Cache write is not atomic (`_cache_put.write_text`) — concurrent readers of the same key across PIDs can
  hit a half-written JSON → `_cache_get` returns None → extra fetch. Benign given TTL semantics, but use
  temp+replace here too since it costs nothing.

**Change (PR comments).**
1. Stale-lock threshold must scale with the enforced delay (Finding 5); prefer `flock`.
2. Retry-After HTTP-date parsing (nit #10).
3. Strip URL userinfo before logging (Finding 9).
4. `Result.text` charset handling: `charset=` extraction splits on `;` but doesn't lowercase/trim the label
   before `decode` — most servers are tidy; add `.strip().lower()` and a quote-strip for robustness.
5. `probe_client()` uses the shared cache dir with `max_attempts=1` — a probe 404 pollutes nothing (good,
   NEGATIVE_STATUSES), but a probe *success* caches full bodies under the same keys as real clients. Fine,
   just document that probes warm the real cache (it's a feature — say so).

---

## `radar/score.py` (354 lines) — brilliant heuristics, accreting structure debt

**Keep.** The rubric faithfully encodes CLAUDE.md, including subtle clauses ("in-house legal seats are never
poor-matched for practice area"). Comments carry dated provenance ("Seth, 2026-09-28") — this is how
regrettable-but-necessary patches stay legible. `SETTLED_REASONS` keeping law-firm rows out of the near-miss
digest while letting non-billable KM seats through shows product thinking, not just code thinking.

**Watch.**
- See Finding 6: rule interaction risk now exceeds rule complexity risk. The function's control flow
  encodes precedence implicitly (hard excludes → judgment override → poor rules → bucket). When the next
  carveout lands, will it fire before or after `override_regex_exclude`? Nothing says.
- `judgment_for(p)` silently prefers a direct-key judgment over a role-key one; when both exist and
  disagree (repost with edited text but same key?) precedence is invisible in output. Emit which source was
  used into `jobs.csv` (`judgment_via=key|role|none`).
- Magic numbers scattered: `FIT_MIN=3`, `150_000` appears twice (signal + floor), `>= 6` years thresholds in
  three places. One constants block, or better, the rubric-as-data table (see 04).

**Change.**
1. Extract the pay-normalization mutation (lines 221-225) into `extract.normalize_pay(p) -> p` called by
   phase4 before scoring. Score becomes pure. Enables golden replay.
2. Convert RX/EXCL dicts to a `Rule` registry with ids; keep messages templated so `rule_id` travels to
   CSV columns. Sample implementation provided (`code_samples/rule_registry.py`).
3. Wrap the `json.loads` loop in `judgments()` with the same torn-line tolerance as `seen._read_jsonl`.
4. Add `invalidate_judgments()` and call it from `phase4.apply_judgments()`.

---

## `radar/extract.py` (388 lines) — regex NLP at its pragmatic best

**Keep.** The `_ORG_COMMISSION` list showing why "Securities and Exchange Commission" isn't commission pay —
this is the right way to encode domain knowledge: specific, commented, tested. Range-suffix logic for
"$150-200K", `$X million AUM` rejection via `_SCALE_AFTER`, hourly-vs-annual sanity bands: all sound.

**Watch.**
- Scoring candidates by proximity to pay-context words is good; ties broken by iteration order means two
  equally-scored ranges pick whichever appears first in the doc. Prefer NYC tier explicitly (you already
  special-case it) — make the tie-break deterministic on "NYC tier wins, else widest range wins" and comment
  why (pay-transparency postings often list multiple locations' tiers; picking the wrong one moves rows
  across the $150K floor).
- `_to_num` treats bare `$1.5` with no suffix as 1.5 — a "$1.5M" written as "$1.5 M" (space + capital M
  outside the regex) silently yields 1.5 dollars. Guard: if value < 1000 and period==year → treat as suspect
  and drop candidate (your 20k lower bound mostly does this; verify the extras path doesn't leak it).

**Change.** Unit-test the multi-tier example directly (a real Greenhouse JSON-LD salary array with 3 city
tiers) — I didn't find one; the behavior is load-bearing for pay-floor decisions.

---

## `radar/pipeline.py` / `phase1/2/4` — orchestration is honest about partial failure

**Keep.** "Always leaves `out/run_log.md` behind; exits non-zero after writing outputs" is exactly the right
contract for an unattended weekly job. Silence-check-first run logs, per-channel exit codes feeding
`health.record`, `ChannelFailure` distinguishing crash(≠124) from timeout(124): mature ops thinking.

**Watch.**
- Finding 4 (deadline starvation) is the headline bug here.
- `finish()` re-derives channel stats by string-matching source prefixes against channel names
  (`src.startswith(c.split(":")[-1])`) — brittle join logic living in the orchestrator. Discovery channels
  should emit their own final counts to `data/runs/<run>/<channel>.stats.json` instead; parent just reads.
- `apply_committed_judgments()` runs, then `finish()` calls it again defensively ("no-op the second time").
  Make it idempotent *by construction* (track applied result filenames in a manifest) so the second call is
  provably free rather than conventionally skipped.

**Change.** Per-child deadlines; stats files; try/finally kill-all around spawn loop; move `closed_notes`'
`import re` and lazy imports to module top (they're there for cycle avoidance — see 04 for the layering fix
that removes the need).

---

## `radar/seen.py` — the product's soul; protect it like production money

**Keep.** Surface-hierarchy semantics (`SATISFIED_BY`: fit covers poor but near-miss doesn't cover fit) are
thoughtfully asymmetric, and the loose-identity ladder (ATS id → URL → name+text-hash → name+pay) matches
how reqs actually get reposted. Bootstrap-from-snapshots is a great recovery story.

**Watch.**
- Finding 2 (non-atomic save). Also `save()` rewrites the whole file every run — fine at current size
  (~thousands of lines), but append-only + periodic compaction would make crash-loss structurally
  impossible and git diffs smaller. Consider: ledger grows append-only; `Ledger.__init__` folds by run.
- Identity collisions are accepted deliberately ("two different reqs with one title and one pay band at one
  company count as one choice") — documented, good. But `rep:` (name+pay) identity means a *new* req that
  happens to reuse a popular band ("Senior Counsel | $175,000-$225,000") inherits seen status forever. The
  text-hash identity should shadow the pay-band identity when both exist; currently `surfaces()` unions all
  ids, so the loosest match wins. Invert: only fall back to looser identities when no tighter identity ever
  matched. This is a genuine product bug risk (silently hiding new opportunities — the opposite failure of
  Finding 2, and worse because it's invisible).
- Same-day runs don't mark seen (by design). But CI run ids differ per day; if you ever schedule twice
  daily, revisit.

**Change.** Tighter-identity-wins lookup; atomic save; append-only ledger sketch in `code_samples/`.

---

## `radar/db.py` — correct call: SQLite as rebuildable cache, committed CSVs as truth

**Keep.** `_heal()` moving a corrupted DB aside instead of failing the run fits the stated invariant
(history lives in git). Thread-local connections avoid the classic shared-connection trap.

**Watch.** WAL mode not enabled (`PRAGMA journal_mode=WAL`) — with 8 parallel channel processes writing
leads, default rollback-journal locking serializes writers and raises `database is locked` under bursts.
One line at connect: `conn.execute("PRAGMA journal_mode=WAL")` + `busy_timeout=5000`.
Dual-bookkeeping (jsonl + sqlite mirrors) risks divergence; pick SQLite as the write target and jsonl as an
export, or vice versa — today both are written from different code paths.

---

## `radar/models.py`, `config.py`, `filelock.py`, `runlog.py`, `robots.py`, `textutil.py`

- `Posting` as a pydantic model serialized into JSONL and SQLite `data` blobs is consistent; make sure
  `Posting.model_validate_json` failures on old-schema candidate files from previous runs are caught
  (phase4 reads `candidates_boards.jsonl` without try — schema evolution will eventually bite mid-week).
- `config.py` hard-coding the contact email default: see nit #10.
- `filelock.py` exists — yet `http.py` hand-rolls its own lock. If `filelock.py` is the abstraction, use it
  (with the delay-aware stale timeout); if it's vestigial, delete it. Two lock implementations invite drift.

## `tests/` — strong culture, missing one dimension

**Keep.** 252 tests, fast (2.6 s), autouse fixtures isolating ledger/judgment state — the conftest shows
someone thought about test pollution. `test_misfires.py` = regression tombstones. Excellent.

**Watch / Change.**
- No property-based testing anywhere despite being the perfect fit for extract/score boundaries
  (hypothesis: "any parsed pay range lands in a sane annual band", "affirmed() never fires on negated-only
  corpora"). Sample in `code_samples/test_properties.py`.
- No golden-corpus replay (the big architectural win — see 04 §Rubric).
- CI installs unpinned `pytest` (Finding 8); pin it or disable plugin autoload.

## Repo hygiene

- `docs/`, `agent flows/`, `seeds/`, `out/`, `data/` mix artifacts and inputs; `.gitignore` handles cache
  but `data/judgments/pending/*.json` (generated batches) are committed — acceptable as work-queue between
  Claude sessions, but stale pending batches from abandoned runs will accumulate. Add a TTL sweep in
  `aggregate.write()` (which already prunes old dated files — extend it).
- README claims `make` optional — verified true (Makefile is thin wrappers). Good.
