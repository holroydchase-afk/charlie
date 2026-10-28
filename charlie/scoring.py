"""The "Charlie score": a Munger-style checklist turned into numbers.

Each factor maps to an idea from Charlie Munger (and the people he learned from
or influenced). Scores are 0-100 per factor, combined with weights, then reduced
by red flags found by *inverting* the question: "what would make this a bad
investment?" Every factor returns a plain-English reason so nothing is a black box.

Factors and their roots:
  competence   Circle of competence (Munger/Buffett), "invest in what you know" (Lynch)
  quality      High return on capital; "a great business at a fair price" (Munger)
  moat         Durable advantage, shown by high and *stable* margins (Buffett/Munger)
  balance      Avoid leverage; "smart men go broke three ways: liquor, ladies and leverage"
  value        Margin of safety via owner-earnings yield (Graham, Buffett) and the
               earnings-yield half of Greenblatt's Magic Formula
  red flags    Inversion: "Tell me where I'm going to die so I'll never go there"
"""

from __future__ import annotations

from dataclasses import dataclass

WEIGHTS = {"competence": 0.25, "quality": 0.25, "moat": 0.15, "balance": 0.15, "value": 0.20}
TREASURY_PROXY = 0.042  # rough 10y yield; the hurdle an owner-earnings yield should beat

QUOTES = {
    "competence": "Knowing the edge of your own competence is very important. — Munger",
    "quality": "Over the long term, it's hard for a stock to earn a much better return than the business which underlies it earns. — Munger",
    "moat": "The key is determining the competitive advantage of any given company and, above all, the durability of that advantage. — Buffett",
    "balance": "Smart men go broke three ways: liquor, ladies and leverage. — Munger",
    "value": "A great business at a fair price is superior to a fair business at a great price. — Munger",
    "inversion": "Invert, always invert. — Munger (borrowing from Jacobi)",
}


@dataclass
class Factor:
    key: str
    score: int
    reason: str


def _lerp(x: float | None, lo: float, hi: float) -> float:
    """Map x linearly from [lo, hi] to [0, 100], clamped."""
    if x is None:
        return 50.0
    if hi == lo:
        return 100.0 if x >= hi else 0.0
    return max(0.0, min(100.0, (x - lo) / (hi - lo) * 100))


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def lynch_category(f: dict, domain: str) -> str:
    g = f.get("rev_growth") or 0
    if domain in ("energy", "autos_ev", "industrials_aero", "transport_logistics", "real_estate") and g < 0.15:
        return "Cyclical"
    if (f.get("op_margin") or 0) < 0 and g > 0.15:
        return "Speculative grower (not yet profitable)"
    if g >= 0.15:
        return "Fast grower"
    if g >= 0.05:
        return "Stalwart"
    if g < 0:
        return "Turnaround / shrinking"
    return "Slow grower"


def score(symbol: str, fundamentals: dict, quote: dict, familiarity: int, familiarity_why: list[str],
          iv: float | None = None, domain: str = "") -> dict:
    f = fundamentals
    factors: list[Factor] = []

    # Circle of competence
    why = "; ".join(familiarity_why[:2]) if familiarity_why else "outside the circle your profile shows"
    factors.append(Factor("competence", int(familiarity), why))

    # Quality: ROIC first, then whether reported profits turn into cash (FCF conversion).
    # Margins alone would punish Costco-style low-price, high-turnover models Munger loved.
    roic, gm, fcfm = f.get("roic"), f.get("gross_margin"), f.get("fcf_margin")
    conv = f.get("fcf_conversion")
    q = 0.60 * _lerp(roic, 0.0, 0.25) + 0.25 * _lerp(conv, 0.4, 1.0) + 0.15 * _lerp(gm, 0.15, 0.70)
    conv_txt = f", turns {conv * 100:.0f}% of profit into free cash" if conv is not None else ""
    factors.append(Factor("quality", round(q),
                          f"earns {_pct(roic)} on the money it invests{conv_txt}, keeps {_pct(gm)} of sales after direct costs"))

    # Moat: returns well above cost of capital, sustained with steady margins
    om, sd = f.get("op_margin"), f.get("op_margin_stdev")
    stability = 100 - _lerp(sd, 0.01, 0.10) if sd is not None else 50
    m = 0.25 * _lerp(om, 0.0, 0.35) + 0.40 * stability + 0.35 * _lerp(roic, 0.08, 0.30)
    stab_txt = "very steady" if (sd or 1) < 0.025 else "fairly steady" if (sd or 1) < 0.05 else "volatile"
    factors.append(Factor("moat", round(m), f"keeps {_pct(om)} of sales as operating profit, {stab_txt} year to year"))

    # Balance sheet: leverage and dilution
    de = f.get("debt_to_equity")
    if de is None:
        b, de_txt = 50, "debt level unknown"
    elif de < 0:
        # Negative equity is usually buybacks (MCD, HD) rather than distress; judge by cash flow.
        b = 55 if (fcfm or 0) > 0.1 else 20
        de_txt = "negative book equity (often from buybacks)"
    else:
        b = 100 - _lerp(de, 0.3, 3.0)
        de_txt = f"debt is {de:.1f}× what owners put in"
    dil = f.get("share_change") or 0
    b = b - max(0, dil) * 600 + max(0, -dil) * 300
    dil_txt = f"share count {'shrinking' if dil < -0.005 else 'growing' if dil > 0.005 else 'flat'} ({dil * 100:+.1f}%/yr)"
    factors.append(Factor("balance", round(max(0, min(100, b))), f"{de_txt}; {dil_txt}"))

    # Value / margin of safety: owner-earnings (FCF) yield vs the risk-free hurdle,
    # plus how far price sits below its 52-week high (Mr. Market's mood).
    fy, ey = f.get("fcf_yield"), f.get("earnings_yield")
    v = 0.6 * _lerp(fy, 0.0, TREASURY_PROXY * 2) + 0.25 * _lerp(ey, 0.0, 0.08)
    hi, px = quote.get("high_52w"), quote.get("price")
    off_high = (1 - px / hi) if hi and px else 0
    v += 0.15 * _lerp(off_high, 0.0, 0.30)
    factors.append(Factor("value", round(min(100, v)),
                          f"free cash is {_pct(fy)} of the price a year (Treasuries pay ~{TREASURY_PROXY * 100:.1f}%); "
                          f"{off_high * 100:.0f}% below its 52-week high"))

    composite = sum(WEIGHTS[x.key] * x.score for x in factors)

    # Inversion: what kills this investment?
    flags = []
    if fcfm is not None and fcfm < 0:
        flags.append(("Burns cash (negative free cash flow)", 12))
    if (om or 0) < 0:
        flags.append(("Not yet profitable at the operating level", 10))
    if de is not None and de > 3:
        flags.append((f"Heavy debt load (debt is {de:.1f}× what owners put in)", 8))
    if dil > 0.03:
        flags.append((f"Shareholder dilution of {dil * 100:.0f}%/yr", 8))
    if (f.get("rev_growth") or 0) < -0.03:
        flags.append(("Revenue shrinking", 6))
    if iv and iv > 0.65:
        flags.append((f"Very high implied volatility ({iv * 100:.0f}%) — the market expects big swings", 6))
    if px and px < 5:
        flags.append(("Penny-stock territory", 15))
    if familiarity < 15:
        flags.append(("Outside your circle of competence", 5))
    penalty = sum(p for _, p in flags)
    total = max(0, min(100, round(composite - penalty)))

    grade = "A" if total >= 75 else "B" if total >= 62 else "C" if total >= 50 else "D" if total >= 38 else "F"
    return {
        "symbol": symbol,
        "score": total,
        "grade": grade,
        "factors": [{"key": x.key, "score": x.score, "reason": x.reason, "quote": QUOTES[x.key],
                     "weight": WEIGHTS[x.key]} for x in factors],
        "red_flags": [t for t, _ in flags],
        "lynch_category": lynch_category(f, domain),
        "data_source": f.get("source", "unknown"),
    }
