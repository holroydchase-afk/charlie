"""Shared fixtures for the browser tests on the built static demo (M1.4, M1.11).

The tests run only with CHARLIE_E2E=1 (each test module skips itself otherwise), so this file
imports Playwright lazily and never fails collection on a machine without it.
CHARLIE_CHROMIUM points at a Chromium binary; CHARLIE_PYODIDE_DIR (an unpacked pyodide npm
package) self-hosts the runtime as the Pages build does. Without it Pyodide loads from the CDN.
"""
import functools
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NFA = "Not financial advice. Paper trading only."


@pytest.fixture(scope="session")
def site_dir(tmp_path_factory):
    """The built demo folder (built once per session)."""
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    # With CHARLIE_PYODIDE_DIR the runtime is self-hosted, exactly as pages.yml builds it.
    pyodide = os.environ.get("CHARLIE_PYODIDE_DIR")
    return Path(build_demo.build(tmp_path_factory.mktemp("e2e") / "site", day="2026-10-22",
                                 pyodide_dir=Path(pyodide) if pyodide else None))


@pytest.fixture(scope="session")
def site_url(site_dir):
    site = site_dir
    handler = functools.partial(type("Quiet", (SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}),
                                directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.handle_error = lambda *a: None  # the browser dropping a connection mid-download isn't a failure
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/index.html"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHARLIE_CHROMIUM") or None)
        yield b
        b.close()


def open_page(browser, site_url, width=390, height=844, scheme=None):
    """A fresh context at the given viewport, with page errors and off-site requests recorded."""
    ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme or "light")
    pg = ctx.new_page()
    pg.errors, pg.external = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    origin = site_url.rsplit("/", 1)[0] + "/"
    pg.on("request", lambda r: None if r.url.startswith((origin, "data:")) else pg.external.append(r.url))
    return ctx, pg


def check_page_clean(pg):
    assert pg.errors == []
    if os.environ.get("CHARLIE_PYODIDE_DIR"):  # self-hosted, as on Pages: nothing may leave the site
        assert pg.external == []


@pytest.fixture
def make_page(browser, site_url):
    """Factory: make_page(width, height, scheme) -> page. Closed (and checked clean unless
    check=False) after the test."""
    made = []

    def make(width=390, height=844, scheme=None, check=True):
        ctx, pg = open_page(browser, site_url, width, height, scheme)
        made.append((ctx, pg, check))
        return pg
    yield make
    for ctx, pg, check in made:
        try:
            if check:
                check_page_clean(pg)
        finally:
            ctx.close()


@pytest.fixture
def page(browser, site_url):
    ctx, pg = open_page(browser, site_url)
    pg.goto(site_url)
    pg.click("#ack-btn")
    yield pg
    check_page_clean(pg)
    ctx.close()
