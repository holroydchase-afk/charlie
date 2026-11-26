"""Hunch pipeline v1 (PLAN M3.1): a plain-English hunch becomes a checked, ranked trail.

Stages, each a plain dict: restate -> premise -> chain -> enrich -> rank -> ideas -> signals.

Who writes what:
- The words (restated claim, premise check, players, signals) come from a curated playbook matched by
  keywords, or, when the LLM is available, from Claude's draft. Claude gets only the hunch text.
- Every number (price, Charlie score, trade, max loss) comes from our own code: ``md`` and the
  engine. Anything numeric in Claude's draft is dropped before it is read, and any Claude sentence that
  makes a price, score, loss or "risk-free" claim is dropped too (CHL-PS-H1).
- Familiarity moves rank (through the Charlie score), never size: trades are sized by
  ``strategies.build`` from capital and risk level only.

This module must not import ``anthropic`` at load time; ``claude_client`` imports it lazily.
"""

from __future__ import annotations

import json
import logging
import re

from . import engine
from .strategies import NFA, RISK_LEVELS, scenario
from .universe import DOMAIN_BY_KEY, DOMAINS, lookup

log = logging.getLogger(__name__)

MAX_HUNCH_CHARS = 600
WEIGHTS = {"pure_play": 1.0, "meaningful": 0.6, "small_slice": 0.25}
EXPOSURE_LABELS = {"pure_play": "pure play", "meaningful": "meaningful slice", "small_slice": "small slice"}
TIERS = ("obvious", "sleeper", "loser")
LISTINGS = ("us", "non_us", "private")
VERDICTS = ("true", "partial", "false")
CLAUDE_LABEL = "Claude's draft, sources not checked"
RANKED_LABEL = "Most exposed: exposure weight times Charlie score"
MAX_IDEAS = 3
MAX_PLAYERS = 20
MAX_LIST = 8  # premise true/added/evidence from Claude (CHL-PS-H5)
MAX_STR = 300
CLAUDE_TIMEOUT = 30  # seconds per request, one retry: a stuck call can't hang the tab (CHL-PS-H5)
HUNCH_SKIP = {"bull_call_spread"}

# Claude's sentences may describe the world, never a stock's numbers (CHL-PS-H1). Premise text may keep
# plain figures ("4.4% of US electricity"); player and signal text may not hold money or percentages at all.
_STOCK_CLAIM = re.compile(r"\b(scores?|max(?:imum)?\s+loss(?:es)?|break-?evens?|price\s+targets?|target\s+prices?"
                          r"|risk[- ]?free)\b|\d\s*/\s*100\b", re.I)
_MONEY_OR_PCT = re.compile(r"\$\s?\d|\d\s?%|\bper\s?cent\b", re.I)
# Names the bar and the score (CHL-UX-H14): "below the bar" alone never said what the bar is.
_TRADE_NOTE_BELOW_BAR = ("No paper trade for this one: at your risk level Charlie needs a score of {bar} or more, "
                         "and {name} scores {score}. It stays a lead to read about.")


def _stock_claim(text: str, strict: bool = False) -> bool:
    return bool(_STOCK_CLAIM.search(text) or (strict and _MONEY_OR_PCT.search(text)))


_DATE = re.compile(r"\d{4}-\d{2}(-\d{2})?")
_TICKER = re.compile(r"[A-Z]{1,5}(?:[.-][A-Z])?")

# Claims register (docs/product/MARKETING.md): the hunch never says these words. Claude's text is
# rewritten on word boundaries, so "buyback" or "buying" stay as they are.
_FORBIDDEN = re.compile(r"\b(winners?|buy|recommend(?:s|ed|ing|ation|ations)?|guaranteed?)\b", re.I)
_SWAP = {"winner": "leader", "winners": "leaders", "buy": "own", "guarantee": "promise", "guaranteed": "certain",
         "recommend": "suggest", "recommends": "suggests", "recommended": "suggested", "recommending": "suggesting",
         "recommendation": "suggestion", "recommendations": "suggestions"}


def _swap(m: re.Match) -> str:
    word = m.group(0)
    new = _SWAP[word.lower()]
    return new.capitalize() if word[0].isupper() else new


def scrub(text: str) -> str:
    return _FORBIDDEN.sub(_swap, text)


def _scrub_tree(node, skip=("trade",)):
    """Scrub every hunch-authored string; the reused trade dicts keep the strategy copy as is."""
    if isinstance(node, str):
        return scrub(node)
    if isinstance(node, dict):
        return {k: (v if k in skip else _scrub_tree(v, skip)) for k, v in node.items()}
    if isinstance(node, list):
        return [_scrub_tree(v, skip) for v in node]
    return node


# ----------------------------------------------------------------------------- playbooks

def _p(symbol, name, role, tier, listing, exposure, risk=None):
    d = {"symbol": symbol, "name": name, "role": role, "tier": tier, "listing": listing, "exposure": exposure}
    if risk:
        d["key_risk"] = risk
    return d


HEARING = {
    "key": "hearing",
    "keywords": (r"hearing", r"earbuds?", r"ear ?buds?", r"airpods", r"deaf(ness)?", r"tinnitus", r"audiolog\w*",
                 r"otc hearing aids?", r"loud music", r"headphones?"),
    "restate": {
        "claim": ("Young people damage their hearing with loud music through earbuds, and hearing help grows for "
                  "decades, mostly as consumer earbuds become over-the-counter (OTC) hearing aids."),
        "horizon": "About 10 years",
    },
    "premise": {
        "verdict": "partial",
        "true": [
            "About 24% of 12 to 34 year olds listen to personal audio at unsafe levels (BMJ Global Health "
            "meta-analysis, 2022).",
            "WHO projects about 2.5 billion people will have some hearing loss by 2050.",
            "The FDA created an over-the-counter (OTC) hearing aid category in August 2022.",
            "Apple's AirPods Pro 2 hearing aid feature was FDA-authorized in September 2024.",
        ],
        "added": [
            "\"Everyone will be deaf\": no source says this.",
            "Rising hearing loss in young people: US hearing loss in children and teens showed no overall change "
            "in NHANES surveys from 1988 to 2010.",
            "That young listeners drive the market: most of the growth in hearing help comes from an aging "
            "population.",
        ],
        "evidence": [
            {"source": "BMJ Global Health (meta-analysis)", "date": "2022-11",
             "fact": "About 24% of 12 to 34 year olds use personal audio devices at unsafe listening levels."},
            {"source": "WHO World Report on Hearing", "date": "2021-03",
             "fact": "Projects about 2.5 billion people with some degree of hearing loss by 2050."},
            {"source": "FDA", "date": "2022-08-16",
             "fact": "Final rule creating the over-the-counter (OTC) hearing aid category for adults with "
                     "perceived mild to moderate hearing loss."},
            {"source": "Apple / FDA", "date": "2024-09-12",
             "fact": "FDA authorized the hearing aid feature for AirPods Pro 2, the first OTC hearing aid "
                     "software."},
            {"source": "JAMA Otolaryngology (NHANES 1988-2010)", "date": "2017-09",
             "fact": "Hearing loss in US children and teens showed no overall change from 1988 to 2010."},
        ],
    },
    "players": [
        _p(None, "Sonova", "Largest hearing aid maker (Phonak), listed in Switzerland (SIX)", "obvious", "non_us",
           "pure_play"),
        _p(None, "Demant", "Hearing aid maker (Oticon), listed in Copenhagen", "obvious", "non_us", "pure_play"),
        _p(None, "GN Store Nord", "Hearing aids (ReSound) and headsets, listed in Copenhagen", "obvious", "non_us",
           "meaningful"),
        _p("AAPL", "Apple", "AirPods Pro 2 with an FDA-authorized hearing aid feature", "obvious", "us",
           "small_slice", "AirPods are a small part of Apple's sales, so iPhone results move the stock far more "
                          "than hearing does."),
        _p(None, "Samsung Electronics", "Galaxy Buds with hearing features, listed in Seoul", "obvious", "non_us",
           "small_slice"),
        _p("SONY", "Sony Group", "Earbuds and OTC hearing aids; home listing in Tokyo", "obvious", "non_us",
           "small_slice"),
        _p(None, "Amplifon", "Hearing care clinic chain, listed in Milan", "sleeper", "non_us", "pure_play"),
        _p("COST", "Costco", "Hearing aid centers inside its warehouses", "sleeper", "us", "small_slice",
           "Hearing aids are a tiny share of Costco's sales; membership and grocery trends drive the stock."),
        _p("WMT", "Walmart", "Sells OTC hearing aids in stores and online", "sleeper", "us", "small_slice",
           "OTC hearing aids are a rounding error at Walmart's size; the hunch can be right with no effect here."),
        _p("KN", "Knowles", "Microphones and tiny speakers inside hearing aids and earbuds", "sleeper", "us",
           "meaningful"),
        _p("QCOM", "Qualcomm", "Wireless audio chips inside earbuds", "sleeper", "us", "small_slice",
           "Phone chips are most of Qualcomm's sales; earbud audio is a small slice."),
        _p(None, "EssilorLuxottica", "Hearing glasses (Nuance Audio), listed in Paris", "sleeper", "non_us",
           "small_slice"),
        _p(None, "Cochlear", "Cochlear implants for severe loss, listed in Australia (ASX)", "sleeper", "non_us",
           "meaningful"),
        _p("REGN", "Regeneron", "Gene therapy research for genetic hearing loss", "sleeper", "us", "small_slice"),
        _p(None, "Loop & Etymotic", "Earplugs and hearing protection for loud music", "sleeper", "private",
           "pure_play"),
        _p(None, "Premium clinic-sold hearing aids",
           "The high-priced clinic channel of Sonova, Demant and GN, if earbuds take the mild-loss market",
           "loser", "non_us", "pure_play"),
    ],
    "signals": {
        "confirm": [
            "New NHANES-type data shows more hearing loss in people under 35",
            "OTC and earbud hearing feature use climbs and insurance coverage widens",
            "Incumbents' unit growth beats 4 to 6% a year, or they acquire consumer audio brands",
        ],
        "kill": [
            "Volume limits cut unsafe listening and young adult hearing stays flat",
            "Earbuds take the mild-loss market and hearing aid prices fall faster than units grow",
            "A therapy that repairs hearing works in clinical trials",
        ],
    },
}

AI_POWER = {
    "key": "ai_power",
    "keywords": (r"data ?cent(?:er|re)s?", r"electricity", r"power demand", r"power grid", r"the grid",
                 r"power plants?", r"utilit(?:y|ies)", r"\w*watts?", r"nuclear", r"ai power", r"energy demand",
                 r"power"),
    "restate": {
        "claim": ("AI data centers need far more electricity, so power demand, and the companies that make and "
                  "move that power, grows for years."),
        "horizon": "About 5 to 10 years",
    },
    "premise": {
        "verdict": "partial",
        "true": [
            "US data centers used about 4.4% of US electricity in 2023 and could use 6.7% to 12% by 2028 "
            "(Lawrence Berkeley National Laboratory report for the DOE).",
            "The IEA projects global data center electricity use roughly doubling to about 945 TWh by 2030.",
            "Big tech firms are signing long power deals, including a nuclear plant restart for Microsoft.",
        ],
        "added": [
            "That demand will \"explode\" in a straight line: better chips and cooling, and slow grid hookups, "
            "can flatten the curve.",
            "That every power company gains: regulated utilities earn on approved spending, not on demand alone.",
            "That AI spending stays at today's pace; a pullback would hit chip and network names first.",
        ],
        "evidence": [
            {"source": "Lawrence Berkeley National Laboratory (for DOE)", "date": "2024-12",
             "fact": "US data centers used about 4.4% of US electricity in 2023; 6.7% to 12% projected by 2028."},
            {"source": "IEA, Energy and AI", "date": "2025-04",
             "fact": "Global data center electricity use projected to roughly double to about 945 TWh by 2030."},
            {"source": "Constellation Energy", "date": "2024-09-20",
             "fact": "20-year power deal with Microsoft to restart the Three Mile Island Unit 1 reactor."},
        ],
    },
    "players": [
        _p("NVDA", "NVIDIA", "GPUs that fill AI data centers, the source of the new power demand", "obvious", "us",
           "meaningful", "If AI spending slows, NVIDIA feels it first, before any power company does."),
        _p("VST", "Vistra", "Power producer with nuclear and gas plants selling into the grid", "obvious", "us",
           "pure_play", "Power prices swing with gas prices and weather, not only with data center demand."),
        _p("NEE", "NextEra Energy", "Largest US renewables developer plus a Florida utility", "obvious", "us",
           "meaningful", "Higher interest rates raise the cost of building plants and weigh on utility stocks."),
        _p("CEG", "Constellation Energy", "Largest US nuclear fleet; restarting a reactor for Microsoft", "obvious",
           "us", "pure_play"),
        _p("GEV", "GE Vernova", "Gas turbines and grid equipment", "obvious", "us", "pure_play"),
        _p("ANET", "Arista Networks", "Network switches inside AI data centers", "sleeper", "us", "meaningful",
           "A few cloud giants are most of its sales; one order pause shows up fast."),
        _p("CAT", "Caterpillar", "Backup generators and gas turbines (Solar Turbines) for data centers", "sleeper",
           "us", "meaningful", "Construction and mining cycles still drive most of Caterpillar's results."),
        _p("GE", "GE Aerospace", "Jet engines; its gas turbine arm left with the GE Vernova spin-off in 2024",
           "sleeper", "us", "small_slice", "Almost all of GE Aerospace's sales are jet engines and their service, "
                                          "so power demand barely touches it."),
        _p("ETN", "Eaton", "Switchgear, transformers and backup power for data centers", "sleeper", "us",
           "meaningful"),
        _p("VRT", "Vertiv", "Power and cooling equipment for data centers", "sleeper", "us", "pure_play"),
        _p("PWR", "Quanta Services", "Builds transmission lines and substations", "sleeper", "us", "meaningful"),
        _p(None, "Siemens Energy", "Gas turbines and grid gear, listed in Frankfurt", "sleeper", "non_us",
           "meaningful"),
        _p(None, "Heavy industrial power buyers", "Aluminum smelters and factories that pay more as power prices "
                                                  "rise", "loser", "us", "meaningful"),
    ],
    "signals": {
        "confirm": [
            "Utilities raise load forecasts and sign more large data center power contracts",
            "Grid hookup queues and transformer wait times keep getting longer",
            "Cloud companies raise capital spending plans again next year",
        ],
        "kill": [
            "Cloud companies cut capital spending plans two quarters in a row",
            "New chips or cooling cut power per AI task faster than usage grows",
            "Regulators make data centers pay for grid upgrades and new hookups stall",
        ],
    },
}

PLAYBOOKS = (HEARING, AI_POWER)
_MIN_HITS = 2  # two distinct keyword hits, so one stray word ("power") doesn't trigger a playbook


def _hits(patterns, text: str) -> int:
    t = text.lower()
    return sum(1 for p in patterns if re.search(rf"\b(?:{p})\b", t))


def match_playbook(text: str) -> dict | None:
    best, best_n = None, 0
    for pb in PLAYBOOKS:
        n = _hits(pb["keywords"], text)
        if n > best_n:
            best, best_n = pb, n
    return best if best_n >= _MIN_HITS else None


def closest_domain(text: str) -> str | None:
    best, best_n = None, 0
    for d in DOMAINS:
        n = _hits([re.escape(k) for k in d.keywords], text)
        if n > best_n:
            best, best_n = d.key, n
    return best


# ----------------------------------------------------------------------------- Claude drafter

SYSTEM_PROMPT = """You turn one investing hunch into a research map for an educational paper-trading app. \
Reply with JSON only, matching the schema. Never include prices, scores, position sizes, max loss or any other \
numbers about a stock; the app computes those itself. Never use the words buy, winner, recommend or guaranteed.

- restate: the hunch as one testable claim, plus a time horizon.
- premise: verdict true, partial or false. "true" lists what evidence supports; "added" lists what the hunch \
assumes without proof. Evidence items name a source and a date (YYYY-MM or YYYY-MM-DD) for one fact each.
- players: up to 15 companies or groups. symbol is the US ticker or null; listing is us, non_us or private; \
tier is obvious, sleeper or loser; exposure is pure_play, meaningful or small_slice of the company's business.
- signals: exactly 3 confirm and 3 kill items, each naming something concrete to watch."""

_STR = {"type": "string"}
_STRS = {"type": "array", "items": _STR}
DRAFT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["restate", "premise", "players", "signals"],
    "properties": {
        "restate": {"type": "object", "additionalProperties": False, "required": ["claim", "horizon"],
                    "properties": {"claim": _STR, "horizon": _STR}},
        "premise": {"type": "object", "additionalProperties": False,
                    "required": ["verdict", "true", "added", "evidence"],
                    "properties": {"verdict": {"type": "string", "enum": list(VERDICTS)}, "true": _STRS,
                                   "added": _STRS,
                                   "evidence": {"type": "array", "items": {
                                       "type": "object", "additionalProperties": False,
                                       "required": ["source", "date", "fact"],
                                       "properties": {"source": _STR, "date": _STR, "fact": _STR}}}}},
        "players": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["symbol", "name", "role", "tier", "listing", "exposure"],
            "properties": {"symbol": {"type": ["string", "null"]}, "name": _STR, "role": _STR,
                           "tier": {"type": "string", "enum": list(TIERS)},
                           "listing": {"type": "string", "enum": list(LISTINGS)},
                           "exposure": {"type": "string", "enum": list(WEIGHTS)}}}},
        "signals": {"type": "object", "additionalProperties": False, "required": ["confirm", "kill"],
                    "properties": {"confirm": _STRS, "kill": _STRS}},
    },
}


class ClaudeDrafter:
    """Sends Anthropic exactly one user message: the hunch text. No profile, holdings, capital or resume."""

    def draft(self, text: str) -> str:
        import anthropic

        from .chat import MODEL
        client = anthropic.Anthropic(timeout=CLAUDE_TIMEOUT, max_retries=1)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": DRAFT_SCHEMA}},
        )
        if getattr(resp, "stop_reason", None) == "refusal":
            raise RuntimeError("refused")
        return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")


def claude_client():
    """A drafter when the LLM is available (and never in the static demo, which doesn't call this), else None."""
    from .chat import llm_available
    return ClaudeDrafter() if llm_available() else None


class DraftError(ValueError):
    pass


def _s(v, field: str, allow_empty: bool = False) -> str:
    if not isinstance(v, str) or (not allow_empty and not v.strip()):
        raise DraftError(field)
    return v.strip()[:MAX_STR]


def _slist(v, field: str, strict: bool = False) -> list[str]:
    """Non-empty strings, minus any that make a stock-number claim (strict: no money or percentages either)."""
    if not isinstance(v, list):
        raise DraftError(field)
    return [_s(x, field) for x in v if isinstance(x, str) and x.strip() and not _stock_claim(x, strict)]


def validate_draft(raw: str) -> dict:
    """Claude's JSON, checked field by field. Only the words survive; numbers and unknown keys are dropped."""
    try:
        d = json.loads(raw)
    except (TypeError, ValueError):
        raise DraftError("json")
    if not isinstance(d, dict):
        raise DraftError("root")
    r, pr, pl, sg = d.get("restate"), d.get("premise"), d.get("players"), d.get("signals")
    if not all(isinstance(x, dict) for x in (r, pr, sg)) or not isinstance(pl, list):
        raise DraftError("shape")
    restate = {"claim": _s(r.get("claim"), "claim"), "horizon": _s(r.get("horizon"), "horizon")}
    if _stock_claim(restate["claim"]) or _stock_claim(restate["horizon"]):
        raise DraftError("claim")
    if pr.get("verdict") not in VERDICTS:
        raise DraftError("verdict")
    true, added = _slist(pr.get("true"), "true")[:MAX_LIST], _slist(pr.get("added"), "added")
    added = [x for x in added if x not in true][:MAX_LIST]
    if not isinstance(pr.get("evidence"), list):
        raise DraftError("evidence")
    evidence = []
    for e in pr["evidence"]:
        if isinstance(e, dict) and isinstance(e.get("date"), str) and _DATE.fullmatch(e["date"].strip()) \
                and isinstance(e.get("source"), str) and e["source"].strip() \
                and isinstance(e.get("fact"), str) and e["fact"].strip() \
                and not _stock_claim(e["source"]) and not _stock_claim(e["fact"]):
            if len(evidence) >= MAX_LIST:
                break
            evidence.append({"source": _s(e["source"], "source"), "date": e["date"].strip(),
                             "fact": _s(e["fact"], "fact")})
    players = []
    for p in pl[:MAX_PLAYERS]:
        if not isinstance(p, dict):
            raise DraftError("player")
        if p.get("tier") not in TIERS or p.get("listing") not in LISTINGS or p.get("exposure") not in WEIGHTS:
            raise DraftError("player enums")
        sym = p.get("symbol")
        if sym is not None and not isinstance(sym, str):
            raise DraftError("symbol")
        name, role = _s(p.get("name"), "name"), _s(p.get("role"), "role")
        if _stock_claim(name, strict=True) or _stock_claim(role, strict=True):
            continue  # a player Claude dressed up with prices or scores is left off the map
        players.append({"symbol": sym, "name": name, "role": role,
                        "tier": p["tier"], "listing": p["listing"], "exposure": p["exposure"]})
    confirm = _slist(sg.get("confirm"), "confirm", strict=True)
    kill = _slist(sg.get("kill"), "kill", strict=True)
    kill = [x for x in kill if x not in confirm]
    if len(confirm) < 3 or len(kill) < 3:
        raise DraftError("signals")
    return {"restate": restate,
            "premise": {"verdict": pr["verdict"], "true": true, "added": added, "evidence": evidence,
                        "label": CLAUDE_LABEL},
            "players": players, "signals": {"confirm": confirm[:3], "kill": kill[:3]}}


# ----------------------------------------------------------------------------- enrich, rank, ideas

def _clean_symbol(sym) -> tuple[str | None, bool]:
    """(symbol, malformed). A symbol that isn't ticker-shaped is dropped, never echoed or looked up."""
    if sym is None:
        return None, False
    s = str(sym).strip().upper()
    if not s:
        return None, False
    if not _TICKER.fullmatch(s):
        return None, True
    return s, False


def _unscored_reason(sym: str | None, listing: str, malformed: bool) -> str:
    if malformed:
        return "The ticker didn't look valid, so Charlie left it unscored."
    if listing == "private":
        return "Private company: no stock to price or score."
    if listing == "non_us":
        return "Listed outside the US; Charlie only scores US stocks in its universe."
    if sym is None:
        return "No single US ticker for this one."
    return f"{sym} isn't in Charlie's universe yet, so there's no price or score for it here."


def _enrich(players: list[dict], md, profile) -> tuple[list[dict], dict]:
    chain, analyses, seen = [], {}, set()
    for p in players:
        sym, malformed = _clean_symbol(p.get("symbol"))
        info = lookup(sym) if sym and p["listing"] == "us" else None
        name = p["name"]
        if info:
            sym, name = info.symbol, info.name  # a scored ticker always carries the universe's name (CHL-PS-H2)
        key = sym or p["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        row = {"symbol": sym, "name": name, "role": p["role"], "tier": p["tier"], "listing": p["listing"],
               "exposure": p["exposure"], "exposure_label": EXPOSURE_LABELS[p["exposure"]],
               "scored": False, "unscored_reason": None, "price": None, "score": None}
        if info:
            a = analyses.get(sym) or engine.analyze(md, profile, sym)
            analyses[sym] = a
            row.update(scored=True, price=a["quote"]["price"], score=a["charlie"]["score"])
        else:
            row["unscored_reason"] = _unscored_reason(sym, p["listing"], malformed)
        if p.get("key_risk"):
            row["_key_risk"] = p["key_risk"]
        chain.append(row)
    return chain, analyses


def _rank(chain: list[dict]) -> list[dict]:
    ranked = [{"symbol": p["symbol"], "name": p["name"], "exposure": p["exposure"], "weight": WEIGHTS[p["exposure"]],
               "score": p["score"], "rank_score": round(WEIGHTS[p["exposure"]] * p["score"], 2), "tier": p["tier"]}
              for p in chain if p["scored"]]
    ranked.sort(key=lambda x: (-x["rank_score"], x["symbol"]))
    return ranked


_GENERIC_RISK = {
    "pure_play": "The whole business rides on this hunch; if a kill signal shows up, the reason to look is gone.",
    "meaningful": "Only part of the business rides on this hunch, and the rest can pull the stock the other way.",
    "small_slice": "This is a small slice of a big company, so the hunch can be right and barely move the stock.",
}


def _trade(a: dict, profile, level: int, md) -> dict | None:
    live = a["quote"]["source"] != "mock"
    if md.mode != "mock" and not live:
        return None  # never build a live-looking trade on a demo price
    # A hunch's trade never sells a call except against shares (covered call, collar); the debit spread's
    # short call is hedged, but the hunch keeps to the stricter reading (CHL-HUNCH-9).
    prefs = [s for s in RISK_LEVELS[level]["prefs"] if s not in HUNCH_SKIP]
    if "covered_call" in prefs and profile.holdings.get(a["symbol"], 0) >= 100:
        prefs = ["covered_call"] + [x for x in prefs if x != "covered_call"]
    trade, _ = engine._trade_for(a, profile, level, prefs, live)
    if trade:
        trade["scenarios"] = scenario(trade)
    return trade


def _ideas(chain, ranked, analyses, profile, level, md) -> list[dict]:
    by_sym = {p["symbol"]: p for p in chain if p["scored"]}
    ideas = []
    for x in ranked:
        if len(ideas) >= MAX_IDEAS:
            break
        p = by_sym[x["symbol"]]
        if p["tier"] == "loser":
            continue
        a = analyses[x["symbol"]]
        # The daily ideas' score bar holds here too: below it the lead stays, with no trade (CHL-PS-H3).
        below_bar = p["score"] < engine.MIN_SCORE_BY_LEVEL[level]
        trade = None if below_bar else _trade(a, profile, level, md)
        role = p["role"]
        first = role.split(" ", 1)[0]
        role = role[0].lower() + role[1:] if first[:1].isupper() and first[1:].islower() else role
        why = f"{p['name']} is a {EXPOSURE_LABELS[p['exposure']]} of this hunch: {role}."
        ideas.append({"symbol": p["symbol"], "name": p["name"], "label": "research lead", "why": why,
                      "key_risk": p.get("_key_risk") or _GENERIC_RISK[p["exposure"]],
                      "exposure": p["exposure"], "score": p["score"], "price": p["price"],
                      "trade": trade,
                      "trade_note": None if trade else _TRADE_NOTE_BELOW_BAR.format(
                          bar=engine.MIN_SCORE_BY_LEVEL[level], name=p["name"], score=p["score"]) if below_bar
                      else "No trade fits your capital and risk level for this one.",
                      "disclaimer": NFA})
    return ideas


# ----------------------------------------------------------------------------- the pipeline

def _none_result(text: str, level: int) -> dict:
    dom = closest_domain(text)
    msg = "There's no playbook yet for this hunch"
    msg += (f". The closest area Charlie covers is {DOMAIN_BY_KEY[dom].label}; the Screener can search it."
            if dom else ", and it doesn't match an area Charlie covers.")
    return {
        "restate": {"claim": text.strip()[:MAX_HUNCH_CHARS], "horizon": "Not set"},
        "premise": {"verdict": None, "true": [], "added": [], "evidence": []},
        "chain": [], "unscored": [], "ranked": [], "ranked_label": RANKED_LABEL, "ideas": [],
        "signals": {"confirm": [], "kill": []},
        "source": "none", "message": msg, "closest_domain": dom, "risk_level": level,
        "data_source": None, "disclaimer": NFA,
    }


def run_hunch(text: str, md, profile, level: int | None = None, client=None) -> dict:
    level = max(1, min(5, int(level or profile.risk_level or 2)))
    text = text if isinstance(text, str) else ""
    log.info("hunch: %d characters", len(text))  # the length only, never the text (CHL-HUNCH-14)

    draft, source, pb = None, "none", None
    if client is not None:
        try:
            draft = validate_draft(client.draft(text.strip()))
            source = "claude"
        except Exception as e:  # any failure falls back; the message may echo the hunch, so it isn't logged
            log.info("hunch: Claude draft unusable (%s), falling back", type(e).__name__)
            draft = None
    if draft is None:
        pb = match_playbook(text)
        if pb is None:
            return _scrub_tree(_none_result(text, level))
        source = "playbook"
        draft = {"restate": dict(pb["restate"]),
                 "premise": {k: (list(v) if isinstance(v, list) else v) for k, v in pb["premise"].items()},
                 "players": [dict(p) for p in pb["players"]],
                 "signals": {k: list(v) for k, v in pb["signals"].items()}}

    chain, analyses = _enrich(draft["players"], md, profile)
    ranked = _rank(chain)
    ideas = _ideas(chain, ranked, analyses, profile, level, md)
    for p in chain:
        p.pop("_key_risk", None)
    unscored = [{"symbol": p["symbol"], "name": p["name"], "reason": p["unscored_reason"]}
                for p in chain if not p["scored"]]
    result = {
        "restate": draft["restate"], "premise": draft["premise"], "chain": chain, "unscored": unscored,
        "ranked": ranked, "ranked_label": RANKED_LABEL, "ideas": ideas, "signals": draft["signals"],
        "source": source, "playbook": pb["key"] if pb else None, "message": None, "closest_domain": None,
        "risk_level": level,
        "data_source": engine.data_source(md, list(analyses.values())) if analyses else None,
        "disclaimer": NFA,
    }
    return _scrub_tree(result)
