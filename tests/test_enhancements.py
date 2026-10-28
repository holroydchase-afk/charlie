"""M1.13 enhancements (release plan "Phase 5 picks"): failing-first tests.

A. Idea track record: GET /api/track-record (and Api.route) grades past ideas at today's price,
   next to simply holding SPY. Local mode reads past days from the `daily` store; the static demo
   (BrowserStore keeps only the latest day) backdates the mock market for the current profile.
B. Exit-plan alerts: every position in GET /api/paper carries `alerts`, computed from the trade's
   management rules (50% of max profit, 21 days or fewer to expiry, price through breakeven).

Interface contract (for the engineer) is in the M1.13 hand-off; the tests below pin it. Only
fictional data: the sample person and made-up trades. Nothing touches the network.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from charlie import browser
from charlie.browser_store import BrowserStore
from charlie.data.market import MarketData
from charlie.demo import sample_profile
from charlie.handlers import Api
from charlie.options_math import occ_symbol
from charlie.store import Store
from charlie.strategies import STRATEGIES
from charlie.universe import lookup

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DAY = date(2026, 10, 22)  # a Thursday, the demo's pinned day in the tests
LOOPBACK = "http://127.0.0.1:8000"
NFA = "Not financial advice. Paper trading only."
# No language that claims returns or promises performance (hard rule: never claim returns).
FORBIDDEN = ("guaranteed", "beat the market", "returns of")
ITEM_KEYS = {"date", "symbol", "strategy", "label", "entry_price", "price_today", "breakeven", "above_breakeven",
             "underlying_move_pct", "spy_move_pct", "outcome"}
SUMMARY_KEYS = {"count", "above_breakeven", "avg_underlying_move_pct", "avg_spy_move_pct"}
ALERT_TYPES = {"take_profit", "time", "breakeven"}


class FakeStorage(dict):
    getItem = dict.get

    def setItem(self, k, v):
        self[k] = v

    def removeItem(self, k):
        self.pop(k, None)


def _mock(day: date, tmp_path=None) -> MarketData:
    return MarketData(mode="mock", today=day, cache_dir=str(tmp_path / f"cache-{day}") if tmp_path else None)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "t.db"


def _client(monkeypatch, store, md):
    from charlie import server
    monkeypatch.setattr(server, "store", store)
    monkeypatch.setattr(server, "md", lambda: md)
    return TestClient(server.app, base_url=LOOPBACK, raise_server_exceptions=False)


def _static_api(day: date = DAY, storage=None) -> Api:
    """The demo's router exactly as charlie.browser.init builds it: sample person, BrowserStore."""
    return Api(BrowserStore(storage if storage is not None else FakeStorage()), _mock(day), static=True,
               default_profile=lambda level: sample_profile(day, level))


def _route(api: Api, path: str = "/api/track-record", method: str = "GET", body=None):
    status, out = api.route(method, path, None, body)
    return status, json.loads(json.dumps(out))  # what crosses the JS boundary


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _check_shape(body: dict) -> None:
    """Every track-record response: items, summary, disclaimer, data-source and sample labels."""
    assert {"items", "summary", "disclaimer", "data_source", "sample", "as_of", "risk_level", "benchmark"} <= set(body), (
        sorted(body))
    assert body["disclaimer"] == NFA
    assert body["benchmark"] == "SPY"
    assert isinstance(body["sample"], bool)
    assert isinstance(body["items"], list)
    assert SUMMARY_KEYS <= set(body["summary"]), sorted(body["summary"])
    for it in body["items"]:
        assert ITEM_KEYS <= set(it), sorted(it)


def _check_math(body: dict, today: date) -> None:
    """Each item's numbers agree with each other and with today's (mock) market."""
    md_today = _mock(today)
    by_date_spy = {}
    for it in body["items"]:
        assert it["date"] < today.isoformat(), f"{it['date']} isn't a past day"
        for k in ("entry_price", "price_today", "underlying_move_pct", "spy_move_pct"):
            assert _finite(it[k]), (k, it[k])
        assert it["price_today"] == pytest.approx(md_today.quote(it["symbol"])["price"], abs=0.011)
        assert it["underlying_move_pct"] == pytest.approx(it["price_today"] / it["entry_price"] - 1, abs=1e-3)
        if it["breakeven"] is None:
            assert it["above_breakeven"] is None
        else:
            assert it["above_breakeven"] is (it["price_today"] >= it["breakeven"])
        assert isinstance(it["outcome"], str) and it["outcome"].strip()
        if it["above_breakeven"] is True:
            assert "above breakeven" in it["outcome"].lower()
        if it["above_breakeven"] is False:
            assert "below breakeven" in it["outcome"].lower()
        # SPY's move is over the same span, so it's the same for every idea from the same day.
        by_date_spy.setdefault(it["date"], set()).add(round(it["spy_move_pct"], 6))
    assert all(len(v) == 1 for v in by_date_spy.values()), by_date_spy
    s, items = body["summary"], body["items"]
    assert s["count"] == len(items)
    assert s["above_breakeven"] == sum(1 for it in items if it["above_breakeven"] is True)
    if items:
        assert s["avg_underlying_move_pct"] == pytest.approx(sum(it["underlying_move_pct"] for it in items) / len(items), abs=1e-3)
        assert s["avg_spy_move_pct"] == pytest.approx(sum(it["spy_move_pct"] for it in items) / len(items), abs=1e-3)
    else:
        assert s["avg_underlying_move_pct"] is None and s["avg_spy_move_pct"] is None


def _no_return_claims(text: str) -> None:
    low = text.lower()
    hits = [w for w in FORBIDDEN if w in low]
    assert hits == [], f"claims returns or performance: {hits}"


# ============================================================ A. track record, local app

def test_TR1_fresh_local_user_has_an_empty_track_record(monkeypatch, db_path, tmp_path):
    client = _client(monkeypatch, Store(str(db_path)), _mock(DAY, tmp_path))
    r = client.get("/api/track-record")
    assert r.status_code == 200, r.text
    body = r.json()
    _check_shape(body)
    assert body["items"] == [] and body["summary"]["count"] == 0
    assert body["sample"] is False
    assert "demo" in body["data_source"].lower()  # mock mode says so
    _no_return_claims(r.text)


def test_TR2_local_track_record_reads_past_days_from_the_daily_store(monkeypatch, db_path, tmp_path):
    """Ideas the user saw on earlier days (the daily snapshot) are graded at today's price;
    today's own ideas aren't in the record yet, and a day asked for at 1 and 3 ideas counts once."""
    store = Store(str(db_path))
    past = [DAY - timedelta(days=7), DAY - timedelta(days=14)]
    seen = {}
    for d in past:
        api_then = Api(store, _mock(d, tmp_path))
        api_then.ideas(count=1)
        r3 = api_then.ideas(count=3)
        seen[d.isoformat()] = {(i["trade"]["symbol"], i["trade"]["strategy"]) for i in r3["ideas"]}
    Api(store, _mock(DAY, tmp_path)).ideas()  # today's ideas: not part of the track record

    client = _client(monkeypatch, store, _mock(DAY, tmp_path))
    r = client.get("/api/track-record")
    assert r.status_code == 200, r.text
    body = r.json()
    _check_shape(body)
    assert body["sample"] is False
    dates = {it["date"] for it in body["items"]}
    assert dates == set(seen), f"want exactly the past days {sorted(seen)}, got {sorted(dates)}"
    for d, pairs in seen.items():
        got = [(it["symbol"], it["strategy"]) for it in body["items"] if it["date"] == d]
        assert len(got) == len(set(got)), f"{d}: an idea appears twice: {got}"
        assert set(got) == pairs, d
    # Newest first.
    assert [it["date"] for it in body["items"]] == sorted((it["date"] for it in body["items"]), reverse=True)
    # The entry price is the price on the day of the idea.
    for it in body["items"]:
        then = _mock(date.fromisoformat(it["date"]))
        assert it["entry_price"] == pytest.approx(then.quote(it["symbol"])["price"], abs=0.011)
    _check_math(body, DAY)
    _no_return_claims(r.text)

    # Static parity: the browser's router gives the same answer on the same store and market.
    status, routed = _route(Api(store, _mock(DAY, tmp_path)))
    assert status == 200 and routed == body


def test_TR3_track_record_route_is_get_only(monkeypatch, db_path, tmp_path):
    client = _client(monkeypatch, Store(str(db_path)), _mock(DAY, tmp_path))
    assert client.post("/api/track-record", json={}).status_code in (404, 405)
    assert _route(_static_api(), method="POST", body={})[0] == 404


# ============================================================ A. track record, static demo

@pytest.fixture(scope="module")
def demo_record():
    status, body = _route(_static_api())
    assert status == 200, body
    return body


def test_TR4_demo_backdates_the_sample_persons_track_record(demo_record):
    body = demo_record
    _check_shape(body)
    assert body["sample"] is True
    assert "demo" in body["data_source"].lower()
    assert body["risk_level"] == 2  # the sample person's level
    items = body["items"]
    assert len(items) >= 3, "the demo needs a few past ideas to show"
    dates = sorted({it["date"] for it in items})
    assert len(dates) >= 2, f"want ideas from at least 2 past days, got {dates}"
    for d in dates:
        dd = date.fromisoformat(d)
        assert dd < DAY and (DAY - dd).days <= 42 and dd.weekday() < 5, d
    for it in items:
        assert lookup(it["symbol"]), it["symbol"]
        assert it["strategy"] in STRATEGIES and STRATEGIES[it["strategy"]]["min_level"] <= 2
        then = _mock(date.fromisoformat(it["date"]))
        assert it["entry_price"] == pytest.approx(then.quote(it["symbol"])["price"], abs=0.011)
    _check_math(body, DAY)


def test_TR5_demo_track_record_is_deterministic(demo_record):
    assert _route(_static_api())[1] == demo_record
    # The cache of today's ideas doesn't change the record.
    api = _static_api()
    assert api.route("GET", "/api/ideas")[0] == 200
    assert _route(api)[1] == demo_record


def test_TR6_risk_query_picks_the_level(demo_record):
    status, body = _route(_static_api(), "/api/track-record?risk=1")
    assert status == 200, body
    assert body["risk_level"] == 1
    for it in body["items"]:
        assert STRATEGIES[it["strategy"]]["min_level"] <= 1, it
    status, bad = _route(_static_api(), "/api/track-record?risk=abc")
    assert status == 422


def test_TR7_track_record_never_claims_returns(demo_record):
    _no_return_claims(json.dumps(demo_record))
    for f in ("app.js", "index.html", "static.js"):
        _no_return_claims((WEB / f).read_text())


def test_TR8_prebuilt_has_the_track_record_for_every_level():
    """Today shows the record below the ideas, so the demo's first screen needs it before Pyodide loads.
    (test_first_screen's parity test then checks it matches what the engine computes.)"""
    pre = browser.prebuild(DAY.isoformat())
    for lvl, entries in pre["levels"].items():
        rec = entries.get("GET /api/track-record")
        assert rec, f"level {lvl}: no prebuilt GET /api/track-record"
        assert rec["risk_level"] == int(lvl) and rec["sample"] is True and rec["disclaimer"] == NFA
        s = FakeStorage()
        s.setItem("charlie:kv:sample_risk", lvl)
        browser.init(s, DAY.isoformat())
        got = json.loads(browser.request("GET", "/api/track-record"))
        assert got["status"] == 200 and got["body"] == json.loads(json.dumps(rec)), lvl


def test_TR9_ui_has_the_track_record_section_and_empty_state():
    html, js = (WEB / "index.html").read_text(), (WEB / "app.js").read_text()
    today = html[html.index('id="tab-today"'):]
    today = today[:today.index("</section>")]
    assert 'id="track-record"' in today, "Today needs a #track-record section below the ideas"
    assert today.index('id="track-record"') > today.index('id="ideas"')
    assert "/api/track-record" in js
    assert "No past ideas yet" in js, "a fresh local user needs an empty state"


# ============================================================ B. exit-plan alerts

class StubMarket(MarketData):
    """Mock market whose spot and option mids the test sets, to force each alert."""

    def __init__(self, today: date, spot: float, mids: dict[str, float] | None = None):
        super().__init__(mode="mock", today=today)
        self.spot, self.mids = spot, mids or {}

    def quote(self, symbol: str) -> dict:
        return {"symbol": symbol.upper(), "price": self.spot, "source": "mock", "as_of": self.today.isoformat()}

    def chain(self, symbol: str) -> list[dict]:
        return [{"symbol": s, "mid": m} for s, m in self.mids.items()]


SYM = "UNH"


def _spread(dte: int) -> tuple[dict, str, str]:
    """A made-up 100/95 bull put spread for 1.00 credit: max profit $100, max loss $400, breakeven 99."""
    exp = DAY + timedelta(days=dte)
    short, long_ = occ_symbol(SYM, exp, "put", 100), occ_symbol(SYM, exp, "put", 95)
    legs = [{"action": "sell", "instrument": "put", "symbol": short, "strike": 100.0, "expiry": exp.isoformat(),
             "qty": 1, "price": 2.00},
            {"action": "buy", "instrument": "put", "symbol": long_, "strike": 95.0, "expiry": exp.isoformat(),
             "qty": 1, "price": 1.00}]
    trade = {"strategy": "bull_put_spread", "label": STRATEGIES["bull_put_spread"]["label"], "symbol": SYM,
             "spot": 105.0, "legs": legs, "contracts": 1, "net_premium": 1.0, "max_profit": 100.0, "max_loss": 400.0,
             "breakeven": 99.0, "capital_required": 400.0, "dte": dte, "expiry": exp.isoformat(),
             "management": ["Close at ~50% of max profit.",
                            "If the stock closes below your short strike with 21 days left, close for a small loss rather than hoping."],
             "disclaimer": NFA}
    return trade, short, long_


# name: (days to expiry, spot, short mid, long mid, expected alert types)
CASES = {
    "take_profit": (40, 110.0, 0.40, 0.10, {"take_profit"}),   # P&L +$70 = 70% of max profit
    "time_14d": (14, 110.0, 1.80, 0.90, {"time"}),             # P&L +$10, 14 days left
    "time_21d_boundary": (21, 110.0, 1.80, 0.90, {"time"}),    # exactly 21 days counts
    "no_time_22d": (22, 110.0, 1.80, 0.90, set()),             # 22 days doesn't
    "breakeven": (40, 97.0, 3.50, 1.50, {"breakeven"}),        # spot 97 below breakeven 99, P&L -$100
    "none": (40, 105.0, 1.90, 0.95, set()),                    # P&L +$5, 40 days, above breakeven
}


def _seed(store, case: str):
    dte, spot, smid, lmid, want = CASES[case]
    trade, short, long_ = _spread(dte)
    store.open_position(trade)
    return StubMarket(DAY, spot, {short: smid, long_: lmid}), want


def _check_alerts(pos: dict, want: set) -> None:
    assert "alerts" in pos, sorted(pos)
    alerts = pos["alerts"]
    assert isinstance(alerts, list)
    for a in alerts:
        assert a["type"] in ALERT_TYPES, a
        assert isinstance(a["message"], str) and len(a["message"].strip()) > 10, a
    assert {a["type"] for a in alerts} == want, alerts
    assert len(alerts) == len({a["type"] for a in alerts}), "one alert per type"
    for a in alerts:
        msg = a["message"].lower()
        if a["type"] == "take_profit":
            assert "50%" in msg and "profit" in msg, a
        if a["type"] == "time":
            assert re.search(r"\b\d+ days?\b", msg), a
        if a["type"] == "breakeven":
            assert "breakeven" in msg, a


@pytest.mark.parametrize("case", list(CASES))
def test_ALERT1_paper_positions_carry_exit_plan_alerts_server(monkeypatch, db_path, case):
    store = Store(str(db_path))
    md, want = _seed(store, case)
    client = _client(monkeypatch, store, md)
    r = client.get("/api/paper")
    assert r.status_code == 200, r.text
    (pos,) = r.json()["positions"]
    _check_alerts(pos, want)


@pytest.mark.parametrize("case", list(CASES))
def test_ALERT2_paper_positions_carry_exit_plan_alerts_static(case):
    store = BrowserStore(FakeStorage())
    md, want = _seed(store, case)
    status, body = _route(Api(store, md, static=True), "/api/paper")
    assert status == 200, body
    (pos,) = body["positions"]
    _check_alerts(pos, want)


def test_ALERT3_time_message_names_the_days_left(db_path):
    store = Store(str(db_path))
    md, _ = _seed(store, "time_14d")
    (pos,) = Api(store, md).paper()["positions"]
    (a,) = pos["alerts"]
    assert re.search(r"\b14 days\b", a["message"]), a


def test_ALERT4_breakeven_message_names_the_breakeven_price(db_path):
    store = Store(str(db_path))
    md, _ = _seed(store, "breakeven")
    (pos,) = Api(store, md).paper()["positions"]
    (a,) = pos["alerts"]
    assert "99" in a["message"], a


def test_ALERT5_several_rules_can_fire_at_once(db_path):
    store = Store(str(db_path))
    trade, short, long_ = _spread(10)
    store.open_position(trade)
    md = StubMarket(DAY, 110.0, {short: 0.30, long_: 0.10})  # P&L +$80 and 10 days left
    (pos,) = Api(store, md).paper()["positions"]
    _check_alerts(pos, {"take_profit", "time"})


def test_ALERT6_closed_positions_have_no_alerts(db_path):
    store = Store(str(db_path))
    md, _ = _seed(store, "breakeven")
    api = Api(store, md)
    pid = api.paper()["positions"][0]["id"]
    api.paper_close(pid)
    (pos,) = api.paper()["positions"]
    assert pos["status"] == "closed" and pos["alerts"] == []


def test_ALERT7_shares_get_a_breakeven_alert_but_never_a_time_alert(db_path):
    store = Store(str(db_path))
    trade = {"strategy": "shares", "label": STRATEGIES["shares"]["label"], "symbol": SYM, "spot": 100.0,
             "legs": [{"action": "buy", "instrument": "stock", "symbol": SYM, "qty": 10, "price": 100.0}],
             "contracts": 0, "net_premium": None, "max_profit": None, "max_loss": 1000.0, "breakeven": 100.0,
             "capital_required": 1000.0, "dte": None, "expiry": None, "management": [], "disclaimer": NFA}
    store.open_position(trade)
    (below,) = Api(store, StubMarket(DAY, 90.0)).paper()["positions"]
    _check_alerts(below, {"breakeven"})
    (above,) = Api(store, StubMarket(DAY, 120.0)).paper()["positions"]
    _check_alerts(above, set())


def test_ALERT8_ui_renders_alert_chips():
    js = (WEB / "app.js").read_text()
    assert "alert-chip" in js and "data-alert" in js and "p.alerts" in js
