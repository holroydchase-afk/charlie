"""Copy the user reads: no stray markdown in plain-text fields."""
from charlie.profile import build_profile


def test_profile_text_has_no_raw_markdown():
    p = build_profile("Nurse at HCA Healthcare", capital=20000)
    for text in (p.summary, p.caution):
        assert "*" not in text and "_" not in text


# ---------------------------------------------------------------- CHL-UX27 explainer headings
def test_UX27_every_strategy_has_a_grammatical_explainer_title():
    import re
    from charlie.strategies import STRATEGIES
    problems = []
    for key, s in STRATEGIES.items():
        title = s.get("explainer_title")
        if not title:
            problems.append(f"{key}: no explainer_title")
            continue
        if re.search(r"What is a buy", title, re.I) or "leaps" in title:
            problems.append(f"{key}: {title!r}")
        if not title[0].isupper():
            problems.append(f"{key}: should start with a capital: {title!r}")
        m = re.match(r"What is (an?) (\w)", title)
        if m and (m.group(1) == "an") != (m.group(2).lower() in "aeiou"):
            problems.append(f"{key}: wrong article: {title!r}")
    assert problems == []
    assert "shares" in STRATEGIES["shares"]["explainer_title"].lower()
    assert "LEAPS" in STRATEGIES["leaps_call"]["explainer_title"]


def test_UX27_trades_and_meta_carry_the_explainer_title():
    from datetime import date
    from charlie.browser_store import BrowserStore
    from charlie.data.market import MarketData
    from charlie.handlers import Api
    from charlie.strategies import STRATEGIES, build
    md = MarketData(mode="mock", today=date(2026, 10, 22), cache_dir="/tmp/charlie-test-cache")
    t = build("shares", "KO", md.quote("KO")["price"], md.chain("KO"), 25000, 1)
    assert t.get("explainer_title") == STRATEGIES["shares"]["explainer_title"]

    class Mem(dict):  # the browser's localStorage, in memory
        def getItem(self, k): return self.get(k)
        def setItem(self, k, v): self[k] = v
        def removeItem(self, k): self.pop(k, None)
    meta = Api(BrowserStore(Mem()), md, static=True).meta()
    missing = [k for k, v in meta["strategies"].items() if v.get("explainer_title") != STRATEGIES[k]["explainer_title"]]
    assert missing == [], f"/api/meta strategies without explainer_title: {missing}"


def test_UX27_app_js_never_builds_a_heading_from_the_lower_cased_label():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text()
    assert "What is a ${" not in js, "app.js builds 'What is a <label>?' from the label; use trade.explainer_title"
    assert "explainer_title" in js


# ---------------------------------------------------------------- CHL-UX1 / CHL-UX2 shares skip reasons
def _shares_reason(spot, capital):
    import pytest
    from charlie.strategies import Infeasible, build
    with pytest.raises(Infeasible) as exc:
        build("shares", "TEST", spot, [], capital, 1)
    return str(exc.value)


def test_CHL_UX1_zero_paper_capital_message_names_paper_capital_and_profile():
    assert _shares_reason(100.0, 0) == "no paper capital set (add it in your profile)"


def test_CHL_UX2_missing_share_price_message_says_try_again_later():
    for spot in (0, 0.0, -1.0):
        assert _shares_reason(spot, 20000) == "no current share price for this stock; try again later"


# ---------------------------------------------------------------- CHL-UX43 to UX50, CHL-R11 (ux-reviewer, Oct 29)
import re as _re
import subprocess as _sp
from pathlib import Path as _Path

_WEB = _Path(__file__).resolve().parents[1] / "web"
_NFA = "Not financial advice. Paper trading only."


def _app_js():
    return (_WEB / "app.js").read_text()


def _fn(js, name):
    """The source of a top-level app.js function (same pattern as test_privacy's disclaimer check)."""
    m = _re.search(r"(?:async )?function " + name + r"\(.*?\n}\n", js, _re.S)
    assert m, f"app.js has no function {name}"
    return m.group(0)


def _html_block(html, open_re):
    """The markup from the first tag matching open_re to its matching close tag (div/section/footer)."""
    m = _re.search(open_re, html)
    assert m, open_re
    tag = _re.match(r"<(\w+)", m.group(0)).group(1)
    depth, i = 0, m.start()
    for t in _re.finditer(rf"<(/?){tag}\b[^>]*>", html[m.start():]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return html[m.start(): m.start() + t.end()]
    raise AssertionError(f"unclosed {open_re}")


def _text(markup):
    return _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", "", markup)).strip()


def test_CHL_UX43_demo_date_line_says_sample_market_day_with_a_human_date():
    body = _fn(_app_js(), "loadIdeas")
    assert "${esc(r.date)} ·" not in body, "Today's date line still shows the raw ISO date (2026-10-29 · …)"
    assert "Sample market day: " in body, "the demo's date line must read 'Sample market day: Oct 29, 2026 · …'"
    assert _re.search(r"status\??\.static|charlieStatic", body), \
        "the 'Sample market day' prefix must be for the static demo only (state.status.static)"
    assert "fmtDate(r.date)" in body, "the date line must use the shared fmtDate helper (Oct 29, 2026)"


def test_CHL_UX45_drawer_sticky_header_carries_the_disclaimer_and_demo_sample_label():
    html = (_WEB / "index.html").read_text()
    head = _html_block(html, r'<div class="drawer-head"[^>]*>')
    assert _NFA in _text(head), "the drawer's sticky header (.drawer-head) must say the disclaimer"
    # In the demo, "Sample data · " sits right before it, in a static-only element.
    m = _re.search(r'<(\w+)[^>]*class="[^"]*static-only[^"]*"[^>]*>\s*Sample data ·\s*</\1>\s*' + _re.escape(_NFA), head)
    assert m, "the drawer header needs a static-only 'Sample data · ' right before the disclaimer"
    # The rendered drawer body still carries it too (CLAUDE.md: the ticker drawer is a trade surface).
    assert "nfa()" in _fn(_app_js(), "openTicker")


def test_CHL_UX46_static_build_footer_links_back_to_chaseholroyd_com(tmp_path):
    import sys
    root = _WEB.parent
    sys.path.insert(0, str(root / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    out = build_demo.build(tmp_path / "site", day="2026-10-22")
    footer = _html_block((out / "index.html").read_text(), r'<footer[^>]*id="footer-disclaimer"[^>]*>')
    assert _re.search(r'<a [^>]*href="https://chaseholroyd\.com/"[^>]*>\s*chaseholroyd\.com\s*</a>', footer), \
        "the demo's fixed footer must link to https://chaseholroyd.com/ with the text 'chaseholroyd.com'"
    assert _NFA in _text(footer)


def test_CHL_UX47_chat_tab_has_a_chat_with_charlie_heading():
    html = (_WEB / "index.html").read_text()
    chat = _html_block(html, r'<section id="tab-chat"[^>]*>')
    assert _re.search(r"<h1[^>]*>\s*Chat with Charlie\s*</h1>", chat), "the Chat tab needs <h1>Chat with Charlie</h1>"


def _fmt_date(*args, tz="America/Los_Angeles"):
    """Run app.js's fmtDate in node (in a US time zone, so a UTC-parsed date would slip a day)."""
    import json, os
    js = _app_js()
    m = (_re.search(r"\nfunction fmtDate\(.*?\n}\n", js, _re.S)
         or _re.search(r"\nconst fmtDate = .*?;\n", js, _re.S))
    assert m, "app.js needs one shared fmtDate helper for user-facing dates (Dec 11, 2026)"
    prog = m.group(0) + f"\nconsole.log(JSON.stringify({json.dumps(list(args))}.map((d) => fmtDate(d))));"
    r = _sp.run(["node", "-e", prog], capture_output=True, text=True, env={**os.environ, "TZ": tz})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_CHL_UX48_fmtDate_renders_month_day_year_without_a_time_zone_slip():
    got = _fmt_date("2026-12-11", "2026-10-29T14:03:12", "2026-01-02")
    assert got == ["Dec 11, 2026", "Oct 29, 2026", "Jan 2, 2026"]
    for empty in _fmt_date(None, ""):
        assert "Invalid" not in str(empty) and "NaN" not in str(empty)


def test_CHL_UX48_cards_drawer_track_record_and_portfolio_use_fmtDate():
    js = _app_js()
    raw = {
        "tradeTag (idea cards, trade blocks)": (_fn(js, "tradeTag"), ["${t.expiry}"]),
        "trackItem (track record)": (_fn(js, "trackItem"), ["esc(it.date)"]),
        "openTicker (drawer)": (_fn(js, "openTicker"), ["esc(d.history[0].date)", "esc(d.history[d.history.length - 1].date)"]),
        "loadPaper (Portfolio)": (_fn(js, "loadPaper"), ["p.opened.slice(0, 10)", "esc(p.trade.expiry"]),
    }
    problems = []
    for site, (body, bad) in raw.items():
        problems += [f"{site}: renders a raw ISO date via {b}" for b in bad if b in body]
        if "fmtDate(" not in body:
            problems.append(f"{site}: doesn't use fmtDate")
    assert problems == []


def test_CHL_UX48b_chat_trade_cards_and_screener_expiry_column_use_fmtDate():
    js = _app_js()
    chat = _fn(js, "renderChatMsg")
    screen = _fn(js, "runScreen")
    problems = []
    if "esc(t.expiry)" in chat:
        problems.append("renderChatMsg (chat trade cards): renders a raw ISO expiry via esc(t.expiry)")
    if "expires ${esc(fmtDate(t.expiry))}" not in chat:
        problems.append("renderChatMsg (chat trade cards): should read '· expires <fmtDate(expiry)>'")
    if "esc(x.trade.expiry" in screen:
        problems.append("runScreen (screener Expires column): renders a raw ISO expiry via esc(x.trade.expiry")
    if "fmtDate(x.trade.expiry)" not in screen:
        problems.append("runScreen (screener Expires column): doesn't use fmtDate")
    assert problems == []


def test_CHL_UX51_engine_status_pill_says_loading_charlies_engine():
    html = (_WEB / "index.html").read_text()
    pill = _text(_html_block(html, r'<div[^>]*id="engine-status"[^>]*>'))
    assert pill == "Loading Charlie's engine…", pill
    assert "The first visit takes a few seconds" not in html


def test_CHL_UX49_profile_done_message_points_to_todays_ideas():
    body = _fn(_app_js(), "submitProfile")
    assert "Done. Your circle is below, and Today now shows ideas for it." in body
    assert "Read ${r.resume_chars" not in body, "drop the character count from the done message"
    assert _re.search(r"""data-(?:goto|tab)=["']today["'][^>]*>\s*See today's ideas""", body), \
        "the done message needs a 'See today's ideas' link/button that opens the Today tab"


def test_CHL_UX50_copy_button_says_trade_details_not_order_details():
    js = _app_js()
    for f in ("app.js", "index.html", "static.js"):
        text = (_WEB / f).read_text()
        assert "Copy order details" not in text, f
        assert "Order details copied" not in text, f
    assert "Copy trade details" in _fn(js, "tradeActions")
    assert "Trade details copied." in js


def test_CHL_R11_build_my_profile_button_disables_while_building_and_engine_toast_sets_expectations():
    body = _fn(_app_js(), "submitProfile")
    assert _re.search(r"\.disabled = true", body), "Build my profile must be disabled while it runs"
    assert "Building…" in body, "the button must read 'Building…' while it runs"
    assert "finally" in body and _re.search(r"\.disabled = false", body) and "Build my profile" in body, \
        "the button must come back (enabled, 'Build my profile') when the build ends, even on an error"
    web = _app_js() + (_WEB / "index.html").read_text()
    assert ("Loading Charlie's engine (about 6 MB). On a phone this can take up to a minute. "
            "It's faster next time.") in web
