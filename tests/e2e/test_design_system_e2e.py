"""CHL-DS-6 to DS-19: the studio design core as a visitor sees it, on the built static demo in Chromium.

Spec: the CHL-DS acceptance criteria (Paper theme from hearth main 711fdb8). Written first, red, by qa-tdd on
Nov 21 2026. Fixtures: conftest.py. Runs only with CHARLIE_E2E=1. The unit half is tests/test_design_system.py.

One "sweep" per width (390x844 and 1280x800) walks every place a visitor reads or taps: the ack modal, all five
tabs and the Profile view (CHL-DS-25: Profile left the tab bar for a header button) (with every <details> opened, a paper trade open and a chat reply), the demo bar open and closed (with the
reset question), the Read more dialog and the ticker drawer. DS-7, DS-8, DS-14 and DS-15 read that sweep.
"""
import os
import re

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

NFA = "Not financial advice. Paper trading only."
PHONE = (390, 844)
DESKTOP = (1280, 800)
SIZES = [PHONE, DESKTOP]
SIZE_IDS = ["390x844", "1280x800"]
ENGINE = 120_000  # ms: the first Pyodide start in a cold browser
FAMILY = "Atkinson Hyperlegible Next"
TYPE = {17: 22, 22: 28, 28: 34, 34: 34}  # font size -> line height (STUDIO-CORE section 4)
TARGET = 48
PAPER = {
    "light": {"bg": "#F7F7F4", "ink": "#1E1B17", "accent": "#AD371D"},
    "dark": {"bg": "#131210", "ink": "#F1EEE8", "accent": "#FF8A65"},
}
HC = {"light": {"muted": "#59534B", "line": "#77736C", "tab-line": "#77736C", "accent": "#822F1B", "accent-soft": "#EFE9E5"},
      "dark": {"muted": "#B2ACA2", "line": "#86837E", "tab-line": "#86837E", "accent": "#FBA88C", "accent-soft": "#3D2D26"}}
OLD_WARN = ["#8A5100", "#E3A64A", "#FBF0DC", "#33281A"]
KINDS = ["btn-primary", "btn-tinted", "btn-secondary", "btn-quiet", "btn-danger"]
# DS-14's one exemption: links inside running prose <p>.
PROSE_LINKS = ["#profile-nudge a"]
# DS-15: tabs (the tab bar component) and whole-row targets (section 6 rows) aren't buttons with a kind.
NOT_BUTTON_KINDS = "[role=tab], .row-card, .demo-bar__toggle"


# CHL-DS-25 (Chase, Nov 22): five tabs, in this order; Profile opens from a header button, not a tab.
# CHL-NAV-1 (Chase, Nov 22): the visible words are now Today, Search, Chat, Trades, Learn (ids and data-tab unchanged).
TAB_NAMES = ["Today", "Search", "Chat", "Trades", "Learn"]
VIEWS = ["today", "profile", "screener", "chat", "paper", "learn"]  # every view a visitor can open


def _profile_button(pg):
    """CHL-DS-25: the header button whose visible word is Profile."""
    return pg.locator("header").get_by_role("button", name=re.compile(r"\bProfile\b"))


def _go(pg, view):
    """Open a view the way a visitor does: a tab, or the header Profile button for Profile."""
    if view == "profile":
        _profile_button(pg).click()
        expect(pg.locator("#tab-profile")).to_be_visible()
    else:
        pg.click(f"[role=tab][data-tab={view}]")


def _rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def _new(browser, site_url, size, scheme="light", contrast=None):
    kw = {"viewport": {"width": size[0], "height": size[1]}, "color_scheme": scheme}
    if contrast:
        kw["contrast"] = contrast
    ctx = browser.new_context(**kw)
    pg = ctx.new_page()
    pg.errors, pg.console_csp = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.console_csp.append(m.text) if "Content Security Policy" in m.text else None)
    return ctx, pg


def _ready(pg, ack=True):
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    if ack:
        pg.click("#ack-btn")


def _booted_on(pg, tab):
    """After a reload the app reopens the tab in location.hash (boot -> showTab), so a reload taken on
    Profile comes back on Profile, not Today. Booted = boot() made that tab active (only Today is active
    in the static HTML) and it is visible."""
    assert pg.evaluate("location.hash") == f"#{tab}"
    expect(pg.locator(f"#tab-{tab}.active")).to_be_visible(timeout=ENGINE)


def _engine_idle(pg):
    pg.wait_for_timeout(200)
    pg.wait_for_function("document.querySelector('#engine-status').classList.contains('hidden')", timeout=ENGINE)


def _color(pg, expr):
    return pg.evaluate("""(v) => { const i = document.createElement('i'); i.style.color = v;
        document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; }""", expr)


# ---------------------------------------------------------------- the sweep
COLLECT = r"""([scope, prose, notKinds]) => {
  const root = scope ? document.querySelector(scope) : document.body;
  const vis = (el) => el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}) && !el.closest('.sr-only');
  const name = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
      [...el.classList].slice(0, 3).map((c) => '.' + c).join('');
  const where = (el) => { const t = el.closest('.tab, #drawer, #ack, .demo-bar, #disclaimer-line, footer, header, nav');
      return (t ? name(t) + ' ' : '') + name(el); };
  const text = [];
  const seen = new Set();
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = tw.nextNode())) {
    const el = n.parentElement;
    if (!n.textContent.trim() || !el || seen.has(el) || ['SCRIPT', 'STYLE', 'OPTION', 'TITLE'].includes(el.tagName)) continue;
    if (!vis(el)) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    if (![...r.getClientRects()].some((x) => x.width > 0 && x.height > 0)) continue;
    seen.add(el);
    const s = getComputedStyle(el);
    let px = parseFloat(s.fontSize), svg = el instanceof SVGElement;
    if (svg) { const m = el.getScreenCTM(); px *= m ? Math.hypot(m.a, m.b) : 1; }
    text.push({where: where(el), text: n.textContent.trim().slice(0, 40), px, lh: s.lineHeight, svg,
               weight: s.fontWeight, style: s.fontStyle, transform: s.textTransform, ls: s.letterSpacing});
  }
  for (const el of root.querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([type=range]):not([type=hidden]):not([type=file]), select, textarea')) {
    if (!vis(el)) continue;
    const s = getComputedStyle(el);
    text.push({where: where(el), text: (el.value || el.placeholder || '').slice(0, 40), px: parseFloat(s.fontSize), lh: s.lineHeight,
               svg: false, weight: s.fontWeight, style: s.fontStyle, transform: s.textTransform, ls: s.letterSpacing});
  }
  const SEL = 'button, a, [role=tab], summary, select, input, label:has(input[type=checkbox]), label:has(input[type=radio])';
  const exempt = new Set(prose.flatMap((p) => [...document.querySelectorAll(p)]));
  const targets = [...root.querySelectorAll(SEL)].filter((el) => vis(el) && !exempt.has(el)
      && !(el.matches('input[type=checkbox], input[type=radio]') && el.closest('label'))
      && !(el.matches('input[type=hidden]'))).map((el) => {
    const r = el.getBoundingClientRect();
    let fixed = false;
    for (let p = el; p; p = p.parentElement) { const pos = getComputedStyle(p).position; if (pos === 'fixed' || pos === 'sticky') { fixed = true; break; } }
    // The part you can see: clipped by any scrolling or overflow-hidden ancestor (e.g. the chat log).
    let [L, T, R, B] = [r.left, r.top, r.right, r.bottom];
    for (let p = el.parentElement; p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
      const q = getComputedStyle(p);
      if (/auto|scroll|hidden|clip/.test(q.overflowX + ' ' + q.overflowY)) {
        const c = p.getBoundingClientRect();
        [L, T, R, B] = [Math.max(L, c.left), Math.max(T, c.top), Math.min(R, c.right), Math.min(B, c.bottom)];
      }
    }
    const dx = fixed ? 0 : scrollX, dy = fixed ? 0 : scrollY;
    return {where: where(el), text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 30),
            w: r.width, h: r.height, fixed, cx: L + dx, cy: T + dy, cw: Math.max(0, R - L), ch: Math.max(0, B - T),
            id: (el.dataset.qaId = el.dataset.qaId || Math.random().toString(36).slice(2))};
  });
  const nested = targets.map((t) => [...document.querySelectorAll(`[data-qa-id="${t.id}"] [data-qa-id]`)].map((e) => e.dataset.qaId));
  targets.forEach((t, i) => { t.inside = nested[i]; });
  const buttons = [...root.querySelectorAll('button')].filter((b) => vis(b) && !b.matches(notKinds)).map((b) => {
    const s = getComputedStyle(b);
    return {where: where(b), text: (b.innerText || b.getAttribute('aria-label') || '').trim().slice(0, 30),
            kinds: [...b.classList].filter((c) => c.startsWith('btn-')), bg: s.backgroundColor, color: s.color,
            radius: parseFloat(s.borderTopLeftRadius), h: b.getBoundingClientRect().height,
            group: (b.closest('.tab, #drawer, #ack') || {}).id || 'chrome'};
  });
  return {text, targets, buttons};
}"""


def _collect(pg, state, scope=None):
    got = pg.evaluate(COLLECT, [scope, PROSE_LINKS, NOT_BUTTON_KINDS])
    for k in got:
        for x in got[k]:
            x["state"] = state
    return got


def _open_all_details(pg, scope):
    pg.evaluate("(s) => document.querySelectorAll(s + ' details').forEach((d) => { d.open = true; })", scope)
    pg.wait_for_timeout(100)


def _sweep(browser, site_url, size):
    ctx, pg = _new(browser, site_url, size)
    out = {"text": [], "targets": [], "buttons": [], "errors": []}

    def add(got):
        for k in ("text", "targets", "buttons"):
            out[k] += got[k]
    try:
        pg.goto(site_url)
        _ready(pg, ack=False)
        _open_all_details(pg, "#ack")
        add(_collect(pg, "ack modal", "#ack"))
        pg.click("#ack-btn")
        card = pg.locator("#ideas .card").first
        card.locator("[data-paper]").click()
        expect(pg.locator("#toast")).to_contain_text("Paper trade opened", timeout=ENGINE)
        for tab in VIEWS:
            _go(pg, tab)
            _engine_idle(pg)
            if tab == "screener":
                expect(pg.locator("#screen-results [data-row]").first).to_be_attached(timeout=ENGINE)
                if pg.locator("#edit-filters").is_visible():
                    pg.click("#edit-filters")
            if tab == "chat":
                pg.locator("#chat-log .chip").first.click()
                expect(pg.locator("#chat-log .msg.bot").last).to_contain_text(NFA, timeout=ENGINE)
            if tab == "paper":
                expect(pg.locator("#paper-list [data-close]").first).to_be_attached(timeout=ENGINE)
            _open_all_details(pg, f"#tab-{tab}")
            pg.evaluate("scrollTo(0, 0)")
            add(_collect(pg, f"tab {tab}"))
            if tab == "profile":  # fix round 1: the inline delete confirm (CHL-DS-R2) is a screen of its own
                pg.click("#delete-profile")
                expect(pg.locator("#delete-confirm")).to_be_visible()
                add(_collect(pg, "tab profile, delete confirm open"))
                pg.click("#delete-no")
                expect(pg.locator("#delete-confirm")).to_be_hidden()
        pg.click("[data-tab=today]")
        bar = pg.get_by_role("region", name="Demo")
        bar.get_by_role("button", name="Demo details").click()
        bar.get_by_role("button", name="Reset demo").click()
        add(_collect(pg, "demo bar open, reset question", "section.demo-bar"))
        bar.get_by_role("button", name="Keep").click()
        add(_collect(pg, "demo bar open", "section.demo-bar"))
        bar.get_by_role("button", name="Demo details").click()
        # CHL-NAV-3/11: the phone line is itself the button; the laptop sidebar line has Read more.
        line = pg.locator("#disclaimer-line")
        if size[0] < 760:
            line.get_by_role("button").filter(visible=True).first.click()
        else:
            line.get_by_role("button", name=re.compile("read more", re.I)).click()
        expect(pg.locator("#ack")).to_be_visible()
        _open_all_details(pg, "#ack")
        add(_collect(pg, "read more dialog", "#ack"))
        pg.click("#ack-btn")
        pg.locator("#ideas .card [data-ticker]").first.click()
        expect(pg.locator("#drawer svg.payoff").first).to_be_visible(timeout=ENGINE)
        _engine_idle(pg)
        _open_all_details(pg, "#drawer")
        add(_collect(pg, "drawer", "#drawer"))
        out["errors"] = list(pg.errors)
    finally:
        ctx.close()
    return out


@pytest.fixture(scope="module")
def sweeps(browser, site_url):
    return {size: _sweep(browser, site_url, size) for size in SIZES}


# ---------------------------------------------------------------- CHL-DS-6 the font loads, from this site
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_6_atkinson_loads_same_origin_with_no_csp_violation(browser, site_url, size):
    ctx, pg = _new(browser, site_url, size)
    try:
        fonts = []
        pg.on("request", lambda r: fonts.append(r.url) if r.resource_type == "font" or r.url.endswith(".woff2") else None)
        pg.add_init_script("window.__csp = []; document.addEventListener('securitypolicyviolation', "
                           "(e) => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));")
        pg.goto(site_url)
        _ready(pg)
        got = pg.evaluate(f"""async () => {{
            await document.fonts.ready;
            const r400 = await document.fonts.load('17px "{FAMILY}"');
            const r600 = await document.fonts.load('600 17px "{FAMILY}"');
            return {{c400: document.fonts.check('17px "{FAMILY}"'), c600: document.fonts.check('600 17px "{FAMILY}"'),
                     l400: r400.map((f) => f.family + ' ' + f.weight + ' ' + f.status),
                     l600: r600.map((f) => f.family + ' ' + f.weight + ' ' + f.status),
                     body: getComputedStyle(document.body).fontFamily, csp: window.__csp}}; }}""")
        assert got["l400"] and all(x.endswith("loaded") and "400" in x for x in got["l400"]), got
        assert got["l600"] and all(x.endswith("loaded") and "600" in x for x in got["l600"]), got
        assert got["c400"] and got["c600"], got
        assert got["body"].split(",")[0].strip().strip('"') == FAMILY, got["body"]
        origin = site_url.rsplit("/", 1)[0] + "/"
        assert fonts and all(u.startswith(origin) for u in fonts), f"font requests: {fonts}"
        assert got["csp"] == [] and pg.console_csp == [], (got["csp"], pg.console_csp)
        assert pg.errors == []
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-DS-7 17px floor, studio sizes, line heights
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_7_every_visible_text_is_a_studio_size_with_its_line_height(sweeps, size):
    s = sweeps[size]
    assert s["text"], "the sweep found no text"
    bad = []
    for x in s["text"]:
        tol = 0.5 if x["svg"] else 0.25
        sz = next((k for k in TYPE if abs(x["px"] - k) <= tol), None)
        if sz is None:
            bad.append(f"{x['state']}: {x['where']} '{x['text']}' {x['px']:.2f}px")
            continue
        if not x["svg"]:
            lh = float(x["lh"][:-2]) if x["lh"].endswith("px") else None
            if lh is None or abs(lh - TYPE[sz]) > 0.5:
                bad.append(f"{x['state']}: {x['where']} '{x['text']}' {sz}px with line-height {x['lh']} (want {TYPE[sz]}px)")
    assert bad == [], f"{len(bad)} text runs off the studio type ramp at {size[0]}px:\n" + "\n".join(sorted(set(bad))[:60])


# ---------------------------------------------------------------- CHL-DS-8 weights, no italics, no caps
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_8_weights_400_500_600_no_italics_caps_or_letter_spacing(sweeps, size):
    bad = []
    for x in sweeps[size]["text"]:
        why = []
        if x["weight"] not in ("400", "500", "600"):
            why.append(f"weight {x['weight']}")
        if x["style"] != "normal":
            why.append(x["style"])
        if x["transform"] != "none":
            why.append(f"text-transform {x['transform']}")
        if x["ls"] not in ("normal", "0px"):
            why.append(f"letter-spacing {x['ls']}")
        if why:
            bad.append(f"{x['state']}: {x['where']} '{x['text']}' {', '.join(why)}")
    assert bad == [], f"{len(bad)} text runs break the weight/style rules at {size[0]}px:\n" + "\n".join(sorted(set(bad))[:60])


# ---------------------------------------------------------------- CHL-DS-9 text grows with the browser's text size
def test_CHL_DS_9_raising_the_root_size_grows_the_text(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    pg.evaluate("document.documentElement.style.fontSize = '20px'")
    pg.wait_for_timeout(300)
    body = float(pg.evaluate("getComputedStyle(document.body).fontSize")[:-2])
    assert body >= 21, f"body text is {body}px with a 20px root (want >= 21: sizes in rem)"
    small = pg.evaluate("""() => [...document.querySelectorAll('#tab-today *, header *, nav *, footer *, #disclaimer-line *')]
        .filter((el) => el.checkVisibility() && !el.closest('.sr-only') && [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
        .map((el) => { const m = el instanceof SVGElement ? el.getScreenCTM() : null;
            return {t: el.textContent.trim().slice(0, 30), px: parseFloat(getComputedStyle(el).fontSize) * (m ? Math.hypot(m.a, m.b) : 1)}; })
        .filter((x) => x.px < 20.75)""")
    assert small == [], f"text that didn't grow with the root size (px, not rem): {small[:20]}"


# ---------------------------------------------------------------- CHL-DS-11 no shadows
SHADOWS = """() => [...document.querySelectorAll('*')].flatMap((el) => ['', '::before', '::after'].map((p) => {
    const s = getComputedStyle(el, p || null);
    return (s.boxShadow !== 'none' || s.textShadow !== 'none') ? `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}.${[...el.classList].join('.')}${p}: ${s.boxShadow} / ${s.textShadow}` : null;
})).filter(Boolean)"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_11_no_box_or_text_shadow_anywhere(browser, site_url, size, scheme):
    ctx, pg = _new(browser, site_url, size, scheme)
    try:
        pg.goto(site_url)
        _ready(pg, ack=False)
        found = pg.evaluate(SHADOWS)
        pg.click("#ack-btn")
        pg.locator("#ideas .card [data-ticker]").first.click()
        expect(pg.locator("#drawer svg.payoff").first).to_be_visible(timeout=ENGINE)
        found += pg.evaluate(SHADOWS)
        assert sorted(set(found)) == [], f"shadows at {size[0]} {scheme}: {sorted(set(found))[:20]}"
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-DS-12 no card in a card
FILLED = r"""(roots) => roots.flatMap((sel) => [...document.querySelectorAll(sel)].filter((r) => r.checkVisibility()).flatMap((root) =>
  [...root.querySelectorAll('*')].filter((el) => {
    if (!el.checkVisibility() || el.closest('svg, .chart, button, input, select, textarea, .sr-only')) return false;
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    const painted = s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'transparent' || s.backgroundImage !== 'none';
    if (!painted) return false;
    const pill = parseFloat(s.borderTopLeftRadius) >= 999 || parseFloat(s.borderTopLeftRadius) >= r.height / 2 - 0.5;
    return !pill;
  }).map((el) => `${sel} > ${el.tagName.toLowerCase()}.${[...el.classList].join('.')} (${getComputedStyle(el).backgroundColor})`)))"""


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_12_content_inside_cards_hero_stats_and_drawer_sits_on_the_page(browser, site_url, size):
    ctx, pg = _new(browser, site_url, size)
    try:
        pg.goto(site_url)
        _ready(pg)
        pg.locator("#ideas .card").first.locator("[data-paper]").click()
        expect(pg.locator("#toast")).to_contain_text("Paper trade opened", timeout=ENGINE)
        _open_all_details(pg, "#ideas")
        found = pg.evaluate(FILLED, ["#ideas .card", ".hero"])
        pg.click("[data-tab=paper]")
        expect(pg.locator("#paper-stats .metric").first).to_be_visible(timeout=ENGINE)
        found += pg.evaluate(FILLED, ["#paper-stats", ".pos-card"])
        pg.click("[data-tab=today]")
        pg.locator("#ideas .card [data-ticker]").first.click()
        expect(pg.locator("#drawer svg.payoff").first).to_be_visible(timeout=ENGINE)
        _engine_idle(pg)
        _open_all_details(pg, "#drawer")
        found += pg.evaluate(FILLED, ["#drawer-body"])
        assert sorted(set(found)) == [], f"filled boxes inside a card/sheet at {size[0]}: {sorted(set(found))[:25]}"
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-DS-13 no amber; caution words stay; no decorative accent
CAUTION = [  # (selector as rendered by app.js, markup injected so every caution style is checked)
    (".badge.mock", '<span class="badge mock">Sample</span>'),
    (".pill.l4", '<span class="pill l4">Growth</span>'),
    (".pill.l5", '<span class="pill l5">Speculative</span>'),
    (".grade.C", '<span class="grade C"><span class="gscore">Score 55 · C</span></span>'),
    (".grade.D", '<span class="grade D"><span class="gscore">Score 45 · D</span></span>'),
    (".callout", '<div class="callout small">Charlie doesn\'t cover ZZZZ yet.</div>'),
    (".be-chip.below", '<span class="be-chip below">Below breakeven <span class="num">$12.00</span></span>'),
    (".alert-chip", '<span class="alert-chip" data-alert="time">Near expiry</span>'),
    (".rung.l4 .n", '<div class="ladder"><div class="rung l4"><div class="n">4</div><div><b>Growth</b></div></div></div>'),
    (".rung.l5 .n", '<div class="ladder"><div class="rung l5"><div class="n">5</div><div><b>Speculative</b></div></div></div>'),
]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_CHL_DS_13_caution_elements_keep_their_word_in_ink_or_danger_text_never_amber(browser, site_url, scheme):
    ctx, pg = _new(browser, site_url, DESKTOP, scheme)
    try:
        pg.goto(site_url)
        _ready(pg)
        ink, danger = _color(pg, "var(--ink)"), _color(pg, "var(--danger-text)")
        pg.evaluate("(html) => { const d = document.createElement('div'); d.id = 'qa-caution'; d.innerHTML = html;"
                    " document.querySelector('#tab-today').prepend(d); }", "".join(h for _, h in CAUTION))
        bad = []
        for sel, _ in CAUTION:
            got = pg.locator(f"#qa-caution {sel}").first.evaluate(
                "(e) => ({t: e.innerText.trim(), c: getComputedStyle(e).color})")
            if not got["t"]:
                bad.append(f"{sel}: no word")
            if got["c"] not in (ink, danger):
                bad.append(f"{sel}: color {got['c']}, want ink {ink} or dangerText {danger}")
        pg.click("[data-tab=learn]")
        _engine_idle(pg)
        warn = [_rgb(c) for c in OLD_WARN]
        amber = pg.evaluate("""(warn) => [...document.querySelectorAll('*')].flatMap((el) => { const s = getComputedStyle(el);
            return ['color', 'backgroundColor', 'borderTopColor', 'borderBottomColor', 'borderLeftColor', 'borderRightColor', 'outlineColor', 'fill', 'stroke']
              .filter((p) => warn.includes(s[p])).map((p) => `${el.tagName.toLowerCase()}.${[...el.classList].join('.')} ${p}`); })""", warn)
        assert bad == [] and amber == [], {"caution": bad, "amber": amber[:20]}
    finally:
        ctx.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_CHL_DS_13_the_accent_only_marks_things_you_can_tap(browser, site_url, scheme):
    """Principle 6: the logo isn't accent-filled, and no other non-tappable element wears the accent
    (text, fill or the accent-soft tint). Outlines and borders (focus, the picked tab or rung) are allowed."""
    ctx, pg = _new(browser, site_url, DESKTOP, scheme)
    try:
        pg.goto(site_url)
        _ready(pg)
        accent, soft = _color(pg, "var(--accent)"), _color(pg, "var(--accent-soft)")
        logo = pg.locator("header .logo").evaluate("(e) => getComputedStyle(e).backgroundColor")
        assert logo != accent, "the logo is accent-filled (decoration)"
        found = []
        for tab in ["today", "profile", "screener", "paper", "learn"]:
            _go(pg, tab)
            _engine_idle(pg)
            found += pg.evaluate("""([accent, soft]) => [...document.querySelectorAll('body *')].filter((el) => {
                if (!el.checkVisibility() || el.closest('svg, .chart, .sr-only')) return false;
                if (el.closest('a, button, summary, label, select, input, [role=tab]')) return false;
                const s = getComputedStyle(el);
                const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
                return (own && s.color === accent) || [accent, soft].includes(s.backgroundColor)
                    || /gradient/.test(s.backgroundImage);
            }).map((el) => `${el.tagName.toLowerCase()}.${[...el.classList].join('.')} '${(el.innerText || '').trim().slice(0, 30)}'`)""",
                                 [accent, soft])
        assert sorted(set(found)) == [], f"accent used as decoration ({scheme}): {sorted(set(found))[:25]}"
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-DS-14 every target 48x48, none overlapping
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_14_every_tap_target_is_at_least_48_by_48(sweeps, size):
    small = sorted({f"{t['state']}: {t['where']} '{t['text']}' {t['w']:.0f}x{t['h']:.0f}"
                    for t in sweeps[size]["targets"] if t["w"] < TARGET - 0.5 or t["h"] < TARGET - 0.5})
    assert small == [], f"{len(small)} targets under 48x48 at {size[0]}px:\n" + "\n".join(small[:60])


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_14_no_two_tap_targets_overlap(sweeps, size):
    by_state = {}
    for t in sweeps[size]["targets"]:
        by_state.setdefault(t["state"], []).append(t)
    hits = set()
    for state, ts in by_state.items():
        for i, a in enumerate(ts):
            for b in ts[i + 1:]:
                if a["fixed"] != b["fixed"] or b["id"] in a["inside"] or a["id"] in b["inside"]:
                    continue
                if not (a["cw"] and a["ch"] and b["cw"] and b["ch"]):
                    continue  # scrolled out of its container: not tappable right now
                ox = min(a["cx"] + a["cw"], b["cx"] + b["cw"]) - max(a["cx"], b["cx"])
                oy = min(a["cy"] + a["ch"], b["cy"] + b["ch"]) - max(a["cy"], b["cy"])
                if ox > 0.5 and oy > 0.5:
                    hits.add(f"{state}: '{a['text']}' ({a['where']}) overlaps '{b['text']}' ({b['where']})")
    assert sorted(hits) == [], f"{len(hits)} overlapping targets at {size[0]}px:\n" + "\n".join(sorted(hits)[:40])


# ---------------------------------------------------------------- CHL-DS-15 one kind per button, colors match
def _kind_colors(pg_colors):
    c = pg_colors
    return {"btn-primary": (c["accent"], c["accent-ink"]), "btn-tinted": (c["accent-soft"], c["accent"]),
            "btn-secondary": (c["fill"], c["ink"]), "btn-quiet": ("rgba(0, 0, 0, 0)", c["accent"]),
            "btn-danger": (c["danger"], c["on-danger"])}


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_15_every_button_has_one_kind_and_at_most_one_primary_and_tinted_per_screen(browser, site_url, sweeps, size):
    ctx, pg = _new(browser, site_url, size)
    try:
        pg.goto(site_url)
        _ready(pg)
        colors = {k: _color(pg, f"var(--{k})") for k in
                  ("accent", "accent-ink", "accent-soft", "fill", "ink", "danger", "on-danger", "danger-text")}
    finally:
        ctx.close()
    want = _kind_colors(colors)
    bad, per_screen = [], {}
    for b in sweeps[size]["buttons"]:
        label = f"{b['state']}: {b['where']} '{b['text']}'"
        if len(b["kinds"]) != 1 or b["kinds"][0] not in want:
            bad.append(f"{label} kinds {b['kinds']}")
            continue
        k = b["kinds"][0]
        # Chief of staff, Nov 22: the disclaimer line (#disclaimer-line, and its Read more in the laptop sidebar) is a
        # settings-style row / navigation item, so like the tabs it is exempt from the kind's colors; it must still
        # be exactly one kind (checked above) and a 48px target.
        if "#disclaimer-line" in b["where"].split(" ")[0]:
            if b["h"] < 47.5:
                bad.append(f"{label} the disclaimer line button is {b['h']:.1f}px tall (want 48)")
            continue
        bg, fg = want[k]
        # Fix round 1 (CHL-DS-R2): the one exception. The quiet trigger that opens the inline delete confirm names
        # a destructive action, so it may use --danger-text; the filled danger is on the confirm (#delete-yes).
        if k == "btn-quiet" and b["where"].endswith("button#delete-profile.btn-quiet.danger-text"):
            fg = colors["danger-text"]
        # Nov 22 (chief of staff, CHL-DS-R25/R26): the header Profile button is a navigation item, the sixth
        # view's tab, and section 6 exempts tabs from the kind colour rule. So its text colour is exempt here only;
        # R25/R26 assert it (inactive tab colour at rest, accent while Profile shows). Its background, its one kind
        # and its 48px target (DS-14, DS-25) are still checked.
        if k == "btn-quiet" and "button#profile-btn." in b["where"]:
            fg = b["color"]
        if b["bg"] != bg or b["color"] != fg:
            bad.append(f"{label} {k}: bg {b['bg']} color {b['color']}, want bg {bg} color {fg}")
        if k == "btn-tinted" and b["radius"] < min(999, b["h"] / 2 - 0.5):
            bad.append(f"{label} btn-tinted is a capsule (pill radius), radius {b['radius']}")
        if k in ("btn-primary", "btn-tinted"):
            per_screen.setdefault((b["state"], b["group"], k), set()).add(b["text"])
    many = [f"{s} / {g}: {len(t)} {k} buttons {sorted(t)}" for (s, g, k), t in per_screen.items() if len(t) > 1]
    confirm = [b for b in sweeps[size]["buttons"] if b["state"] == "tab profile, delete confirm open" and "#delete-yes" in b["where"]]
    if not (len(confirm) == 1 and confirm[0]["kinds"] == ["btn-danger"] and confirm[0]["text"] == "Delete my data"):
        bad.append(f"the delete confirm's 'Delete my data' (#delete-yes) must be the one btn-danger, got {confirm}")
    if not any("#disclaimer-line" in b["where"].split(" ")[0] for b in sweeps[size]["buttons"]):
        bad.append("no visible button in #disclaimer-line in any swept state (the exemption must not hide a missing line)")
    triggers = [b for b in sweeps[size]["buttons"] if "#delete-profile" in b["where"]]
    if not triggers or any(b["kinds"] != ["btn-quiet"] for b in triggers):
        bad.append(f"#delete-profile must be a btn-quiet trigger, got {triggers}")
    nav = [b for b in sweeps[size]["buttons"] if "button#profile-btn." in b["where"]]
    if not nav or any(len(b["kinds"]) != 1 for b in nav):
        bad.append(f"#profile-btn must carry exactly one kind class, got {[(b['state'], b['kinds']) for b in nav]}")
    assert bad == [] and many == [], {"kinds": bad[:40], "more than one per screen": many}


# ---------------------------------------------------------------- CHL-DS-16 focus ring: 2px accent, no shift
TAB_STEP = """() => { const el = document.activeElement; if (!el || el === document.body) return null;
    const s = getComputedStyle(el);
    const fixed = (() => { for (let p = el; p; p = p.parentElement) { const q = getComputedStyle(p).position; if (q === 'fixed' || q === 'sticky') return true; } return false; })();
    const box = (e) => { const r = e.getBoundingClientRect(); return [r.left + scrollX, r.top + scrollY, r.width, r.height].map((v) => Math.round(v * 10) / 10); };
    return {name: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + '.' + [...el.classList].join('.') + " '" + (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 25) + "'",
            qa: el.dataset.qaFocus, style: s.outlineStyle, width: s.outlineWidth, color: s.outlineColor, shadow: s.boxShadow, fixed,
            boxes: [el, ...(el.parentElement ? el.parentElement.children : [])].map(box)}; }"""


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_16_keyboard_focus_is_a_2px_accent_ring_that_moves_nothing(browser, site_url, size):
    ctx, pg = _new(browser, site_url, size)
    try:
        pg.goto(site_url)
        _ready(pg)
        accent = _color(pg, "var(--accent)")
        pg.get_by_role("region", name="Demo").get_by_role("button", name="Demo details").click()
        pg.evaluate("document.activeElement.blur(); scrollTo(0, 0)")
        rest = pg.evaluate("""() => { const box = (e) => { const r = e.getBoundingClientRect();
            return [r.left + scrollX, r.top + scrollY, r.width, r.height].map((v) => Math.round(v * 10) / 10); };
            const out = {}; document.querySelectorAll('a, button, input, select, textarea, summary, [tabindex]').forEach((e, i) => {
              e.dataset.qaFocus = i; out[i] = [e, ...(e.parentElement ? e.parentElement.children : [])].map(box); }); return out; }""")
        bad, seen = [], 0
        pg.focus("section.demo-bar a")
        pg.keyboard.press("Shift+Tab")
        for _ in range(60):
            pg.keyboard.press("Tab")
            got = pg.evaluate(TAB_STEP)
            if not got:
                continue
            seen += 1
            if got["style"] != "solid" or got["width"] != "2px" or got["color"] != accent:
                bad.append(f"{got['name']}: outline {got['style']} {got['width']} {got['color']} (want solid 2px {accent})")
            if got["shadow"] != "none":
                bad.append(f"{got['name']}: box-shadow {got['shadow']} on focus")
            # Compare with the layout at rest, after undoing the scroll the focus caused (fixed/sticky skipped).
            if not got["fixed"] and got["qa"] is not None and got["qa"] in rest:
                before = rest[got["qa"]]
                if before != got["boxes"]:
                    # the page may have scrolled: compare sizes only, and positions relative to the element
                    rel = lambda bs: [(round(b[0] - bs[0][0], 1), round(b[1] - bs[0][1], 1), b[2], b[3]) for b in bs]  # noqa: E731
                    if rel(before) != rel(got["boxes"]):
                        bad.append(f"{got['name']}: focusing moved it or its siblings")
        assert seen >= 20, f"only {seen} elements took keyboard focus"
        assert bad == [], "\n".join(sorted(set(bad))[:40])
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-DS-17 Appearance: Auto / Light / Dark
def _profile(pg):
    _go(pg, "profile")
    return pg.get_by_role("group", name="Appearance")


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_CHL_DS_17_profile_has_an_appearance_choice_auto_by_default(make_page, site_url, size):
    pg = make_page(*size)
    pg.goto(site_url)
    _ready(pg)
    group = _profile(pg)
    expect(group).to_be_visible()
    assert group.evaluate("(g) => g.tagName") == "FIELDSET"
    radios = group.get_by_role("radio")
    expect(radios).to_have_count(3)
    assert [r.evaluate("(r) => r.labels[0].innerText.trim()") for r in radios.all()] == ["Match device", "Light", "Dark"]
    expect(group.get_by_role("radio", name="Match device")).to_be_checked()
    for name in ("Match device", "Light", "Dark"):
        r = group.get_by_role("radio", name=name)
        assert r.evaluate("(r) => r.type") == "radio", "native radios"
        box = r.evaluate("(r) => { const b = r.labels[0].getBoundingClientRect(); return [b.width, b.height]; }")
        assert box[0] >= TARGET and box[1] >= TARGET, f"{name} is {box[0]:.0f}x{box[1]:.0f}"


# ---------------------------------------------------------------- CHL-DS-18 the choice sticks, before first paint
FIRST_PAINT = """window.__firstTheme = 'unset';
new MutationObserver((ms, o) => { if (document.body) { window.__firstTheme = document.documentElement.getAttribute('data-theme'); o.disconnect(); } })
  .observe(document, {childList: true, subtree: true});"""


def _bg(pg):
    return pg.evaluate("getComputedStyle(document.body).backgroundColor")


@pytest.mark.parametrize("os_scheme,pick,other", [("dark", "Light", "light"), ("light", "Dark", "dark")])
def test_CHL_DS_18_light_or_dark_overrides_the_os_and_survives_reload(make_page, site_url, os_scheme, pick, other):
    pg = make_page(*PHONE, scheme=os_scheme)
    pg.add_init_script(FIRST_PAINT)
    pg.goto(site_url)
    _ready(pg)
    assert _bg(pg) == _rgb(PAPER[os_scheme]["bg"]), "Auto follows the OS"
    _profile(pg).get_by_role("radio", name=pick).check()
    expect(pg.locator(f"html[data-theme={other}]")).to_have_count(1)
    assert _bg(pg) == _rgb(PAPER[other]["bg"])
    assert pg.evaluate("localStorage.getItem('charlie-appearance')") == other
    pg.reload()
    _booted_on(pg, "profile")
    assert pg.evaluate("window.__firstTheme") == other, "data-theme must be set before <body> exists (no wrong first paint)"
    assert _bg(pg) == _rgb(PAPER[other]["bg"])
    expect(_profile(pg).get_by_role("radio", name=pick)).to_be_checked()
    # Auto removes the attribute and follows the OS again, live.
    _profile(pg).get_by_role("radio", name="Match device").check()
    expect(pg.locator("html[data-theme]")).to_have_count(0)
    assert _bg(pg) == _rgb(PAPER[os_scheme]["bg"])
    pg.emulate_media(color_scheme=other)
    assert _bg(pg) == _rgb(PAPER[other]["bg"]), "Auto follows an OS change without a reload"


def test_CHL_DS_18_a_bad_stored_value_means_auto(make_page, site_url):
    pg = make_page(*PHONE, scheme="dark")
    pg.add_init_script("try { localStorage.setItem('charlie-appearance', 'purple'); } catch (_) {}")
    pg.goto(site_url)
    _ready(pg)
    expect(pg.locator("html[data-theme]")).to_have_count(0)
    assert _bg(pg) == _rgb(PAPER["dark"]["bg"])
    expect(_profile(pg).get_by_role("radio", name="Match device")).to_be_checked()


def test_CHL_DS_18_reset_demo_keeps_the_appearance_choice(make_page, site_url):
    pg = make_page(*PHONE, scheme="light")
    pg.goto(site_url)
    _ready(pg)
    _profile(pg).get_by_role("radio", name="Dark").check()
    bar = pg.get_by_role("region", name="Demo")
    bar.get_by_role("button", name="Demo details").click()
    bar.get_by_role("button", name="Reset demo").click()
    with pg.expect_navigation():
        bar.get_by_role("button", name="Reset", exact=True).click()
    _booted_on(pg, "profile")
    assert pg.evaluate("localStorage.getItem('charlie-appearance')") == "dark"
    expect(pg.locator("html[data-theme=dark]")).to_have_count(1)


# ---------------------------------------------------------------- CHL-DS-19 increased contrast
@pytest.mark.parametrize("scheme,theme", [("light", None), ("dark", None), ("light", "dark"), ("dark", "light")])
def test_CHL_DS_19_increased_contrast_gives_the_hc_tokens(browser, site_url, scheme, theme):
    ctx, pg = _new(browser, site_url, PHONE, scheme, contrast="more")
    try:
        if theme:
            pg.add_init_script(f"try {{ localStorage.setItem('charlie-appearance', '{theme}'); }} catch (_) {{}}")
        pg.goto(site_url)
        _ready(pg)
        mode = theme or scheme
        got = {k: _color(pg, f"var(--{k})") for k in HC[mode]}
        want = {k: _rgb(v) for k, v in HC[mode].items()}
        assert got == want, f"HC {mode} (OS {scheme}, picked {theme}): {got}"
    finally:
        ctx.close()


# ================================================================ fix round 1: ux-reviewer's CHL-DS-R1 to R14
# Written first, red, by qa-tdd on Nov 21 2026 from ux-reviewer's 7/10 restyle review. One test per finding.
SMALL = (320, 700)
TABS = VIEWS  # CHL-DS-25: the five tabs plus the Profile view (opened from the header)
MONEY = re.compile(r"\$\d")


def _open_tab(pg, tab):
    _go(pg, tab)
    _engine_idle(pg)
    if tab == "screener":
        expect(pg.locator("#screen-results [data-row]").first).to_be_attached(timeout=ENGINE)
    pg.evaluate("scrollTo(0, 0)")


CLIPPED_BUTTONS = """() => [...document.querySelectorAll('button')].filter((b) => b.checkVisibility() && !b.closest('.sr-only')
    && b.getBoundingClientRect().width > 0 && b.scrollWidth > b.clientWidth)
    .map((b) => `${b.id ? '#' + b.id : '.' + [...b.classList].join('.')} '${(b.innerText || '').trim().slice(0, 30)}' scrollWidth ${b.scrollWidth} > clientWidth ${b.clientWidth}`)"""
TAB_BOXES = """() => [...document.querySelectorAll('nav.tabs [role=tab]')].map((b) => { const r = b.getBoundingClientRect();
    return {t: b.innerText.trim(), l: r.left, r: r.right, top: r.top, b: r.bottom}; })"""


# ---------------------------------------------------------------- CHL-DS-R1 no clipped button text, no overlapping tabs
@pytest.mark.parametrize("size", [SMALL, PHONE, DESKTOP], ids=["320x700", "390x844", "1280x800"])
def test_CHL_DS_R1_no_button_clips_its_text_and_no_tabs_overlap_on_any_tab(browser, site_url, size):
    ctx, pg = _new(browser, site_url, size)
    try:
        pg.goto(site_url)
        _ready(pg)
        bad = []
        for tab in TABS:
            _open_tab(pg, tab)
            bad += [f"{tab}: {x}" for x in pg.evaluate(CLIPPED_BUTTONS)]
            boxes = pg.evaluate(TAB_BOXES)
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    ox = min(a["r"], b["r"]) - max(a["l"], b["l"])
                    oy = min(a["b"], b["b"]) - max(a["top"], b["top"])
                    if ox > 0.5 and oy > 0.5:
                        bad.append(f"{tab}: tab '{a['t']}' overlaps tab '{b['t']}' by {ox:.1f}px")
        assert bad == [], f"at {size[0]}px:\n" + "\n".join(sorted(set(bad))[:40])
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-DS-R2 Profile: one filled button, inline delete confirm
FILLED_BUTTONS = """() => [...document.querySelectorAll('#tab-profile button')].filter((b) => b.checkVisibility()
    && (b.classList.contains('btn-primary') || b.classList.contains('btn-danger'))).map((b) => b.innerText.trim())"""


def test_CHL_DS_R2_profile_has_one_filled_button_and_delete_confirms_inline(make_page, site_url):
    pg = make_page(*PHONE)
    pg.add_init_script("window.__confirms = 0; window.confirm = () => { window.__confirms += 1; return false; };")
    pg.goto(site_url)
    _ready(pg)
    _open_tab(pg, "profile")
    tab = pg.locator("#tab-profile")
    filled = pg.evaluate(FILLED_BUTTONS)
    assert len(filled) <= 1, f"{len(filled)} filled (primary/danger) buttons on Profile at rest: {filled}"
    build = tab.get_by_role("button", name="Build my profile")
    assert "btn-tinted" in build.get_attribute("class").split(), f"Build my profile is {build.get_attribute('class')}"
    delete = tab.get_by_role("button", name="Delete my data")
    expect(delete).to_have_count(1)
    assert "btn-danger" not in delete.get_attribute("class").split(), "Delete my data is filled danger before it's tapped"
    delete.click()
    pg.wait_for_timeout(200)
    assert pg.evaluate("window.__confirms") == 0, "Delete my data called window.confirm (want an inline confirm)"
    yes = tab.locator("button.btn-danger", has_text=re.compile(r"^\s*Delete my data\s*$"))
    keep = tab.get_by_role("button", name="Keep my data", exact=True)
    expect(yes).to_be_visible()
    expect(keep).to_be_visible()
    assert len(pg.evaluate(FILLED_BUTTONS)) <= 1, f"filled buttons with the confirm open: {pg.evaluate(FILLED_BUTTONS)}"
    keep.click()
    expect(keep).to_be_hidden()
    assert pg.evaluate("window.__confirms") == 0


# ---------------------------------------------------------------- CHL-DS-R3 dollar figures are never accent
ACCENT_MONEY = r"""(accent) => [...document.querySelectorAll('body *')].filter((el) => {
    if (!el.checkVisibility() || el.closest('svg, .sr-only')) return false;
    const own = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('');
    return /\$\d/.test(own) && getComputedStyle(el).color === accent;
}).map((el) => `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}.${[...el.classList].join('.')} '${el.textContent.trim().slice(0, 50)}'`)"""


@pytest.mark.parametrize("scheme,contrast", [("light", None), ("dark", None), ("light", "more")], ids=["light", "dark", "hc"])
def test_CHL_DS_R3_no_dollar_figure_is_in_the_accent_and_the_hero_link_names_the_idea(browser, site_url, scheme, contrast):
    """No-$-in-accent half unchanged. Link half superseded by CHL-NAV-8: no top-idea link on Today."""
    ctx, pg = _new(browser, site_url, PHONE, scheme, contrast)
    try:
        pg.goto(site_url)
        _ready(pg)
        accent = _color(pg, "var(--accent)")
        bad = []
        for tab in TABS:
            _open_tab(pg, tab)
            bad += [f"{tab}: {x}" for x in pg.evaluate(ACCENT_MONEY, accent)]
        pg.click("[data-tab=today]")
        _engine_idle(pg)
        pg.locator("#ideas .card [data-ticker]").first.click()
        expect(pg.locator("#drawer svg.payoff").first).to_be_visible(timeout=ENGINE)
        bad += [f"drawer: {x}" for x in pg.evaluate(ACCENT_MONEY, accent)]
        pg.keyboard.press("Escape")
        pg.evaluate("scrollTo(0, 0)")
        # Link half superseded by CHL-NAV-8: Today has no top-idea link at all (the card is in the first screen).
        today = pg.locator("#tab-today")
        links = today.get_by_role("link", name=re.compile("top idea", re.I)).filter(visible=True).count()
        assert links == 0 and not pg.locator("#hero-top-idea").filter(visible=True).count(), \
            "Today still shows a top-idea link (CHL-NAV-8: no hero link)"
        assert bad == [], f"dollar figures in the accent ({scheme}{', HC' if contrast else ''}):\n" + "\n".join(sorted(set(bad))[:30])
    finally:
        ctx.close()


# ---------------------------------------------------------------- CHL-DS-R4 cards stay short; why-reasons have no pill fill
def test_CHL_DS_R4_idea_cards_stay_under_800px_and_why_reasons_are_unfilled(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    pg.evaluate("document.querySelectorAll('#ideas details').forEach((d) => d.open = false)")
    cards = pg.locator("#ideas .card")
    assert cards.count() >= 1
    tall = [f"card {i + 1}: {cards.nth(i).bounding_box()['height']:.0f}px" for i in range(cards.count())
            if cards.nth(i).bounding_box()["height"] > 800]
    filled = pg.evaluate("""() => [...document.querySelectorAll('#ideas .card .why-chips > *')].filter((e) => e.checkVisibility())
        .map((e) => ({t: e.textContent.trim().slice(0, 40), bg: getComputedStyle(e).backgroundColor}))
        .filter((x) => x.bg !== 'rgba(0, 0, 0, 0)' && x.bg !== 'transparent')""")
    assert pg.locator("#ideas .card .why-chips > *").count() >= 1, "no why-reasons on the cards"
    assert tall == [] and filled == [], {"over 800px at 390": tall, "why-reasons with a fill": filled[:10]}


# ---------------------------------------------------------------- CHL-DS-R5 the drawer's Close says Close
def test_CHL_DS_R5_drawer_close_reads_close_is_48px_and_escape_still_closes(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    pg.locator("#ideas .card [data-ticker]").first.click()
    drawer = pg.locator("#drawer")
    expect(drawer.locator("svg.payoff").first).to_be_visible(timeout=ENGINE)
    close = pg.locator("#drawer-close")
    got = close.evaluate("(b) => ({t: b.innerText.trim(), h: b.getBoundingClientRect().height, w: b.getBoundingClientRect().width,"
                         " label: b.getAttribute('aria-label')})")
    assert got["t"] == "Close", f"#drawer-close shows {got['t']!r}, want the word 'Close'"
    assert abs(got["h"] - 48) <= 0.5 and got["w"] >= 48, f"#drawer-close is {got['w']:.0f}x{got['h']:.0f} (want 48 tall)"
    assert got["label"], "#drawer-close lost its aria-label"
    pg.keyboard.press("Escape")
    expect(drawer).to_be_hidden()


# ---------------------------------------------------------------- CHL-DS-R6 the risk slider is usable at 320
def test_CHL_DS_R6_risk_slider_is_at_least_240px_wide_at_320(make_page, site_url):
    pg = make_page(*SMALL)
    pg.goto(site_url)
    _ready(pg)
    w = pg.locator("#risk").bounding_box()["width"]
    assert w >= 240, f"the risk range input is {w:.0f}px wide at 320px (want >= 240)"


# ---------------------------------------------------------------- CHL-DS-R7 chat: no card around the messages
def test_CHL_DS_R7_chat_welcome_and_panel_have_no_card_border_or_fill(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    _open_tab(pg, "chat")
    got = pg.evaluate("""() => { const st = (e) => { const s = getComputedStyle(e);
            return {bw: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth].map(parseFloat).reduce((a, b) => a + b, 0),
                    bs: s.borderTopStyle, bg: s.backgroundColor}; };
        const w = document.querySelector('#chat-log .msg.bot');
        let p = w.parentElement, pbg = 'rgba(0, 0, 0, 0)';
        for (; p; p = p.parentElement) { const b = getComputedStyle(p).backgroundColor; if (b !== 'rgba(0, 0, 0, 0)') { pbg = b; break; } }
        return {welcome: st(w), parentBg: pbg, wrap: st(document.querySelector('.chat-wrap')), log: st(document.querySelector('#chat-log'))}; }""")
    bad = []
    w = got["welcome"]
    if w["bw"] > 0 and w["bs"] != "none":
        bad.append(f"welcome message has a border ({w['bw']:g}px summed over its sides)")
    if w["bg"] not in ("rgba(0, 0, 0, 0)", got["parentBg"]):
        bad.append(f"welcome message background {w['bg']} differs from its parent's {got['parentBg']}")
    for k in ("wrap", "log"):
        if got[k]["bw"] > 0 and got[k]["bs"] != "none":
            bad.append(f"{'.chat-wrap' if k == 'wrap' else '#chat-log'} has a card border ({got[k]['bw']:g}px summed over its sides)")
    assert bad == [], bad


# ---------------------------------------------------------------- CHL-DS-R8 footer disclaimer on one row at 320
def test_CHL_DS_R8_footer_disclaimer_line_fits_one_row_at_320(make_page, site_url):
    """Superseded by CHL-NAV-3: the line above the bottom bar (#disclaimer-line, all its text) is one row at 320,
    and exactly 48px tall (a full tap target; chief of staff, Nov 22: principle 2 wins over the spec's 40px)."""
    pg = make_page(*SMALL)
    pg.goto(site_url)
    _ready(pg)
    expect(pg.locator("#disclaimer-line")).to_be_visible()
    rows = pg.evaluate("""() => { const t = document.querySelector('#disclaimer-line'); const tops = new Set();
        const tw = document.createTreeWalker(t, NodeFilter.SHOW_TEXT); let n;
        while ((n = tw.nextNode())) { if (!n.textContent.trim() || !n.parentElement.checkVisibility()) continue;
          const r = document.createRange(); r.selectNodeContents(n);
          [...r.getClientRects()].filter((x) => x.width > 0).forEach((x) => tops.add(Math.round(x.top))); }
        return {rows: tops.size, text: t.innerText.trim(), h: t.getBoundingClientRect().height}; }""")
    assert rows["rows"] == 1, f"the disclaimer line '{rows['text']}' wraps onto {rows['rows']} rows at 320px (orphan word)"
    assert abs(rows["h"] - 48) <= 0.5, f"the disclaimer line is {rows['h']:.1f}px tall at 320px (want exactly 48)"


# ---------------------------------------------------------------- CHL-DS-R9 Appearance above the circle, plain labels
def test_CHL_DS_R9_appearance_sits_above_the_circle_with_match_device_light_dark(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    _open_tab(pg, "profile")
    a, v = pg.locator("#appearance").bounding_box(), pg.locator("#profile-view").bounding_box()
    assert a["y"] < v["y"], f"#appearance top {a['y']:.0f} is below the profile circle view top {v['y']:.0f} at 390"
    labels = pg.evaluate("[...document.querySelectorAll('#appearance input[type=radio]')].map((r) => [r.labels[0].innerText.trim(), r.value])")
    assert labels == [["Match device", "auto"], ["Light", "light"], ["Dark", "dark"]], labels
    legend = pg.locator("#appearance legend").evaluate("(l) => [getComputedStyle(l).fontSize, getComputedStyle(l).lineHeight]")
    assert legend == ["22px", "28px"], f"Appearance legend is {legend}, want the 22/28 title size"
    group = pg.get_by_role("group", name="Appearance")
    group.get_by_role("radio", name="Dark").check()
    group.get_by_role("radio", name="Match device").check()
    assert pg.evaluate("localStorage.getItem('charlie-appearance')") in (None, "auto")


# ---------------------------------------------------------------- CHL-DS-R10 the Profile risk select isn't clipped
def test_CHL_DS_R10_profile_risk_select_text_is_not_clipped_at_390(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    _open_tab(pg, "profile")
    sel = pg.locator("#profile-form select[name=risk_level]")
    bad = []
    for v in ["1", "2", "3", "4", "5"]:
        sel.select_option(v)
        got = sel.evaluate("""(s) => { const c = getComputedStyle(s), x = document.createElement('canvas').getContext('2d');
            x.font = `${c.fontWeight} ${c.fontSize} ${c.fontFamily}`;
            return {t: s.options[s.selectedIndex].text, need: x.measureText(s.options[s.selectedIndex].text).width,
                    room: s.clientWidth - parseFloat(c.paddingLeft) - parseFloat(c.paddingRight), sw: s.scrollWidth, cw: s.clientWidth}; }""")
        if got["sw"] > got["cw"] or got["need"] > got["room"] + 0.5:
            bad.append(f"'{got['t']}' needs {got['need']:.0f}px, has {got['room']:.0f}px (scrollWidth {got['sw']}, clientWidth {got['cw']})")
    assert bad == [], f"Profile risk select clips its text at 390: {bad}"


# ---------------------------------------------------------------- CHL-DS-R11 the hero metric values line up
def test_CHL_DS_R11_card_one_hero_values_share_a_baseline_at_390(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    tops = pg.evaluate("""() => [...document.querySelector('#ideas .card').querySelectorAll('.hero-m .metric .v')]
        .map((v) => ({t: v.innerText.trim(), top: v.getBoundingClientRect().top}))""")
    assert len(tops) == 3, tops
    spread = max(t["top"] for t in tops) - min(t["top"] for t in tops)
    assert spread <= 1, f"card 1 hero values start {spread:.0f}px apart at 390 (want within 1px): {tops}"


# ---------------------------------------------------------------- CHL-DS-R12 drawer head: 22px name, "Sample data" once
def test_CHL_DS_R12_drawer_head_name_is_22px_and_says_sample_data_once(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    pg.locator("#ideas .card [data-ticker]").first.click()
    expect(pg.locator("#drawer svg.payoff").first).to_be_visible(timeout=ENGINE)
    got = pg.evaluate("""() => { const t = document.querySelector('#drawer-title');
        const body = document.querySelector('#drawer-body'), first = [...body.children].find((e) => e.checkVisibility() && e.innerText.trim());
        return {px: getComputedStyle(t).fontSize, head: document.querySelector('.drawer-head').innerText, first: first ? first.innerText : ''}; }""")
    assert got["px"] == "22px", f"the drawer's company name is {got['px']} (want 22px)"
    n = (got["head"] + "\n" + got["first"]).count("Sample data")
    assert n == 1, f"'Sample data' appears {n} times in the drawer head and first body line: {got['head']!r} / {got['first']!r}"


# ---------------------------------------------------------------- CHL-DS-R13 one left edge at 1280
def test_CHL_DS_R13_brand_tabs_and_content_share_a_left_edge_at_1280(make_page, site_url):
    """Superseded by CHL-NAV-11: the brand and the tabs moved into the laptop sidebar. In the sidebar, the brand mark,
    every tab row's icon and the Profile row's icon start on one left edge; in the main column, the risk slider,
    each view's title and Today's cards start on main's content edge, right of the sidebar. Same intent (one left
    edge per column), now two columns."""
    pg = make_page(*DESKTOP)
    pg.goto(site_url)
    _ready(pg)
    edges = """() => { const L = (e) => e ? e.getBoundingClientRect().left : null;
        const inner = (e) => e ? e.getBoundingClientRect().left + parseFloat(getComputedStyle(e).paddingLeft) : null;
        const side = document.querySelector('header'), m = document.querySelector('main');
        const prof = [...side.querySelectorAll('button')].find((b) => b.checkVisibility() && b.innerText.trim() === 'Profile');
        const v = document.querySelector('main .tab.active');
        return {sideRight: side.getBoundingClientRect().right, content: inner(m),
                logo: L(document.querySelector('header .brand .logo')),
                tabs: [...document.querySelectorAll('nav.tabs [role=tab]')].map((t) => L(t.querySelector('svg'))),
                profile: prof ? L(prof.querySelector('svg')) : null,
                risk: L([...document.querySelectorAll('#risk-row')].find((e) => e.checkVisibility())),
                h1: L(v && v.querySelector('h1')),
                cards: [...document.querySelectorAll('#ideas .card')].filter((c) => c.checkVisibility()).map(L)}; }"""
    got = pg.evaluate(edges)
    bad = []
    side = [got["logo"], *got["tabs"], got["profile"]]
    if None in side or max(side) - min(side) > 1:
        bad.append(f"sidebar: mark {got['logo']}, tab icons {got['tabs']}, Profile icon {got['profile']} (want one left edge)")
    if got["content"] < got["sideRight"]:
        bad.append(f"main content edge {got['content']:.0f} is not right of the sidebar ({got['sideRight']:.0f})")
    main_col = {"risk slider": got["risk"], "Today title": got["h1"], **{f"card {i + 1}": x for i, x in enumerate(got["cards"])}}
    if not got["cards"]:
        bad.append("no idea card to line up")
    for what, x in main_col.items():
        if x is None or abs(x - got["content"]) > 1:
            bad.append(f"{what} starts at {x}, main content edge {got['content']:.0f}")
    for view in ("screener", "chat", "paper", "learn"):
        pg.click(f"nav.tabs [role=tab][data-tab={view}]")
        expect(pg.locator(f"#tab-{view}")).to_be_visible()
        x = pg.evaluate(edges)
        if x["h1"] is None or abs(x["h1"] - x["content"]) > 1:
            bad.append(f"{view} title starts at {x['h1']}, main content edge {x['content']:.0f}")
    assert bad == [], "at 1280:\n" + "\n".join(bad)


# ---------------------------------------------------------------- CHL-DS-R14 empty Portfolio: no icon, no Refresh
def test_CHL_DS_R14_empty_portfolio_has_no_icon_circle_and_no_refresh(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    _open_tab(pg, "paper")
    expect(pg.get_by_text("No paper trades yet")).to_be_visible(timeout=ENGINE)
    icons = pg.evaluate("[...document.querySelectorAll('#tab-paper .icon')].filter((e) => e.checkVisibility()).length")
    refresh = pg.locator("#tab-paper").get_by_role("button", name="Refresh")
    vis = refresh.count() and refresh.first.is_visible()
    assert icons == 0 and not vis, f"empty Portfolio shows {icons} icon circle(s) and Refresh visible={bool(vis)}"


# ---------------------------------------------------------------- CHL-DS-R15 card head: sector line under the score button
CARD_HEADS = """() => [...document.querySelectorAll('#ideas .card')].map((c, i) => {
    const b = (s) => { const e = c.querySelector(s); return e ? e.getBoundingClientRect() : null; };
    const t = b('.card-title'), s = b('.card-sub'), g = b('.grade');
    return {i: i + 1, titleBottom: t && t.bottom, subTop: s && s.top, gradeBottom: g && g.bottom,
            h: c.getBoundingClientRect().height}; })"""


@pytest.mark.parametrize("size", [SMALL, PHONE], ids=["320x700", "390x844"])
def test_CHL_DS_R15_card_sector_line_sits_below_the_score_button_and_the_title(make_page, site_url, size):
    pg = make_page(*size)
    pg.goto(site_url)
    _ready(pg)
    pg.evaluate("document.querySelectorAll('#ideas details').forEach((d) => d.open = false)")
    heads = pg.evaluate(CARD_HEADS)
    assert heads, "no idea cards"
    bad = []
    for h in heads:
        if None in (h["titleBottom"], h["subTop"], h["gradeBottom"]):
            bad.append(f"card {h['i']}: missing .card-title, .card-sub or .grade ({h})")
            continue
        if h["subTop"] < h["gradeBottom"] - 0.5:
            bad.append(f"card {h['i']}: .card-sub top {h['subTop']:.1f} is above the .grade bottom {h['gradeBottom']:.1f}")
        if h["titleBottom"] > h["subTop"] + 0.5:
            bad.append(f"card {h['i']}: .card-title bottom {h['titleBottom']:.1f} runs past the .card-sub top {h['subTop']:.1f}")
    if size == PHONE and heads[0]["h"] > 800:
        bad.append(f"card 1 is {heads[0]['h']:.0f}px tall at 390 (want <= 800)")
    assert bad == [], f"at {size[0]}px:\n" + "\n".join(bad)


# ---------------------------------------------------------------- CHL-DS-R16 jumping to card 1 lands below the sticky bar
# The sticky bar = every visible fixed/sticky element pinned at the top of the viewport (header, tabs), not
# the bottom demo bar or a full-screen modal.
STICKY_BOTTOM = """() => { let b = 0;
    for (const e of document.querySelectorAll('body *')) {
      const p = getComputedStyle(e).position;
      if ((p !== 'sticky' && p !== 'fixed') || !e.checkVisibility()) continue;
      const r = e.getBoundingClientRect();
      if (r.height === 0 || r.top > 1 || r.bottom > innerHeight / 2) continue;
      b = Math.max(b, r.bottom);
    }
    return b; }"""


def _settle_scroll(pg):
    pg.wait_for_function("""() => new Promise((ok) => { let y = scrollY, n = 0;
        const t = setInterval(() => { if (scrollY === y) { if (++n >= 5) { clearInterval(t); ok(true); } } else { y = scrollY; n = 0; } }, 50); })""",
                         timeout=10_000)


def _card_one_under_sticky(pg):
    got = pg.evaluate("""(sb) => { const t = document.querySelector('#ideas .card .card-title').getBoundingClientRect();
        return {top: t.top, bottom: t.bottom, sticky: sb, vh: innerHeight, y: scrollY}; }""", pg.evaluate(STICKY_BOTTOM))
    assert got["sticky"] > 0, "found no sticky bar at the top of the page"
    assert got["top"] >= got["sticky"] - 0.5 and got["bottom"] <= got["vh"], \
        f"card 1 title spans {got['top']:.0f} to {got['bottom']:.0f}px but the sticky bar ends at {got['sticky']:.0f}px " \
        f"(viewport {got['vh']}px, scrollY {got['y']:.0f})"


def test_CHL_DS_R16_hero_top_idea_link_lands_card_one_title_below_the_sticky_bar_at_390(make_page, site_url):
    """Superseded by CHL-NAV-5/8: no link at 390; at rest card 1 starts below the header, and a jump to any
    #ideas .card (scrollIntoView, block start) lands its title clear of the 56px sticky header."""
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    pg.evaluate("scrollTo(0, 0)")
    expect(pg.locator("#hero-top-idea").filter(visible=True)).to_have_count(0)
    rest = pg.evaluate("""() => ({card: document.querySelector('#ideas .card').getBoundingClientRect().top,
        header: document.querySelector('header').getBoundingClientRect().bottom})""")
    assert rest["card"] >= rest["header"] - 0.5, f"at rest card 1 top {rest['card']:.0f} is under the header bottom {rest['header']:.0f}"
    for i in range(pg.locator("#ideas .card").count()):
        pg.evaluate("(i) => document.querySelectorAll('#ideas .card')[i].scrollIntoView({block: 'start'})", i)
        _settle_scroll(pg)
        got = pg.evaluate("""(i) => ({t: document.querySelectorAll('#ideas .card .card-title')[i].getBoundingClientRect().top,
            m: parseFloat(getComputedStyle(document.querySelectorAll('#ideas .card')[i]).scrollMarginTop)})""", i)
        assert got["m"] >= 56 and got["t"] >= 56 - 0.5, f"card {i + 1}: scroll-margin-top {got['m']}px, title top {got['t']:.0f}px (want both >= 56)"
    pg.evaluate("document.querySelector('#ideas .card').scrollIntoView({block: 'start'})")
    _settle_scroll(pg)
    _card_one_under_sticky(pg)


def test_CHL_DS_R16_card_one_scrolled_into_view_sits_below_the_sticky_bar_at_1280(make_page, site_url):
    """Superseded by CHL-NAV-8/11: no link; card 1 scrolled into view (block start) has its top >= 0 and nothing
    sticky or fixed over its title (the sidebar sits beside it, not on top)."""
    pg = make_page(*DESKTOP)
    pg.goto(site_url)
    _ready(pg)
    expect(pg.locator("#hero-top-idea").filter(visible=True)).to_have_count(0)
    pg.evaluate("document.querySelector('#ideas .card').scrollIntoView({block: 'start'})")
    _settle_scroll(pg)
    got = pg.evaluate("""() => { const c = document.querySelector('#ideas .card').getBoundingClientRect(),
        t = document.querySelector('#ideas .card .card-title').getBoundingClientRect();
        const over = [...document.querySelectorAll('body *')].filter((e) => { const p = getComputedStyle(e).position;
            if ((p !== 'sticky' && p !== 'fixed') || !e.checkVisibility() || e.closest('#toast, #engine-status')) return false;
            const r = e.getBoundingClientRect();
            return r.height > 0 && r.left < t.right && r.right > t.left && r.top < t.bottom && r.bottom > t.top; })
            .map((e) => e.tagName + '.' + [...e.classList].join('.'));
        return {top: c.top, over}; }""")
    assert got["top"] >= -0.5 and got["over"] == [], f"card 1 top {got['top']:.0f}px; sticky/fixed over its title: {got['over']}"


# ---------------------------------------------------------------- CHL-DS-R17 Appearance options stack at 390
def test_CHL_DS_R17_appearance_options_each_take_a_48px_row_with_one_left_edge_at_390(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    _open_tab(pg, "profile")
    rows = pg.evaluate("""() => [...document.querySelectorAll('#appearance input[type=radio]')].map((r) => {
        const b = r.labels[0].getBoundingClientRect(); return {t: r.labels[0].innerText.trim(), l: b.left, top: b.top, b: b.bottom, h: b.height}; })""")
    assert len(rows) == 3, rows
    bad = [f"'{r['t']}' is {r['h']:.0f}px tall (want >= 48)" for r in rows if r["h"] < TARGET - 0.5]
    bad += [f"'{b['t']}' (top {b['top']:.0f}) is not on its own row below '{a['t']}' (bottom {a['b']:.0f})"
            for a, b in zip(rows, rows[1:]) if b["top"] < a["b"] - 0.5]
    if max(r["l"] for r in rows) - min(r["l"] for r in rows) > 0.5:
        bad.append("left edges differ: " + ", ".join(f"'{r['t']}' {r['l']:.0f}" for r in rows))
    assert bad == [], "Appearance at 390:\n" + "\n".join(bad)


# ---------------------------------------------------------------- CHL-DS-R18 the tab bar shows there is more (none at 320 since DS-25)
# Testable signal for the engineer: while the tab scroller (nav.tabs .tabs-inner) has more to its right
# (scrollLeft + clientWidth < scrollWidth - 1), nav.tabs carries the class "has-more" and its ::after draws the
# right-edge fade (computed content is not "none", display is not "none", width > 0). Scrolled to the end, the
# class is gone and ::after draws nothing (content "none" or display "none" or width 0). Update it on the
# scroller's "scroll" event and on resize.
TAB_FADE = """() => { const n = document.querySelector('nav.tabs'), s = n.querySelector('[role=tablist]'), a = getComputedStyle(n, '::after');
    return {more: s.scrollLeft + s.clientWidth < s.scrollWidth - 1, sl: s.scrollLeft, cw: s.clientWidth, sw: s.scrollWidth,
            cls: n.classList.contains('has-more'),
            fade: a.content !== 'none' && a.content !== 'normal' && a.display !== 'none' && parseFloat(a.width) > 0}; }"""


def test_CHL_DS_R18_no_fade_at_320_when_all_five_tabs_fit(make_page, site_url):
    """CHL-DS-25 changed R18: with five tabs, nothing hides at 320, so there's no fade to draw (and no R20 Learn cut-off)."""
    pg = make_page(*SMALL)
    pg.goto(site_url)
    _ready(pg)
    pg.wait_for_timeout(300)
    got = pg.evaluate(TAB_FADE)
    assert not got["more"] and not got["cls"] and not got["fade"], \
        f"at 320 the tab bar overflows or fades: scrollWidth {got['sw']} > clientWidth {got['cw']}={got['more']}, has-more={got['cls']}, fade={got['fade']}"


def test_CHL_DS_R18_tab_bar_fades_on_the_right_while_more_tabs_are_hidden_when_it_overflows(make_page, site_url):
    """Superseded by CHL-NAV-1/11: the bar (320, 390) and the sidebar (1280) never scroll sideways, so there is
    never anything hidden to fade to: scrollWidth <= clientWidth, a forced scrollLeft stays 0, has-more never set."""
    bad = []
    for size in (SMALL, PHONE, DESKTOP):
        pg = make_page(*size)
        pg.goto(site_url)
        _ready(pg)
        pg.wait_for_timeout(300)
        pg.evaluate("(() => { const s = document.querySelector('nav.tabs [role=tablist]'); s.scrollLeft = s.scrollWidth; dispatchEvent(new Event('resize')); })()")
        pg.wait_for_timeout(300)
        got = pg.evaluate(TAB_FADE)
        if got["sw"] > got["cw"] or got["sl"] > 0 or got["cls"] or got["fade"]:
            bad.append(f"{size[0]}px: scrollWidth {got['sw']} clientWidth {got['cw']} scrollLeft {got['sl']} has-more={got['cls']} fade={got['fade']}")
    assert bad == [], "the tab bar/sidebar scrolls or fades:\n" + "\n".join(bad)


# ---------------------------------------------------------------- CHL-DS-R19 drawer reasons are plain lines, not pills
def test_CHL_DS_R19_drawer_reason_lines_are_why_lines_with_no_fill(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    pg.locator("#ideas .card [data-ticker]").first.click()
    expect(pg.locator("#drawer svg.payoff").first).to_be_visible(timeout=ENGINE)
    got = pg.evaluate("""() => { const b = document.querySelector('#drawer-body');
        const lines = [...b.querySelectorAll('.why-line')].filter((e) => e.checkVisibility())
            .map((e) => ({t: e.textContent.trim().slice(0, 40), bg: getComputedStyle(e).backgroundColor}));
        const pills = [...b.querySelectorAll('span.chip')].filter((e) => e.checkVisibility()).map((e) => e.textContent.trim().slice(0, 40));
        return {lines, pills}; }""")
    filled = [x for x in got["lines"] if x["bg"] not in ("rgba(0, 0, 0, 0)", "transparent")]
    assert got["lines"] and not filled and not got["pills"], \
        {"drawer .why-line count": len(got["lines"]), "with a fill": filled, "reasons still as span.chip pills": got["pills"]}


# ================================================================ CHL-DS-25 Profile leaves the tab bar (Chase, Nov 22)
# Written first, red, by qa-tdd on Nov 22 2026. Profile isn't updated often, so it moves off the main tabs:
# exactly five tabs (Today, Screener, Chat, Portfolio, Learn), and a header button with the visible word
# "Profile" opens the same #tab-profile view. Testable signal for "shows it as the active view": #tab-profile
# is the only visible view, the hash is #profile, the Profile button carries aria-current="page" (and drops it
# when you leave), and no tab claims aria-selected="true" or .active while Profile shows.
TAB_STATE = """() => [...document.querySelectorAll('nav.tabs [role=tab]')].map((t) => ({
    t: t.innerText.trim(), sel: t.getAttribute('aria-selected'), act: t.classList.contains('active')}))"""
VISIBLE_VIEWS = "[...document.querySelectorAll('main .tab')].filter((s) => s.checkVisibility()).map((s) => s.id)"


def _profile_is_the_view(pg):
    expect(pg.locator("#tab-profile")).to_be_visible()
    assert pg.evaluate(VISIBLE_VIEWS) == ["tab-profile"], pg.evaluate(VISIBLE_VIEWS)
    assert pg.evaluate("location.hash") == "#profile"
    expect(_profile_button(pg)).to_have_attribute("aria-current", "page")
    picked = [t for t in pg.evaluate(TAB_STATE) if t["sel"] == "true" or t["act"]]
    assert picked == [], f"a tab still looks picked while Profile shows: {picked}"


def _today_is_the_view(pg):
    expect(pg.locator("#tab-today")).to_be_visible()
    assert pg.evaluate(VISIBLE_VIEWS) == ["tab-today"], pg.evaluate(VISIBLE_VIEWS)
    assert pg.evaluate("location.hash") == "#today"
    expect(pg.get_by_role("tab", name="Today")).to_have_attribute("aria-selected", "true")
    assert _profile_button(pg).get_attribute("aria-current") in (None, "false"), "Profile still marked current on Today"


@pytest.mark.parametrize("size", [SMALL, PHONE, DESKTOP], ids=["320x700", "390x844", "1280x800"])
def test_CHL_DS_25_tab_bar_has_exactly_five_tabs_in_order_with_no_profile_tab(make_page, site_url, size):
    pg = make_page(*size)
    pg.goto(site_url)
    _ready(pg)
    tabs = pg.locator("nav.tabs [role=tab]")
    assert [t.strip() for t in tabs.all_inner_texts()] == TAB_NAMES, f"tabs at {size[0]}: {tabs.all_inner_texts()}"
    expect(pg.get_by_role("tab", name="Profile")).to_have_count(0)
    expect(pg.locator("[role=tab][data-tab=profile], #tabbtn-profile")).to_have_count(0)
    # Keyboard (ARIA tabs): End lands on Learn, ArrowRight wraps to Today, never through Profile.
    pg.get_by_role("tab", name="Today").focus()
    pg.keyboard.press("End")
    expect(pg.get_by_role("tab", name="Learn")).to_be_focused()
    pg.keyboard.press("ArrowRight")
    expect(pg.get_by_role("tab", name="Today")).to_be_focused()


def test_CHL_DS_25_all_five_tabs_fit_at_320_with_no_horizontal_scroll(make_page, site_url):
    """Closes CHL-DS-R20 (Learn hidden at 320): every tab sits wholly inside the bar and the viewport."""
    pg = make_page(*SMALL)
    pg.goto(site_url)
    _ready(pg)
    pg.wait_for_timeout(300)
    got = pg.evaluate("""() => { const s = document.querySelector('nav.tabs [role=tablist]'), bar = s.getBoundingClientRect();
        return {sw: s.scrollWidth, cw: s.clientWidth, doc: document.documentElement.scrollWidth,
            tabs: [...s.querySelectorAll('[role=tab]')].map((t) => { const r = t.getBoundingClientRect();
                return {t: t.innerText.trim(), l: r.left, r: r.right, w: r.width, h: r.height,
                        out: r.left < Math.max(0, bar.left) - 0.5 || r.right > Math.min(320, bar.right) + 0.5}; })}; }""")
    bad = []
    if got["sw"] > got["cw"] + 1:
        bad.append(f"tab bar scrolls: scrollWidth {got['sw']} > clientWidth {got['cw']}")
    if got["doc"] > 320:
        bad.append(f"page scrolls sideways: document scrollWidth {got['doc']}")
    bad += [f"'{t['t']}' {t['l']:.0f}-{t['r']:.0f} is cut off" for t in got["tabs"] if t["out"]]
    bad += [f"'{t['t']}' is {t['w']:.0f}x{t['h']:.0f} (want >= 48x48)" for t in got["tabs"] if t["w"] < TARGET - 0.5 or t["h"] < TARGET - 0.5]
    assert len(got["tabs"]) == 5 and bad == [], f"at 320: {[t['t'] for t in got['tabs']]}\n" + "\n".join(bad)


@pytest.mark.parametrize("size", [SMALL, PHONE, DESKTOP], ids=["320x700", "390x844", "1280x800"])
def test_CHL_DS_25_header_profile_button_is_a_48px_quiet_button_clear_of_the_brand(make_page, site_url, size):
    pg = make_page(*size)
    pg.goto(site_url)
    _ready(pg)
    btn = _profile_button(pg)
    expect(btn).to_have_count(1)
    expect(btn).to_be_visible()
    assert "Profile" in btn.inner_text(), f"the header button's visible text is {btn.inner_text()!r}, want the word Profile"
    kinds = set((btn.get_attribute("class") or "").split()) & {"btn-quiet", "btn-secondary"}
    assert kinds, f"Profile button classes {btn.get_attribute('class')!r}: want btn-quiet or btn-secondary"
    got = pg.evaluate("""() => { const h = document.querySelector('header'), b = [...h.querySelectorAll('button')].find((x) => /\\bProfile\\b/.test(x.innerText)),
        r = b.getBoundingClientRect(), br = h.querySelector('.brand').getBoundingClientRect();
        return {b: [r.left, r.top, r.right, r.bottom], brand: [br.left, br.top, br.right, br.bottom], doc: document.documentElement.scrollWidth}; }""")
    (l, t, r, b), (bl, bt, br, bb) = got["b"], got["brand"]
    bad = []
    if r - l < TARGET - 0.5 or b - t < TARGET - 0.5:
        bad.append(f"target {r - l:.0f}x{b - t:.0f} (want >= 48x48)")
    if l < -0.5 or r > size[0] + 0.5:
        bad.append(f"off screen: {l:.0f}-{r:.0f} in a {size[0]}px viewport")
    if min(r, br) - max(l, bl) > 0.5 and min(b, bb) - max(t, bt) > 0.5:
        bad.append(f"overlaps the brand: button {got['b']}, brand {got['brand']}")
    if got["doc"] > size[0]:
        bad.append(f"page scrolls sideways: document scrollWidth {got['doc']}")
    assert bad == [], f"Profile button at {size[0]}px:\n" + "\n".join(bad)


@pytest.mark.parametrize("size", [SMALL, PHONE, DESKTOP], ids=["320x700", "390x844", "1280x800"])
def test_CHL_DS_25_profile_button_opens_profile_as_the_active_view_and_tabs_lead_back(make_page, site_url, size):
    pg = make_page(*size)
    pg.goto(site_url)
    _ready(pg)
    _today_is_the_view(pg)
    _profile_button(pg).click()
    _profile_is_the_view(pg)
    # CHL-NAV-6/7: the view's large title is "Profile"; "Your circle of competence" becomes its h2.
    expect(pg.locator("#tab-profile h1")).to_have_text("Profile")
    expect(pg.locator("#tab-profile").get_by_role("heading", level=2, name="Your circle of competence")).to_be_visible()
    expect(pg.get_by_role("group", name="Appearance")).to_be_visible()
    expect(pg.locator("#tab-profile").get_by_role("button", name="Build my profile")).to_be_visible()
    # the view stays named for assistive tech: whatever labels #tab-profile must exist
    dangling = pg.evaluate("""() => (document.querySelector('#tab-profile').getAttribute('aria-labelledby') || '')
        .split(/\\s+/).filter((id) => id && !document.getElementById(id))""")
    assert dangling == [], f"#tab-profile aria-labelledby points at missing ids: {dangling}"
    # the tabs still work from Profile, and Today brings you back
    pg.get_by_role("tab", name="Chat").click()
    expect(pg.locator("#tab-chat")).to_be_visible()
    expect(pg.get_by_role("tab", name="Chat")).to_have_attribute("aria-selected", "true")
    assert _profile_button(pg).get_attribute("aria-current") in (None, "false")
    _profile_button(pg).click()
    _profile_is_the_view(pg)
    pg.get_by_role("tab", name="Today").click()
    _today_is_the_view(pg)


def test_CHL_DS_25_profile_hash_still_opens_profile_on_load(make_page, site_url):
    pg = make_page(*PHONE)
    pg.goto(site_url + "#profile")
    _booted_on(pg, "profile")
    pg.locator("#ack-btn").click(timeout=ENGINE)
    _profile_is_the_view(pg)
    expect(pg.get_by_role("group", name="Appearance")).to_be_visible()


def test_CHL_DS_25_first_run_paste_a_resume_then_see_todays_ideas_still_works(make_page, site_url):
    """The demo's first run: header Profile -> Paste a resume (sample) -> Build -> See today's ideas -> Today.
    (The local server's "Add your resume" nudge link isn't in the demo; setWhose swaps it for the sample line.)"""
    pg = make_page(*PHONE)
    pg.goto(site_url)
    _ready(pg)
    _profile_button(pg).click()
    _profile_is_the_view(pg)
    pg.click("#use-sample")
    expect(pg.get_by_label("Paste a resume")).to_have_value(re.compile(r"\S"))
    pg.locator("#tab-profile").get_by_role("button", name="Build my profile").click()
    see = pg.locator("#profile-status").get_by_role("button", name="See today's ideas")
    expect(see).to_be_visible(timeout=ENGINE)
    see.click()
    _today_is_the_view(pg)
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)


# CHL-DS-R25 / R26 (ux-reviewer, Nov 22): the header Profile button reads as a tab, not as an underlined link.
# Written first, red, by qa-tdd on Nov 22 2026. Styles are read with the pointer parked off every control so
# :hover never colours the answer.
NAV_LOOK = """(sel) => { const el = document.querySelector(sel), s = getComputedStyle(el), a = getComputedStyle(el, '::after');
    const clear = (c) => !c || c === 'transparent' || /rgba\\(.*,\\s*0\\)$/.test(c);
    const marks = [];
    if (s.borderBottomStyle !== 'none' && parseFloat(s.borderBottomWidth) > 0 && !clear(s.borderBottomColor))
        marks.push({by: 'border-bottom', px: parseFloat(s.borderBottomWidth), color: s.borderBottomColor});
    if (s.boxShadow && s.boxShadow !== 'none') marks.push({by: 'box-shadow', value: s.boxShadow});
    if (a.content && a.content !== 'none' && a.content !== 'normal' && parseFloat(a.height) > 0 && !clear(a.backgroundColor))
        marks.push({by: '::after', px: parseFloat(a.height), color: a.backgroundColor});
    return {color: s.color, deco: s.textDecorationLine, weight: s.fontWeight, marks}; }"""


def _park_pointer(pg):
    pg.mouse.move(1, pg.viewport_size["height"] - 1)
    pg.wait_for_timeout(100)


@pytest.mark.parametrize("size", [PHONE, DESKTOP], ids=["390", "1280"])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_CHL_DS_R25_profile_button_looks_like_the_active_tab_while_profile_is_open(make_page, site_url, scheme, size):
    """Rewritten for CHL-NAV (chief of staff's option a, Nov 22). The active tab now wears an accent-soft pill,
    not a bottom bar, so the old "same mark as the active tab" precondition is gone. With Profile open:
    accent colour (the active tab's), no underline, aria-current="page", and a 2px accent bottom mark
    (border-bottom or ::after bar) that is absent at rest. At 390 and 1280, light and dark."""
    pg = make_page(*size, scheme=scheme)
    pg.goto(site_url)
    _ready(pg)
    _park_pointer(pg)
    accent = _color(pg, "var(--accent)")
    active = pg.evaluate(NAV_LOOK, "nav.tabs [role=tab][aria-selected=true]")
    assert active["color"] == accent, f"test bug guard: the active tab isn't accent in {scheme}: {active}"

    def accent_bar(look):
        return [m for m in look["marks"] if m["by"] != "box-shadow" and abs(m["px"] - 2) < 0.5 and m["color"] == accent]

    at_rest = pg.evaluate(NAV_LOOK, "#profile-btn")
    _profile_button(pg).click()
    _profile_is_the_view(pg)
    _park_pointer(pg)
    got = pg.evaluate(NAV_LOOK, "#profile-btn")
    current = pg.get_attribute("#profile-btn", "aria-current")
    bad = []
    if got["deco"] != "none":
        bad.append(f"text-decoration-line is {got['deco']!r}, want 'none'")
    if got["color"] != active["color"]:
        bad.append(f"color {got['color']} != active tab color {active['color']}")
    if current != "page":
        bad.append(f"aria-current is {current!r}, want 'page'")
    if not accent_bar(got):
        bad.append(f"no 2px accent bottom mark while open; Profile button shows {got['marks'] or 'none'}")
    if accent_bar(at_rest):
        bad.append(f"the 2px accent mark already shows at rest (Today open): {at_rest['marks']}")
    assert bad == [], f"Profile open, {size[0]}px {scheme}:\n" + "\n".join(bad)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_CHL_DS_R26_profile_button_looks_like_an_inactive_tab_on_today(make_page, site_url, scheme):
    pg = make_page(*PHONE, scheme=scheme)
    pg.goto(site_url)
    _ready(pg)
    _today_is_the_view(pg)
    _park_pointer(pg)
    inactive = pg.evaluate(NAV_LOOK, "nav.tabs [role=tab][data-tab=screener]")
    got = pg.evaluate(NAV_LOOK, "#profile-btn")
    bad = []
    if got["color"] != inactive["color"]:
        bad.append(f"color {got['color']} != inactive tab color {inactive['color']}")
    if got["deco"] != "none":
        bad.append(f"text-decoration-line is {got['deco']!r}, want 'none'")
    if got["weight"] != "600":
        bad.append(f"font-weight {got['weight']}, want 600")
    assert bad == [], f"Today open, {scheme}:\n" + "\n".join(bad)
