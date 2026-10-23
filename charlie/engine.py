"""Daily ideas, the criteria screener, and single-ticker analysis.

Selection follows Munger's process more than a quant model:
  1. Start inside the circle of competence (profile tickers).
  2. Keep only businesses that pass the quality/moat/balance-sheet checklist.
  3. Prefer the ones Mr. Market is offering at a reasonable price.
  4. Express the idea with the least risky structure the slider allows.
  5. Few, high-conviction ideas: 1-3 a day, never more, one per sector.
"""

from __future__ import annotations

import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor

from . import scoring
from .data.market import MarketData
from .profile import Profile
from .strategies import RISK_LEVELS, STRATEGIES, Infeasible, allowed, build, scenario
from .universe import DOMAIN_BY_KEY, TICKERS, lookup

MIN_SCORE_BY_LEVEL = {1: 55, 2: 55, 3: 50, 4: 50, 5: 45}


def _atm_iv(chain: list[dict], spot: float) -> float | None:
    near = [c for c in chain if 20 <= c["dte"] <= 60 and c["iv"] > 0]
    if not near:
        return None
    best = min(near, key=lambda c: abs(c["strike"] - spot))
    return best["iv"]


def analyze(md: MarketData, profile: Profile, symbol: str) -> dict:
    symbol = symbol.upper()
    info = lookup(symbol)
    q = md.quote(symbol)
    f = md.fundamentals(symbol)
    ch = md.chain(symbol)
    iv = _atm_iv(ch, q["price"])
    fam, why = profile.familiarity_for(symbol)
    s = scoring.score(symbol, f, q, fam, why, iv=iv, domain=info.domain if info else "")
    return {
        "symbol": symbol,
        "name": info.name if info else symbol,
        "domain": info.domain if info else None,
        "domain_label": DOMAIN_BY_KEY[info.domain].label if info else None,
        "quote": q,
        "fundamentals": f,
        "atm_iv": iv,
        "familiarity": fam,
        "familiarity_why": why,
        "charlie": s,
        "_chain": ch,
    }


def _analyze_all(md: MarketData, profile: Profile, symbols: list[str]) -> list[dict]:
    """Analyze in parallel where threads exist; in the browser (Pyodide) there are none."""
    if sys.platform == "emscripten":
        return [analyze(md, profile, s) for s in symbols]
    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(lambda s: analyze(md, profile, s), symbols))


def _public(a: dict) -> dict:
    return {k: v for k, v in a.items() if not k.startswith("_")}


def _thesis(a: dict, trade: dict) -> dict:
    s = a["charlie"]
    fac = {f["key"]: f for f in s["factors"]}
    strengths = [f for f in sorted(s["factors"], key=lambda f: -f["score"]) if f["score"] >= 60][:3]
    weak = [f for f in s["factors"] if f["score"] < 45]
    why_you = a["familiarity_why"] or ["broad, durable franchise outside your stated circle"]
    lines = [f"{a['name']} is a {s['lynch_category'].lower()} with a Charlie score of {s['score']} ({s['grade']})."]
    for f in strengths:
        lines.append(f"{f['key'].capitalize()}: {f['reason']}.")
    inversion = list(s["red_flags"])
    for f in weak:
        if f["key"] == "competence":
            inversion.append(f"Thin circle-of-competence evidence (familiarity {f['score']}/100): you may not spot trouble early.")
        else:
            inversion.append(f"Weak {f['key']}: {f['reason']}")
    if trade["strategy"] in ("cash_secured_put", "bull_put_spread"):
        inversion.append(f"A drop below ${trade['breakeven']:.2f} (about {100 * (1 - trade['breakeven'] / trade['spot']):.0f}% down) "
                         "means a loss; that's what happens in a market-wide selloff too.")
    elif trade["strategy"] in ("long_call", "bull_call_spread", "leaps_call"):
        inversion.append(f"If the stock is below ${trade['breakeven']:.2f} at expiry, you lose money; time works against you.")
    elif trade["strategy"] == "shares":
        inversion.append("If the thesis is wrong you can sit through a 30-50% drawdown; quality names have done this too.")
    if not inversion:
        inversion.append("No major red flags in the numbers; the main risk is paying too much or a broad market drop.")
    return {"summary": lines, "why_you": why_you, "inversion": inversion,
            "munger": fac.get("value", {}).get("quote") if s["score"] >= 62 else scoring.QUOTES["inversion"]}


def _trade_for(a: dict, profile: Profile, level: int, prefs: list[str], live: bool, params: dict | None = None):
    reasons = []
    for strat in prefs:
        try:
            t = build(strat, a["symbol"], a["quote"]["price"], a["_chain"], profile.capital, level,
                      profile.holdings, live=live, params=params)
            return t, reasons
        except Infeasible as e:
            reasons.append(f"{STRATEGIES[strat]['label']}: {e}")
    return None, reasons


def daily_ideas(md: MarketData, profile: Profile, level: int | None = None, count: int = 3) -> dict:
    level = int(level or profile.risk_level or 2)
    level = max(1, min(5, level))
    count = max(1, min(3, int(count)))
    symbols = [t["symbol"] for t in profile.tickers] or [t.symbol for t in TICKERS[:15]]
    for s in profile.holdings:
        if s not in symbols and lookup(s):
            symbols.append(s)

    analyses = _analyze_all(md, profile, symbols)

    live = all(a["quote"]["source"] != "mock" for a in analyses)
    # Rank by Charlie score; a small date-seeded tiebreak rotates near-equal names day to day.
    day = md.today.isoformat()

    def jitter(sym):
        return int(hashlib.md5(f"{sym}{day}".encode()).hexdigest()[:4], 16) / 65535 * 4

    ranked = sorted(analyses, key=lambda a: -(a["charlie"]["score"] + jitter(a["symbol"])))
    threshold = MIN_SCORE_BY_LEVEL[level]
    prefs = RISK_LEVELS[level]["prefs"]

    ideas, used_domains, skipped = [], set(), []
    eligible = []
    for a in ranked:
        if a["charlie"]["score"] < threshold:
            skipped.append({"symbol": a["symbol"], "reason": f"Charlie score {a['charlie']['score']} below {threshold}"})
        else:
            eligible.append(a)

    # Pass 1 expresses ideas with the options strategies the slider unlocks; pass 2
    # falls back to plain shares so a small account still gets ideas.
    option_prefs = [p for p in prefs if p != "shares"] or prefs
    for pass_prefs in (option_prefs, ["shares"]):
        for a in eligible:
            if len(ideas) >= count:
                break
            if a["domain"] in used_domains:
                continue
            rot = len(ideas) % len(pass_prefs)
            order = pass_prefs[rot:] + pass_prefs[:rot]
            # Covered calls on holdings come first: the lowest-risk use of what you own.
            if "covered_call" in order and profile.holdings.get(a["symbol"], 0) >= 100:
                order = ["covered_call"] + [o for o in order if o != "covered_call"]
            trade, why_not = _trade_for(a, profile, level, order, live)
            if not trade:
                if pass_prefs is option_prefs:
                    skipped.append({"symbol": a["symbol"], "reason": "; ".join(why_not)})
                continue
            trade["scenarios"] = scenario(trade)
            used_domains.add(a["domain"])
            ideas.append({"rank": len(ideas) + 1, "analysis": _public(a), "trade": trade, "thesis": _thesis(a, trade)})

    return {
        "date": day,
        "risk_level": level,
        "risk_label": RISK_LEVELS[level]["label"],
        "risk_blurb": RISK_LEVELS[level]["blurb"],
        "data_source": "live (delayed)" if live else "mock (demo data, not real prices)",
        "ideas": ideas,
        "considered": len(analyses),
        "skipped": skipped[:8],
        "note": None if ideas else "Nothing cleared the bar today. Munger: 'The big money is not in the buying or the selling, but in the waiting.'",
    }


DEFAULT_CRITERIA = {
    "scope": "circle",          # circle | all | list
    "symbols": [],
    "domains": [],
    "min_score": 50,
    "max_price": None,
    "min_iv": None,
    "max_iv": None,
    "strategies": [],           # empty = everything the slider allows
    "min_pop": None,
    "max_capital": None,
    "min_annualized": None,
    "dte_min": 25,
    "dte_max": 55,
    "delta": None,
    "exclude_red_flags": False,
}


def screen(md: MarketData, profile: Profile, criteria: dict, level: int | None = None, limit: int = 25) -> dict:
    c = {**DEFAULT_CRITERIA, **{k: v for k, v in (criteria or {}).items() if v not in (None, "", [])}}
    level = max(1, min(5, int(level or profile.risk_level or 2)))
    if c["scope"] == "list" and c["symbols"]:
        symbols = [s.upper() for s in c["symbols"]]
    elif c["scope"] == "all":
        symbols = [t.symbol for t in TICKERS]
    else:
        symbols = [t["symbol"] for t in profile.tickers] or [t.symbol for t in TICKERS]
    if c["domains"]:
        symbols = [s for s in symbols if lookup(s) and lookup(s).domain in c["domains"]]

    strategies = [s for s in (c["strategies"] or allowed(level)) if s in allowed(level)]
    params = {"dte_min": int(c["dte_min"]), "dte_max": int(c["dte_max"]),
              "dte_target": (int(c["dte_min"]) + int(c["dte_max"])) // 2}
    if c["delta"]:
        params["delta"] = float(c["delta"])

    analyses = _analyze_all(md, profile, symbols)
    live = all(a["quote"]["source"] != "mock" for a in analyses)

    rows, filtered = [], 0
    for a in analyses:
        sc = a["charlie"]
        px = a["quote"]["price"]
        iv = a["atm_iv"] or 0
        if sc["score"] < float(c["min_score"]):
            filtered += 1
            continue
        if c["max_price"] and px > float(c["max_price"]):
            filtered += 1
            continue
        if c["min_iv"] and iv * 100 < float(c["min_iv"]):
            filtered += 1
            continue
        if c["max_iv"] and iv * 100 > float(c["max_iv"]):
            filtered += 1
            continue
        if c["exclude_red_flags"] and sc["red_flags"]:
            filtered += 1
            continue
        for strat in strategies:
            try:
                t = build(strat, a["symbol"], px, a["_chain"], profile.capital, level, profile.holdings, live, params)
            except Infeasible:
                continue
            if c["min_pop"] and (t["pop"] is None or t["pop"] * 100 < float(c["min_pop"])):
                continue
            if c["max_capital"] and t["capital_required"] > float(c["max_capital"]):
                continue
            if c["min_annualized"] and (t["annualized"] is None or t["annualized"] * 100 < float(c["min_annualized"])):
                continue
            rows.append({
                "symbol": a["symbol"], "name": a["name"], "domain_label": a["domain_label"],
                "price": px, "iv": a["atm_iv"], "score": sc["score"], "grade": sc["grade"],
                "familiarity": a["familiarity"], "red_flags": sc["red_flags"], "trade": t,
            })
    # Sort: quality first, then probability of profit, then annualized return
    rows.sort(key=lambda r: (-r["score"], -(r["trade"]["pop"] or 0), -(r["trade"]["annualized"] or 0)))
    return {"criteria": c, "risk_level": level, "strategies": strategies, "results": rows[:limit],
            "total": len(rows), "filtered_out": filtered,
            "data_source": "live (delayed)" if live else "mock (demo data, not real prices)"}


def ticker_detail(md: MarketData, profile: Profile, symbol: str, level: int | None = None) -> dict:
    level = max(1, min(5, int(level or profile.risk_level or 2)))
    a = analyze(md, profile, symbol)
    trades, blocked = [], []
    for strat in STRATEGIES:
        if STRATEGIES[strat]["min_level"] > level:
            blocked.append({"strategy": strat, "label": STRATEGIES[strat]["label"],
                            "reason": f"unlocks at risk level {STRATEGIES[strat]['min_level']}"})
            continue
        try:
            t = build(strat, a["symbol"], a["quote"]["price"], a["_chain"], profile.capital, level,
                      profile.holdings, live=a["quote"]["source"] != "mock")
            t["scenarios"] = scenario(t)
            trades.append(t)
        except Infeasible as e:
            blocked.append({"strategy": strat, "label": STRATEGIES[strat]["label"], "reason": str(e)})
    hist = md.history(symbol)[-260:]
    return {**_public(a), "trades": trades, "blocked": blocked, "history": hist, "risk_level": level}
