# 04 — Architectures, Frameworks & Approaches for Improvement

Not a rewrite pitch. The system's shape (polite client → channels → verify → score → present) is right.
These are targeted evolutions ordered by payoff-per-effort, each with the framework/pattern named and a
concrete adoption path in *this* codebase.

---

## A. Rubric-as-data: declarative rule registry + golden-corpus replay  ★ highest payoff

**Pattern:** Production Rule Systems-lite (condition-action rules with explicit precedence + explanation),
not CLIPS/Drools — keep it in-Python. **Companion practice:** golden/characterization testing at scale
(snapshot every labeled posting's bucket; PRs must explain diffs).

**Why now.** `score.py` already contains the *components* of a rule engine (RX, EXCL dicts, ordered if-chain,
human-judgment overrides). What's missing is that rules aren't first-class values: no ids, no declared
precedence, no per-rule telemetry, no batch attribution. Every future misfire fix grows the chain.

**Design sketch** (full runnable sample: `code_samples/rule_registry.py`):

```python
@dataclass(frozen=True)
class Rule:
    id: str                      # "sales_title", "pay_floor", "lawyer_carveout"
    effect: Effect               # HARD_EXCLUDE | POOR | SIGNAL | VETO (suppresses other rules)
    when: Callable[[Ctx], bool] = lambda c: True   # gate: lawyer-titled? seed source?
    fire: Callable[[Ctx], Match | None]            # predicate -> evidence
    message: str = "{evidence}"
    priority: int = 0            # VETO rules run first and can suppress by id

def score(p): 
    ctx = Ctx(p, judgment_for(p))                 # one place resolves judgment vs regex
    fired = [r for r in RULES if r.when(ctx) and (m := r.fire(ctx))]
    vetoed = {v for r in fired if r.effect is VETO for v in r.suppresses}
    ...fold into Posting verdict, carrying [rule_id...] everywhere
```

**The unlock:** LLM judgments become *targeted vetoes*. Today `override_regex_exclude` is a blunt flag that
drops all regex excludes except OTE. With rule ids, the judge returns
`{"vetoes": ["sales_title"], "reason": "'supports the sales team' ≠ quota-carrying"}` — precise, auditable,
and each veto automatically becomes a labeled counterexample for the golden corpus. Over months you can
mine which regexes get vetoed most and either fix or delete them (the corpus tells you what heuristics earn
their keep).

**Golden corpus:** build once from `data/snapshots/*.csv` + `judgments.jsonl` (~hundreds of labeled rows
already exist). Harness = load corpus → run current rules → diff `(key → bucket, reasons)` → fail CI on
unexplained flips. This converts your excellent hand-written `test_misfires` culture into exhaustive
replay pressure at near-zero marginal cost.

---

## B. Evals for the human/LLM judgment loop

**Framework ideas:** LangDatasets-style JSONL eval sets / promptfoo-style matrix runs (borrow the *shape*,
no dependency needed). You already have pending/results batches — add:

1. `judge_evals.jsonl`: pairs of (batch excerpt, Seth-accepted verdict). Seth's `decisions.csv` is a free
   label source: `right_call`/`fit` rows validate past judgments; dismissals after a fit recommendation
   indict them.
2. A weekly offline command `python -m radar judge-accuracy` computing precision of recommendations against
   decisions, sliced by seat family and rule id. That single number ("recommendations accepted 38%") is the
   metric the whole project should optimize; nothing today measures it end-to-end.
3. Prompt versioning: store `prompt_version` in each judgment record so rubric-prompt changes are diffable
   like code changes.

**Deeper thought:** the pipeline currently treats regex-score and LLM-judgment as fallback layers. Flip it:
regex = cheap *pre-filter + feature extractor*; LLM = authority on ambiguous classes only (you already do
this for sales/floor/litigation — extend to law-firm/government detection, where GOVERNMENT_NAME/LAW_FIRM
regexes carry the largest false-positive surface and an LLM call on ~dozens of borderline rows/run is cheap).

---

## C. Concurrency & orchestration modernization

**Problems seen:** Finding 4 (deadline starvation), ThreadPoolExecutor(8) + global lock-file gating,
per-process state (`_blocked_hosts`, robots cache) duplicated across 8 subprocesses.

**Options, cheapest first:**

1. **Keep subprocess fan-out, fix semantics:** per-child deadlines (sample provided); children write
   `<channel>.stats.json`; parent merges instead of string-guessing. Zero new deps. Do this regardless.
2. **Structured concurrency library — `anyio` or `asyncio.TaskGroup` (3.11+):** convert `PoliteClient` to
   `httpx.AsyncClient` with a per-host `asyncio.Lock` + token-bucket limiter
   (`aiolimiter` or 20 lines inline). One process, channels as tasks, natural cancellation scopes replace
   kill-timeouts, contextvars already used for channel tagging map 1:1 onto tasks. The cross-*process* file
   gate stays useful only for concurrent Claude subagents — you could drop it then, since one event loop
   enforces spacing directly. Big simplification; medium migration effort (all adapters sync→async).
3. **Durable workflow engines (Prefect/Airflow/Dagster/nomad-style):** overkill for weekly personal runs.
   The honest comparison: what they'd buy you is retries-per-task + backfills + UI. Your run_log + health +
   GitHub Actions already approximate that. Consider Dagster *assets* only if `out/*` artifacts grow into
   something re-consumed (e.g., the Lovable app reading intermediate tables) — asset-versioned lineage
   would make "why does this CSV look like that" answerable. Don't pay that tax today.

**Recommendation:** do (1) now; schedule (2) as the next structural step, ideally bundled with the parser
shim (E) so you touch IO code once.

---

## D. State management: single-writer stores, atomicity as policy

**Patterns:** append-only log + compaction (event-sourcing-lite); atomic file replacement (temp+fsync+rename);
CRDT not needed; SQLite WAL.

- Ledger: append-only `seen.jsonl` + `compact()` called by `aggregate.write()` (which already prunes files —
  same mental slot). Crash-loss becomes impossible; git diffs become additive.
- All committed data files (`decisions.csv`, `source_health.csv`, `companies.csv` rewrite in phase2 — check
  its tempfile usage; I saw `import tempfile` there, good instinct — apply the same everywhere including
  `_cache_put`).
- Make the *policy* explicit in CLAUDE.md: "every durable write is atomic-replace; every reader tolerates
  torn lines." Then audit violations mechanically (grep `open(...,"w")` outside helpers).
- SQLite: enable WAL + busy_timeout before adding any more parallel writers; consider making jsonl files
  generated-from-SQLite rather than parallel sources of truth.

---

## E. Parsing layer: one shim, two backends, HTML5 correctness

**Approach:** internal `radar/htmlparser.py` exposing `parse(html) -> Node` implemented over
`selectolax.lexbor` (modern HTML5 tokenizer, faster) with fallback import path for old installs — kills
Finding 1 permanently and centralizes the migration. Keep BeautifulSoup only where you need
`find_all(attrs=...)` gymnastics Lexbor handles awkwardly; otherwise drop it from requirements (check actual
usage first — I saw both imported).

**Adjacent idea worth stealing from frameworks:** schema-first extraction. JSON-LD `JobPosting` already gets
a dedicated path (`jsonld_jobposting`) — treat it as the *primary* extractor and regex text mining as
fallback; log `extraction_method` per posting so you can watch JSON-LD coverage trend (it's rising yearly
due to Google's structured-data push; your regex debt should shrink accordingly).

---

## F. Dependency & CI engineering

- **`pyproject.toml` + packaging:** real package metadata, `[project.optional-dependencies] dev = ["pytest",
  "hypothesis", "ruff", "mypy"]`, entry point `radar = radar.__main__:main` (kills the sys.path hack).
- **Lockfiles:** `uv.lock` (fast, single tool) or `requirements.lock` via pip-tools. CI installs from lock;
  a scheduled "resolve-latest" job runs tests against unpinned to catch upstream breaks *before* users do.
- **CI additions:** `ruff check` (would have caught the dead docstring, unused imports), `mypy radar` in
  relaxed mode (typed core already; drift will increase without a gate), `--cov` optional but
  `pytest -p no:cacheprovider PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for hermeticity (Finding 8).
- Add `python -m compileall` already present — keep; extend to `radar` **and** `tests`.

---

## G. Observability: from run logs to metrics

`run_log.md` is a great artifact but prose-shaped. Layer machine-readable signals beside it:

- Per-rule hit counters (falls out of A) written to `data/runs/<run>/rule_stats.json`; `health.record()`
  alerts on distribution shifts ("lawyer_carveout fired 3× more than last run → investigate before trusting
  the list").
- Channel yield funnel per run: leads → verified_open → kept → *presented-new* (seen-filtered). A channel
  producing many verified-but-always-seen rows is dead weight; today nobody sees that ratio.
- `source_health.csv` exists — add per-source *staleness* (days since last new posting found) to catch a
  silently-changed board format that returns valid-but-empty JSON (the classic silent crawler failure).

---

## H. Search/discovery upgrades (where new value actually comes from)

- **Embedding-based dedupe/canonicalization:** cosine similarity on description embeddings replaces/augments
  exact `body()` hashing in `dedupe` — catches reposts with trivial edits ("now hiring!" prefix). Cheap with
  sqlite-vec or even hashed TF-IDF (no model dependency) if you want zero-infra. Same vectors power
  "near-miss" ranking beyond the current 12-row digest.
- **Learning-to-rank lite:** once decisions.csv has enough labels, fit logistic regression on existing
  features (fit_signals, seat_family, segment) to produce a calibrated `p(interest)` alongside the rubric
  score — don't replace the rubric (explainability matters to him), *add* the second number and watch
  disagreements between them; those are where rubric improvements hide.
- **Entity resolution:** norm_company is name-string matching; ATS registries accumulate slug collisions.
  A tiny alias table (company → canonical, learned from verified postings) prevents cross-board dupes the
  rank-order hack in `dedupe` can miss.

---

## Prioritized roadmap

| Order | Move | Effort | Payoff |
|---|---|---|---|
| 1 | Pin `selectolax<1.0` + lockfile + CI plugin hermeticity (F) | hours | stops live breakage class |
| 2 | Atomic ledger save + append-only option (D) | hours | protects core product promise |
| 3 | Per-child channel deadlines + stats files (C1) | half day | ends false-red runs |
| 4 | Judgment-cache invalidation + torn-line tolerance (A precursor) | 1 hour | removes heisenbugs |
| 5 | Parser shim → Lexbor (E) | day | HTML5 correctness + speed |
| 6 | Rule registry + golden corpus (A) | few days | makes all future tuning safe |
| 7 | Judge-accuracy evals from decisions.csv (B) | day | measures whether any of it works |
| 8 | asyncio conversion (C2) | week | simplifies concurrency; bundle after 6 |
| 9 | Embedding dedupe + p(interest) (H) | weekend experiments | discovery quality ceiling |
