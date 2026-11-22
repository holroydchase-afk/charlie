"""Studio checks from holroydchase-afk/studio-agents, run with the normal test command."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_agent_roster_matches_claude_md():
    # Every .claude/agents/*.md is in the CLAUDE.md table and every table row has a file.
    r = subprocess.run(["bash", "scripts/check-agents.sh"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_agent_roster_check_catches_drift(tmp_path):
    # An agent file with no CLAUDE.md row must fail the check.
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "check-agents.sh", tmp_path / "scripts")
    shutil.copy(ROOT / "CLAUDE.md", tmp_path)
    shutil.copytree(ROOT / ".claude" / "agents", tmp_path / ".claude" / "agents")
    (tmp_path / ".claude" / "agents" / "ghost.md").write_text("---\nname: ghost\n---\n")
    r = subprocess.run(["bash", "scripts/check-agents.sh"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 1
    assert "ghost" in r.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_logs_never_print_secrets_or_personal_data():
    # console.* calls in web/ and spike/ never log keys, URLs, emails, resumes or raw errors.
    r = subprocess.run(["node", "scripts/check-logs.mjs"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ---- SPEC-STUDIO-AGENTS (issue #51): wire Charlie to studio-agents --as / agent-prompt.sh ----
import os
import re


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _temp_repo(tmp_path, branch="feat/x"):
    # A throwaway git repo with this repo's scripts and agent files, so nothing writes ROOT/.claude/agent-runs/.
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "checkout", "-q", "-b", branch)
    shutil.copytree(ROOT / "scripts", repo / "scripts")
    shutil.copytree(ROOT / ".claude" / "agents", repo / ".claude" / "agents")
    return repo


def _log_lines(repo, name="feat-x.log"):
    p = repo / ".claude" / "agent-runs" / name
    return p.read_text().splitlines() if p.exists() else []


def _studio_section(text):
    m = re.search(r"^## Studio agents.*?(?=^## |\Z)", text, re.S | re.M)
    assert m, "CLAUDE.md has no '## Studio agents' section"
    return m.group(0)


def test_SA1_agent_prompt_builds_qa_tdd_prompt():
    assert (ROOT / "scripts" / "agent-prompt.sh").is_file(), "scripts/agent-prompt.sh is missing (run studio-agents sync.sh)"
    r = subprocess.run(["bash", "scripts/agent-prompt.sh", "qa-tdd", "test"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "You are acting as the studio agent qa-tdd" in r.stdout
    assert "log-agent-run.sh --as qa-tdd" in r.stdout
    assert r.stdout.rstrip().endswith("test")


@pytest.mark.parametrize("agent", ["ghost", "../x"])
def test_SA2_agent_prompt_rejects_unknown_or_bad_agent(agent):
    assert (ROOT / "scripts" / "agent-prompt.sh").is_file(), "scripts/agent-prompt.sh is missing (run studio-agents sync.sh)"
    r = subprocess.run(["bash", "scripts/agent-prompt.sh", agent, "test"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0, r.stdout


def test_SA3_log_agent_run_as_logs_via_general_purpose(tmp_path):
    repo = _temp_repo(tmp_path)
    r = subprocess.run(["bash", "scripts/log-agent-run.sh", "--as", "qa-tdd"], cwd=repo, input="",
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = _log_lines(repo)
    assert len(lines) == 1, f"expected exactly one log line, got {lines!r}"
    assert re.fullmatch(r"\S+Z qa-tdd via-general-purpose", lines[0]), lines[0]


@pytest.mark.parametrize("agent", ["ghost", "Bad Name"])
def test_SA4_log_agent_run_as_rejects_unknown_or_bad_agent(tmp_path, agent):
    repo = _temp_repo(tmp_path)
    r = subprocess.run(["bash", "scripts/log-agent-run.sh", "--as", agent], cwd=repo, input="",
                       capture_output=True, text=True, timeout=30)
    assert r.returncode != 0, "log-agent-run.sh --as must fail for an unknown or malformed agent"
    runs = repo / ".claude" / "agent-runs"
    written = [l for p in runs.glob("*.log") for l in p.read_text().splitlines()] if runs.exists() else []
    assert written == [], written


def _check_runs_dir(tmp_path, log_text):
    # No studio-checks.json here, so check-agent-runs.sh does not rerun the suite.
    d = tmp_path / "ck"
    shutil.copytree(ROOT / "scripts", d / "scripts")
    shutil.copytree(ROOT / ".claude" / "agents", d / ".claude" / "agents")
    (d / ".claude" / "agent-runs").mkdir()
    (d / ".claude" / "agent-runs" / "feat-x.log").write_text(log_text)
    return d


def test_SA5_check_agent_runs_accepts_via_general_purpose(tmp_path):
    d = _check_runs_dir(tmp_path, "2026-11-22T00:00:00Z qa-tdd via-general-purpose\n")
    env = dict(os.environ, BODY="Agents: qa-tdd red then green", HEAD_REF="feat/x")
    r = subprocess.run(["bash", "scripts/check-agent-runs.sh"], cwd=d, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_SA5_check_agent_runs_fails_when_qa_tdd_missing(tmp_path):
    d = _check_runs_dir(tmp_path, "2026-11-22T00:00:00Z staff-pm via-general-purpose\n")
    env = dict(os.environ, BODY="Agents: qa-tdd red then green", HEAD_REF="feat/x")
    r = subprocess.run(["bash", "scripts/check-agent-runs.sh"], cwd=d, env=env, capture_output=True, text=True)
    assert r.returncode != 0
    assert "qa-tdd" in r.stdout + r.stderr


def test_SA6_agents_check_workflow_wires_run_log_and_no_skip_rule():
    wf = (ROOT / ".github" / "workflows" / "agents-check.yml").read_text()
    assert "qa-tdd cannot be skipped" in wf
    assert "scripts/check-agent-runs.sh" in wf
    versions = re.findall(r"actions/checkout@(\S+)", wf)
    assert versions and all(v == "v7" for v in versions), versions


def test_SA7_claude_md_studio_section_matches_template():
    text = (ROOT / "CLAUDE.md").read_text()
    assert "is not wired yet" not in text
    assert "scripts/agent-prompt.sh" in text
    assert "log-agent-run.sh --as" in text
    section = _studio_section(text)
    for sentence in [
        "**Open every thread the same way.**",
        "**Agents come from studio-agents, never your own copy.**",
        "run it as `general-purpose` with the prompt from `bash scripts/agent-prompt.sh <agent> \"<task>\"`; that subagent logs itself with `bash scripts/log-agent-run.sh --as <agent>`.",
        "\"qa-tdd skipped\" is only allowed for docs-only or config-only PRs, and agents-check fails any other.",
        "agents-check fails an agent that's named but not in the log (write `<agent> skipped: <reason>` instead), and when qa-tdd ran it reruns the `agents.verify` command from `studio-checks.json` 3x on CI.",
        "| Before any publish or release (npm, plugin, store, deploy tag); after a version bump | `release-captain` |",
    ]:
        assert sentence in section, f"Studio agents section is missing template text: {sentence[:70]}"


def test_SA7_release_captain_synced_from_studio_agents():
    assert (ROOT / ".claude" / "agents" / "release-captain.md").is_file(), "release-captain.md not synced"
