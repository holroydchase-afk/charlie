"""CHL-DARK-3 to DARK-9 (and 8b): dark-mode layering as a visitor sees it, on the built static demo in Chromium.

Spec: docs/product/SPEC-DARK-LAYERS.md (intake #55, CHL-M1.16). Written first, red, by qa-tdd on Nov 23 2026,
before any change in web/. Fixtures: conftest.py. Runs only with CHARLIE_E2E=1 (axe needs CHARLIE_AXE_JS).
The unit half (token values, the rule, DS-3 pairs on --raised) is tests/test_dark_layers.py.

Everything here reads computed styles at 390x844 and 1280x800. "Dark" is reached two ways: the OS setting
(color_scheme) and the in-app choice (OS light, Appearance Dark, so <html data-theme=dark>). CHL-DARK-11 to 13
(the first-open notice) wait on Chase's D5 call and are not here.
"""
import os
import re
from pathlib import Path

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

NFA = "Not financial advice. Paper trading only."
PHONE = (390, 844)
DESKTOP = (1280, 800)
SIZES = [PHONE, DESKTOP]
SIZE_IDS = ["390x844", "1280x800"]
ENGINE = 120_000
VIEWS = ["today", "screener", "chat", "paper", "learn", "profile"]
LAYER = 1.15  # the intake's step between a layer and what it sits on
EDGE = 3.0  # WCAG 1.4.11 for a control's boundary
# (OS scheme, in-app Appearance choice): both ways to get dark.
DARK_WAYS = [("dark", None), ("light", "dark")]
DARK_IDS = ["os-dark", "picked-dark"]
# (OS scheme, contrast): every mode a control edge must hold in.
MODES = [("light", None), ("dark", None), ("light", "more"), ("dark", "more")]
MODE_IDS = ["light", "dark", "hc-light", "hc-dark"]
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


# ---------------------------------------------------------------- colors
def _parse(c: str):
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)", c.strip())
    assert m, f"can't read the computed color {c!r} (expected rgb()/rgba())"
    a = m.group(4)
    alpha = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
    return [float(m.group(i)) for i in (1, 2, 3)], alpha


def _over(top: str, under: str) -> str:
    """top composited over an opaque under, as rgb()."""
    (t, a), (u, _) = _parse(top), _parse(under)
    return "rgb({}, {}, {})".format(*[round(t[i] * a + u[i] * (1 - a)) for i in range(3)])


def _lum(c: str) -> float:
    rgb, _ = _parse(c)
    v = [x / 255 for x in rgb]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted([_lum(a), _lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _alpha(c: str) -> float:
    return 0.0 if c.strip() == "transparent" else _parse(c)[1]


# ---------------------------------------------------------------- pages
def _new(browser, size, scheme="light", contrast_pref=None, theme=None):
    kw = {"viewport": {"width": size[0], "height": size[1]}, "color_scheme": scheme}
    if contrast_pref:
        kw["contrast"] = contrast_pref
    ctx = browser.new_context(**kw)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    if theme:
        pg.add_init_script(f"try {{ localStorage.setItem('charlie-appearance', '{theme}'); }} catch (_) {{}}")
    return ctx, pg


def _open(browser, site_url, size, scheme="light", contrast_pref=None, theme=None, ack=True):
    ctx, pg = _new(browser, size, scheme, contrast_pref, theme)
    pg.goto(site_url)
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    if theme:
        expect(pg.locator(f"html[data-theme={theme}]")).to_have_count(1)
    if ack:
        pg.click("#ack-btn")
    return ctx, pg


def _engine_idle(pg):
    pg.wait_for_timeout(200)
    pg.wait_for_function("() => document.querySelector('#engine-status').classList.contains('hidden')", timeout=ENGINE)


def _go(pg, view):
    if view == "profile":
        pg.locator("header").get_by_role("button", name=re.compile(r"\bProfile\b")).click()
        expect(pg.locator("#tab-profile")).to_be_visible()
    else:
        pg.click(f"[role=tab][data-tab={view}]")
    _engine_idle(pg)
    if view == "screener":
        expect(pg.locator("#screen-results [data-row]").first).to_be_attached(timeout=ENGINE)
        if pg.locator("#edit-filters").is_visible():
            pg.click("#edit-filters")  # show the filter controls too
    if view == "chat":
        pg.locator("#chat-log .chip").first.click()
        expect(pg.locator("#chat-log .msg.bot").last).to_contain_text(NFA, timeout=ENGINE)
    pg.evaluate("scrollTo(0, 0)")


def _var(pg, name):
    """A token as the page resolves it, as rgb()/rgba(); '' when it isn't defined."""
    return pg.evaluate("""(n) => { if (!getComputedStyle(document.documentElement).getPropertyValue(n).trim()) return '';
        const i = document.createElement('i'); i.style.color = `var(${n})`; document.body.append(i);
        const c = getComputedStyle(i).color; i.remove(); return c; }""", name)


def _page_bg(pg):
    return pg.evaluate("getComputedStyle(document.body).backgroundColor")


def _open_read_more(pg, size):
    line = pg.locator("#disclaimer-line")
    if size[0] < 760:  # CHL-NAV-3/11: on phones the line itself is the button
        line.get_by_role("button").filter(visible=True).first.click()
    else:
        line.get_by_role("button", name=re.compile("read more", re.I)).click()
    expect(pg.locator("#ack")).to_be_visible()


def _open_drawer(pg):
    pg.click("[role=tab][data-tab=today]")
    pg.locator("#ideas .card [data-ticker]").first.click()
    expect(pg.locator("#drawer svg.payoff").first).to_be_visible(timeout=ENGINE)
    _engine_idle(pg)


# The first non-transparent background outside an element (walking up), as the spec's "directly outside it".
OUTSIDE_FN = r"""(el) => { let p = el.parentElement;
  while (p) { const c = getComputedStyle(p).backgroundColor;
    if (c !== 'transparent' && !/rgba\([^)]*,\s*0\)$/.test(c)) return c; p = p.parentElement; }
  return getComputedStyle(document.body).backgroundColor; }"""

LAYERS_JS = r"""() => { const outside = """ + OUTSIDE_FN + r""";
  const vis = (el) => el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}) && el.getBoundingClientRect().height > 0;
  const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + [...el.classList].slice(0, 3).map((c) => '.' + c).join('');
  return [...document.querySelectorAll('.tab.active .card, .tab.active .panel')]
    .filter((el) => vis(el) && !el.parentElement.closest('.card, .panel'))
    .map((el) => ({name: name(el), bg: getComputedStyle(el).backgroundColor, outside: outside(el)})); }"""

CONTROLS_JS = r"""() => { const outside = """ + OUTSIDE_FN + r""";
  const vis = (el) => el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}) && el.getBoundingClientRect().width > 0;
  const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.name ? `[name=${el.name}]` : '') +
      [...el.classList].slice(0, 2).map((c) => '.' + c).join('');
  // .chip-check joins the list (spec Triage QA-R3); a disabled chip is inactive, so WCAG 1.4.11 doesn't apply.
  const sel = 'input:not([type=range]):not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea, .choice, .chip-check:not(.disabled)';
  return [...document.querySelectorAll(sel)].filter((el) => vis(el) && !el.closest('.sr-only')).map((el) => {
    const s = getComputedStyle(el);
    return {name: name(el), widths: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth].map(parseFloat),
            styles: [s.borderTopStyle, s.borderRightStyle, s.borderBottomStyle, s.borderLeftStyle],
            color: s.borderTopColor, outside: outside(el)}; }); }"""


def _solid(c, page_bg):
    return c if _alpha(c) >= 1 else _over(c, page_bg)


# ================================================================ CHL-DARK-3 cards and panels step off the page
@pytest.mark.parametrize("way", DARK_WAYS, ids=DARK_IDS)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DARK_3_every_top_level_card_and_panel_is_1_15_against_the_page(browser, site_url, size, way):
    ctx, pg = _open(browser, site_url, size, scheme=way[0], theme=way[1])
    try:
        page = _page_bg(pg)
        bad, counted = [], 0
        for view in VIEWS:
            _go(pg, view)
            for el in pg.evaluate(LAYERS_JS):
                if _solid(el["outside"], page) != _solid(page, page):
                    continue  # sits on something other than the page (spec: parent background is --bg)
                counted += 1
                bg = _solid(el["bg"], page) if _alpha(el["bg"]) else page
                r = contrast(bg, page)
                if r < LAYER:
                    bad.append(f"{view}: {el['name']} {bg} on page {page}: {r:.2f}:1")
        assert counted >= len(VIEWS), f"only {counted} cards/panels found on the page background"
        assert bad == [], f"dark ({way}) at {size[0]}px, want {LAYER}:1 or more:\n" + "\n".join(sorted(set(bad))[:30])
        assert pg.errors == []
    finally:
        ctx.close()


# ================================================================ CHL-DARK-4 the dialog steps off the page and the scrim
@pytest.mark.parametrize("way", DARK_WAYS, ids=DARK_IDS)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DARK_4_read_more_dialog_is_on_the_scrim_and_1_15_against_page_and_scrim(browser, site_url, size, way):
    ctx, pg = _open(browser, site_url, size, scheme=way[0], theme=way[1])
    try:
        page, scrim = _page_bg(pg), _var(pg, "--scrim")
        _open_read_more(pg, size)
        got = pg.evaluate("""() => ({modal: getComputedStyle(document.querySelector('#ack.modal, #ack .modal, .modal')).backgroundColor,
            inner: getComputedStyle(document.querySelector('#ack .modal-inner')).backgroundColor})""")
        assert got["modal"] == scrim, f".modal paints {got['modal']}, want --scrim {scrim}"
        scrimmed = _over(scrim, page)
        inner = _solid(got["inner"], page)
        r_page, r_scrim = contrast(inner, page), contrast(inner, scrimmed)
        assert r_page >= LAYER and r_scrim >= LAYER, (
            f".modal-inner {inner}: {r_page:.2f}:1 on the page {page}, {r_scrim:.2f}:1 on the scrimmed page {scrimmed} "
            f"(want {LAYER}:1 on both)")
    finally:
        ctx.close()


# ================================================================ CHL-DARK-5 the drawer steps off the page and the scrim
@pytest.mark.parametrize("way", DARK_WAYS, ids=DARK_IDS)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DARK_5_ticker_drawer_is_1_15_against_page_and_scrim_and_trades_sit_on_it(browser, site_url, size, way):
    ctx, pg = _open(browser, site_url, size, scheme=way[0], theme=way[1])
    try:
        page, scrim = _page_bg(pg), _var(pg, "--scrim")
        _open_drawer(pg)
        got = pg.evaluate("""() => ({drawer: getComputedStyle(document.querySelector('#drawer')).backgroundColor,
            inner: getComputedStyle(document.querySelector('#drawer .drawer-inner')).backgroundColor,
            cards: [...document.querySelectorAll('#drawer-body .card')].map((c) => getComputedStyle(c).backgroundColor)})""")
        assert got["drawer"] == scrim, f"#drawer paints {got['drawer']}, want --scrim {scrim}"
        scrimmed = _over(scrim, page)
        inner = _solid(got["inner"], page)
        r_page, r_scrim = contrast(inner, page), contrast(inner, scrimmed)
        assert r_page >= LAYER and r_scrim >= LAYER, (
            f".drawer-inner {inner}: {r_page:.2f}:1 on the page {page}, {r_scrim:.2f}:1 on the scrimmed page {scrimmed} "
            f"(want {LAYER}:1 on both)")
        assert got["cards"], "the drawer shows its trades"
        assert all(_alpha(c) == 0 for c in got["cards"]), f"UX11: drawer trades sit on the drawer, not in cards: {got['cards']}"
    finally:
        ctx.close()


# ================================================================ CHL-DARK-6 every control's edge is 3:1 against what's outside it
@pytest.mark.parametrize("mode", MODES, ids=MODE_IDS)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DARK_6_every_field_select_textarea_and_choice_has_a_3_to_1_edge(browser, site_url, size, mode):
    ctx, pg = _open(browser, site_url, size, scheme=mode[0], contrast_pref=mode[1])
    try:
        page = _page_bg(pg)
        bad, seen = [], set()
        for view in VIEWS:
            _go(pg, view)
            for c in pg.evaluate(CONTROLS_JS):
                seen.add(c["name"])
                if min(c["widths"]) < 1 or any(s in ("none", "hidden") for s in c["styles"]):
                    bad.append(f"{view}: {c['name']} border {c['widths']} {c['styles']}")
                    continue
                out = _solid(c["outside"], page)
                edge = _solid(c["color"], out)
                r = contrast(edge, out)
                if r < EDGE:
                    bad.append(f"{view}: {c['name']} edge {edge} on {out}: {r:.2f}:1")
        assert any(n.startswith("textarea") for n in seen) and any(".choice" in n for n in seen) \
            and any(".chip-check" in n for n in seen), \
            f"the sweep should reach the Profile textarea, the Appearance choices and the Screener chips; saw {sorted(seen)}"
        assert bad == [], f"{mode} at {size[0]}px, want {EDGE}:1 edges:\n" + "\n".join(sorted(set(bad))[:30])
    finally:
        ctx.close()


@pytest.mark.parametrize("way", DARK_WAYS, ids=DARK_IDS)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DARK_6_controls_on_a_raised_card_use_control_edge(browser, site_url, size, way):
    # The spec's biggest risk: --tab-line passes on --surface today but drops under 3:1 on a raised card.
    # This pins the per-control edge to --control-edge, so it holds whatever the card is painted.
    ctx, pg = _open(browser, site_url, size, scheme=way[0], theme=way[1])
    try:
        edge = _var(pg, "--control-edge")
        assert edge, "--control-edge is not defined (CHL-DARK-1)"
        _go(pg, "profile")
        got = pg.evaluate("""() => [...document.querySelectorAll('#tab-profile textarea, #tab-profile .choice:not(:has(input:checked))')]
            .filter((el) => el.checkVisibility()).map((el) => getComputedStyle(el).borderTopColor)""")
        assert got and set(got) == {edge}, f"profile control edges {sorted(set(got))}, want --control-edge {edge}"
        _go(pg, "screener")  # Triage QA-R3: the unticked filter chips are controls on a raised panel too
        # QA-R4: the visible trade-type chips start ticked (or disabled) by design, so the unticked chips a
        # visitor meets are the Industries ones under "More filters". Open it as a person would.
        more = pg.locator("#more-filters")
        if not more.evaluate("(d) => d.open"):
            more.locator("summary").click()
        expect(pg.locator("#domain-select .chip-check").first).to_be_visible()
        chips =pg.evaluate("""() => [...document.querySelectorAll('#tab-screener .chip-check:not(.disabled):not(:has(input:checked))')]
            .filter((el) => el.checkVisibility()).map((el) => getComputedStyle(el).borderTopColor)""")
        assert chips and set(chips) == {edge}, f"screener .chip-check edges {sorted(set(chips))}, want --control-edge {edge}"
    finally:
        ctx.close()


# ================================================================ CHL-DARK-7 the risk slider
@pytest.mark.parametrize("mode", MODES + [("light", "picked-dark")], ids=MODE_IDS + ["picked-dark"])
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DARK_7_risk_slider_keeps_the_accent_at_3_to_1_and_its_outline_is_control_edge(browser, site_url, size, mode):
    theme = "dark" if mode[1] == "picked-dark" else None
    ctx, pg = _open(browser, site_url, size, scheme=mode[0], contrast_pref=None if theme else mode[1], theme=theme)
    try:
        slider = pg.locator(".risk-control input[type=range]").filter(visible=True).first
        expect(slider).to_be_visible()
        accent, raised, surface, edge = (_var(pg, n) for n in ("--accent", "--raised", "--surface", "--control-edge"))
        assert raised and edge, f"--raised {raised!r} / --control-edge {edge!r} not defined (CHL-DARK-1)"
        assert slider.evaluate("(s) => getComputedStyle(s).accentColor") == accent, "the slider keeps accent-color: var(--accent)"
        assert contrast(accent, raised) >= EDGE and contrast(accent, surface) >= EDGE, \
            f"--accent {accent}: {contrast(accent, raised):.2f}:1 on --raised, {contrast(accent, surface):.2f}:1 on --surface"
        outline = slider.evaluate("(s) => getComputedStyle(s.closest('.risk-control')).borderTopColor")
        assert outline == edge, f".risk-control outline is {outline}, want --control-edge {edge}"
    finally:
        ctx.close()


# ================================================================ CHL-DARK-8b HC dark: the --line border is the layer cue
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DARK_8b_hc_dark_cards_panels_and_dialog_have_a_3_to_1_line_border(browser, site_url, size):
    # Triage QA-R2: in HC dark --raised = --surface, so .card, .panel and .modal-inner need a 1px+ --line border
    # at 3:1 or more against the page.
    ctx, pg = _open(browser, site_url, size, scheme="dark", contrast_pref="more")
    try:
        page, line = _page_bg(pg), _var(pg, "--line")
        assert contrast(_solid(line, page), page) >= EDGE, f"HC dark --line {line} on the page {page}"
        border_js = """(sel) => [...document.querySelectorAll(sel)].filter((el) => el.checkVisibility()).map((el) => {
            const s = getComputedStyle(el); return {w: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth,
            s.borderLeftWidth].map(parseFloat), c: s.borderTopColor}; })"""
        bad, seen = [], set()
        for view, sel in (("today", "#ideas .card"), ("profile", "#tab-profile .panel")):
            _go(pg, view)
            for b in pg.evaluate(border_js, sel):
                seen.add(sel)
                if min(b["w"]) < 1 or b["c"] != line:
                    bad.append(f"{view} {sel}: border {b['w']} {b['c']}, want 1px+ --line {line}")
        pg.click("[role=tab][data-tab=today]")
        _open_read_more(pg, size)
        for b in pg.evaluate(border_js, "#ack .modal-inner"):
            seen.add(".modal-inner")
            if min(b["w"]) < 1 or b["c"] != line:
                bad.append(f".modal-inner: border {b['w']} {b['c']}, want 1px+ --line {line}")
        assert len(seen) == 3, f"found {sorted(seen)}"
        assert bad == [], "\n".join(bad[:20])
    finally:
        ctx.close()


# ================================================================ CHL-DARK-9 axe and fit on every tab, the dialog and the drawer
@pytest.fixture(scope="module")
def axe_source():
    path = os.environ.get("CHARLIE_AXE_JS")
    if not path:
        pytest.fail("set CHARLIE_AXE_JS to axe-core's axe.min.js (CI installs axe-core@4.10.3 with npm)")
    return Path(path).read_text()


def _axe(pg, axe_url, where):
    if not pg.evaluate("() => typeof window.axe !== 'undefined'"):
        pg.add_script_tag(url=axe_url)
    found = pg.evaluate("(tags) => axe.run(document, {runOnly: tags}).then((r) => r.violations.map((v) => "
                        "v.id + ' ' + v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(', ')))", AXE_TAGS)
    out = [f"{where}: {v}" for v in found]
    if pg.evaluate("document.documentElement.scrollWidth > innerWidth"):
        out.append(f"{where}: horizontal overflow")
    return out


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DARK_9_axe_passes_on_every_tab_the_dialog_and_the_drawer(browser, site_url, axe_source, size, scheme):
    ctx, pg = _new(browser, size, scheme)
    try:
        # The demo's CSP blocks inline scripts, so axe is served as a same-origin file.
        axe_url = site_url.rsplit("/", 1)[0] + "/__axe.min.js"
        pg.route(axe_url, lambda route: route.fulfill(body=axe_source, content_type="text/javascript"))
        pg.goto(site_url)
        expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
        problems = _axe(pg, axe_url, "first-open dialog")
        pg.click("#ack-btn")
        for view in VIEWS:
            _go(pg, view)
            problems += _axe(pg, axe_url, view)
        pg.click("[role=tab][data-tab=today]")
        _open_read_more(pg, size)
        problems += _axe(pg, axe_url, "read more dialog")
        pg.click("#ack-btn")
        _open_drawer(pg)
        problems += _axe(pg, axe_url, "drawer")
        assert problems == [], f"{scheme} at {size[0]}px:\n" + "\n".join(problems[:30])
        assert pg.errors == []
    finally:
        ctx.close()
