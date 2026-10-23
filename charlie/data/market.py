"""One facade for quotes, option chains, price history and fundamentals.

Modes (CHARLIE_DATA):
  auto  try the free live sources and fall back to labeled demo data per call (default)
  mock  demo data only, no network
  live  live sources only; errors propagate instead of falling back
Every record carries a "source" so the UI can always say where a number came from.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import date
from pathlib import Path

from . import mock

MODES = ("auto", "mock", "live")
TTL = {"options": 15 * 60, "history": 12 * 3600, "facts": 7 * 86400, "ciks": 30 * 86400}
OFFLINE_BACKOFF = 300  # after a network failure in auto mode, skip live calls for 5 minutes


def _today_from_env() -> date:
    v = os.environ.get("CHARLIE_TODAY")
    return date.fromisoformat(v) if v else date.today()


class MarketData:
    def __init__(self, mode: str | None = None, today: date | None = None, cache_dir: str | None = None):
        mode = (mode or os.environ.get("CHARLIE_DATA", "auto")).lower()
        if mode not in MODES:
            raise ValueError(f"CHARLIE_DATA must be one of {MODES}, not {mode!r}")
        self.mode = mode
        self.today = today or _today_from_env()
        self.cache_dir = Path(cache_dir or os.environ.get("CHARLIE_CACHE", "data/cache"))
        self._lock = threading.Lock()
        self._mem: dict[tuple, object] = {}
        self._offline_until = 0.0
        self._errors: list[str] = []
        self._live_hits = 0

    # ------------------------------------------------------------------ plumbing

    def _cached(self, kind: str, key: str, fetch):
        """Fetch JSON through an on-disk cache (live modes only)."""
        path = self.cache_dir / kind / f"{key.replace('/', '_')}.json"
        try:
            if time.time() - path.stat().st_mtime < TTL[kind]:
                return json.loads(path.read_text())
        except (OSError, ValueError):
            pass
        data = fetch()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        except OSError:
            pass
        return data

    def _live(self, what: str, fn, fallback):
        if self.mode == "mock":
            return fallback()
        if self.mode == "auto" and time.monotonic() < self._offline_until:
            return fallback()
        try:
            out = fn()
            with self._lock:
                self._live_hits += 1
            return out
        except Exception as e:
            if self.mode == "live":
                raise
            with self._lock:
                if isinstance(e, (OSError, ConnectionError)) or "requests" in type(e).__module__:
                    self._offline_until = time.monotonic() + OFFLINE_BACKOFF
                msg = f"{what}: {type(e).__name__}: {e}"[:200]
                if msg not in self._errors:
                    self._errors = (self._errors + [msg])[-5:]
            return fallback()

    def _memo(self, key: tuple, fn):
        with self._lock:
            if key in self._mem:
                return self._mem[key]
        val = fn()
        with self._lock:
            self._mem[key] = val
        return val

    def _options_payload(self, symbol: str) -> dict:
        from . import cboe
        return self._cached("options", symbol, lambda: cboe.fetch_options(symbol))

    # ------------------------------------------------------------------ public API

    def history(self, symbol: str) -> list[dict]:
        symbol = symbol.upper()

        def live():
            from . import cboe
            rows = cboe.parse_history(self._cached("history", symbol, lambda: cboe.fetch_history(symbol)))
            if not rows:
                raise ValueError("empty history")
            return rows

        return self._memo(("history", symbol), lambda: self._live(
            f"history {symbol}", live, lambda: mock.history(symbol, self.today)))

    def quote(self, symbol: str) -> dict:
        symbol = symbol.upper()

        def live():
            from . import cboe
            closes = [r["close"] for r in self.history(symbol) if r.get("close")]
            q = cboe.parse_quote(self._options_payload(symbol), symbol, closes)
            if not q["price"]:
                raise ValueError("no price in Cboe payload")
            return q

        return self._memo(("quote", symbol), lambda: self._live(
            f"quote {symbol}", live, lambda: mock.quote(symbol, self.today)))

    def chain(self, symbol: str) -> list[dict]:
        symbol = symbol.upper()

        def live():
            from . import cboe
            rows = cboe.parse_chain(self._options_payload(symbol), symbol, self.today)
            if not rows:
                raise ValueError("empty option chain")
            return rows

        if self.quote(symbol)["source"] == "mock":  # never mix a live chain with a mock price
            return self._memo(("chain", symbol), lambda: mock.chain(symbol, self.today))
        return self._memo(("chain", symbol), lambda: self._live(
            f"chain {symbol}", live, lambda: mock.chain(symbol, self.today)))

    def fundamentals(self, symbol: str) -> dict:
        symbol = symbol.upper()

        def live():
            from . import sec
            sec.user_agent()  # refuse before any request while the identity is unset
            ciks = self._cached("ciks", "company_tickers", sec.fetch_cik_map)
            cik = ciks.get(symbol)
            if not cik:
                raise KeyError(f"no SEC CIK for {symbol}")
            facts = self._cached("facts", str(cik), lambda: sec.fetch_facts(int(cik)))
            q = self.quote(symbol)
            return {"symbol": symbol, **sec.compute_metrics(facts, q["price"] if q["source"] != "mock" else None)}

        def fallback():
            return mock.fundamentals(symbol, self.today)

        def guarded():
            if self.mode != "mock" and not _sec_ready():
                if self.mode == "live":
                    from . import sec
                    sec.user_agent()
                return fallback()
            return self._live(f"fundamentals {symbol}", live, fallback)

        return self._memo(("fundamentals", symbol), guarded)

    def status(self) -> dict:
        notes = []
        if self.mode != "mock" and not _sec_ready():
            notes.append("Live SEC fundamentals are off until CHARLIE_SEC_UA is set ('AppName your-email').")
        if self.mode == "mock":
            notes.append("Demo data only (CHARLIE_DATA=mock). Prices are simulated.")
        elif self._errors:
            notes.append("Live data unreachable, showing demo data where needed.")
        with self._lock:
            return {
                "mode": self.mode,
                "today": self.today.isoformat(),
                "live_ok": self.mode != "mock" and not self._errors and self._live_hits > 0,
                "sec_user_agent_set": _sec_ready(),
                "errors": list(self._errors),
                "notes": notes,
            }


def _sec_ready() -> bool:
    if not os.environ.get("CHARLIE_SEC_UA"):
        return False
    from . import sec  # the live adapters load only when used, so the browser demo never imports them
    try:
        sec.user_agent()
        return True
    except sec.SecConfigError:
        return False


_market: MarketData | None = None
_market_lock = threading.Lock()


def get_market() -> MarketData:
    """The process-wide facade, built from environment variables on first use."""
    global _market
    with _market_lock:
        if _market is None:
            _market = MarketData()
        return _market
