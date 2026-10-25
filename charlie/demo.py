"""The static demo's entry points: a fictional sample person on mock data, no server.

This is what the browser build (Pyodide) calls. It imports only the engine, the
profile builder and the mock data, so it never pulls in the web server, storage,
chat, document parsers or anything that touches the network.
"""

from __future__ import annotations

import json
from datetime import date

from .data.market import MarketData
from .engine import daily_ideas
from .profile import build_profile
from .strategies import NFA

# Same text as samples/sample_resume.txt (a test keeps them in sync). Alex Rivera is fictional.
SAMPLE_RESUME = """Alex Rivera
Registered Nurse (BSN) | Clinical Informatics

EXPERIENCE
HCA Healthcare — Charge Nurse, Surgical ICU, 2017 - 2022
- Led 12-nurse team; trained staff on Epic Systems EHR and the da Vinci surgical workflow
- Partnered with pharmacy on medication reconciliation; reduced errors 18%

UnitedHealth Group (Optum) — Clinical Informatics Specialist, 2022 - Present
- Build Medicare Advantage care-management dashboards in SQL and Tableau
- Work with medical device vendors (Abbott, Stryker) on patient monitoring integrations

EDUCATION
BSN, University of Texas, 2016

INTERESTS: biotech news, GLP-1 drugs, clinical trial readouts, running, Lululemon
"""
SAMPLE_CAPITAL = 25000
SAMPLE_LEVEL = 2


def sample_profile(today: date, risk_level: int = SAMPLE_LEVEL):
    return build_profile(SAMPLE_RESUME, capital=SAMPLE_CAPITAL, risk_level=risk_level, name="Alex Rivera (sample)",
                         this_year=today.year)


def sample_ideas(today: date, level: int = SAMPLE_LEVEL, count: int = 3) -> dict:
    md = MarketData(mode="mock", today=today)
    return daily_ideas(md, sample_profile(today, level), level, count)


def summarize(result: dict) -> dict:
    """The parts of a day's ideas that must match between pytest and the browser."""
    return {
        "date": result["date"],
        "risk_level": result["risk_level"],
        "data_source": result["data_source"],
        "disclaimer": NFA,
        "ideas": [{
            "symbol": i["trade"]["symbol"],
            "strategy": i["trade"]["strategy"],
            "score": i["analysis"]["charlie"]["score"],
            "legs": [[leg["action"], leg["instrument"], leg.get("strike"), leg.get("expiry"), leg["qty"]]
                     for leg in i["trade"]["legs"]],
            "max_loss": i["trade"]["max_loss"],
            "breakeven": i["trade"]["breakeven"],
            "pop": i["trade"]["pop"],
        } for i in result["ideas"]],
    }


def ideas_json(day_iso: str, level: int = SAMPLE_LEVEL, count: int = 3) -> str:
    """JSON for the page: the full ideas payload plus the comparable summary."""
    result = sample_ideas(date.fromisoformat(day_iso), level, count)
    return json.dumps({"result": result, "summary": summarize(result)})
