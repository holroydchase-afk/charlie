"""FastAPI app: JSON API + the single-page web UI."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .data.market import get_market
from .handlers import DISCLAIMER, Api, ApiError  # noqa: F401  (DISCLAIMER re-exported for callers)
from .profile import extract_text
from .store import Store

WEB = Path(__file__).resolve().parent.parent / "web"

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


@app.exception_handler(ApiError)
async def api_error(request: Request, e: ApiError):
    return JSONResponse({"detail": e.detail}, status_code=e.status)


def md():
    return get_market()


def api() -> Api:
    # Built per request from the module globals, so tests can swap the store or market.
    return Api(store, md())


# ----------------------------------------------------------------------------- meta

@app.get("/api/status")
def status():
    return api().status()


@app.get("/api/meta")
def meta():
    return api().meta()


# ----------------------------------------------------------------------------- profile

@app.get("/api/profile")
def get_profile():
    return api().get_profile()


@app.delete("/api/profile")
def delete_profile(all: bool = False):  # noqa: A002 (the query parameter is ?all=true)
    return api().delete_profile(all)


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
    a = api()
    if not text:
        text = store.get("intake", {}).get("resume_text", "")
    boosts = None
    if use_ai:
        from .llm_profile import enrich
        boosts = enrich(text, interests + "\n" + brands)
    return a.save_profile(text, interests, brands, holdings, capital, risk_level, name, boosts)


class RiskBody(BaseModel):
    risk_level: int


@app.post("/api/profile/risk")
def set_risk(body: RiskBody):
    return api().set_risk(body.risk_level)


# ----------------------------------------------------------------------------- ideas & analysis

@app.get("/api/ideas")
def ideas(risk: int | None = None, count: int = 3, refresh: bool = False):
    return api().ideas(risk, count, refresh)


@app.get("/api/ticker/{symbol}")
def ticker(symbol: str, risk: int | None = None):
    return api().ticker(symbol, risk)


class ScreenBody(BaseModel):
    criteria: dict = {}
    risk: int | None = None
    name: str | None = None
    save: bool = False


@app.post("/api/screen")
def run_screen(body: ScreenBody):
    return api().screen(body.criteria, body.risk, body.name, body.save)


@app.get("/api/screens")
def list_screens():
    return api().screens()


@app.delete("/api/screens/{sid}")
def delete_screen(sid: str):
    return api().delete_screen(sid)


# ----------------------------------------------------------------------------- chat

class ChatBody(BaseModel):
    messages: list[dict]


@app.post("/api/chat")
def chat(body: ChatBody):
    return api().chat(body.messages)


# ----------------------------------------------------------------------------- paper trading

class PaperBody(BaseModel):
    trade: dict
    note: str = ""


@app.get("/api/paper")
def paper():
    return api().paper()


@app.post("/api/paper")
def paper_open(body: PaperBody):
    return api().paper_open(body.trade, body.note)


@app.post("/api/paper/{pid}/close")
def paper_close(pid: str):
    return api().paper_close(pid)


# ----------------------------------------------------------------------------- web

app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
