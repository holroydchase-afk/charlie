"""CHL-NAV-1 to NAV-14: app-style navigation (phone bottom tab bar, laptop sidebar), on the built static demo.

Spec: staff-pm's CHL-NAV spec (Nov 22, Chase approved the design). Written first, red, by qa-tdd on Nov 22 2026.
Fixtures: conftest.py. Runs only with CHARLIE_E2E=1. The unit half is tests/test_nav.py.

Selector contract for the engineer (role and label first; these ids/classes are the only structural hooks):
- The tab bar / sidebar is the one existing `nav.tabs` (aria-label "Sections") holding the `[role=tablist]`;
  tab ids, `data-tab` values (today, screener, chat, paper, learn) and hashes stay. Visible words change.
- `#disclaimer-line` is the disclaimer line: on a phone it sits fixed directly above the bar and is (or holds) one
  full-width button that opens the full disclaimer; on a laptop it sits at the bottom of the sidebar and holds a
  visible "Read more" button. Its text contains "Not financial advice. Paper trading only.".
- The Profile button stays inside `<header>` at every width (on a laptop the sidebar may be that header) and its
  accessible name is "Profile". Profile's view is still `#tab-profile`; its Close button is inside it.
- The risk slider is the range input labelled "Risk level".

CHL-NAV-10 and CHL-NAV-13 ship as "no" (chief of staff's safe default, Nov 22, until Chase answers; privacy-security
rated NAV-13 as built a P1 and NAV-10 a P2): the disclaimer line stays visible while typing, and Chat keeps its
page-level disclaimer paragraph. Every trade-surface and chat-reply disclaimer test elsewhere stays untouched.
"""
import os
import re

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

NFA = "Not financial advice. Paper trading only."
SMALL = (320, 640)
PHONE = (390, 844)
DESKTOP = (1280, 800)
PHONES = [SMALL, PHONE]
PHONE_IDS = ["320x640", "390x844"]
ENGINE = 120_000  # ms: the first Pyodide start in a cold browser
TAB_WORDS = ["Today", "Search", "Chat", "Trades", "Learn"]
TAB_KEYS = ["today", "screener", "chat", "paper", "learn"]
TITLES = {"today": "Today", "screener": "Search trades", "chat": "Chat", "paper": "Paper trades",
          "learn": "Learn", "profile": "Profile"}
VIEWS = ["today", "screener", "chat", "paper", "learn", "profile"]
FULL_TEXT = "Options involve significant risk"


# ---------------------------------------------------------------- helpers
def _open(make_page, site_url, size=PHONE, scheme=None, ack=True, hash_=""):
    pg = make_page(*size, scheme=scheme)
    pg.goto(site_url + hash_)
    expect(pg.locator("#ack-btn")).to_be_visible(timeout=ENGINE)
    if ack:
        pg.click("#ack-btn")
    if not hash_:
        expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    return pg


def _profile_button(pg):
    return pg.locator("header").get_by_role("button", name="Profile", exact=True)


def _engine_idle(pg):
    pg.wait_for_timeout(200)
    pg.wait_for_function("document.querySelector('#engine-status').classList.contains('hidden')", timeout=ENGINE)


def _go(pg, view):
    if view == "profile":
        _profile_button(pg).click()
    else:
        pg.click(f"nav.tabs [role=tab][data-tab={view}]")
    expect(pg.locator(f"#tab-{view}")).to_be_visible()
    _engine_idle(pg)
    if view == "screener":
        expect(pg.locator("#screen-results [data-row]").first).to_be_attached(timeout=ENGINE)
    pg.evaluate("document.activeElement && document.activeElement.blur && document.activeElement.blur()")
    pg.evaluate("scrollTo(0, 0)")
    pg.wait_for_timeout(100)


def _color(pg, expr):
    return pg.evaluate("""(v) => { const i = document.createElement('i'); i.style.color = v;
        document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; }""", expr)


# Boxes of the bar and the line (null when missing or not rendered).
STACK = """() => { const box = (e) => { if (!e || !e.checkVisibility()) return null; const r = e.getBoundingClientRect();
        return r.height > 0 ? {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height} : null; };
    return {bar: box(document.querySelector('nav.tabs')), line: box(document.querySelector('#disclaimer-line')),
            vw: innerWidth, vh: innerHeight}; }"""


def _stack(pg):
    s = pg.evaluate(STACK)
    assert s["bar"], "no visible nav.tabs"
    assert s["line"], "no visible #disclaimer-line"
    s["top"] = min(s["bar"]["t"], s["line"]["t"])
    return s


ROWS = """(el) => { const tops = new Set(); const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
    while ((n = tw.nextNode())) { if (!n.textContent.trim() || !n.parentElement.checkVisibility()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      [...r.getClientRects()].filter((x) => x.width > 0).forEach((x) => tops.add(Math.round(x.top))); }
    return tops.size; }"""

SHOWN = """(sel) => { const e = document.querySelector(sel); if (!e || !e.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return false;
    const r = e.getBoundingClientRect(); return r.height > 0 && r.width > 0 && r.top < innerHeight && r.bottom > 0; }"""


# ================================================================ CHL-NAV-1 phone bottom tab bar
@pytest.mark.parametrize("size", PHONES, ids=PHONE_IDS)
def test_CHL_NAV_1_phone_bottom_bar_has_five_icon_tabs_in_order(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    tabs = pg.locator("nav.tabs [role=tab]")
    assert [t.strip() for t in tabs.all_inner_texts()] == TAB_WORDS, tabs.all_inner_texts()
    assert [tabs.nth(i).get_attribute("data-tab") for i in range(tabs.count())] == TAB_KEYS
    for word in TAB_WORDS:
        expect(pg.get_by_role("tab", name=word, exact=True)).to_have_count(1)
    got = pg.evaluate("""() => { const n = document.querySelector('nav.tabs'), r = n.getBoundingClientRect(), s = getComputedStyle(n);
        return {pos: s.position, t: r.top, b: r.bottom, l: r.left, w: r.width, h: r.height, vw: innerWidth, vh: innerHeight,
          tabs: [...n.querySelectorAll('[role=tab]')].map((t) => { const tr = t.getBoundingClientRect(), svgs = t.querySelectorAll('svg');
            const word = [...t.querySelectorAll('*'), t].find((e) => [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()));
            const sv = svgs[0] && svgs[0].getBoundingClientRect(), wr = word && word.getBoundingClientRect();
            return {t: t.innerText.trim(), w: tr.width, h: tr.height, svgs: svgs.length,
                    hidden: svgs[0] ? svgs[0].getAttribute('aria-hidden') : null,
                    sw: sv ? sv.width : 0, sh: sv ? sv.height : 0, svgBottom: sv ? sv.bottom : 0,
                    wordTop: wr ? wr.top : 0, px: word ? parseFloat(getComputedStyle(word).fontSize) : 0}; })}; }""")
    bad = []
    if got["pos"] != "fixed":
        bad.append(f"nav.tabs position {got['pos']} (want fixed)")
    if abs(got["b"] - got["vh"]) > 1 or got["l"] > 0.5 or got["w"] < got["vw"] - 0.5:
        bad.append(f"bar not pinned full width to the bottom: left {got['l']:.0f}, width {got['w']:.0f}, bottom {got['b']:.0f} of {got['vh']}")
    if got["h"] < 60:
        bad.append(f"bar is {got['h']:.0f}px tall (want >= 60)")
    for t in got["tabs"]:
        if t["w"] < 48 - 0.5:
            bad.append(f"{t['t']}: {t['w']:.0f}px wide (want >= 48)")
        if t["svgs"] != 1 or t["hidden"] != "true":
            bad.append(f"{t['t']}: {t['svgs']} svg icons, aria-hidden={t['hidden']} (want one, aria-hidden=true)")
        if abs(t["sw"] - 26) > 0.5 or abs(t["sh"] - 26) > 0.5:
            bad.append(f"{t['t']}: icon {t['sw']:.1f}x{t['sh']:.1f} (want 26x26)")
        if t["svgBottom"] > t["wordTop"] + 1:
            bad.append(f"{t['t']}: icon not over the word (icon bottom {t['svgBottom']:.0f}, word top {t['wordTop']:.0f})")
        if abs(t["px"] - 17) > 0.1:
            bad.append(f"{t['t']}: word is {t['px']}px (want 17)")
    assert bad == [], f"bottom bar at {size[0]}px:\n" + "\n".join(bad)


# ================================================================ CHL-NAV-2 the picked tab
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_CHL_NAV_2_only_the_picked_tab_is_selected_accent_600_with_an_accent_soft_pill(make_page, site_url, scheme):
    pg = _open(make_page, site_url, PHONE, scheme)
    accent, soft = _color(pg, "var(--accent)"), _color(pg, "var(--accent-soft)")
    calm = {_color(pg, "var(--ink)"), _color(pg, "var(--muted)")}
    bad = []
    for key in TAB_KEYS:
        pg.click(f"nav.tabs [role=tab][data-tab={key}]")
        pg.wait_for_timeout(250)
        st = pg.evaluate("""(soft) => [...document.querySelectorAll('nav.tabs [role=tab]')].map((t) => {
            const word = [...t.querySelectorAll('*'), t].find((e) => [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())) || t;
            const s = getComputedStyle(word);
            return {k: t.dataset.tab, sel: t.getAttribute('aria-selected'), color: s.color, weight: s.fontWeight,
                    pill: [t, ...t.querySelectorAll('*')].some((e) => getComputedStyle(e).backgroundColor === soft)}; })""", soft)
        for t in st:
            if t["k"] == key:
                if t["sel"] != "true" or t["color"] != accent or t["weight"] != "600" or not t["pill"]:
                    bad.append(f"picked {key}: aria-selected={t['sel']} color={t['color']} (accent {accent}) weight={t['weight']} pill={t['pill']}")
            elif t["sel"] == "true" or t["color"] not in calm or t["weight"] not in ("400", "500") or t["pill"]:
                bad.append(f"{key} picked, {t['k']}: aria-selected={t['sel']} color={t['color']} weight={t['weight']} pill={t['pill']}")
    assert bad == [], f"tab states ({scheme}):\n" + "\n".join(bad)


# ================================================================ CHL-NAV-3 the disclaimer line above the bar
@pytest.mark.parametrize("size", PHONES, ids=PHONE_IDS)
def test_CHL_NAV_3_one_40px_disclaimer_line_sits_directly_above_the_bar(make_page, site_url, size):
    """CHL-NAV-3 as amended by the chief of staff (Nov 22): the line is a 48px tap target (design system section 2,
    principle 2 wins over the spec's 40px), exactly 48px tall, one row, full width, directly above the bar."""
    pg = _open(make_page, site_url, size)
    line = pg.locator("#disclaimer-line")
    expect(line).to_be_visible()
    expect(line).to_contain_text(NFA)
    for y in (0, 900):
        pg.evaluate(f"scrollTo(0, {y})")
        pg.wait_for_timeout(100)
        s = _stack(pg)
        assert abs(s["line"]["b"] - s["bar"]["t"]) <= 1, f"scrollY {y}: line bottom {s['line']['b']:.0f} vs bar top {s['bar']['t']:.0f}"
        assert abs(s["line"]["h"] - 48) <= 0.5, f"line is {s['line']['h']:.1f}px tall (want exactly 48, a full tap target)"
    rows = line.evaluate(ROWS)
    clip = line.evaluate("(l) => [l, ...l.querySelectorAll('*')].filter((e) => e.checkVisibility() && (e.scrollWidth > e.clientWidth + 1"
                         " || e.scrollHeight > e.clientHeight + 1)).map((e) => e.tagName + '.' + [...e.classList].join('.'))")
    assert rows == 1 and clip == [], f"line at {size[0]}: {rows} rows, clipped: {clip}"
    btn = line.get_by_role("button").filter(visible=True)
    expect(btn).to_have_count(1)
    b = btn.bounding_box()
    assert abs(b["height"] - 48) <= 0.5 and b["width"] >= size[0] - 0.5, f"line button {b['width']:.0f}x{b['height']:.0f} (want full width, exactly 48 tall)"
    btn.click()
    expect(pg.get_by_text(FULL_TEXT, exact=False).first).to_be_visible()


# ================================================================ CHL-NAV-4 the bottom stack budget, nothing hidden under it
# Amended Nov 22 (chief of staff): the line is 48px (a full tap target), so the budget is 48 line + 64 bar + up to
# 8px rounding = 120 at 390, and 138 at 320 (the spec's 130 plus the same 8px the line grew).
@pytest.mark.parametrize("size,limit", [(PHONE, 120), (SMALL, 138)], ids=["390x844", "320x640"])
def test_CHL_NAV_4_bottom_stack_fits_its_budget(make_page, site_url, size, limit):
    pg = _open(make_page, site_url, size)
    s = _stack(pg)
    h = s["bar"]["b"] - s["top"]
    assert h <= limit, f"line + bar take {h:.0f}px at {size[0]}px (budget {limit})"


LAST_BOTTOM = """() => { const v = document.querySelector('main .tab.active'); let b = 0, who = '';
    for (const e of v.querySelectorAll('*')) { if (!e.checkVisibility() || e.children.length) continue;
      const r = e.getBoundingClientRect(); if (r.height > 0 && r.bottom > b) { b = r.bottom; who = e.tagName + '.' + [...e.classList].join('.'); } }
    return {b, who}; }"""


@pytest.mark.parametrize("size", PHONES, ids=PHONE_IDS)
def test_CHL_NAV_4_nothing_in_any_view_ends_under_the_bottom_stack(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    card = pg.locator("#ideas .card").first
    card.locator("[data-paper]").click()  # a Trades row to check
    expect(pg.locator("#toast")).to_contain_text("Paper trade opened", timeout=ENGINE)
    bad = []
    for view in VIEWS:
        _go(pg, view)
        if view == "paper":
            expect(pg.locator("#paper-list [data-close]").first).to_be_attached(timeout=ENGINE)
        pg.evaluate("scrollTo(0, document.documentElement.scrollHeight)")
        pg.wait_for_timeout(200)
        s, end = _stack(pg), pg.evaluate(LAST_BOTTOM)
        if end["b"] > s["top"] + 0.5:
            bad.append(f"{view}: last content {end['who']} ends at {end['b']:.0f}px, under the stack top {s['top']:.0f}px")
        if view == "chat":
            f = pg.locator("#chat-form").bounding_box()
            if f["y"] + f["height"] > s["top"] - 8:
                bad.append(f"chat: input bottom {f['y'] + f['height']:.0f}px is not 8px above the stack top {s['top']:.0f}px")
    assert bad == [], f"at full scroll, {size[0]}px:\n" + "\n".join(bad)


# ================================================================ CHL-NAV-5 the phone header
STICKY_TOP = """() => Math.max(0, ...[...document.body.querySelectorAll('*')].filter((el) => {
    if (['engine-status', 'toast', 'drawer', 'ack', 'disclaimer-line'].includes(el.id) || el.closest('nav.tabs')) return false;
    const p = getComputedStyle(el).position;
    if (p !== 'sticky' && p !== 'fixed') return false;
    const r = el.getBoundingClientRect();
    return el.checkVisibility() && r.top < 60 && r.height > 0;
}).map((el) => el.getBoundingClientRect().bottom))"""


@pytest.mark.parametrize("size", PHONES, ids=PHONE_IDS)
def test_CHL_NAV_5_phone_header_is_brand_left_profile_right_56px_sticky_no_tagline_no_tabs(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    btn = _profile_button(pg)
    expect(btn).to_be_visible()
    expect(btn).to_have_text(re.compile(r"^\s*Profile\s*$"))
    expect(pg.get_by_text("Invest in what you know", exact=False)).to_have_count(0)
    got = pg.evaluate("""() => { const h = document.querySelector('header'), hr = h.getBoundingClientRect();
        const b = [...h.querySelectorAll('button')].find((x) => x.checkVisibility() && x.innerText.trim() === 'Profile');
        const br = b.getBoundingClientRect(), svg = b.querySelector('svg');
        const brand = [...h.querySelectorAll('*')].find((e) => e.checkVisibility() && [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim() === 'Charlie'));
        const kr = brand ? brand.getBoundingClientRect() : null;
        const tabs = [...document.querySelectorAll('[role=tab]')].filter((t) => { const r = t.getBoundingClientRect();
            return t.checkVisibility() && r.bottom > hr.top && r.top < hr.bottom; }).length;
        return {pos: getComputedStyle(h).position, h: hr.height, mid: hr.left + hr.width / 2,
                brandL: kr ? kr.left : null, brandR: kr ? kr.right : null, bL: br.left, bW: br.width, bH: br.height,
                svg: !!svg && svg.getAttribute('aria-hidden') === 'true', tabs}; }""")
    bad = []
    if got["pos"] not in ("sticky", "fixed"):
        bad.append(f"header position {got['pos']}")
    if got["h"] > 56.5:
        bad.append(f"header {got['h']:.0f}px tall (max 56)")
    if got["brandL"] is None or got["brandR"] > got["mid"]:
        bad.append(f"'Charlie' not on the left half (box {got['brandL']}-{got['brandR']}, mid {got['mid']:.0f})")
    if got["bL"] < got["mid"]:
        bad.append(f"Profile button not on the right (left {got['bL']:.0f})")
    if got["bW"] < 47.5 or got["bH"] < 47.5:
        bad.append(f"Profile target {got['bW']:.0f}x{got['bH']:.0f}")
    if not got["svg"]:
        bad.append("Profile button has no aria-hidden person icon")
    if got["tabs"]:
        bad.append(f"{got['tabs']} tabs sit in the header")
    pg.evaluate("scrollTo(0, 900)")
    pg.wait_for_timeout(150)
    stuck = pg.evaluate(STICKY_TOP)
    if stuck > 56.5:
        bad.append(f"sticky chrome covers {stuck:.0f}px while scrolled (max 56)")
    assert bad == [], f"header at {size[0]}px:\n" + "\n".join(bad)


# ================================================================ CHL-NAV-6 Profile as a sheet-like view
@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])
@pytest.mark.parametrize("how", ["close", "escape"])
def test_CHL_NAV_6_profile_close_or_escape_returns_to_the_last_tab_and_focuses_profile(make_page, site_url, size, how):
    pg = _open(make_page, site_url, size)
    _go(pg, "screener")
    _profile_button(pg).click()
    view = pg.locator("#tab-profile")
    expect(view).to_be_visible()
    expect(view.get_by_role("heading", level=1)).to_have_text("Profile")
    close = view.get_by_role("button", name="Close", exact=True)
    expect(close).to_be_visible()
    if how == "close":
        close.click()
    else:
        pg.keyboard.press("Escape")
    expect(pg.locator("#tab-screener")).to_be_visible()
    expect(view).to_be_hidden()
    expect(pg.get_by_role("tab", name="Search", exact=True)).to_have_attribute("aria-selected", "true")
    assert pg.evaluate("location.hash") == "#screener"
    expect(_profile_button(pg)).to_be_focused()


def test_CHL_NAV_6_profile_hash_on_load_still_opens_profile(make_page, site_url):
    pg = _open(make_page, site_url, PHONE, hash_="#profile")
    view = pg.locator("#tab-profile")
    expect(view).to_be_visible(timeout=ENGINE)
    expect(view.get_by_role("heading", level=1)).to_have_text("Profile")
    expect(view.get_by_role("button", name="Close", exact=True)).to_be_visible()


# ================================================================ CHL-NAV-7 large titles
@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])
def test_CHL_NAV_7_every_view_opens_with_a_34px_large_title(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    bad = []
    for view in VIEWS:
        _go(pg, view)
        got = pg.evaluate("""(id) => { const v = document.getElementById(id);
            const hs = [...v.querySelectorAll('h1')].filter((h) => h.checkVisibility());
            if (hs.length !== 1) return {n: hs.length};
            const h = hs[0], top = h.getBoundingClientRect().top;
            const above = [...v.querySelectorAll('*')].filter((e) => e.checkVisibility() && !h.contains(e) && !e.contains(h)
                && [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()) && e.getBoundingClientRect().bottom <= top + 0.5)
                .map((e) => e.textContent.trim().slice(0, 30));
            return {n: 1, t: h.innerText.trim(), px: getComputedStyle(h).fontSize, above}; }""", f"tab-{view}")
        if got["n"] != 1:
            bad.append(f"{view}: {got['n']} visible h1")
            continue
        if got["t"] != TITLES[view] or got["px"] != "34px":
            bad.append(f"{view}: h1 {got['t']!r} at {got['px']} (want {TITLES[view]!r} at 34px)")
        if got["above"]:
            bad.append(f"{view}: text above the title: {got['above'][:3]}")
    assert bad == [], f"titles at {size[0]}px:\n" + "\n".join(bad)


# ================================================================ CHL-NAV-8 Today's first screen
def test_CHL_NAV_8_today_has_no_pitch_proof_or_top_idea_link_and_card_one_starts_by_500px(make_page, site_url):
    pg = _open(make_page, site_url, PHONE)
    pg.evaluate("scrollTo(0, 0)")
    today = pg.locator("#tab-today")
    bad = []
    if today.get_by_text("Stock ideas from what you already know").filter(visible=True).count():
        bad.append("the hero pitch h1 still shows")
    if today.get_by_role("list", name="What makes Charlie different").filter(visible=True).count():
        bad.append("the proof list still shows")
    if today.get_by_role("link", name=re.compile("top idea", re.I)).filter(visible=True).count() or pg.evaluate(SHOWN, "#hero-top-idea"):
        bad.append("the top-idea link still shows")
    got = pg.evaluate("""() => { const v = document.querySelector('#tab-today');
        const rowsOf = (el) => { const tops = new Set(); const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n;
            while ((n = tw.nextNode())) { if (!n.textContent.trim() || !n.parentElement.checkVisibility()) continue;
              const r = document.createRange(); r.selectNodeContents(n);
              [...r.getClientRects()].filter((x) => x.width > 0).forEach((x) => tops.add(Math.round(x.top))); }
            return tops.size; };
        const h = [...v.querySelectorAll('h1')].find((x) => x.checkVisibility()); if (!h) return null;
        const sub = h.nextElementSibling, hb = h.getBoundingClientRect().bottom;
        const card = document.querySelector('#ideas .card').getBoundingClientRect();
        const r = document.querySelector('input[type=range]'), rt = r ? Math.min(r.getBoundingClientRect().top,
            ...[...r.labels].map((l) => l.getBoundingClientRect().top)) : card.top;
        const stop = Math.min(rt, card.top);
        const between = [...document.querySelectorAll('body *')].filter((e) => e.checkVisibility() && !(sub && sub.contains(e))
            && [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())
            && e.getBoundingClientRect().top >= hb - 0.5 && e.getBoundingClientRect().bottom <= stop + 0.5)
            .map((e) => e.textContent.trim().slice(0, 40));
        return {sub: sub ? sub.innerText.trim() : null, subRows: sub && sub.checkVisibility() ? rowsOf(sub) : 0,
                between, cardTop: card.top}; }""")
    if got is None:
        bad.append("Today has no visible h1")
    else:
        if got["subRows"] != 1:
            bad.append(f"subtitle {got['sub']!r} takes {got['subRows']} rows (want exactly 1)")
        if got["between"]:
            bad.append(f"more than one subtitle line under the title: {got['between'][:4]}")
        if got["cardTop"] > 500:
            bad.append(f"card 1 top at {got['cardTop']:.0f}px (want <= 500)")
    s = _stack(pg)
    m = pg.locator("#ideas .card").first.locator(".hero-m .metric").first.bounding_box()
    if not m or m["y"] + m["height"] > s["top"]:
        bad.append(f"card 1 first hero metric ends at {(m['y'] + m['height']) if m else None}, stack top {s['top']:.0f}")
    assert bad == [], "Today at 390x844:\n" + "\n".join(bad)


# ================================================================ CHL-NAV-9 where the risk slider is
SLIDER = """(id) => { const v = document.getElementById(id);
    const sl = [...document.querySelectorAll('input[type=range]')].filter((e) => e.checkVisibility());
    const h = [...v.querySelectorAll('h1')].find((x) => x.checkVisibility());
    const out = {n: sl.length};
    if (sl.length !== 1 || !h) return out;
    const r = sl[0], row = Math.min(r.getBoundingClientRect().top, ...[...r.labels].map((l) => l.getBoundingClientRect().top));
    const hb = h.getBoundingClientRect().bottom, sub = h.nextElementSibling;
    const own = (e) => [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()) || ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(e.tagName);
    out.row = row; out.hb = hb;
    out.between = [...document.querySelectorAll('body *')].filter((e) => e.checkVisibility() && own(e) && !(sub && sub.contains(e))
        && ![...r.labels].some((l) => l.contains(e)) && e !== r && !e.closest('header, nav, #disclaimer-line, .demo-bar')
        && e.getBoundingClientRect().top >= hb - 0.5 && e.getBoundingClientRect().bottom <= row + 0.5)
        .map((e) => e.tagName + ' ' + (e.textContent || '').trim().slice(0, 30));
    return out; }"""


@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])
def test_CHL_NAV_9_risk_slider_sits_under_the_title_on_today_and_search_only(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    bad = []
    for view in ("today", "screener"):
        _go(pg, view)
        got = pg.evaluate(SLIDER, f"tab-{view}")
        if got["n"] != 1:
            bad.append(f"{view}: {got['n']} visible risk sliders (want 1)")
            continue
        if got["row"] < got["hb"] - 0.5:
            bad.append(f"{view}: the slider ({got['row']:.0f}px) is above the title bottom ({got['hb']:.0f}px)")
        if got["between"]:
            bad.append(f"{view}: between the title and the slider: {got['between'][:4]}")
    for view in ("chat", "paper"):
        _go(pg, view)
        n = pg.evaluate("[...document.querySelectorAll('input[type=range]')].filter((e) => e.checkVisibility()).length")
        if n:
            bad.append(f"{view}: shows {n} risk slider(s) (want none)")
    _go(pg, "learn")
    above = pg.evaluate("""() => { const first = [...document.querySelectorAll('#learn *')].find((e) => e.checkVisibility());
        const ft = first ? first.getBoundingClientRect().top : Infinity;
        return [...document.querySelectorAll('input[type=range]')].filter((e) => e.checkVisibility() && e.getBoundingClientRect().top < ft).length; }""")
    if above:
        bad.append(f"learn: {above} slider(s) above Learn's first content")
    assert bad == [], f"risk slider at {size[0]}px:\n" + "\n".join(bad)


# ================================================================ CHL-NAV-10 ("no": the line stays while typing)
@pytest.mark.parametrize("field", ["chat", "profile", "screener"])
def test_CHL_NAV_10_disclaimer_line_stays_visible_while_a_field_has_focus(make_page, site_url, field):
    """NAV-10 ships as "no" (safe default until Chase answers). The tab bar may hide or not; only the line is checked,
    before focus, while focused, and after blur."""
    pg = _open(make_page, site_url, PHONE)
    sel = {"chat": "#chat-input", "profile": "#resume-text", "screener": "#screen-form input[name=max_capital]"}[field]
    _go(pg, field)
    if field == "screener" and pg.locator("#edit-filters").is_visible():
        pg.click("#edit-filters")
    assert pg.evaluate(SHOWN, "#disclaimer-line"), "precondition: the line shows"
    pg.locator(sel).focus()
    pg.wait_for_timeout(250)
    assert pg.evaluate(SHOWN, "#disclaimer-line"), f"{field} focused: the disclaimer line is hidden while typing"
    assert NFA in pg.locator("#disclaimer-line").inner_text()
    if field == "chat":
        b = pg.locator(sel).bounding_box()
        assert 0 <= b["y"] and b["y"] + b["height"] <= 844, f"chat input at {b['y']:.0f}-{b['y'] + b['height']:.0f} while typing"
    pg.locator(sel).blur()
    pg.wait_for_timeout(250)
    assert pg.evaluate(SHOWN, "#disclaimer-line"), f"{field} blurred: the line is hidden"


# ================================================================ CHL-NAV-11 laptop sidebar
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_CHL_NAV_11_laptop_sidebar_holds_brand_tabs_profile_and_the_disclaimer_line(make_page, site_url, scheme):
    pg = _open(make_page, site_url, DESKTOP, scheme)
    accent, soft = _color(pg, "var(--accent)"), _color(pg, "var(--accent-soft)")
    pg.evaluate("scrollTo(0, 0)")
    got = pg.evaluate("""(soft) => { const vis = (e) => e && e.checkVisibility(), R = (e) => e.getBoundingClientRect();
        const nav = document.querySelector('nav.tabs'), nr = R(nav);
        const tabs = [...nav.querySelectorAll('[role=tab]')].map((t) => { const r = R(t),
            word = [...t.querySelectorAll('*'), t].find((e) => [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())) || t;
            return {t: t.innerText.trim(), sel: t.getAttribute('aria-selected'), top: r.top, bottom: r.bottom, h: r.height, l: r.left, r: r.right,
                    svg: !!t.querySelector('svg[aria-hidden=true]'), color: getComputedStyle(word).color,
                    pill: [t, ...t.querySelectorAll('*')].some((e) => getComputedStyle(e).backgroundColor === soft)}; });
        const brand = [...document.querySelectorAll('body *')].find((e) => vis(e) && [...e.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim() === 'Charlie'));
        const prof = [...document.querySelectorAll('header button')].find((b) => vis(b) && b.innerText.trim() === 'Profile');
        const line = document.querySelector('#disclaimer-line');
        const more = line && [...line.querySelectorAll('button, a')].find((b) => vis(b) && /read more/i.test(b.innerText));
        const wide = [...document.querySelectorAll('body *')].filter((e) => { const p = getComputedStyle(e).position;
            return (p === 'fixed' || p === 'sticky') && vis(e) && R(e).width > innerWidth / 2 && R(e).height > 0
                && !e.closest('#drawer, #ack, #toast, #engine-status'); }).map((e) => e.tagName + '.' + [...e.classList].join('.'));
        const main = R(document.querySelector('main'));
        const box = (e) => e ? (({left, top, right, bottom}) => ({l: left, t: top, r: right, b: bottom}))(R(e)) : null;
        return {nav: {l: nr.left, r: nr.right, w: nr.width, vis: vis(nav)}, tabs, brand: box(brand), prof: box(prof),
                line: vis(line) ? box(line) : null, lineText: line ? line.innerText : '', more: !!more, wide, mainL: main.left}; }""", soft)
    bad = []
    nav = got["nav"]
    if not nav["vis"] or nav["l"] > 0.5 or nav["w"] < 232:
        bad.append(f"sidebar: visible={nav['vis']} left {nav['l']:.0f} width {nav['w']:.0f} (want >= 232 at the left edge)")
    edge = nav["r"] + 1
    ts = got["tabs"]
    if [t["t"] for t in ts] != TAB_WORDS:
        bad.append(f"rows {[t['t'] for t in ts]}")
    for a, b in zip(ts, ts[1:]):
        if b["top"] < a["bottom"] - 0.5:
            bad.append(f"'{b['t']}' is not below '{a['t']}' (rows must stack)")
    for t in ts:
        if abs(t["h"] - 48) > 0.5 or not t["svg"] or t["r"] > edge:
            bad.append(f"'{t['t']}': {t['h']:.0f}px tall, icon={t['svg']}, right {t['r']:.0f}")
        if t["sel"] == "true" and (t["color"] != accent or not t["pill"]):
            bad.append(f"picked '{t['t']}': color {t['color']} (accent {accent}), pill={t['pill']}")
    first, last = ts[0], ts[-1]
    if not got["brand"] or got["brand"]["r"] > edge or got["brand"]["b"] > first["top"] + 0.5:
        bad.append(f"'Charlie' mark not at the sidebar top: {got['brand']}")
    if not got["prof"] or got["prof"]["r"] > edge or got["prof"]["t"] < last["bottom"] - 0.5:
        bad.append(f"Profile row not in the sidebar below the tabs: {got['prof']}")
    ln = got["line"]
    if not ln or ln["r"] > edge or (got["prof"] and ln["t"] < got["prof"]["b"] - 0.5) or NFA not in got["lineText"] or not got["more"]:
        bad.append(f"disclaimer line not at the sidebar bottom with Read more: {ln}, more={got['more']}, text {got['lineText']!r}")
    if got["wide"]:
        bad.append(f"bottom/brand/footer bars still show: {got['wide']}")
    if got["mainL"] < nav["r"] - 0.5:
        bad.append(f"main starts at {got['mainL']:.0f}px, under the sidebar (right {nav['r']:.0f})")
    m = pg.locator("#ideas .card").first.locator(".hero-m .metric").evaluate_all("(ms) => ms.map((e) => e.getBoundingClientRect().bottom)")
    if not m or max(m) > 800:
        bad.append(f"card 1 hero metrics end at {max(m) if m else None}px (want <= 800)")
    assert bad == [], f"sidebar at 1280 ({scheme}):\n" + "\n".join(bad)


# ================================================================ CHL-NAV-12 no sideways scroll on any view
@pytest.mark.parametrize("size", [(320, 640), PHONE, DESKTOP], ids=["320x640", "390x844", "1280x800"])
def test_CHL_NAV_12_no_sideways_scroll_on_any_view(make_page, site_url, size):
    """axe (light and dark, every view) and check_site.py are held by test_demo_e2e::test_every_tab_passes_axe_and_fits
    and tests/test_guardrails.py; this adds 320 and the fixed chrome."""
    pg = _open(make_page, site_url, size)
    wide = []
    for view in VIEWS:
        _go(pg, view)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        if sw > size[0]:
            wide.append(f"{view}: scrollWidth {sw}")
    assert wide == [], f"at {size[0]}px: {wide}"


# ================================================================ CHL-NAV-13 ("no": Chat keeps its page paragraph)
@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390x844", "1280x800"])
def test_CHL_NAV_13_chat_page_keeps_its_paragraph_and_every_reply_ends_with_it(make_page, site_url, size):
    """NAV-13 ships as "no" (safe default until Chase answers). The rendered Chat page shows the exact disclaimer outside
    the conversation log and outside #disclaimer-line, the line still carries it, and a reply ends with it.
    test_demo_e2e::test_chat_panel_and_reply_show_the_disclaimer stays as is."""
    pg = _open(make_page, site_url, size)
    _go(pg, "chat")
    page_copy = pg.evaluate("""(nfa) => [...document.querySelectorAll('#tab-chat *')].filter((e) => e.checkVisibility()
        && !e.closest('#chat-log') && !e.closest('#disclaimer-line') && e.innerText.trim() === nfa).length""", NFA)
    assert page_copy >= 1, "Chat's page-level disclaimer paragraph is not shown"
    line = pg.locator("#disclaimer-line")
    expect(line).to_be_visible()
    assert NFA in line.inner_text(), f"disclaimer line reads {line.inner_text()!r}"
    pg.fill("#chat-input", "Tell me about Visa")
    pg.keyboard.press("Enter")
    reply = pg.locator("#chat-log .msg.bot").last
    expect(reply).to_contain_text(NFA, timeout=ENGINE)
    assert reply.inner_text().strip().endswith(NFA), f"the reply must end with the disclaimer: ...{reply.inner_text()[-80:]!r}"
    pg.locator("#chat-input").blur()
    pg.wait_for_timeout(250)
    expect(line).to_be_visible()


# ================================================================ CHL-NAV-14 one way back to chaseholroyd.com
@pytest.mark.parametrize("size", [(320, 640), PHONE, DESKTOP], ids=["320x640", "390x844", "1280x800"])
def test_CHL_NAV_14_one_visible_way_back_home_the_demo_bar_link(make_page, site_url, size):
    pg = _open(make_page, site_url, size)
    pg.evaluate("scrollTo(0, 0)")
    links = pg.evaluate("""() => [...document.querySelectorAll('a[href^="https://chaseholroyd.com"]')].filter((a) => a.checkVisibility())
        .map((a) => ({t: a.innerText.trim(), bar: !!a.closest('.demo-bar')}))""")
    assert links == [{"t": "← Portfolio", "bar": True}], f"visible links home at {size[0]}: {links}"
    inside = pg.evaluate("""() => [...document.querySelectorAll('nav.tabs a, #disclaimer-line a')].map((a) => a.href)""")
    assert inside == [], f"links in the nav or disclaimer line: {inside}"
    bar = pg.get_by_role("region", name="Demo")
    bar.get_by_role("button", name="Demo details").click()
    expect(bar.get_by_role("link", name="← Back to Chase's portfolio")).to_have_attribute("href", "https://chaseholroyd.com/")
