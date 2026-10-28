"""M1.4: the built static demo in a real browser (Playwright, Chromium). Fixtures: conftest.py.

Runs only with CHARLIE_E2E=1 (CI's e2e job sets it) because it needs Chromium and Pyodide.
CHARLIE_CHROMIUM points at a Chromium binary; CHARLIE_PYODIDE_DIR (an unpacked pyodide npm
package) self-hosts the runtime as the Pages build does. Without it Pyodide loads from the CDN.
"""
import re
import os
from pathlib import Path

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

NFA = "Not financial advice. Paper trading only."


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


def test_first_screen_and_chat_starters_work_before_the_engine_loads(browser, site_url):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.route("**/pyodide.js", lambda route: route.abort())  # the engine never arrives
    page.goto(site_url)
    page.click("#ack-btn")
    cards = page.locator("#ideas .card")
    expect(cards.first).to_be_visible()
    page.click("[data-tab=chat]")
    page.click(".chip[data-q='How does the risk slider work?']")
    expect(page.locator("#chat-log .msg.bot").last).to_contain_text("Not financial advice. Paper trading only.")
    expect(page.locator("#chat-log .msg.bot").last).to_contain_text("level")
    ctx.close()
