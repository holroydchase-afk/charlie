"""M1.13: track record and exit-plan alerts in the built static demo (Chromium). Runs with CHARLIE_E2E=1.

TR-UI: Today shows a #track-record section below the ideas, with past ideas (.track-item), the
SPY comparison, a sample label and the disclaimer, and no language that claims returns.
ALERT-UI: a paper position whose exit-plan rule fired shows an .alert-chip[data-alert=<type>] with
the message; a position with no alerts shows none. Positions are seeded into localStorage (the
demo's store) with made-up trades, so the alert is forced by the date, not by luck.
"""
import json
import os
import re
from datetime import date

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

from charlie.data.market import MarketData  # noqa: E402
from charlie.options_math import occ_symbol  # noqa: E402

NFA = "Not financial advice. Paper trading only."
PHONE = (390, 844)
DESKTOP = (1280, 800)
ENGINE = 120_000  # ms: the first Pyodide start in a cold browser
DAY = date(2026, 10, 22)  # the build's pinned day (conftest)
FORBIDDEN = ("guaranteed", "beat the market", "returns of")
SIZES = pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])


def _open(make_page, site_url, size, init_script=None):
    pg = make_page(*size)
    if init_script:
        pg.add_init_script(init_script)
    pg.goto(site_url)
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    pg.click("#ack-btn")
    return pg


# ---------------------------------------------------------------- TR-UI track record on Today
@SIZES
def test_TR_UI_track_record_shows_below_the_ideas_with_labels(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    box = pg.locator("#track-record")
    expect(box.locator(".track-item").first).to_be_visible(timeout=ENGINE)
    assert box.locator(".track-item").count() >= 3
    # Below the ideas.
    ideas_bottom = pg.locator("#ideas").bounding_box()
    tr_top = box.bounding_box()
    assert tr_top["y"] >= ideas_bottom["y"] + ideas_bottom["height"] - 1
    text = box.inner_text()
    assert "SPY" in text, "the record compares each idea with holding SPY"
    assert "sample" in text.lower(), "the demo's record is labeled as sample data"
    assert "breakeven" in text.lower()
    nfa = box.locator(".nfa", has_text=NFA)
    expect(nfa.first).to_be_visible()
    low = text.lower()
    assert [w for w in FORBIDDEN if w in low] == []
    # Each item names its stock and the day of the idea.
    first = box.locator(".track-item").first.inner_text()
    assert any(c.isupper() for c in first) and re.search(r"[A-Z][a-z]{2} \d{1,2}, 2026", first), first  # CHL-UX48 human dates
    # No sideways scroll at phone width.
    assert pg.evaluate("document.scrollingElement.scrollWidth <= innerWidth + 1")


# ---------------------------------------------------------------- ALERT-UI chips on paper positions
def _seed_positions():
    md = MarketData(mode="mock", today=DAY)
    unh, ko = md.quote("UNH")["price"], md.quote("KO")["price"]
    exp = date(2026, 11, 6)  # 15 days after DAY: the time rule fires
    strike = round(unh * 0.8)
    put = occ_symbol("UNH", exp, "put", strike)
    csp = {"strategy": "cash_secured_put", "label": "Cash-secured put", "symbol": "UNH", "spot": unh,
           "legs": [{"action": "sell", "instrument": "put", "symbol": put, "strike": float(strike),
                     "expiry": exp.isoformat(), "qty": 1, "price": 1.5}],
           "contracts": 1, "net_premium": 1.5, "max_profit": 150.0, "max_loss": (strike - 1.5) * 100,
           "breakeven": strike - 1.5, "capital_required": strike * 100.0, "dte": 15, "expiry": exp.isoformat(),
           "management": ["Close early once you've captured ~50% of the premium."], "disclaimer": NFA}
    entry = round(ko * 0.8, 2)  # well above breakeven today, no expiry: no alerts
    shares = {"strategy": "shares", "label": "Buy shares", "symbol": "KO", "spot": entry,
              "legs": [{"action": "buy", "instrument": "stock", "symbol": "KO", "qty": 10, "price": entry}],
              "contracts": 0, "net_premium": None, "max_profit": None, "max_loss": entry * 10, "breakeven": entry,
              "capital_required": entry * 10, "dte": None, "expiry": None, "management": [], "disclaimer": NFA}
    rows = [{"id": "e2ecsp0001", "opened": "2026-10-01T15:00:00+00:00", "symbol": "UNH", "strategy": "cash_secured_put",
             "trade": csp, "entry_value": -150.0, "status": "open", "closed": None, "exit_value": None, "note": ""},
            {"id": "e2eshr0001", "opened": "2026-10-02T15:00:00+00:00", "symbol": "KO", "strategy": "shares",
             "trade": shares, "entry_value": round(entry * 10, 2), "status": "open", "closed": None,
             "exit_value": None, "note": ""}]
    return f"localStorage.setItem('charlie:positions', {json.dumps(json.dumps(rows))});"


def _visible_rows(pg, symbol):
    return pg.locator("#paper-list .pos-card:visible, #paper-list tbody tr:visible").filter(has_text=symbol)


@SIZES
def test_ALERT_UI_position_with_a_fired_rule_shows_a_chip(make_page, site_url, size):
    pg = _open(make_page, site_url, size, init_script=_seed_positions())
    pg.click("[data-tab=paper]")
    unh = _visible_rows(pg, "UNH")
    expect(unh.first).to_be_visible(timeout=ENGINE)
    chip = unh.first.locator(".alert-chip[data-alert=time]")
    expect(chip).to_be_visible()
    assert "15 days" in chip.inner_text() or "15 days" in (chip.get_attribute("title") or ""), chip.inner_text()
    # A position with no alerts shows no chip.
    ko = _visible_rows(pg, "KO")
    expect(ko.first).to_be_visible()
    assert ko.first.locator(".alert-chip").count() == 0
