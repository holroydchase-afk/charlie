"""Paper portfolio marking. Paper only: nothing here talks to a broker."""

from __future__ import annotations

from .data.market import MarketData
from .options_math import parse_occ
from .store import Store, leg_key, position_value


def current_prices(md: MarketData, legs: list[dict], underlying: str) -> dict[str, float]:
    spot = md.quote(underlying)["price"]
    chain = {c["symbol"]: c for c in md.chain(underlying)} if any(l["instrument"] != "stock" for l in legs) else {}
    prices = {}
    for leg in legs:
        if leg["instrument"] == "stock":
            prices[leg_key(leg)] = spot
            continue
        c = chain.get(leg["symbol"])
        if c:
            prices[leg_key(leg)] = c["mid"]
        else:
            # Expired or missing from the chain: value at intrinsic.
            _, _, kind, strike = parse_occ(leg["symbol"])
            prices[leg_key(leg)] = max(0.0, spot - strike) if kind == "call" else max(0.0, strike - spot)
    return prices


def mark(md: MarketData, pos: dict) -> dict:
    trade = pos["trade"]
    if pos["status"] == "closed":
        value = pos["exit_value"]
    else:
        value = position_value(trade["legs"], current_prices(md, trade["legs"], trade["symbol"]))
    pnl = round(value - pos["entry_value"], 2)
    basis = trade.get("capital_required") or abs(pos["entry_value"]) or 1
    return {**pos, "current_value": value, "pnl": pnl, "pnl_pct": round(pnl / basis, 4),
            "max_profit": trade.get("max_profit"), "max_loss": trade.get("max_loss"),
            "pct_of_max_profit": round(pnl / trade["max_profit"], 3) if trade.get("max_profit") else None}


def summary(md: MarketData, store: Store) -> dict:
    marked = [mark(md, p) for p in store.positions()]
    open_ = [p for p in marked if p["status"] == "open"]
    closed = [p for p in marked if p["status"] == "closed"]
    return {
        "positions": marked,
        "open_count": len(open_),
        "open_pnl": round(sum(p["pnl"] for p in open_), 2),
        "realized_pnl": round(sum(p["pnl"] for p in closed), 2),
        "capital_at_risk": round(sum(p["trade"].get("max_loss") or 0 for p in open_), 2),
        "win_rate": round(sum(1 for p in closed if p["pnl"] > 0) / len(closed), 3) if closed else None,
    }


def close(md: MarketData, store: Store, pid: str) -> dict | None:
    pos = store.position(pid)
    if not pos or pos["status"] != "open":
        return pos
    value = position_value(pos["trade"]["legs"], current_prices(md, pos["trade"]["legs"], pos["trade"]["symbol"]))
    return mark(md, store.close_position(pid, value))
