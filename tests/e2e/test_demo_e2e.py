"""M1.4: the built static demo in a real browser (Playwright, Chromium).

Runs only with CHARLIE_E2E=1 (CI's e2e job sets it) because it needs Chromium and Pyodide.
CHARLIE_CHROMIUM points at a Chromium binary; CHARLIE_PYODIDE_DIR serves a local Pyodide
instead of the CDN (for sandboxes that can't reach it).
"""
import functools
import re
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect, sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
NFA = "Not financial advice. Paper trading only."


@pytest.fixture(scope="module")
def site_url(tmp_path_factory):
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    site = build_demo.build(tmp_path_factory.mktemp("e2e") / "site", day="2026-10-22")
    query = ""
    if os.environ.get("CHARLIE_PYODIDE_DIR"):
        (site / "pyodide").symlink_to(os.environ["CHARLIE_PYODIDE_DIR"])
        query = "?pyodide=pyodide/"
    handler = functools.partial(type("Quiet", (SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}),
                                directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.handle_error = lambda *a: None  # the browser dropping a connection mid-download isn't a failure
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/index.html{query}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHARLIE_CHROMIUM") or None)
        yield b
        b.close()


@pytest.fixture
def page(browser, site_url):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(site_url)
    pg.click("#ack-btn")
    yield pg
    assert pg.errors == []
    ctx.close()


def test_every_idea_card_shows_the_disclaimer(page):
    cards = page.locator("#ideas .card")
    expect(cards.first).to_be_visible()
    assert cards.count() >= 1
    for i in range(cards.count()):
        expect(cards.nth(i).locator(".nfa").first).to_have_text(NFA)


def test_banner_says_sample_and_links_back(page):
    banner = page.locator("#demo-banner")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text("stays in this browser")
    expect(page.locator("#demo-banner a")).to_have_attribute("href", "https://chaseholroyd.com/")
    expect(page.locator("#profile-nudge")).to_contain_text("Alex Rivera, a fictional sample person")


def test_chat_panel_and_reply_show_the_disclaimer(page):
    page.click("[data-tab=chat]")
    expect(page.locator("#tab-chat .nfa").first).to_have_text(NFA)
    page.fill("#chat-input", "Tell me about Visa")
    page.keyboard.press("Enter")
    reply = page.locator("#chat-log .msg.bot").last
    expect(reply).to_contain_text(NFA, timeout=120_000)


def test_profile_shows_the_sample_and_can_load_its_resume(page):
    page.click("[data-tab=profile]")
    expect(page.locator("#profile-view h2")).to_have_text("Alex Rivera's circle (sample)")
    page.click("#use-sample")
    expect(page.locator("textarea[name=resume_text]")).to_have_value(re.compile("Registered Nurse"))


def test_reset_demo_clears_local_data(page):
    page.evaluate("localStorage.setItem('charlie:kv:sample_risk', '4')")
    page.click("#reset-demo")
    page.wait_for_load_state("load")
    expect(page.locator("#ideas .card").first).to_be_visible()
    keys = page.evaluate("Object.keys(localStorage).filter((k) => k.startsWith('charlie:'))")
    assert "charlie:kv:sample_risk" not in keys


AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


@pytest.fixture(scope="module")
def axe_source():
    path = os.environ.get("CHARLIE_AXE_JS")
    if not path:
        pytest.fail("set CHARLIE_AXE_JS to axe-core's axe.min.js (CI installs axe-core with npm)")
    return Path(path).read_text()


def _wait_for_engine_if_needed(page):
    page.wait_for_timeout(300)
    page.wait_for_function("document.querySelector('#engine-status').classList.contains('hidden')", timeout=120_000)
    page.wait_for_timeout(300)


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", [(390, 844), (1280, 800)])
def test_every_tab_passes_axe_and_fits(browser, site_url, axe_source, scheme, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
    page = ctx.new_page()
    page.goto(site_url)
    expect(page.locator("#ideas .card").first).to_be_visible()
    page.click("#ack-btn")
    problems = []
    for tab in ["today", "profile", "screener", "chat", "paper", "learn"]:
        page.click(f"[data-tab={tab}]")
        _wait_for_engine_if_needed(page)
        if page.evaluate("document.documentElement.scrollWidth > innerWidth"):
            problems.append(f"{tab}: horizontal overflow")
        clipped = page.evaluate("""[...document.querySelectorAll('.tab.active svg.payoff')].filter((svg) => {
            const r = svg.getBoundingClientRect(), box = svg.parentElement.getBoundingClientRect();
            return r.width < 50 || r.left < box.left - 1 || r.right > box.right + 1;
        }).length""")
        if clipped:
            problems.append(f"{tab}: {clipped} clipped payoff chart(s)")
        page.add_script_tag(content=axe_source)
        found = page.evaluate("(tags) => axe.run(document, {runOnly: tags}).then((r) => r.violations.map((v) => "
                              "v.id + ' ' + v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(', ')))", AXE_TAGS)
        problems += [f"{tab}: {v}" for v in found]
    ctx.close()
    assert problems == []
