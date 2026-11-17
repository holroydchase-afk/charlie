"""M3.1 Hunches tab in the browser (CHL-HUNCH-10, 15, 16, 17). Runs only with CHARLIE_E2E=1.

The tab lives in the local app (FastAPI on 127.0.0.1, mock data, LLM off), so these tests start
uvicorn the way test_demo_bar_e2e.py does; the static-demo half uses conftest's built site.
UI is found by role and label: the "Hunches" tab, a text box and a button whose names say "hunch",
and one article per research lead. The interface is pinned in tests/test_hunch.py's docstring.
"""
import os
import re
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
NFA = "Not financial advice. Paper trading only."
HEARING = ("Everyone wears earbuds all day now and OTC hearing aids are legal, "
           "so hearing health is about to become a huge consumer market.")
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
FORBIDDEN = re.compile(r"\b(winners?|buy|recommend(?:s|ed|ing|ation|ations)?|guaranteed?)\b", re.I)


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def local_app(tmp_path_factory):
    import httpx
    tmp = tmp_path_factory.mktemp("hunch-app")
    port = _free_port()
    env = {**os.environ, "CHARLIE_DATA": "mock", "CHARLIE_LLM": "off", "CHARLIE_TODAY": "2026-10-22",
           "CHARLIE_DB": str(tmp / "s.db"), "CHARLIE_CACHE": str(tmp / "cache")}
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


@pytest.fixture(scope="module")
def axe_source():
    path = os.environ.get("CHARLIE_AXE_JS")
    if not path:
        pytest.fail("set CHARLIE_AXE_JS to axe-core's axe.min.js (CI installs axe-core with npm)")
    return Path(path).read_text()


def _open(browser, url, width=1280, height=800, scheme="light"):
    ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(url)
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=60_000)
    if pg.locator("#ack-btn").is_visible():
        pg.click("#ack-btn")
    return ctx, pg


def _hunch_panel(pg):
    pg.get_by_role("tab", name="Hunches").click()
    panel = pg.get_by_role("tabpanel", name="Hunches")
    expect(panel).to_be_visible()
    return panel


def _run_hearing(pg):
    panel = _hunch_panel(pg)
    panel.get_by_role("textbox", name=re.compile("hunch", re.I)).fill(HEARING)
    panel.get_by_role("button", name=re.compile("hunch", re.I)).click()
    expect(panel.get_by_role("article").first).to_be_visible(timeout=60_000)
    return panel


# ============================================================ CHL-HUNCH-15 tab: local yes, static no

def test_CHL_HUNCH_15_local_app_shows_the_hunches_tab(browser, local_app):
    ctx, pg = _open(browser, local_app)
    try:
        expect(pg.get_by_role("tab", name="Hunches")).to_be_visible()
        assert pg.errors == []
    finally:
        ctx.close()


def test_CHL_HUNCH_15_static_demo_hides_the_hunches_tab(page):
    # Both directions: the local app shows it (above); the public demo never does.
    expect(page.get_by_role("tab", name="Hunches")).to_have_count(0)
    expect(page.locator("[data-tab=hunch]:visible, #tab-hunch:visible")).to_have_count(0)


# ============================================================ CHL-HUNCH-10 NFA on the panel and each trade card

def test_CHL_HUNCH_10_panel_and_every_trade_card_show_the_disclaimer(browser, local_app):
    ctx, pg = _open(browser, local_app)
    try:
        panel = _run_hearing(pg)
        expect(panel.get_by_text(NFA, exact=True).first).to_be_visible()
        cards = panel.get_by_role("article")
        assert 1 <= cards.count() <= 3
        for i in range(cards.count()):
            card = cards.nth(i)
            expect(card).to_contain_text("research lead", ignore_case=True)
            expect(card.get_by_text(NFA, exact=True)).to_have_count(1)
            if card.get_by_text(re.compile(r"max loss", re.I)).count():  # a card with a trade
                expect(card).to_contain_text(re.compile(r"breakeven", re.I))
                expect(card).to_contain_text(re.compile(r"exit plan", re.I))
        assert pg.errors == []
    finally:
        ctx.close()


# ============================================================ CHL-HUNCH-16 tab copy

def test_CHL_HUNCH_16_tab_copy_has_no_forbidden_words_and_uses_the_register(browser, local_app):
    ctx, pg = _open(browser, local_app)
    try:
        panel = _hunch_panel(pg)
        before = panel.inner_text()
        assert FORBIDDEN.findall(before) == [], before
        _run_hearing(pg)
        # Outside the research-lead cards (whose trade blocks reuse strategy copy like "Buy shares").
        outside = pg.evaluate("""() => {
            const p = document.querySelector('#tab-hunch').cloneNode(true);
            p.querySelectorAll('article').forEach((a) => a.remove());
            return p.innerText; }""")
        assert FORBIDDEN.findall(outside) == [], outside
        text = panel.inner_text().lower()
        assert "most exposed" in text and "research lead" in text
    finally:
        ctx.close()


# ============================================================ CHL-HUNCH-17 fit and axe

@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", [(390, 844), (1280, 800)])
def test_CHL_HUNCH_17_hunches_tab_fits_and_passes_axe(browser, local_app, axe_source, scheme, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # The local page's CSP allows same-origin scripts only, so axe is served as a same-origin file.
    axe_url = local_app + "__axe.min.js"
    pg.route(axe_url, lambda route: route.fulfill(body=axe_source, content_type="text/javascript"))
    try:
        pg.goto(local_app)
        expect(pg.locator("#ideas .card").first).to_be_visible(timeout=60_000)
        if pg.locator("#ack-btn").is_visible():
            pg.click("#ack-btn")
        problems = []
        for state in ("empty", "mapped"):
            if state == "empty":
                _hunch_panel(pg)
            else:
                _run_hearing(pg)
            if pg.evaluate("document.documentElement.scrollWidth > innerWidth"):
                problems.append(f"{state}: horizontal overflow")
            wide = pg.evaluate("""[...document.querySelectorAll('#tab-hunch *')].filter((el) => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1);
            }).map((el) => el.tagName + '.' + el.className).slice(0, 5)""")
            if wide:
                problems.append(f"{state}: off-screen {wide}")
            pg.add_script_tag(url=axe_url)
            found = pg.evaluate(
                "(tags) => axe.run(document, {runOnly: tags}).then((r) => r.violations.map((v) => "
                "v.id + ' ' + v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(', ')))", AXE_TAGS)
            problems += [f"{state}: {v}" for v in found]
        assert problems == []
        assert errors == []
    finally:
        ctx.close()
