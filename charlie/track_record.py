"""How past ideas are doing: each one graded at today's price, next to holding SPY over the same days.

This measures the stock, not the trade: the underlying's move since the day of the idea and
whether today's price is above the trade's breakeven. It doesn't price options after the fact,
and it never claims a return. Shared by the server and the static demo.

Local app: past days come from the `daily` idea snapshots the user actually saw.
Static demo: the browser keeps only today's snapshot, so the sample record is rebuilt by
running the same engine on the mock market as it was on a few past weekdays.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from . import engine
from .data.market import MarketData
from .strategies import NFA

BENCHMARK = "SPY"
MAX_ITEMS = 30  # newest first; older ideas drop off the list
SAMPLE_DAYS_BACK = (7, 14, 28)  # the demo's past days, moved back to a weekday
_SAMPLE_CACHE: dict[tuple, list] = {}


def _weekday_on_or_before(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def sample_days(today: date) -> list[date]:
    return [_weekday_on_or_before(today - timedelta(days=n)) for n in SAMPLE_DAYS_BACK]


def sample_entries(today: date, profile, level: int, key: str) -> list[tuple[str, dict]]:
    """(day, idea) pairs for the demo: the engine's ideas on the mock market of each past day."""
    ck = (today.isoformat(), level, key)
    if ck not in _SAMPLE_CACHE:
        out = []
        for d in sample_days(today):
            ideas = engine.daily_ideas(MarketData(mode="mock", today=d), profile, level, 3)["ideas"]
            out += [(d.isoformat(), i) for i in ideas]
        if len(_SAMPLE_CACHE) > 16:
            _SAMPLE_CACHE.clear()
        _SAMPLE_CACHE[ck] = out
    return list(_SAMPLE_CACHE[ck])


def dedupe(entries: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Newest day first, one row per (day, symbol, strategy), in the order the ideas were ranked."""
    seen, out = set(), []
    for day, idea in sorted(entries, key=lambda e: e[0], reverse=True):
        t = idea.get("trade") or {}
        k = (day, t.get("symbol"), t.get("strategy"))
        if not t.get("symbol") or k in seen:
            continue
        seen.add(k)
        out.append((day, idea))
    return out[:MAX_ITEMS]


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _close_on(history: list[dict], day: str) -> float | None:
    """The last close on or before day."""
    best = None
    for row in history:
        if row.get("date", "") <= day and _finite(row.get("close")) and row["close"] > 0:
            best = row["close"]
    return best


def _signed(x: float) -> str:
    return f"{'up' if x >= 0 else 'down'} {abs(x) * 100:.1f}%"


def _outcome(symbol: str, price: float, breakeven, above, move: float, spy_move) -> str:
    if above is None:
        head = f"{symbol} is ${price:,.2f}."
    else:
        head = (f"{symbol} is ${price:,.2f}, {'above' if above else 'below'} breakeven "
                f"(${breakeven:,.2f}).")
    spy = f" SPY is {_signed(spy_move)} over the same days." if spy_move is not None else ""
    return f"{head} The stock is {_signed(move)} since the idea.{spy}"


def grade(md: MarketData, entries: list[tuple[str, dict]], level: int, sample: bool) -> dict:
    """Grade (day, idea) pairs at md's prices today."""
    today = md.today.isoformat()
    entries = [e for e in dedupe(entries) if e[0] < today]
    spy_now = md.quote(BENCHMARK)["price"] if entries else None
    spy_hist = md.history(BENCHMARK) if entries else []
    items, sources = [], []
    for day, idea in entries:
        t = idea["trade"]
        sym = t["symbol"]
        entry = t.get("spot")
        q = md.quote(sym)
        price = q["price"]
        if not (_finite(entry) and entry > 0 and _finite(price)):
            continue
        sources.append(q.get("source"))
        be = t.get("breakeven")
        be = float(be) if _finite(be) else None
        above = None if be is None else price >= be
        move = round(price / entry - 1, 5)
        spy_then = _close_on(spy_hist, day)
        spy_move = round(spy_now / spy_then - 1, 5) if spy_then and _finite(spy_now) else None
        items.append({"date": day, "symbol": sym, "strategy": t["strategy"], "label": t.get("label", t["strategy"]),
                      "entry_price": round(float(entry), 2), "price_today": round(float(price), 2),
                      "breakeven": be, "above_breakeven": above, "underlying_move_pct": move,
                      "spy_move_pct": spy_move, "outcome": _outcome(sym, price, be, above, move, spy_move)})
    spy_moves = [it["spy_move_pct"] for it in items if it["spy_move_pct"] is not None]
    summary = {
        "count": len(items),
        "above_breakeven": sum(1 for it in items if it["above_breakeven"] is True),
        "avg_underlying_move_pct": round(sum(it["underlying_move_pct"] for it in items) / len(items), 5) if items else None,
        "avg_spy_move_pct": round(sum(spy_moves) / len(spy_moves), 5) if spy_moves else None,
    }
    if md.mode == "mock" or (sources and all(s == "mock" for s in sources)):
        source = engine.MOCK_LABEL
    elif not sources or not any(s == "mock" for s in sources):
        source = "live (delayed)"
    else:
        source = "mixed (some demo prices; the rest are live, delayed)"
    return {"items": items, "summary": summary, "benchmark": BENCHMARK, "risk_level": level, "as_of": today,
            "sample": sample, "data_source": source, "disclaimer": NFA,
            "method": ("Each past idea at today's price: the stock's move since the idea, whether it's above the "
                       "trade's breakeven, and SPY's move over the same days. Options aren't re-priced.")}
