# Style and maintainability notes

This repo is readable and deliberately structured, but there are several places where code clarity is trading off against compactness and a lot of the logic is “clever” rather than obvious.

## 1) Some functions are doing too much at once

Examples:

- `radar/phase1.py:verify_seeds()` is doing verification, repost detection, aggregator resolution, DB writes, and report generation in one large function.
- `radar/phase4.py:gather()` handles reading prior-state files, loading leads, verifying them, updating stats, and aggregating results.
- `radar/score.py:score()` combines hard-exclude logic, fit-signal generation, poor-fit logic, and bucket classification in a single method.

This is a common pattern in research pipelines, but it makes the code harder to test in isolation and harder to maintain when requirements change.

## 2) The project has a lot of “magic strings” and implicit contracts

There are many string-valued statuses and source labels, such as:

- `open`, `closed`, `unverified`, `fit`, `poor`, `outside`
- `board:greenhouse`, `public_sector:*`, `discover:*`, `seed`
- board-specific identifiers like `greenhouse`, `lever`, `ashby`, `workday`

These are central to the logic, but they are not always guarded by a shared enum or schema. The same values are re-used across files and sometimes assumed but not validated. That is workable today, but it increases the chance of subtle regressions.

## 3) Dedupe and matching logic can be hard to follow because it is spread across multiple helper functions

The matching logic is split across:

- `phase1.same_role()`
- `phase1.find_repost()`
- `output._match_key()`
- `phase4.dedupe()`
- `score._role_key()`

Each one uses a different definition of identity. That is a clear sign that the repo has multiple “same job” semantics, depending on whether it is diffing a run, verifying a seed row, or de-duping discovered leads.

This is not wrong, but it is not self-evident and is easy to misuse.

## 4) Naming is mostly good, but some names over-encode implementation details

A few names are practical but not very expressive:

- `phase1`, `phase2`, `phase4` are fine but opaque unless you know the architecture.
- `display_company()` is doing more than display; it also normalizes board slugs to employer names.
- `ATS_URL` in `radar/discover/common.py` is not just an URL regex; it is essentially a whitelist of accepted lead URL shapes.

The project is understandable to the current author, but less obvious to a new maintainer.

## 5) Some code is compact but not obviously defensive

Examples:

- `score()` uses many regex checks and a few fallback heuristics, but not all branches are explicit or strongly tested.
- `phase1._compare()` makes assumptions about pay values and location buckets without a central normalization layer.
- `keywords.relevance()` is intentionally compact, but it acts on a lot of domain knowledge without obvious unit tests covering edge cases.

This is a style choice: the code is compressed for speed and clarity of intent, but it is not as defensive or self-documenting as it could be.

## 6) Documentation is good on the top-level command flow, but not always on the failure modes

The project’s README explains the e2e flow well, yet the more error-prone parts are still under-documented:

- what a failed ATS detection means,
- which lead URLs are intentionally dropped,
- how run artifacts are meant to be read back,
- and which heuristics are domain-specific versus generic.

This is a documentation debt rather than a code defect, but it matters a lot in a pipeline that depends on heuristics.

## Overall assessment

This is not a sloppy project. It is a compact, opinionated pipeline with a lot of domain-specific logic and a few places where the code is carrying too much implicit knowledge. A little more explicit structure, especially around identity/dedupe and shared state contracts, would substantially improve maintainability without changing the project’s direction.
