"""M1.7: the tab bar follows the ARIA tabs pattern (axe flagged buttons inside role=tablist)."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
TABS = ["today", "screener", "chat", "paper", "learn"]  # CHL-DS-25: five tabs; Profile opens from the header
VIEWS = TABS + ["profile"]  # every view a #hash can open


def test_tab_buttons_and_panels_are_wired():
    html = (WEB / "index.html").read_text()
    tablist = html.split('role="tablist"', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r'<button[^>]*data-tab="([a-z]+)"', tablist) == TABS, "CHL-DS-25: exactly five tabs, in order"
    for name in TABS:
        btn = re.search(rf'<button[^>]*data-tab="{name}"[^>]*>', html.split('role="tablist"', 1)[1]).group(0)
        assert 'role="tab"' in btn and f'id="tabbtn-{name}"' in btn and f'aria-controls="tab-{name}"' in btn
        panel = re.search(rf'<section id="tab-{name}"[^>]*>', html).group(0)
        assert 'role="tabpanel"' in panel and f'aria-labelledby="tabbtn-{name}"' in panel


def test_show_tab_updates_selection_and_roving_focus():
    js = (WEB / "app.js").read_text()
    body = re.search(r"function showTab\(.*?\n}\n", js, re.S).group(0)
    assert "aria-selected" in body and "tabIndex" in body
    assert "ArrowRight" in js and "ArrowLeft" in js


def test_no_placeholder_text_or_dead_links():
    for f in ("index.html", "app.js"):
        text = (WEB / f).read_text()
        assert not re.search(r"\b(TODO|FIXME|TBD|lorem ipsum)\b", text, re.I), f
        for href in re.findall(r'href="([^"]*)"', text):
            if href.startswith("#"):
                assert href[1:] in VIEWS, f"{f}: {href} goes nowhere"
            elif href == "https://github.com/holroydchase-afk/charlie":  # CHL-DEMO-R4: exactly the public repo
                continue
            else:
                assert href.startswith(("https://chaseholroyd.com/", "data:image/", "/static/")), f"{f}: {href}"
