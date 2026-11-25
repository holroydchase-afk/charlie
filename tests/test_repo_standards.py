"""CHL-M1.18 public repo standards (intake #61): failing-first tests, written by qa-tdd before any change.

Spec: docs/product/SPEC-REPO-STANDARDS.md, criteria CHL-RS-1 to 8 and 10 (auto). CHL-RS-9 and 11 are manual
(positioning copy check; GitHub description and topics on Chase's go) and are not tested here.
Reads files only; nothing touches the network or writes outside tmp_path.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GH = ROOT / ".github"
RULE = "Not financial advice. Paper trading only."

# Same pattern as the CI privacy check in .github/workflows/ci.yml (email part), built so this file never matches it.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+" + "@" + r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SECRET = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|AKIA[0-9A-Z]{16}")
CI_ALLOWED = re.compile("@" + r"(example\.(com|org)|anthropic\.com)|noreply" + "@")


def _text(p: Path) -> str:
    assert p.is_file(), f"{p.relative_to(ROOT)} is missing"
    return p.read_text(encoding="utf-8")


# ---- CHL-RS-1: community files at the root ----
@pytest.mark.parametrize("name", ["CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md"])
def test_CHL_RS_1_community_file_exists_and_not_empty(name):
    p = ROOT / name
    assert p.is_file(), f"{name} is missing from the repo root"
    assert p.read_text(encoding="utf-8").strip(), f"{name} is empty"


# ---- CHL-RS-2: the paper-only rule is the first thing under the title ----
def test_CHL_RS_2_readme_rule_line_first_after_title():
    lines = _text(ROOT / "README.md").splitlines()
    assert lines and lines[0].strip() == "# Charlie", f"README should open with '# Charlie', got {lines[:1]!r}"
    first = next((l for l in lines[1:] if l.strip()), "")
    assert RULE in first, f"First line after '# Charlie' must contain {RULE!r}; got {first[:120]!r}"


# ---- CHL-RS-3: what already passes stays (regression guard; green before and after) ----
def test_CHL_RS_3_ci_badge_license_dependabot_kept():
    readme = _text(ROOT / "README.md")
    assert re.search(r"\[!\[[^\]]*\]\([^)]*actions/workflows/ci\.yml/badge\.svg\)\]\([^)]*actions/workflows/ci\.yml\)",
                     readme), "README lost the CI badge linking to actions/workflows/ci.yml"
    assert (ROOT / "LICENSE").is_file() and (ROOT / "LICENSE").read_text().strip(), "LICENSE missing or empty"
    assert (GH / "dependabot.yml").is_file(), ".github/dependabot.yml missing"


# ---- CHL-RS-4: issue templates ----
def test_CHL_RS_4_issue_templates_bug_idea_and_config():
    d = GH / "ISSUE_TEMPLATE"
    assert d.is_dir(), ".github/ISSUE_TEMPLATE/ is missing"
    forms = [p for p in d.iterdir() if p.suffix in (".md", ".yml", ".yaml") and p.name != "config.yml"]
    assert any("bug" in p.stem.lower() for p in forms), f"no bug report template in {[p.name for p in forms]}"
    assert any(("idea" in p.stem.lower() or "feature" in p.stem.lower()) for p in forms), \
        f"no idea template in {[p.name for p in forms]}"
    cfg = d / "config.yml"
    assert cfg.is_file() and cfg.read_text().strip(), ".github/ISSUE_TEMPLATE/config.yml missing or empty"
    for p in forms:
        assert p.read_text(encoding="utf-8").strip(), f"{p.name} is empty"


# ---- CHL-RS-5: PR template matches agents-check and handoff-check ----
def test_CHL_RS_5_pr_template_has_agents_line_handoff_and_tests():
    text = _text(GH / "pull_request_template.md")
    # Same match as agents-check.yml: grep -iE '^[[:space:]>*_-]*agents:'
    assert re.search(r"^[ \t>*_-]*Agents:", text, re.M), "PR template needs a line starting 'Agents:'"
    assert "HANDOFF.md" in text, "PR template must remind to update HANDOFF.md"
    assert re.search(r"pytest|run the tests|tests? (pass|run|green)", text, re.I), \
        "PR template must remind to run the tests"


# ---- CHL-RS-6: no email in SECURITY / CODE_OF_CONDUCT; private reporting; privacy check pattern clean ----
@pytest.mark.parametrize("name", ["SECURITY.md", "CODE_OF_CONDUCT.md"])
def test_CHL_RS_6_no_email_and_private_reporting(name):
    text = _text(ROOT / name)
    assert not EMAIL.search(text), f"{name} holds an email address: {EMAIL.search(text).group(0)!r}"
    assert "[INSERT" not in text.upper(), f"{name} still has a template placeholder"
    assert re.search(r"private(ly)? (vulnerability )?report|report (it )?privately|security advisor", text, re.I), \
        f"{name} must send reports through GitHub private vulnerability reporting"


def test_CHL_RS_6_new_files_pass_ci_privacy_pattern():
    paths = [ROOT / n for n in ("CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md")]
    paths.append(GH / "pull_request_template.md")
    tpl = GH / "ISSUE_TEMPLATE"
    paths += sorted(tpl.iterdir()) if tpl.is_dir() else [tpl]
    hits = []
    for p in paths:
        for i, line in enumerate(_text(p).splitlines(), 1):
            if (SECRET.search(line) or EMAIL.search(line)) and not CI_ALLOWED.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    assert not hits, f"CI privacy check would fail on: {hits}"


# ---- CHL-RS-7: spike/ moved to tools/spike/, builder and log check follow ----
def test_CHL_RS_7_spike_moved_to_tools():
    assert not (ROOT / "spike").exists(), "spike/ is still at the repo root (move it to tools/spike/)"
    for name in ("index.html", "spike.js"):
        assert (ROOT / "tools" / "spike" / name).is_file(), f"tools/spike/{name} is missing"


def test_CHL_RS_7_build_spike_copies_from_tools_spike(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_spike
    finally:
        sys.path.pop(0)
    out = build_spike.build(tmp_path / "out")
    for name in ("index.html", "spike.js"):
        assert (out / name).read_bytes() == _text(ROOT / "tools" / "spike" / name).encode("utf-8"), \
            f"build_spike.py did not copy tools/spike/{name}"


def test_CHL_RS_7_studio_checks_log_roots_follow_the_move():
    roots = json.loads(_text(ROOT / "studio-checks.json"))["logs"]["roots"]
    assert "tools/spike" in roots, f"studio-checks.json logs.roots should scan tools/spike, has {roots}"
    missing = [r for r in roots if not (ROOT / r).exists()]
    assert not missing, f"studio-checks.json logs.roots point at missing paths: {missing}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_CHL_RS_7_check_logs_passes_over_configured_roots():
    r = subprocess.run(["node", "scripts/check-logs.mjs"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ---- CHL-RS-8: root docs stay; nothing points at the moved path ----
@pytest.mark.parametrize("name", ["CLAUDE.md", "HANDOFF.md", "PLAN.md"])
def test_CHL_RS_8_root_docs_stay(name):
    assert (ROOT / name).is_file(), f"{name} must stay at the repo root"


# Files that describe the move itself (the spec and the plan) may name the old path.
_MOVE_DOCS = {"docs/product/SPEC-REPO-STANDARDS.md", "PLAN.md", "tests/test_repo_standards.py"}
_OLD_SPIKE = [
    re.compile(r"(?<![\w./-])spike/"),          # `spike/`, spike/index.html (not tools/spike/ or build/spike/)
    re.compile(r"ROOT\s*/\s*[\"']spike[\"']"),  # ROOT / "spike" in Python
    re.compile(r"^\s*[\"']spike[\"'],?\s*$"),   # "spike" as a bare JSON list entry (studio-checks roots)
]


def _tracked_text_files():
    r = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    for rel in r.stdout.decode().split("\0"):
        if not rel or rel in _MOVE_DOCS or rel.startswith(("spike/", "tools/spike/")):
            continue
        p = ROOT / rel
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".pdf", ".docx", ".woff", ".woff2"):
            continue
        try:
            yield rel, p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue


def test_CHL_RS_8_nothing_points_at_old_spike_path():
    hits = []
    for rel, text in _tracked_text_files():
        for i, line in enumerate(text.splitlines(), 1):
            if any(rx.search(line) for rx in _OLD_SPIKE):
                hits.append(f"{rel}:{i}")
    assert not hits, f"these still point at the old root spike/ path: {hits}"


# ---- CHL-RS-10: CONTRIBUTING states the paper-only and personal-data rules ----
def test_CHL_RS_10_contributing_paper_only_and_education():
    text = _text(ROOT / "CONTRIBUTING.md").lower()
    assert "paper trading" in text and "education" in text, "CONTRIBUTING must say paper trading and education only"


def test_CHL_RS_10_contributing_declines_real_orders_and_broker_credentials():
    text = _text(ROOT / "CONTRIBUTING.md").lower()
    assert re.search(r"real(-|\s)(money\s)?(brokerage\s)?orders?", text), "CONTRIBUTING must name real-order code"
    assert "broker" in text and "credential" in text, "CONTRIBUTING must name broker-credential code"
    assert re.search(r"declin|not (be )?accept|won't (be )?(merge|accept)|will not (be )?(merge|accept)", text), \
        "CONTRIBUTING must say such PRs are declined"


def test_CHL_RS_10_contributing_keeps_resumes_and_personal_data_out():
    text = _text(ROOT / "CONTRIBUTING.md").lower()
    assert re.search(r"r[eé]sum[eé]s?", text), "CONTRIBUTING must mention resumes"
    assert "personal data" in text, "CONTRIBUTING must mention personal data"
    for where in ("issue", "test", "fixture"):
        assert where in text, f"CONTRIBUTING must say personal data never goes in {where}s"
