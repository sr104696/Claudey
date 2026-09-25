# Security review

This repo is a crawler and data aggregator, so the main security concerns are around network trust boundaries, sensitive output handling, and outbound fetch behavior.

## 1) Unbounded outbound fetches from untrusted URLs are not constrained by an allow-list

The pipeline fetches employer boards, public search results, and discovery leads from a wide variety of URLs. The code checks robots.txt and rate limits, but it does not enforce a strict allow-list of destinations or block dangerous schemes beyond the default HTTP(S) assumptions.

The most relevant examples:

- `radar/phase4.py` resolves lead URLs and fetches them directly.
- `radar/verify.py` fetches generic employer pages with no additional provenance check beyond the input URL.
- `radar/http.py` is built around a flexible HTTP client and will follow redirect chains manually, but there is no well-defined policy for “trusted domains only.”

This is a classic crawler tradeoff, but from a security perspective it means a compromised or malicious `companies.csv`, discovery result, or URL from a lead can trigger fetches to arbitrary public destinations. That is not catastrophic in this repo's context, but it is a real risk to operational safety and should be documented or constrained.

## 2) Sensitive run logs may leak more than intended

`radar/http.py` logs every request, including URL, method, status, and channel, and `radar/runlog.py` writes the aggregate results to `out/run_log.md`.

That is useful for debugging and compliance, but it may also capture URLs, employer names, lead sources, and content-derived identifiers that are not intended for broad distribution. This project is a job tracker and may include small amounts of candidate-specific or sensitive lead data, which means log retention and file permissions should be deliberate rather than accidental.

A reasonable hardening step would be to strip or redact query strings, limit retention, and ensure generated output is not accidentally exposed in an environment that is shared outside the repo owner.

## 3) Secrets are handled as local env state, but the repo does not defend against bad `.env` content

The repo loads `.env` via `load_dotenv(ROOT / ".env")` in `radar/config.py`. That is a common pattern, but it is not a security boundary by itself. The code uses environment values for API keys and a contact email, but it does not validate the shape of those variables or fail closed if a secret is missing or malformed.

This is not a direct vulnerability, but it is an operational footgun: a malformed key or an accidental secret export can result in bogus network requests or silent failures without clear diagnostics.

## 4) A few paths are effectively trust-based rather than integrity-checked

The project writes a lot of output to `data/` and `out/` directly, and the generated files are later consumed by other phases. The code trusts the input files and prior JSONL/CSV outputs too strongly:

- `radar/discover/commoncrawl.py` writes `data/cc_boards.json` and `data/discovered_boards.csv` from network-derived data.
- `radar/phase4.py` merges judgment JSON files from `data/judgments/results/*.json`.
- `radar/output.py` writes a markdown diff and CSV snapshot from previous runs.

If a stale or malicious file is present, the code will consume it as ground truth. This is mostly a local-dev risk, but the repo would benefit from checksum or schema validation around these generated artifacts.

## 5) The project is intentionally aggressive about scraping public web pages, but the same pattern can become unsafe if reused in a broader environment

The read-only crawler model is a good fit for a personal research tool, and `robots.txt` plus rate limiting mitigate the obvious issues. The main remaining concern is not exploitation in the strict sense; it is the drift from “personal research tool” into “generic web data collection system.”

Once the repo starts ingesting more user-controlled URLs, more external feeds, and more third-party search data, the combination of broad URL fetches, logging, and local output makes it more important to add strict validation and a formal trust model.

## Overall assessment

There is nothing here that looks like a serious remote-code-execution or credential-leak bug in the code as written, but there is a legitimate operational-security concern from the combination of:

- arbitrary outbound fetches,
- permissive logging,
- and trust in generated state files.

The project should keep the current “read-only, polite” spirit but add stronger destination validation and output hygiene if it expands beyond a single-user local workflow.
