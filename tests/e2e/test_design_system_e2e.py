"""CHL-DS-6 to DS-19: the studio design core as a visitor sees it, on the built static demo in Chromium.

Spec: the CHL-DS acceptance criteria (Paper theme from hearth main 711fdb8). Written first, red, by qa-tdd on
Nov 21 2026. Fixtures: conftest.py. Runs only with CHARLIE_E2E=1. The unit half is tests/test_design_system.py.

One "sweep" per width (390x844 and 1280x800) walks every place a visitor reads or taps: the ack modal, all six
tabs (with every <details> opened, a paper trade open and a chat reply), the demo bar open and closed (with the
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
  const where = (el) => { const t = el.closest('.tab, #drawer, #ack, .demo-bar, footer, header, nav');
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
        for tab in ["today", "profile", "screener", "chat", "paper", "learn"]:
            pg.click(f"[data-tab={tab}]")
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
        pg.click("[data-tab=today]")
        bar = pg.get_by_role("region", name="Demo")
        bar.get_by_role("button", name="Demo details").click()
        bar.get_by_role("button", name="Reset demo").click()
        add(_collect(pg, "demo bar open, reset question", "section.demo-bar"))
        bar.get_by_role("button", name="Keep").click()
        add(_collect(pg, "demo bar open", "section.demo-bar"))
        bar.get_by_role("button", name="Demo details").click()
        pg.locator("#footer-disclaimer").get_by_role("button", name=re.compile("read more", re.I)).click()
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
    small = pg.evaluate("""() => [...document.querySelectorAll('#tab-today *, header *, nav *, footer *')]
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
            pg.click(f"[data-tab={tab}]")
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
                  ("accent", "accent-ink", "accent-soft", "fill", "ink", "danger", "on-danger")}
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
        bg, fg = want[k]
        if b["bg"] != bg or b["color"] != fg:
            bad.append(f"{label} {k}: bg {b['bg']} color {b['color']}, want bg {bg} color {fg}")
        if k == "btn-tinted" and b["radius"] < min(999, b["h"] / 2 - 0.5):
            bad.append(f"{label} btn-tinted is a capsule (pill radius), radius {b['radius']}")
        if k in ("btn-primary", "btn-tinted"):
            per_screen.setdefault((b["state"], b["group"], k), set()).add(b["text"])
    many = [f"{s} / {g}: {len(t)} {k} buttons {sorted(t)}" for (s, g, k), t in per_screen.items() if len(t) > 1]
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
    pg.click("[data-tab=profile]")
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
    assert [r.evaluate("(r) => r.labels[0].innerText.trim()") for r in radios.all()] == ["Auto", "Light", "Dark"]
    expect(group.get_by_role("radio", name="Auto")).to_be_checked()
    for name in ("Auto", "Light", "Dark"):
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
    _profile(pg).get_by_role("radio", name="Auto").check()
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
    expect(_profile(pg).get_by_role("radio", name="Auto")).to_be_checked()


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
