"""M3.1 Hunch pipeline v1 (CHL-HUNCH-1 to 17): failing-first tests, written by qa-tdd before any code.

Acceptance criteria: PLAN.md, M3.1. The browser half (tab visible locally, hidden in static, NFA on
the panel and cards, fit and axe at 390/1280 light/dark) is in tests/e2e/test_hunch_e2e.py.
Only fictional data here; nothing touches the network (Claude is always a fake).

Pinned interface (the engineer builds to this; change it only by changing these tests first)
---------------------------------------------------------------------------------------------
Module ``charlie/hunch.py``. It must not import ``anthropic`` at module level.

``run_hunch(text: str, md, profile, level: int | None = None, client=None) -> dict``
    ``client`` is a Claude-like drafter or None. None means no LLM: playbook or nothing.
    ``level`` defaults to ``profile.risk_level``. The result is plain JSON (``allow_nan=False``):

    restate      {"claim": str, "horizon": str}
    premise      {"verdict": "true"|"partial"|"false"|None, "true": [str], "added": [str],
                  "evidence": [{"source": str, "date": "YYYY-MM[-DD]", "fact": str}],
                  "label": "Claude's draft, sources not checked"   # only when source == "claude"}
                  verdict is None only when source == "none": Charlie didn't check the premise, so it
                  never reads as "false" (CHL-HUNCH-12); playbook and Claude results always carry one.
    chain        [player], every player:
                  {"symbol": str|None, "name": str, "role": str, "tier": "obvious"|"sleeper"|"loser",
                   "listing": "us"|"non_us"|"private", "exposure": "pure_play"|"meaningful"|"small_slice",
                   "scored": bool, "unscored_reason": str|None, "price": float|None, "score": int|None}
                  price is md.quote(symbol)["price"] and score is engine.analyze(...)["charlie"]["score"]
                  for scored players; both None for unscored ones.
    unscored     [{"symbol": str|None, "name": str, "reason": str}]  (players not in the universe,
                  non-US, private, unknown or malformed tickers)
    ranked       [{"symbol", "name", "exposure", "weight", "score", "rank_score"}], scored players only,
                  rank_score = weight x score with pure_play 1.0, meaningful 0.6, small_slice 0.25,
                  sorted by rank_score descending, ties by symbol ascending.
    ideas        <= 3, from ranked (in ranked order), never a loser-tier player:
                  {"symbol", "name", "label": "research lead", "why": str, "key_risk": str,
                   "trade": dict|None (a strategies.build() trade dict), "disclaimer": NFA}
    signals      {"confirm": [3 str], "kill": [3 str]}
    source       "playbook" | "claude" | "none"
    message      str|None; when source == "none" it says there is no playbook yet and names the
                  closest universe domain's label, if any
    closest_domain  universe domain key or None (meaningful when source == "none")
    disclaimer   NFA ("Not financial advice. Paper trading only."), added by code
    The phrase "most exposed" appears in the hunch's own copy (for example the top ranked label).

``claude_client() -> object | None``: None unless ``chat.llm_available()``. The object it returns
    has ``draft(text: str) -> str`` (JSON text) and sends Anthropic only the hunch text as the one
    user message. Tests monkeypatch ``charlie.hunch.claude_client``, so callers must look it up on
    the module at call time.

Claude drafter contract (what ``draft()`` returns, validated by our code):
    {"restate": {...}, "premise": {"verdict", "true", "added", "evidence"}, "players": [player
     without scored/price/score], "signals": {"confirm", "kill"}}. Anything else (price, score,
    max_loss, ...) is dropped; invalid JSON, a schema miss or an exception falls back to the
    playbook, or to source "none".

``Api.hunch(text, risk=None) -> dict`` uses the current profile and, unless static,
    ``client=hunch.claude_client()``. 422 when text is empty/blank or over 600 characters.
    Routes: ``POST /api/hunch`` with JSON ``{"text": str, "risk": int|None}`` in server.py and in
    ``Api.route``. In static mode (``Api(static=True)``) the route answers 404.

Web: a tab button ``data-tab="hunch"`` named "Hunches" with panel ``#tab-hunch``, both marked
    ``server-only`` so the static demo hides them.

CHL-HUNCH-16 scope: the reused trade dicts (``idea["trade"]``) carry the existing strategy copy
("Buy shares", "BUY TO OPEN", "protecting a big winner"), so the forbidden-word check covers every
hunch-authored string in the result except the ``trade`` subtrees. Words match on word boundaries,
so "buyback" or "buying" don't count.
"""
from __future__ import annotations

import importlib
import json
import logging
import math
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from charlie import engine
from charlie.data.market import MarketData
from charlie.handlers import Api
from charlie.profile import Profile, build_profile
from charlie.store import Store
from charlie.strategies import allowed
from charlie.universe import DOMAIN_BY_KEY, lookup

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DAY = date(2026, 10, 22)
LOOPBACK = "http://127.0.0.1:8000"
NFA = "Not financial advice. Paper trading only."
CLAUDE_LABEL = "Claude's draft, sources not checked"

# Case 1, in the words a person would type.
HEARING = ("Everyone wears earbuds all day now and OTC hearing aids are legal, "
           "so hearing health is about to become a huge consumer market.")
AI_POWER = "AI data centers need so much electricity that power demand is going to explode."
CYBER_NO_PLAYBOOK = "Cybersecurity budgets will keep growing because every company is a target."
GIBBERISH = "Zorbly quandix flemwort will plonk the wibbertons."

TIERS = {"obvious", "sleeper", "loser"}
LISTINGS = {"us", "non_us", "private"}
# The plan's ranking table (PLAN.md, "Ranking, plainly"), not the code's own constant.
WEIGHTS = {"pure_play": 1.0, "meaningful": 0.6, "small_slice": 0.25}
TOP_KEYS = {"restate", "premise", "chain", "ranked", "unscored", "ideas", "signals", "source", "disclaimer"}
FORBIDDEN = re.compile(r"\b(winners?|buy|recommend(?:s|ed|ing|ation|ations)?|guaranteed?)\b", re.I)


# ----------------------------------------------------------------------------- helpers

@pytest.fixture
def hunch():
    """charlie.hunch, imported per test so every test fails on its own until the module exists."""
    return importlib.import_module("charlie.hunch")


@pytest.fixture
def md(tmp_path):
    return MarketData(mode="mock", today=DAY, cache_dir=str(tmp_path / "cache"))


def _profile(capital: float = 30000, level: int = 3) -> Profile:
    # A fictional person: only interests, no resume.
    return build_profile(interests="audio gear, consumer tech, semiconductors", capital=capital, risk_level=level)


def _json(result: dict) -> dict:
    """What crosses the API or Pyodide boundary; NaN or inf fail here."""
    return json.loads(json.dumps(result, allow_nan=False))


def _player(result: dict, needle: str) -> dict:
    needle = needle.lower()
    hits = [p for p in result["chain"] if needle in (p.get("name") or "").lower()
            or needle == (p.get("symbol") or "").lower()]
    assert hits, f"no player matching {needle!r} in {[p.get('name') for p in result['chain']]}"
    return hits[0]


def _strings(node, skip=("trade",)):
    """Every user-facing string in a result, outside the reused trade dicts (see module docstring)."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            if k not in skip:
                yield from _strings(v, skip)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v, skip)


def _trades(result: dict) -> list[dict]:
    return [i["trade"] for i in result["ideas"] if i.get("trade")]


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


class FakeClaude:
    """A Claude-like drafter: draft(text) -> JSON text. Records every call's arguments."""

    def __init__(self, reply=None, exc: Exception | None = None):
        self.reply, self.exc, self.calls = reply, exc, []

    def draft(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc:
            raise self.exc
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


def claude_draft() -> dict:
    """A schema-valid Claude draft for the hearing hunch (fictional wording, real public facts)."""
    return {
        "restate": {"claim": "Earbuds that double as OTC hearing aids grow the hearing market.",
                    "horizon": "3 to 5 years"},
        "premise": {
            "verdict": "partial",
            "true": ["OTC hearing aids have been legal in the US since 2022."],
            "added": ["That most earbud wearers will use hearing features."],
            "evidence": [
                {"source": "FDA", "date": "2022-08-16", "fact": "Final rule creating OTC hearing aids."},
                {"source": "Apple", "date": "2024-09-09", "fact": "AirPods Pro 2 hearing aid feature announced."},
            ],
        },
        "players": [
            {"symbol": "AAPL", "name": "Apple", "role": "Earbuds with a hearing aid mode", "tier": "obvious",
             "listing": "us", "exposure": "small_slice"},
            {"symbol": "QCOM", "name": "Qualcomm", "role": "Audio chips in earbuds", "tier": "sleeper",
             "listing": "us", "exposure": "small_slice"},
            {"symbol": "COST", "name": "Costco", "role": "Hearing aid centers in stores", "tier": "obvious",
             "listing": "us", "exposure": "small_slice"},
            {"symbol": None, "name": "Sonova", "role": "Premium clinic-sold hearing aids", "tier": "loser",
             "listing": "non_us", "exposure": "pure_play"},
        ],
        "signals": {
            "confirm": ["OTC hearing aid unit sales rising each quarter",
                        "Earbud makers adding hearing tests to new models",
                        "Retailers widening hearing aid shelf space"],
            "kill": ["Users returning OTC devices at high rates",
                     "A rule change that limits OTC sales",
                     "Clinic channel prices holding up with no volume loss"],
        },
    }


def _static_api(md) -> Api:
    from charlie.browser_store import BrowserStore
    from charlie.demo import sample_profile

    class Storage(dict):
        getItem = dict.get

        def setItem(self, k, v):
            self[k] = v

        def removeItem(self, k):
            self.pop(k, None)
    return Api(BrowserStore(Storage()), md, static=True, default_profile=lambda level: sample_profile(DAY, level))


def _client(monkeypatch, md, store=None):
    from charlie import server
    monkeypatch.setattr(server, "store", store or Store(":memory:"))
    monkeypatch.setattr(server, "md", lambda: md)
    return TestClient(server.app, base_url=LOOPBACK, raise_server_exceptions=False)


def _no_claude(monkeypatch, hunch):
    monkeypatch.setattr(hunch, "claude_client", lambda: None)


# ============================================================ CHL-HUNCH-1 shape

@pytest.mark.parametrize("text,source", [(HEARING, "playbook"), (AI_POWER, "playbook"), (GIBBERISH, "none")])
def test_CHL_HUNCH_1_result_is_json_with_every_stage(hunch, md, text, source):
    r = hunch.run_hunch(text, md, _profile())
    assert r == _json(r)
    assert TOP_KEYS <= set(r), sorted(TOP_KEYS - set(r))
    assert r["source"] == source
    assert isinstance(r["chain"], list) and isinstance(r["ranked"], list)
    assert isinstance(r["unscored"], list) and isinstance(r["ideas"], list)
    assert set(r["signals"]) >= {"confirm", "kill"}


def test_CHL_HUNCH_1_llm_off_means_no_client_and_no_claude(hunch, monkeypatch):
    monkeypatch.setenv("CHARLIE_LLM", "off")
    assert hunch.claude_client() is None


# ============================================================ CHL-HUNCH-2 restate

def test_CHL_HUNCH_2_restates_the_hearing_claim_with_a_horizon(hunch, md):
    r = hunch.run_hunch(HEARING, md, _profile())
    claim, horizon = r["restate"]["claim"], r["restate"]["horizon"]
    assert isinstance(claim, str) and claim.strip()
    assert isinstance(horizon, str) and horizon.strip()
    assert re.search(r"earbud|otc hearing aid", claim, re.I), claim


# ============================================================ CHL-HUNCH-3 premise

def test_CHL_HUNCH_3_premise_is_partial_with_true_and_added_kept_apart(hunch, md):
    p = hunch.run_hunch(HEARING, md, _profile())["premise"]
    assert p["verdict"] == "partial"
    assert isinstance(p["true"], list) and p["true"] and all(isinstance(x, str) and x.strip() for x in p["true"])
    assert isinstance(p["added"], list) and p["added"] and all(isinstance(x, str) and x.strip() for x in p["added"])
    assert not set(p["true"]) & set(p["added"])
    assert "label" not in p or p["label"] != CLAUDE_LABEL  # the playbook is not Claude's draft


def test_CHL_HUNCH_3_evidence_cites_the_fda_otc_rule_and_airpods_pro_2(hunch, md):
    ev = hunch.run_hunch(HEARING, md, _profile())["premise"]["evidence"]
    for e in ev:
        assert isinstance(e.get("source"), str) and e["source"].strip(), e
        assert re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", str(e.get("date"))), e
    fda = [e for e in ev if "fda" in e["source"].lower() and e["date"].startswith("2022-08")]
    assert fda, "no FDA OTC hearing aid rule (Aug 2022) in the evidence"
    assert any("otc" in json.dumps(e).lower() for e in fda)
    apple = [e for e in ev if "apple" in e["source"].lower() and e["date"].startswith("2024-09")]
    assert apple, "no Apple AirPods Pro 2 hearing aid feature (Sep 2024) in the evidence"
    assert any("airpods pro 2" in json.dumps(e).lower() for e in apple)


# ============================================================ CHL-HUNCH-4 chain

def test_CHL_HUNCH_4_every_player_is_fully_described(hunch, md):
    chain = hunch.run_hunch(HEARING, md, _profile())["chain"]
    assert chain
    for p in chain:
        assert isinstance(p.get("name"), str) and p["name"].strip(), p
        assert isinstance(p.get("role"), str) and p["role"].strip(), p
        assert p.get("tier") in TIERS, p
        assert "symbol" in p and (p["symbol"] is None or isinstance(p["symbol"], str)), p
        assert p.get("listing") in LISTINGS, p
        assert p.get("exposure") in WEIGHTS, p


def test_CHL_HUNCH_4_knowles_and_qualcomm_are_sleepers_and_clinic_aids_lose(hunch, md):
    r = hunch.run_hunch(HEARING, md, _profile())
    assert _player(r, "knowles")["tier"] == "sleeper"
    assert _player(r, "qualcomm")["tier"] == "sleeper"
    losers = [p for p in r["chain"] if p["tier"] == "loser"]
    assert any(re.search(r"clinic", f"{p['name']} {p['role']}", re.I) for p in losers), losers


# ============================================================ CHL-HUNCH-5 unscored players

@pytest.mark.parametrize("needle,listing", [("knowles", "us"), ("regeneron", "us"),
                                            ("sonova", "non_us"), ("loop", "private")])
def test_CHL_HUNCH_5_players_charlie_cant_score_stay_on_the_map(hunch, md, needle, listing):
    r = hunch.run_hunch(HEARING, md, _profile())
    p = _player(r, needle)
    assert p["listing"] == listing
    assert p["scored"] is False and p["price"] is None and p["score"] is None
    assert isinstance(p["unscored_reason"], str) and p["unscored_reason"].strip()
    row = [u for u in r["unscored"] if u["name"] == p["name"]]
    assert row and isinstance(row[0]["reason"], str) and row[0]["reason"].strip()
    assert p["name"] not in {x["name"] for x in r["ranked"]}
    assert p["name"] not in {i["name"] for i in r["ideas"]}


def test_CHL_HUNCH_5_unscored_symbols_are_ones_outside_the_universe(hunch, md):
    r = hunch.run_hunch(HEARING, md, _profile())
    for p in r["chain"]:
        in_universe = p["symbol"] is not None and lookup(p["symbol"]) is not None and p["listing"] == "us"
        assert p["scored"] is in_universe, p


def test_CHL_HUNCH_5_api_answers_200_for_the_hearing_hunch(hunch, md, monkeypatch):
    _no_claude(monkeypatch, hunch)
    r = _client(monkeypatch, md).post("/api/hunch", json={"text": HEARING})
    assert r.status_code == 200, r.text
    assert any(u["name"] for u in r.json()["unscored"])


# ============================================================ CHL-HUNCH-6 our code prices and scores

def test_CHL_HUNCH_6_claudes_numbers_are_dropped_and_bad_tickers_unscored(hunch, md):
    d = claude_draft()
    d["players"][0].update(price=9999.99, score=100, max_loss=31337.17)  # AAPL
    d["players"].append({"symbol": "ZZZZQ", "name": "Made-up Audio Co", "role": "Earbud tips", "tier": "sleeper",
                         "listing": "us", "exposure": "pure_play", "price": 1.23})
    d["players"].append({"symbol": "AAPL; DROP", "name": "Broken Ticker Inc", "role": "Cases", "tier": "obvious",
                         "listing": "us", "exposure": "meaningful"})
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(d))
    assert r["source"] == "claude"
    blob = json.dumps(r)
    for sentinel in ("9999.99", "31337.17", "1.23"):
        assert sentinel not in blob, sentinel
    aapl = _player(r, "apple")
    assert aapl["price"] == md.quote("AAPL")["price"]
    assert aapl["score"] == engine.analyze(md, _profile(), "AAPL")["charlie"]["score"]
    assert "max_loss" not in aapl
    for needle in ("made-up audio", "broken ticker"):
        p = _player(r, needle)
        assert p["scored"] is False and p["price"] is None and p["score"] is None
        assert p["name"] in {u["name"] for u in r["unscored"]}
    assert "AAPL; DROP" not in {x["symbol"] for x in r["ranked"]}


@pytest.mark.parametrize("text", [HEARING, AI_POWER])
def test_CHL_HUNCH_6_every_price_shown_is_the_market_quote(hunch, md, text):
    r = hunch.run_hunch(text, md, _profile())
    priced = [p for p in r["chain"] if p["price"] is not None]
    assert priced
    for p in priced:
        assert p["price"] == md.quote(p["symbol"])["price"], p
    for t in _trades(r):
        assert t["spot"] == pytest.approx(md.quote(t["symbol"])["price"], abs=0.006)


# ============================================================ CHL-HUNCH-7 ranking

@pytest.mark.parametrize("text", [HEARING, AI_POWER])
def test_CHL_HUNCH_7_ranking_is_exposure_times_score_ties_by_symbol(hunch, md, text):
    p = _profile()
    r = hunch.run_hunch(text, md, p)
    assert r["ranked"]
    scored = {x["symbol"] for x in r["chain"] if x["scored"]}
    for x in r["ranked"]:
        assert x["symbol"] in scored
        assert x["weight"] == WEIGHTS[x["exposure"]]
        assert x["score"] == engine.analyze(md, p, x["symbol"])["charlie"]["score"]
        assert x["rank_score"] == pytest.approx(WEIGHTS[x["exposure"]] * x["score"], abs=0.01)
    expected = sorted(r["ranked"], key=lambda x: (-x["rank_score"], x["symbol"]))
    assert [x["symbol"] for x in r["ranked"]] == [x["symbol"] for x in expected]


def test_CHL_HUNCH_7_same_hunch_profile_and_day_rank_the_same(hunch, tmp_path):
    a = hunch.run_hunch(AI_POWER, MarketData(mode="mock", today=DAY, cache_dir=str(tmp_path / "a")), _profile())
    b = hunch.run_hunch(AI_POWER, MarketData(mode="mock", today=DAY, cache_dir=str(tmp_path / "b")), _profile())
    assert [x["symbol"] for x in a["ranked"]] == [x["symbol"] for x in b["ranked"]]
    assert a == b


def test_CHL_HUNCH_7_ai_power_maps_its_universe_names(hunch, md):
    r = hunch.run_hunch(AI_POWER, md, _profile())
    assert {"NVDA", "ANET", "VST", "NEE", "GE", "CAT"} <= {x["symbol"] for x in r["chain"] if x["scored"]}


# ============================================================ CHL-HUNCH-8 familiarity never sizes

def _with_familiarity(base: Profile, symbols, fam: int) -> Profile:
    d = base.to_dict()
    d["tickers"] = [{"symbol": s, "name": lookup(s).name, "domain": lookup(s).domain, "familiarity": fam,
                     "why": [f"familiarity set to {fam} for the test"]} for s in symbols]
    return Profile.from_dict(d)


@pytest.mark.parametrize("text,syms", [(HEARING, ["AAPL", "QCOM", "COST", "WMT"]),
                                       (AI_POWER, ["NVDA", "ANET", "VST", "NEE", "GE", "CAT"])])
@pytest.mark.parametrize("level", [1, 3, 5])
def test_CHL_HUNCH_8_familiarity_moves_rank_never_size(hunch, md, text, syms, level):
    base = build_profile(capital=30000, risk_level=level)
    low = hunch.run_hunch(text, md, _with_familiarity(base, syms, 5), level=level)
    high = hunch.run_hunch(text, md, _with_familiarity(base, syms, 95), level=level)
    lo = {i["symbol"]: i["trade"] for i in low["ideas"] if i.get("trade")}
    hi = {i["symbol"]: i["trade"] for i in high["ideas"] if i.get("trade")}
    common = [s for s in lo if s in hi and lo[s]["strategy"] == hi[s]["strategy"]]
    assert common, (sorted(lo), sorted(hi))
    for s in common:
        assert lo[s]["contracts"] == hi[s]["contracts"], s
        assert [leg["qty"] for leg in lo[s]["legs"]] == [leg["qty"] for leg in hi[s]["legs"]], s
        assert lo[s]["max_loss"] == hi[s]["max_loss"], s


# ============================================================ CHL-HUNCH-9 ideas and safe trades

@pytest.mark.parametrize("text", [HEARING, AI_POWER])
@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_CHL_HUNCH_9_at_most_3_research_leads_with_safe_trades(hunch, md, text, level):
    p = _profile(level=level)
    r = hunch.run_hunch(text, md, p, level=level)
    ranked = [x["symbol"] for x in r["ranked"]]
    losers = {x["symbol"] for x in r["chain"] if x["tier"] == "loser"}
    assert len(r["ideas"]) <= 3
    syms = [i["symbol"] for i in r["ideas"]]
    assert syms == sorted(syms, key=ranked.index), "ideas follow the ranking"
    for i in r["ideas"]:
        assert lookup(i["symbol"]) is not None and i["symbol"] not in losers
        assert isinstance(i["why"], str) and i["why"].strip()
        assert isinstance(i["key_risk"], str) and i["key_risk"].strip()
        t = i.get("trade")
        if t is None:
            continue
        assert t["symbol"] == i["symbol"]
        assert t["strategy"] in allowed(level)
        assert _finite(t["max_loss"]) and t["max_loss"] > 0
        assert _finite(t["breakeven"]) and t["breakeven"] > 0
        assert t["management"] and all(isinstance(m, str) and m.strip() for m in t["management"])
        for leg in t["legs"]:
            if leg["instrument"] == "call" and leg["action"] == "sell":  # only ever covered
                assert t["strategy"] in ("covered_call", "collar")
                assert p.holdings.get(t["symbol"], 0) >= 100 * leg["qty"]
            if leg["instrument"] != "stock":
                assert date.fromisoformat(leg["expiry"]) >= DAY + timedelta(days=20), leg
        if t["dte"] is not None:
            assert t["dte"] >= 20


# ============================================================ CHL-HUNCH-10 NFA added by code

@pytest.mark.parametrize("text", [HEARING, AI_POWER, GIBBERISH])
def test_CHL_HUNCH_10_result_ideas_and_trades_carry_the_disclaimer(hunch, md, text):
    r = hunch.run_hunch(text, md, _profile())
    assert r["disclaimer"] == NFA
    for i in r["ideas"]:
        assert i["disclaimer"] == NFA
        if i.get("trade"):
            assert i["trade"]["disclaimer"] == NFA


def test_CHL_HUNCH_10_claude_path_carries_the_disclaimer_even_if_claude_omits_it(hunch, md):
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(claude_draft()))
    assert r["source"] == "claude" and r["disclaimer"] == NFA
    assert all(i["disclaimer"] == NFA for i in r["ideas"])


# ============================================================ CHL-HUNCH-11 signals

@pytest.mark.parametrize("text", [HEARING, AI_POWER])
def test_CHL_HUNCH_11_three_confirm_and_three_kill_signals(hunch, md, text):
    s = hunch.run_hunch(text, md, _profile())["signals"]
    for side in ("confirm", "kill"):
        assert len(s[side]) == 3, s[side]
        assert all(isinstance(x, str) and len(x.strip().split()) >= 3 for x in s[side]), s[side]
    assert not set(s["confirm"]) & set(s["kill"])


# ============================================================ CHL-HUNCH-12 no playbook, no LLM

def test_CHL_HUNCH_12_unknown_hunch_says_no_playbook_and_names_the_closest_domain(hunch, md):
    r = hunch.run_hunch(CYBER_NO_PLAYBOOK, md, _profile())
    assert r["source"] == "none"
    assert "no playbook yet" in r["message"].lower()
    assert r["closest_domain"] == "cybersecurity"
    assert DOMAIN_BY_KEY["cybersecurity"].label in r["message"]
    assert r["chain"] == [] and r["ranked"] == [] and r["ideas"] == [] and _trades(r) == []


def test_CHL_HUNCH_12_gibberish_has_no_closest_domain(hunch, md):
    r = hunch.run_hunch(GIBBERISH, md, _profile())
    assert r["source"] == "none" and r["closest_domain"] is None
    assert "no playbook yet" in r["message"].lower()
    assert r["chain"] == [] and r["ideas"] == []


@pytest.mark.parametrize("text", [CYBER_NO_PLAYBOOK, GIBBERISH], ids=["closest_domain", "gibberish"])
def test_CHL_HUNCH_12_unmatched_hunch_leaves_the_premise_unchecked_not_false(hunch, md, text):
    # No playbook and no Claude means nobody judged the premise: it must not read as "false".
    r = hunch.run_hunch(text, md, _profile())
    assert r["source"] == "none"
    assert r["premise"] == {"verdict": None, "true": [], "added": [], "evidence": []}
    json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("text", [HEARING, AI_POWER], ids=["hearing", "ai_power"])
def test_CHL_HUNCH_12_matched_hunch_always_carries_a_verdict(hunch, md, text):
    r = hunch.run_hunch(text, md, _profile())
    assert r["source"] == "playbook"
    assert r["premise"]["verdict"] in {"true", "partial", "false"}


def test_CHL_HUNCH_12_claude_draft_always_carries_a_verdict(hunch, md):
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(claude_draft()))
    assert r["source"] == "claude"
    assert r["premise"]["verdict"] in {"true", "partial", "false"}


# ============================================================ CHL-HUNCH-13 Claude falls back safely

BAD_CLAUDE = {
    "invalid_json": lambda: FakeClaude("this is not json {"),
    "schema_miss": lambda: FakeClaude({"restate": {"claim": "x"}}),
    "bad_enums": lambda: FakeClaude({**claude_draft(), "players": [{**claude_draft()["players"][0], "tier": "rocket"}]}),
    "raises": lambda: FakeClaude(exc=RuntimeError("upstream timeout")),
}


@pytest.mark.parametrize("case", sorted(BAD_CLAUDE))
@pytest.mark.parametrize("text,fallback", [(HEARING, "playbook"), (GIBBERISH, "none")])
def test_CHL_HUNCH_13_bad_claude_falls_back(hunch, md, case, text, fallback):
    r = hunch.run_hunch(text, md, _profile(), client=BAD_CLAUDE[case]())
    assert r["source"] == fallback
    assert r == _json(r) and r["disclaimer"] == NFA


@pytest.mark.parametrize("case", sorted(BAD_CLAUDE))
def test_CHL_HUNCH_13_bad_claude_is_still_a_200_from_the_api(hunch, md, monkeypatch, case):
    monkeypatch.setattr(hunch, "claude_client", BAD_CLAUDE[case])
    r = _client(monkeypatch, md).post("/api/hunch", json={"text": HEARING})
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "playbook"


def test_CHL_HUNCH_13_valid_claude_draft_is_labeled_unchecked(hunch, md):
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(claude_draft()))
    assert r["source"] == "claude"
    assert r["premise"]["label"] == CLAUDE_LABEL
    assert r["restate"]["claim"] == claude_draft()["restate"]["claim"]


def test_CHL_HUNCH_13_api_uses_claude_when_a_client_exists(hunch, md, monkeypatch):
    monkeypatch.setattr(hunch, "claude_client", lambda: FakeClaude(claude_draft()))
    status, out = Api(Store(":memory:"), md).route("POST", "/api/hunch", None, {"text": HEARING})
    assert status == 200 and out["source"] == "claude" and out["premise"]["label"] == CLAUDE_LABEL


# ============================================================ CHL-HUNCH-14 only the hunch goes to Claude

PRIVATE_MARKERS = ("Quentin Fictional", "31337", "ZZTOP")


def _private_profile() -> Profile:
    p = build_profile(interests="audio", capital=31337, risk_level=3, name="Quentin Fictional")
    p.holdings = {"ZZTOP": 400}
    return p


def test_CHL_HUNCH_14_drafter_gets_only_the_hunch_text(hunch, md):
    fake = FakeClaude(claude_draft())
    hunch.run_hunch(HEARING, md, _private_profile(), client=fake)
    assert fake.calls == [((HEARING,), {})]


def test_CHL_HUNCH_14_api_sends_no_profile_holdings_or_capital(hunch, md, monkeypatch):
    fake = FakeClaude(claude_draft())
    monkeypatch.setattr(hunch, "claude_client", lambda: fake)
    store = Store(":memory:")
    store.put("profile", _private_profile().to_dict())
    status, _ = Api(store, md).route("POST", "/api/hunch", None, {"text": HEARING})
    assert status == 200
    sent = json.dumps(fake.calls)
    assert HEARING in sent
    for m in PRIVATE_MARKERS:
        assert m not in sent, m


def test_CHL_HUNCH_14_real_adapter_request_carries_only_the_hunch(hunch, monkeypatch):
    import anthropic
    calls = []
    reply = NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(claude_draft()))])

    def create(**kw):
        calls.append(kw)
        return reply
    fake = NS(messages=NS(create=create), beta=NS(messages=NS(create=create)))
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: fake)
    monkeypatch.setenv("CHARLIE_LLM", "on")
    client = hunch.claude_client()
    assert client is not None
    client.draft(HEARING)
    assert len(calls) == 1
    msgs = calls[0]["messages"]
    assert [m["role"] for m in msgs] == ["user"]
    content = msgs[0]["content"]
    text = content if isinstance(content, str) else "".join(b.get("text", "") for b in content)
    assert text == HEARING
    sent = json.dumps(calls[0], default=str)
    for m in PRIVATE_MARKERS:
        assert m not in sent


def test_CHL_HUNCH_14_nothing_logged_but_the_length(hunch, md, monkeypatch, caplog, capsys):
    marker = "Quixotic-marker-earbuds hearing hunch"
    text = f"{HEARING} {marker}"
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(hunch, "claude_client", lambda: FakeClaude(exc=RuntimeError(f"echo: {text}")))
    store = Store(":memory:")
    store.put("profile", _private_profile().to_dict())
    status, _ = Api(store, md).route("POST", "/api/hunch", None, {"text": text})
    assert status == 200
    hunch.run_hunch(text, md, _private_profile(), client=FakeClaude("not json"))
    out = capsys.readouterr()
    logged = caplog.text + out.out + out.err
    assert "Quixotic-marker" not in logged
    for m in PRIVATE_MARKERS:
        assert m not in logged


# ============================================================ CHL-HUNCH-15 limits and static mode

@pytest.mark.parametrize("text", ["", "   ", "x" * 601])
def test_CHL_HUNCH_15_empty_or_too_long_is_422_on_the_server(hunch, md, monkeypatch, text):
    _no_claude(monkeypatch, hunch)
    r = _client(monkeypatch, md).post("/api/hunch", json={"text": text})
    assert r.status_code == 422, r.text


@pytest.mark.parametrize("text", ["", "   ", "x" * 601])
def test_CHL_HUNCH_15_empty_or_too_long_is_422_in_the_router(hunch, md, monkeypatch, text):
    _no_claude(monkeypatch, hunch)
    status, out = Api(Store(":memory:"), md).route("POST", "/api/hunch", None, {"text": text})
    assert status == 422, out


def test_CHL_HUNCH_15_600_characters_is_allowed(hunch, md, monkeypatch):
    _no_claude(monkeypatch, hunch)
    text = (HEARING + " ") * 10
    text = text[:600]
    assert len(text) == 600
    assert _client(monkeypatch, md).post("/api/hunch", json={"text": text}).status_code == 200
    status, _ = Api(Store(":memory:"), md).route("POST", "/api/hunch", None, {"text": text})
    assert status == 200


def test_CHL_HUNCH_15_static_mode_has_no_hunch_route(hunch, md, monkeypatch):
    called = []
    monkeypatch.setattr(hunch, "claude_client", lambda: called.append(1) or FakeClaude(claude_draft()))
    status, _ = _static_api(md).route("POST", "/api/hunch", None, {"text": HEARING})
    assert status == 404
    assert called == []


def test_CHL_HUNCH_15_static_mode_never_imports_anthropic(hunch):
    # A fresh interpreter, with the LLM switched on, so only static mode keeps Claude out.
    code = (
        "import sys, json\n"
        "from datetime import date\n"
        "import charlie.hunch as hunch\n"
        "from charlie.browser_store import BrowserStore\n"
        "from charlie.data.market import MarketData\n"
        "from charlie.demo import sample_profile\n"
        "from charlie.handlers import Api\n"
        "class S(dict):\n"
        "    getItem = dict.get\n"
        "    def setItem(self, k, v): self[k] = v\n"
        "    def removeItem(self, k): self.pop(k, None)\n"
        "day = date(2026, 10, 22)\n"
        "md = MarketData(mode='mock', today=day)\n"
        "api = Api(BrowserStore(S()), md, static=True, default_profile=lambda l: sample_profile(day, l))\n"
        "status, _ = api.route('POST', '/api/hunch', None, {'text': 'earbuds and OTC hearing aids'})\n"
        "print(json.dumps({'status': status, 'anthropic': 'anthropic' in sys.modules}))\n"
    )
    env = {**os.environ, "CHARLIE_DATA": "mock", "CHARLIE_LLM": "on", "ANTHROPIC_API_KEY": "placeholder-not-a-key"}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res == {"status": 404, "anthropic": False}


def test_CHL_HUNCH_15_hunches_tab_exists_and_is_server_only():
    html = (WEB / "index.html").read_text()
    btn = re.search(r'<button[^>]*data-tab="hunch"[^>]*>(.*?)</button>', html, re.S)
    assert btn, "no Hunches tab button"
    assert re.search(r'role="tab"', btn.group(0)) and btn.group(1).strip() == "Hunches"
    assert "server-only" in btn.group(0)
    panel = re.search(r'<section[^>]*id="tab-hunch"[^>]*>', html)
    assert panel and "server-only" in panel.group(0) and 'role="tabpanel"' in panel.group(0)


# ============================================================ CHL-HUNCH-16 words

def _hunch_copy(result: dict) -> list[str]:
    return list(_strings(result))


@pytest.mark.parametrize("text", [HEARING, AI_POWER, CYBER_NO_PLAYBOOK, GIBBERISH])
def test_CHL_HUNCH_16_no_forbidden_words_in_hunch_copy(hunch, md, text):
    r = hunch.run_hunch(text, md, _profile())
    hits = [s for s in _hunch_copy(r) if FORBIDDEN.search(s)]
    assert hits == []


def test_CHL_HUNCH_16_research_lead_and_most_exposed_labels(hunch, md):
    r = hunch.run_hunch(HEARING, md, _profile())
    assert r["ideas"] and all(i["label"] == "research lead" for i in r["ideas"])
    assert any("most exposed" in s.lower() for s in _hunch_copy(r))


def test_CHL_HUNCH_16_claudes_forbidden_words_never_reach_the_page(hunch, md):
    d = claude_draft()
    d["restate"]["claim"] = "Apple is the clear winner; buy it, guaranteed."
    d["premise"]["true"].append("Analysts recommend the earbud makers.")
    d["players"][0]["role"] = "The winner to buy"
    d["signals"]["confirm"][0] = "Guaranteed demand, so we recommend buying"
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(d))
    hits = [s for s in _hunch_copy(r) if FORBIDDEN.search(s)]
    assert hits == []


def test_CHL_HUNCH_16_word_check_is_on_word_boundaries():
    # The checker itself (a test bug is still a bug): legit substrings don't count.
    assert not FORBIDDEN.search("Shrinking share count from a steady buyback; buying is not the point.")
    assert FORBIDDEN.search("BUY now") and FORBIDDEN.search("a Winner") and FORBIDDEN.search("We recommend")
    assert FORBIDDEN.search("guaranteed upside") and FORBIDDEN.search("winners")


# ============================================================ M3.1 review fixes (red first, qa-tdd, Nov 17)
# Findings: privacy-security CHL-PS-H1 to H6 and ux-reviewer CHL-UX-H1 to H10 (the browser half is in
# tests/e2e/test_hunch_e2e.py). Decisions by the chief of staff: H3 keeps the top 3 leads but gives a paper
# trade only at or above the daily ideas' score floor for that level.

# ---------------------------------------------------------------- CHL-PS-H1 Claude's invented numbers

# (where in Claude's draft, the injected text, sentinels that must never reach any hunch string)
PS_H1_PAYLOADS = {
    "player_role": ("Trades at $412.50, Charlie score 99/100, max loss $0, risk-free",
                    ("$412.50", "99/100", "max loss $0", "risk-free")),
    "player_name": ("Sonova, price target $250, up 40% on its score",
                    ("$250", "price target", "40%")),
    "signal_confirm": ("Price target $900 by March", ("$900", "price target")),
    "signal_kill": ("Breakeven at $3.33 makes it risk-free", ("$3.33", "breakeven at", "risk-free")),
    "premise_true": ("Apple's score is 99/100 with max loss $0", ("99/100", "max loss $0")),
    "premise_added": ("Shares are risk-free with a target price of $777", ("risk-free", "$777")),
    "evidence_fact": ("Analysts set a price target of $888; breakeven is $12.", ("$888", "breakeven is")),
}


def _inject_ps_h1(d: dict, where: str, text: str) -> dict:
    if where == "player_role":
        d["players"][0]["role"] = text                    # AAPL, scored, so it feeds a lead's why
    elif where == "player_name":
        d["players"][3]["name"] = text                    # Sonova, unscored, so H2's rename can't hide it
    elif where == "signal_confirm":
        d["signals"]["confirm"][0] = text
    elif where == "signal_kill":
        d["signals"]["kill"][0] = text
    elif where == "premise_true":
        d["premise"]["true"].append(text)
    elif where == "premise_added":
        d["premise"]["added"].append(text)
    elif where == "evidence_fact":
        d["premise"]["evidence"].append({"source": "Some bank", "date": "2026-10", "fact": text})
    return d


@pytest.mark.parametrize("where", sorted(PS_H1_PAYLOADS))
def test_CHL_PS_H1_claude_text_numbers_never_reach_leads(hunch, md, where):
    text, sentinels = PS_H1_PAYLOADS[where]
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(_inject_ps_h1(claude_draft(), where, text)))
    assert r == _json(r)
    copy = [s.lower() for s in _hunch_copy(r)]  # every hunch string outside the engine's own trade dicts
    leaks = [(m, s) for m in sentinels for s in copy if m.lower() in s]
    assert leaks == [], leaks
    for side in ("confirm", "kill"):  # dropping a bad signal still leaves (or falls back to) 3 each
        assert len(r["signals"][side]) == 3, r["signals"]


def test_CHL_PS_H1_plain_percentages_in_premise_facts_still_show(hunch, md):
    # The other direction: a sourced fact with a plain percentage is not a price claim and survives.
    fact = "US data centers used about 4.4% of US electricity in 2023."
    d = claude_draft()
    d["premise"]["true"].append(fact)
    d["premise"]["evidence"].append({"source": "LBNL", "date": "2024-12", "fact": fact})
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(d))
    assert r["source"] == "claude"
    assert fact in r["premise"]["true"]
    assert fact in [e["fact"] for e in r["premise"]["evidence"]]


# ---------------------------------------------------------------- CHL-PS-H2 universe names for scored tickers

def test_CHL_PS_H2_scored_tickers_use_the_universe_name(hunch, md):
    d = claude_draft()
    d["players"][0]["name"] = "Totally Not Apple"  # AAPL
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(d))
    assert r["source"] == "claude"
    real = lookup("AAPL").name
    aapl = [p for p in r["chain"] if p["symbol"] == "AAPL"]
    assert aapl and aapl[0]["name"] == real, aapl
    assert [x["name"] for x in r["ranked"] if x["symbol"] == "AAPL"] == [real]
    assert all(i["name"] == real for i in r["ideas"] if i["symbol"] == "AAPL")
    assert "Totally Not Apple" not in json.dumps(r)


# ---------------------------------------------------------------- CHL-PS-H3 leads keep the daily score floor

@pytest.mark.parametrize("text", [HEARING, AI_POWER], ids=["hearing", "ai_power"])
@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_CHL_PS_H3_no_paper_trade_below_the_daily_score_floor(hunch, md, text, level):
    floor = engine.MIN_SCORE_BY_LEVEL[level]
    r = hunch.run_hunch(text, md, _profile(level=level), level=level)
    losers = {p["symbol"] for p in r["chain"] if p["tier"] == "loser"}
    eligible = [x for x in r["ranked"] if x["symbol"] not in losers]
    assert len(r["ideas"]) == min(3, len(eligible)), "leads still list the top 3"
    for i in r["ideas"]:
        if i["score"] >= floor:
            continue
        assert i["trade"] is None, f"{i['symbol']} scores {i['score']} < {floor} at level {level} but has a trade"
        note = i.get("trade_note") or ""
        assert re.search(r"\bscore\b", note, re.I) and re.search(r"risk level", note, re.I), note
        assert not re.search(r"MIN_SCORE|threshold|floor", note), note  # plain words, not code words


def test_CHL_PS_H3_the_floor_check_is_not_vacuous(hunch, md):
    # Pins that the case above really exercises a lead below the bar (COST and AAPL at level 1).
    r = hunch.run_hunch(HEARING, md, _profile(level=1), level=1)
    below = [i for i in r["ideas"] if i["score"] < engine.MIN_SCORE_BY_LEVEL[1]]
    above = [i for i in r["ideas"] if i["score"] >= engine.MIN_SCORE_BY_LEVEL[1]]
    assert below and above, [(i["symbol"], i["score"]) for i in r["ideas"]]
    assert all(i["trade"] for i in above)  # the other direction: at or above the bar, a trade is still offered


# ---------------------------------------------------------------- CHL-PS-H5 timeout and list caps

def _timeout_seconds(t):
    if isinstance(t, (int, float)) and not isinstance(t, bool):
        return float(t)
    parts = [getattr(t, k, None) for k in ("read", "connect", "write", "pool")]
    parts = [p for p in parts if isinstance(p, (int, float))]
    return max(parts) if parts else None


def test_CHL_PS_H5_anthropic_call_has_a_timeout_of_60s_or_less(hunch, monkeypatch):
    import anthropic
    made, calls = [], []
    reply = NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(claude_draft()))])

    def create(**kw):
        calls.append(kw)
        return reply

    def ctor(*a, **k):
        made.append(k)
        return NS(messages=NS(create=create), beta=NS(messages=NS(create=create)))
    monkeypatch.setattr(anthropic, "Anthropic", ctor)
    monkeypatch.setenv("CHARLIE_LLM", "on")
    hunch.claude_client().draft(HEARING)
    timeouts = [k["timeout"] for k in made + calls if "timeout" in k]
    assert timeouts, f"no explicit timeout (constructor {made}, create keys {[sorted(c) for c in calls]})"
    secs = [_timeout_seconds(t) for t in timeouts]
    assert all(s is not None and 0 < s <= 60 for s in secs), timeouts


def test_CHL_PS_H5_claudes_lists_are_capped(hunch, md):
    d = claude_draft()
    d["players"] += [{"symbol": None, "name": f"Overseas maker {n}", "role": "Hearing parts abroad",
                      "tier": "sleeper", "listing": "non_us", "exposure": "meaningful"} for n in range(500)]
    d["premise"]["true"] += [f"Supported point number {n}" for n in range(500)]
    d["premise"]["added"] += [f"Assumed point number {n}" for n in range(500)]
    d["premise"]["evidence"] += [{"source": f"Journal {n}", "date": "2025-01", "fact": f"Finding {n}"}
                                 for n in range(500)]
    d["signals"]["confirm"] += [f"Extra confirm sign {n}" for n in range(50)]
    d["signals"]["kill"] += [f"Extra kill sign {n}" for n in range(50)]
    r = hunch.run_hunch(HEARING, md, _profile(), client=FakeClaude(d))
    assert r["source"] == "claude"
    assert len(r["chain"]) <= 25, len(r["chain"])
    assert len(r["unscored"]) <= 25, len(r["unscored"])
    assert len(r["premise"]["evidence"]) <= 8, len(r["premise"]["evidence"])
    assert len(r["premise"]["true"]) <= 8, len(r["premise"]["true"])
    assert len(r["premise"]["added"]) <= 8, len(r["premise"]["added"])
    assert len(r["signals"]["confirm"]) == 3 and len(r["signals"]["kill"]) == 3


# ---------------------------------------------------------------- CHL-PS-H6 cross-site POST

@pytest.mark.parametrize("origin", ["https://evil.example", "http://127.0.0.1.evil.example:8000", "null"])
def test_CHL_PS_H6_cross_site_post_to_hunch_is_403_and_never_calls_claude(hunch, md, monkeypatch, origin):
    called = []
    monkeypatch.setattr(hunch, "claude_client", lambda: called.append(1) or FakeClaude(claude_draft()))
    r = _client(monkeypatch, md).post("/api/hunch", json={"text": HEARING}, headers={"Origin": origin})
    assert r.status_code == 403, (r.status_code, r.text[:200])
    assert called == []
    assert HEARING not in r.text


def test_CHL_PS_H6_same_origin_post_still_works(hunch, md, monkeypatch):
    # The other direction: the local app's own page can still run a hunch.
    _no_claude(monkeypatch, hunch)
    r = _client(monkeypatch, md).post("/api/hunch", json={"text": HEARING}, headers={"Origin": LOOPBACK})
    assert r.status_code == 200, r.text[:200]
