"""Deterministic demo data built from the illustrative fundamentals in universe.py.

Prices follow a mean-reverting random walk around each ticker's reference price, keyed
by calendar day, so a given date always shows the same numbers and the next day moves a
little. Option chains are priced with Black-Scholes on a simple volatility smile. None of
this is real market data; every record carries source "mock" so the UI can say so.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta
from functools import lru_cache

from ..options_math import RISK_FREE, norm_cdf, norm_pdf
from ..universe import lookup

EPOCH = date(2024, 1, 1)
HISTORY_DAYS = 400  # calendar days of closes returned by history()


def _unit(*parts) -> float:
    """A stable pseudo-random number in [0, 1) from the given parts."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:12], 16) / float(1 << 48)


def _normal(*parts) -> float:
    u1 = max(_unit(*parts, "a"), 1e-12)
    u2 = _unit(*parts, "b")
    return math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)


def _info(symbol: str):
    info = lookup(symbol)
    if not info:
        raise KeyError(f"{symbol} isn't in Charlie's universe")
    return info


@lru_cache(maxsize=256)
def _path(symbol: str, today: date) -> tuple[tuple[str, float], ...]:
    """(date, close) for every weekday from EPOCH through today."""
    info = _info(symbol)
    daily_vol = info.vol / math.sqrt(252)
    phi = 0.985  # pull back toward the reference price; keeps the demo near universe.py levels
    x = 0.0
    out = []
    d = EPOCH
    while d <= today:
        if d.weekday() < 5:
            x = phi * x + daily_vol * _normal(symbol, d.isoformat())
            out.append((d.isoformat(), round(info.price * math.exp(x), 2)))
        d += timedelta(days=1)
    if out[-1][0] != today.isoformat():  # weekend: carry Friday's close to today
        out.append((today.isoformat(), out[-1][1]))
    return tuple(out)


def history(symbol: str, today: date) -> list[dict]:
    start = (today - timedelta(days=HISTORY_DAYS)).isoformat()
    return [{"date": d, "close": c} for d, c in _path(symbol.upper(), today) if d >= start]


def quote(symbol: str, today: date) -> dict:
    symbol = symbol.upper()
    path = _path(symbol, today)
    price, prev = path[-1][1], path[-2][1]
    year_ago = (today - timedelta(days=365)).isoformat()
    closes = [c for d, c in path if d >= year_ago]
    return {
        "symbol": symbol,
        "price": price,
        "prev_close": prev,
        "change_pct": round((price / prev - 1) * 100, 2) if prev else 0.0,
        "high_52w": max(closes),
        "low_52w": min(closes),
        "as_of": today.isoformat(),
        "source": "mock",
    }


def fundamentals(symbol: str, today: date) -> dict:
    t = _info(symbol.upper())
    net_margin = t.op_margin * 0.79
    earnings_yield = (1 / t.pe) if t.pe > 0 and net_margin > 0 else net_margin / 8
    # Price-to-sales implied by the P/E; loss-makers get a growth-stock multiple.
    ps = t.pe * net_margin if net_margin > 0.01 else 8.0
    out = {
        "symbol": t.symbol,
        "fiscal_year": today.year - 1,
        "roic": t.roic,
        "gross_margin": t.gross_margin,
        "op_margin": t.op_margin,
        "op_margin_stdev": t.op_margin_stdev,
        "net_margin": round(net_margin, 4),
        "fcf_margin": t.fcf_margin,
        "fcf_conversion": round(t.fcf_margin / net_margin, 3) if net_margin > 0.01 else None,
        "debt_to_equity": t.debt_to_equity,
        "rev_growth": t.rev_growth,
        "share_change": t.share_change,
        "earnings_yield": round(earnings_yield, 4),
        "fcf_yield": round(t.fcf_margin / ps, 4),
        "pe": t.pe,
        "source": "mock",
    }
    out.update(t.extra)
    return out


# ------------------------------------------------------------------ option chains

def _third_friday(year: int, month: int) -> date:
    d = date(year, month, 15)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def expirations(today: date) -> list[date]:
    """Weeklies 3-8 weeks out, monthlies for 9 months, and two January LEAPS."""
    exps = set()
    friday = today + timedelta(days=(4 - today.weekday()) % 7)
    for w in range(3, 9):
        exps.add(friday + timedelta(weeks=w))
    y, m = today.year, today.month
    for _ in range(10):
        f = _third_friday(y, m)
        if f > today + timedelta(days=7):
            exps.add(f)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for dy in (1, 2):
        exps.add(_third_friday(today.year + dy, 1))
    return sorted(exps)


def strike_step(price: float) -> float:
    for limit, step in ((25, 0.5), (100, 1.0), (200, 2.5), (500, 5.0), (1000, 10.0)):
        if price < limit:
            return step
    return 25.0


def _smile(base_vol: float, moneyness: float, t: float) -> float:
    """Put skew: lower strikes trade at higher implied vol; the effect fades with time."""
    skew = 0.35 * max(0.0, -moneyness) - 0.10 * max(0.0, moneyness) + 0.6 * moneyness * moneyness
    return max(0.05, base_vol * (1 + skew / math.sqrt(max(t, 0.05)) * 0.35))


@lru_cache(maxsize=128)
def _chain(symbol: str, today: date) -> tuple[dict, ...]:
    info = _info(symbol)
    spot = quote(symbol, today)["price"]
    step = strike_step(spot)
    rows = []
    for exp in expirations(today):
        dte = (exp - today).days
        t = dte / 365
        # Wide enough for every strategy's strikes (deep ITM LEAPS need the most room), and no
        # wider: chain size drives load time in the browser demo.
        width = 0.22 if dte < 120 else 0.45
        lo = math.floor(spot * (1 - width) / step) * step
        hi = math.ceil(spot * (1 + width) / step) * step
        n = int(round((hi - lo) / step))
        sq = math.sqrt(t)
        disc = math.exp(-RISK_FREE * t)
        exp_iso, exp_tag = exp.isoformat(), f"{exp:%y%m%d}"
        root = symbol.replace(".", "")
        for i in range(n + 1):
            k = round(lo + i * step, 2)
            if k <= 0:
                continue
            m = math.log(k / spot)
            iv = _smile(info.vol, m, t)
            dist = abs(m) / max(info.vol * sq, 0.02)
            # Black-Scholes once per strike; the put comes from put-call parity (same math as
            # options_math.bs_price/greeks, inlined because chain size drives browser load time).
            d1 = (-m + (RISK_FREE + 0.5 * iv * iv) * t) / (iv * sq)
            d2 = d1 - iv * sq
            n1, n2, pdf = norm_cdf(d1), norm_cdf(d2), norm_pdf(d1)
            k_disc = k * disc
            call = spot * n1 - k_disc * n2
            gamma = pdf / (spot * iv * sq)
            vega = spot * pdf * sq / 100
            decay = -spot * pdf * iv / (2 * sq)
            for j, (kind, theo, delta, theta) in enumerate((
                    ("call", call, n1, (decay - RISK_FREE * k_disc * n2) / 365),
                    ("put", call - spot + k_disc, n1 - 1, (decay + RISK_FREE * k_disc * (1 - n2)) / 365))):
                if theo < 0.03:
                    continue
                half = max(0.01, theo * 0.025, 0.02 * math.sqrt(spot / 100))
                bid, ask = round(max(0.0, theo - half), 2), round(theo + half, 2)
                oi = int(4000 * math.exp(-dist) * (0.5 + ((i * 7 + j * 3 + dte) % 10) / 10))
                rows.append({
                    "symbol": f"{root}{exp_tag}{'C' if kind == 'call' else 'P'}{int(round(k * 1000)):08d}",
                    "underlying": symbol,
                    "kind": kind,
                    "strike": k,
                    "expiry": exp_iso,
                    "dte": dte,
                    "bid": bid,
                    "ask": ask,
                    "mid": round((bid + ask) / 2, 2),
                    "last": round(theo, 2),
                    "iv": round(iv, 4),
                    "delta": round(delta, 4),
                    "gamma": round(gamma, 5),
                    "theta": round(theta, 4),
                    "vega": round(vega, 4),
                    "open_interest": oi,
                    "volume": int(oi * 0.1),
                    "source": "mock",
                })
    return tuple(rows)


def chain(symbol: str, today: date) -> list[dict]:
    return [dict(r) for r in _chain(symbol.upper(), today)]
