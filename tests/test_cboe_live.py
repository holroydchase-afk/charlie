"""Live Cboe hardening, built against a trimmed copy of a real Cboe response (ABT, saved 2026-10-28)."""
import json
from datetime import date
from pathlib import Path

import pytest

from charlie.data import cboe
from charlie.data.market import MarketData
from charlie.strategies import build, pick_expiry

FIX = Path(__file__).parent / "fixtures" / "cboe"
TODAY = date(2026, 10, 28)


def _payload(kind):
    return json.loads((FIX / f"{kind}_ABT.json").read_text())


@pytest.fixture
def live_md(monkeypatch, tmp_path):
    monkeypatch.setattr(cboe, "fetch_options", lambda s: _payload("options"))
    monkeypatch.setattr(cboe, "fetch_history", lambda s: _payload("history"))
    return MarketData(mode="auto", today=TODAY, cache_dir=str(tmp_path))


def test_real_payload_parses(live_md):
    q = live_md.quote("ABT")
    assert q["source"] == "cboe (delayed)" and q["price"] == round(q["price"], 2) > 0
    assert q["low_52w"] <= q["price"] <= q["high_52w"]
    chain = live_md.chain("ABT")
    assert chain and all(c["source"] == "cboe" and c["dte"] > 0 for c in chain)
    assert all(0 <= c["iv"] < 5 for c in chain)  # Cboe sends IV as a fraction, like the mock
    hist = live_md.history("ABT")
    assert len(hist) == 300 and hist[0]["date"] < hist[-1]["date"]


def test_live_expiry_skips_thin_weeklies(live_md):
    # 2026-12-04 is the closest to 40 days but its puts have almost no open interest.
    chain = live_md.chain("ABT")
    assert pick_expiry(chain, 25, 55, 40) == "2026-12-04"
    assert pick_expiry(chain, 25, 55, 40, live=True) == "2026-12-18"


def test_live_cash_secured_put_builds(live_md):
    q, chain = live_md.quote("ABT"), live_md.chain("ABT")
    t = build("cash_secured_put", "ABT", q["price"], chain, 25000, 2, [], live=True)
    assert t["expiry"] == "2026-12-18" and t["max_loss"] > 0 and t["breakeven"] < q["price"]


def test_unknown_symbol_does_not_take_live_data_offline(monkeypatch, tmp_path):
    import requests

    def fetch(sym):
        if sym == "KO":  # e.g. a ticker Cboe spells differently
            r = requests.Response()
            r.status_code, r.url = 403, "https://cdn-api.cboe.com/x/KO.json"
            r.raise_for_status()
        return _payload("options")
    monkeypatch.setattr(cboe, "fetch_options", fetch)
    monkeypatch.setattr(cboe, "fetch_history", lambda s: fetch(s) and _payload("history"))
    md = MarketData(mode="auto", today=TODAY, cache_dir=str(tmp_path))
    assert md.quote("KO")["source"] == "mock"
    assert md.quote("ABT")["source"] == "cboe (delayed)"
    st = md.status()
    assert st["errors"] and "Some live data" in st["notes"][-1]


def test_network_failure_still_backs_off(monkeypatch, tmp_path):
    calls = []

    def down(sym):
        calls.append(sym)
        raise ConnectionError("no route")
    monkeypatch.setattr(cboe, "fetch_options", down)
    monkeypatch.setattr(cboe, "fetch_history", down)
    md = MarketData(mode="auto", today=TODAY, cache_dir=str(tmp_path))
    md.quote("ABT"), md.quote("KO")
    assert len(calls) == 1  # the second symbol skips the network during the backoff
    assert "unreachable" in md.status()["notes"][-1]


def test_live_quotes_refresh_in_a_long_running_server(live_md, monkeypatch):
    import charlie.data.market as m
    first = live_md.quote("ABT")
    assert live_md.quote("ABT") is first
    clock = [m.time.monotonic() + m.TTL["options"] + 1]
    monkeypatch.setattr(m.time, "monotonic", lambda: clock[0])
    assert live_md.quote("ABT") is not first  # memo expired, re-read through the 15-minute cache


def test_mock_memo_never_expires(tmp_path, monkeypatch):
    import charlie.data.market as m
    md = MarketData(mode="mock", today=TODAY, cache_dir=str(tmp_path))
    first = md.quote("KO")
    monkeypatch.setattr(m.time, "monotonic", lambda: 1e12)
    assert md.quote("KO") is first
