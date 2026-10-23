"""Entry point for the static demo in Pyodide: the same handlers as the server, on localStorage.

Static mode means demo data only, rule-based chat, and nothing that touches the network:
no anthropic, requests, SQLite or live market adapters are imported.
"""

from __future__ import annotations

import json
import os
from datetime import date

from .browser_store import BrowserStore
from .data.market import MarketData
from .handlers import Api

_api: Api | None = None


def init(storage, today_iso: str | None = None) -> None:
    global _api
    os.environ["CHARLIE_DATA"] = "mock"
    os.environ["CHARLIE_LLM"] = "off"
    today = date.fromisoformat(today_iso) if today_iso else date.today()
    _api = Api(BrowserStore(storage), MarketData(mode="mock", today=today, cache_dir="/tmp/charlie-cache"), static=True)


def request(method: str, path: str, query_json: str = "{}", body_json: str = "null") -> str:
    """JSON in, JSON out ({"status", "body"}), so nothing but strings crosses the JS boundary."""
    if _api is None:
        raise RuntimeError("call charlie.browser.init() first")
    status, body = _api.route(method, path, json.loads(query_json or "{}"), json.loads(body_json or "null"))
    return json.dumps({"status": status, "body": body})
