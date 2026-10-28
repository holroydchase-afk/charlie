"""Paper portfolio marking. Paper only: nothing here talks to a broker."""

from __future__ import annotations

from datetime import date

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


TAKE_PROFIT_AT = 0.5  # the exit plan's "close at ~50% of max profit"
TIME_DAYS = 21  # and "decide with 21 days left"


def _expiry(trade: dict) -> date | None:
    """The trade's expiry, or its nearest option leg's; None for shares."""
    days = [trade.get("expiry")] + [l.get("expiry") for l in trade.get("legs", []) if l.get("instrument") != "stock"]
    parsed = []
    for d in days:
        try:
            parsed.append(date.fromisoformat(str(d)[:10]))
        except (TypeError, ValueError):
            pass
    return min(parsed) if parsed else None


def _number(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def alerts(md: MarketData, trade: dict, pnl: float, spot: float | None) -> list[dict]:
    """Which exit-plan rules have fired for an open trade, at most one per type (M1.13).

    take_profit: P&L is at least 50% of the max profit. time: 21 days or fewer to expiry
    (never for shares). breakeven: the stock is below the trade's breakeven. All the trades
    Charlie suggests are bullish or neutral, so below breakeven is the losing side."""
    out = []
    max_profit = _number(trade.get("max_profit"))
    if max_profit and max_profit > 0 and pnl >= TAKE_PROFIT_AT * max_profit:
        out.append({"type": "take_profit", "message": (
            f"Up ${pnl:,.0f}, {pnl / max_profit:.0%} of the most this trade can make. "
            f"The exit plan says take profit at 50%: consider closing.")})
    exp = _expiry(trade)
    if exp is not None:
        left = (exp - md.today).days
        if left <= TIME_DAYS:
            n = abs(left)
            days = f"{n} day{'' if n == 1 else 's'}"
            msg = (f"Expired {days} ago. Close it or let it settle." if left < 0 else
                   f"{days} to expiry. The exit plan says decide now: close or roll, rather than hold into expiration.")
            out.append({"type": "time", "message": msg})
    be = _number(trade.get("breakeven"))
    if be is not None and spot is not None and spot < be:
        out.append({"type": "breakeven", "message": (
            f"{trade.get('symbol', 'The stock')} is ${spot:,.2f}, below your breakeven of ${be:,.2f}. "
            f"Check your exit plan.")})
    return out


def mark(md: MarketData, pos: dict) -> dict:
    trade = pos["trade"]
    spot = None
    if pos["status"] == "closed":
        value = pos["exit_value"]
    else:
        value = position_value(trade["legs"], current_prices(md, trade["legs"], trade["symbol"]))
        spot = _number(md.quote(trade["symbol"])["price"])
    pnl = round(value - pos["entry_value"], 2)
    basis = trade.get("capital_required") or abs(pos["entry_value"]) or 1
    return {**pos, "current_value": value, "pnl": pnl, "pnl_pct": round(pnl / basis, 4),
            "max_profit": trade.get("max_profit"), "max_loss": trade.get("max_loss"),
            "pct_of_max_profit": round(pnl / trade["max_profit"], 3) if trade.get("max_profit") else None,
            "alerts": [] if pos["status"] == "closed" else alerts(md, trade, pnl, spot)}


def summary(md: MarketData, store: Store) -> dict:
    marked = [mark(md, p) for p in store.positions()]
    open_ = [p for p in marked if p["status"] == "open"]
    closed = [p for p in marked if p["status"] == "closed"]
    wins = sum(1 for p in closed if p["pnl"] > 0)
    losses = sum(1 for p in closed if p["pnl"] < 0)
    scratch = len(closed) - wins - losses
    return {
        "positions": marked,
        "open_count": len(open_),
        "open_pnl": round(sum(p["pnl"] for p in open_), 2),
        "realized_pnl": round(sum(p["pnl"] for p in closed), 2),
        "capital_at_risk": round(sum(p["trade"].get("max_loss") or 0 for p in open_), 2),
        # A $0 close is a scratch, neither a win nor a loss.
        "scratch": scratch,
        "win_rate": round(wins / (wins + losses), 3) if wins + losses else None,
    }


def close(md: MarketData, store: Store, pid: str) -> dict | None:
    pos = store.position(pid)
    if not pos or pos["status"] != "open":
        return pos
    value = position_value(pos["trade"]["legs"], current_prices(md, pos["trade"]["legs"], pos["trade"]["symbol"]))
    return mark(md, store.close_position(pid, value))
