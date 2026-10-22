"""Exercise the Claude tool loop with a fake client (no network, no key)."""
from datetime import date
from types import SimpleNamespace as NS

import anthropic

from charlie import chat
from charlie.data.market import MarketData
from charlie.profile import build_profile
from charlie.store import Store


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        if len(self.calls) == 1:
            return NS(stop_reason="tool_use", content=[
                NS(type="text", text="Let me check."),
                NS(type="tool_use", id="tu_1", name="analyze_ticker", input={"symbol": "KO"}),
                NS(type="tool_use", id="tu_2", name="get_daily_ideas", input={}),
            ])
        return NS(stop_reason="end_turn", content=[NS(type="text", text="KO scores well. Max loss shown above.")])


def test_claude_tool_loop(monkeypatch):
    fake = FakeMessages()
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: NS(beta=NS(messages=fake)))
    monkeypatch.setenv("CHARLIE_LLM", "on")
    md = MarketData(mode="mock", today=date(2026, 10, 22), cache_dir="/tmp/charlie-test-cache")
    out = chat.chat([{"role": "user", "content": "Is Coca-Cola a good covered call?"}], md, Store(":memory:"),
                    build_profile("Beverage brand manager at Coca-Cola", capital=30000))
    assert out["mode"] == "claude" and "KO" in out["reply"]
    assert out["cards"]
    first, second = fake.calls
    assert first["model"] == "claude-opus-5-5" and first["fallbacks"] == "default"
    results = second["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["tu_1", "tu_2"]  # both results in one user turn
    assert not any(r.get("is_error") for r in results)


def test_claude_refusal_and_failure_fall_back(monkeypatch):
    md = MarketData(mode="mock", today=date(2026, 10, 22), cache_dir="/tmp/charlie-test-cache")
    p = build_profile(capital=30000)
    monkeypatch.setenv("CHARLIE_LLM", "on")
    refuse = NS(create=lambda **kw: NS(stop_reason="refusal", content=[]))
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: NS(beta=NS(messages=refuse)))
    assert "can't help" in chat.chat([{"role": "user", "content": "hi"}], md, Store(":memory:"), p)["reply"]

    def boom(*a, **k):
        raise anthropic.APIConnectionError(request=None)
    monkeypatch.setattr(anthropic, "Anthropic", boom)
    out = chat.chat([{"role": "user", "content": "Tell me about Visa"}], md, Store(":memory:"), p)
    assert out["mode"] == "rules" and "Claude unavailable" in out["reply"]
