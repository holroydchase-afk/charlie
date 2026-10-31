"""M1.14 Demo verified: the built demo as Pages will serve it (Chromium). Runs with CHARLIE_E2E=1.

DEMO-SUBPATH: Pages serves the demo at chaseholroyd.com/charlie/, so every file the page asks for
must be relative. The built site is served under /charlie/ and must load, start the engine and
open the drawer with no failed request and nothing outside /charlie/.
DEMO-PHONE-2S: on a phone profile (4x CPU throttle, slow 4G: 150 ms RTT, 1.6 Mbps down) with a
cold cache and gzip (as Pages serves text files), Today's first idea card paints in under 2 s.
"""
import functools
import gzip
import io
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

if os.environ.get("CHARLIE_E2E") != "1":
    pytest.skip("browser tests run with CHARLIE_E2E=1", allow_module_level=True)

from playwright.sync_api import expect  # noqa: E402

NFA = "Not financial advice. Paper trading only."
ENGINE = 120_000
GZ_TYPES = ("text/", "application/javascript", "application/json")


class _Handler(SimpleHTTPRequestHandler):
    gzip_text = False
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm",
                      ".js": "application/javascript", ".json": "application/json"}

    def log_message(self, *a):
        pass

    def send_head(self):  # gzip text files, as GitHub Pages does
        path = self.translate_path(self.path)
        ctype = self.guess_type(path)
        if (not self.gzip_text or os.path.isdir(path) or not os.path.isfile(path)
                or "gzip" not in self.headers.get("Accept-Encoding", "") or not ctype.startswith(GZ_TYPES)):
            return super().send_head()
        with open(path, "rb") as f:
            data = gzip.compress(f.read(), 6)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        return io.BytesIO(data)


def _serve_under_charlie(site_dir, tmp_path, gzip_text=False):
    root = tmp_path / "pages"
    root.mkdir()
    (root / "charlie").symlink_to(site_dir, target_is_directory=True)
    handler = functools.partial(type("H", (_Handler,), {"gzip_text": gzip_text}), directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.handle_error = lambda *a: None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_DEMO_SUBPATH_demo_works_when_served_under_charlie(browser, site_dir, tmp_path):
    server, origin = _serve_under_charlie(site_dir, tmp_path)
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    bad, outside, errors = [], [], []
    pg.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    pg.on("requestfailed", lambda r: bad.append(f"failed {r.url}"))
    pg.on("request", lambda r: None if r.url.startswith((origin + "/charlie/", "data:")) else outside.append(r.url))
    pg.on("pageerror", lambda e: errors.append(str(e)))
    try:
        pg.goto(origin + "/charlie/")
        expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
        pg.click("#ack-btn")
        pg.wait_for_function("() => document.querySelector('#engine-status').classList.contains('hidden')",
                             timeout=ENGINE)
        pg.locator("#ideas .card").first.locator("[data-ticker]").first.click()
        expect(pg.locator("#drawer .nfa").first).to_have_text(NFA, timeout=ENGINE)
        pg.keyboard.press("Escape")
        pg.click("[data-tab=chat]")
        pg.fill("#chat-input", "Tell me about Visa")
        pg.keyboard.press("Enter")
        expect(pg.locator("#chat-log .msg.bot").last).to_contain_text(NFA, timeout=ENGINE)
        assert bad == [], bad
        assert outside == [], outside
        assert errors == [], errors
    finally:
        ctx.close()
        server.shutdown()


PHONE_NET = {"offline": False, "latency": 150, "downloadThroughput": 1.6e6 / 8, "uploadThroughput": 750e3 / 8}
CARD_TIME = """
window.__card = null;
new MutationObserver(() => {
  if (window.__card === null && document.querySelector('#ideas .card')) window.__card = performance.now();
}).observe(document, {subtree: true, childList: true});
"""


def test_DEMO_PHONE_2S_today_paints_under_2s_on_a_throttled_phone(browser, site_dir, tmp_path):
    server, origin = _serve_under_charlie(site_dir, tmp_path, gzip_text=True)
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                              device_scale_factor=3)
    pg = ctx.new_page()
    try:
        cdp = ctx.new_cdp_session(pg)
        cdp.send("Network.enable")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        cdp.send("Network.emulateNetworkConditions", PHONE_NET)
        pg.add_init_script(CARD_TIME)
        pg.goto(origin + "/charlie/")
        pg.wait_for_function("() => window.__card !== null", timeout=30_000)
        ms = pg.evaluate("() => window.__card")
        assert ms < 2000, f"Today's first idea card painted at {ms:.0f} ms on the throttled phone profile"
    finally:
        ctx.close()
        server.shutdown()


# ---------------------------------------------------------------- M1.14 review fixes (CHL-UX37 to UX39, CHL-R9)
LAPTOP = (1280, 800)


def _seed_option_position():
    import json
    from datetime import date

    from charlie.data.market import MarketData
    from charlie.options_math import occ_symbol
    md = MarketData(mode="mock", today=date(2026, 10, 22))  # the e2e build's pinned day
    unh = md.quote("UNH")["price"]
    exp = date(2026, 11, 6)
    strike = round(unh * 0.8)
    t = {"strategy": "cash_secured_put", "label": "Cash-secured put", "symbol": "UNH", "spot": unh,
         "legs": [{"action": "sell", "instrument": "put", "symbol": occ_symbol("UNH", exp, "put", strike),
                   "strike": float(strike), "expiry": exp.isoformat(), "qty": 1, "price": 1.5}],
         "contracts": 1, "net_premium": 1.5, "max_profit": 150.0, "max_loss": (strike - 1.5) * 100,
         "breakeven": strike - 1.5, "capital_required": strike * 100.0, "dte": 15, "expiry": exp.isoformat(),
         "management": ["Close early once you've captured ~50% of the premium."], "disclaimer": NFA}
    rows = [{"id": "m114csp001", "opened": "2026-10-01T15:00:00+00:00", "symbol": "UNH",
             "strategy": "cash_secured_put", "trade": t, "entry_value": -150.0, "status": "open",
             "closed": None, "exit_value": None, "note": ""}]
    return f"localStorage.setItem('charlie:positions', {json.dumps(json.dumps(rows))});"


def _open(make_page, site_url, size, init_script=None):
    pg = make_page(*size)
    if init_script:
        pg.add_init_script(init_script)
    pg.goto(site_url)
    expect(pg.locator("#ideas .card").first).to_be_visible(timeout=ENGINE)
    pg.click("#ack-btn")
    return pg


LINES = """(el) => {  // how many rendered lines the element's own text takes
  const r = document.createRange(); r.selectNodeContents(el);
  return new Set([...r.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top))).size;
}"""


def test_CHL_UX37_laptop_banner_says_reset_demo_with_a_space(make_page, site_url):
    # CHL-DEMO-BAR: Reset demo now lives in the demo bar's drawer.
    pg = _open(make_page, site_url, LAPTOP)
    bar = pg.get_by_role("region", name="Demo")
    bar.get_by_role("button", name="Demo details").click()
    btn = bar.get_by_role("button", name="Reset demo", exact=True)
    expect(btn).to_be_visible()
    assert btn.inner_text().strip() == "Reset demo", repr(btn.inner_text())


def test_CHL_UX38_laptop_paper_table_dates_stay_on_one_line(make_page, site_url):
    pg = _open(make_page, site_url, LAPTOP, init_script=_seed_option_position())
    pg.click("[data-tab=paper]")
    row = pg.locator("#paper-list tbody tr:visible").first
    expect(row).to_be_visible(timeout=ENGINE)
    opened = row.locator("td").first
    expires = row.locator("td .muted", has_text="expires")
    assert opened.evaluate(LINES) == 1, opened.inner_text()
    assert expires.evaluate(LINES) == 1, expires.inner_text()


def test_CHL_UX39_laptop_track_record_columns_line_up(make_page, site_url):
    pg = _open(make_page, site_url, LAPTOP)
    expect(pg.locator("#track-record .track-item").first).to_be_visible(timeout=ENGINE)
    lefts = pg.locator("#track-record .track-item:visible .ti-grid").evaluate_all(
        "(els) => els.map((e) => Math.round(e.getBoundingClientRect().left))")
    assert len(lefts) >= 3 and max(lefts) - min(lefts) <= 1, lefts
    widths = pg.locator("#track-record .track-item:visible .ti-grid").evaluate_all(
        "(els) => els.map((e) => Math.round(e.getBoundingClientRect().width))")
    assert max(widths) - min(widths) <= 1, widths


@pytest.mark.parametrize("size", [(390, 844), LAPTOP], ids=["390x844", "1280x800"])
def test_CHL_R9_screener_results_and_paper_positions_show_the_disclaimer(make_page, site_url, size):
    pg = _open(make_page, site_url, size, init_script=_seed_option_position())
    pg.click("[data-tab=screener]")
    expect(pg.locator("#screen-results [data-row]:visible").first).to_be_visible(timeout=ENGINE)
    expect(pg.locator("#screen-results .nfa")).to_have_text(NFA)
    pg.click("[data-tab=paper]")
    expect(pg.locator("#paper-list .pos-card:visible, #paper-list tbody tr:visible").first).to_be_visible(timeout=ENGINE)
    expect(pg.locator("#paper-list .nfa")).to_have_text(NFA)
