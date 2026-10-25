"""SEC EDGAR XBRL company facts: free and keyless, but the SEC requires a User-Agent that
identifies you ("AppName you@example.com") and fewer than 10 requests a second.

The identity comes only from the CHARLIE_SEC_UA environment variable. While it's unset
(or still the placeholder) live calls refuse to run, so nobody's address ends up in code.
"""

from __future__ import annotations

import os
import statistics
import time
from datetime import date

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
PLACEHOLDER_UA = "Charlie you@example.com"
TAX_RATE = 0.21
TIMEOUT = 15
_last_call = [0.0]


class SecConfigError(RuntimeError):
    pass


def user_agent() -> str:
    ua = os.environ.get("CHARLIE_SEC_UA", "").strip()
    if not ua or ua == PLACEHOLDER_UA or "@" not in ua:
        raise SecConfigError("Set CHARLIE_SEC_UA to 'AppName your-email' to use live SEC fundamentals.")
    return ua


def _get_json(url: str) -> dict:
    import requests

    wait = 0.15 - (time.monotonic() - _last_call[0])  # stay well under 10 requests a second
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": user_agent(), "Accept-Encoding": "gzip"})
    r.raise_for_status()
    return r.json()


def fetch_cik_map() -> dict[str, int]:
    data = _get_json(TICKERS_URL)
    return {row["ticker"].upper().replace("-", "."): int(row["cik_str"]) for row in data.values()}


def fetch_facts(cik: int) -> dict:
    return _get_json(FACTS_URL.format(cik=cik))


# ------------------------------------------------------------------ metrics

FLOW = {
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"),
    "gross_profit": ("GrossProfit",),
    "op_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "ocf": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
}
INSTANT = {
    "equity": ("StockholdersEquity",),
    "debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
}


def _annual(facts: dict, names: tuple[str, ...], flow: bool) -> dict[int, float]:
    """Fiscal-year values from 10-K filings, keyed by the year the period ends."""
    gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    for name in names:
        units = (gaap.get(name) or {}).get("units") or {}
        rows = next(iter(units.values()), None)
        if not rows:
            continue
        out: dict[int, tuple[str, float]] = {}
        for r in rows:
            if r.get("form") != "10-K" or r.get("fp") != "FY" or "end" not in r:
                continue
            if flow and "start" in r:
                days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
                if not 350 <= days <= 380:
                    continue
            year = int(r["end"][:4])
            filed = r.get("filed", "")
            if year not in out or filed >= out[year][0]:
                out[year] = (filed, float(r["val"]))
        if out:
            return {y: v for y, (_, v) in out.items()}
    return {}


def _cagr(series: dict[int, float], years: int = 4) -> float | None:
    ys = sorted(series)
    if len(ys) < 2:
        return None
    last = ys[-1]
    first = max(ys[0], last - years)
    a, b = series.get(first), series[last]
    if not a or a <= 0 or b <= 0:
        return None
    return (b / a) ** (1 / (last - first)) - 1


def _div(a, b):
    return a / b if a is not None and b not in (None, 0) else None


def compute_metrics(facts: dict, price: float | None) -> dict:
    s = {k: _annual(facts, v, True) for k, v in FLOW.items()}
    s.update({k: _annual(facts, v, False) for k, v in INSTANT.items()})
    if not s["revenue"]:
        raise ValueError("no annual revenue in SEC facts")
    fy = max(s["revenue"])
    at = {k: v.get(fy) for k, v in s.items()}
    fcf = at["ocf"] - (at["capex"] or 0) if at["ocf"] is not None else None
    invested = (at["equity"] or 0) + (at["debt"] or 0) - (at["cash"] or 0)
    margins = [s["op_income"][y] / s["revenue"][y] for y in s["revenue"] if s["op_income"].get(y) is not None]
    mcap = price * at["shares"] if price and at["shares"] else None
    return {
        "fiscal_year": fy,
        "roic": _div(at["op_income"] * (1 - TAX_RATE), invested) if at["op_income"] is not None and invested > 0 else None,
        "gross_margin": _div(at["gross_profit"], at["revenue"]),
        "op_margin": _div(at["op_income"], at["revenue"]),
        "op_margin_stdev": statistics.pstdev(margins) if len(margins) >= 3 else None,
        "net_margin": _div(at["net_income"], at["revenue"]),
        "fcf_margin": _div(fcf, at["revenue"]),
        "fcf_conversion": _div(fcf, at["net_income"]) if (at["net_income"] or 0) > 0 else None,
        "debt_to_equity": _div(at["debt"] or 0, at["equity"]),
        "rev_growth": _cagr(s["revenue"]),
        "share_change": _cagr(s["shares"]),
        "earnings_yield": _div(at["net_income"], mcap),
        "fcf_yield": _div(fcf, mcap),
        "pe": _div(mcap, at["net_income"]) if (at["net_income"] or 0) > 0 else None,
        "source": "sec",
    }
