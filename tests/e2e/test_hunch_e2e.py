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


def _hunches_view(pg):
    """The Hunches view: a named region inside Search (it is no longer a tab panel of its own)."""
    return pg.get_by_role("region", name="Hunches", exact=True)


def _hunch_panel(pg):
    """Reach Hunches the way a person does since the app-style nav: Search, then Hunches in the switch.
    (Before the nav it was its own tab, get_by_role("tab", name="Hunches").) Already there: stay put."""
    panel = _hunches_view(pg)
    if not panel.is_visible():
        pg.get_by_role("tab", name="Search", exact=True).click()
        switch = pg.get_by_role("group", name="Search by")
        expect(switch).to_have_count(1)
        switch.get_by_role("button", name="Hunches", exact=True).click()
    expect(panel).to_be_visible()
    return panel


def _run_hearing(pg):
    panel = _hunch_panel(pg)
    panel.get_by_role("textbox", name=re.compile("hunch", re.I)).fill(HEARING)
    # Exact name: since the nav change the view also holds the switch's "Hunches" button, which a /hunch/i
    # pattern would match too.
    panel.get_by_role("button", name="Run hunch", exact=True).click()
    expect(panel.get_by_role("article").first).to_be_visible(timeout=60_000)
    return panel


# ============================================================ CHL-HUNCH-15 tab: local and (since M3.2) static demo

# Placement since the app-style nav (CHL-NAV-1): Hunches is a sub-view of Search behind a
# "Search by" switch (Screener / Hunches), the Search tab stays selected while it shows, #hunch deep-links,
# and the phone bar keeps exactly five tabs. Since M3.2 the static demo has the switch and the view too.

TABS = ["Today", "Search", "Chat", "Trades", "Learn"]
SIZES = [(390, 844), (1280, 800)]
SIZE_IDS = ["390x844", "1280x800"]


def _tab_names(pg):
    return [t.text_content().strip() for t in pg.get_by_role("tab").all()]


def _switch_buttons(pg):
    """The visible switch's two buttons (each view has its own copy; hidden views drop out of the a11y tree)."""
    sw = pg.get_by_role("group", name="Search by")
    expect(sw).to_have_count(1)
    return sw.get_by_role("button", name="Screener", exact=True), sw.get_by_role("button", name="Hunches", exact=True)


def _expect_on(pg, view):
    """Search stays the selected tab either way; the switch marks the view showing, and only that one."""
    expect(pg.get_by_role("tab", name="Search", exact=True)).to_have_attribute("aria-selected", "true")
    for name in TABS:
        if name != "Search":
            expect(pg.get_by_role("tab", name=name, exact=True)).to_have_attribute("aria-selected", "false")
    screener, hunches = _switch_buttons(pg)
    on, off = (hunches, screener) if view == "hunch" else (screener, hunches)
    expect(on).to_have_attribute("aria-current", "page")
    expect(off).not_to_have_attribute("aria-current", re.compile(".*"))
    expect(pg).to_have_url(re.compile(rf"#{view}$"))
    if view == "hunch":
        expect(_hunches_view(pg)).to_be_visible()
        expect(pg.locator("#tab-screener")).to_be_hidden()
    else:
        expect(pg.locator("#tab-screener")).to_be_visible()
        expect(_hunches_view(pg)).to_be_hidden()


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_15_local_app_reaches_hunches_from_search(browser, local_app, width, height):
    ctx, pg = _open(browser, local_app, width, height)
    try:
        assert _tab_names(pg) == TABS, "the tab bar must stay at exactly five tabs (CHL-NAV-1)"
        expect(pg.get_by_role("tab", name="Hunches")).to_have_count(0)
        pg.get_by_role("tab", name="Search", exact=True).click()
        _expect_on(pg, "screener")
        screener, hunches = _switch_buttons(pg)
        expect(hunches).to_be_in_viewport()
        box = hunches.bounding_box()
        assert box["height"] >= 44 and box["width"] >= 44, f"Hunches button is {box['width']:.0f}x{box['height']:.0f}"
        hunches.click()
        _expect_on(pg, "hunch")
        _switch_buttons(pg)[0].click()
        _expect_on(pg, "screener")
        assert _tab_names(pg) == TABS
        assert pg.errors == []
    finally:
        ctx.close()


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_15_hunch_address_deep_links_to_search_hunches(browser, local_app, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    try:
        pg.goto(local_app + "#hunch")
        expect(_hunches_view(pg)).to_be_visible(timeout=60_000)
        if pg.locator("#ack-btn").is_visible():
            pg.click("#ack-btn")
        _expect_on(pg, "hunch")
        pg.reload()
        expect(_hunches_view(pg)).to_be_visible(timeout=60_000)
        _expect_on(pg, "hunch")
        assert errors == []
    finally:
        ctx.close()


# Re-pinned by qa-tdd, Nov 23, for M3.2 (Chase's call, "can we get it to the demo?"). A spec change, not a
# weakening: these were "the static demo hides Hunches and #hunch falls back to Today". Now (CHL-HUNCH-DEMO-3)
# the demo reaches Hunches through Search exactly as the local app does, the bar keeps exactly five tabs and
# there is still no Hunches tab of its own. The "never imports anthropic" half stays in tests/test_hunch.py.
def test_CHL_HUNCH_15_DEMO_3_static_demo_reaches_hunches_from_search(page):
    expect(page.get_by_role("tab", name="Hunches")).to_have_count(0)
    assert _tab_names(page) == TABS
    page.get_by_role("tab", name="Search", exact=True).click()
    _expect_on(page, "screener")
    _switch_buttons(page)[1].click()
    _expect_on(page, "hunch")
    assert _tab_names(page) == TABS


def test_CHL_HUNCH_15_DEMO_3_static_demo_hunch_address_deep_links_to_search_hunches(make_page, site_url):
    pg = make_page(390, 844)
    pg.goto(site_url + "#hunch")
    pg.click("#ack-btn")
    expect(_hunches_view(pg)).to_be_visible(timeout=60_000)
    _expect_on(pg, "hunch")
    expect(pg.locator("#tab-today")).to_be_hidden()


# ============================================================ CHL-HUNCH-SW the Screener / Hunches switch (local app)

def _focused(loc):
    return loc.evaluate("(el) => el === document.activeElement")


def _tab_to(pg, loc, presses=40):
    for _ in range(presses):
        if _focused(loc):
            return True
        pg.keyboard.press("Tab")
    return _focused(loc)


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_SW_1_switch_is_reachable_and_works_from_the_keyboard(browser, local_app, width, height):
    ctx, pg = _open(browser, local_app, width, height)
    try:
        pg.get_by_role("tab", name="Search", exact=True).focus()
        pg.keyboard.press("Enter")
        _expect_on(pg, "screener")
        hunches = _switch_buttons(pg)[1]
        assert _tab_to(pg, hunches), "Tab never reaches the Hunches button"
        pg.keyboard.press("Enter")
        _expect_on(pg, "hunch")
        screener = _switch_buttons(pg)[0]
        assert _tab_to(pg, screener), "Tab never reaches the Screener button from Hunches"
        pg.keyboard.press("Space")
        _expect_on(pg, "screener")
        assert pg.errors == []
    finally:
        ctx.close()


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_SW_1_keyboard_focus_stays_on_the_switch_after_switching(browser, local_app, width, height):
    # Activating a switch button swaps the whole view; focus must land on the new view's switch, not fall back to
    # the top of the page (WCAG 2.4.3 focus order), so a keyboard user can switch straight back.
    ctx, pg = _open(browser, local_app, width, height)
    try:
        pg.get_by_role("tab", name="Search", exact=True).click()
        _switch_buttons(pg)[1].focus()
        pg.keyboard.press("Enter")
        _expect_on(pg, "hunch")
        where = pg.evaluate("""() => { const a = document.activeElement;
            return a && a.closest('.search-switch') && a.offsetParent ? a.textContent.trim() : (a ? a.tagName : 'none'); }""")
        assert where == "Hunches", f"after switching to Hunches, focus is on {where!r}"
        _switch_buttons(pg)[0].focus()
        pg.keyboard.press("Enter")
        _expect_on(pg, "screener")
        where = pg.evaluate("""() => { const a = document.activeElement;
            return a && a.closest('.search-switch') && a.offsetParent ? a.textContent.trim() : (a ? a.tagName : 'none'); }""")
        assert where == "Screener", f"after switching to Screener, focus is on {where!r}"
    finally:
        ctx.close()


def test_CHL_HUNCH_SW_2_aria_current_moves_with_the_view(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        pg.get_by_role("tab", name="Search", exact=True).click()
        for view in ("hunch", "screener", "hunch"):
            screener, hunches = _switch_buttons(pg)
            (hunches if view == "hunch" else screener).click()
            _expect_on(pg, view)
            # Exactly one switch button on the page claims to be the current view.
            current = pg.locator(".search-switch [aria-current=page]:visible")
            expect(current).to_have_count(1)
            expect(current).to_have_text("Hunches" if view == "hunch" else "Screener")
        # Leaving Search and coming back keeps the switch honest.
        pg.get_by_role("tab", name="Today", exact=True).click()
        expect(pg.get_by_role("group", name="Search by")).to_have_count(0)
        pg.get_by_role("tab", name="Search", exact=True).click()
        _expect_on(pg, "screener")
    finally:
        ctx.close()


@pytest.mark.parametrize("view", ["hunch", "screener"])
def test_CHL_HUNCH_SW_3_risk_slider_reruns_only_the_view_showing(browser, local_app, restore_risk, view):
    # Both directions: on Hunches the slider re-runs the hunch, not the screener; on Screener, the reverse.
    _set_risk(local_app, 2)
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        if view == "hunch":
            _run(pg, HEARING)
        else:
            with pg.expect_response(lambda r: r.url.endswith("/api/screen")):
                pg.get_by_role("tab", name="Search", exact=True).click()
            _run(pg, HEARING)  # a hunch result exists, so a wrong re-run would show
            _switch_buttons(pg)[0].click()
            _expect_on(pg, "screener")
        seen = []
        pg.on("request", lambda r: seen.append((r.url.rsplit("/", 1)[-1], r.post_data_json))
              if r.method == "POST" and r.url.endswith(("/api/hunch", "/api/screen")) else None)
        want = "hunch" if view == "hunch" else "screen"
        slider = pg.get_by_role("slider", name="Risk level")
        expect(slider).to_be_visible()
        with pg.expect_response(lambda r: r.url.endswith(f"/api/{want}") and r.request.method == "POST"):
            slider.fill("3")
        pg.wait_for_load_state("networkidle")
        assert [u for u, _ in seen] == [want], f"the slider on {view} sent {seen}"
        assert seen[0][1]["risk"] == 3, seen
        _expect_on(pg, view)
        assert pg.errors == []
    finally:
        ctx.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_SW_4_search_screener_and_search_hunches_pass_axe(browser, local_app, axe_source, scheme, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    axe_url = local_app + "__axe.min.js"
    pg.route(axe_url, lambda route: route.fulfill(body=axe_source, content_type="text/javascript"))
    try:
        pg.goto(local_app)
        expect(pg.locator("#ideas .card").first).to_be_visible(timeout=60_000)
        if pg.locator("#ack-btn").is_visible():
            pg.click("#ack-btn")
        problems = []
        for view in ("screener", "hunch"):
            if view == "screener":
                with pg.expect_response(lambda r: r.url.endswith("/api/screen")):
                    pg.get_by_role("tab", name="Search", exact=True).click()
            else:
                _switch_buttons(pg)[1].click()
            _expect_on(pg, view)
            if pg.evaluate("document.documentElement.scrollWidth > innerWidth"):
                problems.append(f"{view}: horizontal overflow")
            pg.add_script_tag(url=axe_url)
            found = pg.evaluate(
                "(tags) => axe.run(document, {runOnly: tags}).then((r) => r.violations.map((v) => "
                "v.id + ' ' + v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(', ')))", AXE_TAGS)
            problems += [f"{view}: {v}" for v in found]
        assert problems == []
        assert errors == []
    finally:
        ctx.close()


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


# ============================================================ M3.1 review fixes (red first, qa-tdd, Nov 17)
# ux-reviewer CHL-UX-H1 to H10 and privacy-security CHL-PS-H4 (scratchpad hunch-*-review.md). The unit
# half (CHL-PS-H1 to H6) is in tests/test_hunch.py. Not in scope: UX-H8 (the "Buy shares" trade-block
# exemption stays) and UX-H11 (shared engine sizing).

AI_POWER = "AI data centers need so much electricity that power demand is going to explode."
GIBBERISH = "Zorbly quandix flemwort will plonk the wibbertons."
HINT_ON = "Your hunch text is sent to Anthropic's Claude to draft the map."
# CHL-UX-H16 (round 2): the offline note leads with the reassurance. This constant moved with it, on purpose,
# so the CHL-PS-H4 hint test below pins the new copy with the same strictness.
HINT_OFF = "Your hunch stays on this computer. Charlie uses its built-in maps."
HEARING_PURE_ABROAD = ("Sonova", "Demant", "Amplifon")  # the hearing map's pure plays listed outside the US


def _run(pg, text):
    """Type a hunch, press Run hunch, wait for the result; returns (panel, the API's JSON)."""
    panel = _hunch_panel(pg)
    panel.get_by_role("textbox", name=re.compile("hunch", re.I)).fill(text)
    with pg.expect_response(lambda r: r.url.endswith("/api/hunch") and r.request.method == "POST") as resp:
        panel.get_by_role("button", name="Run hunch", exact=True).click()
    data = resp.value.json()
    if data["ideas"]:
        expect(panel.get_by_role("article").first).to_be_visible(timeout=60_000)
    else:
        expect(pg.locator("#hunch-result > *").first).to_be_visible(timeout=60_000)
    return panel, data


def _block_of(heading):
    """The panel (nearest enclosing div or section) that a heading heads."""
    return heading.locator("xpath=ancestor::*[self::div or self::section][1]")


# ---------------------------------------------------------------- CHL-PS-H4 + CHL-UX-H10 the hint follows status.llm

@pytest.mark.parametrize("llm,hint,other", [(True, HINT_ON, HINT_OFF), (False, HINT_OFF, HINT_ON)],
                         ids=["claude_on", "claude_off"])
def test_CHL_PS_H4_CHL_UX_H10_hint_says_whether_the_hunch_leaves_the_computer(browser, local_app, llm, hint, other):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))

    def status(route):  # the server runs with the LLM off; the page must follow whatever status.llm says
        res = route.fetch()
        body = res.json()
        body["llm"] = llm
        route.fulfill(response=res, json=body)
    pg.route("**/api/status", status)
    try:
        pg.goto(local_app)
        expect(pg.locator("#ideas .card").first).to_be_visible(timeout=60_000)
        if pg.locator("#ack-btn").is_visible():
            pg.click("#ack-btn")
        # The stub took (the chat tab already follows status.llm), so a miss below is the hint's own.
        expect(pg.locator("#chat-mode")).to_have_text(re.compile(r"^Claude is connected" if llm else r"^Offline"))
        panel = _hunch_panel(pg)
        expect(panel.get_by_text(hint, exact=False)).to_be_visible()
        expect(panel.get_by_text(other, exact=False)).to_have_count(0)
        assert not re.search(r"api key", panel.inner_text(), re.I), "API-key jargon on the Hunches tab"
        assert errors == []
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H1 "The trail" first, details folded

def test_CHL_UX_H1_the_trail_summary_comes_first_and_the_rest_is_folded(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        panel, data = _run(pg, HEARING)
        first = pg.locator("#hunch-result > *").first
        expect(first.get_by_role("heading", name="The trail")).to_be_visible()
        for row in ("Claim", "Premise", "Purest plays", "Research leads"):
            expect(first).to_contain_text(row)
        expect(first).to_contain_text("Sonova")  # the purest play, even though Charlie can't score it
        # Each research lead is a link in the summary that lands on its card.
        assert data["ideas"]
        run_y = panel.get_by_role("button", name="Run hunch", exact=True).bounding_box()["y"]
        for n, idea in enumerate(data["ideas"]):
            link = first.get_by_role("link", name=re.compile(re.escape(idea["symbol"])))
            expect(link).to_have_count(1)
            href = link.get_attribute("href")
            assert href and href.startswith("#"), href
            target = pg.locator(href)
            expect(target).to_have_count(1)
            assert target.evaluate("(el) => !!el.closest('article')"), f"{href} is not a research lead card"
            if n == 0:
                assert link.bounding_box()["y"] - run_y <= 1.5 * 844, "first lead link is more than 1.5 screens down"
        # Evidence is folded closed, one tap away.
        ev = panel.locator("summary", has_text=re.compile(r"evidence", re.I))
        expect(ev).to_have_count(1)
        fact = panel.get_by_text(re.compile(r"JAMA Otolaryngology"))
        expect(fact).to_be_hidden()
        ev.click()
        expect(fact).to_be_visible()
        ev.click()
        # Each lead's order details are folded too.
        cards = panel.get_by_role("article")
        for i in range(cards.count()):
            expect(cards.nth(i).get_by_role("heading", name=re.compile(r"order details", re.I))).to_be_hidden()
        height = pg.locator("#hunch-result").bounding_box()["height"]
        assert height < 4500, f"hearing result is {height:.0f}px tall at 390 with folds closed"
        assert pg.errors == []
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H2 honest "most exposed" heading

def test_CHL_UX_H2_heading_and_callout_when_every_scored_name_is_a_small_slice(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        panel, data = _run(pg, HEARING)
        assert {p["exposure"] for p in data["chain"] if p["scored"]} == {"small_slice"}, "fixture assumption"
        heading = panel.get_by_role("heading", name="Most exposed that Charlie can score", exact=True)
        expect(heading).to_be_visible()
        block = _block_of(heading)
        for name in HEARING_PURE_ABROAD:
            expect(block).to_contain_text(name)
        # The other direction: a map whose scored names include pure plays gets no such callout.
        panel, data = _run(pg, AI_POWER)
        assert "pure_play" in {p["exposure"] for p in data["chain"] if p["scored"]}, "fixture assumption"
        heading = panel.get_by_role("heading", name="Most exposed that Charlie can score", exact=True)
        expect(heading).to_be_visible()
        block_text = _block_of(heading).inner_text()
        unscored = [u["name"] for u in data["unscored"]]
        assert not [n for n in unscored if n in block_text], block_text
        assert pg.errors == []
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H3 metric values never wrap mid-word

LINE_BOXES = """(root) => [...root.querySelectorAll('.metric .v')].filter((el) => el.getClientRects().length)
  .map((el) => { const r = document.createRange(); r.selectNodeContents(el);
    const tops = new Set([...r.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top)));
    return [el.textContent.trim(), tops.size]; })"""


@pytest.mark.parametrize("width", [360, 390])
def test_CHL_UX_H3_no_lead_metric_wraps_on_a_phone(browser, local_app, width):
    ctx, pg = _open(browser, local_app, width, 844)
    try:
        _run(pg, HEARING)
        lines = pg.locator("#hunch-result").evaluate(LINE_BOXES)
        assert lines, "no metric values rendered"
        assert any(v == "Unlimited" for v, _ in lines), f"fixture assumption: no 'Unlimited' in {lines}"
        wrapped = [(v, n) for v, n in lines if n > 1]
        assert wrapped == [], wrapped
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H4 say each thing once

def test_CHL_UX_H4_unscored_note_score_and_exit_plan_each_appear_once(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        panel, data = _run(pg, HEARING)
        whole = pg.locator("#hunch-result").evaluate("(el) => el.textContent")
        n = len(re.findall(r"Can.t score yet", whole))
        assert n <= 1, f"'Can't score yet' appears {n} times"
        cards = panel.get_by_role("article")
        assert cards.count() == len(data["ideas"])
        problems = []
        for i, idea in enumerate(data["ideas"]):
            text = cards.nth(i).evaluate("(el) => el.textContent")
            s = idea["score"]
            shown = re.findall(rf"(?<![\d.]){s}\s*/\s*100|\b[Ss]core\s*:?\s*{s}(?![\d.])", text)
            if len(shown) != 1:
                problems.append(f"{idea['symbol']} score shown {len(shown)} times: {shown}")
            if idea["trade"] and idea["trade"]["management"]:
                plan = idea["trade"]["management"][0]
                if text.count(plan) != 1:
                    problems.append(f"{idea['symbol']} exit plan shown {text.count(plan)} times")
        assert problems == []
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H5 unmatched hunch has a next step

def test_CHL_UX_H5_unmatched_hunch_offers_the_two_example_hunches(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        for example, expect_sym in ((re.compile(r"hearing", re.I), "AAPL"), (re.compile(r"AI power", re.I), "NVDA")):
            panel, data = _run(pg, GIBBERISH)
            assert data["source"] == "none"
            result = pg.locator("#hunch-result")
            expect(result.get_by_role("heading", name="No map for this hunch yet")).to_be_visible()
            expect(result).not_to_contain_text("Time frame: Not set")
            buttons = result.get_by_role("button", name=re.compile(r"hearing|AI power", re.I))
            expect(buttons).to_have_count(2)
            with pg.expect_response(lambda r: r.url.endswith("/api/hunch")) as resp:
                result.get_by_role("button", name=example).click()
            assert resp.value.json()["source"] == "playbook"
            expect(panel.get_by_role("article").first).to_be_visible(timeout=60_000)
            expect(result).to_contain_text(expect_sym)
        assert pg.errors == []
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H6 small slice doesn't look like success

STYLE_OF = """(el) => { const c = getComputedStyle(el); return [c.color, c.backgroundColor]; }"""
TOKENS = """(names) => names.map((n) => { const d = document.createElement('span');
  d.style.color = `var(${n})`; document.body.appendChild(d); const v = getComputedStyle(d).color; d.remove(); return v; })"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_CHL_UX_H6_small_slice_exposure_is_not_styled_as_success(browser, local_app, scheme):
    ctx, pg = _open(browser, local_app, 390, 844, scheme)
    try:
        panel, _ = _run(pg, HEARING)
        who = _block_of(panel.get_by_role("heading", name="Who it touches"))
        small = who.get_by_text(re.compile(r"^\s*small slice", re.I))
        pure = who.get_by_text(re.compile(r"^\s*pure play", re.I))
        assert small.count() and pure.count()
        accent, good, accent_soft = pg.evaluate(TOKENS, ["--accent", "--good", "--accent-soft"])
        bad = []
        for i in range(small.count()):
            color, bg = small.nth(i).evaluate(STYLE_OF)
            if color in (accent, good) or bg == accent_soft:
                bad.append((small.nth(i).inner_text(), color, bg))
        assert bad == [], f"small slice uses the success colors ({accent}, {good}, {accent_soft}): {bad}"
        assert small.first.evaluate(STYLE_OF) != pure.first.evaluate(STYLE_OF), "small slice looks like pure play"
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H7 no rank math on screen

def test_CHL_UX_H7_no_raw_rank_math_is_shown(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        _run(pg, HEARING)
        shown = pg.locator("#hunch-result").inner_text()
        math = re.findall(r"×|\d\s*[x*]\s*\d+(?:\.\d+)?\s*=\s*\d", shown)
        assert math == [], math
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H9 44px disclosure toggles

def test_CHL_UX_H9_every_disclosure_toggle_on_the_tab_is_44px_tall(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        _run(pg, HEARING)
        short = pg.evaluate("""() => {
            const tab = document.querySelector('#tab-hunch');
            tab.querySelectorAll('details').forEach((d) => { d.open = true; });  // reach nested toggles too
            return [...tab.querySelectorAll('summary')].filter((s) => s.getClientRects().length)
              .map((s) => [s.textContent.trim().slice(0, 40), Math.round(s.getBoundingClientRect().height)])
              .filter(([, h]) => h < 44); }""")
        count = pg.locator("#tab-hunch summary").count()
        assert count, "no disclosure toggles on the tab"
        assert short == [], short
    finally:
        ctx.close()


# ============================================================ M3.1 review round 2 (red first, qa-tdd, Nov 17)
# ux-reviewer round 2, CHL-UX-H12 to H19 (scratchpad hunch-ux-review.md). H18 (orphan words) stays a
# manual screenshot check. The unit half of H14 is in tests/test_hunch.py. QA-R1 (qa-tdd's own): the
# page-height budget held only at the default risk level; it now holds at levels 1 to 5.

def _risk_level(base):
    import httpx
    return httpx.get(base + "api/profile", timeout=10).json()["profile"]["risk_level"]


def _set_risk(base, level):
    """Set the saved risk level before the page loads (the page reads it on load). Callers restore it."""
    import httpx
    r = httpx.post(base + "api/profile/risk", json={"risk_level": level}, timeout=10)
    r.raise_for_status()
    assert _risk_level(base) == level


def _at_risk(browser, base, level, width, height=844, scheme="light"):
    _set_risk(base, level)
    ctx, pg = _open(browser, base, width, height, scheme)
    expect(pg.locator("#risk")).to_have_value(str(level))
    return ctx, pg


@pytest.fixture
def restore_risk(local_app):
    before = _risk_level(local_app)
    yield
    _set_risk(local_app, before)


# ---------------------------------------------------------------- CHL-UX-H12 "Unlimited" fits inside its tile

METRIC_FIT = """(root) => [...root.querySelectorAll('.hunch-lead .metric .v')].filter((el) => el.getClientRects().length)
  .map((el) => { const r = document.createRange(); r.selectNodeContents(el);
    const text = r.getBoundingClientRect(), tile = el.closest('.metric').getBoundingClientRect();
    return { v: el.textContent.trim(), sw: el.scrollWidth, cw: el.clientWidth,
             textRight: Math.round(text.right), tileRight: Math.round(tile.right) }; })"""


@pytest.mark.parametrize("level", [2, 5])
@pytest.mark.parametrize("width", [360, 390])
def test_CHL_UX_H12_unlimited_fits_inside_its_metric_tile_on_a_phone(browser, local_app, restore_risk, width, level):
    ctx, pg = _at_risk(browser, local_app, level, width)
    try:
        _run(pg, HEARING)
        tiles = pg.locator("#hunch-result").evaluate(METRIC_FIT)
        assert any(t["v"] == "Unlimited" for t in tiles), f"fixture assumption: no 'Unlimited' in {tiles}"
        spill = [t for t in tiles if t["sw"] > t["cw"] or t["textRight"] > t["tileRight"]]
        assert spill == [], f"metric values spill out of their tiles at {width}px, risk {level}: {spill}"
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H13 a lead link lands below the sticky header

SETTLED = """() => new Promise((done) => { let last = -1, same = 0;
  const tick = () => { const y = scrollY; same = y === last ? same + 1 : 0; last = y;
    if (same >= 10) done(y); else requestAnimationFrame(tick); }; tick(); })"""


@pytest.mark.parametrize("width", [360, 390])
def test_CHL_UX_H13_after_tapping_a_trail_lead_the_company_name_is_below_the_header(browser, local_app, width):
    ctx, pg = _open(browser, local_app, width, 844)
    try:
        panel, data = _run(pg, HEARING)
        trail = pg.locator("#hunch-result > *").first
        expect(trail.get_by_role("heading", name="The trail")).to_be_visible()
        problems = []
        for n, idea in enumerate(data["ideas"], start=1):
            pg.evaluate("scrollTo(0, 0)")
            trail.get_by_role("link", name=re.compile(re.escape(idea["symbol"]))).click()
            pg.evaluate(SETTLED)
            header_bottom = pg.get_by_role("banner").bounding_box()
            header_bottom = header_bottom["y"] + header_bottom["height"]
            title = pg.locator(f"#hl-{n}")
            expect(title).to_contain_text(idea["name"])
            box = title.bounding_box()
            if box["y"] < header_bottom - 0.5:
                problems.append(f"{idea['symbol']}: title top {box['y']:.0f} is under the header (bottom {header_bottom:.0f})")
            if box["y"] + box["height"] > 844:
                problems.append(f"{idea['symbol']}: title is below the screen at {box['y']:.0f}")
        assert problems == [], problems
        assert pg.errors == []
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H14 the below-the-bar note on screen

def test_CHL_UX_H14_below_the_bar_card_names_the_score_and_the_bar(browser, local_app, restore_risk):
    from charlie import engine
    ctx, pg = _at_risk(browser, local_app, 1, 390)
    try:
        panel, data = _run(pg, AI_POWER)
        bar = engine.MIN_SCORE_BY_LEVEL[1]
        below = [(n, i) for n, i in enumerate(data["ideas"]) if i["score"] < bar]
        assert any(i["symbol"] == "NVDA" for _, i in below), f"fixture assumption: {data['ideas']}"
        cards = panel.get_by_role("article")
        problems = []
        for n, idea in below:
            text = cards.nth(n).inner_text()
            assert idea["trade"] is None
            if not re.search(rf"\bscores(?:\s+it)?\s+{idea['score']}(?!\d|\s*/\s*100)", text, re.I):
                problems.append(f"{idea['symbol']}: card doesn't say it scores {idea['score']}")
            if not re.search(rf"\bneeds?\b\D{{0,24}}(?<!\d){bar}(?!\d)", text, re.I):
                problems.append(f"{idea['symbol']}: card doesn't say paper trades need {bar}")
        assert problems == [], problems
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H15 no "Today's bar"

def test_CHL_UX_H15_research_leads_intro_has_no_todays_bar_wording(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        panel, _ = _run(pg, HEARING)
        expect(panel.get_by_role("heading", name="Research leads")).to_be_visible()
        text = pg.locator("#tab-hunch").evaluate("(el) => el.textContent")
        assert not re.search(r"today.s\s+bar", text, re.I), "the Hunches tab says \"Today's bar\""
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H16 offline note leads with the reassurance

STAYS = "Your hunch stays on this computer."


@pytest.mark.parametrize("llm", [False, True], ids=["claude_off", "claude_on"])
def test_CHL_UX_H16_offline_note_leads_with_your_hunch_stays_on_this_computer(browser, local_app, llm):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()

    def status(route):
        res = route.fetch()
        body = res.json()
        body["llm"] = llm
        route.fulfill(response=res, json=body)
    pg.route("**/api/status", status)
    try:
        pg.goto(local_app)
        expect(pg.locator("#ideas .card").first).to_be_visible(timeout=60_000)
        if pg.locator("#ack-btn").is_visible():
            pg.click("#ack-btn")
        expect(pg.locator("#chat-mode")).to_have_text(re.compile(r"^Claude is connected" if llm else r"^Offline"))
        panel = _hunch_panel(pg)
        note = pg.locator("#hunch-llm")
        if llm:
            # The other direction: when the text does go to Claude, the page never says it stays here.
            expect(panel.get_by_text(STAYS)).to_have_count(0)
        else:
            expect(note).to_be_visible()
            expect(note).to_have_text(re.compile(r"^\s*" + re.escape(STAYS)))
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H17 "A, B and C", never "A and B and C"

def test_CHL_UX_H17_callout_lists_names_with_a_single_and(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        panel, data = _run(pg, HEARING)
        heading = panel.get_by_role("heading", name="Most exposed that Charlie can score", exact=True)
        text = _block_of(heading).inner_text()
        m = re.search(r"purest plays here \(([^)]*)\)", text)
        assert m, f"fixture assumption: no list of purest plays in {text!r}"
        names = m.group(1)
        assert len(re.findall(r"\band\b", names)) <= 1, f"names joined with more than one 'and': {names!r}"
        assert not re.search(r"\band\s+\w+\s+and\b", names), names
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-UX-H19 "(not scored)" said once in the trail

def test_CHL_UX_H19_not_scored_appears_at_most_once_in_the_trail(browser, local_app):
    ctx, pg = _open(browser, local_app, 390, 844)
    try:
        _run(pg, HEARING)
        trail = pg.locator("#hunch-result > *").first
        expect(trail.get_by_role("heading", name="The trail")).to_be_visible()
        text = trail.evaluate("(el) => el.textContent")
        n = len(re.findall(r"\(not scored\)", text, re.I))
        assert n <= 1, f"'(not scored)' appears {n} times in the trail"
        # Still honest: the purest plays row says Charlie can't score them.
        row = trail.locator(".trail-row", has_text="Purest plays").inner_text()
        assert re.search(r"not scored|none scored", row, re.I), row
    finally:
        ctx.close()


# ---------------------------------------------------------------- QA-R1 page-height budget at every risk level

@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("hunch_text", [HEARING, AI_POWER], ids=["hearing", "ai_power"])
def test_QA_R1_hunch_result_stays_under_the_height_budget_at_every_risk_level(
        browser, local_app, restore_risk, hunch_text, level):
    ctx, pg = _at_risk(browser, local_app, level, 390)
    try:
        panel, data = _run(pg, hunch_text)
        height = pg.locator("#hunch-result").bounding_box()["height"]
        trades = sum(1 for i in data["ideas"] if i["trade"])
        assert height < 4500, f"result is {height:.0f}px tall at 390, risk {level}, {trades} trade blocks, folds closed"
        # Fitting the budget may fold a lead's trade block (chart, actions, explainers) behind its card's
        # details, never the hard-rule parts: max loss, breakeven, the exit plan and the disclaimer show.
        cards = panel.get_by_role("article")
        for n, idea in enumerate(data["ideas"]):
            card = cards.nth(n)
            expect(card.get_by_text(NFA, exact=True)).to_be_visible()
            if idea["trade"]:
                for words in (r"max loss", r"breakeven", r"exit plan"):
                    expect(card.get_by_text(re.compile(words, re.I)).first).to_be_visible()
        assert pg.errors == []
    finally:
        ctx.close()
