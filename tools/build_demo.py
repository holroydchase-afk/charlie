"""Build the static demo into site/: the web app, static.js, a zip of the Python it runs, and
prebuilt.json, the sample person's answers for every risk level, so Today shows before Pyodide loads.

Usage: python tools/build_demo.py [out_dir] [--date YYYY-MM-DD] [--pyodide-dir DIR]   (default site/, today)
The demo's data is pinned to the build date. With --pyodide-dir (an unpacked pyodide npm package), the
runtime is copied into site/pyodide/ and static.js loads it from there, so visitors' browsers never call
a third-party CDN; that's how pages.yml builds the public demo. Without it, Pyodide loads from jsDelivr.
index.html gets a strict meta Content-Security-Policy (see csp()); only the CDN build allows jsDelivr in it.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# What charlie.browser imports. Not the server, Claude profile reading or the live data adapters.
MODULES = [
    "charlie/__init__.py", "charlie/browser.py", "charlie/browser_store.py", "charlie/handlers.py",
    "charlie/store.py", "charlie/chat.py", "charlie/portfolio.py", "charlie/demo.py", "charlie/engine.py",
    "charlie/profile.py", "charlie/scoring.py", "charlie/strategies.py", "charlie/options_math.py",
    "charlie/universe.py", "charlie/data/__init__.py", "charlie/data/market.py", "charlie/data/mock.py",
]
WEB_FILES = ["app.js", "styles.css", "static.js"]
# The Pyodide runtime files the demo actually fetches (checked in Chromium); nothing else is shipped.
PYODIDE_FILES = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
CDN_BASE = re.compile(r'"https://cdn\.jsdelivr\.net/pyodide/v[0-9.]+/full/"')
CDN_ORIGIN = "https://cdn.jsdelivr.net"


def csp(cdn: bool) -> str:
    """The demo's Content-Security-Policy (CHL-PS1): its own files only, plus WebAssembly for Pyodide.
    The CDN build also allows the Pyodide CDN; a self-hosted build allows no other host at all."""
    extra = f" {CDN_ORIGIN}" if cdn else ""
    return ("default-src 'self'; "
            f"script-src 'self' 'wasm-unsafe-eval'{extra}; "
            f"connect-src 'self'{extra}; "
            "img-src 'self' data:; style-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'")


def build(out: Path, day: str | None = None, pyodide_dir: Path | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    for name in WEB_FILES:
        shutil.copy(ROOT / "web" / name, out / name)
    if pyodide_dir:
        missing = [n for n in PYODIDE_FILES if not (Path(pyodide_dir) / n).is_file()]
        if missing:
            raise FileNotFoundError(f"{pyodide_dir} is missing Pyodide files: {', '.join(missing)}")
        (out / "pyodide").mkdir(exist_ok=True)
        for n in PYODIDE_FILES:
            shutil.copy(Path(pyodide_dir) / n, out / "pyodide" / n)
        js = (out / "static.js").read_text()
        assert CDN_BASE.search(js), "static.js no longer names the Pyodide CDN the way build_demo expects"
        (out / "static.js").write_text(CDN_BASE.sub('"pyodide/"', js))
    html = (ROOT / "web" / "index.html").read_text()
    html = html.replace('href="/static/', 'href="').replace('src="/static/', 'src="')  # relative, for a subpath
    html = html.replace('<script src="app.js"></script>', '<script src="static.js"></script>\n  <script src="app.js"></script>')
    assert 'src="static.js"' in html, "index.html no longer loads app.js the way build_demo expects"
    meta = f'<meta http-equiv="Content-Security-Policy" content="{csp(cdn=not pyodide_dir)}">'
    assert '<meta charset="utf-8">' in html, "index.html no longer has the charset meta build_demo puts the CSP after"
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n  ' + meta, 1)
    (out / "index.html").write_text(html)
    with zipfile.ZipFile(out / "charlie.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for m in MODULES:
            z.write(ROOT / m, m)
    sys.path.insert(0, str(ROOT))
    try:
        from charlie.browser import prebuild
    finally:
        sys.path.pop(0)
    pre = prebuild(day or date.today().isoformat())
    (out / "prebuilt.json").write_text(json.dumps(pre, separators=(",", ":")))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=str(ROOT / "site"))
    ap.add_argument("--date", help="pin the demo's day (default: today)")
    ap.add_argument("--pyodide-dir", type=Path, help="unpacked pyodide npm package to self-host")
    a = ap.parse_args()
    print(build(Path(a.out), a.date, a.pyodide_dir))
