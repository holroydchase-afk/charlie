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
        # UX17: a trade with no chance-of-profit estimate (shares) shows "Money tied up" in that tile.
        for label in [("Chance of profit", "Money tied up"), ("Max profit",), ("Max loss",)]:
            if not any(m.startswith(label) for m in metrics):
                problems.append(f"card {i + 1}: hero metrics miss '{' or '.join(label)}'")
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
    # UX23 hides the stats while there are no paper trades, so open one first.
    _open_one_paper_trade(pg)
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


# ================================================================ round 2: CHL-UX16 to UX23 (AFTER report)
def _set_risk(pg, level):
    """Move the risk slider as a person would (change event), then wait for the cards to redraw."""
    pg.locator("#risk").evaluate(
        "(r, v) => { r.value = String(v); r.dispatchEvent(new Event('input', {bubbles: true}));"
        " r.dispatchEvent(new Event('change', {bubbles: true})); }", level)
    pg.wait_for_timeout(200)
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)


HERO_VALUES = """(root) => { const cards = [...root.querySelectorAll('.card')];
    return [...root.querySelectorAll('.hero-m .metric')].filter((m) => m.checkVisibility()).map((m) => ({
    k: m.querySelector('.k')?.textContent.trim() || '', v: m.querySelector('.v')?.textContent.trim() || '',
    card: m.closest('.card')?.querySelector('.strategy-tag')?.textContent.trim() || '',
    idx: cards.indexOf(m.closest('.card'))})); }"""


# ---------------------------------------------------------------- CHL-UX16 the thesis line gives a reason
@pytest.mark.parametrize("level", [1, 2, 4])
def test_UX16_today_thesis_lines_never_repeat_the_charlie_score(make_page, site_url, level):
    pg = _open(make_page, site_url, PHONE)
    if level != 2:
        _set_risk(pg, level)
    theses = pg.locator("#ideas .card .thesis")
    expect(theses.first).to_be_visible()
    lines = theses.all_inner_texts()
    assert len(lines) == pg.locator("#ideas .card").count(), "every idea card should have one thesis line"
    assert [x for x in lines if "Charlie score" in x] == [], f"thesis lines repeat the score badge: {lines}"
    no_downside = [x for x in lines if not re.search(r"\$\d[\d,]*\.\d\d", x)]
    assert no_downside == [], f"thesis lines without the price where you'd lose money: {no_downside}"


# ---------------------------------------------------------------- CHL-UX17 no "—" in the hero numbers
@pytest.mark.parametrize("level", [1, 2], ids=["shares-only", "conservative"])
def test_UX17_today_hero_metrics_never_show_a_dash(make_page, site_url, level):
    pg = _open(make_page, site_url, PHONE)
    if level != 2:
        _set_risk(pg, level)
        pg.wait_for_function("[...document.querySelectorAll('#ideas .card .strategy-tag')]"
                             ".every((t) => t.textContent.startsWith('Buy shares'))", timeout=ENGINE)
    found = pg.locator("#ideas").evaluate(HERO_VALUES)
    assert found, "no hero metrics on Today"
    dashes = [f"{x['card']}: {x['k']}" for x in found if x["v"] in ("—", "-", "–", "")]
    assert dashes == [], f"hero metrics show a dash: {dashes}"
    shares = [x for x in found if x["card"].startswith("Buy shares")]
    if level == 1:
        assert shares, "at level 1 every idea is a share purchase"
    missing = sorted({x["idx"] for x in shares} - {x["idx"] for x in shares if x["k"] == "Money tied up"})
    assert missing == [], f"share ideas without a 'Money tied up' hero tile: {missing}"
    tied = [x["v"] for x in shares if x["k"] == "Money tied up"]
    assert all(re.fullmatch(r"\$\d[\d,]*", v) for v in tied), f"'Money tied up' should be a dollar amount: {tied}"


def test_UX17_screener_cards_show_money_tied_up_not_a_dash(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.click("[data-tab=screener]")
    cards = pg.locator("#screen-results .row-card")
    expect(cards.first).to_be_visible(timeout=ENGINE)
    found = cards.evaluate_all("""(cs) => cs.filter((c) => c.checkVisibility()).map((c) => ({
        type: c.querySelector('.rc-top')?.innerText.replace(/\\s+/g, ' ').trim() || '',
        cells: [...c.querySelectorAll('.rc-grid > span')].map((s) => ({
            k: s.firstElementChild?.textContent.trim() || '', v: s.querySelector('b')?.textContent.trim() || ''}))}))""")
    assert found
    dashes = [f"{c['type']}: {x['k']}" for c in found for x in c["cells"] if x["v"] in ("—", "-", "–", "")]
    assert dashes == [], f"screener cards show a dash: {dashes[:5]}"
    shares = [c for c in found if "Buy shares" in c["type"]]
    assert shares, "the default screen should include share purchases"
    no_tied = [c["type"] for c in shares if not any(x["k"] == "Money tied up" for x in c["cells"])]
    assert no_tied == [], f"share cards without 'Money tied up': {no_tied[:5]}"


# ---------------------------------------------------------------- CHL-UX3 (updated for UX17)
# UX3 asked for "Chance of profit" in every hero row; UX17 swaps that tile for "Money tied up" on
# trades with no chance-of-profit estimate (share purchases). Both must still be three tiles.
def test_UX3_UX17_hero_row_is_chance_or_money_tied_up_then_profit_and_loss(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    found = pg.locator("#ideas").evaluate(HERO_VALUES)
    by_card = {}
    for x in found:
        by_card.setdefault(f"card {x['idx'] + 1} ({x['card']})", []).append(x["k"])
    problems = [f"{c}: {ks}" for c, ks in by_card.items()
                if len(ks) != 3 or ks[0] not in ("Chance of profit", "Money tied up") or ks[1:] != ["Max profit", "Max loss"]]
    assert problems == []


# ---------------------------------------------------------------- CHL-UX18 payoff chart labels
CHART_LABELS = """(root) => [...root.querySelectorAll('svg.payoff')].filter((s) => s.checkVisibility()
        && s.closest('.chart')?.dataset.chart && s.querySelector('.curve')).map((svg) => {
    const card = svg.closest('.card');
    const box = (t) => { const r = t.getBoundingClientRect();
        return {text: t.textContent.trim(), cls: t.getAttribute('class') || '', l: r.left, r: r.right, t: r.top, b: r.bottom}; };
    return {card: card?.querySelector('.strategy-tag')?.textContent.trim() || '',
            sym: (card?.querySelector('[data-ticker]')?.dataset.ticker) || (document.querySelector('#drawer [data-ticker]')?.dataset.ticker) || '',
            cardText: card ? card.innerText : '',
            labels: [...svg.querySelectorAll('text')].filter((t) => t.checkVisibility()).map(box)};
})"""


def _chart_problems(charts):
    problems = []
    for c in charts:
        name, labs = c["card"], c["labels"]
        for i, a in enumerate(labs):
            for b in labs[i + 1:]:
                if a["l"] < b["r"] and b["l"] < a["r"] and a["t"] < b["b"] and b["t"] < a["b"]:
                    problems.append(f"{name}: '{a['text']}' overlaps '{b['text']}'")
        ys = [x for x in labs if "y-label" in x["cls"].split()]
        xs = [x for x in labs if "x-label" in x["cls"].split()]
        if not ys or not xs:
            problems.append(f"{name}: want P&L labels (text.y-label) and price labels (text.x-label), got "
                            f"{[(x['text'], x['cls']) for x in labs]}")
            continue
        for y in ys:
            for x in xs:
                same_x = y["l"] < x["r"] + 4 and x["l"] < y["r"] + 4
                if same_x and abs((y["t"] + y["b"]) / 2 - (x["t"] + x["b"]) / 2) < 20:
                    problems.append(f"{name}: P&L '{y['text']}' sits within 20px of price '{x['text']}'")
        if not any(y["text"] == "$0" for y in ys):
            problems.append(f"{name}: no '$0' baseline label among {[y['text'] for y in ys]}")
        unsigned = [y["text"] for y in ys if y["text"] != "$0" and not re.match(r"^[+\-−]\$", y["text"])]
        if unsigned:
            problems.append(f"{name}: P&L labels need a + or − sign: {unsigned}")
        cap = re.search(r"Shown for ([A-Z.]+) between \$[\d,]+ and \$[\d,]+", c["cardText"])
        if not cap:
            problems.append(f"{name}: no caption 'Shown for <SYM> between $X and $Y'")
        elif c["sym"] and cap.group(1) != c["sym"]:
            problems.append(f"{name}: caption names {cap.group(1)}, card is {c['sym']}")
    return problems


@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])
def test_UX18_payoff_labels_dont_collide_and_have_a_caption(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    charts = pg.locator("#ideas").evaluate(CHART_LABELS)
    assert charts, "no payoff charts on Today"
    assert _chart_problems(charts) == []


# ---------------------------------------------------------------- CHL-UX19 screener: results first on a phone
FIRST_ROW_TOP = """() => { const r = [...document.querySelectorAll('#screen-results [data-row]')].find((x) => x.checkVisibility());
    return r ? r.getBoundingClientRect().top + scrollY : null; }"""


def test_UX19_phone_screener_shows_results_in_the_first_screen(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.click("[data-tab=screener]")
    expect(pg.locator("#screen-results [data-row]").first).to_be_attached(timeout=ENGINE)
    pg.evaluate("scrollTo(0, 0)")
    top = pg.evaluate(FIRST_ROW_TOP)
    assert top is not None and top < 844, f"first screener result starts {top}px down the page at 390x844 (want < 844)"
    edit = pg.locator("#tab-screener").get_by_role("button", name=re.compile("Edit filters", re.I))
    expect(edit).to_be_visible()
    expect(pg.locator("#strategy-select")).to_be_hidden()  # folded into the summary row
    edit.click()
    expect(pg.locator("#strategy-select")).to_be_visible()


@pytest.mark.parametrize("level", [2, 4])
def test_UX19_strategy_chips_above_the_level_are_disabled_and_allowed_ones_ticked(make_page, site_url, level):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from charlie.strategies import STRATEGIES
    pg = _open(make_page, site_url, DESKTOP)
    if level != 2:
        _set_risk(pg, level)
    pg.click("[data-tab=screener]")
    expect(pg.locator("#screen-results [data-row]").first).to_be_attached(timeout=ENGINE)
    chips = pg.locator("#strategy-select input[name=strategies]").evaluate_all(
        "(xs) => xs.map((x) => ({key: x.value, checked: x.checked, disabled: x.disabled,"
        " label: x.closest('label')?.innerText.replace(/\\s+/g, ' ').trim() || ''}))")
    assert {c["key"] for c in chips} == set(STRATEGIES)
    problems = []
    for c in chips:
        need = STRATEGIES[c["key"]]["min_level"]
        if need > level:
            if not c["disabled"]:
                problems.append(f"{c['label']}: needs level {need} but can be ticked at level {level}")
            if f"(needs level {need})" not in c["label"]:
                problems.append(f"{c['label']}: should say '(needs level {need})'")
        else:
            if c["disabled"] or not c["checked"]:
                problems.append(f"{c['label']}: allowed at level {level}, should be enabled and ticked by default")
            if "needs level" in c["label"]:
                problems.append(f"{c['label']}: allowed, shouldn't say 'needs level'")
    assert problems == []


# ---------------------------------------------------------------- CHL-UX20 a number above the fold on a laptop
def test_UX20_first_card_hero_metrics_are_in_the_first_laptop_screen(make_page, site_url):
    pg = _open(make_page, site_url, DESKTOP)
    pg.evaluate("scrollTo(0, 0)")
    boxes = pg.locator("#ideas .card").first.locator(".hero-m .metric").evaluate_all(
        "(ms) => ms.map((m) => { const r = m.getBoundingClientRect(); return {k: m.querySelector('.k').textContent, t: r.top, b: r.bottom}; })")
    assert len(boxes) == 3
    foot = pg.locator("#footer-disclaimer").bounding_box()
    limit = min(800, foot["y"]) if foot else 800
    out = [f"{b['k']}: {b['t']:.0f}-{b['b']:.0f}px" for b in boxes if b["t"] < 0 or b["b"] > limit]
    assert out == [], f"card 1 hero metrics not fully visible above {limit:.0f}px at 1280x800: {out}"


# ---------------------------------------------------------------- CHL-UX21 all six tabs fit at 390
def test_UX21_all_six_tabs_fit_at_390_and_the_last_says_portfolio(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    tabs = pg.locator("[role=tab]")
    expect(tabs).to_have_count(6)
    expect(pg.locator("#tabbtn-paper")).to_have_text("Portfolio")
    boxes = tabs.evaluate_all("""(ts) => ts.map((t) => { const r = t.getBoundingClientRect(), bar = t.parentElement.getBoundingClientRect();
        return {name: t.textContent.trim(), l: r.left, r: r.right, barL: bar.left, barR: bar.right}; })""")
    clipped = [f"{b['name']} {b['l']:.0f}-{b['r']:.0f}" for b in boxes
               if b["l"] < max(0, b["barL"]) - 0.5 or b["r"] > min(390, b["barR"]) + 0.5]
    assert clipped == [], f"tabs clipped at 390px: {clipped}"
    pg.click("[data-tab=paper]")
    expect(pg.locator("#tab-paper h1")).to_have_text("Paper portfolio")


# ---------------------------------------------------------------- CHL-UX22 plain drawer labels
def test_UX22_drawer_metric_labels_are_plain_words(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.locator("#ideas .card [data-ticker]").first.click()
    drawer = pg.locator("#drawer")
    expect(drawer.locator("svg.payoff").first).to_be_visible()
    labels = drawer.locator(".metric .k").all_inner_texts()
    jargon = [k for k in labels if k.strip() in ("ROIC", "FCF yield", "ATM IV", "Op. margin", "Debt/Equity")]
    assert jargon == [], f"drawer metric labels use jargon: {jargon}"
    for plain in ["Return on capital", "Operating margin", "Free-cash yield", "Debt to equity"]:
        assert plain in labels, f"drawer metrics miss '{plain}': {labels}"
    text = drawer.inner_text()
    bare = re.findall(r"\bROIC\b|\bFCF\b|\bATM IV\b", text)
    assert bare == [], f"bare jargon in the drawer: {bare}"


# ---------------------------------------------------------------- CHL-UX23 paper portfolio
def test_UX23_empty_paper_portfolio_hides_stats_and_shows_the_button_high(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.click("[data-tab=paper]")
    btn = pg.locator("#paper-list").get_by_role("button", name=re.compile("today's ideas", re.I))
    expect(btn).to_be_visible()
    visible_stats = pg.locator("#paper-stats .metric").evaluate_all("(ms) => ms.filter((m) => m.checkVisibility()).length")
    assert visible_stats == 0, f"{visible_stats} stat tiles show while there are no paper trades"
    pg.evaluate("scrollTo(0, 0)")
    b = btn.bounding_box()
    bottom = b["y"] + b["height"] + pg.evaluate("scrollY")
    assert bottom <= 600, f"'See today's ideas' ends {bottom:.0f}px down at 390x844 (want <= 600)"


def _open_one_paper_trade(pg):
    card = pg.locator("#ideas .card").first
    sym = card.locator("[data-ticker]").get_attribute("data-ticker")
    card.locator("[data-paper]").click()
    expect(pg.locator("#toast")).to_contain_text("Paper trade opened", timeout=ENGINE)
    pg.click("[data-tab=paper]")
    expect(pg.locator("#paper-list [data-close]").first).to_be_attached(timeout=ENGINE)
    return sym


def test_UX23_open_position_close_button_says_close_trade(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    sym = _open_one_paper_trade(pg)
    btn = pg.locator("#paper-list [data-close]").filter(visible=True).first
    expect(btn).to_have_text("Close trade")
    label = btn.get_attribute("aria-label") or ""
    assert label.startswith(f"Close paper trade {sym}"), f"close button aria-label: {label!r}"
    # With a position open, the stats come back.
    expect(pg.locator("#paper-stats .metric").first).to_be_visible()


# ================================================================ round 3: CHL-UX27 to UX34 (AFTER report 2)
SMALL = (320, 700)


def _strategies():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from charlie.strategies import STRATEGIES
    return STRATEGIES


EXPLAINER_HEADINGS = """(root) => [...root.querySelectorAll('h3, summary')].map((x) => x.textContent.replace(/\\s+/g, ' ').trim())
    .filter((x) => /^(What is|How )/.test(x))"""


def _explainer_problems(headings, titles):
    problems = [h for h in headings if re.search(r"What is a buy", h, re.I) or "leaps" in h]
    problems += [f"not a strategy explainer_title: {h!r}" for h in headings if h not in titles]
    return problems


# ---------------------------------------------------------------- CHL-UX27 explainer heading is real English
@pytest.mark.parametrize("level", [1, 4], ids=["shares-only", "growth-leaps"])
def test_UX27_explainer_headings_come_from_the_strategy_not_the_label(make_page, site_url, level):
    titles = {s["explainer_title"] for s in _strategies().values() if "explainer_title" in s}
    pg = _open(make_page, site_url, PHONE)
    _set_risk(pg, level)
    if level == 1:
        pg.wait_for_function("[...document.querySelectorAll('#ideas .card .strategy-tag')]"
                             ".every((t) => t.textContent.startsWith('Buy shares'))", timeout=ENGINE)
    cards = pg.locator("#ideas").evaluate(EXPLAINER_HEADINGS)
    assert len(cards) >= pg.locator("#ideas .card").count(), f"each idea card needs an explainer heading: {cards}"
    pg.locator("#ideas .card [data-ticker]").first.click()
    drawer = pg.locator("#drawer")
    expect(drawer.locator("svg.payoff").first).to_be_visible()
    found = cards + drawer.evaluate(EXPLAINER_HEADINGS)
    assert _explainer_problems(found, titles) == []


# ---------------------------------------------------------------- CHL-UX28 an idea number in the phone's first screen
def test_UX28_phone_first_screen_shows_a_top_idea_number(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.evaluate("scrollTo(0, 0)")
    foot = pg.locator("#footer-disclaimer").bounding_box()
    limit = min(844, foot["y"]) if foot else 844
    m = pg.locator("#ideas .card").first.locator(".hero-m .metric").first.bounding_box()
    metric_ok = m is not None and m["y"] >= 0 and m["y"] + m["height"] <= limit
    link = pg.locator(".hero-top-idea")
    link_ok = False
    if link.count() and link.first.is_visible():
        b = link.first.bounding_box()
        link_ok = b["y"] >= 0 and b["y"] + b["height"] <= limit and bool(re.search(r"\d", link.first.inner_text()))
    assert metric_ok or link_ok, (
        f"no idea number above {limit:.0f}px at 390x844: card 1 first metric bottom "
        f"{(m['y'] + m['height']) if m else None}, .hero-top-idea visible={link_ok}")


# ---------------------------------------------------------------- CHL-UX29 reflow at 320px
@pytest.mark.parametrize("tab", ["today", "profile", "screener", "chat", "paper", "learn"])
def test_UX29_no_horizontal_scroll_at_320_on_any_tab(make_page, site_url, tab):
    pg = _open(make_page, site_url, SMALL)
    if tab != "today":
        pg.click(f"[data-tab={tab}]")
        if tab == "screener":
            expect(pg.locator("#screen-results [data-row]").first).to_be_attached(timeout=ENGINE)
        pg.wait_for_timeout(300)
    wide = pg.evaluate("""() => ({sw: document.documentElement.scrollWidth,
        over: [...document.querySelectorAll('body *')].filter((e) => e.checkVisibility()
            && e.getBoundingClientRect().right > 320.5 && !e.closest('.table-wrap, .ticket, pre')
            && ![...Array(20)].reduce((a, _) => [...a, (a.at(-1) || e).parentElement].filter(Boolean), [])
                .some((p) => p !== document.body && p !== document.documentElement && /auto|scroll|hidden/.test(getComputedStyle(p).overflowX)))
            .slice(0, 5).map((e) => `${e.tagName.toLowerCase()}${e.id ? '#' + e.id : ''}.${[...e.classList].join('.')} → ${Math.round(e.getBoundingClientRect().right)}`)})""")
    assert wide["sw"] <= 320, f"{tab}: scrollWidth {wide['sw']} at 320x700; overflowing: {wide['over']}"


# ---------------------------------------------------------------- CHL-UX30 paper credit reads as money received
def _open_one_credit_paper_trade(pg):
    ids = pg.locator("#ideas .card [data-paper]").evaluate_all(
        "(bs) => bs.map((b) => b.dataset.paper).filter((id) => (window._trades[id]?.net_premium || 0) > 0)")
    assert ids, "no credit trade (net_premium > 0) among Today's ideas at the default level"
    pg.locator(f"#ideas .card [data-paper='{ids[0]}']").click()
    expect(pg.locator("#toast")).to_contain_text("Paper trade opened", timeout=ENGINE)
    pg.click("[data-tab=paper]")
    expect(pg.locator("#paper-list [data-close]").first).to_be_attached(timeout=ENGINE)


@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])
def test_UX30_paper_credit_shows_you_received_not_a_minus(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    _open_one_credit_paper_trade(pg)
    text = pg.locator("#paper-list").inner_text()
    assert re.search(r"You received \$\d", text), f"a credit position should say 'You received $X':\n{text}"
    hyphen = re.findall(r"(?<![\w$])-\$[\d,.]+", text)
    assert hyphen == [], f"credit amounts shown with a hyphen minus: {hyphen}"


def test_UX30_win_rate_tile_hidden_until_a_trade_is_closed(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    _open_one_paper_trade(pg)
    expect(pg.locator("#paper-stats .metric").first).to_be_visible()
    keys = pg.locator("#paper-stats .metric .k").all_inner_texts()
    assert not [k for k in keys if "Win rate" in k], f"win-rate tile shows with no closed trades: {keys}"
    pg.locator("#paper-list [data-close]").filter(visible=True).first.click()
    expect(pg.locator("#paper-stats .metric .k", has_text="Win rate")).to_be_visible(timeout=ENGINE)


# ---------------------------------------------------------------- CHL-UX31 banner targets at least 24px
def test_UX31_banner_reset_and_back_link_are_at_least_24px_tall(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    small = []
    for sel in ("#reset-demo", ".demo-actions a"):
        b = pg.locator(sel).first.bounding_box()
        if b["height"] < 24:
            small.append(f"{sel}: {b['width']:.0f}x{b['height']:.0f}")
    assert small == [], f"banner targets under 24px tall at 390: {small}"


# ---------------------------------------------------------------- CHL-UX33 "Why this one" doesn't repeat the thesis
def test_UX33_why_this_one_does_not_repeat_the_thesis_line(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    first = pg.locator("#ideas .card").first
    first.locator("details.more > summary").click()
    expect(first.locator("details.more h3", has_text="Why this one")).to_be_visible()
    found = pg.locator("#ideas .card").evaluate_all("""(cs) => cs.map((c) => {
        const h = [...c.querySelectorAll('details.more h3')].find((x) => x.textContent.trim() === 'Why this one');
        return {thesis: c.querySelector('.thesis')?.textContent.trim() || '',
                why: h ? [...h.parentElement.querySelectorAll('li')].map((l) => l.textContent.trim()) : null}; })""")
    problems = [f"card {i + 1}: '{c['thesis']}'" for i, c in enumerate(found)
                if c["why"] is not None and c["thesis"] and c["thesis"] in c["why"]]
    assert problems == [], f"'Why this one' repeats the thesis line: {problems}"
    assert all(c["why"] for c in found), f"every card keeps a non-empty 'Why this one' list: {found}"


# ---------------------------------------------------------------- CHL-UX34 phone score badge has a noun
def test_UX34_phone_score_badge_starts_with_score(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    badges = pg.locator("#ideas .card .grade").evaluate_all(
        "(bs) => bs.map((b) => ({text: b.querySelector('.gscore').innerText.replace(/\\s+/g, ' ').trim(),"
        " label: b.getAttribute('aria-label') || ''}))")
    assert badges
    bad = [b["text"] for b in badges if not re.match(r"Score \d+", b["text"])]
    assert bad == [], f"phone score badges should read 'Score 76 · A': {bad}"
    assert all(b["label"].startswith("Charlie score ") for b in badges), badges


def test_UX42_alert_explainer_shows_only_once_there_is_a_trade(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.click("[data-tab=paper]")
    expect(pg.locator("#paper-list").get_by_role("button", name=re.compile("today's ideas", re.I))).to_be_visible()
    expect(pg.locator("#alert-explainer")).to_be_hidden()
    pg.click("[data-tab=today]")
    _open_one_paper_trade(pg)
    expect(pg.locator("#alert-explainer")).to_be_visible()
    expect(pg.locator("#alert-explainer")).to_contain_text("Near expiry")
