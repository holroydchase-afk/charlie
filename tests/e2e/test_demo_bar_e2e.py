"""CHL-DEMO-BAR (intake #35): the studio demo bar on the built static demo, in Chromium.

Spec: pm-tools docs/DEMO-BANNER.md ("Done when"), ported from pm-tools tests/e2e/demos.e2e.ts
(DEMO-BAR, DEMO-R1..R5). Fixtures: conftest.py. Runs only with CHARLIE_E2E=1.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
HOME = "https://chaseholroyd.com/"
GITHUB = "https://github.com/holroydchase-afk/charlie"
BACK = "← Back to Chase's portfolio"  # CHL-DEMO-R3
ENGINE = 120_000  # ms: the first Pyodide start in a cold browser
COPY = ("This is the real Charlie, running on made-up sample data. Anything you change is saved only "
        "in this browser and is never sent anywhere. Reset demo puts the sample data back.")
OVERFLOW = "document.documentElement.scrollWidth - window.innerWidth"


def _open(make_page, site_url, width=390, height=844, scheme=None):
    pg = make_page(width, height, scheme)
    pg.goto(site_url)
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    pg.click("#ack-btn")
    return pg


def _bar(pg):
    return pg.get_by_role("region", name="Demo")


def _toggle(pg):
    return _bar(pg).get_by_role("button", name="Demo details")


def _panel(pg):
    return pg.locator("#" + _toggle(pg).get_attribute("aria-controls"))


def _color(pg, expr):
    """A CSS color expression resolved to the browser's rgb() form."""
    return pg.evaluate("""(v) => { const i = document.createElement('i'); i.style.color = v;
        document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; }""", expr)


# ---------------------------------------------------------------- collapsed bar
@pytest.mark.parametrize("width", [390, 1280])
def test_CHL_DEMO_BAR_slim_and_collapsed_on_load(make_page, site_url, width):
    pg = _open(make_page, site_url, width)
    bar = _bar(pg)
    expect(bar).to_be_visible()
    box = bar.bounding_box()
    assert box["height"] <= 48, f"bar is {box['height']}px tall at {width}"
    assert box["y"] <= 1, f"the bar sits at the top of the page, not at y={box['y']}"
    assert bar.evaluate("(b) => getComputedStyle(b).position") in ("static", "relative"), "in the flow, not sticky"
    expect(bar.get_by_text("Demo", exact=True)).to_be_visible()
    toggle = _toggle(pg)
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(_panel(pg)).to_be_hidden()
    assert toggle.bounding_box()["height"] >= 44, "toggle is a 44px tap target"
    # DEMO-R1: the way back is on the collapsed bar, not only in the drawer.
    home = bar.get_by_role("link", name="← Portfolio")
    expect(home).to_be_visible()
    expect(home).to_have_attribute("href", HOME)
    assert home.bounding_box()["height"] >= 44, "back link is a 44px tap target"
    assert pg.evaluate(OVERFLOW) <= 0


def test_CHL_DEMO_BAR_collapsed_again_on_every_load(make_page, site_url):
    pg = _open(make_page, site_url)
    _toggle(pg).click()
    expect(_toggle(pg)).to_have_attribute("aria-expanded", "true")
    pg.reload()
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    expect(_toggle(pg)).to_have_attribute("aria-expanded", "false")
    expect(_panel(pg)).to_be_hidden()


@pytest.mark.parametrize("width", [320, 359])
def test_CHL_DEMO_BAR_no_sideways_scroll_and_back_link_visible_on_small_phones(make_page, site_url, width):
    pg = _open(make_page, site_url, width, 640)
    expect(_bar(pg).get_by_role("link", name="← Portfolio")).to_be_visible()
    assert pg.evaluate(OVERFLOW) <= 0, f"closed bar scrolls sideways at {width}"
    _toggle(pg).click()
    expect(_panel(pg)).to_be_visible()
    _panel(pg).get_by_role("button", name="Reset demo").click()
    expect(_panel(pg).get_by_role("button", name="Keep")).to_be_visible()
    assert pg.evaluate(OVERFLOW) <= 0, f"open drawer with the reset question scrolls sideways at {width}"


@pytest.mark.parametrize("width,expected", [(320, None), (359, None), (390, "Sample data"), (599, "Sample data"),
                                            (600, "Sample data · changes stay in this browser"),
                                            (1280, "Sample data · changes stay in this browser")])
def test_CHL_DEMO_BAR_middle_text_by_width(make_page, site_url, width, expected):
    pg = _open(make_page, site_url, width)
    expect(_bar(pg)).to_be_visible()
    mid = _bar(pg).locator(".demo-bar__sum")
    if expected is None:
        expect(mid).to_be_hidden()
    else:
        expect(mid).to_be_visible()
        assert " ".join(mid.inner_text().split()) == expected


# ---------------------------------------------------------------- drawer
@pytest.mark.parametrize("width", [390, 1280])
def test_CHL_DEMO_BAR_opens_to_standard_copy_pushes_app_down_esc_closes(make_page, site_url, width):
    pg = _open(make_page, site_url, width)
    app_top = """() => { let el = document.querySelector('section[aria-label="Demo"]').nextElementSibling;
        while (el && !el.getBoundingClientRect().height) el = el.nextElementSibling;
        return el ? el.getBoundingClientRect().top : NaN; }"""
    closed = pg.evaluate(app_top)
    toggle = _toggle(pg)
    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    panel = _panel(pg)
    expect(panel).to_be_visible()
    assert " ".join(panel.locator("p").first.inner_text().split()) == COPY
    assert pg.evaluate(app_top) > closed, "the drawer pushes the app down instead of covering it"
    # DEMO-R4: drawer text at least 16px; every control at least 44px tall.
    assert float(panel.locator("p").first.evaluate("(p) => getComputedStyle(p).fontSize")[:-2]) >= 16
    back = panel.get_by_role("link", name=BACK)
    expect(back).to_have_attribute("href", HOME)
    # CHL-DEMO-R4: the optional third action is there, a plain link to the public repo.
    gh = panel.get_by_role("link", name="Code on GitHub")
    expect(gh).to_be_visible()
    expect(gh).to_have_attribute("href", GITHUB)
    for el in (panel.get_by_role("button", name="Reset demo"), back, gh):
        assert el.bounding_box()["height"] >= 44, f"{el.inner_text()!r} is under 44px tall"
    # Order: Reset demo, then the way back, then GitHub.
    order = panel.evaluate("""(p) => [...p.querySelectorAll('a, button')].map((e) => e.textContent.trim())
        .filter((t) => t === 'Reset demo' || t.startsWith('← Back') || t === 'Code on GitHub')""")
    assert order == ["Reset demo", BACK, "Code on GitHub"], order
    assert pg.evaluate(OVERFLOW) <= 0, f"open drawer scrolls sideways at {width}"
    # Esc from inside the drawer closes it and puts focus back on the toggle.
    panel.get_by_role("button", name="Reset demo").focus()
    pg.keyboard.press("Escape")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(panel).to_be_hidden()
    assert pg.evaluate("document.activeElement.getAttribute('aria-label')") == "Demo details"
    assert pg.evaluate(app_top) == closed


# ---------------------------------------------------------------- look: the product's own type and colors
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_CHL_DEMO_BAR_drawn_in_charlies_type_and_colors(make_page, site_url, scheme):
    pg = _open(make_page, site_url, 1280, 800, scheme)
    bar = _bar(pg)
    bar_font, bar_bg, bar_fg = bar.evaluate(
        "(b) => { const s = getComputedStyle(b); return [s.fontFamily, s.backgroundColor, s.color]; }")
    body_font = pg.evaluate("getComputedStyle(document.body).fontFamily")
    assert bar_font.replace(" ", "") == body_font.replace(" ", ""), (bar_font, body_font)
    assert bar_bg == _color(pg, "var(--panel)"), "bar surface is Charlie's card surface (--panel)"
    assert bar_fg == _color(pg, "var(--ink)"), "bar text is Charlie's body text color (--ink)"
    # DEMO-R2: the Demo badge never wears the accent color, in fill, text or outline.
    accent = _color(pg, "var(--accent)")
    badge = bar.get_by_text("Demo", exact=True)
    worn = badge.evaluate("(e) => { const s = getComputedStyle(e); return [s.backgroundColor, s.color, s.borderTopColor]; }")
    assert accent not in worn, f"badge uses the accent {accent}: {worn}"


# ---------------------------------------------------------------- reset
def test_CHL_DEMO_BAR_reset_asks_first_and_keep_changes_nothing(make_page, site_url):
    pg = _open(make_page, site_url)
    # A visitor's paper trade, a risk change and another app's key (Pages shares one origin).
    card = pg.locator("#ideas .card").first
    card.locator("[data-paper]").click()
    expect(pg.locator("#toast")).to_contain_text("Paper trade opened", timeout=ENGINE)
    pg.evaluate("localStorage.setItem('charlie:kv:sample_risk', '4'); localStorage.setItem('other-demo:x', '1');"
                "window.__noReload = 1")
    before = pg.evaluate("JSON.stringify(Object.entries(localStorage).sort())")
    _toggle(pg).click()
    panel = _panel(pg)
    panel.get_by_role("button", name="Reset demo").click()
    expect(panel).to_contain_text("Put the sample data back? Your changes will be lost.")
    assert pg.evaluate("JSON.stringify(Object.entries(localStorage).sort())") == before, "the first tap clears nothing"
    panel.get_by_role("button", name="Keep").click()
    assert pg.evaluate("JSON.stringify(Object.entries(localStorage).sort())") == before
    assert pg.evaluate("window.__noReload") == 1, "Keep must not reload the page"
    expect(panel.get_by_role("button", name="Reset demo")).to_be_visible()
    expect(panel.get_by_role("button", name="Keep")).to_be_hidden()
    pg.click("[data-tab=paper]")
    expect(pg.locator("#paper-list [data-close]").first).to_be_attached(timeout=ENGINE)


def test_CHL_DEMO_BAR_reset_restores_sample_data_and_says_so_once(make_page, site_url):
    pg = _open(make_page, site_url)
    pg.evaluate("localStorage.setItem('charlie:kv:sample_risk', '4'); localStorage.setItem('other-demo:x', '1')")
    _toggle(pg).click()
    _panel(pg).get_by_role("button", name="Reset demo").click()
    with pg.expect_navigation():
        _panel(pg).get_by_role("button", name="Reset", exact=True).click()
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    keys = pg.evaluate("Object.keys(localStorage)")
    assert not [k for k in keys if k.startswith("charlie:")], keys
    assert "other-demo:x" in keys, "reset clears only Charlie's own keys"
    expect(_toggle(pg)).to_have_attribute("aria-expanded", "true")
    expect(_panel(pg)).to_be_visible()
    assert _panel(pg).locator("p").first.inner_text().strip().startswith("Sample data restored.")
    pg.reload()  # once: the next load is collapsed again
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    expect(_toggle(pg)).to_have_attribute("aria-expanded", "false")
    assert "Sample data restored." not in _bar(pg).inner_text()


# ---------------------------------------------------------------- exactly one demo notice
def test_CHL_DEMO_BAR_is_the_only_demo_notice(make_page, site_url):
    pg = _open(make_page, site_url)
    expect(pg.locator("#demo-banner, .demo-banner, #reset-demo")).to_have_count(0)
    expect(pg.get_by_role("region", name="Demo")).to_have_count(1)
    expect(pg.locator("[role=note]:visible")).to_have_count(0)


# ---------------------------------------------------------------- CHL-DEMO-R1 one "Sample data" in the top chrome
TOP_TEXT = """() => [document.querySelector('section[aria-label="Demo"]'), document.querySelector('header.top')]
    .map((e) => e.innerText).join(' ')"""


@pytest.mark.parametrize("width", [390, 1280])
def test_CHL_DEMO_R1_header_badge_hidden_so_sample_data_is_said_once(make_page, site_url, width):
    pg = _open(make_page, site_url, width)
    expect(pg.locator("#data-badge")).to_be_hidden()
    top = pg.evaluate(TOP_TEXT)
    assert top.count("Sample data") == 1, f"'Sample data' {top.count('Sample data')}x in the top chrome: {top!r}"


# ---------------------------------------------------------------- CHL-DEMO-R2 the bar lines up with the header
@pytest.mark.parametrize("width", [390, 700, 1280])
def test_CHL_DEMO_R2_back_link_lines_up_with_the_header_logo(make_page, site_url, width):
    pg = _open(make_page, site_url, width)
    home = _bar(pg).get_by_role("link", name="← Portfolio").bounding_box()["x"]
    logo = pg.locator("header.top .logo").bounding_box()["x"]
    assert abs(home - logo) <= 1, f"at {width}: ← Portfolio starts at {home}px, the logo at {logo}px"
    _toggle(pg).click()
    copy = _panel(pg).locator("p").first.bounding_box()["x"]
    assert abs(copy - logo) <= 1, f"at {width}: drawer copy starts at {copy}px, the logo at {logo}px"


# ---------------------------------------------------------------- the local app never shows it
def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def local_app(tmp_path):
    import httpx
    port = _free_port()
    env = {**os.environ, "CHARLIE_DATA": "mock", "CHARLIE_LLM": "off", "CHARLIE_TODAY": "2026-10-22",
           "CHARLIE_DB": str(tmp_path / "s.db"), "CHARLIE_CACHE": str(tmp_path / "cache")}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "charlie.server:app", "--host", "127.0.0.1",
                             "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(200):
            try:
                httpx.get(base + "/api/status", timeout=1)
                break
            except httpx.HTTPError:
                time.sleep(0.1)
        yield base + "/"
    finally:
        proc.terminate()
        proc.wait(10)


def test_CHL_DEMO_BAR_local_app_shows_no_demo_bar(browser, local_app):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    try:
        pg = ctx.new_page()
        pg.goto(local_app)
        expect(pg.locator("#ideas .card").first).to_be_visible(timeout=60_000)
        expect(pg.get_by_role("region", name="Demo")).to_have_count(0)  # hidden elements aren't in the a11y tree
        expect(pg.locator("section[aria-label=Demo]:visible, #demo-banner:visible")).to_have_count(0)
        expect(pg.get_by_role("link", name="← Portfolio")).to_have_count(0)
        # CHL-DEMO-R1: the local app keeps its header badge (mock vs live).
        expect(pg.locator("#data-badge")).to_be_visible()
        expect(pg.locator("#data-badge")).to_have_text("Demo data")
    finally:
        ctx.close()
