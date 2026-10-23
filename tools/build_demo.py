"""Build the static demo into site/: the web app, static.js, and a zip of the Python it runs.

Usage: python tools/build_demo.py [out_dir]   (default site/)
M1.3 adds the prebuilt first screen; M1.6 deploys the folder to Pages.
"""

from __future__ import annotations

import shutil
import sys
import zipfile
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


def build(out: Path) -> Path:
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
    return out


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"))
