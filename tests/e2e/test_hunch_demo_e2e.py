"""M3.2 Hunches in the public demo, in a real browser (CHL-HUNCH-DEMO-3, 4, 5 to 10). Runs only with CHARLIE_E2E=1.

Failing-first tests, written by qa-tdd before any product code (PLAN.md, M3.2). The unit half (DEMO-1, 2, 4, 6)
is tests/test_hunch_demo.py, which also pins the interface (prebuilt key, static route). The built static demo
comes from conftest (site_dir, site_url, make_page); the throttled-phone helpers are reused from
test_demo_verified_e2e.py and the Search switch helpers from test_hunch_e2e.py.

Spec change, not a weakening (Chase's call, Nov 23): before M3.2 the demo had no Hunches view; the old
"static demo hides Hunches" e2e twin is re-pinned in test_hunch_e2e.py (test_CHL_HUNCH_15_DEMO_3_*).
UI is found by role and label: the "Hunches" region, the "Search by" group, a text box named for the hunch,
the "Run hunch" button, an example button named for AI power, and one article per research lead.
"""
import json
import os
import re
from pathlib import Path

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

from test_demo_verified_e2e import CARD_TIME, PHONE_NET, _serve_under_charlie  # noqa: E402
from test_hunch_e2e import (AXE_TAGS, FORBIDDEN, TABS, _expect_on, _hunches_view,  # noqa: E402
                            _switch_buttons, _tab_names, _tab_to)

ROOT = Path(__file__).resolve().parents[2]
NFA = "Not financial advice. Paper trading only."
ENGINE = 120_000
SIZES = [(390, 844), (1280, 800)]
SIZE_IDS = ["390x844", "1280x800"]
HEARING_FREE = ("Everyone wears earbuds all day now and OTC hearing aids are legal, "
                "so hearing health is about to become a huge consumer market.")
GIBBERISH = "Zorbly quandix flemwort will plonk the wibbertons."
# A free-text hunch that still matches the hearing playbook, with a marker no Charlie copy contains.
PRIVATE_HUNCH = ("My private hunch 7Q4X: everyone wears earbuds all day now and OTC hearing aids are legal, "
                 "so hearing health is about to become a huge consumer market.")
MARKER = "7Q4X"


def _examples() -> dict:
    js = (ROOT / "web" / "app.js").read_text()
    m = re.search(r"const HUNCH_EXAMPLES = \{(.*?)\};", js, re.S)
    assert m, "web/app.js has no HUNCH_EXAMPLES"
    return dict(re.findall(r'(\w+):\s*"([^"]+)"', m.group(1)))


HEARING = _examples()["hearing"]


def _marketing_strings() -> list[str]:
    """Every backticked string in docs/product/MARKETING.md: on-screen copy must come from there (DEMO-7)."""
    return re.findall(r"`([^`]+)`", (ROOT / "docs" / "product" / "MARKETING.md").read_text())


@pytest.fixture(scope="module")
def axe_source():
    path = os.environ.get("CHARLIE_AXE_JS")
    if not path:
        pytest.fail("set CHARLIE_AXE_JS to axe-core's axe.min.js (CI installs axe-core with npm)")
    return Path(path).read_text()


@pytest.fixture(scope="module")
def pre(site_dir):
    return json.loads((site_dir / "prebuilt.json").read_text())


def _demo(make_page, site_url, width=390, height=844, scheme=None, risk=None, hold=False, hash="", storage=None,
          check=True):
    """A fresh demo page. hold=True keeps the engine (pyodide.js) waiting until release(pg) is called.
    risk sets the sample person's level; storage pre-seeds other localStorage keys. Console lines are kept."""
    pg = make_page(width, height, scheme, check=check)
    pg.held, pg.console_lines = [], []
    pg.on("console", lambda m: pg.console_lines.append(m.text))
    if hold:
        pg.route("**/pyodide.js", lambda route: pg.held.append(route))
    seed = dict(storage or {})
    if risk:
        seed["charlie:kv:sample_risk"] = str(risk)
    if seed:
        pg.add_init_script(f"(() => {{ const s = {json.dumps(seed)}; "
                           "for (const k in s) if (localStorage.getItem(k) === null) localStorage.setItem(k, s[k]); })()")
    pg.goto(site_url + hash)
    pg.click("#ack-btn")
    return pg


def _release(pg):
    for _ in range(100):
        if pg.held:
            break
        pg.wait_for_timeout(100)
    assert pg.held, "the page never asked for the engine"
    for route in pg.held:
        route.continue_()
    pg.held.clear()


def _to_hunches(pg):
    view = _hunches_view(pg)
    if not view.is_visible():
        pg.get_by_role("tab", name="Search", exact=True).click()
        _switch_buttons(pg)[1].click()
    expect(view).to_be_visible()
    return view


def _box(view):
    return view.get_by_role("textbox", name=re.compile("hunch", re.I))


def _run_btn(view):
    return view.get_by_role("button", name="Run hunch", exact=True)


def _ai_power_btn(view):
    return view.get_by_role("button", name=re.compile(r"AI power", re.I)).first


def _engine_ready(view):
    expect(_run_btn(view)).to_be_enabled(timeout=ENGINE)


def _map_shows(view, timeout=5_000):
    expect(view.get_by_role("article").first).to_be_visible(timeout=timeout)
    expect(view.get_by_role("heading", name="Who it touches")).to_be_visible(timeout=timeout)


def _run(pg, view, text):
    _engine_ready(view)
    _box(view).fill(text)
    _run_btn(view).click()


def _storage_values(pg):
    return pg.evaluate("""() => [localStorage, sessionStorage].flatMap((s) =>
        Object.keys(s).map((k) => k + '=' + s.getItem(k)))""")


# ============================================================ CHL-HUNCH-DEMO-3 the switch in the demo (+ SW-1 to SW-4)
# The basic reach and #hunch deep link are the re-pinned CHL-HUNCH-15 twins in test_hunch_e2e.py; these add
# the sizes and SW-1 to SW-4 on the demo build.

@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_DEMO_3_search_shows_the_switch_and_five_tabs(make_page, site_url, width, height):
    pg = _demo(make_page, site_url, width, height)
    assert _tab_names(pg) == TABS
    expect(pg.get_by_role("tab", name="Hunches")).to_have_count(0)
    pg.get_by_role("tab", name="Search", exact=True).click()
    _expect_on(pg, "screener")
    hunches = _switch_buttons(pg)[1]
    expect(hunches).to_be_in_viewport()
    box = hunches.bounding_box()
    assert box["height"] >= 44 and box["width"] >= 44, f"Hunches button is {box['width']:.0f}x{box['height']:.0f}"
    hunches.click()
    _expect_on(pg, "hunch")
    assert _tab_names(pg) == TABS


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_DEMO_3_hunch_address_deep_links_and_survives_reload(make_page, site_url, width, height):
    pg = _demo(make_page, site_url, width, height, hash="#hunch")
    expect(_hunches_view(pg)).to_be_visible(timeout=ENGINE)
    _expect_on(pg, "hunch")
    pg.reload()
    expect(_hunches_view(pg)).to_be_visible(timeout=ENGINE)
    _expect_on(pg, "hunch")


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_DEMO_3_SW_1_switch_works_from_the_keyboard(make_page, site_url, width, height):
    pg = _demo(make_page, site_url, width, height)
    pg.get_by_role("tab", name="Search", exact=True).focus()
    pg.keyboard.press("Enter")
    _expect_on(pg, "screener")
    assert _tab_to(pg, _switch_buttons(pg)[1]), "Tab never reaches the Hunches button"
    pg.keyboard.press("Enter")
    _expect_on(pg, "hunch")
    where = pg.evaluate("""() => { const a = document.activeElement;
        return a && a.closest('.search-switch') && a.offsetParent ? a.textContent.trim() : (a ? a.tagName : 'none'); }""")
    assert where == "Hunches", f"after switching to Hunches, focus is on {where!r}"
    assert _tab_to(pg, _switch_buttons(pg)[0]), "Tab never reaches the Screener button from Hunches"
    pg.keyboard.press("Space")
    _expect_on(pg, "screener")


def test_CHL_HUNCH_DEMO_3_SW_2_aria_current_moves_with_the_view(make_page, site_url):
    pg = _demo(make_page, site_url)
    pg.get_by_role("tab", name="Search", exact=True).click()
    for view in ("hunch", "screener", "hunch"):
        screener, hunches = _switch_buttons(pg)
        (hunches if view == "hunch" else screener).click()
        _expect_on(pg, view)
        current = pg.locator(".search-switch [aria-current=page]:visible")
        expect(current).to_have_count(1)
        expect(current).to_have_text("Hunches" if view == "hunch" else "Screener")
    pg.get_by_role("tab", name="Today", exact=True).click()
    expect(pg.get_by_role("group", name="Search by")).to_have_count(0)
    pg.get_by_role("tab", name="Search", exact=True).click()
    _expect_on(pg, "screener")


SPY = """() => { const s = window.charlieStatic, orig = s.request.bind(s); window.__calls = [];
  s.request = (method, path, body) => { window.__calls.push([method, path, body && body.risk]); return orig(method, path, body); }; }"""


@pytest.mark.parametrize("view", ["hunch", "screener"])
def test_CHL_HUNCH_DEMO_3_SW_3_risk_slider_reruns_only_the_view_showing(make_page, site_url, view):
    # Both directions: on Hunches the slider re-runs the hunch, not the screener; on Screener, the reverse.
    pg = _demo(make_page, site_url)
    hv = _to_hunches(pg)
    _map_shows(hv)
    _engine_ready(hv)
    if view == "screener":
        _switch_buttons(pg)[0].click()
        _expect_on(pg, "screener")
    pg.evaluate(SPY)
    want, other = ("/api/hunch", "/api/screen") if view == "hunch" else ("/api/screen", "/api/hunch")
    slider = pg.get_by_role("slider", name="Risk level")
    expect(slider).to_be_visible()
    slider.fill("3")
    pg.wait_for_function("(p) => window.__calls.some((c) => c[0] === 'POST' && c[1] === p)", arg=want,
                         timeout=ENGINE)
    pg.wait_for_timeout(500)
    calls = pg.evaluate("window.__calls")
    assert [c for c in calls if c[1] == other] == [], f"the slider on {view} also sent {calls}"
    assert [c[2] for c in calls if c[1] == want] == [3], calls
    _expect_on(pg, view)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_DEMO_3_SW_4_search_screener_and_hunches_pass_axe(make_page, site_url, axe_source, scheme,
                                                                    width, height):
    pg = _demo(make_page, site_url, width, height, scheme)
    axe_url = site_url.rsplit("/", 1)[0] + "/__axe.min.js"
    pg.route(axe_url, lambda route: route.fulfill(body=axe_source, content_type="text/javascript"))
    problems = []
    for view in ("screener", "hunch"):
        if view == "screener":
            pg.get_by_role("tab", name="Search", exact=True).click()
        else:
            _switch_buttons(pg)[1].click()
            _map_shows(_hunches_view(pg))
        _expect_on(pg, view)
        if pg.evaluate("document.documentElement.scrollWidth > innerWidth"):
            problems.append(f"{view}: horizontal overflow")
        pg.add_script_tag(url=axe_url)
        found = pg.evaluate(
            "(tags) => axe.run(document, {runOnly: tags}).then((r) => r.violations.map((v) => "
            "v.id + ' ' + v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(', ')))", AXE_TAGS)
        problems += [f"{view}: {v}" for v in found]
    assert problems == []


# ============================================================ CHL-HUNCH-DEMO-4 visitor changes stop the prebuilt map

PREBUILT_MARK = "Prebuilt copy marker 51Z"


@pytest.mark.parametrize("changed", [False, True], ids=["sample_untouched", "resume_saved"])
def test_CHL_HUNCH_DEMO_4_saved_profile_turns_off_the_prebuilt_map(make_page, site_url, changed):
    # Both directions, via a marked copy of prebuilt.json: untouched, the map comes from prebuilt (the marker
    # shows); once the visitor has saved a resume (charlie:kv:intake), it comes from the engine (no marker).
    pg = make_page(390, 844)

    def marked(route):
        resp = route.fetch()
        pre = resp.json()
        for entries in pre.get("levels", {}).values():
            for body in (entries.get("hunch") or {}).values():
                for idea in body.get("ideas", []):
                    idea["why"] = PREBUILT_MARK
        route.fulfill(response=resp, body=json.dumps(pre), content_type="application/json")
    pg.route("**/prebuilt.json", marked)
    if changed:
        pg.add_init_script("localStorage.setItem('charlie:kv:intake', JSON.stringify({interests: 'gardening'}))")
    pg.goto(site_url)
    pg.click("#ack-btn")
    view = _to_hunches(pg)
    _map_shows(view, timeout=ENGINE)
    _engine_ready(view)
    marks = view.get_by_text(PREBUILT_MARK)
    if changed:
        expect(marks).to_have_count(0)
    else:
        expect(marks.first).to_be_visible()


# ============================================================ CHL-HUNCH-DEMO-5 prebuilt first, then the engine

def test_CHL_HUNCH_DEMO_5_prebuilt_map_paints_and_controls_wait_for_the_engine(make_page, site_url):
    pg = _demo(make_page, site_url, hold=True)
    view = _to_hunches(pg)
    expect(_box(view)).to_have_value(HEARING)
    _map_shows(view)  # from prebuilt: the engine is still held back
    for control in (_run_btn(view), _ai_power_btn(view), _box(view)):
        expect(control).to_be_disabled()
    expect(view.get_by_text("Loading the engine…")).to_be_visible()
    _release(pg)
    _engine_ready(view)
    expect(_ai_power_btn(view)).to_be_enabled()
    expect(_box(view)).to_be_enabled()
    expect(view.get_by_text("Loading the engine…")).to_have_count(0)


# ============================================================ CHL-HUNCH-DEMO-6 examples, free text, no match

def test_CHL_HUNCH_DEMO_6_ai_power_example_maps_from_the_engine(make_page, site_url):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _engine_ready(view)
    _ai_power_btn(view).click()
    expect(view.get_by_text(re.compile(r"Arista|NVIDIA|Vistra", re.I)).first).to_be_visible(timeout=ENGINE)
    _map_shows(view, timeout=ENGINE)


def test_CHL_HUNCH_DEMO_6_free_text_matching_a_playbook_maps(make_page, site_url):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _run(pg, view, HEARING_FREE)
    _map_shows(view, timeout=ENGINE)
    expect(view.get_by_text(re.compile(r"Qualcomm", re.I)).first).to_be_visible()


def test_CHL_HUNCH_DEMO_6_unmatched_text_offers_the_two_examples(make_page, site_url):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _run(pg, view, GIBBERISH)
    expect(view.get_by_role("heading", name="No map for this hunch yet")).to_be_visible(timeout=ENGINE)
    expect(view.get_by_role("button", name="Try the hearing hunch")).to_be_visible()
    expect(view.get_by_role("button", name="Try the AI power hunch")).to_be_visible()
    expect(view.get_by_role("article")).to_have_count(0)


def test_CHL_HUNCH_DEMO_6_empty_hunch_says_type_a_hunch_first(make_page, site_url):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _run(pg, view, "   ")
    expect(pg.get_by_text("Type a hunch first.")).to_be_visible()


# ============================================================ CHL-HUNCH-DEMO-7 sample label and the form note

@pytest.mark.parametrize("engine", ["prebuilt", "engine_ready"])
def test_CHL_HUNCH_DEMO_7_sample_label_and_browser_only_note(make_page, site_url, engine):
    pg = _demo(make_page, site_url, hold=engine == "prebuilt")
    view = _to_hunches(pg)
    if engine == "engine_ready":
        _engine_ready(view)
    expect(view.get_by_text(re.compile(r"\bSample data\b")).first).to_be_visible()
    note = view.get_by_text(re.compile(r"stays in this browser"))
    expect(note).to_have_count(1)
    expect(note).to_be_visible()
    text = note.inner_text().strip()
    # Re-pinned for CHL-UX-H34 (ux-reviewer round 6, Nov 23): the "built-in maps" fact now lives once, in the
    # sample line above the form; the note says only where the hunch stays. Spec change, not a weakening:
    # test_CHL_UX_H34_* pins the new note and that the fact appears exactly once.
    assert text == "Your hunch stays in this browser.", text
    assert not re.search(r"computer|Claude|Anthropic", text, re.I), text
    assert text in _marketing_strings(), f"the note {text!r} isn't a MARKETING.md string"
    whole = view.inner_text()
    assert not re.search(r"Claude|Anthropic|this computer", whole), "the demo's Hunches view mentions Claude or 'computer'"


# ============================================================ CHL-HUNCH-DEMO-8 paper trades and the hunch text

def test_CHL_HUNCH_DEMO_8_lead_paper_trade_survives_reload_and_reset_clears_it(make_page, site_url, pre):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _map_shows(view)
    ideas = pre["levels"][str(pre["default_risk"])]["hunch"][HEARING]["ideas"]
    n = next(i for i, idea in enumerate(ideas) if idea["trade"])
    sym = ideas[n]["symbol"]
    card = view.get_by_role("article").nth(n)
    card.get_by_text("Chart, plan and order details").click()
    card.get_by_role("button", name="Paper trade this").click()
    pg.wait_for_function("(s) => (localStorage.getItem('charlie:positions') || '').includes(s)", arg=sym,
                         timeout=ENGINE)
    trades = pg.locator("#tab-paper")
    pg.get_by_role("tab", name="Trades", exact=True).click()
    expect(trades).to_contain_text(sym, timeout=ENGINE)
    assert not [v for v in _storage_values(pg) if HEARING in v], "the hunch text was written to storage"
    pg.reload()
    pg.get_by_role("tab", name="Trades", exact=True).click()
    expect(trades).to_contain_text(sym, timeout=ENGINE)
    bar = pg.get_by_role("region", name="Demo")
    bar.get_by_role("button", name="Demo details").click()
    bar.get_by_role("button", name="Reset demo").click()
    with pg.expect_navigation():
        bar.get_by_role("button", name="Reset", exact=True).click()
    # Reset reloads and keeps the URL hash (test_CHL_DS_18_reset_demo_keeps_the_appearance_choice), so the
    # app reopens on Trades. Booted there = the Trades tab is the active, visible panel after the reload.
    assert pg.evaluate("location.hash") == "#paper"
    expect(pg.locator("#tab-paper.active")).to_be_visible(timeout=ENGINE)
    # Positive proof the reset emptied it: the rendered empty state, not just the symbol's absence.
    expect(trades.get_by_role("heading", name="No paper trades yet")).to_be_visible(timeout=ENGINE)
    expect(trades).not_to_contain_text(sym)
    assert pg.evaluate("localStorage.getItem('charlie:positions')") is None
    assert not [v for v in _storage_values(pg) if sym in v], "the lead's paper trade is still in storage"


def test_CHL_HUNCH_DEMO_8_hunch_text_never_reaches_storage_url_or_console(make_page, site_url):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _run(pg, view, PRIVATE_HUNCH)
    _map_shows(view, timeout=ENGINE)
    # And once more through a paper trade, which writes to localStorage.
    card = view.get_by_role("article").first
    card.get_by_text("Chart, plan and order details").click()
    card.get_by_role("button", name="Paper trade this").click()
    pg.wait_for_function("() => localStorage.getItem('charlie:positions') !== null", timeout=ENGINE)
    leaks = [v[:80] for v in _storage_values(pg) if MARKER in v or HEARING in v]
    assert leaks == [], f"hunch text in storage: {leaks}"
    assert MARKER not in pg.url and "earbuds" not in pg.url.lower(), pg.url
    assert not [c for c in pg.console_lines if MARKER in c or "earbuds" in c.lower()], pg.console_lines


# ============================================================ CHL-HUNCH-DEMO-9 NFA, words, axe, fit, height

@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_CHL_HUNCH_DEMO_9_every_lead_and_trade_shows_the_disclaimer(make_page, site_url, pre, level):
    pg = _demo(make_page, site_url, risk=level)
    view = _to_hunches(pg)
    _map_shows(view)
    ideas = pre["levels"][str(level)]["hunch"][HEARING]["ideas"]
    cards = view.get_by_role("article")
    expect(cards).to_have_count(len(ideas))
    for n, idea in enumerate(ideas):
        card = cards.nth(n)
        expect(card).to_contain_text("research lead", ignore_case=True)
        expect(card.get_by_text(NFA, exact=True)).to_have_count(1)
        expect(card.get_by_text(NFA, exact=True)).to_be_visible()
        if idea["trade"]:
            for words in (r"max loss", r"breakeven", r"exit plan"):
                expect(card.get_by_text(re.compile(words, re.I)).first).to_be_visible()


def test_CHL_HUNCH_DEMO_9_no_banned_words_and_the_register(make_page, site_url):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _map_shows(view)
    # Outside the research-lead cards, whose trade blocks reuse strategy copy like "Buy shares" (CHL-HUNCH-16).
    outside = pg.evaluate("""() => { const p = document.querySelector('#tab-hunch').cloneNode(true);
        p.querySelectorAll('article').forEach((a) => a.remove()); return p.innerText; }""")
    assert FORBIDDEN.findall(outside) == [], outside
    text = view.inner_text().lower()
    assert "most exposed" in text and "research lead" in text


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_DEMO_9_hunches_fits_and_passes_axe(make_page, site_url, axe_source, scheme, width, height):
    pg = _demo(make_page, site_url, width, height, scheme)
    axe_url = site_url.rsplit("/", 1)[0] + "/__axe.min.js"
    pg.route(axe_url, lambda route: route.fulfill(body=axe_source, content_type="text/javascript"))
    view = _to_hunches(pg)
    _map_shows(view)
    _engine_ready(view)
    problems = []
    if pg.evaluate("document.documentElement.scrollWidth > innerWidth"):
        problems.append("horizontal overflow")
    wide = pg.evaluate("""[...document.querySelectorAll('#tab-hunch *')].filter((el) => {
        const r = el.getBoundingClientRect(); return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1);
    }).map((el) => el.tagName + '.' + el.className).slice(0, 5)""")
    if wide:
        problems.append(f"off-screen {wide}")
    pg.add_script_tag(url=axe_url)
    problems += pg.evaluate(
        "(tags) => axe.run(document, {runOnly: tags}).then((r) => r.violations.map((v) => "
        "v.id + ' ' + v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(', ')))", AXE_TAGS)
    assert problems == []


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_CHL_HUNCH_DEMO_9_hearing_result_fits_the_phone_height_budget_with_the_demo_bar(make_page, site_url, level):
    pg = _demo(make_page, site_url, 390, 844, risk=level)
    view = _to_hunches(pg)
    _map_shows(view)
    bar = pg.get_by_role("region", name="Demo")
    expect(bar).to_be_visible()
    result = pg.locator("#hunch-result").bounding_box()["height"]
    total = result + bar.bounding_box()["height"]
    assert total < 4500, f"hearing result {result:.0f}px + demo bar = {total:.0f}px at 390, risk {level}"


# ============================================================ CHL-HUNCH-DEMO-10 throttled phone first paint

LEAD_TIME = """
window.__lead = null;
new MutationObserver(() => {
  if (window.__lead === null && document.querySelector('#tab-hunch article')) window.__lead = performance.now();
}).observe(document, {subtree: true, childList: true});
"""


def _throttled(browser, origin, path, script, flag):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                              device_scale_factor=3)
    pg = ctx.new_page()
    try:
        cdp = ctx.new_cdp_session(pg)
        cdp.send("Network.enable")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        cdp.send("Network.emulateNetworkConditions", PHONE_NET)
        pg.add_init_script(script)
        pg.goto(origin + path)
        pg.wait_for_function(f"() => window.{flag} !== null", timeout=30_000)
        return pg.evaluate(f"() => window.{flag}")
    finally:
        ctx.close()


def test_CHL_HUNCH_DEMO_10_today_still_paints_under_2s_with_the_hunch_prebuilt(browser, site_dir, tmp_path, pre):
    # DEMO-PHONE-2S unchanged, on a build whose prebuilt.json now carries the hearing hunch.
    assert all("hunch" in e for e in pre["levels"].values()), "this build has no prebuilt hunch to weigh"
    server, origin = _serve_under_charlie(site_dir, tmp_path, gzip_text=True)
    try:
        ms = _throttled(browser, origin, "/charlie/", CARD_TIME, "__card")
    finally:
        server.shutdown()
    assert ms < 2000, f"Today's first idea card painted at {ms:.0f} ms on the throttled phone profile"


def test_CHL_HUNCH_DEMO_10_hunches_paints_the_prebuilt_map_under_2s(browser, site_dir, tmp_path):
    server, origin = _serve_under_charlie(site_dir, tmp_path, gzip_text=True)
    try:
        ms = _throttled(browser, origin, "/charlie/#hunch", LEAD_TIME, "__lead")
    finally:
        server.shutdown()
    assert ms < 2000, f"Search > Hunches' first research lead painted at {ms:.0f} ms on the throttled phone profile"


# ============================================================ Round 5 showcase review fixes (CHL-HUNCH-H27 to H33)
# Failing-first, written by qa-tdd on Nov 23 from ux-reviewer round 5 (public demo). Each test names its finding.

SEG_LOOK = """() => {
  const sw = [...document.querySelectorAll('.search-switch')].find((s) => s.offsetParent);
  const probe = document.createElement('span'); probe.style.color = 'var(--accent)'; document.body.appendChild(probe);
  const accent = getComputedStyle(probe).color; probe.remove();
  const look = (el) => { const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return {text: el.textContent.trim(), current: el.getAttribute('aria-current'), deco: s.textDecorationLine,
            color: s.color, bg: s.backgroundColor, weight: parseFloat(s.fontWeight), h: r.height, top: r.top,
            parent: el.parentElement === sw}; };
  const t = getComputedStyle(sw);
  return {accent, track: {bg: t.backgroundColor, border: parseFloat(t.borderTopWidth), borderStyle: t.borderTopStyle},
          segs: [...sw.querySelectorAll('.seg')].map(look)};
}"""


def _seg_problems(got, where):
    bad = []
    segs = got["segs"]
    if len(segs) != 2 or not all(s["parent"] for s in segs):
        return [f"{where}: want 2 .seg segments directly inside one .search-switch track, got {segs}"]
    cur = [s for s in segs if s["current"] == "page"]
    other = [s for s in segs if s["current"] != "page"]
    if len(cur) != 1 or len(other) != 1:
        return [f"{where}: want one current segment, got {segs}"]
    cur, other = cur[0], other[0]
    track = got["track"]
    if track["bg"] == "rgba(0, 0, 0, 0)" and not (track["border"] > 0 and track["borderStyle"] != "none"):
        bad.append(f"{where}: the track is neither filled nor bordered, so the two segments don't read as one control")
    if abs(cur["h"] - other["h"]) > 0.5 or abs(cur["top"] - other["top"]) > 0.5:
        bad.append(f"{where}: segments differ in height/top: {cur['h']:.1f}@{cur['top']:.1f} vs {other['h']:.1f}@{other['top']:.1f}")
    if min(cur["h"], other["h"]) < 44:
        bad.append(f"{where}: a segment is under 44px tall")
    if "underline" in other["deco"]:
        bad.append(f"{where}: the other segment '{other['text']}' is underlined like a link ({other['deco']})")
    if other["color"] == got["accent"]:
        bad.append(f"{where}: the other segment '{other['text']}' is in the accent link color {other['color']}")
    if cur["bg"] in ("rgba(0, 0, 0, 0)", track["bg"]):
        bad.append(f"{where}: the current segment isn't filled apart from the track (bg {cur['bg']}, track {track['bg']})")
    if cur["weight"] <= other["weight"]:
        bad.append(f"{where}: the current segment ({cur['weight']}) isn't heavier than the other ({other['weight']})")
    return bad


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_H27_search_switch_reads_as_a_segmented_control_not_a_link(make_page, site_url, scheme, width, height):
    pg = _demo(make_page, site_url, width, height, scheme)
    pg.get_by_role("tab", name="Search", exact=True).click()
    bad = []
    for view in ("screener", "hunch"):
        if view == "hunch":
            _switch_buttons(pg)[1].click()
        _expect_on(pg, view)
        pg.mouse.move(0, 0)
        bad += _seg_problems(pg.evaluate(SEG_LOOK), f"{scheme} {width}px #{view} at rest")
        # Hover the other segment: it still must not turn into an underlined link.
        other = _switch_buttons(pg)[0 if view == "hunch" else 1]
        other.hover()
        bad += [p for p in _seg_problems(pg.evaluate(SEG_LOOK), f"{scheme} {width}px #{view} other hovered")
                if "other segment" in p]
    assert bad == [], "\n".join(bad)


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_H28_switch_sits_above_the_risk_panel(make_page, site_url, width, height):
    pg = _demo(make_page, site_url, width, height)
    pg.get_by_role("tab", name="Search", exact=True).click()
    bad = []
    for view in ("screener", "hunch"):
        if view == "hunch":
            _switch_buttons(pg)[1].click()
        _expect_on(pg, view)
        got = pg.evaluate("""() => { const sw = [...document.querySelectorAll('.search-switch')].find((s) => s.offsetParent),
            risk = document.querySelector('#risk-row');
            return {riskShown: !!risk.offsetParent, before: !!(sw.compareDocumentPosition(risk) & Node.DOCUMENT_POSITION_FOLLOWING),
                    sw: sw.getBoundingClientRect().top, risk: risk.getBoundingClientRect().top}; }""")
        assert got["riskShown"], f"#{view}: the risk panel isn't showing (this test needs it)"
        if not got["before"]:
            bad.append(f"#{view} {width}px: the risk panel comes before the switch in the DOM")
        if not got["sw"] < got["risk"]:
            bad.append(f"#{view} {width}px: switch top {got['sw']:.0f} is not above risk panel top {got['risk']:.0f}")
    assert bad == [], "\n".join(bad)


@pytest.mark.parametrize("width,height", [(360, 740), (390, 844)], ids=["360x740", "390x844"])
def test_CHL_HUNCH_H29_loading_line_is_in_the_first_phone_screen(make_page, site_url, width, height):
    pg = _demo(make_page, site_url, width, height, hold=True)
    view = _to_hunches(pg)
    pg.evaluate("scrollTo(0, 0)")
    line = view.get_by_text("Loading the engine…")
    expect(line).to_be_visible()
    box = line.bounding_box()
    # The visible bottom: the top of a bottom-docked tab bar or demo bar, else the viewport.
    bottom = pg.evaluate("""() => { let b = innerHeight;
        for (const el of document.querySelectorAll('nav.tabs, .demo-bar, [role=region][aria-label=Demo]')) {
          const s = getComputedStyle(el), r = el.getBoundingClientRect();
          if ((s.position === 'fixed' || s.position === 'sticky') && r.top > innerHeight / 2) b = Math.min(b, r.top); }
        return b; }""")
    _release(pg)
    assert box["y"] + box["height"] <= bottom, \
        f"{width}x{height}: 'Loading the engine…' ends at y={box['y'] + box['height']:.0f}, below the first screen's bottom {bottom:.0f}"


def test_CHL_HUNCH_H30_paper_trade_toast_names_the_trades_tab(make_page, site_url):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _engine_ready(view)
    card = view.get_by_role("article").first
    card.locator("summary").first.click()
    card.get_by_role("button", name="Paper trade this").click()
    toast = pg.locator("#toast")
    expect(toast).to_contain_text("Paper trade opened", timeout=ENGINE)
    text = toast.inner_text()
    assert "See it in Trades." in text, text
    assert "Paper portfolio" not in text, text


@pytest.mark.parametrize("level,kind", [(2, "shares"), (3, "option")])
def test_CHL_HUNCH_H31_at_expiry_only_on_option_leads(make_page, site_url, pre, level, kind):
    pg = _demo(make_page, site_url, risk=level)
    view = _to_hunches(pg)
    _map_shows(view)
    ideas = pre["levels"][str(level)]["hunch"][HEARING]["ideas"]
    n = next(i for i, idea in enumerate(ideas)
             if idea["trade"] and (idea["trade"].get("expiry") is None) == (kind == "shares"))
    card = view.get_by_role("article").nth(n)
    expect(card).to_contain_text(ideas[n]["symbol"])
    card.locator("summary").first.click()
    text = card.evaluate("(a) => a.textContent")
    if kind == "shares":
        assert "at expiry" not in text, f"{ideas[n]['symbol']} {ideas[n]['trade']['label']} says 'at expiry'"
    else:
        assert "at expiry" in text, f"option lead {ideas[n]['symbol']} lost its 'at expiry'"


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_HUNCH_H32_sample_line_is_body_weight_and_smaller_than_the_title(make_page, site_url, width, height):
    pg = _demo(make_page, site_url, width, height)
    view = _to_hunches(pg)
    sample = view.get_by_text("Sample data. Built-in maps for two example hunches.")
    expect(sample).to_be_visible()
    got = sample.evaluate("""(el) => { const s = getComputedStyle(el), h1 = getComputedStyle(el.closest('section').querySelector('h1')),
        sub = getComputedStyle(el.closest('section').querySelector('.page-sub'));
        return {w: parseFloat(s.fontWeight), px: parseFloat(s.fontSize), h1: parseFloat(h1.fontSize), sub: parseFloat(sub.fontWeight)}; }""")
    assert got["w"] <= 400, f"the sample line is weight {got['w']} (want 400, not bold)"
    assert got["w"] <= got["sub"], f"the sample line ({got['w']}) is heavier than the subtitle ({got['sub']})"
    assert got["px"] < got["h1"], f"the sample line ({got['px']}px) isn't smaller than the title ({got['h1']}px)"


def test_CHL_HUNCH_H33_unmatched_hunch_shows_one_set_of_examples(make_page, site_url):
    pg = _demo(make_page, site_url)
    view = _to_hunches(pg)
    _run(pg, view, GIBBERISH)
    expect(view.get_by_role("heading", name="No map for this hunch yet")).to_be_visible(timeout=ENGINE)
    expect(view.get_by_role("button", name="Try the hearing hunch")).to_be_visible()
    expect(view.get_by_role("button", name="Try the AI power hunch")).to_be_visible()
    expect(view.get_by_role("button", name="Hearing", exact=True)).to_be_hidden()
    expect(view.get_by_role("button", name="AI power", exact=True)).to_be_hidden()
    shown = view.locator("[data-hunch-example]:visible")
    expect(shown).to_have_count(2)


# ============================================================ ux-reviewer round 6 (CHL-UX-H34 to H36, AC-H34..AC-H36)

@pytest.mark.parametrize("engine", ["prebuilt", "engine_ready"])
def test_CHL_UX_H34_built_in_maps_fact_said_once_on_the_hunches_form(make_page, site_url, engine):
    pg = _demo(make_page, site_url, hold=engine == "prebuilt")
    view = _to_hunches(pg)
    if engine == "engine_ready":
        _engine_ready(view)
    _map_shows(view)
    said = view.inner_text().lower().count("built-in maps for two example hunches")
    assert said == 1, f"'built-in maps for two example hunches' appears {said}x in #tab-hunch (want once, the sample line)"
    note = view.get_by_text(re.compile(r"stays in this browser"))
    expect(note).to_have_count(1)
    assert note.inner_text().strip() == "Your hunch stays in this browser.", note.inner_text()
    if engine == "prebuilt":
        _release(pg)


# The band a result heading must land in: below every sticky/fixed bar at the top that covers it (header, demo
# bar) and at least 48px above every fixed bar at the bottom (disclaimer line, tab bar). Toasts and the engine
# pill are transient and don't count.
RESULT_SPOT = """() => {
    const box = document.querySelector('#hunch-result'), h = box.querySelector('h2');
    if (!h) return {h2: null};
    const r = h.getBoundingClientRect(), a = document.activeElement;
    let top = 0, bottom = innerHeight;
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('.toast, .engine-status, .drawer, .modal, #hunch-result')) continue;
      const s = getComputedStyle(el);
      if (s.position !== 'fixed' && s.position !== 'sticky') continue;
      if (s.display === 'none' || s.visibility === 'hidden') continue;
      const b = el.getBoundingClientRect();
      if (!b.width || !b.height || b.height > innerHeight / 2) continue;      // side nav on laptops
      if (b.right <= r.left || b.left >= r.right) continue;                   // doesn't sit over the heading
      if (b.top < innerHeight / 2) top = Math.max(top, b.bottom); else bottom = Math.min(bottom, b.top);
    }
    return {h2: h.textContent.trim().slice(0, 50), y: r.top, top, bottom, scrollY,
            focusIsH2: a === h, focusIn: box.contains(a), focus: a ? (a.id || a.tagName) + ' ' + (a.textContent || '').trim().slice(0, 30) : null};
}"""


def _settled_spot(pg, wait_ms=4_000):
    """RESULT_SPOT once the (maybe smooth) scroll has stopped: two reads 250ms apart that agree."""
    last, waited = None, 0
    while waited < wait_ms:
        got = pg.evaluate(RESULT_SPOT)
        if last and got.get("y") == last.get("y") and got.get("scrollY") == last.get("scrollY"):
            return got
        last = got
        pg.wait_for_timeout(250)
        waited += 250
    return last


def _spot_problems(got, where):
    if got["h2"] is None:
        return [f"{where}: #hunch-result has no h2"]
    bad = []
    if not got["y"] >= got["top"]:
        bad.append(f"{where}: first result h2 {got['h2']!r} top {got['y']:.0f} is behind the top bars (end at {got['top']:.0f})")
    if not got["y"] <= got["bottom"] - 48:
        bad.append(f"{where}: first result h2 {got['h2']!r} top {got['y']:.0f} is below {got['bottom'] - 48:.0f} "
                   f"(bottom bars start at {got['bottom']:.0f}; scrollY {got['scrollY']:.0f})")
    if not got["focusIsH2"]:
        bad.append(f"{where}: focus is on {got['focus']!r}, not the first result h2 {got['h2']!r}")
    return bad


@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_UX_H35_a_run_you_start_scrolls_the_result_into_view_and_focuses_it(make_page, site_url, width, height):
    pg = _demo(make_page, site_url, width, height)
    view = _to_hunches(pg)
    _engine_ready(view)
    bad = []

    # 1. The AI power example button in the form.
    pg.evaluate("scrollTo(0, 0)")
    pg.locator("#hunch-form").get_by_role("button", name="AI power", exact=True).click()
    expect(view.get_by_text(re.compile(r"Arista|NVIDIA|Vistra", re.I)).first).to_be_attached(timeout=ENGINE)
    _engine_ready(view)
    bad += _spot_problems(_settled_spot(pg), f"{width}px Examples > AI power")

    # 2. Run hunch on free text that matches a playbook.
    pg.evaluate("scrollTo(0, 0)")
    _box(view).fill(HEARING_FREE)
    _run_btn(view).click()
    expect(view.get_by_text(re.compile(r"Qualcomm", re.I)).first).to_be_attached(timeout=ENGINE)
    _engine_ready(view)
    bad += _spot_problems(_settled_spot(pg), f"{width}px Run hunch (hearing free text)")

    # 3. Run hunch on text with no map.
    pg.evaluate("scrollTo(0, 0)")
    _box(view).fill(GIBBERISH)
    _run_btn(view).click()
    expect(view.get_by_role("heading", name="No map for this hunch yet")).to_be_attached(timeout=ENGINE)
    _engine_ready(view)
    bad += _spot_problems(_settled_spot(pg), f"{width}px Run hunch (no map)")

    # 4. "Try the AI power hunch" in the no-map panel.
    view.get_by_role("button", name="Try the AI power hunch").click()
    expect(view.get_by_role("heading", name="Who it touches")).to_be_attached(timeout=ENGINE)
    _engine_ready(view)
    bad += _spot_problems(_settled_spot(pg), f"{width}px Try the AI power hunch")
    assert bad == [], "\n".join(bad)


@pytest.mark.parametrize("hash", ["", "#hunch"], ids=["via_switch", "deep_link"])
@pytest.mark.parametrize("width,height", SIZES, ids=SIZE_IDS)
def test_CHL_UX_H35_first_demo_paint_does_not_scroll_or_take_focus(make_page, site_url, width, height, hash):
    pg = _demo(make_page, site_url, width, height, hash=hash)
    view = _to_hunches(pg)
    _map_shows(view)
    _engine_ready(view)
    pg.wait_for_timeout(1_000)
    got = pg.evaluate(RESULT_SPOT)
    assert got["scrollY"] == 0, f"{width}px {hash or 'switch'}: the first (prebuilt) paint scrolled the page to {got['scrollY']}"
    assert not got["focusIn"], f"{width}px {hash or 'switch'}: the first paint moved focus into the result ({got['focus']!r})"


SWITCH_TOP = """() => { const sw = [...document.querySelectorAll('.search-switch')].find((s) => s.offsetParent);
    return sw.getBoundingClientRect().top + scrollY; }"""


@pytest.mark.parametrize("width,height", [(360, 740), (390, 844), (1280, 800)], ids=["360x740", "390x844", "1280x800"])
def test_CHL_UX_H36_search_switch_stays_put_between_screener_and_hunches(make_page, site_url, width, height):
    pg = _demo(make_page, site_url, width, height)
    pg.get_by_role("tab", name="Search", exact=True).click()
    tops = {}
    for view in ("screener", "hunch"):
        if view == "hunch":
            _switch_buttons(pg)[1].click()
        _expect_on(pg, view)
        pg.evaluate("scrollTo(0, 0)")
        tops[view] = pg.evaluate(SWITCH_TOP)
    assert abs(tops["screener"] - tops["hunch"]) <= 2, \
        f"{width}px: Search switch top is {tops['screener']:.0f} on Screener but {tops['hunch']:.0f} on Hunches (want within 2px)"
