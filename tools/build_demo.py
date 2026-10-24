"""Build the static demo into site/: the web app, static.js, a zip of the Python it runs, and
prebuilt.json, the sample person's answers for every risk level, so Today shows before Pyodide loads.

Usage: python tools/build_demo.py [out_dir] [--date YYYY-MM-DD]   (default site/, today)
The demo's data is pinned to the build date. M1.6 deploys the folder to Pages.
"""

from __future__ import annotations

import argparse
import json
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


def build(out: Path, day: str | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    for name in WEB_FILES:
        shutil.copy(ROOT / "web" / name, out / name)
    html = (ROOT / "web" / "index.html").read_text()
    html = html.replace('href="/static/', 'href="').replace('src="/static/', 'src="')  # relative, for a subpath
    html = html.replace('<script src="app.js"></script>', '<script src="static.js"></script>\n  <script src="app.js"></script>')
    assert 'src="static.js"' in html, "index.html no longer loads app.js the way build_demo expects"
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
    a = ap.parse_args()
    print(build(Path(a.out), a.date))
