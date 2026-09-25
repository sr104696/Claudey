# Architecture review

The project has a strong modular structure, but the architecture is carrying a fair amount of hidden complexity. The modules are well-named and generally isolated, yet some cross-cutting responsibilities are spread too broadly.

## 1) The pipeline is logically clean, but phase boundaries are not always enforced

The repo separates phases into `phase1.py`, `phase2.py`, `phase4.py`, and `pipeline.py`, which is a good foundation. But the actual implementations still rely on shared mutable state and coarse assumptions about what has already happened.

Examples:

- `pipeline.refresh()` runs Phase 1, then discovery, then phase 2 and phase 4 in sequence.
- `phase4.gather()` reads `phase1.json`, board candidate files, and leads from the current run directory; it assumes all prior steps wrote the expected artifacts in the expected shape.
- `output.write()` relies on the previous run snapshot and the current run state to compute diffs without a stronger typed contract between runs.

This works for the current one-user workflow, but the architecture is brittle when the repo is extended or reused for experiments.

## 2) Discovery, verification, scoring, and output logic are duplicated in several places

There is a lot of the same logic repeated in different layers:

- lead filtering is handled in `discover/common.py`, `keywords.py`, and `phase4.resolve_lead()`;
- role matching logic appears in `phase1.same_role()`, `phase4.resolve_lead()`, and `output._match_key()`;
- jobs are filtered by relevance in `keywords.relevance()`, `phase2._relevant()`, and `phase4.run()`.

This duplication is understandable for a research pipeline, but it makes the project harder to reason about when a small change in one subsystem impacts another. The architecture would be easier to maintain if the dedupe/relevance rules were centralized behind a single “posting eligibility” abstraction.

## 3) The code relies on file-based state as if it were a database

The repo stores run state, judgement results, and snapshots in JSONL/CSV/SQLite files across `data/` and `out/`. That is a pragmatic choice, but it means the architecture is built around a set of file conventions more than a durable schema contract.

Examples:

- `radar/db.py` uses SQLite for postings and snapshots, but the run pipeline still depends heavily on file-based JSON in `data/runs/<run>/`.
- `radar/phase4.apply_judgments()` merges external judgment batches by scanning files and using a loose convention about `pending` and `results` directories.
- `radar/runlog.py` reads/writes per-run log files and turns them into markdown output.

This is manageable for a local pipeline, but it is a weak foundation for more automation or multi-user operation.

## 4) The tool is strong on “crawler hygiene,” but weak on “pipeline observability” once a job is admitted

The project is excellent at rate limiting and robots compliance. It logs blocks and failures, and it keeps output artifacts. However, once a job gets into the pipeline, there is less explicit instrumentation around why it was kept or discarded.

The code mostly relies on:

- `relevance()` reasons,
- `score()` signals,
- `runlog.md` counts,
- and the data snapshots.

That is enough for a single researcher, but it is not a high-trust debugging story for a larger team. There is no central, queryable audit trail of “why this posting was included/excluded” beyond logs and markdown, which makes regressions harder to diagnose.

## 5) The ATS handling layer is intentionally broad but not uniform

The `radar/ats/` package is a good example of domain partitioning, but the implementation is uneven across systems:

- Greenhouse, Lever, and Ashby are first-class and well-supported.
- Workday, Workable, Recruitee, BambooHR, and SuccessFactors are handled later and more variably.
- Generic page parsing is an escape hatch rather than a first-class strategy.

This creates an architectural asymmetry: a job is only as “supported” as the branch handling its ATS. The project compensates with heuristics and verification rules, but it means the long tail of ATS variants is harder to reason about and easier to break.

## 6) The candidate-specific business rules are increasingly embedded in the pipeline itself

`radar/score.py` and `radar/keywords.py` make a strong domain-specific set of decisions around target practice areas, salary bands, and fit signals. This is appropriate for the project goal, but it also means the architecture is a mixture of:

- a general crawler,
- a verification pipeline,
- and a domain-specific decision engine.

Those responsibilities are all in the same codebase, which is workable but can get confusing over time. A cleaner architecture would separate the generic posting-intake pipeline from the candidate-specific scoring layer.

## Overall assessment

The system is modular and intentional, but it has the classic “research tool” architecture problem: broad functionality is implemented with a lot of implicit conventions rather than a cohesive state model. That makes it strong for this project and weak for generalization or long-term maintenance.
