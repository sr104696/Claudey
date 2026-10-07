# Qwen Coder's Debug Review — Executive Summary

**Repo:** `job radar` (Python 3.12, ~7,000 LOC in `radar/`, 252 tests in `tests/`)
**Reviewer:** Qwen Coder
**Date:** 2026-10-07
**Verification performed:** full test suite executed locally; live dependency-resolution bug reproduced and root-caused.

---

## What this is

A personal, read-only job-posting discovery pipeline: seed verification → parallel discovery channels →
ATS board pulls → verification/dedupe → rubric scoring → markdown/CSV outputs, with an LLM-subagent
"judgment" loop layered on top of regex heuristics. The design discipline is unusually high for a
single-maintainer project: polite cross-process rate limiting, robots.txt compliance (RFC 9309),
secret redaction in logs, crash-isolated channels, self-healing SQLite, and regression tests named
`test_misfires.py` / `test_scoring_regressions.py` that treat every heuristic false-positive as a bug
with a tombstone test. **This is good code.** The findings below are calibrated accordingly: one live
breakage, several latent correctness risks, and a set of architectural moves that pay off as the
heuristic surface keeps growing.

## Findings at a glance

| # | Severity | Finding | Where |
|---|----------|---------|-------|
| 1 | 🔴 **Live breakage** | `requirements.txt` floats `selectolax>=0.3.21`; selectolax 1.0 removed the `selectolax.parser.HTMLParser` backend. Every fresh `pip install -r requirements.txt` now produces an environment where **all 12 test modules fail to import** and the pipeline crashes at import time. Reproduced locally. | `requirements.txt`, `radar/textutil.py:9`, `radar/ats/html.py:13`, `radar/ats/nyag.py:13`, `radar/discover/rlegaltech.py:19` |
| 2 | 🟠 High | Ledger rewrite (`seen.Ledger.save()`) is not atomic and drops *this* run's earlier lines from the in-memory copy before writing — a crash mid-`save()` loses the entire seen-history, silently re-showing old postings ("Never present the same choice twice" is the project's core promise). | `radar/seen.py:124-138` |
| 3 | 🟠 High | Cached judgments reused by `company|title` can be applied to a posting whose text changed when `desc_hash` is missing/stale, and the `_judg` module-level cache has no invalidation after `apply-judgments` within a process — later scoring in the same process reads a pre-merge snapshot. | `radar/score.py:149-183`, `radar/phase4.py` |
| 4 | 🟠 High | `pipeline.run_discovery()` waits on channels **sequentially against one shared deadline**: channel N effectively gets `deadline − Σ(time of 1..N−1)`. A slow first channel starves later ones into spurious exit-124 timeouts even though they ran in parallel. | `radar/pipeline.py:33-40` |
| 5 | 🟡 Medium | Rate-limit lock uses a fixed 60 s stale-lock window while a single request can hold the gate through retries up to ~minutes (backoff max 60 s × attempts); another process can delete the lock and stampede a host the policy says 1 req/s. Also `.ts` write and request issue are not the same instant, so crawl-delay hosts drift early over time. | `radar/http.py:155-193` |
| 6 | 🟡 Medium | Scoring rubric is ~40 hand-tuned regexes with order-dependent interactions and per-fix special cases (`law_firm_title_carveout`, `real_ote`, `NEGATION` lookahead windows). Each fix adds a clause; there is no declarative rule layer or golden-set replay, so regressions are caught only if someone thought to write a test for that exact string. | `radar/score.py`, `radar/extract.py` |
| 7 | 🟡 Medium | Silent-failure pattern: bare `except Exception:` in board pulls keeps the *light* posting but doesn't log which job failed or why (`phase2.py:267,281,296`); combined with `status="partial"` aggregation it can quietly degrade extraction quality run-over-run. | `radar/phase2.py`, `radar/db.py:105` |
| 8 | 🟡 Medium | No CI pinning of transitive deps, no lockfile, no `pyproject.toml`, tests depend on ambient site-packages plugins (an unrelated globally-installed `libtmux` pytest plugin aborts collection here — exactly how #1-style breakage hides). | repo-wide |
| 9 | 🟢 Low | `redact_url` only redacts query params; credentials embedded in path segments or basic-auth URLs pass through to `http-<pid>.jsonl`. | `radar/http.py:69-80` |
| 10 | 🟢 Low | Docstring placed *after* the function signature in `phase4.dedupe` (dead expression, not a docstring) — cosmetic but signals the function grew past its comment. | `radar/phase4.py:203-207` |

## Top three recommendations

1. **Pin dependencies and add a lockfile today** (`selectolax==0.3.*` upper-bound or migrate to the
   `lexbor` backend behind a small internal parser shim). Add `pip freeze`-quality locking
   (`uv lock` / `pip-tools`) and make CI install from the lock. *(Details & code: `02-Debug-Findings.md`, `code_samples/parser_shim.py`)*
2. **Make durable state writes crash-safe**: atomic replace + fsync for `seen.jsonl` (and any committed
   CSV), and keep the current run's prior lines until the new file is fully written.
   *(Code: `code_samples/atomic_jsonl.py`)*
3. **Evolve the rubric from regex soup to a declarative rule registry + golden-corpus replay harness.**
   Rules become data (id, predicate, effect, precedence, explanation), every judgment lands as a labeled
   example, and each PR replays the corpus to diff bucket changes. This converts the current
   "one test per misfire" culture into systematic regression pressure and makes the human/LLM judgment
   loop self-improving. *(Design & sample: `04-Architecture-and-Frameworks.md`, `code_samples/rule_registry.py`)*

## Document map

- `01-Executive-Summary.md` — this file
- `02-Debug-Findings.md` — reproduced bugs and latent defects, with line references and evidence
- `03-Code-Review.md` — module-by-module review notes (what's good, what's fragile)
- `04-Architecture-and-Frameworks.md` — frameworks, patterns and target architectures for improvement
- `05-Prompting-Thoughts.md` — Socratic question bank to provoke the next round of improvements
- `code_samples/` — runnable sketches demonstrating the fixes
