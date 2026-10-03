import base64
import json
import subprocess

import pytest

from radar import github
from radar.__main__ import main


def fake_gh(monkeypatch, payload="", code=0, stderr=""):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        assert kwargs["timeout"] == 60
        assert kwargs["capture_output"] and not kwargs["check"]
        return subprocess.CompletedProcess(args, code, payload, stderr)

    monkeypatch.setattr(github.subprocess, "run", run)
    return calls


def test_status_filters_branch_and_dispatch(monkeypatch):
    calls = fake_gh(monkeypatch, json.dumps({"workflow_runs": [
        {"id": 12, "status": "completed", "conclusion": "success", "unwanted": "hidden"},
    ]}))
    result = github.status(ref="release")
    assert result["run"]["id"] == 12
    assert "unwanted" not in result["run"]
    assert "branch=release" in calls[0]
    assert "event=workflow_dispatch" in calls[0]
    assert "GET" in calls[0]


def test_no_runs_is_not_a_failure(monkeypatch):
    fake_gh(monkeypatch, '{"workflow_runs": []}')
    assert github.status()["run"] is None


@pytest.mark.parametrize("quick,value", [(True, "true"), (False, "false")])
def test_dispatch_204_and_exact_inputs(monkeypatch, quick, value):
    calls = fake_gh(monkeypatch)
    assert github.trigger(quick=quick)["dispatched"]
    assert len(calls) == 1
    assert "POST" in calls[0]
    assert "ref=main" in calls[0]
    assert f"inputs[skip_commoncrawl]={value}" in calls[0]


def test_report_decodes_utf8(monkeypatch, capsys):
    content = "# Positions\nNew †\n"
    calls = fake_gh(monkeypatch, json.dumps({
        "type": "file", "encoding": "base64",
        "content": base64.b64encode(content.encode()).decode() + "\n",
    }))
    assert main(["github", "report"]) == 0
    assert capsys.readouterr().out == content
    assert "contents/out/all_positions.md" in calls[0][2]


def test_trigger_requires_confirmation(monkeypatch):
    calls = fake_gh(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        main(["github", "trigger"])
    assert exc.value.code == 2
    assert not calls
    assert main(["github", "trigger", "--confirm", "--quick"]) == 0
    assert len(calls) == 1


@pytest.mark.parametrize("path", ["../secret.md", "out/../secret.md", "out/jobs.csv?ref=other", ".env"])
def test_report_path_restricted(monkeypatch, path):
    calls = fake_gh(monkeypatch)
    with pytest.raises(github.GitHubError):
        github.report(path)
    assert not calls


def test_repo_validation(monkeypatch):
    calls = fake_gh(monkeypatch)
    with pytest.raises(github.GitHubError):
        github.status("owner/repo?query=bad")
    assert not calls


@pytest.mark.parametrize("payload", ["not json", "[]", "{}", '{"workflow_runs": [null]}'])
def test_malformed_status(monkeypatch, payload):
    fake_gh(monkeypatch, payload)
    with pytest.raises(github.GitHubError):
        github.status()


@pytest.mark.parametrize("data", [
    {"type": "file", "encoding": "none"},
    {"type": "file", "encoding": "base64", "content": "!invalid!"},
    {"type": "file", "encoding": "base64", "content": None},
])
def test_malformed_report(monkeypatch, data):
    fake_gh(monkeypatch, json.dumps(data))
    with pytest.raises(github.GitHubError):
        github.report()


def test_auth_error_is_sanitized(monkeypatch, capsys):
    fake_gh(monkeypatch, code=1, stderr="HTTP 403 credential secret-value")
    assert main(["github", "status"]) == 1
    output = capsys.readouterr().err
    assert "reconnect" in output
    assert "secret-value" not in output


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("gh", 60)])
def test_missing_cli_and_timeout(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(github.subprocess, "run", fail)
    with pytest.raises(github.GitHubError):
        github.status()
