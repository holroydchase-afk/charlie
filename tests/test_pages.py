"""M1.6 prep: a self-hosted Pyodide build and the Pages workflow (deploys only once the repo is public)."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / ".github" / "workflows" / "pages.yml"


def _build_demo():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    return build_demo


@pytest.fixture
def fake_pyodide(tmp_path):
    d = tmp_path / "pyodide-pkg"
    d.mkdir()
    for name in _build_demo().PYODIDE_FILES:
        (d / name).write_text(f"// {name} with a url https://docs.python.org/3/ inside\n")
    (d / "pyodide.d.ts").write_text("types we don't ship")
    return d


def _check(site, *flags):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "check_site.py"), str(site), *flags],
                          capture_output=True, text=True)


def test_self_hosted_build_copies_the_runtime_and_points_static_js_at_it(tmp_path, fake_pyodide):
    bd = _build_demo()
    out = bd.build(tmp_path / "site", day="2026-10-22", pyodide_dir=fake_pyodide)
    assert sorted(p.name for p in (out / "pyodide").iterdir()) == sorted(bd.PYODIDE_FILES)
    js = (out / "static.js").read_text()
    assert "cdn.jsdelivr.net" not in js and '"pyodide/"' in js
    r = _check(out, "--no-cdn")
    assert r.returncode == 0, r.stdout


def test_default_build_still_uses_the_cdn_and_fails_the_no_cdn_check(tmp_path):
    out = _build_demo().build(tmp_path / "site", day="2026-10-22")
    assert not (out / "pyodide").exists()
    assert "cdn.jsdelivr.net" in (out / "static.js").read_text()
    assert _check(out).returncode == 0
    r = _check(out, "--no-cdn")
    assert r.returncode == 1 and "cdn.jsdelivr.net" in r.stdout


def test_missing_runtime_file_fails_the_build(tmp_path, fake_pyodide):
    (fake_pyodide / "pyodide.asm.wasm").unlink()
    with pytest.raises(FileNotFoundError):
        _build_demo().build(tmp_path / "site", day="2026-10-22", pyodide_dir=fake_pyodide)


def test_site_check_still_scans_everything_outside_the_vendored_runtime(tmp_path, fake_pyodide):
    out = _build_demo().build(tmp_path / "site", day="2026-10-22", pyodide_dir=fake_pyodide)
    (out / "extra.js").write_text('fetch("https://tracker.example.net/x")\n')
    (out / "pyodide" / "hidden.js").write_text("anything")
    r = _check(out, "--no-cdn")
    assert r.returncode == 1 and "tracker.example.net" in r.stdout
    assert "pyodide/hidden.js: not a Pyodide runtime file" in r.stdout


def test_pages_workflow_deploys_main_after_ci_and_only_when_public():
    wf = PAGES.read_text()
    assert re.search(r"workflow_run:\s*\n\s*workflows: \[\"?CI\"?\]", wf)
    assert "branches: [main]" in wf
    assert "github.event.workflow_run.conclusion == 'success'" in wf
    assert "github.event.repository.private == false" in wf
    assert "--pyodide-dir" in wf and "check_site.py site --no-cdn" in wf
    assert "actions/deploy-pages" in wf


def test_pages_and_ci_pin_the_same_pyodide_version_as_static_js():
    version = re.search(r"pyodide/v([0-9.]+)/full/", (ROOT / "web" / "static.js").read_text()).group(1)
    for wf in (PAGES, ROOT / ".github" / "workflows" / "ci.yml"):
        assert f"pyodide@{version}" in wf.read_text(), wf.name
