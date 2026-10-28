"""The API's logic, shared by the FastAPI server and the static browser demo.

The server wraps these methods in routes (and keeps uploads, Claude profile reading and
the Origin check to itself). The browser calls route() through Pyodide instead of fetch,
so both modes run the same code. In static mode chat is rule-based and Claude is never used.
"""

from __future__ import annotations

import hashlib
import json
import math
from urllib.parse import parse_qsl, unquote, urlsplit

from . import __version__, chat as chat_mod, engine, portfolio
from .profile import RISK_LABELS, Profile, build_profile
from .strategies import RISK_LEVELS, STRATEGIES
from .universe import DOMAINS, TICKERS, lookup

DISCLAIMER = ("Charlie is an educational tool for paper trading. It is not a broker or a registered investment "
              "adviser, and nothing here is personalized financial advice. Options involve significant risk and "
              "are not suitable for all investors; read the OCC's 'Characteristics and Risks of Standardized "
              "Options' before trading real money. Data may be delayed, incomplete, or simulated.")


# Input limits (CHL-PS5, PS12): both the server and the demo's router go through these.
MAX_CAPITAL = 1e9
MAX_SHARES = 1e9
MAX_RESUME_CHARS = 50_000  # the profile is built from at most this much resume text (CHL-PS3)
MAX_SCREEN_NAME = 100
MAX_NOTE = 500
MAX_CHAT_CONTENT = 4000
MAX_CHAT_MESSAGES = 40


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def profile_hash(p: Profile) -> str:
    return hashlib.sha1(json.dumps(p.to_dict(), sort_keys=True).encode()).hexdigest()[:12]


def parse_holdings(holdings: str) -> dict[str, int]:
    hold = {}
    for part in holdings.replace(";", ",").split(","):
        bits = part.replace(":", " ").split()
        if len(bits) == 2 and bits[1].replace(".", "").isdigit():
            n = float(bits[1])
            if math.isfinite(n) and n <= MAX_SHARES:  # an absurd count is dropped, never a crash (CHL-PS5)
                hold[bits[0].upper()] = int(n)
    return hold


def _int(v, default=None):
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        raise ApiError(422, f"expected a number, got {v!r}")


# Screener criteria that must be numbers when given (CHL-R5: a bad value is a 422 naming the field).
NUMERIC_CRITERIA = ("min_score", "max_price", "min_iv", "max_iv", "min_pop", "max_capital", "min_annualized",
                    "dte_min", "dte_max", "delta")


def _number(v, field: str) -> float:
    if isinstance(v, bool):
        raise ApiError(422, f"{field} must be a number, not {v!r}.")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ApiError(422, f"{field} must be a number, not {v!r}.")
    if not math.isfinite(x):
        raise ApiError(422, f"{field} must be a finite number.")
    return x


def check_capital(v) -> float:
    """Paper capital must be a finite number above 0 and at most $1 billion (CHL-PS5)."""
    x = _number(25000 if v is None or v == "" else v, "capital")
    if not 0 < x <= MAX_CAPITAL:
        raise ApiError(422, "capital must be more than $0 and at most $1,000,000,000.")
    return x


def clean_criteria(criteria) -> dict:
    """Check the screener's criteria before the engine sees them, so bad input is a 422, never a 500."""
    if not isinstance(criteria, dict):
        raise ApiError(422, "criteria must be an object.")
    c = dict(criteria)
    for k in NUMERIC_CRITERIA:
        if c.get(k) not in (None, ""):
            c[k] = _number(c[k], k)
    for k in ("dte_min", "dte_max"):
        if c.get(k) not in (None, ""):
            c[k] = int(c[k])
    if c.get("scope") not in (None, "", "circle", "all", "list"):
        raise ApiError(422, "scope must be circle, all or list.")
    for k in ("symbols", "domains", "strategies"):
        v = c.get(k)
        if isinstance(v, str):
            v = [x for x in v.replace(",", " ").split() if x]
        if v not in (None, "") and (not isinstance(v, list) or not all(isinstance(x, str) for x in v)):
            raise ApiError(422, f"{k} must be a list of names.")
        if v is not None:
            c[k] = v
    return c


LEG_ACTIONS, LEG_INSTRUMENTS = ("buy", "sell"), ("stock", "call", "put")


def check_legs(legs) -> list[dict]:
    """A paper trade's legs must be complete before the store prices them (CHL-R5)."""
    if not isinstance(legs, list) or not legs:
        raise ApiError(422, "A paper trade needs at least one leg.")
    from .options_math import parse_occ
    for i, leg in enumerate(legs, 1):
        if not isinstance(leg, dict):
            raise ApiError(422, f"Leg {i} is not a leg object.")
        missing = [k for k in ("action", "instrument", "symbol", "qty", "price") if leg.get(k) in (None, "")]
        if missing:
            raise ApiError(422, f"Leg {i} is missing {', '.join(missing)}.")
        if leg["action"] not in LEG_ACTIONS:
            raise ApiError(422, f"Leg {i} action must be buy or sell.")
        if leg["instrument"] not in LEG_INSTRUMENTS:
            raise ApiError(422, f"Leg {i} instrument must be stock, call or put.")
        if not isinstance(leg["symbol"], str):
            raise ApiError(422, f"Leg {i} symbol must be text.")
        qty, price = _number(leg["qty"], f"Leg {i} qty"), _number(leg["price"], f"Leg {i} price")
        if qty <= 0 or qty != int(qty) or price < 0:
            raise ApiError(422, f"Leg {i} needs a whole positive qty and a price of 0 or more.")
        if leg["instrument"] != "stock":
            try:
                parse_occ(leg["symbol"])
            except Exception:
                raise ApiError(422, f"Leg {i} symbol isn't an option symbol.")
    return legs


def _leg_signature(trade: dict) -> tuple:
    """What makes two paper trades the same: symbol, strategy and legs (prices aside, since a
    re-click after the quote moved is still the same trade)."""
    legs = tuple(sorted((str(l["symbol"]), l["action"], l["instrument"], float(l["qty"])) for l in trade["legs"]))
    return str(trade["symbol"]).upper(), trade["strategy"], legs


def _bool(v) -> bool:
    return v is True or str(v).lower() in ("1", "true", "on", "yes")


class Api:
    def __init__(self, store, md, static: bool = False, default_profile=None):
        """default_profile(risk_level) is who the visitor sees before saving their own (the demo's sample person)."""
        self.store, self.md, self.static = store, md, static
        self.default_profile = default_profile

    def current_profile(self) -> Profile:
        data = self.store.get("profile")
        if data:
            return Profile.from_dict(data)
        if self.default_profile:
            return self.default_profile(self.store.get("sample_risk", 2))
        # Sensible starting point until the user fills in the intake.
        return build_profile(capital=25000, risk_level=2)

    # meta
    def status(self) -> dict:
        return {"version": __version__, "data": self.md.status(), "llm": not self.static and chat_mod.llm_available(),
                "has_profile": self.store.get("profile") is not None, "disclaimer": DISCLAIMER, "static": self.static}

    def meta(self) -> dict:
        return {
            "risk_levels": {k: {"label": v["label"], "blurb": v["blurb"], "plain": v["plain"], "max_risk_pct": v["max_risk_pct"]}
                            for k, v in RISK_LEVELS.items()},
            "strategies": {k: {kk: v[kk] for kk in ("label", "min_level", "outlook", "risk", "learn")}
                           for k, v in STRATEGIES.items()},
            "domains": [{"key": d.key, "label": d.label} for d in DOMAINS],
            "tickers": [{"symbol": t.symbol, "name": t.name, "domain": t.domain} for t in TICKERS],
            "disclaimer": DISCLAIMER,
        }

    # profile
    def get_profile(self) -> dict:
        intake = dict(self.store.get("intake", {}))
        text = intake.pop("resume_text", None)  # never send the resume back out; the length is enough for the UI
        if text is not None:
            intake["resume_chars"] = len(text)
        return {"profile": self.current_profile().to_dict(), "saved": self.store.get("profile") is not None,
                "intake": intake}

    def delete_profile(self, everything: bool = False) -> dict:
        """Delete the profile and resume. With everything=True also wipe saved screens, paper
        trades, cached ideas and the live-data cache (the "Delete my data" button's default)."""
        if everything:
            self.store.wipe()
            self._clear_market_cache()
            return {"ok": True, "deleted": ["profile", "resume", "saved screens", "paper trades", "cached ideas",
                                            "cached market data"]}
        self.store.delete("profile")
        self.store.delete("intake")
        self.store.delete("sample_risk")
        self.store.clear_daily()
        return {"ok": True}

    def _clear_market_cache(self) -> None:
        """Remove the cached quotes, chains, history and filings (CHL-PS8): their file names are the
        tickers the profile pointed to. Only the cache's own kind folders are touched."""
        import shutil
        from pathlib import Path

        from .data.market import TTL
        cache = getattr(self.md, "cache_dir", None)
        if not cache:
            return
        for kind in TTL:
            d = Path(cache) / kind
            if d.is_dir() and not d.is_symlink():
                shutil.rmtree(d, ignore_errors=True)

    def save_profile(self, text: str = "", interests: str = "", brands: str = "", holdings: str = "",
                     capital: float = 25000, risk_level: int = 2, name: str = "", boosts=None) -> dict:
        capital = check_capital(capital)
        if not text:
            text = self.store.get("intake", {}).get("resume_text", "")
        text = text[:MAX_RESUME_CHARS]
        p = build_profile(text, interests, brands, parse_holdings(holdings), capital, risk_level, name,
                          this_year=self.md.today.year,
                          domain_boosts=boosts[0] if boosts else None,
                          ticker_boosts=boosts[1] if boosts else None)
        if boosts:
            p.source = "rules + claude"
        self.store.put("profile", p.to_dict())
        self.store.put("intake", {"resume_text": text, "interests": interests, "brands": brands,
                                  "holdings": holdings, "capital": capital, "risk_level": risk_level, "name": name})
        return {"profile": p.to_dict(), "resume_chars": len(text)}

    def set_risk(self, risk_level: int) -> dict:
        p = self.current_profile()
        p.risk_level = max(1, min(5, risk_level))
        if self.default_profile and self.store.get("profile") is None:
            # Still the sample person: remember only the level, so the demo's prebuilt answers stay valid.
            self.store.put("sample_risk", p.risk_level)
        else:
            self.store.put("profile", p.to_dict())
        return {"risk_level": p.risk_level, "label": RISK_LABELS[p.risk_level]}

    # ideas & analysis
    def ideas(self, risk: int | None = None, count: int = 3, refresh: bool = False) -> dict:
        p = self.current_profile()
        level = max(1, min(5, risk or p.risk_level))
        day = self.md.today.isoformat()
        count = max(1, min(3, count))  # the engine clamps too; clamp first so the cache key can't grow (CHL-PS12)
        h = profile_hash(p) + f"-{count}"
        if not refresh:
            cached = self.store.daily_get(day, level, h)
            if cached:
                return cached
        result = engine.daily_ideas(self.md, p, level, count)
        self.store.daily_put(day, level, h, result)
        return result

    def ticker(self, symbol: str, risk: int | None = None) -> dict:
        if not lookup(symbol):
            raise ApiError(404, f"{symbol.upper()} isn't in Charlie's universe yet.")
        return engine.ticker_detail(self.md, self.current_profile(), symbol, risk)

    def screen(self, criteria: dict | None = None, risk: int | None = None, name: str | None = None,
               save: bool = False) -> dict:
        if name is not None and len(str(name)) > MAX_SCREEN_NAME:
            raise ApiError(422, f"name must be at most {MAX_SCREEN_NAME} characters.")
        criteria = clean_criteria(criteria or {})
        result = engine.screen(self.md, self.current_profile(), criteria, risk)
        if save and name:
            result["saved"] = self.store.save_screen(name, criteria)
        return result

    def screens(self) -> dict:
        return {"screens": self.store.screens(), "defaults": engine.DEFAULT_CRITERIA}

    def delete_screen(self, sid: str) -> dict:
        self.store.delete_screen(sid)
        return {"ok": True}

    # chat
    def chat(self, messages) -> dict:
        if isinstance(messages, list) and len(messages) > MAX_CHAT_MESSAGES:
            raise ApiError(422, f"messages: at most {MAX_CHAT_MESSAGES} per request.")
        if any(isinstance(m, dict) and isinstance(m.get("content"), str) and len(m["content"]) > MAX_CHAT_CONTENT
               for m in messages or []):
            raise ApiError(422, f"content: each message must be at most {MAX_CHAT_CONTENT} characters.")
        msgs = [m for m in messages or [] if isinstance(m, dict) and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)]
        if not msgs or msgs[-1]["role"] != "user":
            raise ApiError(400, "last message must be from the user")
        return chat_mod.chat(msgs[-20:], self.md, self.store, self.current_profile(), allow_llm=not self.static)

    # paper trading
    def paper(self) -> dict:
        return portfolio.summary(self.md, self.store)

    def paper_open(self, trade: dict, note: str = "") -> dict:
        if len(note or "") > MAX_NOTE:
            raise ApiError(422, f"note must be at most {MAX_NOTE} characters.")
        t = trade if isinstance(trade, dict) else {}
        if not t.get("legs") or not t.get("symbol") or t.get("strategy") not in STRATEGIES:
            raise ApiError(400, "not a valid trade")
        check_legs(t["legs"])
        if not isinstance(t["symbol"], str):
            raise ApiError(422, "symbol must be text.")
        new_loss = _number(t["max_loss"], "max_loss") if t.get("max_loss") is not None else 0.0
        p = self.current_profile()
        if STRATEGIES[t["strategy"]]["min_level"] > p.risk_level:
            raise ApiError(403, f"{STRATEGIES[t['strategy']]['label']} is above your risk level ({p.risk_level}).")
        open_ = [x for x in self.store.positions() if x.get("status") == "open"]
        sig = _leg_signature(t)
        if any(_leg_signature(x["trade"]) == sig for x in open_):
            raise ApiError(409, "You already have this paper trade open.")
        at_risk = sum(float(x["trade"].get("max_loss") or 0) for x in open_) + new_loss
        out = portfolio.mark(self.md, self.store.open_position(t, note))
        if at_risk > p.capital:
            out["warning"] = (f"Heads up: your open paper trades could now lose up to ${at_risk:,.0f}, more than your "
                              f"${p.capital:,.0f} of paper capital. Try closing one first.")
        return out

    def paper_close(self, pid: str) -> dict:
        pos = portfolio.close(self.md, self.store, pid)
        if not pos:
            raise ApiError(404, "no such position")
        return pos

    # the browser's router: same paths and payloads as the FastAPI routes
    def route(self, method: str, path: str, query: dict | None = None, body: dict | None = None) -> tuple[int, dict]:
        parts = urlsplit(path)
        q = dict(parse_qsl(parts.query))
        q.update(query or {})
        b = body if isinstance(body, dict) else {}
        seg = [unquote(s) for s in parts.path.strip("/").split("/")]
        if seg[:1] != ["api"]:
            return 404, {"detail": "Not Found"}
        seg, m = seg[1:], method.upper()
        try:
            if m == "GET" and seg == ["status"]:
                return 200, self.status()
            if m == "GET" and seg == ["meta"]:
                return 200, self.meta()
            if seg == ["profile"]:
                if m == "GET":
                    return 200, self.get_profile()
                if m == "DELETE":
                    return 200, self.delete_profile(_bool(q.get("all")))
                if m == "POST":  # the form's fields; there are no file uploads or Claude reading in the demo
                    return 200, self.save_profile(
                        str(b.get("resume_text", "")), str(b.get("interests", "")), str(b.get("brands", "")),
                        str(b.get("holdings", "")), check_capital(b.get("capital")), _int(b.get("risk_level"), 2),
                        str(b.get("name", "")),
                        boosts=None if self.static or not _bool(b.get("use_ai")) else self._enrich(b))
            if m == "POST" and seg == ["profile", "risk"]:
                return 200, self.set_risk(_int(b.get("risk_level"), 2))
            if m == "GET" and seg == ["ideas"]:
                return 200, self.ideas(_int(q.get("risk")), _int(q.get("count"), 3), _bool(q.get("refresh")))
            if m == "GET" and len(seg) == 2 and seg[0] == "ticker":
                return 200, self.ticker(seg[1], _int(q.get("risk")))
            if m == "POST" and seg == ["screen"]:
                return 200, self.screen(b.get("criteria") or {}, _int(b.get("risk")), b.get("name"), _bool(b.get("save")))
            if m == "GET" and seg == ["screens"]:
                return 200, self.screens()
            if m == "DELETE" and len(seg) == 2 and seg[0] == "screens":
                return 200, self.delete_screen(seg[1])
            if m == "POST" and seg == ["chat"]:
                return 200, self.chat(b.get("messages"))
            if seg == ["paper"]:
                if m == "GET":
                    return 200, self.paper()
                if m == "POST":
                    return 200, self.paper_open(b.get("trade"), str(b.get("note", "")))
            if m == "POST" and len(seg) == 3 and seg[0] == "paper" and seg[2] == "close":
                return 200, self.paper_close(seg[1])
        except ApiError as e:
            return e.status, {"detail": e.detail}
        return 404, {"detail": "Not Found"}

    def _enrich(self, b: dict):
        from .llm_profile import enrich
        return enrich(str(b.get("resume_text", ""))[:MAX_RESUME_CHARS], f"{b.get('interests', '')}\n{b.get('brands', '')}")
