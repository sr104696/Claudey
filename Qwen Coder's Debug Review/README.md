# Qwen Coder's Debug Review

A full code review, debugging report, improvement proposals with runnable code samples, and a Socratic
question bank for the `job radar` repository (reviewed at commit `bc763c7`, 2026-10-07).

## Read in order

| File | Contents |
|------|----------|
| `01-Executive-Summary.md` | Verdict, severity-ranked findings table, top-3 recommendations |
| `02-Debug-Findings.md` | 10 findings with reproduction evidence and line references — incl. **one live breakage**: floating `selectolax>=0.3.21` now resolves to 1.0, which deletes the imported API and breaks every fresh install |
| `03-Code-Review.md` | Module-by-module review: Keep / Watch / Change comments per file |
| `04-Architecture-and-Frameworks.md` | Eight improvement tracks (rubric-as-data rule registry, LLM-judgment evals, structured concurrency, atomic state writes, parser shim, dependency engineering, observability, discovery upgrades) + prioritized roadmap |
| `05-Prompting-Thoughts.md` | 20 targeted questions designed to provoke the next round of improvements |

## code_samples/ — all self-tested, run them

| Sample | Demonstrates | Status |
|--------|--------------|--------|
| `atomic_jsonl.py` | Crash-safe rewrite of `seen.Ledger.save()` (temp+fsync+`os.replace`) | ✅ self-test passes; shows old strategy losing history on simulated crash |
| `rule_registry.py` | Rubric-as-data scoring core with rule ids + targeted judge vetoes | ✅ runs; scores known misfire strings correctly |
| `channel_watchdog.py` | Per-child deadlines fixing `pipeline.run_discovery` starvation | ✅ fix verified in demo |
| `parser_shim.py` | Single import site over selectolax lexbor/modest ending Finding 1 | ✅ runs on lexbor backend |
| `test_properties.py` | Hypothesis property tests for extract/score boundary (drop-in for `tests/`) | needs `pip install hypothesis` + repo on path |

## Verification performed during this review

- Installed requirements fresh → reproduced the selectolax 1.0 import failure across all 12 test modules;
  pinned `selectolax==0.3.29` → **252/252 tests pass** (`pytest -q`, 2.5 s).
- All claims in `02`/`03` were checked against actual file contents (line numbers cited).

## Note on scope

No production files were modified — this folder is additive only. The single most urgent action item,
for whoever applies it: change `requirements.txt` line 8 to `selectolax>=0.3.21,<1.0` today, then plan
the lockfile + shim migration (see `04` §F and §E).
