"""Strategy builders, the risk slider, and plain-English explanations.

The slider mirrors how brokers gate options approval (e.g. Alpaca: L1 covered
calls/cash-secured puts, L2 + long options, L3 + spreads), but starts one notch
lower with shares only. Nothing here ever sells an uncovered call, and nothing
trades same-week expirations.

Defaults follow widely used retail conventions: 30-50 days to expiration, short
strikes around 0.20-0.30 delta, take profits at ~50% of max, and revisit at ~21
days left. They are starting points, not guarantees.
"""

from __future__ import annotations

import math
from datetime import date

from .options_math import expected_move, prob_above

# Added by code to every trade and chat reply (CLAUDE.md hard rule), never left to a prompt.
NFA = "Not financial advice. Paper trading only."

STRATEGIES = {
    "shares": {
        "label": "Buy shares", "min_level": 1, "outlook": "bullish, long-term",
        "risk": "You can lose what you put in, but there's no expiration clock.",
        "learn": ("Owning the business outright. Munger's default: buy a wonderful company at a fair price "
                  "and sit on your hands. No leverage, no expiry, no options math."),
    },
    "cash_secured_put": {
        "label": "Cash-secured put", "min_level": 2, "outlook": "neutral to bullish; happy to own lower",
        "risk": "If the stock falls below the strike you buy 100 shares at the strike (minus the premium).",
        "learn": ("You sell someone the right to sell you 100 shares at a lower price, and set the cash aside to "
                  "cover it. You get paid now. If the stock stays above the strike, you keep the premium; if it "
                  "drops, you buy a company you already wanted, at a discount to today's price. Think of it as a "
                  "limit order that pays you while you wait. Same downside as owning the stock, minus the premium."),
    },
    "covered_call": {
        "label": "Covered call", "min_level": 2, "outlook": "neutral to mildly bullish on shares you own",
        "risk": "Caps your upside at the strike; shares can still fall.",
        "learn": ("You own 100 shares and sell someone the right to buy them from you at a higher price. You earn "
                  "the premium as extra income. If the stock rises past the strike, your shares get sold at that "
                  "price (still a profit). The trade-off: you give up gains above the strike."),
    },
    "collar": {
        "label": "Collar", "min_level": 3, "outlook": "protect shares you own",
        "risk": "Limits both downside and upside on shares you already hold.",
        "learn": ("On shares you own, buy a put (insurance) and pay for it by selling a call. Your losses are "
                  "floored at the put strike and your gains capped at the call strike. Good for protecting a big "
                  "winner without selling it."),
    },
    "bull_put_spread": {
        "label": "Bull put credit spread", "min_level": 3, "outlook": "neutral to bullish",
        "risk": "Max loss is fixed: the width between strikes minus the credit.",
        "learn": ("A cash-secured put with a safety net: you sell one put and buy a cheaper, lower-strike put. "
                  "You collect less premium, but your worst case is known and small, and it ties up far less "
                  "cash than buying 100 shares."),
    },
    "bull_call_spread": {
        "label": "Bull call debit spread", "min_level": 4, "outlook": "bullish over the next 1-3 months",
        "risk": "You can lose the whole debit if the stock doesn't rise.",
        "learn": ("Buy a call and sell a higher-strike call against it. Cheaper than a call alone, with a defined "
                  "maximum gain and a defined maximum loss (what you paid)."),
    },
    "leaps_call": {
        "label": "LEAPS call (stock replacement)", "min_level": 4, "outlook": "bullish over 9-18 months",
        "risk": "Can lose the full premium; time decay is slow but real.",
        "learn": ("A long-dated, in-the-money call that moves almost like the stock for a fraction of the cost. "
                  "Leverage, so size it small. Munger would remind you leverage is how smart people go broke."),
    },
    "long_call": {
        "label": "Long call", "min_level": 5, "outlook": "bullish, near-term move expected",
        "risk": "Most short-dated calls expire worthless; you can lose 100% quickly.",
        "learn": ("The lottery-ticket trade most beginners start with. Time decay works against you every day, "
                  "and you need the move to happen fast. Kept at the top of the slider for a reason."),
    },
}

RISK_LEVELS = {
    1: {"label": "Learn (shares only)", "max_risk_pct": 0.05, "max_collateral_pct": 0.0,
        "prefs": ["shares"],
        "blurb": "Ideas are plain stock purchases sized at 5% of your capital. Read the option explainers risk-free.",
        "plain": "Plain share purchases, each about 5% of your paper capital. Options wait in Learn until you're ready."},
    2: {"label": "Conservative", "max_risk_pct": 0.05, "max_collateral_pct": 0.5,
        "prefs": ["covered_call", "cash_secured_put", "shares"],
        "blurb": "Income strategies on companies you'd be glad to own: covered calls and cash-secured puts at ~0.20 delta, 30-50 days out.",
        "plain": "Steady-income trades on companies you'd be happy to own."},
    3: {"label": "Moderate", "max_risk_pct": 0.05, "max_collateral_pct": 0.5,
        "prefs": ["cash_secured_put", "bull_put_spread", "covered_call", "collar", "shares"],
        "blurb": "Adds defined-risk credit spreads and collars. Every trade has a known worst case.",
        "plain": "Adds spreads and collars. You know the worst case before you start."},
    4: {"label": "Growth", "max_risk_pct": 0.04, "max_collateral_pct": 0.5,
        "prefs": ["bull_call_spread", "leaps_call", "bull_put_spread", "cash_secured_put", "shares"],
        "blurb": "Adds debit spreads and LEAPS for more upside per dollar, with smaller position sizes.",
        "plain": "Adds trades that aim for more upside per dollar, with smaller position sizes."},
    5: {"label": "Speculative", "max_risk_pct": 0.02, "max_collateral_pct": 0.5,
        "prefs": ["long_call", "bull_call_spread", "leaps_call", "bull_put_spread", "shares"],
        "blurb": "Adds short-dated long calls, capped at 2% of capital per trade. Most of these lose; size accordingly.",
        "plain": "Adds short-term bets that a stock will rise. Most of these lose, so each is capped at 2% of your capital."},
}

DEFAULT_RISK_LEVEL = 2


def allowed(level: int) -> list[str]:
    return [k for k, v in STRATEGIES.items() if v["min_level"] <= level]


# ------------------------------------------------------------------ contract picking

def _liquid(c: dict, live: bool) -> bool:
    if c["bid"] <= 0 or c["ask"] <= 0:
        return False
    mid = (c["bid"] + c["ask"]) / 2
    if (c["ask"] - c["bid"]) / mid > 0.35:
        return False
    return c["open_interest"] >= (50 if live else 0)


MIN_LIQUID_PER_EXPIRY = 6


def pick_expiry(chain: list[dict], dte_min: int, dte_max: int, target: int, live: bool = False) -> str | None:
    """The expiration closest to `target` days. With live quotes, skip thin weeklies that have
    too few tradable contracts (real chains list many expirations nobody trades)."""
    pool = chain
    if live:
        counts: dict[str, int] = {}
        for c in chain:
            if _liquid(c, True):
                counts[c["expiry"]] = counts.get(c["expiry"], 0) + 1
        pool = [c for c in chain if counts.get(c["expiry"], 0) >= MIN_LIQUID_PER_EXPIRY]
    exps = sorted({(c["expiry"], c["dte"]) for c in pool if dte_min <= c["dte"] <= dte_max},
                  key=lambda e: abs(e[1] - target))
    return exps[0][0] if exps else None


def pick_by_delta(chain: list[dict], expiry: str, kind: str, target_abs_delta: float, live: bool,
                  below: float | None = None, above: float | None = None) -> dict | None:
    cands = [c for c in chain if c["expiry"] == expiry and c["kind"] == kind and _liquid(c, live)]
    if below is not None:
        cands = [c for c in cands if c["strike"] < below]
    if above is not None:
        cands = [c for c in cands if c["strike"] > above]
    if not cands:
        return None
    return min(cands, key=lambda c: abs(abs(c["delta"]) - target_abs_delta))


def pick_by_strike(chain: list[dict], expiry: str, kind: str, strike: float, live: bool) -> dict | None:
    cands = [c for c in chain if c["expiry"] == expiry and c["kind"] == kind and _liquid(c, live)]
    return min(cands, key=lambda c: abs(c["strike"] - strike)) if cands else None


# ------------------------------------------------------------------ builders

def _leg(action: str, c: dict | None = None, qty: int = 1, stock_symbol: str = "", price: float = 0.0) -> dict:
    if c is None:
        return {"action": action, "instrument": "stock", "symbol": stock_symbol, "qty": qty, "price": round(price, 2)}
    return {"action": action, "instrument": c["kind"], "symbol": c["symbol"], "strike": c["strike"],
            "expiry": c["expiry"], "qty": qty, "price": c["mid"], "bid": c["bid"], "ask": c["ask"],
            "delta": c["delta"], "iv": c["iv"]}


def _ticket(symbol: str, legs: list[dict], net: float | None) -> list[str]:
    lines = []
    for leg in legs:
        verb = {"buy": "BUY", "sell": "SELL"}[leg["action"]]
        if leg["instrument"] == "stock":
            lines.append(f"{verb} {leg['qty']} {symbol} shares @ LIMIT {leg['price']:.2f}")
        else:
            oc = "TO OPEN"
            lines.append(f"{verb} {oc} {leg['qty']} {symbol} {leg['expiry']} {leg['strike']:g} "
                         f"{leg['instrument'].upper()}")
    if net is not None and any(l["instrument"] != "stock" for l in legs):
        side = "CREDIT" if net > 0 else "DEBIT"
        lines.append(f"Order type: LIMIT {abs(net):.2f} {side} (mid price), good for the day")
    return lines


def _finish(strategy: str, symbol: str, spot: float, legs: list[dict], contracts: int, net: float | None,
            max_profit: float | None, max_loss: float, breakeven: float | None, pop: float | None,
            capital: float, dte: int | None, iv: float | None, management: list[str], extra: dict | None = None) -> dict:
    roc = (max_profit / capital) if (max_profit is not None and capital > 0) else None
    out = {
        "strategy": strategy,
        "label": STRATEGIES[strategy]["label"],
        "symbol": symbol,
        "spot": round(spot, 2),
        "legs": legs,
        "contracts": contracts,
        "net_premium": None if net is None else round(net, 2),
        "max_profit": None if max_profit is None else round(max_profit, 2),
        "max_loss": round(max_loss, 2),
        "breakeven": None if breakeven is None else round(breakeven, 2),
        "pop": None if pop is None else round(pop, 3),
        "capital_required": round(capital, 2),
        "return_on_capital": None if roc is None else round(roc, 4),
        # Annualizing only makes sense when the capital is fully cash-backed; on spreads it
        # produces silly four-digit numbers, so those show return on risk instead.
        "annualized": (round(roc * 365 / dte, 4)
                       if roc is not None and dte and strategy in ("cash_secured_put", "covered_call") else None),
        "return_on_risk": (round(max_profit / max_loss, 3)
                           if max_profit is not None and max_loss > 0 and strategy not in ("shares",) else None),
        "dte": dte,
        "expiry": next((l["expiry"] for l in legs if l["instrument"] != "stock"), None),
        "iv": None if iv is None else round(iv, 4),
        "expected_move": None if (iv is None or dte is None) else round(expected_move(spot, iv, dte / 365), 2),
        "ticket": _ticket(symbol, legs, net),
        "management": management,
        "risk": STRATEGIES[strategy]["risk"],
        "learn": STRATEGIES[strategy]["learn"],
        "min_level": STRATEGIES[strategy]["min_level"],
        "disclaimer": NFA,
    }
    if extra:
        out.update(extra)
    return out


class Infeasible(Exception):
    pass


def build(strategy: str, symbol: str, spot: float, chain: list[dict], capital: float, level: int,
          holdings: dict[str, int] | None = None, live: bool = False, params: dict | None = None) -> dict:
    """Build one concrete trade. Raises Infeasible with a human-readable reason."""
    if strategy not in STRATEGIES:
        raise Infeasible(f"unknown strategy {strategy}")
    if STRATEGIES[strategy]["min_level"] > level:
        raise Infeasible(f"{STRATEGIES[strategy]['label']} needs risk level {STRATEGIES[strategy]['min_level']}+")
    p = params or {}
    cfg = RISK_LEVELS[level]
    risk_budget = capital * cfg["max_risk_pct"]
    held = (holdings or {}).get(symbol, 0)

    if strategy == "shares":
        budget = capital * (0.05 if level == 1 else 0.10)
        qty = int(budget // spot)
        if qty < 1:
            raise Infeasible(f"one share (${spot:,.0f}) is more than {budget / capital:.0%} of your capital; consider fractional shares or the sector ETF")
        cost = qty * spot
        return _finish("shares", symbol, spot, [_leg("buy", qty=qty, stock_symbol=symbol, price=spot)], 0, None,
                       None, cost, spot, None, cost, None, None,
                       ["Hold while the business thesis holds; re-check after each earnings report.",
                        "Write down now what would make you sell (thesis broken), not a price target."],
                       {"shares": qty})

    dte_min, dte_max, target_dte = p.get("dte_min", 25), p.get("dte_max", 55), p.get("dte_target", 40)

    if strategy == "cash_secured_put":
        exp = pick_expiry(chain, dte_min, dte_max, target_dte, live) or pick_expiry(chain, 20, 70, target_dte, live)
        if not exp:
            raise Infeasible("no expiration 3-8 weeks out")
        target = p.get("delta", 0.20 if level <= 2 else 0.25)
        c = pick_by_delta(chain, exp, "put", target, live, below=spot)
        if not c:
            raise Infeasible("no liquid out-of-the-money put")
        collateral = c["strike"] * 100
        max_coll = capital * cfg["max_collateral_pct"]
        n = int(max_coll // collateral)
        if n < 1:
            raise Infeasible(f"one put needs ${collateral:,.0f} set aside, more than {cfg['max_collateral_pct']:.0%} of your capital")
        n = min(n, p.get("max_contracts", 1))
        credit = c["mid"]
        be = c["strike"] - credit
        t = c["dte"] / 365
        return _finish("cash_secured_put", symbol, spot, [_leg("sell", c, n)], n, credit, credit * 100 * n,
                       be * 100 * n, be, prob_above(spot, be, t, c["iv"] or 0.3), collateral * n, c["dte"], c["iv"],
                       ["Close early once you've captured ~50% of the premium.",
                        "With ~21 days left, close or roll if the put is near the money.",
                        f"If assigned, you own {100 * n} shares at an effective ${be:.2f} and can sell covered calls (the 'wheel')."],
                       {"effective_buy_price": round(be, 2), "discount_to_spot": round(1 - be / spot, 4)})

    if strategy == "covered_call":
        if held < 100:
            raise Infeasible("covered calls need 100 shares you already own (add holdings in your profile)")
        n = held // 100
        exp = pick_expiry(chain, dte_min, dte_max, target_dte, live)
        if not exp:
            raise Infeasible("no expiration 3-8 weeks out")
        c = pick_by_delta(chain, exp, "call", p.get("delta", 0.25), live, above=spot)
        if not c:
            raise Infeasible("no liquid out-of-the-money call")
        credit = c["mid"]
        t = c["dte"] / 365
        be = spot - credit
        return _finish("covered_call", symbol, spot, [_leg("sell", c, n)], n, credit,
                       (c["strike"] - spot + credit) * 100 * n, be * 100 * n, be,
                       prob_above(spot, be, t, c["iv"] or 0.3), spot * 100 * n, c["dte"], c["iv"],
                       ["Close early once you've captured ~50% of the premium.",
                        "If the stock runs past the strike and you want to keep the shares, roll up and out for a credit.",
                        "Avoid selling through an earnings date if you'd hate to lose the shares."],
                       {"yield_on_shares": round(credit / spot, 4)})

    if strategy == "collar":
        if held < 100:
            raise Infeasible("collars protect 100 shares you already own")
        n = held // 100
        exp = pick_expiry(chain, 45, 100, 75, live)
        if not exp:
            raise Infeasible("no expiration 6-14 weeks out")
        put = pick_by_delta(chain, exp, "put", 0.25, live, below=spot)
        call = pick_by_delta(chain, exp, "call", 0.25, live, above=spot)
        if not put or not call:
            raise Infeasible("no liquid strikes for a collar")
        net = call["mid"] - put["mid"]
        floor = put["strike"]
        return _finish("collar", symbol, spot, [_leg("buy", put, n), _leg("sell", call, n)], n, net,
                       (call["strike"] - spot + net) * 100 * n, max(0, (spot - floor - net)) * 100 * n, spot - net,
                       None, spot * 100 * n, put["dte"], put["iv"],
                       ["Let it run to expiry, or lift both legs together if your outlook changes.",
                        f"Your shares are protected below ${floor:g} until {exp}."])

    if strategy == "bull_put_spread":
        exp = pick_expiry(chain, dte_min, dte_max, target_dte, live)
        if not exp:
            raise Infeasible("no expiration 3-8 weeks out")
        short = pick_by_delta(chain, exp, "put", p.get("delta", 0.30), live, below=spot)
        if not short:
            raise Infeasible("no liquid out-of-the-money put")
        long_ = pick_by_strike(chain, exp, "put", short["strike"] - max(spot * p.get("width_pct", 0.03), 1), live)
        if long_ and long_["strike"] >= short["strike"]:
            lower = [c for c in chain if c["expiry"] == exp and c["kind"] == "put" and c["strike"] < short["strike"]
                     and _liquid(c, live)]
            long_ = max(lower, key=lambda c: c["strike"]) if lower else None
        if not long_:
            raise Infeasible("no protective lower put")
        width = short["strike"] - long_["strike"]
        credit = round(short["mid"] - long_["mid"], 2)
        if credit <= width * 0.12:
            raise Infeasible("credit too small for the risk")
        loss_per = (width - credit) * 100
        n = max(0, min(int(risk_budget // loss_per), p.get("max_contracts", 5)))
        if n < 1:
            raise Infeasible(f"max loss of ${loss_per:,.0f} per spread exceeds your ${risk_budget:,.0f} risk budget")
        be = short["strike"] - credit
        return _finish("bull_put_spread", symbol, spot, [_leg("sell", short, n), _leg("buy", long_, n)], n, credit,
                       credit * 100 * n, loss_per * n, be, prob_above(spot, be, short["dte"] / 365, short["iv"] or 0.3),
                       loss_per * n, short["dte"], short["iv"],
                       ["Close at ~50% of max profit.",
                        "If the stock closes below your short strike with 21 days left, close for a small loss rather than hoping.",
                        "Never let a spread go into expiration partly in the money (pin and assignment risk)."],
                       {"width": width})

    if strategy == "bull_call_spread":
        exp = pick_expiry(chain, 40, 90, 60, live)
        if not exp:
            raise Infeasible("no expiration 6-13 weeks out")
        long_ = pick_by_delta(chain, exp, "call", 0.55, live)
        short = pick_by_delta(chain, exp, "call", 0.38, live, above=long_["strike"]) if long_ else None
        if not long_ or not short:
            raise Infeasible("no liquid call strikes")
        width = short["strike"] - long_["strike"]
        debit = round(long_["mid"] - short["mid"], 2)
        if debit <= 0 or debit >= width:
            raise Infeasible("spread is mispriced")
        n = min(int(risk_budget // (debit * 100)), p.get("max_contracts", 5))
        if n < 1:
            raise Infeasible(f"one spread costs ${debit * 100:,.0f}, above your ${risk_budget:,.0f} risk budget")
        be = long_["strike"] + debit
        return _finish("bull_call_spread", symbol, spot, [_leg("buy", long_, n), _leg("sell", short, n)], n, -debit,
                       (width - debit) * 100 * n, debit * 100 * n, be,
                       prob_above(spot, be, long_["dte"] / 365, long_["iv"] or 0.3), debit * 100 * n,
                       long_["dte"], long_["iv"],
                       ["Take profits at 50-75% of max gain; the last bit isn't worth the wait.",
                        "Cut it if the reason you bought is gone, not because of daily wiggles."])

    if strategy in ("leaps_call", "long_call"):
        if strategy == "leaps_call":
            exp = pick_expiry(chain, 240, 800, 420, live)
            target = 0.75
            if not exp:
                raise Infeasible("no LEAPS expiration listed")
        else:
            exp = pick_expiry(chain, 30, 75, 50, live)
            target = 0.45
            if not exp:
                raise Infeasible("no expiration 4-10 weeks out")
        c = pick_by_delta(chain, exp, "call", target, live)
        if not c:
            raise Infeasible("no liquid call")
        cost = c["mid"] * 100
        n = min(int(risk_budget // cost), p.get("max_contracts", 3))
        if n < 1:
            raise Infeasible(f"one contract costs ${cost:,.0f}, above your ${risk_budget:,.0f} risk budget")
        be = c["strike"] + c["mid"]
        mgmt = (["Treat it like owning ~{:.0f} shares: hold for the thesis, not the daily price.".format(abs(c['delta']) * 100 * n),
                 "Roll or close with ~90 days left so time decay doesn't speed up on you."]
                if strategy == "leaps_call" else
                ["Decide your exit before entering: e.g. take profits at +50-100% or cut at -50%.",
                 "Close with 2-3 weeks left; don't hold to expiration hoping."])
        return _finish(strategy, symbol, spot, [_leg("buy", c, n)], n, -c["mid"], None, cost * n, be,
                       prob_above(spot, be, c["dte"] / 365, c["iv"] or 0.3), cost * n, c["dte"], c["iv"], mgmt,
                       {"share_equivalent": round(abs(c["delta"]) * 100 * n)})

    raise Infeasible("not implemented")


def scenario(trade: dict, moves=(-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2)) -> list[dict]:
    """P&L at expiration for a few price moves (intrinsic values only)."""
    spot = trade["spot"]
    out = []
    for m in moves:
        px = spot * (1 + m)
        pnl = 0.0
        for leg in trade["legs"]:
            sign = 1 if leg["action"] == "buy" else -1
            if leg["instrument"] == "stock":
                pnl += sign * (px - leg["price"]) * leg["qty"]
            else:
                intrinsic = max(0.0, px - leg["strike"]) if leg["instrument"] == "call" else max(0.0, leg["strike"] - px)
                pnl += sign * (intrinsic - leg["price"]) * 100 * leg["qty"]
        if trade["strategy"] in ("covered_call", "collar"):
            pnl += (px - spot) * 100 * trade["contracts"]
        out.append({"move": m, "price": round(px, 2), "pnl": round(pnl, 2)})
    return out


def is_finite(x) -> bool:
    return x is None or (isinstance(x, (int, float)) and math.isfinite(x))
