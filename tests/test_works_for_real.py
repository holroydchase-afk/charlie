"""M1.10 Works for real: failing-first tests for CHL-R1 to CHL-R8.

Acceptance criteria live in the appendix of docs/plans/2026-10-28-release.md.
Live mode never touches the network here: the Cboe fetchers are monkeypatched to serve the saved
ABT payload for "live" symbols and a 403 for the rest, which makes MarketData fall back to mock
per symbol, exactly like FI and EA did on Oct 28.
"""
import json
import logging
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from charlie.browser_store import BrowserStore
from charlie.data import cboe
from charlie.data.market import MarketData
from charlie.handlers import Api
from charlie.store import Store

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures" / "cboe"
DAY = date(2026, 10, 22)
LIVE_DAY = date(2026, 10, 28)  # the Cboe fixture was saved this day


class FakeStorage:
    def __init__(self):
        self.items = {}

    def getItem(self, k):
        return self.items.get(k)

    def setItem(self, k, v):
        self.items[k] = v

    def removeItem(self, k):
        self.items.pop(k, None)


def _payload(kind):
    return json.loads((FIX / f"{kind}_ABT.json").read_text())


def live_market(monkeypatch, tmp_path, blocked=(), all_blocked=False):
    """Auto mode with no network: every symbol gets the saved ABT payload, except `blocked`
    symbols, which get Cboe's 403 and so fall back to labeled mock data."""
    import requests

    blocked = {s.upper() for s in blocked}

    def forbid(sym):
        r = requests.Response()
        r.status_code, r.url = 403, f"https://cdn-api.cboe.com/x/{sym}.json"
        r.raise_for_status()

    def fetch(kind):
        def f(sym):
            if all_blocked or sym.upper() in blocked:
                forbid(sym)
            return _payload(kind)
        return f

    monkeypatch.setattr(cboe, "fetch_options", fetch("options"))
    monkeypatch.setattr(cboe, "fetch_history", fetch("history"))
    monkeypatch.delenv("CHARLIE_SEC_UA", raising=False)  # SEC fundamentals off, so no SEC call either
    return MarketData(mode="auto", today=LIVE_DAY, cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def mock_md(tmp_path):
    return MarketData(mode="mock", today=DAY, cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def client(tmp_path, monkeypatch, mock_md):
    """FastAPI with a temp SQLite store and a mock market; server errors come back as 500s."""
    from charlie import server
    monkeypatch.setattr(server, "store", Store(str(tmp_path / "t.db")))
    monkeypatch.setattr(server, "md", lambda: mock_md)
    return TestClient(server.app, base_url="http://127.0.0.1:8000", raise_server_exceptions=False)


@pytest.fixture
def static_api(mock_md):
    """The browser router (static demo), on a localStorage-shaped store."""
    return Api(BrowserStore(FakeStorage()), mock_md, static=True)


def _post_screen(client_or_api, criteria):
    if isinstance(client_or_api, Api):
        return client_or_api.route("POST", "/api/screen", body={"criteria": criteria})
    r = client_or_api.post("/api/screen", json={"criteria": criteria})
    return r.status_code, _body(r)


def _body(r):
    """JSON body, or {"detail": <text>} for a plain-text 500, so a red test shows the status, not a decode error."""
    try:
        return r.json()
    except ValueError:
        return {"detail": r.text}


def _real_trade(md, symbol="KO", strategy="shares", capital=25000, level=3):
    from charlie.strategies import build
    return build(strategy, symbol, md.quote(symbol)["price"], md.chain(symbol), capital, level)


# ============================================================ CHL-R1 unknown symbols in a list screen

@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_R1_list_screen_with_unknown_symbol_returns_200(via, client, static_api):
    target = client if via == "client" else static_api
    status, body = _post_screen(target, {"scope": "list", "symbols": ["ZZZZ", "AAPL"], "min_score": 0})
    assert status == 200, body
    assert body["unknown_symbols"] == ["ZZZZ"]
    assert body["results"], "the known symbol should still get rows"
    assert {r["symbol"] for r in body["results"]} == {"AAPL"}


@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_R1_list_screen_with_only_unknown_symbols_returns_empty_200(via, client, static_api):
    target = client if via == "client" else static_api
    status, body = _post_screen(target, {"scope": "list", "symbols": ["ZZZZ", "XYZQ"]})
    assert status == 200, body
    assert body["results"] == []
    assert body["unknown_symbols"] == ["ZZZZ", "XYZQ"]


# ============================================================ CHL-R2 data-source label

def test_CHL_R2_empty_screen_is_not_labeled_live(client):
    status, body = _post_screen(client, {"domains": ["nope"]})
    assert status == 200
    assert body["results"] == []
    assert not body["data_source"].startswith("live"), body["data_source"]
    assert body["data_source"].startswith("mock")  # the market mode, since nothing was analyzed


def test_CHL_R2_all_live_screen_labels_live_and_rows_carry_price_source(monkeypatch, tmp_path):
    md = live_market(monkeypatch, tmp_path)
    api = Api(Store(":memory:"), md)
    status, body = api.route("POST", "/api/screen", body={"criteria": {"scope": "list", "symbols": ["ABT", "KO"], "min_score": 0}})
    assert status == 200
    assert body["data_source"] == "live (delayed)"
    assert body["results"]
    assert all(r["price_source"] == "cboe (delayed)" for r in body["results"])


def test_CHL_R2_all_mock_in_auto_mode_labels_mock(monkeypatch, tmp_path):
    md = live_market(monkeypatch, tmp_path, all_blocked=True)
    api = Api(Store(":memory:"), md)
    status, body = api.route("POST", "/api/screen", body={"criteria": {"scope": "list", "symbols": ["ABT", "KO"], "min_score": 0}})
    assert status == 200
    assert body["data_source"].startswith("mock"), body["data_source"]
    assert all(r["price_source"] == "mock" for r in body["results"])


def test_CHL_R2_mixed_screen_labels_mixed_and_names_mock_symbols(monkeypatch, tmp_path):
    md = live_market(monkeypatch, tmp_path, blocked={"KO"})
    api = Api(Store(":memory:"), md)
    status, body = api.route("POST", "/api/screen", body={"criteria": {"scope": "list", "symbols": ["ABT", "KO"], "min_score": 0}})
    assert status == 200
    assert body["data_source"].startswith("mixed"), body["data_source"]
    assert "KO" in body["data_source"] and "ABT" not in body["data_source"]
    by_sym = {}
    for r in body["results"]:
        by_sym.setdefault(r["symbol"], set()).add(r["price_source"])
    assert by_sym.get("KO") == {"mock"}
    assert by_sym.get("ABT") == {"cboe (delayed)"}


def test_CHL_R2_mixed_ideas_label_mixed_and_ideas_carry_price_source(monkeypatch, tmp_path):
    # Repro 1: interests "video games, fintech" with one name per domain falling back to mock.
    md = live_market(monkeypatch, tmp_path, blocked={"TTWO", "PYPL"})
    api = Api(Store(":memory:"), md)
    api.save_profile(interests="video games, fintech", capital=25000, risk_level=2)
    status, body = api.route("GET", "/api/ideas", query={"count": "3", "refresh": "1"})
    assert status == 200
    assert body["data_source"].startswith("mixed"), body["data_source"]
    assert "TTWO" in body["data_source"] and "PYPL" in body["data_source"]
    assert body["ideas"]
    for idea in body["ideas"]:
        assert idea["price_source"] == idea["analysis"]["quote"]["source"]


def test_CHL_R2_all_live_ideas_label_live(monkeypatch, tmp_path):
    md = live_market(monkeypatch, tmp_path)
    api = Api(Store(":memory:"), md)
    api.save_profile(interests="video games, fintech", capital=25000, risk_level=2)
    status, body = api.route("GET", "/api/ideas", query={"count": "3", "refresh": "1"})
    assert status == 200
    assert body["data_source"] == "live (delayed)"
    assert body["ideas"] and all(i["price_source"] == "cboe (delayed)" for i in body["ideas"])


# ============================================================ CHL-R3 no ideas on fake prices in live mode

def _ideas(md):
    api = Api(Store(":memory:"), md)
    api.save_profile(interests="video games, fintech", capital=25000, risk_level=2)
    return api, api.route("GET", "/api/ideas", query={"count": "3", "refresh": "1"})[1]


def test_CHL_R3_live_ideas_skip_symbols_without_a_live_price(monkeypatch, tmp_path):
    # Find what would be today's top idea with every price live, then make Cboe refuse it.
    _, all_live = _ideas(live_market(monkeypatch, tmp_path / "a"))
    assert all_live["ideas"], "fixture should produce ideas when everything is live"
    top = all_live["ideas"][0]["analysis"]["symbol"]

    api, body = _ideas(live_market(monkeypatch, tmp_path / "b", blocked={top}))
    syms = [i["analysis"]["symbol"] for i in body["ideas"]]
    assert top not in syms, f"{top} has only a demo price, so it must not be a live idea"
    assert all(i["analysis"]["quote"]["source"] != "mock" for i in body["ideas"])
    assert {"symbol": top, "reason": "no live price today"} in body["skipped"], body["skipped"]

    # The ticker drawer still works for it, labeled as demo.
    status, detail = api.route("GET", f"/api/ticker/{top}")
    assert status == 200 and detail["quote"]["source"] == "mock"


def test_CHL_R3_mock_mode_ideas_are_not_skipped_for_mock_prices(client):
    # The other direction: in mock mode every price is mock and ideas still come.
    client.post("/api/profile", data={"interests": "video games, fintech", "capital": "25000", "risk_level": "2"})
    body = client.get("/api/ideas?count=3").json()
    assert body["ideas"]
    assert not any(s["reason"] == "no live price today" for s in body["skipped"])


# ============================================================ CHL-R4 live prices with demo fundamentals

def test_CHL_R4_status_reports_demo_fundamentals_with_live_prices(monkeypatch, tmp_path):
    from charlie import server
    md = live_market(monkeypatch, tmp_path)
    md.quote("ABT")  # one live hit, so prices really are live
    monkeypatch.setattr(server, "store", Store(str(tmp_path / "t.db")))
    monkeypatch.setattr(server, "md", lambda: md)
    s = TestClient(server.app, base_url="http://127.0.0.1:8000").get("/api/status").json()
    assert s["data"]["fundamentals"] == "demo"


def test_CHL_R4_badge_says_live_prices_demo_fundamentals():
    # UI text check only; the e2e test should assert the rendered badge and its tooltip.
    js = (ROOT / "web" / "app.js").read_text()
    assert "Live prices · demo fundamentals" in js


# ============================================================ CHL-R5 bad input is a 422, not a 500

BAD_SCREENS = [({"min_score": "abc"}, "min_score"), ({"delta": "x"}, "delta")]


@pytest.mark.parametrize("criteria,field", BAD_SCREENS)
@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_R5_non_numeric_screen_criterion_is_422(via, criteria, field, client, static_api, caplog):
    target = client if via == "client" else static_api
    with caplog.at_level(logging.ERROR):
        status, body = _post_screen(target, criteria)
    assert status == 422, body
    assert field in str(body["detail"])
    assert not any(r.exc_info for r in caplog.records), "no traceback in the server log"


@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_R5_malformed_paper_leg_is_422(via, client, static_api, caplog):
    trade = {"symbol": "AAPL", "strategy": "shares", "legs": [{"x": 1}]}
    with caplog.at_level(logging.ERROR):
        if via == "client":
            r = client.post("/api/paper", json={"trade": trade})
            status, body = r.status_code, _body(r)
        else:
            status, body = static_api.route("POST", "/api/paper", body={"trade": trade})
    assert status == 422, body
    assert "leg" in str(body["detail"]).lower()
    assert not any(r.exc_info for r in caplog.records), "no traceback in the server log"


# ============================================================ CHL-R6 duplicate paper trades

@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_R6_same_open_trade_twice_is_409(via, client, static_api, mock_md):
    trade = _real_trade(mock_md, "KO")
    if via == "client":
        first = client.post("/api/paper", json={"trade": trade})
        second = client.post("/api/paper", json={"trade": trade})
        assert first.status_code == 200
        status, body = second.status_code, _body(second)
        count = len(client.get("/api/paper").json()["positions"])
    else:
        assert static_api.route("POST", "/api/paper", body={"trade": trade})[0] == 200
        status, body = static_api.route("POST", "/api/paper", body={"trade": trade})
        count = len(static_api.route("GET", "/api/paper")[1]["positions"])
    assert status == 409
    assert body["detail"] == "You already have this paper trade open."
    assert count == 1


def test_CHL_R6_same_trade_after_closing_is_allowed(client, mock_md):
    trade = _real_trade(mock_md, "KO")
    pid = client.post("/api/paper", json={"trade": trade}).json()["id"]
    client.post(f"/api/paper/{pid}/close")
    assert client.post("/api/paper", json={"trade": trade}).status_code == 200


def test_CHL_R6_warning_when_open_max_loss_exceeds_capital(client, mock_md):
    # Profile capital is the default 25,000.
    a = _real_trade(mock_md, "KO")
    b = _real_trade(mock_md, "PEP")
    a["max_loss"], b["max_loss"] = 15000.0, 15000.0
    first = client.post("/api/paper", json={"trade": a})
    assert first.status_code == 200
    assert not first.json().get("warning"), "15,000 of 25,000 at risk needs no warning"
    second = client.post("/api/paper", json={"trade": b})
    assert second.status_code == 200
    assert second.json().get("warning"), "30,000 at risk against 25,000 of capital must warn"


# ============================================================ CHL-R7 scratch trades and win rate

def _closed(store, md, symbol, exit_delta):
    trade = _real_trade(md, symbol)
    pos = store.open_position(trade)
    store.close_position(pos["id"], pos["entry_value"] + exit_delta)


def test_CHL_R7_win_rate_ignores_scratch_trades(tmp_path, monkeypatch, mock_md):
    from charlie import server
    store = Store(str(tmp_path / "w.db"))
    monkeypatch.setattr(server, "store", store)
    monkeypatch.setattr(server, "md", lambda: mock_md)
    _closed(store, mock_md, "KO", +50.0)
    _closed(store, mock_md, "PEP", -50.0)
    _closed(store, mock_md, "MCD", 0.0)
    s = TestClient(server.app, base_url="http://127.0.0.1:8000").get("/api/paper").json()
    assert s["scratch"] == 1
    assert s["win_rate"] == 0.5  # 1 win / (1 win + 1 loss)


def test_CHL_R7_only_scratch_trades_have_no_win_rate(tmp_path, monkeypatch, mock_md):
    from charlie import server
    store = Store(str(tmp_path / "s.db"))
    monkeypatch.setattr(server, "store", store)
    monkeypatch.setattr(server, "md", lambda: mock_md)
    _closed(store, mock_md, "KO", 0.0)
    s = TestClient(server.app, base_url="http://127.0.0.1:8000").get("/api/paper").json()
    assert s["scratch"] == 1 and s["win_rate"] is None


# ============================================================ CHL-R8 delete everything

def _seed(target, md):
    trade = _real_trade(md, "KO")
    if isinstance(target, Api):
        target.route("POST", "/api/profile", body={"interests": "coffee", "capital": "25000", "risk_level": "3"})
        target.route("GET", "/api/ideas")
        target.route("POST", "/api/screen", body={"criteria": {}, "save": True, "name": "mine"})
        target.route("POST", "/api/paper", body={"trade": trade})
    else:
        target.post("/api/profile", data={"interests": "coffee", "capital": "25000", "risk_level": "3"})
        target.get("/api/ideas")
        target.post("/api/screen", json={"criteria": {}, "save": True, "name": "mine"})
        target.post("/api/paper", json={"trade": trade})


def _get(target, path):
    if isinstance(target, Api):
        return target.route("GET", path)[1]
    return target.get(path).json()


def _delete(target, path):
    if isinstance(target, Api):
        return target.route("DELETE", path)[0]
    return target.delete(path).status_code


@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_R8_delete_all_empties_every_table(via, client, mock_md, tmp_path):
    target = client if via == "client" else Api(BrowserStore(FakeStorage()), mock_md, static=False)
    _seed(target, mock_md)
    assert len(_get(target, "/api/paper")["positions"]) == 1
    assert len(_get(target, "/api/screens")["screens"]) == 1
    assert _delete(target, "/api/profile?all=true") == 200
    assert _get(target, "/api/paper")["positions"] == []
    assert _get(target, "/api/screens")["screens"] == []
    assert _get(target, "/api/profile")["saved"] is False


def test_CHL_R8_delete_all_clears_the_sqlite_store(client, mock_md, tmp_path):
    from charlie import server
    _seed(client, mock_md)
    assert client.delete("/api/profile?all=true").status_code == 200
    conn = server.store._conn
    for table in ("kv", "screens", "daily", "positions"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_R8_plain_delete_keeps_trades_and_screens(via, client, mock_md):
    # Without ?all, today's behavior stays (logged under "Decisions to review").
    target = client if via == "client" else Api(BrowserStore(FakeStorage()), mock_md, static=False)
    _seed(target, mock_md)
    assert _delete(target, "/api/profile") == 200
    assert len(_get(target, "/api/paper")["positions"]) == 1
    assert len(_get(target, "/api/screens")["screens"]) == 1
    assert _get(target, "/api/profile")["saved"] is False
