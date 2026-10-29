"""M1.14 Demo verified: unit checks from the recruiter-ready re-review (docs/reviews/2026-10-28-recruiter-ready.md)."""
import re
from datetime import date
from pathlib import Path

from charlie.browser_store import BrowserStore
from charlie.data.market import MarketData
from charlie.handlers import Api
from tests.test_browser import FakeStorage

ROOT = Path(__file__).resolve().parents[1]


def test_CHL_UX40_delete_all_names_what_it_deleted_in_the_buttons_words():
    """The API's `deleted` list uses the words the local app's confirm shows ("saved market data",
    not "cached market data"), so the two never tell the user different things."""
    api = Api(BrowserStore(FakeStorage()), MarketData(mode="mock", today=date(2026, 10, 22)), static=True)
    deleted = api.delete_profile(everything=True)["deleted"]
    app = (ROOT / "web" / "app.js").read_text()
    local = re.search(r': "(profile, resume, saved screens, paper trades, saved ideas and saved market data)"', app)
    assert local, "the local app's delete confirm wording moved"
    words = local.group(1)
    assert [d for d in deleted if d not in words] == [], deleted


def test_CHL_UX41_chat_ideas_reply_names_the_data_in_plain_words():
    """The rule-based "What are today's ideas?" reply said "(mock (demo data, not real prices))":
    jargon and nested brackets. It now says "(sample data, not real prices)"."""
    api = Api(BrowserStore(FakeStorage()), MarketData(mode="mock", today=date(2026, 10, 22)), static=True)
    status, out = api.route("POST", "/api/chat", body={"messages": [{"role": "user", "content": "What are today's ideas?"}]})
    assert status == 200
    first = out["reply"].splitlines()[0]
    assert "mock" not in first.lower() and "((" not in first and "))" not in first, first
    assert "sample data, not real prices" in first, first


def test_CHL_UX42_portfolio_explains_alert_chips_before_any_fire():
    """A demo visitor's trades are opened on the pinned day, so no exit-plan rule fires and they never see
    an alert chip. The Portfolio intro names the chips so the feature isn't invisible."""
    html = (ROOT / "web" / "index.html").read_text()
    section = html[html.index('id="tab-paper"'):html.index("<!-- LEARN -->")]
    intro = section[:section.index('id="paper-stats"')]
    assert "id=\"alert-explainer\" hidden" in intro
    for label in ("Take profit?", "Near expiry", "Below breakeven"):
        assert label in intro, label
    app = (ROOT / "web" / "app.js").read_text()
    assert 'take_profit: "Take profit?", time: "Near expiry", breakeven: "Below breakeven"' in app
    assert '$("#alert-explainer").hidden = !r.positions.length' in app  # hidden while empty (keeps UX23's button high)
