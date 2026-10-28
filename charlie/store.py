"""Tiny SQLite store: profile, saved screens, daily idea snapshots, paper positions."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS screens (id TEXT PRIMARY KEY, name TEXT NOT NULL, criteria TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS daily (day TEXT, level INTEGER, profile_hash TEXT, payload TEXT NOT NULL,
                                  PRIMARY KEY (day, level, profile_hash));
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY, opened TEXT NOT NULL, symbol TEXT NOT NULL, strategy TEXT NOT NULL,
    trade TEXT NOT NULL, entry_value REAL NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    closed TEXT, exit_value REAL, note TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path | None = None):
        import sqlite3  # here, not at the top: the browser demo imports this module but uses BrowserStore

        path = Path(path or os.environ.get("CHARLIE_DB", "data/charlie.db"))
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def _exec(self, sql: str, args=()):
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur

    # kv
    def get(self, key: str, default=None):
        row = self._exec("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return json.loads(row["v"]) if row else default

    def put(self, key: str, value) -> None:
        self._exec("INSERT INTO kv(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                   (key, json.dumps(value)))

    def delete(self, key: str) -> None:
        self._exec("DELETE FROM kv WHERE k=?", (key,))

    def wipe(self) -> None:
        """Delete everything: profile, resume, saved screens, cached ideas and paper trades."""
        with self._lock:
            for table in ("kv", "screens", "daily", "positions"):
                self._conn.execute(f"DELETE FROM {table}")
            self._conn.commit()

    # screens
    def save_screen(self, name: str, criteria: dict) -> dict:
        sid = uuid.uuid4().hex[:10]
        self._exec("INSERT INTO screens VALUES(?,?,?,?)", (sid, name, json.dumps(criteria), _now()))
        return {"id": sid, "name": name, "criteria": criteria}

    def screens(self) -> list[dict]:
        rows = self._exec("SELECT * FROM screens ORDER BY created DESC").fetchall()
        return [{"id": r["id"], "name": r["name"], "criteria": json.loads(r["criteria"]), "created": r["created"]} for r in rows]

    def delete_screen(self, sid: str) -> None:
        self._exec("DELETE FROM screens WHERE id=?", (sid,))

    # daily idea snapshots (so "today's ideas" stay stable through the day)
    def daily_get(self, day: str, level: int, profile_hash: str):
        row = self._exec("SELECT payload FROM daily WHERE day=? AND level=? AND profile_hash=?",
                         (day, level, profile_hash)).fetchone()
        return json.loads(row["payload"]) if row else None

    def daily_put(self, day: str, level: int, profile_hash: str, payload: dict) -> None:
        self._exec("INSERT OR REPLACE INTO daily VALUES(?,?,?,?)", (day, level, profile_hash, json.dumps(payload)))

    def clear_daily(self) -> None:
        self._exec("DELETE FROM daily")

    # paper positions
    def open_position(self, trade: dict, note: str = "") -> dict:
        pid = uuid.uuid4().hex[:10]
        entry = position_value(trade["legs"], {leg_key(l): l["price"] for l in trade["legs"]})
        self._exec("INSERT INTO positions(id, opened, symbol, strategy, trade, entry_value, note) VALUES(?,?,?,?,?,?,?)",
                   (pid, _now(), trade["symbol"], trade["strategy"], json.dumps(trade), entry, note))
        return self.position(pid)

    def position(self, pid: str) -> dict | None:
        r = self._exec("SELECT * FROM positions WHERE id=?", (pid,)).fetchone()
        return _row(r) if r else None

    def positions(self) -> list[dict]:
        return [_row(r) for r in self._exec("SELECT * FROM positions ORDER BY opened DESC").fetchall()]

    def close_position(self, pid: str, exit_value: float) -> dict | None:
        self._exec("UPDATE positions SET status='closed', closed=?, exit_value=? WHERE id=? AND status='open'",
                   (_now(), exit_value, pid))
        return self.position(pid)


def _row(r) -> dict:
    d = dict(r)
    d["trade"] = json.loads(d["trade"])
    return d


def leg_key(leg: dict) -> str:
    return leg["symbol"]


def position_value(legs: list[dict], prices: dict[str, float]) -> float:
    """Signed market value: what you'd receive (+) or pay (-) to liquidate.

    Long legs are worth +price, short legs -price; options x100.
    P&L = value_now - value_at_entry.
    """
    total = 0.0
    for leg in legs:
        mult = 1 if leg["instrument"] == "stock" else 100
        sign = 1 if leg["action"] == "buy" else -1
        total += sign * prices[leg_key(leg)] * mult * leg["qty"]
    return round(total, 2)
