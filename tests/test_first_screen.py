"""M1.3: the demo's first screen is prebuilt JSON that matches what Pyodide computes later."""
import json
import sys
from datetime import date
from pathlib import Path

import pytest

from charlie import browser
from charlie.browser_store import BrowserStore
from charlie.data.market import MarketData
from charlie.demo import SAMPLE_LEVEL
from charlie.handlers import Api

ROOT = Path(__file__).resolve().parent.parent
DAY = "2026-10-22"


class FakeStorage(dict):
    getItem = dict.get

    def setItem(self, k, v):
        assert isinstance(v, str)
        self[k] = v

    def removeItem(self, k):
        self.pop(k, None)


@pytest.fixture(scope="module")
def pre():
    return browser.prebuild(DAY)


def _norm(x):
    return json.loads(json.dumps(x))


def test_prebuilt_shape(pre):
    assert pre["date"] == DAY and pre["default_risk"] == SAMPLE_LEVEL
    assert {"GET /api/meta", "GET /api/status", "GET /api/screens", "GET /api/paper"} <= set(pre["common"])
    assert sorted(pre["levels"]) == ["1", "2", "3", "4", "5"]
    for lvl, entries in pre["levels"].items():
        assert "GET /api/profile" in entries and "POST /api/profile/risk" in entries
        ideas = entries[f"GET /api/ideas?risk={lvl}&count=3"]
        assert ideas["ideas"], lvl
        for i in ideas["ideas"]:
            assert i["trade"]["disclaimer"] == "Not financial advice. Paper trading only."
            assert f"GET /api/ticker/{i['trade']['symbol']}?risk={lvl}" in entries
        assert entries["GET /api/profile"]["profile"]["risk_level"] == int(lvl)


def test_prebuilt_matches_what_pyodide_computes(pre):
    for lvl, entries in pre["levels"].items():
        s = FakeStorage()
        s.setItem("charlie:kv:sample_risk", lvl)
        browser.init(s, DAY)
        for key, body in {**pre["common"], **entries}.items():
            if key.startswith("POST ") or key == "chat":  # chat starters have their own parity test
                continue
            method, path = key.split(" ", 1)
            got = json.loads(browser.request(method, path))
            assert got["status"] == 200 and got["body"] == _norm(body), key


def test_risk_change_in_sample_mode_writes_only_the_sample_risk_key(pre):
    s = FakeStorage()
    browser.init(s, DAY)
    for lvl in range(1, 6):
        got = json.loads(browser.request("POST", "/api/profile/risk", "{}", json.dumps({"risk_level": lvl})))
        assert got["body"] == _norm(pre["levels"][str(lvl)]["POST /api/profile/risk"])
        assert s == {"charlie:kv:sample_risk": str(lvl)}  # what static.js writes on its fast path


def test_sample_person_is_the_default_profile():
    s = FakeStorage()
    browser.init(s, DAY)
    got = json.loads(browser.request("GET", "/api/profile"))["body"]
    assert got["saved"] is False and got["profile"]["name"] == "Alex Rivera (sample)"


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/profile", {"resume_text": "nurse"}),
    ("POST", "/api/screen", {"criteria": {}, "save": True, "name": "x"}),
])
def test_any_visitor_change_turns_off_the_prebuilt_answers(pre, method, path, body):
    s = FakeStorage()
    browser.init(s, DAY)
    assert json.loads(browser.request(method, path, "{}", json.dumps(body)))["status"] == 200
    assert any(k in s for k in pre["invalid_if_keys"])


def test_paper_trade_turns_off_the_prebuilt_answers(pre):
    s = FakeStorage()
    browser.init(s, DAY)
    trade = pre["levels"]["2"][f"GET /api/ideas?risk=2&count=3"]["ideas"][0]["trade"]
    assert json.loads(browser.request("POST", "/api/paper", "{}", json.dumps({"trade": trade})))["status"] == 200
    assert any(k in s for k in pre["invalid_if_keys"])


def test_non_static_api_keeps_the_generic_default_profile():
    api = Api(BrowserStore(FakeStorage()), MarketData(mode="mock", today=date(2026, 10, 22)))
    assert api.current_profile().name != "Alex Rivera (sample)"


def test_build_demo_writes_prebuilt_json_and_engine_status(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    out = build_demo.build(tmp_path / "site", day=DAY)
    pre = json.loads((out / "prebuilt.json").read_text())
    assert pre["date"] == DAY and pre["levels"]["2"]
    assert 'id="engine-status"' in (out / "index.html").read_text()


def test_app_starts_the_engine_after_first_render_and_shows_waits():
    js = (ROOT / "web" / "app.js").read_text()
    assert "charlieStatic?.start()" in js and "charlie:engine" in js
    st = (ROOT / "web" / "static.js").read_text()
    assert "prebuilt.json" in st and "invalid_if_keys" in st and "charlie:engine" in st


def test_chat_starter_chips_are_prebuilt_for_every_level(pre):
    import re
    html = (ROOT / "web" / "index.html").read_text()
    chips = re.findall(r'class="chip" data-q="([^"]+)"', html)
    assert chips and chips == browser.CHAT_STARTERS
    for lvl, entries in pre["levels"].items():
        assert sorted(entries["chat"]) == sorted(chips), lvl


def test_prebuilt_chat_answers_match_the_engine(pre):
    for lvl in ("1", "3"):
        s = FakeStorage()
        s.setItem("charlie:kv:sample_risk", lvl)
        browser.init(s, DAY)
        for q, body in pre["levels"][lvl]["chat"].items():
            got = json.loads(browser.request("POST", "/api/chat", "{}", json.dumps({"messages": [{"role": "user", "content": q}]})))
            assert got["status"] == 200 and got["body"] == _norm(body), q
            assert body["reply"].rstrip("_ \n").endswith("Not financial advice. Paper trading only.")


def test_static_js_serves_prebuilt_chat_only_for_a_first_question():
    st = (ROOT / "web" / "static.js").read_text()
    assert "POST /api/chat" in st and "messages.length === 1" in st
