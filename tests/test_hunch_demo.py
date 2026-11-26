"""M3.2 Hunches in the public demo (CHL-HUNCH-DEMO-1, 2, 4, 6): failing-first tests, written by qa-tdd
before any product code. Acceptance criteria: PLAN.md, M3.2. The browser half (DEMO-3, 5 to 10) is in
tests/e2e/test_hunch_demo_e2e.py. Fictional data only (the sample person); nothing touches the network.

Spec change, not a weakening (Chase's call, Nov 23, "can we get it to the demo?"): the static half of
CHL-HUNCH-15 used to say "static mode answers 404 and has no Hunches tab". It is re-pinned in
tests/test_hunch.py and tests/e2e/test_hunch_e2e.py to this spec. What stays exactly as strict: static
mode never imports ``anthropic`` and never calls ``claude_client`` (DEMO-1 adds a spy and more banned
modules); what changes: static mode answers the hunch from the playbooks (200) and shows the view.

Pinned interface (the engineer builds to this; change it only by changing these tests first)
---------------------------------------------------------------------------------------------
* ``Api(static=True).hunch(text, risk)`` runs ``hunch.run_hunch(text, md, profile, level, client=None)``:
  playbooks only, ``hunch.claude_client`` is never looked up or called. Same 422 rules as the local app.
* ``tools/build_demo.MODULES`` includes ``"charlie/hunch.py"``.
* ``charlie.browser.prebuild(day)["levels"][str(L)]["hunch"]`` is a dict ``{text: body}`` with exactly
  one key, the hearing example text as written in web/app.js ``HUNCH_EXAMPLES.hearing``, whose body is
  what ``POST /api/hunch {"text": text, "risk": L}`` returns from the engine for the sample person at
  level L (L = 1 to 5). web/static.js serves it for ``POST /api/hunch`` through ``fromPrebuilt`` (so the
  same ``invalid_if_keys`` rule stops serving it once the visitor saves a profile, resume, position or screen).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from charlie import browser

ROOT = Path(__file__).resolve().parent.parent
DAY = "2026-10-22"
NFA = "Not financial advice. Paper trading only."
HEARING_FREE = ("Everyone wears earbuds all day now and OTC hearing aids are legal, "
                "so hearing health is about to become a huge consumer market.")
GIBBERISH = "Zorbly quandix flemwort will plonk the wibbertons."
BANNED_IN_STATIC = ("anthropic", "charlie.llm_profile", "requests", "charlie.server")


def _examples() -> dict:
    """web/app.js HUNCH_EXAMPLES: the texts the example buttons fill in (what the visitor actually runs)."""
    js = (ROOT / "web" / "app.js").read_text()
    m = re.search(r"const HUNCH_EXAMPLES = \{(.*?)\};", js, re.S)
    assert m, "web/app.js has no HUNCH_EXAMPLES"
    return dict(re.findall(r'(\w+):\s*"([^"]+)"', m.group(1)))


HEARING = _examples()["hearing"]
AI_POWER = _examples()["ai_power"]


class FakeStorage(dict):
    getItem = dict.get

    def setItem(self, k, v):
        assert isinstance(v, str)
        self[k] = v

    def removeItem(self, k):
        self.pop(k, None)


def _norm(x):
    return json.loads(json.dumps(x, allow_nan=False))


def _post_hunch(text, risk=None):
    body = {"text": text} if risk is None else {"text": text, "risk": risk}
    return json.loads(browser.request("POST", "/api/hunch", "{}", json.dumps(body)))


@pytest.fixture
def static(monkeypatch):
    """charlie.browser on fresh fake localStorage, as static.js starts it; the env it changes is restored."""
    monkeypatch.setenv("CHARLIE_DATA", "mock")
    monkeypatch.setenv("CHARLIE_LLM", "off")
    s = FakeStorage()
    browser.init(s, DAY)
    return s


@pytest.fixture
def claude_spy(monkeypatch):
    """Replaces hunch.claude_client with a recorder that would hand back a drafter if anyone asked."""
    from charlie import hunch
    calls = []

    class Drafter:
        def draft(self, text):
            calls.append(("draft", len(text)))
            return "{}"

    monkeypatch.setattr(hunch, "claude_client", lambda: calls.append("claude_client") or Drafter())
    return calls


def _build_demo():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    return build_demo


# ============================================================ CHL-HUNCH-DEMO-1 the static router runs playbooks only

def test_CHL_HUNCH_DEMO_1_static_router_answers_the_hearing_hunch_from_the_playbook(static, claude_spy):
    got = _post_hunch(HEARING, 2)
    assert got["status"] == 200, got
    body = got["body"]
    assert body["source"] == "playbook" and body["disclaimer"] == NFA
    assert 1 <= len(body["ideas"]) <= 3
    assert claude_spy == [], "static mode looked up or called claude_client"


def test_CHL_HUNCH_DEMO_1_static_never_asks_for_claude_even_with_the_llm_switched_on(monkeypatch, claude_spy):
    # Both directions of the CHL-HUNCH-13 rule: the local app asks claude_client when the LLM is on
    # (test_CHL_HUNCH_13_api_uses_claude_when_a_client_exists); the static demo never does, whatever the env.
    from charlie.browser_store import BrowserStore
    from charlie.data.market import MarketData
    from charlie.demo import sample_profile
    from charlie.handlers import Api
    monkeypatch.setenv("CHARLIE_LLM", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-not-a-key")
    day = date.fromisoformat(DAY)
    api = Api(BrowserStore(FakeStorage()), MarketData(mode="mock", today=day), static=True,
              default_profile=lambda level: sample_profile(day, level))
    status, body = api.route("POST", "/api/hunch", None, {"text": HEARING, "risk": 2})
    assert status == 200, body
    assert body["source"] == "playbook"
    assert claude_spy == []


def test_CHL_HUNCH_DEMO_1_fresh_process_keeps_claude_network_and_server_code_out():
    # A fresh interpreter with the LLM switched on and a placeholder key, so only static mode keeps them out.
    code = (
        "import sys, json; sys.path.insert(0, '.')\n"
        "import charlie.browser as b\n"
        "class S(dict):\n"
        "    getItem = dict.get\n"
        "    def setItem(self, k, v): self[k] = v\n"
        "    def removeItem(self, k): self.pop(k, None)\n"
        "b.init(S(), '2026-10-22')\n"
        "import charlie.hunch as h\n"
        "called = []\n"
        "h.claude_client = lambda: called.append(1)\n"
        f"r = json.loads(b.request('POST', '/api/hunch', '{{}}', json.dumps({{'text': {HEARING!r}, 'risk': 2}})))\n"
        f"bad = [m for m in {BANNED_IN_STATIC!r} if m in sys.modules]\n"
        "print(json.dumps({'status': r['status'], 'source': (r['body'] or {}).get('source'), 'bad': bad, "
        "'called': len(called)}))\n"
    )
    env = {**os.environ, "CHARLIE_DATA": "mock", "CHARLIE_LLM": "on", "ANTHROPIC_API_KEY": "placeholder-not-a-key"}
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                         timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res == {"status": 200, "source": "playbook", "bad": [], "called": 0}


# ============================================================ CHL-HUNCH-DEMO-2 the bundle

def test_CHL_HUNCH_DEMO_2_hunch_module_is_in_the_demo_bundle():
    assert "charlie/hunch.py" in _build_demo().MODULES


def test_CHL_HUNCH_DEMO_2_hunch_module_imports_nothing_the_demo_bans():
    # Guard (passes before the change, must keep passing): the same banned list as
    # tests/test_demo.py::test_demo_imports_no_server_network_or_llm_code, for charlie.hunch run with no client.
    code = ("import sys, datetime; sys.path.insert(0, '.')\n"
            "import charlie.hunch as h\n"
            "from charlie.data.market import MarketData\n"
            "from charlie.demo import sample_profile\n"
            "d = datetime.date(2026, 10, 22)\n"
            f"r = h.run_hunch({HEARING!r}, MarketData(mode='mock', today=d), sample_profile(d, 2), 2, client=None)\n"
            "assert r['source'] == 'playbook', r['source']\n"
            "bad = [m for m in ('requests', 'anthropic', 'fastapi', 'sqlite3', 'charlie.server', 'charlie.store', "
            "'charlie.chat', 'charlie.llm_profile', 'pypdf', 'docx') if m in sys.modules]; print(','.join(bad))")
    env = {**os.environ, "CHARLIE_DATA": "mock", "CHARLIE_LLM": "off"}
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == ""


def test_CHL_HUNCH_DEMO_2_built_zip_alone_runs_the_hunch(tmp_path):
    out = _build_demo().build(tmp_path / "site", day=DAY)
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import charlie.browser as b\n"
            "class S(dict):\n"
            "  getItem = dict.get\n"
            "  def setItem(self, k, v): self[k] = v\n"
            "  def removeItem(self, k): self.pop(k, None)\n"
            "b.init(S(), '2026-10-22')\n"
            f"r = json.loads(b.request('POST', '/api/hunch', '{{}}', json.dumps({{'text': {AI_POWER!r}}})))\n"
            "import charlie.hunch as h\n"
            "print(r['status'], (r['body'] or {}).get('source'), h.__file__)")
    r = subprocess.run([sys.executable, "-I", "-c", code, str(out / "charlie.zip")], capture_output=True, text=True,
                       cwd=tmp_path)
    assert r.returncode == 0, r.stderr[-2000:]
    status, source, path = r.stdout.split()
    assert status == "200" and source == "playbook" and "charlie.zip" in path


def test_CHL_HUNCH_DEMO_2_self_hosted_build_with_the_hunch_passes_check_site(tmp_path):
    bd = _build_demo()
    pkg = tmp_path / "pyodide-pkg"
    pkg.mkdir()
    for name in bd.PYODIDE_FILES:
        (pkg / name).write_text(f"// {name}\n")
    site = bd.build(tmp_path / "site", day=DAY, pyodide_dir=pkg)
    import zipfile
    with zipfile.ZipFile(site / "charlie.zip") as z:
        assert "charlie/hunch.py" in z.namelist(), "the check must actually scan the hunch module"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check_site.py"), str(site), "--no-cdn"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    # No new host: the allow-list is exactly what it was before M3.2.
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import check_site
    finally:
        sys.path.pop(0)
    assert check_site.ALLOWED == {"cdn.jsdelivr.net", "chaseholroyd.com", "www.w3.org"}


# ============================================================ CHL-HUNCH-DEMO-4 prebuilt hearing hunch + drift

@pytest.fixture(scope="module")
def pre():
    os.environ.setdefault("CHARLIE_DATA", "mock")
    return browser.prebuild(DAY)


def test_CHL_HUNCH_DEMO_4_prebuilt_holds_the_hearing_hunch_for_every_level(pre):
    assert sorted(pre["levels"]) == ["1", "2", "3", "4", "5"]
    for lvl, entries in pre["levels"].items():
        assert "hunch" in entries, f"level {lvl}: no prebuilt hunch"
        assert list(entries["hunch"]) == [HEARING], f"level {lvl}: keys {list(entries['hunch'])}"
        body = entries["hunch"][HEARING]
        assert body["source"] == "playbook" and body["disclaimer"] == NFA, lvl
        assert 1 <= len(body["ideas"]) <= 3, lvl
        for idea in body["ideas"]:
            assert idea["disclaimer"] == NFA
            if idea["trade"]:
                assert idea["trade"]["disclaimer"] == NFA


def test_CHL_HUNCH_DEMO_4_prebuilt_hunch_matches_what_pyodide_computes(pre, monkeypatch):
    # Drift test, like test_prebuilt_matches_what_pyodide_computes: same day, same sample person, same level.
    monkeypatch.setenv("CHARLIE_DATA", "mock")
    for lvl, entries in pre["levels"].items():
        s = FakeStorage()
        s.setItem("charlie:kv:sample_risk", lvl)
        browser.init(s, DAY)
        got = _post_hunch(HEARING, int(lvl))
        assert got["status"] == 200, (lvl, got)
        assert got["body"] == _norm(entries["hunch"][HEARING]), f"level {lvl}: prebuilt hunch drifted from the engine"


def test_CHL_HUNCH_DEMO_4_prebuilt_follows_the_risk_level(pre):
    # Not vacuous: the five prebuilt answers aren't one copy; the trades follow the level.
    trades = {lvl: sum(1 for i in e["hunch"][HEARING]["ideas"] if i["trade"]) for lvl, e in pre["levels"].items()}
    assert trades["5"] > trades["1"], trades


def test_CHL_HUNCH_DEMO_4_profile_and_resume_changes_stop_the_prebuilt_hunch(pre):
    # The prebuilt hunch rides the same switch as Today: once the visitor saves a profile or resume, static.js
    # stops serving prebuilt answers (browser half: test_CHL_HUNCH_DEMO_4_saved_profile_turns_off_the_prebuilt_map).
    assert {"charlie:kv:profile", "charlie:kv:intake"} <= set(pre["invalid_if_keys"])
    st = (ROOT / "web" / "static.js").read_text()
    assert "POST /api/hunch" in st, "static.js doesn't serve the prebuilt hunch"
    fn = st[st.index("function fromPrebuilt("):]
    fn = fn[:fn.index("\n  }\n")]
    assert fn.index("invalid_if_keys") < fn.index("POST /api/hunch"), \
        "the prebuilt hunch must be behind the invalid_if_keys check"


# ============================================================ CHL-HUNCH-DEMO-6 examples, free text, no match, limits

@pytest.mark.parametrize("text", [AI_POWER, HEARING_FREE], ids=["ai_power_example", "hearing_free_text"])
def test_CHL_HUNCH_DEMO_6_matching_text_maps_from_the_engine(static, claude_spy, text):
    got = _post_hunch(text, 2)
    assert got["status"] == 200, got
    assert got["body"]["source"] == "playbook" and got["body"]["chain"] and got["body"]["ideas"]
    assert claude_spy == []


def test_CHL_HUNCH_DEMO_6_unmatched_text_is_a_200_with_no_map(static, claude_spy):
    got = _post_hunch(GIBBERISH, 2)
    assert got["status"] == 200, got
    body = got["body"]
    assert body["source"] == "none" and body["message"]
    assert body["chain"] == [] and body["ideas"] == []
    assert claude_spy == []


@pytest.mark.parametrize("text,msg", [("", "Type a hunch first."), ("   ", "Type a hunch first."),
                                      ("x" * 601, "A hunch must be at most 600 characters.")],
                         ids=["empty", "blank", "601_chars"])
def test_CHL_HUNCH_DEMO_6_empty_or_too_long_is_422_with_the_message(static, text, msg):
    got = _post_hunch(text, 2)
    assert got["status"] == 422 and got["body"] == {"detail": msg}, got


def test_CHL_HUNCH_DEMO_6_600_characters_is_allowed_in_the_demo(static):
    text = ((HEARING_FREE + " ") * 10)[:600]
    assert _post_hunch(text, 2)["status"] == 200


# ============================================================ Round 5 showcase review fixes (static half)
# Failing-first, written by qa-tdd on Nov 23 from ux-reviewer round 5. Browser half: test_hunch_demo_e2e.py.

def _index() -> str:
    return (ROOT / "web" / "index.html").read_text()


def test_CHL_PS_H7_hunch_textarea_turns_autocomplete_off():
    # A hunch can hold something personal; the browser must not offer to remember it (CHL-PS-H7).
    m = re.search(r'<textarea[^>]*\bid="hunch-text"[^>]*>', _index())
    assert m, "no #hunch-text textarea"
    assert re.search(r'\bautocomplete="off"', m.group(0)), m.group(0)


def test_CHL_HUNCH_H27_switch_segments_are_not_link_styled_buttons():
    # The switch is a segmented control, not two buttons of different kinds: no segment wears btn-quiet, the
    # accent-and-underline "link" kind (DS-15 exempts .search-switch .seg like [role=tab]).
    segs = re.findall(r'<button[^>]*class="[^"]*\bseg\b[^"]*"[^>]*>', _index())
    assert len(segs) == 4, f"want 2 segments in each of the 2 switches, got {len(segs)}"
    quiet = [s for s in segs if re.search(r'class="[^"]*\bbtn-quiet\b', s)]
    assert quiet == [], f"segments styled as quiet (link) buttons: {quiet}"


def test_CHL_HUNCH_H30_paper_trade_toasts_name_the_trades_tab():
    js = (ROOT / "web" / "app.js").read_text()
    m = re.search(r"async function paperTrade\(.*?\n\}", js, re.S)
    assert m, "no paperTrade in web/app.js"
    body = m.group(0)
    assert "Paper portfolio" not in body, "the paper-trade toast still says 'Paper portfolio'; the tab is 'Trades'"
    assert "See it in Trades." in body
