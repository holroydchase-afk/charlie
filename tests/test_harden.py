"""M1.12 hardening: failing-first tests for the privacy-security review (CHL-PS1 to PS8, PS11, PS12),
the core-flow coverage gaps in charlie/handlers.py, and an end-to-end "no resume in the logs" check.
The re-check added CHL-PS14 (PDF content-stream bomb) and CHL-PS15 (malformed holdings); their tests are at the end.

Findings and their Given/When/Then are in the M1.12 privacy-security review. Deferred to M1.13 or
later (no tests here): CHL-PS9 (chat disclosure line and explicit key check), CHL-PS10 (demo keeps
resume_text in localStorage), CHL-PS13 (dependency minimums, lockfile, pip-audit).

Only fictional data is used: the people in samples/ and made-up strings. Nothing here touches the
network; the Playwright test runs only with CHARLIE_E2E=1, like tests/e2e.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
import zipfile
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from charlie.browser_store import BrowserStore
from charlie.data.market import MarketData
from charlie.handlers import Api
from charlie.store import Store

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
DAY = date(2026, 10, 22)
LOOPBACK = "http://127.0.0.1:8000"
MB = 1_000_000


# ============================================================ shared fixtures and helpers

class FakeStorage:
    def __init__(self):
        self.items = {}

    def getItem(self, k):
        return self.items.get(k)

    def setItem(self, k, v):
        self.items[k] = v

    def removeItem(self, k):
        self.items.pop(k, None)


@pytest.fixture
def mock_md(tmp_path):
    return MarketData(mode="mock", today=DAY, cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "t.db"


@pytest.fixture
def client(db_path, monkeypatch, mock_md):
    """The local app as a browser on the same machine sees it: Host 127.0.0.1:8000."""
    from charlie import server
    monkeypatch.setattr(server, "store", Store(str(db_path)))
    monkeypatch.setattr(server, "md", lambda: mock_md)
    return TestClient(server.app, base_url=LOOPBACK, raise_server_exceptions=False)


@pytest.fixture
def static_api(mock_md):
    """The browser router (static demo) on a localStorage-shaped store."""
    return Api(BrowserStore(FakeStorage()), mock_md, static=True)


def _body(r):
    try:
        return r.json()
    except ValueError:
        return {"detail": r.text}


def _call(via, client, static_api, method, path, body=None, form=None):
    """One request through the server (via="client") or the demo's router (via="route")."""
    if via == "route":
        return static_api.route(method, path, body=form if form is not None else body)
    if form is not None:
        r = client.request(method, path, data=form)
    elif body is not None:
        r = client.request(method, path, json=body)
    else:
        r = client.request(method, path)
    return r.status_code, _body(r)


def _real_trade(md, symbol="KO", strategy="shares", capital=25000, level=3):
    from charlie.strategies import build
    return build(strategy, symbol, md.quote(symbol)["price"], md.chain(symbol), capital, level)


def _build_demo():
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import build_demo
    finally:
        sys.path.pop(0)
    return build_demo


def _check_site(site, *flags):
    return subprocess.run([sys.executable, str(ROOT / "tools" / "check_site.py"), str(site), *flags],
                          capture_output=True, text=True)


@pytest.fixture
def fake_pyodide(tmp_path):
    d = tmp_path / "pyodide-pkg"
    d.mkdir()
    for name in _build_demo().PYODIDE_FILES:
        (d / name).write_text(f"// {name}\n")
    return d


@pytest.fixture
def self_hosted_site(tmp_path, fake_pyodide):
    return _build_demo().build(tmp_path / "site", day="2026-10-22", pyodide_dir=fake_pyodide)


CSP_META = re.compile(r'<meta[^>]+http-equiv=["\']Content-Security-Policy["\'][^>]*>', re.I)


def _csp(html: str) -> dict[str, list[str]]:
    """The directives of the page's meta CSP, as {directive: [sources]} ({} when there is none)."""
    m = CSP_META.search(html)
    if not m:
        return {}
    content = re.search(r'content=(["\'])(.*?)\1', m.group(0), re.S)
    out = {}
    for part in (content.group(2) if content else "").split(";"):
        bits = part.split()
        if bits:
            out[bits[0].lower()] = bits[1:]
    return out


GOOD_CSP = ('<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; '
            "script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'\">")


def _ensure_good_csp(site: Path) -> None:
    """Give a built site a valid CSP, so a doctored test fails only for the one thing it breaks."""
    html = (site / "index.html").read_text()
    html = CSP_META.sub("", html)
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n  ' + GOOD_CSP, 1)
    (site / "index.html").write_text(html)


def _strip_pyodide_param(site: Path) -> None:
    js = (site / "static.js").read_text()
    js = re.sub(r'params\.get\(["\']pyodide["\']\)\s*\|\|\s*', "", js)
    (site / "static.js").write_text(js)


# ============================================================ CHL-PS1 public demo can't be pointed at another script

PARAM_READ = re.compile(r'\.get\(\s*["\']pyodide["\']\s*\)')
ORIGIN_GUARD = re.compile(r"\.origin\s*===?\s*location\.origin|location\.origin\s*===?\s*[^;]*\.origin")


def test_CHL_PS1_self_hosted_static_js_has_no_unguarded_pyodide_override(self_hosted_site):
    js = (self_hosted_site / "static.js").read_text()
    if PARAM_READ.search(js):
        assert ORIGIN_GUARD.search(js), (
            "the shipped static.js still reads ?pyodide= into a script URL with no same-origin check")


def test_CHL_PS1_self_hosted_index_html_has_a_strict_meta_csp(self_hosted_site):
    csp = _csp((self_hosted_site / "index.html").read_text())
    assert csp, "the built index.html has no Content-Security-Policy meta tag"
    assert csp.get("default-src") == ["'self'"]
    assert set(csp.get("script-src", [])) == {"'self'", "'wasm-unsafe-eval'"}, csp.get("script-src")
    assert csp.get("connect-src") == ["'self'"], csp.get("connect-src")
    assert csp.get("object-src") == ["'none'"]
    assert csp.get("base-uri") == ["'none'"]


def test_CHL_PS1_cdn_build_csp_allows_only_the_pyodide_cdn(tmp_path):
    out = _build_demo().build(tmp_path / "site", day="2026-10-22")
    csp = _csp((out / "index.html").read_text())
    assert csp, "the CDN build's index.html has no Content-Security-Policy meta tag"
    extra = set(csp.get("script-src", [])) - {"'self'", "'wasm-unsafe-eval'"}
    assert extra == {"https://cdn.jsdelivr.net"}, csp.get("script-src")
    assert set(csp.get("connect-src", [])) <= {"'self'", "https://cdn.jsdelivr.net"}


def test_CHL_PS1_check_site_passes_a_clean_self_hosted_build(self_hosted_site):
    """Guard (passes today, must keep passing): a fixed build passes the fixed check."""
    r = _check_site(self_hosted_site, "--no-cdn")
    assert r.returncode == 0, r.stdout + r.stderr


def test_CHL_PS1_check_site_fails_when_the_csp_meta_is_missing(self_hosted_site):
    _strip_pyodide_param(self_hosted_site)
    html = CSP_META.sub("", (self_hosted_site / "index.html").read_text())
    (self_hosted_site / "index.html").write_text(html)
    r = _check_site(self_hosted_site, "--no-cdn")
    assert r.returncode == 1, "check_site.py passed a site whose index.html has no CSP"
    assert re.search(r"Content-Security-Policy|CSP", r.stdout), r.stdout


def test_CHL_PS1_check_site_fails_on_a_weak_csp(self_hosted_site):
    _strip_pyodide_param(self_hosted_site)
    _ensure_good_csp(self_hosted_site)
    html = (self_hosted_site / "index.html").read_text().replace("script-src 'self'", "script-src * 'self'")
    (self_hosted_site / "index.html").write_text(html)
    r = _check_site(self_hosted_site, "--no-cdn")
    assert r.returncode == 1, "check_site.py passed a CSP whose script-src allows any host"
    assert "script-src" in r.stdout, r.stdout


def test_CHL_PS1_check_site_fails_when_static_js_reads_the_pyodide_param(self_hosted_site):
    _ensure_good_csp(self_hosted_site)
    js = (self_hosted_site / "static.js").read_text()
    js = re.sub(r"const base = [^;]+;", 'const base = params.get("pyodide") || "pyodide/";', js, count=1)
    (self_hosted_site / "static.js").write_text(js)
    r = _check_site(self_hosted_site, "--no-cdn")
    assert r.returncode == 1, "check_site.py passed a static.js that loads a script from ?pyodide="
    assert "pyodide" in r.stdout.lower(), r.stdout


@pytest.mark.skipif(os.environ.get("CHARLIE_E2E") != "1", reason="browser test: set CHARLIE_E2E=1 (see tests/e2e)")
def test_CHL_PS1_e2e_pyodide_param_never_reaches_another_host(self_hosted_site):
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from playwright.sync_api import sync_playwright

    handler = functools.partial(type("Quiet", (SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}),
                                directory=str(self_hosted_site))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.handle_error = lambda *a: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{httpd.server_port}/"
    off_site = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=os.environ.get("CHARLIE_CHROMIUM") or None)
            pg = b.new_page()
            pg.route("**/*", lambda route: route.continue_() if route.request.url.startswith((origin, "data:"))
                     else (off_site.append(route.request.url), route.abort()))
            pg.goto(origin + "index.html?pyodide=https://attacker.example/", wait_until="load")
            pg.wait_for_timeout(3000)  # app.js calls start() after its first render
            srcs = pg.eval_on_selector_all("script[src]", "els => els.map(e => e.src)")
            b.close()
    finally:
        httpd.shutdown()
    assert not [u for u in off_site if "attacker.example" in u], off_site
    assert all(s.startswith(origin) for s in srcs), srcs


# ============================================================ CHL-PS2 DNS rebinding and other localhost ports

def test_CHL_PS2_get_with_a_foreign_host_header_is_refused(client):
    r = client.get("/api/profile", headers={"host": "evil.test:8000"})
    assert r.status_code in (400, 403), r.status_code


def test_CHL_PS2_rebinding_delete_all_is_refused_and_the_profile_survives(client):
    assert client.post("/api/profile", data={"resume_text": "Fictional nurse at a hospital", "capital": "30000"}).status_code == 200
    r = client.delete("/api/profile?all=true", headers={"host": "evil.test:8000", "origin": "http://evil.test:8000"})
    assert r.status_code in (400, 403), r.status_code
    assert client.get("/api/profile").json()["saved"] is True


def test_CHL_PS2_rebinding_post_is_refused(client):
    r = client.post("/api/profile", data={"resume_text": "x"},
                    headers={"host": "evil.test:8000", "origin": "http://evil.test:8000"})
    assert r.status_code in (400, 403), r.status_code


def test_CHL_PS2_origin_on_another_localhost_port_is_refused(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:5173"):
        r = client.post("/api/profile", data={"resume_text": "x"}, headers={"origin": origin})
        assert r.status_code == 403, (origin, r.status_code)
        r = client.delete("/api/profile?all=true", headers={"origin": origin})
        assert r.status_code == 403, (origin, r.status_code)


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "[::1]:8000"])
def test_CHL_PS2_loopback_hosts_are_allowed(client, host):
    """Guard (passes today, must keep passing): the real local app still works on every loopback name."""
    assert client.get("/api/profile", headers={"host": host}).status_code == 200
    assert client.get("/api/status", headers={"host": host}).status_code == 200


@pytest.mark.parametrize("origin", ["http://127.0.0.1:8000", "http://localhost:8000"])
def test_CHL_PS2_same_port_loopback_origin_can_write(client, origin):
    """Guard (passes today, must keep passing)."""
    r = client.post("/api/profile", data={"resume_text": "x"}, headers={"origin": origin})
    assert r.status_code == 200, r.text


def test_CHL_PS2_real_cross_site_origin_still_refused(client):
    """Guard (passes today)."""
    r = client.post("/api/profile", data={"resume_text": "x"}, headers={"origin": "https://evil.example.com"})
    assert r.status_code == 403


# ============================================================ CHL-PS3 decompression bombs and oversized text

def _docx_zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


_CT = (b'<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       b'<Default Extension="xml" ContentType="application/xml"/>'
       b'<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
_RELS = (b'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
         b'Target="word/document.xml"/></Relationships>')


def _docx_bomb(unpacked: int = 25 * MB) -> bytes:
    """A small .docx whose document.xml unpacks to `unpacked` bytes (a decompression bomb)."""
    head = b'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
    tail = b"</w:t></w:r></w:p></w:body></w:document>"
    return _docx_zip({"[Content_Types].xml": _CT, "_rels/.rels": _RELS,
                      "word/document.xml": head + b"A" * unpacked + tail})


def _docx_many_members(n: int = 250) -> bytes:
    members = {"[Content_Types].xml": _CT, "_rels/.rels": _RELS,
               "word/document.xml": b'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>'}
    members.update({f"word/media/pad{i}.xml": b"<x/>" for i in range(n)})
    return _docx_zip(members)


@pytest.fixture
def docx_spy(monkeypatch):
    """Records every python-docx parse; a bomb must be refused before python-docx ever sees it."""
    import docx
    calls, real = [], docx.Document

    def spy(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(docx, "Document", spy)
    return calls


def test_CHL_PS3_docx_bomb_fixture_is_small_and_huge_unpacked():
    """Guard on the test's own fixture: under 1 MB on the wire, over 20 MB unpacked."""
    data = _docx_bomb()
    assert len(data) < MB
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert sum(i.file_size for i in z.infolist()) > 20 * MB


def test_CHL_PS3_extract_text_refuses_a_docx_bomb_without_parsing_it(docx_spy):
    from charlie.profile import extract_text
    t0 = time.monotonic()
    with pytest.raises(Exception):
        extract_text("resume.docx", _docx_bomb())
    assert docx_spy == [], "python-docx parsed the bomb; the zip must be checked first"
    assert time.monotonic() - t0 < 2


def test_CHL_PS3_extract_text_refuses_a_docx_with_too_many_members(docx_spy):
    from charlie.profile import extract_text
    with pytest.raises(Exception):
        extract_text("resume.docx", _docx_many_members())
    assert docx_spy == [], "python-docx parsed a 250-member zip"


def test_CHL_PS3_api_rejects_a_docx_bomb_quickly(client, docx_spy):
    t0 = time.monotonic()
    r = client.post("/api/profile", files={"resume": ("resume.docx", _docx_bomb(), "application/octet-stream")})
    elapsed = time.monotonic() - t0
    assert r.status_code in (400, 413), r.status_code
    assert docx_spy == [], "the upload reached python-docx"
    assert elapsed < 2, f"took {elapsed:.1f}s"
    assert "AAAA" not in r.text
    assert client.get("/api/status").status_code == 200


def test_CHL_PS3_sample_docx_still_parses(docx_spy):
    """Guard (passes today, must keep passing): the zip checks don't refuse a normal resume."""
    from charlie.profile import extract_text
    text = extract_text("sample_resume.docx", (SAMPLES / "sample_resume.docx").read_bytes())
    assert "Registered Nurse" in text and docx_spy == [1]


def _pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF, one line of Helvetica text per page."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None,
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream")
        content_id = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def test_CHL_PS3_pdf_fixture_reads_back():
    """Guard on the test's own fixture: a 3-page PDF extracts all three markers."""
    from charlie.profile import extract_text
    text = extract_text("r.pdf", _pdf(["PAGEMARKA", "PAGEMARKB", "PAGEMARKC"]))
    assert all(m in text for m in ("PAGEMARKA", "PAGEMARKB", "PAGEMARKC")), text


def test_CHL_PS3_pdf_reads_at_most_30_pages():
    from charlie.profile import extract_text
    data = _pdf([f"PAGEMARK{n:02d}" for n in range(1, 32)])
    try:
        text = extract_text("r.pdf", data)
    except Exception:
        return  # refusing a 31-page PDF outright is also fine
    assert "PAGEMARK30" in text
    assert "PAGEMARK31" not in text, "page 31 was read; the cap is 30 pages"


def test_CHL_PS3_extract_text_stops_at_100k_characters():
    from charlie.profile import extract_text
    assert len(extract_text("r.txt", b"nurse " * 70_000)) <= 100_000


def test_CHL_PS3_build_profile_and_enrich_get_at_most_50k_characters(client, monkeypatch):
    from charlie import handlers, llm_profile
    seen = {}
    real_build = handlers.build_profile

    def build_spy(text="", *a, **k):
        seen["build"] = len(text)
        return real_build(text, *a, **k)

    monkeypatch.setattr(handlers, "build_profile", build_spy)
    monkeypatch.setattr(llm_profile, "enrich", lambda text, *a, **k: seen.__setitem__("enrich", len(text)))
    r = client.post("/api/profile", data={"resume_text": "fictional nurse " * 8_000, "capital": "30000",
                                          "use_ai": "true"})
    assert r.status_code == 200, r.text
    assert seen["build"] <= 50_000, f"build_profile got {seen['build']} characters"
    assert seen["enrich"] <= 50_000, f"enrich got {seen['enrich']} characters"


# ============================================================ CHL-PS4 delete really deletes

MARKER = "ZQXFICTIONALRESUMEMARKER"


@pytest.fixture
def stock_sqlite(monkeypatch):
    """Simulate a SQLite build whose secure_delete defaults to 0 (common on macOS Pythons)."""
    real = sqlite3.connect

    def connect(*a, **k):
        conn = real(*a, **k)
        conn.execute("PRAGMA secure_delete=0")
        return conn

    monkeypatch.setattr(sqlite3, "connect", connect)


def _db_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    for extra in ("-journal", "-wal"):
        p = Path(str(path) + extra)
        if p.exists():
            data += p.read_bytes()
    return data


def test_CHL_PS4_store_turns_secure_delete_on(stock_sqlite, tmp_path):
    s = Store(str(tmp_path / "c.db"))
    assert s._conn.execute("PRAGMA secure_delete").fetchone()[0] == 1


def test_CHL_PS4_wipe_leaves_no_resume_bytes_even_without_secure_delete(tmp_path):
    path = tmp_path / "c.db"
    s = Store(str(path))
    s._conn.execute("PRAGMA secure_delete=0")  # worst case: the pragma got turned off after connect
    s.put("intake", {"resume_text": (MARKER + " fictional nurse ") * 400})
    s.put("profile", {"name": MARKER})
    assert MARKER.encode() in _db_bytes(path)
    s.wipe()
    assert MARKER.encode() not in _db_bytes(path), "wipe() left the resume in the db file; it must VACUUM"


def test_CHL_PS4_plain_delete_leaves_no_resume_bytes_on_a_stock_build(stock_sqlite, tmp_path, mock_md):
    path = tmp_path / "c.db"
    api = Api(Store(str(path)), mock_md)
    api.save_profile((MARKER + " fictional nurse at a hospital ") * 300, capital=30000)
    assert MARKER.encode() in _db_bytes(path)
    api.delete_profile(False)
    assert MARKER.encode() not in _db_bytes(path)


def test_CHL_PS4_delete_all_via_api_leaves_no_resume_bytes_on_a_stock_build(stock_sqlite, tmp_path, mock_md, monkeypatch):
    from charlie import server
    path = tmp_path / "c.db"
    monkeypatch.setattr(server, "store", Store(str(path)))
    monkeypatch.setattr(server, "md", lambda: mock_md)
    c = TestClient(server.app, base_url=LOOPBACK)
    assert c.post("/api/profile", data={"resume_text": (MARKER + " fictional nurse ") * 300}).status_code == 200
    assert c.delete("/api/profile?all=true").status_code == 200
    assert MARKER.encode() not in _db_bytes(path)


# ============================================================ CHL-PS5 capital and holdings must be sane numbers

BAD_CAPITAL = ["nan", "inf", "-inf", "-1", "0", "1e10", "abc"]


@pytest.mark.parametrize("capital", BAD_CAPITAL)
def test_CHL_PS5_server_rejects_bad_capital_and_keeps_working(client, capital):
    r = client.post("/api/profile", data={"resume_text": "fictional nurse", "capital": capital})
    assert r.status_code == 422, (capital, r.status_code, r.text[:200])
    assert "capital" in json.dumps(_body(r)).lower()
    assert client.get("/api/profile").status_code == 200
    assert client.get("/api/ideas").status_code == 200


@pytest.mark.parametrize("capital", BAD_CAPITAL)
def test_CHL_PS5_demo_router_rejects_bad_capital_and_stores_nothing(static_api, capital):
    status, body = static_api.route("POST", "/api/profile", body={"resume_text": "fictional nurse", "capital": capital})
    assert status == 422, (capital, status, body)
    assert "capital" in body["detail"].lower()
    assert static_api.store.get("profile") is None and static_api.store.get("intake") is None
    assert static_api.route("GET", "/api/profile")[0] == 200


@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_PS5_capital_at_the_limits_is_accepted(via, client, static_api):
    """Guard (passes today, must keep passing): 1 dollar and 1e9 are allowed."""
    for capital in ("1", "1000000000"):
        status, body = _call(via, client, static_api, "POST", "/api/profile",
                             form={"resume_text": "fictional nurse", "capital": capital})
        assert status == 200, (capital, body)


@pytest.mark.parametrize("via", ["client", "route"])
@pytest.mark.parametrize("holdings", ["AAPL " + "9" * 400, "AAPL 99999999999", "AAPL 5000000000.5"])
def test_CHL_PS5_huge_holdings_never_500(via, client, static_api, holdings):
    status, body = _call(via, client, static_api, "POST", "/api/profile",
                         form={"resume_text": "fictional nurse", "capital": "30000", "holdings": holdings})
    assert status in (200, 422), (status, body)
    if status == 200:
        assert "AAPL" not in body["profile"]["holdings"], "a holding over 1e9 shares was kept"
    assert _call(via, client, static_api, "GET", "/api/profile")[0] == 200


# ============================================================ CHL-PS6 oversized uploads refused before parsing

@pytest.fixture
def multipart_spy(monkeypatch):
    import starlette.formparsers as fp
    calls, real = [], fp.MultiPartParser.parse

    async def spy(self, *a, **k):
        calls.append(1)
        return await real(self, *a, **k)

    monkeypatch.setattr(fp.MultiPartParser, "parse", spy)
    return calls


def test_CHL_PS6_oversized_upload_is_413_before_the_form_is_parsed(client, multipart_spy):
    big = b"%PDF" + b"0" * (10 * MB)
    r = client.post("/api/profile", files={"resume": ("r.pdf", big, "application/pdf")})
    assert r.status_code == 413, r.status_code
    assert multipart_spy == [], "the 10 MB body was parsed (and spooled to disk) before the size check"


def test_CHL_PS6_oversized_chunked_upload_is_413(client, multipart_spy):
    def chunks():
        for _ in range(10):
            yield b"0" * MB

    r = client.post("/api/profile", content=chunks(),
                    headers={"content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413, r.status_code
    assert multipart_spy == []


def test_CHL_PS6_normal_upload_still_parses(client, multipart_spy):
    """Guard (passes today, must keep passing)."""
    r = client.post("/api/profile", files={"resume": ("r.txt", (SAMPLES / "sample_resume.txt").read_bytes(), "text/plain")})
    assert r.status_code == 200 and multipart_spy == [1]


# ============================================================ CHL-PS7 the database lives only in the root /data/

def test_CHL_PS7_default_db_path_is_anchored_to_the_repo_root(tmp_path, monkeypatch):
    seen = []
    real = sqlite3.connect
    monkeypatch.setattr(sqlite3, "connect", lambda p, *a, **k: (seen.append(p), real(":memory:", *a, **k))[1])
    monkeypatch.delenv("CHARLIE_DB", raising=False)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    Store()
    assert Path(seen[0]) == ROOT / "data" / "charlie.db", seen[0]
    assert not (elsewhere / "data").exists(), "Store() made a data/ folder in the current directory"


def test_CHL_PS7_charlie_db_env_still_wins(tmp_path, monkeypatch):
    """Guard (passes today)."""
    monkeypatch.setenv("CHARLIE_DB", str(tmp_path / "x.db"))
    Store()
    assert (tmp_path / "x.db").exists()


def test_CHL_PS7_default_cache_dir_is_anchored_to_the_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("CHARLIE_CACHE", raising=False)
    monkeypatch.chdir(tmp_path)
    assert MarketData(mode="mock", today=DAY).cache_dir == ROOT / "data" / "cache"


@pytest.mark.parametrize("path", ["charlie/data/charlie.db", "tests/data/charlie.db", "x.db", "x.db-journal",
                                  "x.db-wal", "x.db-shm", "charlie/data/cache/options/AAPL.json"])
def test_CHL_PS7_gitignore_covers_databases_anywhere(path):
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT)
    assert r.returncode == 0, f"{path} is not gitignored"


def test_CHL_PS7_no_database_is_tracked():
    """Guard (passes today)."""
    out = subprocess.run(["git", "ls-files", "*.db", "*.sqlite", "*.sqlite3"], cwd=ROOT, capture_output=True, text=True)
    assert out.stdout.strip() == ""


# ============================================================ CHL-PS8 delete-all also clears the live-data cache

@pytest.mark.parametrize("via", ["client", "route"])
def test_CHL_PS8_delete_all_clears_the_market_cache(via, client, static_api, mock_md, tmp_path):
    keep = tmp_path / "not-the-cache.txt"
    keep.write_text("stays")
    for kind in ("options", "history", "facts"):
        (mock_md.cache_dir / kind).mkdir(parents=True, exist_ok=True)
        (mock_md.cache_dir / kind / "AAPL.json").write_text("{}")
    status, _ = _call(via, client, static_api, "DELETE", "/api/profile?all=true")
    assert status == 200
    left = [p for p in mock_md.cache_dir.rglob("*") if p.is_file()] if mock_md.cache_dir.exists() else []
    assert left == [], left
    assert keep.read_text() == "stays", "delete-all removed a file outside the cache folder"


def test_CHL_PS8_plain_delete_keeps_the_cache(client, mock_md):
    """Guard (passes today): only "everything" clears the cache."""
    (mock_md.cache_dir / "options").mkdir(parents=True)
    (mock_md.cache_dir / "options" / "AAPL.json").write_text("{}")
    assert client.delete("/api/profile").status_code == 200
    assert (mock_md.cache_dir / "options" / "AAPL.json").exists()


# ============================================================ CHL-PS11 security headers

@pytest.mark.parametrize("path", ["/api/profile", "/api/status", "/api/paper"])
def test_CHL_PS11_api_responses_are_not_cached_or_sniffed(client, path):
    r = client.get(path)
    assert "no-store" in r.headers.get("cache-control", ""), dict(r.headers)
    assert r.headers.get("x-content-type-options") == "nosniff"


def test_CHL_PS11_api_errors_carry_the_headers_too(client):
    r = client.get("/api/ticker/NOTREAL")
    assert r.status_code == 404
    assert "no-store" in r.headers.get("cache-control", "")
    assert r.headers.get("x-content-type-options") == "nosniff"


def _frame_blocked(headers) -> bool:
    return (headers.get("x-frame-options", "").upper() == "DENY"
            or "frame-ancestors 'none'" in headers.get("content-security-policy", ""))


@pytest.mark.parametrize("path", ["/", "/api/profile"])
def test_CHL_PS11_pages_cannot_be_framed(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert _frame_blocked(r.headers), dict(r.headers)
    assert r.headers.get("x-content-type-options") == "nosniff"


# ============================================================ CHL-PS12 text inputs have size limits

def test_CHL_PS12_screen_name_over_100_chars_is_422(client):
    r = client.post("/api/screen", json={"criteria": {"scope": "all"}, "save": True, "name": "n" * 101})
    assert r.status_code == 422, r.status_code
    assert client.get("/api/screens").json()["screens"] == []


def test_CHL_PS12_screen_name_of_100_chars_is_fine(client):
    """Guard (passes today, must keep passing)."""
    r = client.post("/api/screen", json={"criteria": {"scope": "all"}, "save": True, "name": "n" * 100})
    assert r.status_code == 200


def test_CHL_PS12_paper_note_over_500_chars_is_422(client, mock_md):
    r = client.post("/api/paper", json={"trade": _real_trade(mock_md, level=2), "note": "x" * 501})
    assert r.status_code == 422, r.status_code
    assert client.get("/api/paper").json()["positions"] == []


def test_CHL_PS12_paper_note_of_500_chars_is_fine(client, mock_md):
    """Guard (passes today, must keep passing)."""
    r = client.post("/api/paper", json={"trade": _real_trade(mock_md, level=2), "note": "x" * 500})
    assert r.status_code == 200, r.text


def test_CHL_PS12_chat_message_over_4000_chars_is_422(client):
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "q" * 4001}]})
    assert r.status_code == 422, r.status_code


def test_CHL_PS12_chat_with_more_than_40_messages_is_422(client):
    msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": "hi"} for i in range(41)]
    r = client.post("/api/chat", json={"messages": msgs})
    assert r.status_code == 422, r.status_code


def test_CHL_PS12_chat_message_of_4000_chars_is_fine(client):
    """Guard (passes today, must keep passing)."""
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Tell me about Visa " + "q" * 3981}]})
    assert r.status_code == 200, r.text


def test_CHL_PS12_ideas_count_is_clamped_before_the_cache_key(client, db_path):
    assert client.get("/api/ideas?count=3").status_code == 200
    assert client.get("/api/ideas?count=999999").status_code == 200
    assert client.get("/api/ideas?count=1000000").status_code == 200
    rows = sqlite3.connect(str(db_path)).execute("SELECT COUNT(*) FROM daily").fetchone()[0]
    assert rows == 1, f"{rows} cached idea rows; huge counts must share the clamped key"


# ============================================================ core flows: happy path and bad input per endpoint

VIA = pytest.mark.parametrize("via", ["client", "route"])


@VIA
def test_CORE_status_and_meta(via, client, static_api):
    s, b = _call(via, client, static_api, "GET", "/api/status")
    assert s == 200 and "disclaimer" in b
    s, b = _call(via, client, static_api, "GET", "/api/meta")
    assert s == 200 and {str(k) for k in b["risk_levels"]} == {"1", "2", "3", "4", "5"}


@VIA
def test_CORE_unknown_path_is_404(via, client, static_api):
    assert _call(via, client, static_api, "GET", "/api/nope")[0] == 404
    if via == "route":
        assert static_api.route("GET", "/not-api") == (404, {"detail": "Not Found"})


@VIA
def test_CORE_risk_happy_and_bad(via, client, static_api):
    s, b = _call(via, client, static_api, "POST", "/api/profile/risk", body={"risk_level": 9})
    assert s == 200 and b["risk_level"] == 5
    assert _call(via, client, static_api, "POST", "/api/profile/risk", body={"risk_level": "abc"})[0] == 422


@VIA
def test_CORE_ideas_happy_cached_and_bad(via, client, static_api):
    s1, b1 = _call(via, client, static_api, "GET", "/api/ideas?count=2")
    s2, b2 = _call(via, client, static_api, "GET", "/api/ideas?count=2")
    assert s1 == s2 == 200 and b1 == b2
    assert _call(via, client, static_api, "GET", "/api/ideas?count=abc")[0] == 422


@VIA
def test_CORE_ticker_happy_and_unknown(via, client, static_api):
    s, b = _call(via, client, static_api, "GET", "/api/ticker/KO")
    assert s == 200 and b["trades"]
    s, b = _call(via, client, static_api, "GET", "/api/ticker/ZZZZ")
    assert s == 404 and "ZZZZ" in b["detail"]


@VIA
@pytest.mark.parametrize("criteria,field", [
    ({"min_score": True}, "min_score"), ({"min_score": "nan"}, "min_score"), ({"scope": "everywhere"}, "scope"),
    ({"symbols": [1, 2]}, "symbols"), ({"domains": 5}, "domains"),
])
def test_CORE_screen_bad_criteria_are_422(via, criteria, field, client, static_api):
    s, b = _call(via, client, static_api, "POST", "/api/screen", body={"criteria": criteria})
    assert s == 422 and field in b["detail"], (s, b)


def test_CORE_screen_criteria_must_be_an_object(static_api):
    s, b = static_api.route("POST", "/api/screen", body={"criteria": ["x"]})
    assert s == 422 and "criteria" in b["detail"]


@VIA
def test_CORE_screen_string_lists_and_whole_dte(via, client, static_api):
    s, b = _call(via, client, static_api, "POST", "/api/screen",
                 body={"criteria": {"scope": "list", "symbols": "KO, MSFT", "dte_min": "20.7", "dte_max": 60}})
    assert s == 200, b
    assert {r["symbol"] for r in b["results"]} <= {"KO", "MSFT"}


@VIA
def test_CORE_screens_save_list_delete(via, client, static_api):
    s, b = _call(via, client, static_api, "POST", "/api/screen",
                 body={"criteria": {"scope": "all"}, "save": True, "name": "cheap"})
    assert s == 200
    sid = b["saved"]["id"]
    s, b = _call(via, client, static_api, "GET", "/api/screens")
    assert s == 200 and [x["id"] for x in b["screens"]] == [sid] and b["defaults"]
    assert _call(via, client, static_api, "DELETE", f"/api/screens/{sid}")[0] == 200
    assert _call(via, client, static_api, "GET", "/api/screens")[1]["screens"] == []
    assert _call(via, client, static_api, "DELETE", "/api/screens/nope")[0] == 200  # deleting twice is fine


@VIA
def test_CORE_chat_happy_and_bad(via, client, static_api):
    s, b = _call(via, client, static_api, "POST", "/api/chat",
                 body={"messages": [{"role": "user", "content": "Tell me about Visa"}]})
    assert s == 200 and "Not financial advice. Paper trading only." in json.dumps(b)
    for msgs in ([], [{"role": "assistant", "content": "hi"}], [{"role": "user", "content": 5}]):
        assert _call(via, client, static_api, "POST", "/api/chat", body={"messages": msgs})[0] == 400


@VIA
@pytest.mark.parametrize("leg_patch,word", [
    ("notadict", "leg object"), ({"action": "hold"}, "action"), ({"instrument": "future"}, "instrument"),
    ({"symbol": 7}, "symbol"), ({"qty": 1.5}, "qty"), ({"qty": -1}, "qty"),
])
def test_CORE_paper_bad_legs_are_422(via, leg_patch, word, client, static_api, mock_md):
    t = _real_trade(mock_md, level=2)
    t["legs"] = ["notadict"] if leg_patch == "notadict" else [{**t["legs"][0], **leg_patch}]
    s, b = _call(via, client, static_api, "POST", "/api/paper", body={"trade": t})
    assert s == 422 and word in b["detail"], (s, b)


@VIA
def test_CORE_paper_option_leg_needs_an_option_symbol(via, client, static_api, mock_md):
    t = _real_trade(mock_md, level=2)
    t["legs"] = [{**t["legs"][0], "instrument": "call", "symbol": "KO"}]
    s, b = _call(via, client, static_api, "POST", "/api/paper", body={"trade": t})
    assert s == 422 and "option symbol" in b["detail"]


@VIA
def test_CORE_paper_symbol_must_be_text(via, client, static_api, mock_md):
    t = _real_trade(mock_md, level=2)
    t["symbol"] = 123
    s, b = _call(via, client, static_api, "POST", "/api/paper", body={"trade": t})
    assert s == 422 and "symbol" in b["detail"]


@VIA
def test_CORE_paper_not_a_trade_is_400_and_unknown_close_is_404(via, client, static_api):
    assert _call(via, client, static_api, "POST", "/api/paper", body={"trade": {"symbol": "KO"}})[0] == 400
    assert _call(via, client, static_api, "POST", "/api/paper", body={"trade": "x"})[0] in (400, 422)
    assert _call(via, client, static_api, "POST", "/api/paper/nope/close")[0] == 404


@VIA
def test_CORE_paper_open_list_close(via, client, static_api, mock_md):
    t = _real_trade(mock_md, level=2)
    s, b = _call(via, client, static_api, "POST", "/api/paper", body={"trade": t, "note": "fictional"})
    assert s == 200 and b["status"] == "open"
    s, summary = _call(via, client, static_api, "GET", "/api/paper")
    assert s == 200 and summary["positions"][0]["id"] == b["id"]
    s, closed = _call(via, client, static_api, "POST", f"/api/paper/{b['id']}/close")
    assert s == 200 and closed["status"] == "closed"


def test_CORE_profile_with_claude_boosts_is_labeled(client, monkeypatch):
    from charlie import llm_profile
    monkeypatch.setattr(llm_profile, "enrich", lambda *a, **k: ({"healthcare": (5.0, "AI read: fictional evidence")}, {}))
    r = client.post("/api/profile", data={"resume_text": "fictional nurse", "use_ai": "true"})
    assert r.status_code == 200 and r.json()["profile"]["source"] == "rules + claude"


def test_CORE_route_uses_claude_only_outside_the_demo(mock_md, monkeypatch):
    from charlie import llm_profile
    calls = []
    monkeypatch.setattr(llm_profile, "enrich", lambda *a, **k: calls.append(a) or ({"healthcare": (5.0, "AI read: fictional evidence")}, {}))
    local = Api(BrowserStore(FakeStorage()), mock_md, static=False)
    s, b = local.route("POST", "/api/profile", body={"resume_text": "fictional nurse", "use_ai": "true"})
    assert s == 200 and calls and b["profile"]["source"] == "rules + claude"
    demo = Api(BrowserStore(FakeStorage()), mock_md, static=True)
    demo.route("POST", "/api/profile", body={"resume_text": "fictional nurse", "use_ai": "true"})
    assert len(calls) == 1, "the static demo called Claude"


def test_CORE_profile_reuses_the_saved_resume_when_none_is_sent(client):
    client.post("/api/profile", data={"resume_text": "Fictional nurse, HCA Healthcare, 2017 - 2022"})
    r = client.post("/api/profile", data={"interests": "biotech"})
    assert r.status_code == 200 and r.json()["resume_chars"] > 0


@VIA
def test_CORE_profile_bad_risk_level_is_422(via, client, static_api):
    s, _ = _call(via, client, static_api, "POST", "/api/profile", form={"resume_text": "x", "risk_level": "high"})
    assert s == 422


# ============================================================ logs never hold resume text

RESUME_LINES = [ln.strip("- ").strip() for ln in (SAMPLES / "sample_resume.txt").read_text().splitlines()
                if len(ln.strip()) > 25]


def _requests_that_touch_the_resume(c):
    """Uploads, error paths and a delete. Each call may fail (PS5 bugs can 500 or drop the connection
    today); this only checks what reaches the logs, so failures are swallowed here on purpose."""
    txt = (SAMPLES / "sample_resume.txt").read_bytes()
    docx = (SAMPLES / "sample_resume.docx").read_bytes()
    calls = [
        lambda: c.post("/api/profile", files={"resume": ("r.txt", txt, "text/plain")}, data={"capital": "30000"}),
        lambda: c.post("/api/profile", files={"resume": ("r.docx", docx, "application/octet-stream")}),
        lambda: c.post("/api/profile", data={"resume_text": txt.decode(), "capital": "nan"}),  # bad capital
        lambda: c.delete("/api/profile"),
        lambda: c.post("/api/profile", data={"resume_text": txt.decode(), "holdings": "AAPL " + "9" * 400}),
        lambda: c.post("/api/profile", files={"resume": ("r.pdf", b"%PDF-1.4 " + txt, "application/pdf")}),
        lambda: c.post("/api/profile", files={"resume": ("r.docx", b"PK\x03\x04" + txt, "application/octet-stream")}),
        lambda: c.post("/api/profile", data={"resume_text": txt.decode()}, headers={"origin": "https://evil.example.com"}),
        lambda: c.post("/api/profile", data={"resume_text": txt.decode(), "risk_level": "high"}),  # 422 echoes input
        lambda: c.post("/api/profile", data={"resume_text": txt.decode(), "capital": "30000"}),
        lambda: c.get("/api/profile"),
        lambda: c.post("/api/chat", json={"messages": [{"role": "user", "content": "what are today's ideas"}]}),
        lambda: c.delete("/api/profile?all=true"),
    ]
    for call in calls:
        try:
            call()
        except Exception:  # noqa: BLE001 (a dropped connection is a PS5 bug, tested above, not a log leak)
            pass


def _assert_no_resume(text: str):
    leaked = [ln for ln in RESUME_LINES if ln in text]
    assert not leaked, f"resume lines in the logs: {leaked[:3]}"


def test_LOGS_in_process_requests_log_no_resume_text(client, caplog, capfd):
    """Guard (passes today, must keep passing)."""
    assert len(RESUME_LINES) >= 5
    with caplog.at_level(logging.DEBUG):
        _requests_that_touch_the_resume(client)
    out, err = capfd.readouterr()
    _assert_no_resume(caplog.text + out + err)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_LOGS_live_uvicorn_logs_no_resume_text(tmp_path):
    """Guard (passes today, must keep passing): a real server at debug level, its whole log checked."""
    import httpx

    port = _free_port()
    log = tmp_path / "server.log"
    env = {**os.environ, "CHARLIE_DATA": "mock", "CHARLIE_LLM": "off", "CHARLIE_TODAY": "2026-10-22",
           "CHARLIE_DB": str(tmp_path / "s.db"), "CHARLIE_CACHE": str(tmp_path / "cache")}
    with open(log, "wb") as fh:
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "charlie.server:app", "--host", "127.0.0.1",
                                 "--port", str(port), "--log-level", "debug"],
                                cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(100):
                try:
                    httpx.get(base + "/api/status", timeout=1)
                    break
                except httpx.HTTPError:
                    time.sleep(0.1)
            with httpx.Client(base_url=base, timeout=30) as c:
                _requests_that_touch_the_resume(c)
        finally:
            proc.terminate()
            proc.wait(10)
    text = log.read_text("utf-8", "replace")
    assert "/api/profile" in text, "the server log is empty; the test didn't exercise anything"
    _assert_no_resume(text)


# ============================================================ CHL-PS14 a PDF content-stream bomb is refused quickly

def _pdf_stream_bomb(decoded: int, npages: int = 1) -> bytes:
    """A small PDF whose one shared, Flate-compressed content stream decodes to about `decoded` bytes of
    text operators (fictional filler: the letter a). Every page points at the same stream."""
    import zlib
    line = b"BT /F1 12 Tf 72 700 Td (a) Tj ET\n"
    comp = zlib.compress(line * (decoded // len(line) + 1), 9)
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Count %d /Kids [%s] >>" % (npages, b" ".join(b"%d 0 R" % (5 + i) for i in range(npages))),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(comp) + comp + b"\nendstream"]
    objs += [b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
             b"/Contents 4 0 R >>"] * npages
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


_EXTRACT_PROBE = """
import json, resource, sys, time
sys.path.insert(0, sys.argv[2])
from charlie.profile import extract_text
data = open(sys.argv[1], "rb").read()
t0 = time.monotonic()
try:
    extract_text("resume.pdf", data)
    result = None
except Exception as e:
    result = type(e).__name__
seconds = time.monotonic() - t0
try:  # this process's own high-water mark; ru_maxrss can carry over the forking parent's (Linux)
    peak_kb = int(next(l for l in open("/proc/self/status") if l.startswith("VmHWM:")).split()[1])
except (OSError, StopIteration):
    peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(json.dumps({"raised": result, "seconds": seconds, "peak_mb": peak_kb / 1024}))
"""


def _extract_in_child(tmp_path, data: bytes, timeout: float = 20) -> dict:
    """Run extract_text in a child process, so a slow red run is killed instead of eating the suite."""
    f = tmp_path / "bomb.pdf"
    f.write_bytes(data)
    try:
        r = subprocess.run([sys.executable, "-c", _EXTRACT_PROBE, str(f), str(ROOT)],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        pytest.fail(f"extract_text was still parsing the PDF bomb after {timeout:.0f}s")
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_CHL_PS14_pdf_bomb_fixture_is_small_on_the_wire():
    """Guard on the test's own fixture: a 60 MB content stream in well under 1 MB."""
    assert len(_pdf_stream_bomb(60 * MB)) < MB


@pytest.mark.parametrize("decoded,npages", [(60 * MB, 1), (1 * MB, 30)],
                         ids=["one page 60 MB stream", "30 pages sharing a 1 MB stream"])
def test_CHL_PS14_extract_text_refuses_a_pdf_content_stream_bomb_quickly(tmp_path, decoded, npages):
    out = _extract_in_child(tmp_path, _pdf_stream_bomb(decoded, npages))
    assert out["raised"] == "FileTooComplex", out
    assert out["seconds"] < 2, out
    assert out["peak_mb"] < 300, f"memory blew up: {out}"


def test_CHL_PS14_api_rejects_a_pdf_content_stream_bomb_with_413_quickly(client):
    t0 = time.monotonic()
    r = client.post("/api/profile", files={"resume": ("resume.pdf", _pdf_stream_bomb(3 * MB), "application/pdf")})
    elapsed = time.monotonic() - t0
    assert r.status_code == 413, (r.status_code, r.text[:200])
    assert elapsed < 2, f"took {elapsed:.1f}s"
    assert client.get("/api/status").status_code == 200


def test_CHL_PS14_a_normal_pdf_still_parses():
    """Guard (passes today, must keep passing): an ordinary few-page PDF isn't refused by the content cap."""
    from charlie.profile import extract_text
    text = extract_text("r.pdf", _pdf([f"Fictional Nurse page {n} PAGEMARK{n}" for n in range(1, 4)]))
    assert "PAGEMARK1" in text and "PAGEMARK3" in text


# ============================================================ CHL-PS15 a malformed holding is dropped, never a crash

@pytest.mark.parametrize("via", ["client", "route"])
@pytest.mark.parametrize("holdings", ["AAPL 1.2.3", "AAPL ²", "AAPL 1..", "AAPL ٣"])
def test_CHL_PS15_malformed_holding_is_dropped_not_a_crash(via, client, static_api, holdings):
    status, body = _call(via, client, static_api, "POST", "/api/profile",
                         form={"resume_text": "fictional nurse", "capital": "30000",
                               "holdings": holdings + ", MSFT 10"})
    assert status in (200, 422), (status, body)
    if status == 200:
        assert body["profile"]["holdings"].get("MSFT") == 10, body["profile"]["holdings"]
        assert "AAPL" not in body["profile"]["holdings"], "a malformed share count was kept"
    assert _call(via, client, static_api, "GET", "/api/profile")[0] == 200


# ============================================================ CHL-R3 CI runs every browser test
def test_CHL_R3_ci_e2e_job_runs_every_browser_gated_test_outside_tests_e2e():
    """Tests skipped unless CHARLIE_E2E=1 only run in CI's e2e job, which collected just tests/e2e,
    so a gated test elsewhere (PS1's ?pyodide= check) never ran. Each one must be named in that job."""
    root = Path(__file__).resolve().parent
    ci = (root.parent / ".github" / "workflows" / "ci.yml").read_text()
    e2e_job = ci[ci.index("\n  e2e:"):]
    nxt = re.search(r"\n  [\w-]+:\n", e2e_job[1:])  # stop at the next job
    e2e_job = e2e_job[:nxt.start() + 1] if nxt else e2e_job
    gated = []
    for f in sorted(root.glob("test_*.py")):
        src = f.read_text()
        for m in re.finditer(r'@pytest\.mark\.skipif\(os\.environ\.get\("CHARLIE_E2E"\) != "1".*\n(?:@.*\n)*def (test_\w+)', src):
            gated.append(f"tests/{f.name}::{m.group(1)}")
    assert gated, "expected at least PS1's browser test to be gated"
    missing = [t for t in gated if t not in e2e_job]  # by node id, so the job never runs a whole unit file
    assert missing == [], f"CI's e2e job never runs: {missing}"
