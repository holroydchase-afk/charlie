"""M1.11: UI polish acceptance tests (CHL-UX1 to UX15), on the built static demo in Chromium.

Criteria come from the ux-reviewer BEFORE report (showcase mode, Oct 28). Fixtures are shared
with test_demo_e2e.py in conftest.py. Runs only with CHARLIE_E2E=1.
Hard rule kept here too: the disclaimer stays visible on every idea card, outside any closed <details>.
"""
import json
import os
import re

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

NFA = "Not financial advice. Paper trading only."
PHONE = (390, 844)
DESKTOP = (1280, 800)
ENGINE = 120_000  # ms: the first Pyodide start in a cold browser


def _open(make_page, site_url, size=PHONE, ack=True, check=True):
    pg = make_page(*size, check=check)
    pg.goto(site_url)
    expect(pg.locator("#ideas .card").first).to_be_visible()
    if ack:
        pg.click("#ack-btn")
    return pg


# ---------------------------------------------------------------- CHL-UX1 chat input above the footer
@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])
def test_UX1_chat_input_is_not_covered_by_the_footer(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    pg.click("[data-tab=chat]")
    form = pg.locator("#chat-form")
    form.scroll_into_view_if_needed()
    f, foot = form.bounding_box(), pg.locator("#footer-disclaimer").bounding_box()
    assert f["y"] + f["height"] <= foot["y"] - 8, (
        f"#chat-form bottom {f['y'] + f['height']:.0f}px must sit at least 8px above the footer top {foot['y']:.0f}px")


# ---------------------------------------------------------------- CHL-UX2 hero says what Charlie is
def test_UX2_first_screen_says_what_charlie_does(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.evaluate("scrollTo(0, 0)")
    # One visible block above the first idea card, inside the first viewport, that names both the
    # resume input and the Munger checklist (the banner's "resume" alone doesn't count).
    found = pg.evaluate("""() => {
        const card = document.querySelector('#ideas .card');
        return [...document.body.querySelectorAll('*')].filter((el) => {
            if (el.contains(card) || !(el.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING)) return false;
            if (!el.checkVisibility()) return false;
            const r = el.getBoundingClientRect();
            if (r.top < 0 || r.bottom > innerHeight || r.height === 0) return false;
            const t = el.innerText || '';
            return /resume/i.test(t) && /munger/i.test(t);
        }).map((el) => el.tagName + (el.id ? '#' + el.id : ''));
    }""")
    assert found, "no visible block above the first card, inside 390x844, mentions both 'resume' and 'Munger'"


# ---------------------------------------------------------------- CHL-UX3/4 shorter cards, 3 hero metrics
VISIBLE_METRICS = """(card) => [...card.querySelectorAll('.metric')]
    .filter((m) => m.checkVisibility() && !m.closest('details:not([open])'))
    .map((m) => m.innerText.replace(/\\s+/g, ' ').trim())"""
VISIBLE_NFA = """(card) => [...card.querySelectorAll('.nfa')]
    .filter((n) => n.checkVisibility() && !n.closest('details:not([open])'))
    .map((n) => n.textContent.trim())"""


def test_UX3_UX4_idea_cards_are_short_with_three_hero_metrics(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.evaluate("document.querySelectorAll('#ideas details').forEach((d) => d.open = false)")
    cards = pg.locator("#ideas .card")
    assert cards.count() >= 1
    problems = []
    for i in range(cards.count()):
        card = cards.nth(i)
        h = card.bounding_box()["height"]
        if h > 800:
            problems.append(f"card {i + 1}: {h:.0f}px tall at 390px with details closed (max 800)")
        metrics = card.evaluate(VISIBLE_METRICS)
        if len(metrics) != 3:
            problems.append(f"card {i + 1}: {len(metrics)} visible metric tiles, want exactly 3: {metrics}")
        for label in ["Chance of profit", "Max profit", "Max loss"]:
            if not any(m.startswith(label) for m in metrics):
                problems.append(f"card {i + 1}: hero metrics miss '{label}'")
        # Hard rules: the disclaimer and the breakeven stay visible on the collapsed card.
        if NFA not in card.evaluate(VISIBLE_NFA):
            problems.append(f"card {i + 1}: no visible disclaimer outside a closed <details>")
        if "Breakeven" not in card.inner_text():
            problems.append(f"card {i + 1}: breakeven isn't visible on the collapsed card")
    assert problems == []


def test_UX4_card_details_still_hold_the_plan_and_ticket(make_page, site_url):
    # Collapsing must not drop content: the exit plan and order ticket are one click away.
    pg = _open(make_page, site_url, PHONE)
    card = pg.locator("#ideas .card").first
    more = card.locator("details.more")
    expect(more).to_have_count(1)
    assert more.evaluate("(d) => !d.open"), "the card's 'more' details should start closed"
    more.locator("summary").click()
    expect(more.locator(".ticket")).to_be_visible()
    expect(more).to_contain_text("Plan")
    expect(card.locator(".nfa").last).to_be_visible()


# ---------------------------------------------------------------- CHL-UX5 chart text readable on phones
EFFECTIVE_FONT_PX = """(root) => [...root.querySelectorAll('svg.payoff text')].filter((t) => t.checkVisibility()).map((t) => {
    const m = t.getScreenCTM();
    return {text: t.textContent, px: parseFloat(getComputedStyle(t).fontSize) * (m ? Math.hypot(m.a, m.b) : 1),
            h: t.getBoundingClientRect().height};
})"""


def test_UX5_payoff_and_sparkline_text_is_at_least_11px(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    small = [f"today card: '{x['text']}' {x['px']:.1f}px" for x in pg.locator("#ideas").evaluate(EFFECTIVE_FONT_PX)
             if x["px"] < 11 or x["h"] < 11]
    pg.locator("#ideas .card [data-ticker]").first.click()
    drawer = pg.locator("#drawer")
    expect(drawer.locator("svg.payoff").first).to_be_visible()
    small += [f"drawer: '{x['text']}' {x['px']:.1f}px" for x in drawer.evaluate(EFFECTIVE_FONT_PX)
              if x["px"] < 11 or x["h"] < 11]
    assert small == []


# ---------------------------------------------------------------- CHL-UX6 phone chrome
STICKY_TOP = """() => Math.max(0, ...[...document.body.querySelectorAll('*')].filter((el) => {
    if (['engine-status', 'toast', 'drawer', 'ack', 'footer-disclaimer'].includes(el.id)) return false;
    const p = getComputedStyle(el).position;
    if (p !== 'sticky' && p !== 'fixed') return false;
    const r = el.getBoundingClientRect();
    return el.checkVisibility() && r.top < 60 && r.height > 0;
}).map((el) => el.getBoundingClientRect().bottom))"""


def test_UX6_phone_chrome_above_the_content_is_at_most_160px(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.evaluate("scrollTo(0, 0)")
    top = pg.locator("main").bounding_box()["y"]
    assert top <= 160, f"header + banner + tabs take {top:.0f}px above the content at 390x844 (max 160)"
    pg.evaluate("scrollTo(0, 900)")
    pg.wait_for_timeout(100)
    stuck = pg.evaluate(STICKY_TOP)
    assert stuck <= 160, f"sticky chrome covers {stuck:.0f}px of the screen while scrolling (max 160)"


# ---------------------------------------------------------------- CHL-UX7 footer is one clean line
@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])
def test_UX7_footer_fits_without_a_clipped_line(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    foot = pg.locator("#footer-disclaimer")
    sh, ch = foot.evaluate("(f) => [f.scrollHeight, f.clientHeight]")
    assert sh <= ch, f"footer clips its text: scrollHeight {sh} > clientHeight {ch}"
    assert ch <= 48, f"footer is {ch}px tall (one line, ~40px)"
    expect(foot).to_contain_text("Not financial advice")


def test_UX7_footer_read_more_opens_the_full_disclaimer(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.locator("#footer-disclaimer").get_by_role("button", name=re.compile("read more", re.I)).click()
    expect(pg.get_by_text("Options involve significant risk", exact=False).first).to_be_visible()


# ---------------------------------------------------------------- CHL-UX8 plain-language ack modal
def test_UX8_ack_modal_says_practice_only(make_page, site_url):
    pg = _open(make_page, site_url, PHONE, ack=False)
    modal = pg.locator("#ack")
    expect(modal).to_be_visible()
    expect(modal.get_by_role("heading", name="Practice only, no real money")).to_be_visible()
    expect(modal).to_contain_text("Charlie never places real orders.")
    pg.click("#ack-btn")
    expect(modal).to_be_hidden()


# ---------------------------------------------------------------- CHL-UX9 screener opens with results
def test_UX9_screener_shows_results_on_first_open_and_fits_a_phone(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.click("[data-tab=screener]")
    rows = pg.locator("#screen-results [data-row]")
    expect(rows.first).to_be_visible(timeout=ENGINE)  # no click on "Run screen"
    overflow = pg.locator("#screen-results").evaluate("""(box) => [...box.querySelectorAll('*')].filter((el) => {
        if (!el.checkVisibility()) return false;
        const r = el.getBoundingClientRect();
        const scrolls = el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1;
        return scrolls || r.right > innerWidth + 1 || r.left < -1;
    }).slice(0, 5).map((el) => el.tagName + '.' + el.className + ' ' + el.scrollWidth + '/' + el.clientWidth)""")
    assert overflow == [], f"screener results overflow sideways at 390px: {overflow}"


def test_UX9_run_screen_button_stays_on_one_line(make_page, site_url):
    pg = _open(make_page, site_url, DESKTOP)
    pg.click("[data-tab=screener]")
    btn = pg.locator("#screen-form button[type=submit]")
    expect(btn).to_be_visible()
    lines = btn.evaluate("""(b) => { const r = document.createRange(); r.selectNodeContents(b);
        return new Set([...r.getClientRects()].map((x) => Math.round(x.top))).size; }""")
    assert lines == 1, f"'Run screen' wraps onto {lines} lines"


# ---------------------------------------------------------------- CHL-UX10 paper portfolio
def test_UX10_paper_empty_state_has_a_button_to_today(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.click("[data-tab=paper]")
    btn = pg.locator("#paper-list").get_by_role("button", name=re.compile("today's ideas", re.I))
    expect(btn).to_be_visible()
    btn.click()
    expect(pg.locator("#tabbtn-today")).to_have_attribute("aria-selected", "true")
    expect(pg.locator("#tab-today")).to_be_visible()


def test_UX10_paper_stats_are_visible_tiles_and_zero_is_neutral(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.click("[data-tab=paper]")
    expect(pg.locator("#paper-stats .metric").first).to_be_visible()
    found = pg.evaluate("""() => {
        const page = getComputedStyle(document.body).backgroundColor, ink = getComputedStyle(document.body).color;
        return [...document.querySelectorAll('#paper-stats .metric')].map((m) => {
            const s = getComputedStyle(m), v = m.querySelector('.v');
            const tile = s.backgroundColor !== page || parseFloat(s.borderTopWidth) > 0
                || !!m.closest('.panel');
            return {label: m.innerText.split('\\n')[0], tile, value: v.textContent.trim(), color: getComputedStyle(v).color, ink};
        });
    }""")
    problems = [f"{x['label']}: tile blends into the page" for x in found if not x["tile"]]
    problems += [f"{x['label']}: {x['value']} is colored {x['color']}, want neutral ink {x['ink']}"
                 for x in found if x["value"] in ("$0", "-$0") and x["color"] != x["ink"]]
    assert problems == []


# ---------------------------------------------------------------- CHL-UX11 drawer is an accessible dialog
def test_UX11_drawer_is_a_modal_dialog_that_moves_and_returns_focus(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    opener = pg.locator("#ideas .card [data-ticker]").first
    opener.evaluate("(b) => b.setAttribute('data-test-opener', '1')")
    opener.click()
    drawer = pg.locator("#drawer")
    expect(drawer).to_be_visible()
    expect(drawer).to_have_attribute("role", "dialog")
    expect(drawer).to_have_attribute("aria-modal", "true")
    name = drawer.evaluate("(d) => (d.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean)"
                           ".map((id) => document.getElementById(id)?.textContent.trim() || '').join(' ')"
                           " || d.getAttribute('aria-label') || ''")
    assert name, "the drawer dialog has no accessible name"
    expect(drawer.locator(".nfa").first).to_have_text(NFA)
    assert pg.evaluate("document.querySelector('#drawer').contains(document.activeElement)"), \
        "focus stays behind the overlay after opening the drawer"
    close = pg.locator("#drawer-close").bounding_box()
    assert close["width"] >= 44 and close["height"] >= 44, f"close button is {close['width']:.0f}x{close['height']:.0f}"
    pg.keyboard.press("Escape")
    expect(drawer).to_be_hidden()
    assert pg.evaluate("document.activeElement?.dataset?.testOpener === '1'"), "Escape doesn't return focus to the opener"


def test_UX11_drawer_says_sample_data_not_developer_wording(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.locator("#ideas .card [data-ticker]").first.click()
    drawer = pg.locator("#drawer")
    expect(drawer.locator("svg.payoff").first).to_be_visible()
    expect(drawer).not_to_contain_text("data: ")
    expect(drawer).to_contain_text("Sample data")


# ---------------------------------------------------------------- CHL-UX14 error state with retry
def test_UX14_ideas_error_offers_try_again_that_reloads(make_page, site_url):
    pg = make_page(*PHONE, check=False)  # the engine failing on purpose logs its own errors
    pg.on("pageerror", lambda e: None)
    origin = site_url.rsplit("/", 1)[0]

    def prebuilt_without_ideas(route):
        pre = json.loads(route.fetch().text())
        for level in pre["levels"].values():
            for k in [k for k in level if k.startswith("GET /api/ideas")]:
                del level[k]
        route.fulfill(status=200, content_type="application/json", body=json.dumps(pre))

    def no_engine(route):
        route.abort()
    pg.route(f"{origin}/prebuilt.json", prebuilt_without_ideas)
    pg.route("**/pyodide.js", no_engine)  # ideas need the engine, and it never arrives
    pg.goto(site_url)
    pg.click("#ack-btn")
    retry = pg.locator("#ideas").get_by_role("button", name="Try again")
    expect(retry).to_be_visible(timeout=30_000)
    expect(pg.locator("#ideas")).to_contain_text("Couldn't load ideas")
    pg.unroute("**/pyodide.js", no_engine)  # the network comes back
    retry.click()
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    expect(pg.locator("#ideas .card .nfa").first).to_have_text(NFA)


# ---------------------------------------------------------------- CHL-UX15 focus ring
def test_UX15_focus_visible_ring_uses_the_accent(make_page, site_url):
    pg = _open(make_page, site_url, DESKTOP)
    rule = pg.evaluate("""() => [...document.styleSheets].flatMap((s) => { try { return [...s.cssRules]; } catch (_) { return []; } })
        .some((r) => (r.selectorText || '').includes(':focus-visible') && /var\\(--accent\\)/.test(r.cssText))""")
    assert rule, "no :focus-visible rule that uses var(--accent)"
    pg.locator("#refresh-ideas").focus()
    pg.keyboard.press("Shift+Tab")
    pg.keyboard.press("Tab")  # keyboard focus, so :focus-visible applies
    ring = pg.evaluate("""() => { const s = getComputedStyle(document.activeElement);
        const probe = document.createElement('span'); probe.style.color = 'var(--accent)'; document.body.appendChild(probe);
        const accent = getComputedStyle(probe).color; probe.remove();
        return {style: s.outlineStyle, color: s.outlineColor, accent, id: document.activeElement.id}; }""")
    assert ring["style"] != "none" and ring["color"] == ring["accent"], ring
