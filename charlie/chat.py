"""Chat with Charlie.

With Anthropic credentials available (ANTHROPIC_API_KEY or an `ant auth login`
profile) and CHARLIE_LLM not set to "off", chat runs on Claude with tools that call
the same engine the UI uses. Otherwise a small rule-based assistant answers the
common questions so the app still works offline.
"""

from __future__ import annotations

import json
import os
import re

from . import engine, portfolio
from .data.market import MarketData
from .profile import Profile
from .store import Store
from .strategies import RISK_LEVELS, STRATEGIES
from .universe import DOMAINS, TICKERS, lookup

MODEL = os.environ.get("CHARLIE_MODEL", "claude-opus-5-5")

SYSTEM_PROMPT = """You are Charlie, an educational investing assistant inside a paper-trading app. Your thinking is \
modeled on Charlie Munger: stay inside the user's circle of competence, favor high-quality businesses with durable \
moats and sane balance sheets, demand a margin of safety, invert (ask what would make an idea fail), and be patient. \
You also borrow from Peter Lynch ("invest in what you know") and Benjamin Graham (Mr. Market, margin of safety).

How you work:
- Ground every number in tool results. Never invent prices, greeks, or fundamentals. If a tool says the data source \
is mock, tell the user the numbers are demo data.
- Respect the user's risk slider. Never suggest a strategy above their level; if they ask for one, explain what it \
is, what the level is for, and offer the closest allowed alternative. Never suggest naked/uncovered calls or \
same-week (0DTE) options.
- For any trade, state the maximum loss in dollars, the breakeven, and what would make it go wrong.
- Familiarity is an edge for finding ideas, not evidence of safety. Say so when the user leans on "I know this company".
- Prefer few, high-conviction ideas. Saying "nothing looks good today" is a fine answer.
- Teach. Explain jargon in plain words the first time you use it.
- This is education and paper trading, not personalized financial advice. Mention that briefly when you present \
specific trades, without lecturing.
Keep answers short and skimmable: a direct answer first, then a few bullets."""

TOOLS = [
    {"name": "get_profile", "description": "The user's circle-of-competence profile: top sectors with evidence, "
     "tickers they know, capital, risk level, and holdings.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_daily_ideas", "description": "Today's 1-3 ideas for this user, each with a concrete trade, Charlie "
     "(Munger-style) score, thesis, and inversion (what could go wrong).",
     "input_schema": {"type": "object", "properties": {
         "risk_level": {"type": "integer", "minimum": 1, "maximum": 5,
                        "description": "Override risk level; defaults to the user's slider."}},
         "additionalProperties": False}},
    {"name": "analyze_ticker", "description": "Quote, fundamentals, Charlie score with factor reasons, red flags, and "
     "every trade structure allowed at the user's risk level for one stock.",
     "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}},
                      "required": ["symbol"], "additionalProperties": False}},
    {"name": "run_screen", "description": "Screen stocks and option trades by criteria. Omit fields you don't need.",
     "input_schema": {"type": "object", "properties": {
         "scope": {"type": "string", "enum": ["circle", "all", "list"]},
         "symbols": {"type": "array", "items": {"type": "string"}},
         "domains": {"type": "array", "items": {"type": "string", "enum": [d.key for d in DOMAINS]}},
         "min_score": {"type": "number"}, "max_price": {"type": "number"},
         "min_iv": {"type": "number", "description": "percent"}, "max_iv": {"type": "number", "description": "percent"},
         "strategies": {"type": "array", "items": {"type": "string", "enum": list(STRATEGIES)}},
         "min_pop": {"type": "number", "description": "probability of profit, percent"},
         "max_capital": {"type": "number"}, "min_annualized": {"type": "number", "description": "percent"},
         "dte_min": {"type": "integer"}, "dte_max": {"type": "integer"},
         "exclude_red_flags": {"type": "boolean"}},
         "additionalProperties": False}},
    {"name": "explain_strategy", "description": "Plain-English explainer for an options strategy and the risk slider levels.",
     "input_schema": {"type": "object", "properties": {"strategy": {"type": "string", "enum": list(STRATEGIES)}},
                      "required": ["strategy"], "additionalProperties": False}},
    {"name": "get_paper_portfolio", "description": "The user's paper-trading positions with live P&L.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


def _compact_trade(t: dict) -> dict:
    keep = ("strategy", "label", "symbol", "spot", "contracts", "net_premium", "max_profit", "max_loss", "breakeven",
            "pop", "capital_required", "annualized", "dte", "expiry", "iv", "ticket", "management")
    return {k: t.get(k) for k in keep}


class ToolContext:
    def __init__(self, md: MarketData, store: Store, profile: Profile):
        self.md, self.store, self.profile = md, store, profile
        self.cards: list[dict] = []  # trades surfaced to the UI as clickable cards

    def run(self, name: str, args: dict) -> dict:
        p = self.profile
        if name == "get_profile":
            return {"summary": p.summary, "domains": [{k: d[k] for k in ("label", "familiarity", "evidence")} for d in p.domains],
                    "tickers": [{k: t[k] for k in ("symbol", "name", "familiarity")} for t in p.tickers[:12]],
                    "capital": p.capital, "risk_level": p.risk_level,
                    "risk_label": RISK_LEVELS[p.risk_level]["label"], "holdings": p.holdings}
        if name == "get_daily_ideas":
            r = engine.daily_ideas(self.md, p, args.get("risk_level") or p.risk_level)
            for i in r["ideas"]:
                self.cards.append(i["trade"])
            return {"data_source": r["data_source"], "risk_label": r["risk_label"], "note": r["note"],
                    "ideas": [{"symbol": i["trade"]["symbol"], "name": i["analysis"]["name"],
                               "charlie_score": i["analysis"]["charlie"]["score"],
                               "grade": i["analysis"]["charlie"]["grade"], "trade": _compact_trade(i["trade"]),
                               "thesis": i["thesis"]} for i in r["ideas"]]}
        if name == "analyze_ticker":
            sym = args["symbol"].upper()
            if not lookup(sym):
                return {"error": f"{sym} isn't in Charlie's universe yet. Known tickers: "
                                 + ", ".join(t.symbol for t in TICKERS)}
            d = engine.ticker_detail(self.md, p, sym)
            for t in d["trades"][:2]:
                self.cards.append(t)
            return {"symbol": sym, "name": d["name"], "quote": d["quote"], "atm_iv": d["atm_iv"],
                    "charlie": d["charlie"], "familiarity": d["familiarity"], "familiarity_why": d["familiarity_why"],
                    "trades": [_compact_trade(t) for t in d["trades"]],
                    "blocked": d["blocked"], "data_source": d["quote"]["source"]}
        if name == "run_screen":
            r = engine.screen(self.md, p, args)
            for row in r["results"][:3]:
                self.cards.append(row["trade"])
            return {"data_source": r["data_source"], "total": r["total"], "strategies": r["strategies"],
                    "results": [{"symbol": x["symbol"], "score": x["score"], "price": x["price"],
                                 "trade": _compact_trade(x["trade"])} for x in r["results"][:8]]}
        if name == "explain_strategy":
            s = STRATEGIES[args["strategy"]]
            return {**s, "risk_levels": {k: {"label": v["label"], "blurb": v["blurb"]} for k, v in RISK_LEVELS.items()},
                    "user_level": p.risk_level}
        if name == "get_paper_portfolio":
            sm = portfolio.summary(self.md, self.store)
            return {k: sm[k] for k in ("open_count", "open_pnl", "realized_pnl", "capital_at_risk", "win_rate")} | {
                "positions": [{"symbol": x["symbol"], "strategy": x["strategy"], "status": x["status"],
                               "pnl": x["pnl"], "max_loss": x["max_loss"]} for x in sm["positions"][:15]]}
        return {"error": f"unknown tool {name}"}


def llm_available() -> bool:
    if os.environ.get("CHARLIE_LLM", "auto").lower() == "off":
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.environ.get("CHARLIE_LLM", "").lower() == "on")


def chat_claude(messages: list[dict], ctx: ToolContext) -> str:
    import anthropic

    client = anthropic.Anthropic()
    convo = [{"role": m["role"], "content": m["content"]} for m in messages if m.get("content")]
    system = SYSTEM_PROMPT + (f"\n\nUser's risk level: {ctx.profile.risk_level} "
                              f"({RISK_LEVELS[ctx.profile.risk_level]['label']}). Capital: ${ctx.profile.capital:,.0f}.")
    for _ in range(8):
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system,
            tools=TOOLS,
            messages=convo,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            return "I can't help with that one. Try asking about a company, a strategy, or today's ideas."
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        convo.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            try:
                out = ctx.run(block.name, dict(block.input or {}))
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out, default=str)})
            except Exception as e:  # surface tool failures to the model instead of crashing the chat
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": f"Error: {e}", "is_error": True})
        convo.append({"role": "user", "content": results})
    return "I ran out of steps on that one. Could you narrow the question?"


# ----------------------------------------------------------------------------- offline fallback

_NAME_INDEX = sorted(((a, t.symbol) for t in TICKERS for a in (t.name.lower(),) + t.aliases),
                     key=lambda x: -len(x[0]))


def _find_symbol(text: str) -> str | None:
    for tok in re.findall(r"\$?\b([A-Z]{1,5}(?:\.[A-Z])?)\b", text):
        if len(tok) >= 2 and lookup(tok):
            return lookup(tok).symbol
    low = " " + text.lower() + " "
    for alias, sym in _NAME_INDEX:
        if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", low):
            return sym
    return None


_STRAT_WORDS = {
    "cash_secured_put": ("cash secured put", "cash-secured put", "csp", "sell a put", "selling puts", "short put"),
    "covered_call": ("covered call",),
    "collar": ("collar",),
    "bull_put_spread": ("put spread", "credit spread", "bull put"),
    "bull_call_spread": ("call spread", "debit spread", "bull call"),
    "leaps_call": ("leaps", "leap"),
    "long_call": ("long call", "buy a call", "buying calls"),
    "shares": ("buy shares", "just shares"),
}


def _money(x) -> str:
    return "n/a" if x is None else f"${x:,.0f}"


def _trade_line(t: dict) -> str:
    pop = f", ~{t['pop'] * 100:.0f}% chance of profit" if t.get("pop") else ""
    return (f"**{t['label']}** on {t['symbol']}: max loss {_money(t['max_loss'])}, "
            f"breakeven ${t['breakeven']:.2f}{pop}. Ticket: `{' | '.join(t['ticket'])}`")


def chat_rules(text: str, ctx: ToolContext) -> str:
    low = text.lower()
    p = ctx.profile

    for strat, words in _STRAT_WORDS.items():
        if any(w in low for w in words) and re.search(r"what|explain|how|teach|mean|is a|work", low):
            s = STRATEGIES[strat]
            lock = "" if s["min_level"] <= p.risk_level else f" (unlocks at risk level {s['min_level']}; you're at {p.risk_level})"
            return f"**{s['label']}**{lock}\n\n{s['learn']}\n\n**Risk:** {s['risk']}\n\n**Best when:** {s['outlook']}."

    if re.search(r"\b(risk|slider|safe|safest|levels?)\b", low) and not _find_symbol(text):
        lines = [f"You're at level {p.risk_level} ({RISK_LEVELS[p.risk_level]['label']}). The levels:"]
        for k, v in RISK_LEVELS.items():
            lines.append(f"- **{k}. {v['label']}**: {v['blurb']}")
        return "\n".join(lines)

    if re.search(r"portfolio|positions|my trades|p&l|pnl", low):
        r = ctx.run("get_paper_portfolio", {})
        if not r["positions"]:
            return "No paper trades yet. Open one from Today's Ideas with the **Paper trade** button."
        return (f"{r['open_count']} open paper positions, open P&L {_money(r['open_pnl'])}, realized "
                f"{_money(r['realized_pnl'])}, max capital at risk {_money(r['capital_at_risk'])}.")

    if re.search(r"screen|find|under \$?\d|cheap|below \$?\d|filter", low):
        crit = {}
        m = re.search(r"(?:under|below|less than)\s*\$?(\d+)", low)
        if m:
            crit["max_price"] = float(m.group(1))
        doms = [d.key for d in DOMAINS if any(w in low for w in (d.label.lower().split(" ")[0], d.key.split("_")[0]))]
        if doms:
            crit["domains"] = doms
            crit["scope"] = "all"
        r = ctx.run("run_screen", crit)
        if not r["results"]:
            return "Nothing matched. Try loosening the price or score limits in the Screener tab."
        lines = [f"Top matches ({r['data_source']}):"]
        for x in r["results"][:5]:
            lines.append(f"- {x['symbol']} (score {x['score']}): {_trade_line(x['trade'])}")
        return "\n".join(lines)

    sym = _find_symbol(text)
    if sym:
        r = ctx.run("analyze_ticker", {"symbol": sym})
        c = r["charlie"]
        lines = [f"**{r['name']} ({sym})** at ${r['quote']['price']:.2f} ({r['data_source']}). "
                 f"Charlie score **{c['score']} ({c['grade']})**, {c['lynch_category'].lower()}."]
        for f in c["factors"]:
            lines.append(f"- {f['key'].capitalize()} {f['score']}: {f['reason']}")
        if c["red_flags"]:
            lines.append("**Inversion (what could go wrong):** " + "; ".join(c["red_flags"]))
        if r["trades"]:
            lines.append("At your risk level, the most conservative structure: " + _trade_line(r["trades"][0]))
        return "\n".join(lines)

    if re.search(r"idea|today|pick|suggest|recommend|what should|trade", low):
        r = ctx.run("get_daily_ideas", {})
        if not r["ideas"]:
            return r["note"] or "Nothing cleared the bar today."
        lines = [f"Today's ideas at **{r['risk_label']}** ({r['data_source']}):"]
        for i in r["ideas"]:
            lines.append(f"- {i['name']} (score {i['charlie_score']}): {_trade_line(i['trade'])}")
        lines.append("Education and paper trading only, not financial advice.")
        return "\n".join(lines)

    return ("I can help with:\n- **\"What are today's ideas?\"**\n- **\"Tell me about COST\"** (any ticker or company)\n"
            "- **\"Explain a cash-secured put\"**\n- **\"Find trades under $100 in healthcare\"**\n"
            "- **\"How does the risk slider work?\"**\n- **\"How is my paper portfolio doing?\"**\n\n"
            "_Running in offline mode. Set ANTHROPIC_API_KEY for full conversational answers._")


def chat(messages: list[dict], md: MarketData, store: Store, profile: Profile) -> dict:
    ctx = ToolContext(md, store, profile)
    last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    mode = "rules"
    if llm_available():
        try:
            reply = chat_claude(messages, ctx)
            mode = "claude"
        except Exception as e:  # missing creds, network, API errors: degrade gracefully
            reply = chat_rules(last, ctx) + f"\n\n_(Claude unavailable: {type(e).__name__}; answered offline.)_"
    else:
        reply = chat_rules(last, ctx)
    seen, cards = set(), []
    for t in ctx.cards:
        key = (t["symbol"], t["strategy"], t.get("expiry"))
        if key not in seen:
            seen.add(key)
            cards.append(t)
    return {"reply": reply, "mode": mode, "cards": cards[:3]}
