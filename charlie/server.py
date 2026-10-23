"""FastAPI app: JSON API + the single-page web UI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, chat as chat_mod, engine, portfolio
from .data.market import get_market
from .profile import RISK_LABELS, Profile, build_profile, extract_text
from .store import Store
from .strategies import RISK_LEVELS, STRATEGIES
from .universe import DOMAINS, TICKERS

WEB = Path(__file__).resolve().parent.parent / "web"
DISCLAIMER = ("Charlie is an educational tool for paper trading. It is not a broker or a registered investment "
              "adviser, and nothing here is personalized financial advice. Options involve significant risk and "
              "are not suitable for all investors; read the OCC's 'Characteristics and Risks of Standardized "
              "Options' before trading real money. Data may be delayed, incomplete, or simulated.")

app = FastAPI(title="Charlie", version=__version__)
store = Store()
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@app.middleware("http")
async def same_origin_only(request: Request, call_next):
    """Refuse cross-site writes: a page on another site can't post a resume or chat here.

    Browsers send Origin on cross-site requests; requests without one (curl, tests) are local.
    """
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
        host = urlsplit(origin).hostname or ""
        own = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
        if host not in LOCAL_HOSTS and host != own:
            return JSONResponse({"detail": "Cross-site requests are not allowed."}, status_code=403)
    return await call_next(request)


def md():
    return get_market()


def current_profile() -> Profile:
    data = store.get("profile")
    if data:
        return Profile.from_dict(data)
    # Sensible starting point until the user fills in the intake.
    return build_profile(capital=25000, risk_level=2)


def profile_hash(p: Profile) -> str:
    return hashlib.sha1(json.dumps(p.to_dict(), sort_keys=True).encode()).hexdigest()[:12]


# ----------------------------------------------------------------------------- meta

@app.get("/api/status")
def status():
    return {"version": __version__, "data": md().status(), "llm": chat_mod.llm_available(),
            "has_profile": store.get("profile") is not None, "disclaimer": DISCLAIMER}


@app.get("/api/meta")
def meta():
    return {
        "risk_levels": {k: {"label": v["label"], "blurb": v["blurb"], "max_risk_pct": v["max_risk_pct"]}
                        for k, v in RISK_LEVELS.items()},
        "strategies": {k: {kk: v[kk] for kk in ("label", "min_level", "outlook", "risk", "learn")}
                       for k, v in STRATEGIES.items()},
        "domains": [{"key": d.key, "label": d.label} for d in DOMAINS],
        "tickers": [{"symbol": t.symbol, "name": t.name, "domain": t.domain} for t in TICKERS],
        "disclaimer": DISCLAIMER,
    }


# ----------------------------------------------------------------------------- profile

@app.get("/api/profile")
def get_profile():
    intake = dict(store.get("intake", {}))
    text = intake.pop("resume_text", None)  # never send the resume back out; the length is enough for the UI
    if text is not None:
        intake["resume_chars"] = len(text)
    return {"profile": current_profile().to_dict(), "saved": store.get("profile") is not None, "intake": intake}


@app.delete("/api/profile")
def delete_profile():
    store.delete("profile")
    store.delete("intake")
    store.clear_daily()
    return {"ok": True}


@app.post("/api/profile")
async def post_profile(
    resume: UploadFile | None = File(None),
    resume_text: str = Form(""),
    interests: str = Form(""),
    brands: str = Form(""),
    holdings: str = Form(""),
    capital: float = Form(25000),
    risk_level: int = Form(2),
    name: str = Form(""),
    use_ai: bool = Form(False),
):
    text = resume_text
    if resume is not None and resume.filename:
        data = await resume.read()
        if len(data) > 8_000_000:
            raise HTTPException(413, "Resume file is too large (8 MB max).")
        try:
            text = (extract_text(resume.filename, data) + "\n" + resume_text).strip()
        except Exception:
            raise HTTPException(400, "Couldn't read that file. Try a PDF, DOCX or plain text resume.")
    if not text:
        text = store.get("intake", {}).get("resume_text", "")
    hold = {}
    for part in holdings.replace(";", ",").split(","):
        bits = part.replace(":", " ").split()
        if len(bits) == 2 and bits[1].replace(".", "").isdigit():
            hold[bits[0].upper()] = int(float(bits[1]))
    boosts = None
    if use_ai:
        from .llm_profile import enrich
        boosts = enrich(text, interests + "\n" + brands)
    p = build_profile(text, interests, brands, hold, capital, risk_level, name,
                      this_year=md().today.year,
                      domain_boosts=boosts[0] if boosts else None,
                      ticker_boosts=boosts[1] if boosts else None)
    if boosts:
        p.source = "rules + claude"
    store.put("profile", p.to_dict())
    store.put("intake", {"resume_text": text[:50000], "interests": interests, "brands": brands,
                         "holdings": holdings, "capital": capital, "risk_level": risk_level, "name": name})
    return {"profile": p.to_dict(), "resume_chars": len(text)}


class RiskBody(BaseModel):
    risk_level: int


@app.post("/api/profile/risk")
def set_risk(body: RiskBody):
    p = current_profile()
    p.risk_level = max(1, min(5, body.risk_level))
    store.put("profile", p.to_dict())
    return {"risk_level": p.risk_level, "label": RISK_LABELS[p.risk_level]}


# ----------------------------------------------------------------------------- ideas & analysis

@app.get("/api/ideas")
def ideas(risk: int | None = None, count: int = 3, refresh: bool = False):
    p = current_profile()
    level = max(1, min(5, risk or p.risk_level))
    day = md().today.isoformat()
    h = profile_hash(p) + f"-{count}"
    if not refresh:
        cached = store.daily_get(day, level, h)
        if cached:
            return cached
    result = engine.daily_ideas(md(), p, level, count)
    store.daily_put(day, level, h, result)
    return result


@app.get("/api/ticker/{symbol}")
def ticker(symbol: str, risk: int | None = None):
    from .universe import lookup
    if not lookup(symbol):
        raise HTTPException(404, f"{symbol.upper()} isn't in Charlie's universe yet.")
    return engine.ticker_detail(md(), current_profile(), symbol, risk)


class ScreenBody(BaseModel):
    criteria: dict = {}
    risk: int | None = None
    name: str | None = None
    save: bool = False


@app.post("/api/screen")
def run_screen(body: ScreenBody):
    result = engine.screen(md(), current_profile(), body.criteria, body.risk)
    if body.save and body.name:
        result["saved"] = store.save_screen(body.name, body.criteria)
    return result


@app.get("/api/screens")
def list_screens():
    return {"screens": store.screens(), "defaults": engine.DEFAULT_CRITERIA}


@app.delete("/api/screens/{sid}")
def delete_screen(sid: str):
    store.delete_screen(sid)
    return {"ok": True}


# ----------------------------------------------------------------------------- chat

class ChatBody(BaseModel):
    messages: list[dict]


@app.post("/api/chat")
def chat(body: ChatBody):
    msgs = [m for m in body.messages if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)]
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(400, "last message must be from the user")
    return chat_mod.chat(msgs[-20:], md(), store, current_profile())


# ----------------------------------------------------------------------------- paper trading

class PaperBody(BaseModel):
    trade: dict
    note: str = ""


@app.get("/api/paper")
def paper():
    return portfolio.summary(md(), store)


@app.post("/api/paper")
def paper_open(body: PaperBody):
    t = body.trade
    if not t.get("legs") or not t.get("symbol") or t.get("strategy") not in STRATEGIES:
        raise HTTPException(400, "not a valid trade")
    p = current_profile()
    if STRATEGIES[t["strategy"]]["min_level"] > p.risk_level:
        raise HTTPException(403, f"{STRATEGIES[t['strategy']]['label']} is above your risk level ({p.risk_level}).")
    return portfolio.mark(md(), store.open_position(t, body.note))


@app.post("/api/paper/{pid}/close")
def paper_close(pid: str):
    pos = portfolio.close(md(), store, pid)
    if not pos:
        raise HTTPException(404, "no such position")
    return pos


# ----------------------------------------------------------------------------- web

app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
