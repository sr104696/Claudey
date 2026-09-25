# Summary of the review

## Overall assessment

This is a strong and thoughtful research tool: modular, explicitly rate-limited, and built around a clear “verify before listing” philosophy. The repo does a good job of balancing a real-world crawler’s operational constraints with a candidate-specific relevance filter.

The main issues are not about basic correctness so much as about coverage, blind spots, and how much implicit logic the system relies on.

## Top findings

1. Discovery coverage is narrower than the project assumes.
   - `radar/discover/commoncrawl.py` and `radar/discover/common.py` are heavily centered on Greenhouse/Lever/Ashby.
   - This increases the chance of real jobs never reaching the pipeline.

2. Dedupe and matching heuristics can misclassify roles or produce incorrect diff output.
   - `radar/output.py`, `radar/phase1.py`, and `radar/phase4.py` rely on coarse identity matching.
   - A more stable ID model would reduce false “new/closed” and false “same posting” decisions.

3. The project is built on a lot of heuristic filtering.
   - `radar/keywords.py` and `radar/score.py` aggressively exclude titles and roles before they are scored.
   - That is intentional for this target profile, but it also creates false negatives that are hard to detect.

4. The architecture is modular but carries too many implicit conventions.
   - The phases are separated, yet run state, lead context, and dedupe rules are spread across several files and file-based formats.
   - It works well for one user and one run, but it is not a high-trust platform abstraction.

5. Security posture is acceptable for a local research crawler, but it is not yet policy-driven.
   - The outbound fetch model is intentionally broad, and the repo would benefit from stricter destination validation and output hygiene as it grows.

## Recommended next steps

- Expand ATS support in discovery and board detection.
- Centralize identity/dedupe rules behind a single contract.
- Add targeted regression tests around relevance filtering and title matching.
- Document the trust model for outbound fetches and generated run artifacts.
- Keep the architecture modular, but give the run-state model a bit more explicit structure.

## Bottom line

The project is directionally excellent, especially for a highly targeted, personal job radar. The main improvement opportunity is not a rewrite; it is tightening the heuristics and making the pipeline’s assumptions more explicit so the system remains reliable as the repository grows.
