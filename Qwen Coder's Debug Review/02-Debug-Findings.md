# 02 — Debug Findings (reproduced + latent)

Every claim below was checked against the actual tree at `bc763c7`. Reproduction commands are included so
the findings are traceable.

---

## Finding 1 🔴 — Live breakage: floating `selectolax>=0.3.21` resolves to a version that deletes the API you import

**Evidence (reproduced in this environment):**

```text
$ pip install -r requirements.txt        # fresh env, today
$ python -m pytest tests -q
ImportError while importing test module 'tests/test_seen.py' ...
radar/textutil.py:9: in <module>
    from selectolax.parser import HTMLParser
E   ImportError: Modest backend is deprecated since selectolax 1.0 ...
    Please use lexbor backend instead: `from selectolax.lexbor import LexborHTMLParser`.
Interrupted: 12 errors during collection
```

After pinning `selectolax==0.3.29`: **252 passed**. So the code and tests are healthy; the *dependency
specification* is what broke.

**Root cause.** Four modules import `selectolax.parser.HTMLParser`
(`radar/textutil.py:9`, `radar/ats/html.py:13`, `radar/ats/nyag.py:13`, `radar/discover/rlegaltech.py:19`).
`requirements.txt` says `selectolax>=0.3.21` — an open upper bound. selectolax 1.0 removed the Modest
backend, so any clean install (`make install`, a new contributor, a rebuilt Actions runner without a warm
pip cache) now gets a fatal import error. This also breaks `python -m radar refresh` at import time — not
just tests.

**Why CI didn't catch it:** `.github/workflows/tests.yml` uses `cache: pip` on immutable runner images, so
existing runs keep resolving to the last cached compatible wheel until the cache is evicted — the classic
"works on CI, dies for everyone else" pattern.

**Fix options (in order of preference):**

1. **Immediate band-aid (one line):** `selectolax>=0.3.21,<1.0`. Ship today.
2. **Proper fix:** migrate to `selectolax.lexbor.LexborHTMLParser` behind a single internal shim so the
   backend choice lives in one place (see `code_samples/parser_shim.py`; note the CSS-selection API differs:
   `css_first`/`css` exist on Lexbor but node attributes/iteration semantics change slightly — the shim must
   normalize `text()` stripping as `textutil.html_to_text` currently does).
3. **Structural fix:** adopt a lockfile (`uv lock` or `pip-compile`) and have both workflows install from
   the lock. Then no upstream release can silently break main again. Add a weekly "upgrade lab" scheduled
   job that installs unpinned, runs the suite, and opens an issue on failure — turn the canary into a feature.

---

## Finding 2 🟠 — `seen.Ledger.save()` can destroy the ledger it exists to protect

`radar/seen.py:124-138`:

```python
def save(self) -> int:
    keep = [r for r in self.rows if r.get("run", "") < self.run]   # (a)
    ...
    with open(self.path, "w", encoding="utf-8") as f:              # (b) truncates FIRST
        for r in keep + fresh:
            f.write(json.dumps(r) + "\n")
```

Two problems:

- **(b) truncate-then-write is not crash-safe.** If the process is killed mid-loop (Actions timeout, OOM),
  `data/seen.jsonl` is left truncated — the file that encodes "never present the same choice twice". The
  next run sees a short ledger and re-presents postings as new. Note `_read_jsonl` tolerates a *torn line*
  but nothing recovers *lost lines*.
- **(a) filters strictly `< self.run`,** so if today's run crashed after a partial `save()`, a re-run today
  rebuilds from `keep` (which excludes today's earlier lines) — fine by design — but combined with (b), a
  crash between truncate and completion loses *earlier runs'* history too, because those bytes were already
  overwritten.

Also: `Ledger.load` bootstraps from snapshots when the ledger is empty — good — but bootstrap only fires on
literally-empty files; a *truncated-but-nonempty* ledger skips bootstrap and silently under-reports seen
history. That's the worst failure mode: quiet, not loud.

**Fix:** write to a temp file in the same directory, `flush + os.fsync`, then `os.replace` (atomic on POSIX
and Windows), and back up the previous file before replacing. See `code_samples/atomic_jsonl.py` for a drop-in
rewrite of `save()`. Same treatment belongs on `data/decisions.csv` appends (an interrupted CSV append can
leave a half row that `csv.DictReader` will choke past — here it would just skip, losing a decision).

**Test to add:** simulate `kill` mid-save (raise inside the write loop) and assert the old ledger still
parses intact afterwards.

---

## Finding 3 🟠 — Judgment cache: stale reuse and missing invalidation

`radar/score.py:149-183`:

```python
_judg: dict[str, dict] | None = None          # module-level, built once per process

def judgments() -> dict[str, dict]:
    global _judg
    if _judg is None:                          # never invalidated
        ...
        _judg[d["key"]] = d
        if (p := get_posting(d["key"])):
            _judg[_role_key(p.company, p.title)] = d   # company|title alias index
```

Issues:

1. **No invalidation.** `pipeline.finish()` calls `apply_committed_judgments()` (which merges new results
   into `data/judgments.jsonl`) and *then* `phase4.run()` scores. In a long-lived process (or future
   in-process orchestration), anything that touched `judgments()` before the merge keeps scoring with the
   pre-merge snapshot. Today's CLI flow happens to order things correctly, but the invariant is implicit
   and fragile — a refactor that scores twice in one process silently ignores fresh judgments.
   **Fix:** have `apply-judgments` call `score.invalidate_judgments()` (`global _judg; _judg = None`), or
   key the cache on `(path.stat().st_mtime_ns, size)` and reload on change. One line each; removes a class
   of heisenbugs.
2. **Alias-index correctness depends entirely on `desc_hash` being present in the stored judgment:**
   `role_judgment()` requires `j.get("desc_hash") == desc_hash(p)`. But judgments written by subagents via
   `data/judgments/results/*.json` pass through `phase4.apply_judgments()` — verify that path always stamps
   `desc_hash` from the *posting text that was judged*, not from whatever the board shows now. If a posting
   text changed since judging (edit-in-place re-listing), the alias match correctly fails → falls back to
   regex heuristics → the row can flip bucket for reasons invisible in the diff report. That's acceptable,
   but should be *recorded*: when a direct-key judgment exists but its `desc_hash` mismatches, log
   `judgment_stale=true` on the posting so `out/diff_<date>.md` can explain a fit→poor flip.
3. `judgments()` does `json.loads(line)` per line with **no try/except** — one malformed line (hand-edit,
   bad merge conflict resolution in the committed file) raises and kills the whole scoring phase. Contrast
   with `_read_jsonl` in `seen.py`, which deliberately tolerates torn lines. Same policy should apply here.

---

## Finding 4 🟠 — Sequential deadline starvation in `run_discovery`

`radar/pipeline.py:33-40`:

```python
codes, deadline = {}, time.time() + CHANNEL_TIMEOUT_S
for ch, (p, log) in procs.items():
    try:
        codes[ch] = p.wait(timeout=max(1, deadline - time.time()))
    except subprocess.TimeoutExpired:
        p.kill(); codes[ch] = 124
```

All channels start in parallel, but waits are sequential over a dict. The precise starvation condition:
any channel that finishes **after** the shared deadline spends the wait slot ahead of it gets ~1 s of
remaining budget and is killed with code 124. Example: `commoncrawl` (dict order #5) runs its documented
40–50 min while channels #6–8 finish normally in 10–20 min — but if any earlier channel alone exceeds 50
minutes, *everything after it* is reaped regardless of health; and even without one runaway, later
channels get systematically less grace than earlier ones. Result: exit-124 attributed to healthy
channels, `ChannelFailure`, red run, and `health.record()` blaming the wrong source. (Note the benign
case: when all children finish before the deadline, sequential waiting costs nothing — the bug bites
exactly when the pipeline is under stress, which is when accurate attribution matters most.)

**Fix:** give each child its own deadline (`start_time + CHANNEL_TIMEOUT_S`), enforced either by waiting on
all with a shared poll loop (`psutil`-free version: loop `p.poll()` + sleep, or `concurrent.futures` over
`p.wait`), or simply by having each child enforce its own timeout internally
(`signal.alarm` / a watchdog thread) and letting the parent wait unconditionally. Sketch in
`code_samples/channel_watchdog.py`. Bonus: kill-on-timeout currently leaves grandchildren (none today, but
if a channel ever shells out) — `start_new_session=True` + `os.killpg` makes cleanup robust.

Related sharp edge in the same function: `log = open(...)` handles stay open for all channels until each is
waited on; harmless, but if the parent raises between Popen and wait (e.g., disk full creating later logs),
earlier children are orphaned and unsupervised. Wrap the spawn/wait loop in `try/finally` killing all procs.

---

## Finding 5 🟡 — Rate-limiter gaps: stale-lock window vs. retry duration; delay measured at grant, not at send

`radar/http.py:155-193`. Two interacting details:

1. `_HostGate._lock` treats a lock older than **60 s** as stale and unlinks it. But `attempt()` holds the
   gate only around the request itself — actually no: `wait_turn` releases the lock *after* writing `.ts`,
   and the spacing sleep happens *inside* the lock, so a host with `Crawl-delay: 120` in robots.txt makes
   every waiter hold the lock ~120 s > 60 s → the next process declares it stale, deletes it, and two
   requests go out concurrently. The polite-client's central promise breaks precisely on the hosts that ask
   for the most politeness. **Fix:** derive the stale threshold from the configured delay
   (`max(60, 2*delay + expected_request_time)`), or better, use `fcntl.flock`/`msvcrt.locking` advisory
   locks (kernel-managed, die with the process — no staleness heuristic at all). flock is POSIX-only; GitHub
   runners are Linux, local dev macOS/Linux, so this is safe with a small fallback.
2. `.ts` is stamped *before* the HTTP roundtrip completes but *after* the gap sleep — i.e., spacing is
   "start-to-start", which is right for crawl-delay semantics. However on retries (`_raw` → tenacity), each
   attempt re-acquires the gate — correct — but `Retry-After: 120` sleeps happen where? They're returned as
   tenacity `wait`, applied *outside* the gate — so a 429 storm across processes each independently honoring
   Retry-After is fine, but a process can fire its retry the instant another's window closes. Acceptable;
   document it. What is *not* acceptable is item 1.

3. Minor: `robots_for` fetches robots.txt through `self._raw(...)` directly, bypassing `_blocked_hosts` —
   intentional (you need robots to know about blocks) — but it also means a challenge-walled host still gets
   robots.txt probes per process per 10 min. Bounded, fine. Just make sure the run log counts these so
   "Silence check" doesn't misreport them as traffic to that host.

---

## Finding 6 🟡 — Rubric complexity has crossed the point where structure beats cleverness

`radar/score.py::score()` is a ~140-line function mixing: pay normalization side effects (mutating `p`
in-place at lines 221-225), hard-exclude regexes, judgment overrides, poor-match rules, bucket assignment,
and display strings. Observations from the git-history-visible patch comments ("Seth, 2026-09-25",
"2026-09-28", "RBT Academy matched before"):

- Every false positive became a special case *inline* (`law_firm_title_carveout`, the `real_ote` clause,
  `NOT_AN_ASK`, negative lookbehinds in `er_years`). Each clause is locally justified; globally, rule
  *interaction* is now the main risk (e.g., a judgment `override_regex_exclude` strips excludes but the
  pay-floor poor-rule still fires — intended? nothing states it).
- `affirmed()` negation detection looks 30 chars back within a sentence fragment — misses long-negation
  phrasings ("This role is **not** anything like the billable-hours grind of law-firm associates..." with
  the negator >30 chars from the match). It's a bag-of-heuristics wearing a helper's clothes.
- There is no way to answer, mechanically: *"which rule moved this posting?"* The strings mostly encode it,
  but bucket flips in `diff_<date>.md` can't be attributed to a rule id, so tuning is eyeball-driven.

**Recommended shape** (full design in `04-Architecture-and-Frameworks.md`, working sample in
`code_samples/rule_registry.py`): a list of `Rule(id, applies_when(title_kind), predicate(posting)->match|None,
effect=EXCLUDE/POOR/SIGNAL/BUCKET, message_template, precedence)`. `score()` becomes a fold. You get:
rule ids in output columns, per-rule hit stats in `run_log.md`, golden-corpus replay diffs, and the LLM
judge can emit *structured verdicts keyed by rule id* instead of free-text overrides — which finally makes
`override_regex_exclude` precise ("rule `sales_title` misfired because...") rather than nuclear ("drop all
regex excludes except OTE").

Also split the pure functions from the mutating ones: `score()` currently mutates `p.pay_period/pay_type/
pay_display` — extraction fixes belong in `extract`/normalize phase, decisions in score. Purity here makes
the replay harness trivial (same input → comparable output).

---

## Finding 7 🟡 — Silent degradation paths

- `phase2.py:267, 281, 296`: `except Exception:` keeps the light posting but records neither the failing
  job id nor the exception type. Over weeks, a Workday tenant that starts 500-ing on detail pages yields
  boards of description-less postings → `desc_hash` empty → judgments never apply → scoring drifts to
  regex-only, with zero breadcrumbs. Fix: `failed += 1` *with* `runlog.record_channel(..., failures=[f"{job_id}: {type(e).__name__}"])` (there's already a `_partial_if` counter — attach reasons to it).
- `db.py:105` swallows exceptions in the heal path; fine for a rebuildable store, but print the original
  error to the run dir log so forensic questions ("why did my history vanish on Oct 3?") have answers.
- `pipeline.digest()` catches everything into `summary["digest"] = "failed: ..."` — good; keep it, but also
  feed it to `health.record()` so a permanently broken ntfy topic surfaces in Silence check rather than
  rotting in a JSON summary nobody reads.

---

## Finding 8 🟡 — Environment fragility (meta-bug that let Finding 1 live)

Reproduction aside: in this sandbox, collection initially failed for an *unrelated* reason — a globally
installed `libtmux` pytest plugin incompatible with the installed pytest raised
`Failed: Marks cannot be applied to fixtures.` at import. Nothing in the repo caused it; the ambient
environment did. That is exactly how users will experience your project on shared machines.

Mitigations:
- `pyproject.toml` with `[tool.pytest.ini_options] addopts = "-p no:cacheprovider"` won't help against
  third-party plugins; instead ship a dev extra (`pip install -e ".[dev]"`) and document venv usage.
- Pin `pytest` in CI (`pip install pytest==8.*`), or set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` in the workflow
  and load only what you need.
- No lockfile and no packaging metadata at all today (`setup.py`/`pyproject.toml` absent; `sys.path` hack in
  `conftest.py`). Moving to a real package + `uv`/`pip-tools` lock eliminates three classes of surprise.

---

## Finding 9 🟢 — Redaction gaps

`redact_url` handles `?api_key=...` style secrets. Not covered: `https://user:pass@host/...`
(basic-auth URLs — httpx accepts them), and path-secret APIs like `/v1/companies/{token}/postings`. Cheap
hardening: strip userinfo via `urlsplit()._replace(netloc=hostname)` when logging, and extend the secret
regex to match known path patterns. Also `res.headers` values are logged nowhere today — keep it that way if
any header ever carries tokens (some ATS proxies echo auth).

---

## Finding 10 🟢 — Small verified nits

- `phase4.dedupe`: docstring sits *after* the signature (lines 204-207) — Python evaluates it as a no-op
  expression string; `dedupe.__doc__` is `None`. Move it above `rank = lambda ...`.
- `http.py:346`: `float(ra) if ra and ra.isdigit()` — Retry-After in HTTP-date form (common from CDNs) is
  ignored; falls back to exponential backoff. Acceptable, but a `email.utils.parsedate_to_datetime` branch
  is 3 lines.
- `config.CONTACT_EMAIL` defaults to a real personal address baked in source; CLAUDE.md says "ask the user
  which one." Consider making the default empty and refusing to build the UA without one — prevents
  accidentally mailing a stranger's inbox at 1 req/s forever.
- `score.py:19` `PIPELINE` matching uses `startswith` — "General Legal" seed tracking will miss
  "Legal General"-style variants; fine, but norm_company would be more consistent with the rest of the file.

---

## Positive findings worth preserving (do not "improve" these away)

- Cross-process rate limiting via lock files is genuinely hard; this implementation is 90% right.
- `_cacheable` refusing to cache non-robots 404s (line 54 comment) shows real incident-driven thinking.
- `janestreet_jobs()` raising instead of returning `[]` so outage ≠ "all closed" — the *failure polarity*
  is chosen deliberately per call site. That instinct should become a written principle: **"absence of data
  must never masquerade as a negative finding."** Grep the codebase for other places where `[]`/`None`
  collapses into "closed/not found" and apply the same discipline.
- Bootstrap-from-snapshots for the seen ledger is a smart recovery story.
- Test suite naming (`test_misfires`) reveals an anti-fragile culture. Keep it, and formalize it (Finding 6).
