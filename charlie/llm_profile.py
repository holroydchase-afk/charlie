"""Optional: let Claude read the resume for signals keyword matching misses.

The rules engine catches explicit words ("Kubernetes", "nurse"). Claude also
catches implied knowledge: a hospital billing analyst knows insurers, a Navy
logistics officer knows defense supply chains. Output is constrained to the
app's own domain keys and ticker universe, then merged as extra evidence.
"""

from __future__ import annotations

from pydantic import BaseModel

from .chat import MODEL, llm_available
from .universe import DOMAINS, TICKERS


class DomainSignal(BaseModel):
    domain_key: str
    strength: int  # 1-5
    evidence: str


class TickerSignal(BaseModel):
    symbol: str
    reason: str


class ResumeRead(BaseModel):
    domains: list[DomainSignal]
    tickers: list[TickerSignal]


def enrich(resume_text: str, interests: str) -> tuple[dict, dict] | None:
    if not llm_available() or not (resume_text or interests).strip():
        return None
    import anthropic

    domain_list = "\n".join(f"- {d.key}: {d.label}" for d in DOMAINS)
    ticker_list = ", ".join(f"{t.symbol} ({t.name})" for t in TICKERS)
    prompt = (
        "Read this person's resume and interests. Identify which industries they have real, first-hand knowledge "
        "of (worked in, sold to, operated, or follow closely), including knowledge implied by their roles, not just "
        "keywords. Use only these domain keys:\n" + domain_list +
        "\n\nThen list up to 8 companies from this universe they would understand unusually well, with a short "
        "reason grounded in the resume: " + ticker_list +
        "\n\nStrength: 5 = worked inside the industry for years, 1 = casual interest. Keep evidence under 15 words."
        f"\n\n<resume>\n{resume_text[:20000]}\n</resume>\n<interests>\n{interests[:4000]}\n</interests>"
    )
    try:
        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=MODEL,
            max_tokens=4000,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
            output_format=ResumeRead,
        )
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            return None
        read = resp.parsed_output
    except Exception:
        return None
    valid_domains = {d.key for d in DOMAINS}
    valid_syms = {t.symbol for t in TICKERS}
    domain_boosts = {d.domain_key: (max(1, min(5, d.strength)) * 1.5, f"AI read: {d.evidence}")
                     for d in read.domains if d.domain_key in valid_domains}
    ticker_boosts = {t.symbol.upper(): f"AI read: {t.reason}" for t in read.tickers if t.symbol.upper() in valid_syms}
    return domain_boosts, ticker_boosts
