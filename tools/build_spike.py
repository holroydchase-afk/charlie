"""Build the M1.1 Pyodide spike: spike/ files plus a zip of the engine modules the demo needs.

Usage: python tools/build_spike.py [out_dir]   (default build/spike)
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Only what charlie.demo imports: no server, storage, chat or document parsers.
MODULES = [
    "charlie/__init__.py", "charlie/demo.py", "charlie/engine.py", "charlie/profile.py", "charlie/scoring.py",
    "charlie/strategies.py", "charlie/options_math.py", "charlie/universe.py",
    "charlie/data/__init__.py", "charlie/data/market.py", "charlie/data/mock.py", "charlie/data/cboe.py",
    "charlie/data/sec.py",
]


def build(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "spike.js"):
        shutil.copy(ROOT / "spike" / name, out / name)
    with zipfile.ZipFile(out / "charlie.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for m in MODULES:
            z.write(ROOT / m, m)
    return out


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "spike"))
