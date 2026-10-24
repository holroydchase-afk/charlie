"""Store's interface on top of the browser's localStorage, for the static demo.

Everything stays in the visitor's browser: each section is one JSON string under a
"charlie:" key. Corrupt or missing entries read as empty instead of breaking the page.
"""

from __future__ import annotations

import json
import uuid

from .store import _now, leg_key, position_value

PREFIX = "charlie:"


class BrowserStore:
    def __init__(self, storage):
        self._s = storage  # window.localStorage, or anything with getItem/setItem/removeItem

    def _load(self, name: str, default):
        raw = self._s.getItem(PREFIX + name)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return default

    def _save(self, name: str, value) -> None:
        self._s.setItem(PREFIX + name, json.dumps(value))

    # kv
    def get(self, key: str, default=None):
        return self._load("kv:" + key, default)

    def put(self, key: str, value) -> None:
        self._save("kv:" + key, value)

    def delete(self, key: str) -> None:
        self._s.removeItem(PREFIX + "kv:" + key)

    # screens
    def save_screen(self, name: str, criteria: dict) -> dict:
        s = {"id": uuid.uuid4().hex[:10], "name": name, "criteria": criteria, "created": _now()}
        self._save("screens", [s] + self.screens())
        return {k: s[k] for k in ("id", "name", "criteria")}

    def screens(self) -> list[dict]:
        rows = self._load("screens", [])
        return rows if isinstance(rows, list) else []

    def delete_screen(self, sid: str) -> None:
        self._save("screens", [s for s in self.screens() if s.get("id") != sid])

    # daily idea snapshots: only the latest day is kept, so storage can't grow without bound
    def daily_get(self, day: str, level: int, profile_hash: str):
        d = self._load("daily", {})
        return d.get("payloads", {}).get(f"{level}|{profile_hash}") if d.get("day") == day else None

    def daily_put(self, day: str, level: int, profile_hash: str, payload: dict) -> None:
        d = self._load("daily", {})
        if d.get("day") != day:
            d = {"day": day, "payloads": {}}
        d["payloads"][f"{level}|{profile_hash}"] = payload
        self._save("daily", d)

    def clear_daily(self) -> None:
        self._s.removeItem(PREFIX + "daily")

    # paper positions
    def _positions(self) -> list[dict]:
        rows = self._load("positions", [])
        return rows if isinstance(rows, list) else []

    def open_position(self, trade: dict, note: str = "") -> dict:
        pos = {"id": uuid.uuid4().hex[:10], "opened": _now(), "symbol": trade["symbol"], "strategy": trade["strategy"],
               "trade": trade, "entry_value": float(position_value(trade["legs"], {leg_key(l): l["price"] for l in trade["legs"]})),
               "status": "open", "closed": None, "exit_value": None, "note": note}
        self._save("positions", [pos] + self._positions())
        return dict(pos)

    def position(self, pid: str) -> dict | None:
        return next((dict(p) for p in self._positions() if p.get("id") == pid), None)

    def positions(self) -> list[dict]:
        return sorted(self._positions(), key=lambda p: p.get("opened", ""), reverse=True)

    def close_position(self, pid: str, exit_value: float) -> dict | None:
        rows = self._positions()
        for p in rows:
            if p.get("id") == pid and p.get("status") == "open":
                p.update(status="closed", closed=_now(), exit_value=exit_value)
                self._save("positions", rows)
        return self.position(pid)
