"""M1.2: the browser adapter. Shared handlers, a localStorage store, and a static mode without network code."""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from charlie.browser_store import BrowserStore
from charlie.data.market import MarketData
from charlie.handlers import Api
from charlie.store import Store

ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 10, 22)


class FakeStorage:
    """The slice of window.localStorage the store uses."""

    def __init__(self):
        self.items = {}

    def getItem(self, k):
        return self.items.get(k)

    def setItem(self, k, v):
        assert isinstance(v, str)
        self.items[k] = v

    def removeItem(self, k):
        self.items.pop(k, None)


@pytest.fixture(scope="module")
def md():
    return MarketData(mode="mock", today=DAY, cache_dir="/tmp/charlie-test-cache")


@pytest.fixture(params=["sqlite", "browser"])
def store(request):
    return Store(":memory:") if request.param == "sqlite" else BrowserStore(FakeStorage())


def _trade(md):
    from charlie.strategies import build
    return build("shares", "KO", md.quote("KO")["price"], md.chain("KO"), 50000, 3)


# ------------------------------------------------------------------ store parity

def test_kv_roundtrip_and_delete(store):
    assert store.get("profile") is None and store.get("intake", {}) == {}
    store.put("profile", {"a": 1})
    assert store.get("profile") == {"a": 1}
    store.delete("profile")
    assert store.get("profile") is None


def test_screens_save_list_delete(store):
    a = store.save_screen("cheap", {"max_pe": 20})
    store.save_screen("quality", {"min_roic": 0.15})
    names = [s["name"] for s in store.screens()]
    assert sorted(names) == ["cheap", "quality"]
    assert all({"id", "name", "criteria", "created"} <= set(s) for s in store.screens())
    store.delete_screen(a["id"])
    assert [s["name"] for s in store.screens()] == ["quality"]


def test_daily_cache_and_clear(store):
    store.daily_put("2026-10-22", 2, "h", {"ideas": [1]})
    assert store.daily_get("2026-10-22", 2, "h") == {"ideas": [1]}
    assert store.daily_get("2026-10-22", 3, "h") is None
    store.clear_daily()
    assert store.daily_get("2026-10-22", 2, "h") is None


def test_positions_open_and_close(store, md):
    pos = store.open_position(_trade(md), "note")
    assert pos["status"] == "open" and pos["symbol"] == "KO" and pos["trade"]["symbol"] == "KO"
    assert isinstance(pos["entry_value"], float)
    assert [p["id"] for p in store.positions()] == [pos["id"]]
    closed = store.close_position(pos["id"], 123.0)
    assert closed["status"] == "closed" and closed["exit_value"] == 123.0 and closed["closed"]
    assert store.close_position(pos["id"], 1.0)["exit_value"] == 123.0  # closing twice changes nothing
    assert store.position("nope") is None


def test_browser_store_writes_only_prefixed_json_strings(md):
    s = FakeStorage()
    bs = BrowserStore(s)
    bs.put("profile", {"x": 1})
    bs.save_screen("s", {})
    bs.open_position(_trade(md))
    bs.daily_put("2026-10-22", 2, "h", {"ideas": []})
    assert s.items and all(k.startswith("charlie:") for k in s.items)
    for v in s.items.values():
        json.loads(v)


def test_browser_store_keeps_only_the_latest_day_of_ideas():
    bs = BrowserStore(FakeStorage())
    bs.daily_put("2026-10-21", 2, "h", {"d": 1})
    bs.daily_put("2026-10-22", 2, "h", {"d": 2})
    assert bs.daily_get("2026-10-21", 2, "h") is None
    assert bs.daily_get("2026-10-22", 2, "h") == {"d": 2}


def test_browser_store_survives_corrupt_storage():
    s = FakeStorage()
    s.items["charlie:screens"] = "{not json"
    assert BrowserStore(s).screens() == []


# ------------------------------------------------------------------ handler router

@pytest.fixture
def api(md):
    return Api(BrowserStore(FakeStorage()), md, static=True)


def test_router_matches_the_fastapi_endpoints(api, md, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from charlie import server
    monkeypatch.setattr(server, "store", Store(str(tmp_path / "r.db")))
    monkeypatch.setattr(server, "md", lambda: md)
    client = TestClient(server.app)
    for path in ("/api/meta", "/api/profile", "/api/screens", "/api/paper", "/api/ideas?count=2",
                 "/api/ticker/KO?risk=3"):
        status, body = api.route("GET", path)
        r = client.get(path)
        assert status == r.status_code == 200, path
        assert json.loads(json.dumps(body)) == r.json(), path  # the browser sends it as JSON too


def test_router_profile_save_get_delete(api):
    status, body = api.route("POST", "/api/profile", body={
        "resume_text": "Registered nurse at HCA Healthcare", "interests": "biotech", "capital": "30000",
        "risk_level": "2", "holdings": "KO:10"})
    assert status == 200 and body["resume_chars"] > 0
    got = api.route("GET", "/api/profile")[1]
    assert got["saved"] is True and "resume_text" not in got["intake"]
    assert got["profile"]["holdings"] == {"KO": 10}
    assert api.route("DELETE", "/api/profile") == (200, {"ok": True})
    assert api.route("GET", "/api/profile")[1]["saved"] is False


def test_router_ideas_trade_and_paper(api):
    status, ideas = api.route("GET", "/api/ideas", query={"risk": "2", "count": "3"})
    assert status == 200 and 1 <= len(ideas["ideas"]) <= 3
    trade = ideas["ideas"][0]["trade"]
    assert trade["disclaimer"] == "Not financial advice. Paper trading only."
    status, pos = api.route("POST", "/api/paper", body={"trade": trade})
    assert status == 200
    status, closed = api.route("POST", f"/api/paper/{pos['id']}/close")
    assert status == 200 and closed["status"] == "closed"


def test_router_errors(api):
    assert api.route("GET", "/api/ticker/ZZZZ")[0] == 404
    assert api.route("GET", "/api/nope")[0] == 404
    assert api.route("POST", "/api/paper", body={"trade": {}})[0] == 400
    assert api.route("POST", "/api/paper/none/close")[0] == 404
    assert api.route("POST", "/api/chat", body={"messages": []})[0] == 400
    status, body = api.route("GET", "/api/ticker/ZZZZ")
    assert "detail" in body


def test_router_risk_and_screens(api):
    assert api.route("POST", "/api/profile/risk", body={"risk_level": 9})[1]["risk_level"] == 5
    status, res = api.route("POST", "/api/screen", body={"criteria": {}, "save": True, "name": "mine"})
    assert status == 200 and res["saved"]["name"] == "mine"
    sid = api.route("GET", "/api/screens")[1]["screens"][0]["id"]
    api.route("DELETE", f"/api/screens/{sid}")
    assert api.route("GET", "/api/screens")[1]["screens"] == []


def test_static_mode_status_and_rule_based_chat(api, monkeypatch):
    monkeypatch.setenv("CHARLIE_LLM", "on")  # even with an LLM configured, static mode never calls it
    status = api.route("GET", "/api/status")[1]
    assert status["static"] is True and status["llm"] is False and status["data"]["mode"] == "mock"
    status, out = api.route("POST", "/api/chat", body={"messages": [{"role": "user", "content": "Tell me about Visa"}]})
    assert status == 200 and out["reply"].rstrip("_ \n").endswith("Not financial advice. Paper trading only.")


def test_static_profile_ignores_ai_opt_in(api, monkeypatch):
    import charlie.llm_profile as llm
    monkeypatch.setattr(llm, "enrich", lambda *a, **k: pytest.fail("static mode must not call Claude"))
    assert api.route("POST", "/api/profile", body={"resume_text": "nurse", "use_ai": "on"})[0] == 200


# ------------------------------------------------------------------ static entry point

def test_browser_entry_imports_no_network_llm_or_sqlite_code():
    code = ("import sys, json; sys.path.insert(0, '.'); import charlie.browser as b\n"
            "class S(dict):\n"
            "  getItem = dict.get\n"
            "  def setItem(self, k, v): self[k] = v\n"
            "  def removeItem(self, k): self.pop(k, None)\n"
            "b.init(S(), '2026-10-22')\n"
            "for p in ('/api/status', '/api/ideas', '/api/ticker/KO', '/api/paper'):\n"
            "  assert json.loads(b.request('GET', p, '{}', 'null'))['status'] == 200, p\n"
            "r = json.loads(b.request('POST', '/api/chat', '{}', json.dumps({'messages': [{'role': 'user', 'content': 'hi'}]})))\n"
            "assert r['status'] == 200\n"
            "bad = [m for m in ('requests', 'anthropic', 'fastapi', 'sqlite3', 'charlie.server', 'charlie.llm_profile', "
            "'charlie.data.cboe', 'charlie.data.sec', 'pypdf', 'docx') if m in sys.modules]; print(','.join(bad))")
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == ""


def test_app_js_routes_api_through_python_when_static():
    js = (ROOT / "web" / "app.js").read_text()
    head = js[js.index("async function api("):]
    head = head[:head.index("\n}\n")]
    assert "window.charlieStatic" in head and "fetch(" in head


def test_demo_site_has_static_loader_and_every_module_the_browser_imports(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    out = build_demo.build(tmp_path / "site")
    html = (out / "index.html").read_text()
    assert html.index('src="static.js"') < html.index('src="app.js"') and "/static/" not in html
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import charlie.browser as b\n"
            "class S(dict):\n"
            "  getItem = dict.get\n"
            "  def setItem(self, k, v): self[k] = v\n"
            "  def removeItem(self, k): self.pop(k, None)\n"
            "b.init(S(), '2026-10-22')\n"
            "print(json.loads(b.request('GET', '/api/ideas'))['status'], b.__file__)")
    r = subprocess.run([sys.executable, "-I", "-c", code, str(out / "charlie.zip")], capture_output=True, text=True,
                       cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    status, path = r.stdout.split()
    assert status == "200" and "charlie.zip" in path
