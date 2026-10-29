"""Golden-value risk math tests (qa-tdd Charlie addendum: risk math checklist).

Every expected number below is worked out by hand or taken from a textbook
(Hull, "Options, Futures, and Other Derivatives", Example 15.6 / 13.6 depending
on edition), with the working in a comment. None is copied from the code's output.

Known bugs are kept as strict xfails with a CHL-RM<n> id so they flip red when fixed.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from charlie.options_math import bs_price, expected_move, greeks, prob_above, years_to
from charlie.strategies import RISK_LEVELS, Infeasible, build, scenario

# ---------------------------------------------------------------- Black-Scholes golden values

# Hull's textbook example: S=42, K=40, r=10%, sigma=20%, T=0.5y.
#   d1 = [ln(42/40) + (0.10 + 0.02) * 0.5] / (0.20 * sqrt(0.5))
#      = (0.048790 + 0.06) / 0.141421 = 0.7693
#   d2 = d1 - 0.141421 = 0.6278
#   N(d1) = 0.7791, N(d2) = 0.7349, K e^{-rT} = 40 * e^{-0.05} = 38.049
#   call = 42 * 0.7791 - 38.049 * 0.7349 = 4.76      (Hull: 4.76)
#   put  = 38.049 * N(-0.6278) - 42 * N(-0.7693) = 38.049*0.2651 - 42*0.2209 = 0.81  (Hull: 0.81)
HULL = dict(s=42.0, k=40.0, t=0.5, sigma=0.20, r=0.10)


def test_RM1_hull_call_price():
    assert bs_price("call", **HULL) == pytest.approx(4.76, abs=0.005)


def test_RM2_hull_put_price():
    assert bs_price("put", **HULL) == pytest.approx(0.81, abs=0.005)


def test_RM3_put_call_parity():
    # C - P = S - K e^{-rT} = 42 - 38.049 = 3.951
    c, p = bs_price("call", **HULL), bs_price("put", **HULL)
    assert c - p == pytest.approx(42 - 40 * math.exp(-0.05), abs=1e-9)
    assert c - p == pytest.approx(3.951, abs=0.001)


def test_RM4_atm_zero_rate_call():
    # S=K=100, r=0, sigma=0.2, T=1: d1=0.1, d2=-0.1
    # call = 100 * (N(0.1) - N(-0.1)) = 100 * (2*0.53983 - 1) = 7.966
    assert bs_price("call", 100, 100, 1.0, 0.2, 0.0) == pytest.approx(7.966, abs=0.001)


def test_RM5_hull_greeks_golden():
    # Same Hull inputs. phi(d1) = exp(-0.7693^2/2)/sqrt(2 pi) = 0.7438/2.5066 = 0.2967
    # delta_call = N(d1) = 0.7791 ; delta_put = N(d1) - 1 = -0.2209
    # gamma = phi(d1) / (S sigma sqrt T) = 0.2967 / (42*0.2*0.7071=5.9397) = 0.04996
    # vega per vol point = S phi(d1) sqrt T / 100 = 42*0.2967*0.7071/100 = 0.0881
    # theta_call per day = [-S phi sigma/(2 sqrt T) - r K e^{-rT} N(d2)] / 365
    #   = [-1.7624 - 0.1*38.049*0.7349] / 365 = (-1.7624 - 2.7962)/365 = -0.01249
    # theta_put per day = [-1.7624 + 0.1*38.049*0.2651] / 365 = (-1.7624 + 1.0087)/365 = -0.002065
    gc, gp = greeks("call", **HULL), greeks("put", **HULL)
    assert gc["delta"] == pytest.approx(0.7791, abs=1e-4)
    assert gp["delta"] == pytest.approx(-0.2209, abs=1e-4)
    assert gc["gamma"] == pytest.approx(0.04996, abs=1e-4)
    assert gp["gamma"] == pytest.approx(gc["gamma"])
    assert gc["vega"] == pytest.approx(0.0881, abs=1e-4)
    assert gc["theta"] == pytest.approx(-0.01249, abs=2e-5)
    assert gp["theta"] == pytest.approx(-0.002065, abs=2e-5)


def test_RM6_delta_call_minus_delta_put_is_one():
    for s in (30, 42, 60):
        assert greeks("call", s, 40, 0.5, 0.2, 0.1)["delta"] - greeks("put", s, 40, 0.5, 0.2, 0.1)["delta"] == pytest.approx(1.0)


def test_RM7_units_vega_is_per_vol_point_theta_is_per_day():
    # Vega per 1 vol point ~= price(sigma+0.01) - price(sigma); theta per day ~= price(T - 1/365) - price(T).
    g = greeks("call", **HULL)
    bumped = bs_price("call", 42, 40, 0.5, 0.21, 0.10) - bs_price("call", **HULL)
    assert bumped == pytest.approx(g["vega"], rel=0.02)
    decay = bs_price("call", 42, 40, 0.5 - 1 / 365, 0.20, 0.10) - bs_price("call", **HULL)
    assert decay == pytest.approx(g["theta"], rel=0.02)


def test_RM8_prob_above_golden():
    # S=100, level=100, r=0, sigma=0.2, T=1: d2 = (0 - 0.02)/0.2 = -0.1, N(-0.1) = 0.4602
    assert prob_above(100, 100, 1.0, 0.2, 0.0) == pytest.approx(0.4602, abs=1e-4)


def test_RM9_expected_move_golden_and_units():
    # 1-sd move = S sigma sqrt(T) = 100 * 0.20 * sqrt(0.25) = 10.00 (IV as decimal, T in years)
    assert expected_move(100, 0.20, 0.25) == pytest.approx(10.0)
    assert expected_move(100, 0.20, 0.0) == 0.0
    assert expected_move(100, 0.20, -1.0) == 0.0


def test_RM10_years_to_days_vs_years():
    assert years_to(date(2027, 1, 1), date(2026, 1, 1)) == pytest.approx(1.0)  # 365 days
    assert years_to(date(2026, 1, 31), date(2026, 1, 1)) == pytest.approx(30 / 365)
    assert years_to(date(2026, 1, 1), date(2026, 1, 1)) == 0.0  # expiry day
    assert years_to(date(2025, 12, 1), date(2026, 1, 1)) == 0.0  # past expiry never negative


# ---------------------------------------------------------------- Black-Scholes edges

@pytest.mark.parametrize("t", [0.0, -0.1])
def test_RM11_expiry_day_and_past_expiry_is_intrinsic(t):
    assert bs_price("call", 42, 40, t, 0.2) == 2.0
    assert bs_price("put", 42, 40, t, 0.2) == 0.0
    assert bs_price("put", 38, 40, t, 0.2) == 2.0
    assert prob_above(42, 40, t, 0.2) == 1.0
    assert prob_above(38, 40, t, 0.2) == 0.0


def test_RM12_greeks_finite_at_expiry_day():
    for kind in ("call", "put"):
        for s in (30, 40.5, 60):  # deep OTM/ITM and near the money
            g = greeks(kind, s, 40, 0.0, 0.2)
            assert all(math.isfinite(v) for v in g.values()), (kind, s, g)


def test_RM13_deep_itm_otm_bounds():
    # Deep ITM call ~ S - K e^{-rT}; deep OTM call ~ 0; never negative, never NaN.
    assert bs_price("call", 200, 40, 0.5, 0.2, 0.1) == pytest.approx(200 - 40 * math.exp(-0.05), abs=1e-6)
    assert 0.0 <= bs_price("call", 10, 40, 0.5, 0.2, 0.1) < 1e-6
    assert 0.0 <= bs_price("put", 200, 40, 0.5, 0.2, 0.1) < 1e-6


@pytest.mark.parametrize("sigma", [0.0, -0.2])
def test_RM14_zero_or_negative_iv_is_finite(sigma):
    # With sigma -> 0 the call is worth its discounted forward intrinsic: 42 - 38.049 = 3.951.
    v = bs_price("call", 42, 40, 0.5, sigma, 0.1)
    assert math.isfinite(v) and v == pytest.approx(3.951, abs=0.001)


@pytest.mark.parametrize("sigma", [
    0.0,
    -0.2,
])
def test_RM34_greeks_zero_or_negative_iv_finite_and_sane(sigma):
    g = greeks("call", 42, 40, 0.5, sigma, 0.1)
    assert all(math.isfinite(x) for x in g.values())
    assert g["gamma"] >= 0 and g["vega"] >= 0


def test_RM15_zero_spot_does_not_crash():
    # A zero-priced stock: call worth 0, put worth K e^{-rT}. Expect a value or None, not a crash.
    assert bs_price("call", 0, 40, 0.5, 0.2, 0.1) == pytest.approx(0.0)
    assert prob_above(0, 40, 0.5, 0.2) == pytest.approx(0.0)
    greeks("call", 0, 40, 0.5, 0.2)


def test_RM16_zero_strike_does_not_crash():
    v = bs_price("call", 42, 0, 0.5, 0.2, 0.1)
    assert v is None or math.isfinite(v)


def test_RM17_negative_spot_does_not_crash():
    v = bs_price("call", -5, 40, 0.5, 0.2, 0.1)
    assert v is None or (math.isfinite(v) and v >= 0)


def test_RM35_zero_spot_put_delta_is_minus_one_and_parity_holds():
    # CHL-R1. At S=0 (K=40, r=10%, T=0.5) the call is worth 0 for every S near 0, so its delta is 0.
    # Put-call parity: P = C - S + K e^{-rT} = 0 - S + 38.049, so dP/dS = -1 and delta put = -1.
    # Check: Black-Scholes delta put = N(d1) - 1, and d1 -> -inf as S -> 0, so N(d1) -> 0 and delta -> -1.
    # Hence delta call - delta put = 0 - (-1) = 1, the same identity as RM6.
    gc = greeks("call", 0, 40, 0.5, 0.2, 0.1)
    gp = greeks("put", 0, 40, 0.5, 0.2, 0.1)
    assert gp["delta"] == pytest.approx(-1.0)
    assert gc["delta"] - gp["delta"] == pytest.approx(1.0)
    # Continuity: a stock at a billionth of a dollar has the same deltas as one at zero.
    gp_tiny = greeks("put", 1e-9, 40, 0.5, 0.2, 0.1)
    gc_tiny = greeks("call", 1e-9, 40, 0.5, 0.2, 0.1)
    assert gp["delta"] == pytest.approx(gp_tiny["delta"], abs=1e-6)
    assert gc["delta"] == pytest.approx(gc_tiny["delta"], abs=1e-6)


# ---------------------------------------------------------------- hand-made chain

SPOT = 100.0
E44, E60 = "2026-12-11", "2026-12-27"


def _opt(expiry, dte, kind, strike, bid, ask, delta, iv=0.25, oi=500):
    return {"symbol": f"TEST{expiry}{kind[0].upper()}{strike:g}", "expiry": expiry, "dte": dte, "kind": kind,
            "strike": strike, "bid": bid, "ask": ask, "mid": round((bid + ask) / 2, 2) if bid is not None and ask is not None else None,
            "delta": delta, "iv": iv, "open_interest": oi}


def chain():
    return [
        # 44 DTE puts: mids 2.00 / 1.00 / 0.60
        _opt(E44, 44, "put", 95, 1.90, 2.10, -0.21),
        _opt(E44, 44, "put", 92, 0.90, 1.10, -0.13),
        _opt(E44, 44, "put", 90, 0.55, 0.65, -0.09),
        # 44 DTE calls: mids 3.00 / 1.00
        _opt(E44, 44, "call", 100, 2.90, 3.10, 0.45),
        _opt(E44, 44, "call", 105, 0.90, 1.10, 0.25),
        # 60 DTE calls: mids 4.00 / 2.00 ; 60 DTE put: mid 1.50
        _opt(E60, 60, "call", 100, 3.90, 4.10, 0.55),
        _opt(E60, 60, "call", 105, 1.90, 2.10, 0.38),
        _opt(E60, 60, "put", 95, 1.40, 1.60, -0.25),
    ]


def _finite(trade):
    for k in ("max_loss", "max_profit", "breakeven", "pop", "return_on_risk", "capital_required", "expected_move"):
        v = trade[k]
        assert v is None or (isinstance(v, (int, float)) and math.isfinite(v)), (k, v)
    assert trade["max_loss"] >= 0


def _scenario_min(trade):
    return min(r["pnl"] for r in scenario(trade))


# ---------------------------------------------------------------- strategy golden values

def test_RM18_cash_secured_put_golden():
    # Level 2 targets 0.20 delta -> 95 put (|0.21|). Credit = mid 2.00.
    # Collateral 95*100 = 9,500; 50% of 50,000 = 25,000 -> 2 fit, capped at max_contracts default 1.
    # Breakeven 95 - 2 = 93. Max profit 2*100 = 200. Max loss (stock to 0) 93*100 = 9,300.
    # Return on capital 200/9,500 = 0.0211. Annualized 0.0211*365/44 = 0.1747.
    # POP = N(d2) with level 93: d2 = [ln(100/93) + (0.04 - 0.25^2/2)*44/365] / (0.25*sqrt(44/365))
    #   = (0.072571 + 0.001055)/0.086800 = 0.8482 -> N = 0.802
    t = build("cash_secured_put", "TEST", SPOT, chain(), 50000, 2)
    assert t["contracts"] == 1
    assert t["max_profit"] == 200.0
    assert t["max_loss"] == 9300.0
    assert t["breakeven"] == 93.0
    assert t["capital_required"] == 9500.0
    assert t["return_on_capital"] == pytest.approx(0.0211, abs=1e-4)
    assert t["annualized"] == pytest.approx(0.1747, abs=5e-4)
    assert t["pop"] == pytest.approx(0.802, abs=1e-3)
    _finite(t)


def test_RM19_bull_put_spread_golden():
    # Level 3 targets 0.30 delta -> short 95 put (closest). Long target 95 - max(100*0.03, 1) = 92.
    # Width 3, credit 2.00 - 1.00 = 1.00 (> 12% of width). Loss per spread (3 - 1)*100 = 200.
    # Risk budget 25,000 * 5% = 1,250 -> 1,250 // 200 = 6, capped at 5 contracts.
    # Max loss 200*5 = 1,000 ; max profit 1.00*100*5 = 500 ; breakeven 95 - 1 = 94 ; RoR 500/1000 = 0.5.
    # POP: d2 = [ln(100/94) + 0.00875*0.120548]/0.086800 = (0.061875 + 0.001055)/0.0868 = 0.7250 -> N = 0.766
    t = build("bull_put_spread", "TEST", SPOT, chain(), 25000, 3)
    assert t["contracts"] == 5
    assert t["width"] == 3
    assert t["net_premium"] == 1.0
    assert t["max_loss"] == 1000.0
    assert t["max_profit"] == 500.0
    assert t["breakeven"] == 94.0
    assert t["return_on_risk"] == 0.5
    assert t["pop"] == pytest.approx(0.766, abs=1e-3)
    assert t["max_loss"] <= 25000 * RISK_LEVELS[3]["max_risk_pct"]
    # -20% move: px 80. short 95P: -(15 - 2)*500 = -6,500 ; long 92P: (12 - 1)*500 = +5,500 -> -1,000 = -max loss
    assert _scenario_min(t) == pytest.approx(-t["max_loss"])
    _finite(t)


def test_RM20_bull_call_spread_golden_rounds_down():
    # Level 4 picks the 60 DTE expiry; long 0.55 delta -> 100C (mid 4.00), short 0.38 above 100 -> 105C (mid 2.00).
    # Debit 2.00, width 5. Risk budget 12,000 * 4% = 480 -> 480 // 200 = 2.4 -> 2 contracts (round down).
    # Max loss 2*100*2 = 400 ; max profit (5 - 2)*100*2 = 600 ; breakeven 102 ; RoR 1.5.
    # POP: d2 = [ln(100/102) + 0.00875*60/365] / (0.25*sqrt(60/365)) = (-0.019803 + 0.001438)/0.101361 = -0.1812 -> 0.428
    t = build("bull_call_spread", "TEST", SPOT, chain(), 12000, 4)
    assert t["contracts"] == 2
    assert t["net_premium"] == -2.0
    assert t["max_loss"] == 400.0
    assert t["max_profit"] == 600.0
    assert t["breakeven"] == 102.0
    assert t["return_on_risk"] == 1.5
    assert t["pop"] == pytest.approx(0.428, abs=1e-3)
    assert t["max_loss"] <= 12000 * RISK_LEVELS[4]["max_risk_pct"]
    # -20%: long 100C (0 - 4)*200 = -800 ; short 105C -(0 - 2)*200 = +400 -> -400
    assert _scenario_min(t) == pytest.approx(-t["max_loss"])
    _finite(t)


def test_RM21_long_call_golden():
    # Level 5 long call: 30-75 DTE target 50 -> 44 DTE; 0.45 delta -> 100C mid 3.00. Cost 300.
    # Risk budget 20,000 * 2% = 400 -> 1 contract. Max loss 300, max profit None (unlimited), breakeven 103.
    # POP: d2 = [ln(100/103) + 0.00875*0.120548]/0.086800 = (-0.029559 + 0.001055)/0.0868 = -0.3284 -> 0.371
    t = build("long_call", "TEST", SPOT, chain(), 20000, 5)
    assert t["contracts"] == 1
    assert t["max_loss"] == 300.0
    assert t["max_profit"] is None
    assert t["return_on_risk"] is None
    assert t["breakeven"] == 103.0
    assert t["pop"] == pytest.approx(0.371, abs=1e-3)
    assert t["share_equivalent"] == 45
    assert t["max_loss"] <= 20000 * RISK_LEVELS[5]["max_risk_pct"]
    assert _scenario_min(t) == pytest.approx(-300.0)
    _finite(t)


def test_RM22_covered_call_golden():
    # 250 shares -> 2 contracts. 0.25 delta above spot -> 105C mid 1.00.
    # Breakeven 100 - 1 = 99 ; max profit (105 - 100 + 1)*100*2 = 1,200 ; max loss (to 0) 99*200 = 19,800.
    # Capital 100*200 = 20,000 ; yield 1/100 = 0.01.
    t = build("covered_call", "TEST", SPOT, chain(), 40000, 2, holdings={"TEST": 250})
    assert t["contracts"] == 2
    assert t["max_profit"] == 1200.0
    assert t["max_loss"] == 19800.0
    assert t["breakeven"] == 99.0
    assert t["capital_required"] == 20000.0
    assert t["yield_on_shares"] == 0.01
    _finite(t)


def test_RM23_collar_golden():
    # 45-100 DTE target 75 -> 60 DTE. Buy 95P (0.25 delta, mid 1.50), sell 105C (0.38 is the only call > 100, mid 2.00).
    # Net credit 0.50. Max loss (100 - 95 - 0.5)*100 = 450 ; max profit (105 - 100 + 0.5)*100 = 550 ; breakeven 99.5.
    # -20%: put (15 - 1.5)*100 = 1,350 ; call -(0 - 2)*100 = 200 ; stock -20*100 = -2,000 -> -450
    t = build("collar", "TEST", SPOT, chain(), 40000, 3, holdings={"TEST": 100})
    assert t["contracts"] == 1
    assert t["net_premium"] == 0.5
    assert t["max_loss"] == 450.0
    assert t["max_profit"] == 550.0
    assert t["breakeven"] == 99.5
    assert _scenario_min(t) == pytest.approx(-450.0)
    _finite(t)


def test_RM24_shares_golden_level1():
    # Level 1 budget 5% of 10,000 = 500 -> 500 // 100 = 5 shares, cost 500 = max loss, breakeven 100.
    t = build("shares", "TEST", SPOT, [], 10000, 1)
    assert t["shares"] == 5
    assert t["max_loss"] == 500.0
    assert t["breakeven"] == 100.0
    assert t["max_loss"] <= 10000 * RISK_LEVELS[1]["max_risk_pct"]
    _finite(t)


def test_RM25_iv_missing_from_chain_still_finite():
    # iv=None: pop falls back to 0.3 vol, iv/expected_move become None, never NaN.
    ch = [dict(c, iv=None) for c in chain()]
    t = build("bull_put_spread", "TEST", SPOT, ch, 25000, 3)
    assert t["iv"] is None and t["expected_move"] is None
    assert t["max_loss"] == 1000.0
    _finite(t)


# ---------------------------------------------------------------- sizing edges

@pytest.mark.parametrize("strategy,capital,level", [
    ("bull_put_spread", 3000, 3),     # budget 150 < 200 per spread
    ("bull_call_spread", 4000, 4),    # budget 160 < 200 per spread
    ("long_call", 10000, 5),          # budget 200 < 300 per contract
    ("cash_secured_put", 10000, 2),   # 50% = 5,000 < 9,500 collateral
    ("shares", 1000, 1),              # 5% = 50 < one $100 share
])
def test_RM26_too_small_budget_is_no_trade_not_a_one_lot(strategy, capital, level):
    with pytest.raises(Infeasible):
        build(strategy, "TEST", SPOT, chain(), capital, level)


@pytest.mark.parametrize("capital", [25000, 12000, 7000, 4100])
def test_RM27_defined_risk_max_loss_within_risk_budget(capital):
    for strategy, level in (("bull_put_spread", 3), ("bull_call_spread", 4), ("long_call", 5)):
        try:
            t = build(strategy, "TEST", SPOT, chain(), capital, level)
        except Infeasible:
            continue
        assert 0 < t["max_loss"] <= capital * RISK_LEVELS[level]["max_risk_pct"], (strategy, capital, t["max_loss"])


@pytest.mark.parametrize("capital", [0, -1000])
def test_RM28_zero_or_negative_capital_spreads_no_trade(capital):
    for strategy, level in (("bull_put_spread", 3), ("bull_call_spread", 4), ("long_call", 5), ("cash_secured_put", 2)):
        with pytest.raises(Infeasible):
            build(strategy, "TEST", SPOT, chain(), capital, level)


def test_RM29_zero_capital_shares_no_trade():
    with pytest.raises(Infeasible):
        build("shares", "TEST", SPOT, [], 0, 1)


def test_RM30_zero_spot_shares_no_trade():
    with pytest.raises(Infeasible):
        build("shares", "TEST", 0.0, [], 10000, 1)


# ---------------------------------------------------------------- quote edges

def test_RM31_zero_bid_or_ask_excluded():
    ch = [dict(c, bid=0.0) if c["kind"] == "put" else c for c in chain()]
    with pytest.raises(Infeasible):
        build("cash_secured_put", "TEST", SPOT, ch, 50000, 2)
    ch = [dict(c, ask=0.0) if c["kind"] == "put" else c for c in chain()]
    with pytest.raises(Infeasible):
        build("bull_put_spread", "TEST", SPOT, ch, 25000, 3)


def test_RM32_crossed_quote_is_no_trade():
    # Only put is crossed: bid 2.10 > ask 1.90. A crossed market is bad data, not a fill.
    ch = [_opt(E44, 44, "put", 95, 2.10, 1.90, -0.21)]
    with pytest.raises(Infeasible):
        build("cash_secured_put", "TEST", SPOT, ch, 50000, 2)


def test_RM33_missing_quote_is_no_trade():
    ch = [_opt(E44, 44, "put", 95, None, None, -0.21)]
    with pytest.raises(Infeasible):
        build("cash_secured_put", "TEST", SPOT, ch, 50000, 2)


@pytest.mark.parametrize("bid, ask", [
    (float("nan"), 2.10),
    (1.90, float("nan")),
    (float("nan"), float("nan")),
])
def test_RM36_nan_quote_is_no_trade(bid, ask):
    # CHL-R2. A NaN bid or ask is missing data, like None. Every comparison with NaN is False, so
    # "bid <= 0" and "bid > ask" both let it through, and the mid (bid + ask) / 2 = NaN becomes the credit.
    # The only put is otherwise the RM18 contract (95 strike, 44 DTE, delta -0.21), which builds fine
    # with a real 1.90 / 2.10 quote, so the NaN alone must make it no trade.
    ch = [_opt(E44, 44, "put", 95, bid, ask, -0.21)]
    with pytest.raises(Infeasible):
        build("cash_secured_put", "TEST", SPOT, ch, 50000, 2)
