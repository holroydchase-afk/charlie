"""M1.1: the engine as the static demo runs it (Pyodide: no threads, no network, mock data)."""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from charlie import demo, engine

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "sample_ideas.json"
DAY = date(2026, 10, 22)


def test_sample_resume_is_the_fictional_sample_file():
    assert demo.SAMPLE_RESUME.strip() == (ROOT / "samples" / "sample_resume.txt").read_text().strip()


def test_engine_runs_without_threads(monkeypatch):
    def no_threads(*a, **k):
        raise RuntimeError("can't start new thread")
    monkeypatch.setattr(sys, "platform", "emscripten")
    monkeypatch.setattr(engine, "ThreadPoolExecutor", no_threads)
    out = demo.sample_ideas(DAY)
    assert 1 <= len(out["ideas"]) <= 3


def test_sample_ideas_match_golden():
    got = demo.summarize(demo.sample_ideas(DAY))
    assert got == json.loads(GOLDEN.read_text())


def test_summary_carries_disclaimer_and_mock_label():
    s = demo.summarize(demo.sample_ideas(DAY))
    assert s["disclaimer"] == "Not financial advice. Paper trading only."
    assert "mock" in s["data_source"]


def test_demo_imports_no_server_network_or_llm_code():
    code = ("import sys; sys.path.insert(0, '.'); import charlie.demo, datetime; charlie.demo.sample_ideas(datetime.date(2026, 10, 22)); "
            "bad = [m for m in ('requests', 'anthropic', 'fastapi', 'sqlite3', 'charlie.server', 'charlie.store', "
            "'charlie.chat', 'pypdf', 'docx') if m in sys.modules]; print(','.join(bad))")
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""


def test_spike_zip_holds_everything_the_demo_imports(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_spike
    finally:
        sys.path.pop(0)
    out = build_spike.build(tmp_path)
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import charlie.demo, json; "
            "s = json.loads(charlie.demo.ideas_json('2026-10-22'))['summary']; print(len(s['ideas']), charlie.demo.__file__)")
    r = subprocess.run([sys.executable, "-I", "-c", code, str(out / "charlie.zip")], capture_output=True, text=True,
                       cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    n, path = r.stdout.split()
    assert int(n) >= 1 and "charlie.zip" in path
