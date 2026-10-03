"""GitHub integration through gh, preserving Freebuff's managed authentication.

Never read credentials or put tokens in arguments. gh commands are authenticated
by the workspace; no SDK or additional Python dependency is required.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import subprocess

DEFAULT_REPO = "sr104696/Claudey"
WORKFLOW = "refresh.yml"


class GitHubError(RuntimeError):
    """An actionable failure without leaking subprocess output or credentials."""


def _gh(*args: str) -> str:
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, timeout=60, check=False,
        )
    except FileNotFoundError as exc:
        raise GitHubError("Install GitHub CLI (gh) and retry.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitHubError("GitHub request timed out; retry later.") from exc
    if result.returncode:
        # Do not print raw stderr: subprocess output can contain sensitive data.
        error = result.stderr.lower()
        if any(s in error for s in ("credential", "authentication", "http 401", "http 403", "gh auth login")):
            raise GitHubError(
                "GitHub access was denied. In Freebuff, reconnect the repository or "
                "update the Freebuff GitHub App permissions (Contents: read; Actions: read/write)."
            )
        raise GitHubError(
            f"GitHub CLI failed (exit {result.returncode}); check repository, branch, "
            "workflow and access permissions."
        )
    return result.stdout


def _api(repo: str, path: str, *, method: str = "GET", fields: tuple[str, ...] = ()) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise GitHubError("Repository must be OWNER/REPO.")
    args = [
        "api", f"repos/{repo}/{path}", "--method", method,
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: 2022-11-28",
    ]
    for field in fields:
        args.extend(("--raw-field", field))
    raw = _gh(*args)
    if not raw.strip() and method == "POST":
        return {}  # workflow_dispatch returns 204 with no body
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise GitHubError("GitHub returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise GitHubError("GitHub returned an unexpected response.")
    return data


def status(repo: str = DEFAULT_REPO, ref: str = "main") -> dict:
    """Latest manually dispatched refresh on this branch (not unrelated CI)."""
    data = _api(repo, f"actions/workflows/{WORKFLOW}/runs", fields=(
        "per_page=1", f"branch={ref}", "event=workflow_dispatch",
    ))
    runs = data.get("workflow_runs")
    if not isinstance(runs, list):
        raise GitHubError("GitHub response is missing workflow_runs.")
    if not runs:
        return {"repository": repo, "branch": ref, "run": None}
    run = runs[0]
    if not isinstance(run, dict):
        raise GitHubError("GitHub returned an invalid workflow run.")
    keys = ("id", "status", "conclusion", "html_url", "created_at", "updated_at", "head_sha")
    return {"repository": repo, "branch": ref, "run": {k: run.get(k) for k in keys}}


def trigger(repo: str = DEFAULT_REPO, ref: str = "main", *, quick: bool = False) -> dict:
    """Dispatch once; deliberately never retry a non-idempotent request."""
    _api(repo, f"actions/workflows/{WORKFLOW}/dispatches", method="POST", fields=(
        f"ref={ref}", f"inputs[skip_commoncrawl]={'true' if quick else 'false'}",
    ))
    return {
        "repository": repo, "branch": ref, "dispatched": True, "quick": quick,
        "actions_url": f"https://github.com/{repo}/actions/workflows/{WORKFLOW}",
    }


def report(path: str = "out/all_positions.md", repo: str = DEFAULT_REPO, ref: str = "main") -> str:
    """Read a committed report without writing to the local radar outputs."""
    if not re.fullmatch(r"out/[A-Za-z0-9_-]+\.(md|csv)", path):
        raise GitHubError("Report path must be an .md or .csv file directly under out/.")
    data = _api(repo, f"contents/{path}", fields=(f"ref={ref}",))
    if data.get("type") != "file" or data.get("encoding") != "base64":
        raise GitHubError("Report is not a base64 file (GitHub Contents API supports files up to 1 MB).")
    content = data.get("content")
    if not isinstance(content, str):
        raise GitHubError("GitHub response is missing report content.")
    try:
        return base64.b64decode("".join(content.split()), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeError, ValueError) as exc:
        raise GitHubError("GitHub returned invalid UTF-8 report content.") from exc
