"""Entry point for the static demo in Pyodide: the same handlers as the server, on localStorage.

Static mode means demo data only, rule-based chat, and nothing that touches the network:
no anthropic, requests, SQLite or live market adapters are imported. Until the visitor
saves a profile, they see the fictional sample person from demo.py.

prebuild() runs the same code at build time so the first screen shows before Pyodide loads
(M1.3). Those answers hold only while the visitor hasn't changed anything, which is when
none of INVALID_IF_KEYS exists in localStorage.
"""

from __future__ import annotations

import json
import os
from datetime import date

from .browser_store import PREFIX, BrowserStore
from .data.market import MarketData
from .demo import SAMPLE_LEVEL, SAMPLE_RESUME, sample_profile
from .handlers import Api

INVALID_IF_KEYS = [PREFIX + k for k in ("kv:profile", "kv:intake", "positions", "screens")]
COMMON_GETS = ["/api/meta", "/api/status", "/api/screens", "/api/paper"]

_api: Api | None = None


def init(storage, today_iso: str | None = None) -> None:
    global _api
    os.environ["CHARLIE_DATA"] = "mock"
    os.environ["CHARLIE_LLM"] = "off"
    today = date.fromisoformat(today_iso) if today_iso else date.today()
    _api = Api(BrowserStore(storage), MarketData(mode="mock", today=today, cache_dir="/tmp/charlie-cache"),
               static=True, default_profile=lambda level: sample_profile(today, level))


def request(method: str, path: str, query_json: str = "{}", body_json: str = "null") -> str:
    """JSON in, JSON out ({"status", "body"}), so nothing but strings crosses the JS boundary."""
    if _api is None:
        raise RuntimeError("call charlie.browser.init() first")
    status, body = _api.route(method, path, json.loads(query_json or "{}"), json.loads(body_json or "null"))
    return json.dumps({"status": status, "body": body})


class _Mem(dict):
    getItem = dict.get

    def setItem(self, k, v):
        self[k] = v

    def removeItem(self, k):
        self.pop(k, None)


def prebuild(today_iso: str, count: int = 3) -> dict:
    """The sample person's answers for every risk level, keyed "METHOD path" exactly as app.js asks."""
    def get(path):
        status, body = json.loads(request("GET", path)).values()
        assert status == 200, (path, body)
        return body

    init(_Mem(), today_iso)
    common = {f"GET {p}": get(p) for p in COMMON_GETS}
    levels = {}
    for lvl in range(1, 6):
        init(_Mem(), today_iso)
        risk = json.loads(request("POST", "/api/profile/risk", "{}", json.dumps({"risk_level": lvl})))["body"]
        entries = {"POST /api/profile/risk": risk, "GET /api/profile": get("/api/profile")}
        ideas_path = f"/api/ideas?risk={lvl}&count={count}"
        entries[f"GET {ideas_path}"] = ideas = get(ideas_path)
        for i in ideas["ideas"]:
            path = f"/api/ticker/{i['trade']['symbol']}?risk={lvl}"
            entries[f"GET {path}"] = get(path)
        levels[str(lvl)] = entries
    return {"date": today_iso, "default_risk": SAMPLE_LEVEL, "invalid_if_keys": INVALID_IF_KEYS,
            "sample_resume": SAMPLE_RESUME,  # fictional; the "Use the sample resume" button fills the form with it
            "common": common, "levels": levels}
