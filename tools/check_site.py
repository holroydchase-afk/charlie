"""Fail if the built demo could leak a key or call anything but the Pyodide CDN.

Usage: python tools/check_site.py site/ [--no-cdn]
Scans every text file in the folder and every file inside charlie.zip. A URL is fine only if
its host is in ALLOWED: the Pyodide CDN (the one network call the demo may make), the
portfolio link, and the SVG namespace in the favicon. --no-cdn drops the CDN too, for a
self-hosted build. The vendored Pyodide runtime in site/pyodide/ is not scanned: it's the
unmodified npm release, and its stdlib mentions many URLs it never calls.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ALLOWED = {"cdn.jsdelivr.net", "chaseholroyd.com", "www.w3.org"}
VENDORED = "pyodide"
TEXT = {".html", ".js", ".css", ".json", ".py", ".txt", ".md"}
URL = re.compile(r"https?://([A-Za-z0-9.-]+)")
KEYS = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}")


def _files(site: Path):
    for f in sorted(site.rglob("*")):
        if f.is_symlink() or not f.is_file() or f.relative_to(site).parts[0] == VENDORED:
            continue
        if f.suffix == ".zip":
            with zipfile.ZipFile(f) as z:
                for name in z.namelist():
                    if Path(name).suffix in TEXT:
                        yield f"{f.name}:{name}", z.read(name).decode("utf-8", "replace")
        elif f.suffix in TEXT:
            yield str(f.relative_to(site)), f.read_text("utf-8", "replace")


def check(site: Path, allowed: set[str] = ALLOWED) -> list[str]:
    from build_demo import PYODIDE_FILES  # the only files that may sit in the unscanned runtime folder
    problems = [f"{VENDORED}/{f.name}: not a Pyodide runtime file" for f in sorted((site / VENDORED).glob("*"))
                if f.name not in PYODIDE_FILES]
    for name, text in _files(site):
        for n, line in enumerate(text.splitlines(), 1):
            if KEYS.search(line):
                problems.append(f"{name}:{n}: looks like an API key or token")
            for host in URL.findall(line):
                if host.lower() not in allowed:
                    problems.append(f"{name}:{n}: URL to {host}, which isn't on the allowed list")
    return problems


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    site = Path(args[0] if args else "site")
    allowed = ALLOWED - {"cdn.jsdelivr.net"} if "--no-cdn" in sys.argv else ALLOWED
    if not (site / "index.html").exists():
        sys.exit(f"{site} has no index.html; run tools/build_demo.py first")
    found = check(site, allowed)
    print("\n".join(found) if found else f"ok: {site} has no keys and no hosts beyond {', '.join(sorted(allowed))}")
    sys.exit(1 if found else 0)
