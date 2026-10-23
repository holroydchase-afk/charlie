"""M0.2: the market data package (mock generator, SEC identity rule, facade fallbacks)."""
from datetime import date

import pytest

from charlie.data import cboe, mock, sec
from charlie.data.market import MarketData
from charlie.universe import TICKERS

TODAY = date(2026, 10, 22)


def test_mock_is_deterministic_per_day(tmp_path):
    a = MarketData(mode="mock", today=TODAY, cache_dir=str(tmp_path))
    b = MarketData(mode="mock", today=TODAY, cache_dir=str(tmp_path))
    assert a.quote("KO") == b.quote("KO")
    assert a.chain("KO")[:5] == b.chain("KO")[:5]
    assert a.history("KO") == b.history("KO")


def test_mock_quote_matches_history_and_52w_high():
    q = mock.quote("AAPL", TODAY)
    h = mock.history("AAPL", TODAY)
    assert q["source"] == "mock" and q["price"] > 0
    assert h[-1]["date"] == TODAY.isoformat() and h[-1]["close"] == q["price"]
    assert q["high_52w"] >= q["price"]
    assert all(r["date"] < TODAY.isoformat() for r in h[:-1])


def test_mock_chain_shape():
    rows = mock.chain("MSFT", TODAY)
    assert rows
    for r in rows[:50]:
        assert r["kind"] in ("call", "put") and r["dte"] > 0 and r["bid"] <= r["ask"]
        assert r["mid"] == pytest.approx((r["bid"] + r["ask"]) / 2, abs=0.006)
    dtes = {r["dte"] for r in rows}
    assert any(25 <= d <= 55 for d in dtes) and any(240 <= d <= 800 for d in dtes)
    puts = [r for r in rows if r["kind"] == "put"]
    assert all(-1 <= r["delta"] <= 0 for r in puts)


def test_every_ticker_has_mock_data():
    for t in TICKERS:
        f = mock.fundamentals(t.symbol, TODAY)
        assert f["source"] == "mock" and f["roic"] == t.roic


def test_sec_requires_user_agent_from_env(monkeypatch):
    monkeypatch.delenv("CHARLIE_SEC_UA", raising=False)
    assert "you@example.com" in sec.PLACEHOLDER_UA
    with pytest.raises(sec.SecConfigError):
        sec.user_agent()
    monkeypatch.setenv("CHARLIE_SEC_UA", sec.PLACEHOLDER_UA)
    with pytest.raises(sec.SecConfigError):  # the placeholder itself is not a real identity
        sec.user_agent()
    monkeypatch.setenv("CHARLIE_SEC_UA", "Charlie test@example.org")
    assert sec.user_agent() == "Charlie test@example.org"


def test_live_sec_never_called_without_user_agent(monkeypatch, tmp_path):
    monkeypatch.delenv("CHARLIE_SEC_UA", raising=False)
    calls = []
    monkeypatch.setattr(sec, "_get_json", lambda *a, **k: calls.append(a) or {})
    md = MarketData(mode="auto", today=TODAY, cache_dir=str(tmp_path))
    monkeypatch.setattr(cboe, "_get_json", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked")))
    f = md.fundamentals("KO")
    assert f["source"] == "mock" and calls == []
    assert "CHARLIE_SEC_UA" in md.status()["notes"][0]


def test_auto_falls_back_to_mock_and_live_raises(monkeypatch, tmp_path):
    def blocked(*a, **k):
        raise OSError("403 from proxy")
    monkeypatch.setattr(cboe, "fetch_options", blocked)
    monkeypatch.setattr(cboe, "fetch_history", blocked)
    auto = MarketData(mode="auto", today=TODAY, cache_dir=str(tmp_path))
    assert auto.quote("KO")["source"] == "mock"
    assert auto.status()["mode"] == "auto" and auto.status()["live_ok"] is False
    live = MarketData(mode="live", today=TODAY, cache_dir=str(tmp_path))
    with pytest.raises(OSError):
        live.quote("KO")


