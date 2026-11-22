"""CHL-DEMO-BAR (intake #35): the studio demo bar replaces the static demo's old banner.

Spec: pm-tools docs/DEMO-BANNER.md. These checks need no browser; tests/e2e/test_demo_bar_e2e.py
checks what a visitor sees. The bar is static-only markup, hidden until app.js finds the static
demo, so the local app never shows it even if its script fails.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
HOME = "https://chaseholroyd.com/"
GITHUB = "https://github.com/holroydchase-afk/charlie"
DRAWER_COPY = ("This is the real Charlie, running on made-up sample data. Anything you change is saved only "
               "in this browser and is never sent anywhere. Reset demo puts the sample data back.")
CONFIRM_COPY = "Put the sample data back? Your changes will be lost."


def _html():
    return (WEB / "index.html").read_text()


def _bar():
    m = re.search(r'<section\b[^>]*aria-label="Demo"[^>]*>.*?</section>', _html(), re.S)
    assert m, 'index.html needs the demo bar: <section aria-label="Demo" ...>'
    return m.group(0)


def _text(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment)).strip()


def test_CHL_DEMO_BAR_1_bar_is_static_only_and_hidden_by_default():
    open_tag = re.match(r"<section\b[^>]*>", _bar()).group(0)
    cls = re.search(r'class="([^"]*)"', open_tag)
    assert cls and {"static-only", "hidden"} <= set(cls.group(1).split()), open_tag
    assert "role=" not in open_tag, "a <section> with a name is already a region; don't override its role"


def test_CHL_DEMO_BAR_2_old_banner_is_gone_so_there_is_one_demo_notice():
    html, js, css = _html(), (WEB / "app.js").read_text(), (WEB / "styles.css").read_text()
    assert 'id="demo-banner"' not in html and "demo-banner" not in css
    assert "reset-demo" not in html and "#reset-demo" not in js
    assert len(re.findall(r'aria-label="Demo"', html)) == 1


def test_CHL_DEMO_BAR_3_collapsed_bar_has_back_link_and_one_toggle():
    bar = _bar()
    first_link = re.search(r"<a\b[^>]*>(.*?)</a>", bar, re.S)
    assert first_link and _text(first_link.group(1)) == "← Portfolio", "the way back comes first: ← Portfolio"
    assert f'href="{HOME}"' in first_link.group(0)
    toggle = re.search(r'<button\b[^>]*aria-label="Demo details"[^>]*>', bar)
    assert toggle, 'one toggle button named "Demo details"'
    t = toggle.group(0)
    assert 'aria-expanded="false"' in t, "collapsed on load"
    ctl = re.search(r'aria-controls="([^"]+)"', t)
    assert ctl, "the toggle names the drawer it controls"
    panel = re.search(rf'<[^>]*id="{re.escape(ctl.group(1))}"[^>]*>', bar)
    assert panel and re.search(r"\bhidden\b", panel.group(0)), "the drawer exists and starts hidden"
    assert bar.index(first_link.group(0)) < bar.index(t), "the back link sits before the toggle, not inside it"
    assert re.search(r">\s*Demo\s*<", bar), "a Demo badge"
    assert "Sample data" in bar and "changes stay in this browser" in bar
    assert "Details" in bar


def test_CHL_DEMO_BAR_4_drawer_has_standard_copy_reset_confirm_and_full_way_back():
    bar = _bar()
    text = _text(bar)
    assert DRAWER_COPY in text
    assert CONFIRM_COPY in text
    for label in ("Reset demo", "Reset", "Keep"):
        assert re.search(rf"<button\b[^>]*>\s*{re.escape(label)}\s*</button>", bar), f"{label} button"
    # CHL-DEMO-R3: the drawer's way back names the place, not the domain.
    back = re.search(r"<a\b[^>]*>\s*← Back to Chase's portfolio\s*</a>", bar)
    assert back and f'href="{HOME}"' in back.group(0), "drawer's full way back goes to the same place"
    # CHL-DEMO-R4: the optional third action, a plain link to the public repo, after the way back.
    gh = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>\s*Code on GitHub\s*</a>', bar)
    assert gh, "the drawer links to the code: <a href=GITHUB>Code on GitHub</a>"
    assert gh.group(1) == GITHUB
    assert "target=" not in gh.group(0) and "onclick" not in gh.group(0), "a plain link"
    reset_at = re.search(r"<button\b[^>]*>\s*Reset demo\s*</button>", bar).start()
    assert reset_at < back.start() < gh.start(), "order: Reset demo, the way back, Code on GitHub"
    # Every link in the bar goes to the portfolio, except exactly one to the repo (no other hosts).
    hrefs = re.findall(r'href="([^"]+)"', bar)
    assert hrefs.count(GITHUB) == 1, hrefs
    for href in hrefs:
        assert href in (HOME, GITHUB), href


def test_CHL_DEMO_BAR_5_app_js_asks_inline_and_says_restored():
    js = (WEB / "app.js").read_text()
    assert "Sample data restored." in js
    # The only window.confirm() left is "Delete all your Charlie data"; reset asks inline in the drawer.
    calls = re.findall(r"\bconfirm\((.{0,40})", js)
    assert all("Delete all" in c for c in calls), calls


def test_CHL_DEMO_BAR_6_bar_css_uses_product_tokens_not_the_accent():
    css = (WEB / "styles.css").read_text()
    rules = re.findall(r"[^{}]*\.demo-bar[^{}]*\{[^}]*\}", css)
    assert rules, "styles.css styles the .demo-bar"
    body = " ".join(rules)
    assert "--accent" not in body and "--warn" not in body, "the bar and badge never use the accent or warn colors"
    # CHL-DS-1: Charlie's --panel became the studio --surface token.
    assert "var(--surface" in body and "var(--ink" in body, "surface and text come from the studio tokens"


def test_CHL_DEMO_R1_header_data_badge_is_hidden_in_the_static_demo_only():
    # The demo bar already says "Sample data"; the header badge would say it again. It stays in the local
    # app, where it tells mock from live. server-only is what app.js hides when status.static.
    tag = re.search(r'<[^>]*id="data-badge"[^>]*>', _html())
    assert tag, "the header keeps #data-badge for the local app"
    cls = re.search(r'class="([^"]*)"', tag.group(0)).group(1).split()
    assert "server-only" in cls and "hidden" not in cls, tag.group(0)
    js = (WEB / "app.js").read_text()
    assert re.search(r'\$\$\("\.server-only"\)\.forEach\(\(el\) => el\.classList\.add\("hidden"\)\)', js)


def test_CHL_DEMO_R2_bar_content_uses_the_headers_left_padding_where_the_header_does():
    """CHL-NAV-11 update: under 760px the 56px header pads max(var(--s4), safe-area-left) and the bar follows it.
    From 760px the header is a fixed sidebar and the bar sits over the main column, so the bar's row and drawer
    pad by main's own left padding there (tests/e2e/test_demo_bar_e2e.py checks the rendered edge)."""
    css = (WEB / "styles.css").read_text()
    phone = r"max\(var\(--s4\),\s*env\(safe-area-inset-left,\s*0px\)\)"
    top = re.search(r"(?m)^\.top\s*\{([^}]*)\}", css)
    assert top and re.search(r"padding:[^;]*" + phone, top.group(1)), "the phone header pads max(var(--s4), safe-area-left)"
    row = re.search(r"(?m)^\.demo-bar__row\s*\{([^}]*)\}", css)
    assert row and re.search(r"padding-left:\s*" + phone, row.group(1)), "the phone bar pads like the header"
    # main's left padding from 760px up: its own rule in the 760px block, else the base rule.
    block = "".join(m.group(1) for m in re.finditer(r"@media \(min-width: 76[01]px\)\s*\{(.*?)\n\}", css, re.S))
    main = re.search(r"(?m)^\s*main\s*\{([^}]*)\}", block) or re.search(r"(?m)^main\s*\{([^}]*)\}", css)
    left = re.search(r"padding-left:\s*([^;]+)", main.group(1))
    if left:
        want = left.group(1)
    else:
        pads = re.search(r"padding:\s*([^;]+)", main.group(1)).group(1).split()
        want = pads[{1: 0, 2: 1, 3: 1, 4: 3}[len(pads)]]
    want_var = re.search(r"var\(--s\d\)", want).group(0)
    for sel in (".demo-bar__row", ".demo-bar__panel"):
        rules = [r.group(1) for r in re.finditer(re.escape(sel) + r"\s*\{([^}]*)\}", block)]
        assert rules and any(re.search(r"padding-left:[^;]*" + re.escape(want_var), r) for r in rules), \
            f"{sel} pads {want_var} (main's left padding) from 760px up"
