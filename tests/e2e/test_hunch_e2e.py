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


# ============================================================ M3.1 review fixes (red first, qa-tdd, Nov 17)
# ux-reviewer CHL-UX-H1 to H10 and privacy-security CHL-PS-H4 (scratchpad hunch-*-review.md). The unit
# half (CHL-PS-H1 to H6) is in tests/test_hunch.py. Not in scope: UX-H8 (the "Buy shares" trade-block
# exemption stays) and UX-H11 (shared engine sizing).

AI_POWER = "AI data centers need so much electricity that power demand is going to explode."
GIBBERISH = "Zorbly quandix flemwort will plonk the wibbertons."
HINT_ON = "Your hunch text is sent to Anthropic's Claude to draft the map."
HINT_OFF = "Uses Charlie's built-in maps. No text leaves your computer."
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
