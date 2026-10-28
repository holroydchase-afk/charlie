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
