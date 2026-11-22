"""CHL-NAV unit half: the markup and CSS promises behind the app-style navigation (spec: staff-pm, Nov 22).

Written first, red, by qa-tdd on Nov 22 2026. The browser half is tests/e2e/test_nav_e2e.py (selector contract there).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
NFA = "Not financial advice. Paper trading only."
TABS = [("today", "Today"), ("screener", "Search"), ("chat", "Chat"), ("paper", "Trades"), ("learn", "Learn")]


def _html():
    return (WEB / "index.html").read_text()


def _block(html, open_re):
    m = re.search(open_re, html)
    assert m, open_re
    tag = re.match(r"<(\w+)", m.group(0)).group(1)
    depth = 0
    for t in re.finditer(rf"<(/?){tag}\b[^>]*>", html[m.start():]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return html[m.start(): m.start() + t.end()]
    raise AssertionError(f"unclosed {open_re}")


def _text(markup):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", re.sub(r"<svg\b.*?</svg>", "", markup, flags=re.S))).strip()


def test_CHL_NAV_1_each_tab_is_an_inline_aria_hidden_svg_over_its_word_with_ids_kept():
    html = _html()
    for key, word in TABS:
        btn = _block(html, rf'<button[^>]*data-tab="{key}"[^>]*>')
        assert f'id="tabbtn-{key}"' in btn and f'aria-controls="tab-{key}"' in btn and 'role="tab"' in btn, f"{key}: ids/roles changed"
        svgs = re.findall(r"<svg\b[^>]*>", btn)
        assert len(svgs) == 1 and 'aria-hidden="true"' in svgs[0], f"{key}: want one inline aria-hidden svg, got {svgs}"
        assert _text(btn) == word, f"{key}: visible word {_text(btn)!r}, want {word!r}"
    assert not re.search(r"material-icons|font-awesome|fontawesome|icomoon|glyphicon", html + (WEB / "styles.css").read_text(), re.I), \
        "no icon font"


def test_CHL_NAV_1_bar_padding_includes_the_safe_area_and_the_viewport_allows_it():
    css = (WEB / "styles.css").read_text()
    assert re.search(r"padding(-bottom)?\s*:[^;]*env\(safe-area-inset-bottom", css), \
        "the bottom bar's padding-bottom must include env(safe-area-inset-bottom)"
    meta = re.search(r'<meta name="viewport" content="([^"]+)"', _html()).group(1)
    assert "viewport-fit=cover" in meta, f"env(safe-area-inset-*) is 0 on iOS without viewport-fit=cover: {meta!r}"


def test_CHL_NAV_3_the_disclaimer_line_is_static_markup_with_the_exact_text():
    """The page-level disclaimer is still added by code (static index.html), not by the prompt or JS alone."""
    line = _block(_html(), r'<\w+[^>]*id="disclaimer-line"[^>]*>')
    assert NFA in _text(line)
    assert "<button" in line, "the line opens the full disclaimer, so it holds a button"
    assert "chaseholroyd.com" not in line, "CHL-NAV-14: no link home in the line"


def test_CHL_NAV_5_header_has_no_tagline_no_tabs_and_the_data_badge_moves_under_today():
    html = _html()
    header = _block(html, r"<header\b[^>]*>")
    assert "Invest in what you know" not in html, "the header tagline goes (NAV-5)"
    assert 'id="data-badge"' not in header, "the server-only data badge moves under the Today title"
    today = _block(html, r'<section id="tab-today"[^>]*>')
    badge = re.search(r'<\w+[^>]*id="data-badge"[^>]*>', today)
    assert badge and "server-only" in badge.group(0), "#data-badge sits in #tab-today and stays server-only"
    prof = _block(header, r'<button[^>]*id="profile-btn"[^>]*>')
    assert re.search(r'<svg\b[^>]*aria-hidden="true"', prof) and _text(prof) == "Profile", "Profile: person svg + the word"


def test_CHL_NAV_7_titles_in_markup():
    html = _html()
    want = {"today": "Today", "screener": "Search trades", "chat": "Chat", "paper": "Paper trades", "learn": "Learn", "profile": "Profile"}
    got = {}
    for key, title in want.items():
        sec = _block(html, rf'<section id="tab-{key}"[^>]*>')
        h1 = re.findall(r"<h1\b[^>]*>(.*?)</h1>", sec, re.S)
        got[key] = [_text(h) for h in h1]
    assert got == {k: [v] for k, v in want.items()}, got
    prof = _block(html, r'<section id="tab-profile"[^>]*>')
    assert re.search(r"<h2\b[^>]*>\s*Your circle of competence\s*</h2>", prof), "'Your circle of competence' becomes Profile's h2"


def test_CHL_NAV_8_today_markup_has_no_hero_pitch_proof_list_or_top_idea_link():
    today = _block(_html(), r'<section id="tab-today"[^>]*>')
    for gone in ("Stock ideas from what you already know", 'class="proof"', 'id="hero-top-idea"'):
        assert gone not in today, f"Today still has {gone!r}"
    js = (WEB / "app.js").read_text()
    assert "See today's top idea" not in js, "app.js still writes the top-idea link"


def test_CHL_NAV_13_chat_section_keeps_its_page_level_disclaimer():
    """NAV-13 ships as "keep" (chief of staff's safe default, Nov 22, until Chase answers; privacy-security rated
    dropping the paragraph a P1). Chat's own markup carries the exact disclaimer outside the conversation log, added
    by static code, not by a reply. test_guardrails::test_chat_panel_shows_the_disclaimer_in_markup and DS-23 stay as is."""
    chat = _block(_html(), r'<section id="tab-chat"[^>]*>')
    log = _block(chat, r'<div[^>]*id="chat-log"[^>]*>')
    page_level = chat.replace(log, "")
    assert NFA in _text(page_level), "Chat's page-level disclaimer paragraph is gone (outside #chat-log)"
