"""FastAPI app: JSON API + the single-page web UI."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartParser

from . import __version__
from .data.market import get_market
from .handlers import (DISCLAIMER, MAX_CHAT_CONTENT, MAX_CHAT_MESSAGES, MAX_NOTE, MAX_RESUME_CHARS,  # noqa: F401
                       MAX_SCREEN_NAME, Api, ApiError, check_capital)
from .profile import FileTooComplex, extract_text
from .store import Store

WEB = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Charlie", version=__version__)
store = Store()
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
MAX_BODY = 9_000_000  # a request body over this is refused before it's parsed (CHL-PS6)
# Keep an uploaded resume in memory, never in a temp file on disk: every allowed body fits (CHL-PS6).
MultiPartParser.spool_max_size = MAX_BODY + 1_000_000

# The local app's own page: its files only, and it can't be framed (CHL-PS11).
PAGE_CSP = ("default-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


def _split_host(value: str) -> tuple[str, int | None]:
    """'localhost:8000' -> ('localhost', 8000); '[::1]:8000' -> ('::1', 8000). Port None when absent or bad."""
    try:
        u = urlsplit("//" + value)
        return (u.hostname or ""), u.port
    except ValueError:
        return "", None


OWN_HEADERS = (b"x-content-type-options", b"x-frame-options", b"cache-control", b"content-security-policy")


class LocalOnly:
    """Pure ASGI middleware for the single-user local app (CHL-PS2, PS6, PS11).

    - Host must be a loopback name (127.0.0.1, localhost, [::1]) on every method, which stops DNS rebinding.
    - A write that carries an Origin must come from a loopback page on this server's own port.
      Requests without one (curl, tests) are local.
    - POST/PUT/PATCH bodies over MAX_BODY get 413 before any form parsing, by Content-Length or by counting.
    - Every response gets nosniff and X-Frame-Options; /api/* also gets Cache-Control: no-store, and
      the page gets a strict CSP.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in OWN_HEADERS]
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-frame-options", b"DENY"))
                if path.startswith("/api/"):
                    headers.append((b"cache-control", b"no-store"))
                elif path == "/":
                    headers.append((b"content-security-policy", PAGE_CSP.encode()))
                message = {**message, "headers": headers}
            await send(message)

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        host, port = _split_host(headers.get("host", ""))
        if host not in LOCAL_HOSTS:
            return await self._reply(scope, send_with_headers, 400, "Charlie only answers on 127.0.0.1 or localhost.")
        method = scope.get("method", "GET")
        origin = headers.get("origin")
        if method not in ("GET", "HEAD", "OPTIONS") and origin:
            o = urlsplit(origin)
            try:
                o_port = o.port or {"http": 80, "https": 443}.get(o.scheme)
            except ValueError:
                o_port = None
            own_port = port or 80
            if (o.hostname or "") not in LOCAL_HOSTS or o_port != own_port:
                return await self._reply(scope, send_with_headers, 403, "Cross-site requests are not allowed.")
        if method in ("POST", "PUT", "PATCH"):
            length = headers.get("content-length")
            if length is not None:
                if not length.isdigit() or int(length) > MAX_BODY:
                    return await self._reply(scope, send_with_headers, 413, "That upload is too large (9 MB max).")
            else:  # no length (chunked): read up to the cap first, so nothing is parsed if it's too big
                chunks, size, more = [], 0, True
                while more:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body = message.get("body", b"")
                    size += len(body)
                    if size > MAX_BODY:
                        return await self._reply(scope, send_with_headers, 413, "That upload is too large (9 MB max).")
                    chunks.append(body)
                    more = message.get("more_body", False)
                buffered = [{"type": "http.request", "body": b"".join(chunks), "more_body": False}]

                async def replay():
                    return buffered.pop() if buffered else await receive()

                return await self.app(scope, replay, send_with_headers)
        return await self.app(scope, receive, send_with_headers)

    @staticmethod
    async def _reply(scope, send, status: int, detail: str):
        async def no_body():
            return {"type": "http.disconnect"}
        await JSONResponse({"detail": detail}, status_code=status)(scope, no_body, send)


app.add_middleware(LocalOnly)


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
    capital = check_capital(capital)  # before any parsing or Claude call (CHL-PS5)
    text = resume_text
    if resume is not None and resume.filename:
        data = await resume.read()
        if len(data) > 8_000_000:
            raise HTTPException(413, "Resume file is too large (8 MB max).")
        try:  # off the event loop, so one slow file can't freeze the app (CHL-PS3)
            text = (await run_in_threadpool(extract_text, resume.filename, data) + "\n" + resume_text).strip()
        except FileTooComplex:
            raise HTTPException(413, "That file unpacks to far more than a resume would. Try a PDF or plain text.")
        except Exception:
            raise HTTPException(400, "Couldn't read that file. Try a PDF, DOCX or plain text resume.")
    a = api()
    if not text:
        text = store.get("intake", {}).get("resume_text", "")
    text = text[:MAX_RESUME_CHARS]
    boosts = None
    if use_ai:
        from .llm_profile import enrich
        boosts = await run_in_threadpool(enrich, text, interests + "\n" + brands)
    return await run_in_threadpool(a.save_profile, text, interests, brands, holdings, capital, risk_level, name,
                                   boosts)


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
    name: str | None = Field(None, max_length=MAX_SCREEN_NAME)
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
    messages: list[dict] = Field(max_length=MAX_CHAT_MESSAGES)  # each content's length is checked in Api.chat


@app.post("/api/chat")
def chat(body: ChatBody):
    return api().chat(body.messages)


# ----------------------------------------------------------------------------- paper trading

class PaperBody(BaseModel):
    trade: dict
    note: str = Field("", max_length=MAX_NOTE)


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
