"""Cboe delayed quotes: free, keyless, about 15 minutes delayed, and unofficial.

Endpoints (researched Oct 2026; not verified from the cloud build machine, which blocks them):
  options + quote  https://cdn.cboe.com/api/global/delayed_quotes/options/{SYM}.json
  daily history    https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/{SYM}.json
`data.options[]` rows carry an OCC symbol plus bid, ask, iv, open_interest, volume and greeks.
"""

from __future__ import annotations

from datetime import date

from ..options_math import parse_occ

BASE = "https://cdn.cboe.com/api/global/delayed_quotes"
TIMEOUT = 10


def cboe_symbol(symbol: str) -> str:
    return symbol.upper()


def _get_json(url: str) -> dict:
    import requests  # imported lazily so mock mode (and the browser build) never needs it

    r = requests.get(url, timeout=TIMEOUT, headers={"Accept": "application/json"})
    r.raise_for_status()
    return r.json()


def fetch_options(symbol: str) -> dict:
    return _get_json(f"{BASE}/options/{cboe_symbol(symbol)}.json")


def fetch_history(symbol: str) -> dict:
    return _get_json(f"{BASE}/charts/historical/{cboe_symbol(symbol)}.json")


def _num(x, default: float = 0.0) -> float:
    try:
        return float(x) if x is not None else default
    except (TypeError, ValueError):
        return default


def parse_chain(payload: dict, symbol: str, today: date) -> list[dict]:
    rows = []
    for o in (payload.get("data") or {}).get("options") or []:
        try:
            _, expiry, kind, strike = parse_occ(o["option"])
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        dte = (expiry - today).days
        if dte <= 0:
            continue
        bid, ask = _num(o.get("bid")), _num(o.get("ask"))
        rows.append({
            "symbol": o["option"],
            "underlying": symbol.upper(),
            "kind": kind,
            "strike": strike,
            "expiry": expiry.isoformat(),
            "dte": dte,
            "bid": bid,
            "ask": ask,
            "mid": round((bid + ask) / 2, 2),
            "last": _num(o.get("last_trade_price")),
            "iv": _num(o.get("iv")),
            "delta": _num(o.get("delta")),
            "gamma": _num(o.get("gamma")),
            "theta": _num(o.get("theta")),
            "vega": _num(o.get("vega")),
            "open_interest": int(_num(o.get("open_interest"))),
            "volume": int(_num(o.get("volume"))),
            "source": "cboe",
        })
    return rows


def parse_quote(payload: dict, symbol: str, closes: list[float]) -> dict:
    d = payload.get("data") or {}
    price = _num(d.get("current_price"))
    prev = _num(d.get("prev_day_close")) or (closes[-1] if closes else price)
    window = [c for c in closes[-252:] if c] + [price]
    return {
        "symbol": symbol.upper(),
        "price": price,
        "prev_close": prev,
        "change_pct": round((price / prev - 1) * 100, 2) if prev else 0.0,
        "high_52w": max(window),
        "low_52w": min(window),
        "as_of": payload.get("timestamp"),
        "source": "cboe (delayed)",
    }


def parse_history(payload: dict) -> list[dict]:
    out = []
    for r in payload.get("data") or []:
        if isinstance(r, dict) and r.get("date") and r.get("close") is not None:
            out.append({"date": str(r["date"])[:10], "close": _num(r["close"])})
    return out
