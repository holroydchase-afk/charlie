"""M0.3: disclaimers added in code, resume privacy, and the Origin check on profile posts."""
import os
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

import anthropic
import pytest

os.environ["CHARLIE_DATA"] = "mock"
os.environ["CHARLIE_LLM"] = "off"
os.environ["CHARLIE_TODAY"] = "2026-10-22"

from charlie import chat
from charlie.data.market import MarketData
from charlie.profile import build_profile
from charlie.store import Store
from charlie.strategies import NFA, STRATEGIES, build

WEB = Path(__file__).resolve().parent.parent / "web"
RESUME = b"Fictional Person. Software engineer at Microsoft, Azure, Kubernetes. 2016 - present"


@pytest.fixture(scope="module")
def md():
    return MarketData(mode="mock", today=date(2026, 10, 22), cache_dir="/tmp/charlie-test-cache")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "p.db"
    from fastapi.testclient import TestClient

    from charlie import server
    server.store = Store(str(db))
    return TestClient(server.app, base_url="http://127.0.0.1:8000")


def test_disclaimer_text():
    assert NFA == "Not financial advice. Paper trading only."


@pytest.mark.parametrize("q", ["Tell me about Visa", "what are today's ideas", "explain a covered call",
                               "how does the risk slider work", "hello", "how is my portfolio"])
def test_every_rule_based_reply_ends_with_disclaimer(md, q):
    out = chat.chat([{"role": "user", "content": q}], md, Store(":memory:"), build_profile(capital=30000))
    assert out["reply"].rstrip("_ \n").endswith(NFA)


def test_claude_reply_refusal_and_fallback_end_with_disclaimer(md, monkeypatch):
    p = build_profile(capital=30000)
    monkeypatch.setenv("CHARLIE_LLM", "on")
    ok = NS(create=lambda **kw: NS(stop_reason="end_turn", content=[NS(type="text", text="KO looks fine.")]))
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: NS(beta=NS(messages=ok)))
    assert chat.chat([{"role": "user", "content": "hi"}], md, Store(":memory:"), p)["reply"].rstrip("_ \n").endswith(NFA)
    refuse = NS(create=lambda **kw: NS(stop_reason="refusal", content=[]))
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: NS(beta=NS(messages=refuse)))
    assert chat.chat([{"role": "user", "content": "hi"}], md, Store(":memory:"), p)["reply"].rstrip("_ \n").endswith(NFA)

    def boom(*a, **k):
        raise anthropic.APIConnectionError(request=None)
    monkeypatch.setattr(anthropic, "Anthropic", boom)
    out = chat.chat([{"role": "user", "content": "Tell me about Visa"}], md, Store(":memory:"), p)
    assert out["reply"].rstrip("_ \n").endswith(NFA)
    assert out["reply"].count(NFA) == 1


def test_every_trade_carries_disclaimer(md):
    for strat in ("shares", "cash_secured_put", "bull_put_spread"):
        t = build(strat, "KO", md.quote("KO")["price"], md.chain("KO"), 50000, 3)
        assert t["disclaimer"] == NFA


def test_ui_renders_disclaimer_on_every_trade_surface():
    js = (WEB / "app.js").read_text()
    assert NFA in js
    for fn in ("tradeBlock", "ideaCard", "renderChatMsg", "openTicker"):
        body = re.search(r"function " + fn + r"\(.*?\n}\n", js, re.S)
        assert body, fn
        assert "nfa()" in body.group(0), f"{fn} must render the disclaimer"


def test_ai_resume_reading_is_opt_in():
    html = (WEB / "index.html").read_text()
    box = re.search(r'<input type="checkbox" name="use_ai"[^>]*>', html).group(0)
    assert "checked" not in box
    assert "Anthropic" in html


def test_profile_get_hides_resume_text_and_delete_clears_it(client):
    r = client.post("/api/profile", files={"resume": ("r.txt", RESUME, "text/plain")}, data={"capital": "30000"})
    assert r.status_code == 200, r.text
    got = client.get("/api/profile").json()
    assert "resume_text" not in got["intake"]
    assert got["intake"]["resume_chars"] == len(RESUME.decode())
    assert "Fictional Person" not in str(got)
    assert client.delete("/api/profile").status_code == 200
    gone = client.get("/api/profile").json()
    assert gone["saved"] is False and gone["intake"] == {}


def test_profile_post_defaults_to_no_ai(client, monkeypatch):
    import charlie.llm_profile as llm
    called = []
    monkeypatch.setattr(llm, "enrich", lambda *a, **k: called.append(1))
    client.post("/api/profile", data={"resume_text": "nurse", "capital": "30000"})
    assert called == []


def test_cross_site_posts_are_rejected(client):
    evil = {"Origin": "https://evil.example.com"}
    assert client.post("/api/profile", data={"resume_text": "x"}, headers=evil).status_code == 403
    assert client.delete("/api/profile", headers=evil).status_code == 403
    assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}, headers=evil).status_code == 403
    ok = {"Origin": "http://127.0.0.1:8000"}
    assert client.post("/api/profile", data={"resume_text": "x"}, headers=ok).status_code == 200
    assert client.post("/api/profile", data={"resume_text": "x"}, headers={"Origin": "http://localhost:8000"}).status_code == 200


def test_unreadable_upload_error_is_generic(client):
    r = client.post("/api/profile", files={"resume": ("r.pdf", b"not a pdf at all", "application/pdf")})
    assert r.status_code == 400
    assert r.json()["detail"] == "Couldn't read that file. Try a PDF, DOCX or plain text resume."
