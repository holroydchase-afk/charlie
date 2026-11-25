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


# ---------------------------------------------------------------- CHL-PS17 / CHL-UX43b: who may deploy
def _gh_eval(expr, ctx):
    """A small evaluator for the GitHub Actions expression subset pages.yml uses: dotted context paths,
    'strings', true/false/null, == != ! && || and parentheses, with GitHub's loose equality
    (strings compare case-insensitively; mixed types compare as numbers; a missing property is null)."""
    toks = re.findall(r"\s*(\|\||&&|==|!=|!|\(|\)|'(?:[^']|'')*'|[A-Za-z_][\w.-]*|-?\d+(?:\.\d+)?)", expr)
    assert "".join(toks).replace(" ", "") == re.sub(r"\s+", "", expr), f"unparsed: {expr}"
    toks = [t.strip() for t in toks]
    pos = 0

    def num(v):
        if v is None: return 0.0
        if isinstance(v, bool): return float(v)
        if isinstance(v, (int, float)): return float(v)
        try: return float(v) if v.strip() else 0.0
        except (ValueError, AttributeError): return float("nan")

    def eq(a, b):
        if isinstance(a, str) and isinstance(b, str): return a.lower() == b.lower()
        if type(a) is type(b) and not isinstance(a, (int, float, str, bool)) and a is not None: return a is b
        return num(a) == num(b)

    def truthy(v):
        return not (v is None or v is False or v == 0 or v == "")

    def atom():
        nonlocal pos
        t = toks[pos]; pos += 1
        if t == "(":
            v = orx(); assert toks[pos] == ")"; pos += 1; return v
        if t == "!": return not truthy(atom())
        if t.startswith("'"): return t[1:-1].replace("''", "'")
        if t in ("true", "false"): return t == "true"
        if t == "null": return None
        if re.match(r"-?\d", t): return float(t)
        v = ctx
        for part in t.split("."):
            v = v.get(part) if isinstance(v, dict) else None
        return v

    def cmp():
        nonlocal pos
        v = atom()
        while pos < len(toks) and toks[pos] in ("==", "!="):
            op = toks[pos]; pos += 1
            r = eq(v, atom()); v = r if op == "==" else not r
        return v

    def andx():
        nonlocal pos
        v = cmp()
        while pos < len(toks) and toks[pos] == "&&":
            pos += 1; r = cmp(); v = r if truthy(v) else v
        return v

    def orx():
        nonlocal pos
        v = andx()
        while pos < len(toks) and toks[pos] == "||":
            pos += 1; r = andx(); v = v if truthy(v) else r
        return v

    out = orx()
    assert pos == len(toks), f"trailing tokens in {expr}"
    return truthy(out)


def _jobs():
    """Each job in pages.yml, read without a YAML library (CI installs only requirements.txt):
    {name: {"if": folded or inline expr or None, "needs": [..], "uses": [..], "lines": [..]}}."""
    lines = PAGES.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l == "jobs:")
    jobs, name = {}, None
    for line in lines[start + 1:]:
        if line.strip() and not line.startswith(" "):
            break
        m = re.match(r"^  ([\w-]+):\s*$", line)
        if m:
            name = m.group(1)
            jobs[name] = {"lines": []}
        elif name:
            jobs[name]["lines"].append(line)
    for job in jobs.values():
        body, expr = job["lines"], None
        for i, line in enumerate(body):
            f = re.match(r"^    if: >-\s*$", line)
            if f:
                expr = " ".join(n.strip() for n in body[i + 1:][:next(
                    (k for k, n in enumerate(body[i + 1:]) if n.strip() and len(n) - len(n.lstrip()) <= 4),
                    len(body))] if n.strip())
            elif re.match(r"^    if:\s*\S", line):
                expr = line.split("if:", 1)[1].strip()
        job["if"] = expr
        needs = next((l.split("needs:", 1)[1].strip() for l in body if re.match(r"^    needs:", l)), None)
        job["needs"] = [n.strip() for n in needs.strip("[]").split(",") if n.strip()] if needs else []
        job["uses"] = [re.sub(r"@.*", "", u) for u in re.findall(r"uses:\s*(\S+)", "\n".join(body))]
    return jobs


def _job_using(action):
    hits = [n for n, j in _jobs().items() if action in j["uses"]]
    assert len(hits) == 1, f"expected exactly one job using {action}, found {hits}"
    return hits[0]


def _pages():
    """The build job's `if:` (the job that uploads the Pages artifact carries the folded guard) and the
    `on.schedule` crons, read from pages.yml without a YAML library. Returns yaml.safe_load-like shapes."""
    lines = PAGES.read_text().splitlines()
    crons = []
    for line in lines:
        c = re.match(r"^\s*-\s*cron:\s*[\"']([^\"']+)[\"']", line)
        if c:
            crons.append({"cron": c.group(1)})
    expr = _jobs()[_job_using("actions/upload-pages-artifact")]["if"]
    assert expr, "pages.yml build job has no folded `if: >-` expression"
    on = {"schedule": crons} if crons else {}
    return {"jobs": {"build": {"if": expr}}}, on


def _deploys(event_name, repo="holroydchase-afk/charlie", private=False, run=None):
    wf, _ = _pages()
    expr = wf["jobs"]["build"]["if"]
    expr = re.sub(r"^\$\{\{(.*)\}\}$", r"\1", expr.strip(), flags=re.S)
    event = {"repository": {"private": private, "full_name": repo}}
    if run is not None:
        event["workflow_run"] = run
    return _gh_eval(expr, {"github": {"event_name": event_name, "repository": repo, "event": event}})


def _run(event="push", head_repo="holroydchase-afk/charlie", conclusion="success", branch="main"):
    return {"event": event, "conclusion": conclusion, "head_branch": branch,
            "head_repository": {"full_name": head_repo}, "repository": {"full_name": "holroydchase-afk/charlie"}}


def test_CHL_PS17_evaluator_matches_todays_workflow_for_the_allowed_cases():
    # Sanity for the evaluator itself: the current file already deploys a push to main and a dispatch.
    assert _deploys("workflow_run", run=_run()) is True
    assert _deploys("workflow_dispatch") is True
    assert _deploys("workflow_run", run=_run(conclusion="failure")) is False
    assert _deploys("workflow_run", private=True, run=_run()) is False


def test_CHL_PS17_a_fork_pull_request_from_a_branch_named_main_does_not_deploy():
    # CI runs for a fork's PR; its workflow_run has head_branch "main" and passes the branches filter.
    assert _deploys("workflow_run", run=_run(event="pull_request", head_repo="mallory/charlie")) is False, \
        "build.if must require github.event.workflow_run.event == 'push'"
    assert _deploys("workflow_run", run=_run(event="push", head_repo="mallory/charlie")) is False, \
        "build.if must require github.event.workflow_run.head_repository.full_name == github.repository"
    assert _deploys("workflow_run", run=_run(event="pull_request")) is False, "a same-repo PR run must not deploy"
    assert _deploys("workflow_run", run=_run()) is True


def test_CHL_UX43b_pages_rebuilds_weekly_but_only_on_chases_repo():
    _, on = _pages()
    crons = [s.get("cron") for s in (on.get("schedule") or [])]
    assert crons and all(isinstance(c, str) and len(c.split()) == 5 for c in crons), \
        "pages.yml needs a weekly schedule: cron so the demo's sample market day stays fresh"
    weekday = crons[0].split()[4]
    assert weekday not in ("*",) and crons[0].split()[2] == "*", f"cron {crons[0]!r} is not weekly"
    assert _deploys("schedule", repo="holroydchase-afk/charlie") is True, "a schedule run on Chase's repo deploys"
    assert _deploys("schedule", repo="someone/charlie") is False, \
        "a schedule run on a fork must not deploy (github.repository == 'holroydchase-afk/charlie')"


# ---------------------------------------------------------------- CHL-PAGES-SPLIT: deploy-pages finds 0 artifacts
# Since Nov 24 deploy-pages@v5 in the same job right after upload-pages-artifact@v5 finds no artifact.
# Fix: a guarded `build` job uploads, a separate `deploy` job (needs: build) deploys.
def test_CHL_PAGES_SPLIT_a_upload_runs_in_the_guarded_build_job():
    jobs = _jobs()
    up = _job_using("actions/upload-pages-artifact")
    assert up == "build", f"upload-pages-artifact runs in job {up!r}; it must be the `build` job"
    guard = jobs[up]["if"] or ""
    for clause in ("github.event.repository.private == false",
                   "github.event.workflow_run.event == 'push'",
                   "github.event.workflow_run.head_repository.full_name == github.repository",
                   "github.repository == 'holroydchase-afk/charlie'"):
        assert clause in guard, f"build job's guard lost {clause!r}"
    assert "actions/configure-pages" in jobs[up]["uses"] and "actions/checkout" in jobs[up]["uses"]
    text = "\n".join(jobs[up]["lines"])
    assert "check_site.py site --no-cdn" in text and "github.event.workflow_run.head_sha" in text


def test_CHL_PAGES_SPLIT_b_deploy_is_its_own_job_that_needs_build():
    up, dep = _job_using("actions/upload-pages-artifact"), _job_using("actions/deploy-pages")
    assert dep != up, f"deploy-pages runs in the same job as upload-pages-artifact ({up!r}); it finds 0 artifacts"
    assert _jobs()[dep]["needs"] == ["build"], f"job {dep!r} must have `needs: build`"
    text = "\n".join(_jobs()[dep]["lines"])
    assert "name: github-pages" in text and "steps.deployment.outputs.page_url" in text
    assert re.search(r"id: deployment\s*\n\s*uses: actions/deploy-pages@v5", text)


def test_CHL_PAGES_SPLIT_c_deploy_has_no_if_that_bypasses_the_build_guard():
    dep = _jobs()[_job_using("actions/deploy-pages")]
    expr = dep["if"] or ""
    assert "always()" not in expr and "cancelled()" not in expr, f"deploy if: {expr!r} bypasses build's guard"
    assert dep["if"] is None, f"deploy should rely on needs: build, not its own if: {expr!r}"


def test_CHL_PAGES_SPLIT_d_a_new_run_never_cancels_a_deploy_midway():
    wf = PAGES.read_text()
    m = re.search(r"^concurrency:\s*\n((?:[ ]+.*\n)+)", wf, flags=re.M)
    assert m, "pages.yml needs a top-level concurrency block"
    c = re.search(r"cancel-in-progress:\s*(\S+)", m.group(1))
    assert c and c.group(1) == "false", f"concurrency.cancel-in-progress is {c and c.group(1)!r}; must be false"
