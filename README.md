# Charlie

[![CI](https://github.com/holroydchase-afk/charlie/actions/workflows/ci.yml/badge.svg)](https://github.com/holroydchase-afk/charlie/actions/workflows/ci.yml)

**Invest in what you know, with training wheels.** Charlie reads your resume and interests, maps your *circle of competence* to companies, scores them with a Charlie Munger-style checklist, and turns the best 1-3 into concrete stock or options ideas each day. A risk slider decides how adventurous the trades are. It defaults to conservative (covered calls and cash-secured puts).

> Education and paper trading only. Charlie never places real orders and is not financial advice.

## Quick start

```bash
pip install -r requirements.txt
python -m uvicorn charlie.server:app --host 127.0.0.1 --port 8000
# open http://localhost:8000
```

Keep it on `127.0.0.1`. The local app is single-user with no login, so don't expose it on your network.

Then go to **Profile**, upload a resume (PDF/DOCX/TXT) or paste one, add what you read about and the brands you use, and hit **Build my profile**. **Today** now shows your ideas. Your resume stays in the local `data/` folder. The app never sends it back out, and **Delete my data** on Profile removes it.

Optional settings (environment variables):

| Variable | Default | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | Turns on Claude for chat (with tools). It also allows a deeper resume read, but only if you tick the opt-in box on Profile, since that sends the text to Anthropic's API. Without a key, chat runs on simple rules. |
| `CHARLIE_DATA` | `auto` | `auto` tries free live data and falls back to demo data; `mock` is offline only; `live` errors instead of falling back. |
| `CHARLIE_SEC_UA` | placeholder | SEC asks for `"AppName you@example.com"` (use your own contact; never commit it) as the User-Agent. Set this before using live fundamentals. |
| `CHARLIE_MODEL` | `claude-opus-5-5` | Claude model for chat. |
| `CHARLIE_DB` | `data/charlie.db` | SQLite file for profile, saved screens, and paper trades. |

The header badge shows **Demo data** whenever numbers are simulated.

## What's in the MVP

- **Profile:** resume + interests + brands + holdings → ranked sectors with the evidence behind each ("your resume mentions Da Vinci (Intuitive Surgical)"), and the companies you're positioned to understand.
- **Today:** 1-3 ideas, one per sector. Each has a Charlie score with reasons, why it's in your circle, the exact trade (legs, contracts, credit or debit), max loss in dollars, breakeven, chance of profit, a payoff chart, an exit plan, "what could go wrong," and a broker-ready order ticket. Ideas stay fixed for the day.
- **Risk slider (1-5):** shares only → covered calls / cash-secured puts → credit spreads and collars → debit spreads and LEAPS → short-dated long calls. Position sizing tightens as risk goes up. Uncovered calls and 0DTE are never offered.
- **Screener:** your own criteria (sectors, tickers, min score, max price, IV range, chance of profit, capital, annualized return, days to expiry, delta, skip red flags). Save screens and rerun them.
- **Chat:** ask about ideas, a company, a strategy, or your portfolio. Trades in answers come with **Paper trade** buttons.
- **Paper portfolio:** one click opens a paper position; it's marked to current prices with P&L and % of max profit.
- **Learn:** how the scoring works, the slider levels, each strategy, and a glossary.

## How ideas are picked

See [docs/RESEARCH.md](docs/RESEARCH.md) for sources. In short:

1. Start with the tickers in your circle of competence.
2. Score each on competence, quality (ROIC, cash conversion), moat (stable margins), balance sheet (debt, dilution), and value (free-cash-flow yield vs Treasuries). Subtract points for red flags found by inversion.
3. Drop anything below the bar for your risk level; keep one per sector.
4. Express each idea with the safest structure your slider and capital allow; fall back to shares if no option trade fits.

Familiarity raises a company's rank but never its position size, because research shows people underrate the risk of companies they feel they understand.

## Project layout

```
charlie/
  universe.py      sectors, keywords, ~95 curated tickers (+ illustrative demo fundamentals)
  profile.py       resume/interest parsing → circle-of-competence profile
  llm_profile.py   optional Claude read of the resume (structured output)
  scoring.py       Munger-style Charlie score
  strategies.py    risk slider, strategy builders, payoff scenarios, explainers
  engine.py        daily ideas, screener, ticker analysis
  chat.py          Claude tool-use chat + offline fallback
  portfolio.py     paper position marking
  store.py         SQLite persistence
  server.py        FastAPI API + static web app
  data/            market facade, Cboe and SEC adapters, mock generator
web/               single-page UI (no build step)
tests/             pytest suite (35 tests)
```

Run tests with `python -m pytest -q`.

## Known limits (MVP)

- Live data adapters (Cboe delayed options, SEC EDGAR) are built and unit-tested against their documented formats, but couldn't be exercised against the real endpoints from the build machine. Expect a small fix or two on first live run.
- The ticker universe is a curated ~95 large caps across 17 sectors. Companies outside it (e.g. a small-cap employer) are recognized only through their sector.
- Banks and insurers don't fit ROIC-style metrics well, so Berkshire, JPMorgan, and others score lower than they deserve.
- No earnings-date awareness yet; check before selling options through earnings.
- Single user, local SQLite. No auth.

## Next steps worth considering

1. Alpaca paper-trading connection, so "Paper trade this" places a real paper order (Alpaca supports options levels 1-3 in paper).
2. Earnings calendar and ex-dividend checks before suggesting short options.
3. Daily email or push digest of the day's ideas.
4. Track idea outcomes over time to see whether the scoring actually works.

## Plan and status

Milestones are in [PLAN.md](PLAN.md) and where things stand is in [HANDOFF.md](HANDOFF.md). Next up (M1) is a static, no-login demo on sample data at chaseholroyd.com/charlie/.

## License

[MIT](LICENSE)
