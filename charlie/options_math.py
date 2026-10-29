"""Black-Scholes pricing, greeks, and probability helpers (no SciPy needed)."""

from __future__ import annotations

import math
from datetime import date

RISK_FREE = 0.04


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(s: float, k: float, t: float, sigma: float, r: float) -> tuple[float, float]:
    t = max(t, 1e-6)
    sigma = max(sigma, 1e-4)
    d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    return d1, d1 - sigma * math.sqrt(t)


def bs_price(kind: str, s: float, k: float, t: float, sigma: float, r: float = RISK_FREE) -> float:
    s = max(s, 0.0)  # a stock can't trade below zero; treat bad negative spots as zero
    if t <= 0:
        return max(0.0, s - k) if kind == "call" else max(0.0, k - s)
    if s <= 0 or k <= 0:  # degenerate: no log(S/K); the option is its discounted forward intrinsic
        fwd = s - k * math.exp(-r * t)
        return max(0.0, fwd) if kind == "call" else max(0.0, -fwd)
    d1, d2 = _d1_d2(s, k, t, sigma, r)
    if kind == "call":
        return s * norm_cdf(d1) - k * math.exp(-r * t) * norm_cdf(d2)
    return k * math.exp(-r * t) * norm_cdf(-d2) - s * norm_cdf(-d1)


def greeks(kind: str, s: float, k: float, t: float, sigma: float, r: float = RISK_FREE) -> dict:
    t = max(t, 1e-6)
    sigma = max(sigma, 1e-4)  # same clamp as _d1_d2, so zero/negative IV can't divide by zero
    if s <= 0 or k <= 0:  # degenerate: option is certain to finish worthless (S<=0 call) or in the money
        itm = (k <= 0) if kind == "call" else (s <= 0)
        disc_k = k * math.exp(-r * t)
        delta = (1.0 if kind == "call" else -1.0) if itm else 0.0
        theta = (-r * disc_k if kind == "call" else r * disc_k) / 365 if itm else 0.0
        return {"delta": delta, "gamma": 0.0, "theta": theta, "vega": 0.0}
    d1, d2 = _d1_d2(s, k, t, sigma, r)
    pdf = norm_pdf(d1)
    if kind == "call":
        delta = norm_cdf(d1)
        theta = (-s * pdf * sigma / (2 * math.sqrt(t)) - r * k * math.exp(-r * t) * norm_cdf(d2)) / 365
    else:
        delta = norm_cdf(d1) - 1
        theta = (-s * pdf * sigma / (2 * math.sqrt(t)) + r * k * math.exp(-r * t) * norm_cdf(-d2)) / 365
    return {
        "delta": delta,
        "gamma": pdf / (s * sigma * math.sqrt(t)),
        "theta": theta,
        "vega": s * pdf * math.sqrt(t) / 100,
    }


def prob_above(s: float, level: float, t: float, sigma: float, r: float = RISK_FREE) -> float:
    """Risk-neutral probability the stock finishes above `level` at expiry."""
    if t <= 0 or s <= 0 or level <= 0:
        return 1.0 if s > level else 0.0
    _, d2 = _d1_d2(s, level, t, sigma, r)
    return norm_cdf(d2)


def years_to(expiry: date, today: date) -> float:
    return max((expiry - today).days, 0) / 365.0


def expected_move(s: float, sigma: float, t: float) -> float:
    """One-standard-deviation move by expiry."""
    return s * sigma * math.sqrt(max(t, 0.0))


def occ_symbol(underlying: str, expiry: date, kind: str, strike: float) -> str:
    root = underlying.replace(".", "")
    return f"{root}{expiry:%y%m%d}{'C' if kind == 'call' else 'P'}{int(round(strike * 1000)):08d}"


def parse_occ(sym: str) -> tuple[str, date, str, float]:
    """Parse an OCC option symbol like AAPL261021C00250000."""
    tail = sym[-15:]
    root = sym[:-15].strip()
    yy, mm, dd = int(tail[0:2]), int(tail[2:4]), int(tail[4:6])
    kind = "call" if tail[6] == "C" else "put"
    strike = int(tail[7:]) / 1000.0
    return root, date(2000 + yy, mm, dd), kind, strike
