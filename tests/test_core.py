import math
from datetime import date

import pytest

from charlie import scoring
from charlie.data import cboe, sec
from charlie.data.market import MarketData
from charlie.engine import daily_ideas, screen, ticker_detail
from charlie.options_math import bs_price, greeks, occ_symbol, parse_occ, prob_above
from charlie.profile import build_profile, estimate_years, extract_text
from charlie.strategies import RISK_LEVELS, STRATEGIES, Infeasible, allowed, build, scenario
from charlie.universe import DOMAIN_BY_KEY, DOMAINS, TICKERS, lookup

TODAY = date(2026, 10, 22)

RESUME = """Alex Rivera, Registered Nurse
HCA Healthcare, Charge Nurse, Surgical ICU, 2017 - 2022. Trained staff on Epic Systems EHR and da Vinci workflow.
UnitedHealth Group (Optum), Clinical Informatics Specialist, 2022 - Present. Medicare dashboards in SQL.
Worked with Abbott and Stryker on patient monitoring integrations."""


@pytest.fixture(scope="module")
def md():
    return MarketData(mode="mock", today=TODAY, cache_dir="/tmp/charlie-test-cache")


@pytest.fixture(scope="module")
def profile():
    return build_profile(RESUME, interests="GLP-1 drugs, FDA approvals, $ISRG", brands="Costco, Lululemon",
                         holdings={"ABT": 100}, capital=40000, risk_level=2)


# ---------------------------------------------------------------- universe & profile

def test_universe_is_consistent():
    assert len({t.symbol for t in TICKERS}) == len(TICKERS)
    for d in DOMAINS:
        for s in d.tickers:
            assert lookup(s).domain == d.key


def test_profile_finds_healthcare_circle(profile):
    assert profile.domains[0]["key"] == "healthcare"
    syms = [t["symbol"] for t in profile.tickers]
    for s in ("UNH", "HCA", "ISRG", "ABT", "SYK"):
        assert s in syms
    isrg = next(t for t in profile.tickers if t["symbol"] == "ISRG")
    assert any("Da Vinci" in w for w in isrg["why"])
    assert profile.holdings == {"ABT": 100}
    assert profile.years_experience == 9


def test_profile_avoids_false_positive_aliases():
    p = build_profile("I'm Chase. Built metadata pipelines for startups; delta lake; vertex AI.")
    syms = {t["symbol"] for t in p.tickers}
    assert not {"JPM", "META", "UPS", "DAL", "VRTX"} & syms


def test_empty_profile_has_starter_circle():
    p = build_profile()
    assert p.domains and p.tickers


def test_years_parser():
    assert estimate_years("10+ years of experience in sales", 2026) == 10
    assert estimate_years("2015 - present", 2026) == 11


def test_extract_text_docx_and_txt(tmp_path):
    import docx
    d = docx.Document()
    d.add_paragraph("Software engineer at Microsoft")
    path = tmp_path / "r.docx"
    d.save(path)
    assert "Microsoft" in extract_text("r.docx", path.read_bytes())
    assert extract_text("r.txt", b"hello") == "hello"


# ---------------------------------------------------------------- option math

def test_put_call_parity():
    s, k, t, v, r = 100, 105, 0.25, 0.3, 0.04
    c, p = bs_price("call", s, k, t, v, r), bs_price("put", s, k, t, v, r)
    assert math.isclose(c - p, s - k * math.exp(-r * t), abs_tol=1e-6)


def test_greeks_sane():
    g = greeks("put", 100, 90, 40 / 365, 0.3)
    assert -0.3 < g["delta"] < 0
    assert g["theta"] < 0 and g["gamma"] > 0
    assert 0 < prob_above(100, 90, 40 / 365, 0.3) < 1


def test_occ_roundtrip():
    sym = occ_symbol("BRK.B", date(2026, 12, 18), "put", 452.5)
    assert sym == "BRKB261218P00452500"
    assert parse_occ(sym) == ("BRKB", date(2026, 12, 18), "put", 452.5)


# ---------------------------------------------------------------- data parsers

def test_cboe_parsers():
    payload = {"timestamp": "2026-10-22 00:54:36", "data": {"current_price": 250.0, "prev_day_close": 245.0, "options": [
        {"option": "AAPL261120P00230000", "bid": 3.1, "ask": 3.3, "iv": 0.28, "open_interest": 1200, "volume": 50,
         "delta": -0.22, "gamma": 0.01, "theta": -0.08, "vega": 0.25, "last_trade_price": 3.2},
        {"option": "AAPL251017C00250000", "bid": 1, "ask": 1.2},  # expired: dropped
        {"option": "garbage"},
    ]}}
    rows = cboe.parse_chain(payload, "AAPL", TODAY)
    assert len(rows) == 1 and rows[0]["kind"] == "put" and rows[0]["strike"] == 230 and rows[0]["mid"] == 3.2
    assert rows[0]["dte"] == 29
    q = cboe.parse_quote(payload, "AAPL", [240.0, 245.0])
    assert q["price"] == 250.0 and q["change_pct"] == pytest.approx(2.04, abs=0.01)
    hist = cboe.parse_history({"data": [{"date": "2026-10-21", "close": 249.1}, {"bad": 1}]})
    assert hist == [{"date": "2026-10-21", "close": 249.1}]


def _fact(val, end, start=None):
    r = {"val": val, "end": end, "form": "10-K", "fp": "FY", "filed": end}
    if start:
        r["start"] = start
    return r


def test_sec_metrics():
    years = [2021, 2022, 2023, 2024, 2025]
    flow = lambda vals: [_fact(v, f"{y}-12-31", f"{y}-01-01") for y, v in zip(years, vals)]
    inst = lambda vals: [_fact(v, f"{y}-12-31") for y, v in zip(years, vals)]
    facts = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": flow([100, 110, 121, 133, 146])}},
        "GrossProfit": {"units": {"USD": flow([60, 66, 73, 80, 88])}},
        "OperatingIncomeLoss": {"units": {"USD": flow([30, 33, 36, 40, 44])}},
        "NetIncomeLoss": {"units": {"USD": flow([24, 26, 29, 32, 35])}},
        "StockholdersEquity": {"units": {"USD": inst([100, 110, 120, 130, 140])}},
        "LongTermDebtNoncurrent": {"units": {"USD": inst([50, 50, 50, 50, 50])}},
        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": inst([20, 20, 20, 20, 30])}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": flow([30, 32, 35, 38, 42])}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": flow([5, 5, 6, 6, 7])}},
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": inst([10, 10, 9.8, 9.6, 9.5])}},
    }}}
    m = sec.compute_metrics(facts, price=50.0)
    assert m["fiscal_year"] == 2025
    assert m["gross_margin"] == pytest.approx(88 / 146, abs=1e-3)
    assert m["roic"] == pytest.approx(44 * 0.79 / (140 + 50 - 30), abs=1e-3)
    assert m["rev_growth"] == pytest.approx(0.10, abs=0.005)
    assert m["share_change"] < 0
    assert m["fcf_yield"] == pytest.approx(35 / (50 * 9.5), abs=1e-3)


# ---------------------------------------------------------------- scoring

def test_scoring_prefers_quality(md):
    def s(sym):
        return scoring.score(sym, md.fundamentals(sym), md.quote(sym), 50, ["x"])

    assert s("V")["score"] > s("RBLX")["score"]
    assert "Not yet profitable at the operating level" in s("RBLX")["red_flags"]
    for f in s("V")["factors"]:
        assert 0 <= f["score"] <= 100 and f["reason"] and f["quote"]


def test_competence_moves_score(md):
    lo = scoring.score("KO", md.fundamentals("KO"), md.quote("KO"), 0, [])
    hi = scoring.score("KO", md.fundamentals("KO"), md.quote("KO"), 100, ["worked at Coca-Cola"])
    assert hi["score"] > lo["score"]
    assert "Outside your circle of competence" in lo["red_flags"]


# ---------------------------------------------------------------- strategies

def test_strategy_gating():
    assert allowed(1) == ["shares"]
    assert "long_call" not in allowed(4)
    assert set(allowed(5)) == set(STRATEGIES)
    with pytest.raises(Infeasible):
        build("bull_put_spread", "KO", 68, [], 100000, 2)


def test_cash_secured_put_math(md):
    q = md.quote("KO")
    t = build("cash_secured_put", "KO", q["price"], md.chain("KO"), 50000, 2)
    leg = t["legs"][0]
    assert leg["action"] == "sell" and leg["instrument"] == "put" and leg["strike"] < q["price"]
    assert 0.12 <= abs(leg["delta"]) <= 0.3
    assert t["capital_required"] == leg["strike"] * 100
    assert t["breakeven"] == pytest.approx(leg["strike"] - leg["price"], abs=0.01)
    assert t["max_profit"] == pytest.approx(leg["price"] * 100, abs=0.01)
    assert 25 <= t["dte"] <= 55
    pnl = {s["move"]: s["pnl"] for s in scenario(t)}
    assert pnl[0.2] == pytest.approx(t["max_profit"], abs=0.01)
    assert pnl[-0.2] < 0


def test_spread_risk_within_budget(md):
    q = md.quote("AAPL")
    t = build("bull_put_spread", "AAPL", q["price"], md.chain("AAPL"), 25000, 3)
    assert t["max_loss"] <= 25000 * RISK_LEVELS[3]["max_risk_pct"] + 1e-6
    short, long_ = t["legs"]
    assert short["strike"] > long_["strike"]
    assert min(s["pnl"] for s in scenario(t, moves=(-0.5,))) == pytest.approx(-t["max_loss"], abs=0.01)


def test_covered_call_needs_shares(md):
    with pytest.raises(Infeasible):
        build("covered_call", "ABT", 130, md.chain("ABT"), 40000, 2, holdings={})
    t = build("covered_call", "ABT", md.quote("ABT")["price"], md.chain("ABT"), 40000, 2, holdings={"ABT": 250})
    assert t["contracts"] == 2 and t["legs"][0]["strike"] > t["spot"]


# ---------------------------------------------------------------- engine

@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_daily_ideas_respect_slider(md, profile, level):
    r = daily_ideas(md, profile, level, count=3)
    assert 1 <= len(r["ideas"]) <= 3
    domains = [i["analysis"]["domain"] for i in r["ideas"]]
    assert len(domains) == len(set(domains))
    for i in r["ideas"]:
        t = i["trade"]
        assert STRATEGIES[t["strategy"]]["min_level"] <= level
        assert t["max_loss"] > 0
        assert i["thesis"]["inversion"] and i["thesis"]["why_you"]
        if t["strategy"] in ("bull_put_spread", "bull_call_spread", "leaps_call", "long_call"):
            assert t["max_loss"] <= profile.capital * RISK_LEVELS[level]["max_risk_pct"] + 1e-6
    assert "mock" in r["data_source"]


def test_daily_ideas_are_stable_within_a_day(md, profile):
    a = daily_ideas(md, profile, 2)
    b = daily_ideas(md, profile, 2)
    assert [i["trade"]["symbol"] for i in a["ideas"]] == [i["trade"]["symbol"] for i in b["ideas"]]


def test_covered_call_on_holdings_shows_up(md, profile):
    r = daily_ideas(md, profile, 2)
    assert any(i["trade"]["strategy"] == "covered_call" and i["trade"]["symbol"] == "ABT" for i in r["ideas"])


def test_screen_filters(md, profile):
    r = screen(md, profile, {"scope": "all", "max_price": 150, "min_pop": 70, "strategies": ["cash_secured_put"]}, level=2)
    assert r["results"]
    for row in r["results"]:
        assert row["price"] <= 150
        assert row["trade"]["strategy"] == "cash_secured_put"
        assert row["trade"]["pop"] >= 0.70
    # strategies above the slider are dropped silently
    r2 = screen(md, profile, {"strategies": ["long_call"]}, level=2)
    assert r2["strategies"] == []


def test_ticker_detail(md, profile):
    d = ticker_detail(md, profile, "ISRG", level=3)
    assert d["history"] and d["trades"]
    assert any(b["strategy"] == "long_call" for b in d["blocked"])
