# Agent notes: Charlie

Re-apply after every studio-agents `scripts/sync.sh`; never hand-edit `.claude/agents/`.

The studio agents in `.claude/agents/` are generic and get overwritten on every sync. Charlie-specific guidance for them lives here. Each agent reads its section along with `CLAUDE.md`, whose hard rules win.

## qa-tdd

## Charlie addendum: risk math checklist
Charlie-only section (Chase, 2026-10-28). It used to sit in `.claude/agents/qa-tdd.md` until `scripts/sync.sh` overwrote it, so it now lives here in `docs/eng/AGENT-NOTES.md`. Read it with the qa-tdd agent file.

Any change that touches a number a trader acts on (`charlie/options_math.py`, `charlie/strategies.py`, sizing in `charlie/engine.py`, `scenario()`, the browser engine) gets these tests before it's built, in `tests/test_risk_math.py`:
- **Golden values.** Each calc is checked against an answer worked out by hand or from a textbook (Hull, a published Black-Scholes table), with the working in a comment, never against the code's own output. Covers price, delta, gamma, theta, vega, probability of profit, expected move, max loss, max gain, breakeven, return on risk and contract count.
- **Identities.** Put-call parity, delta call minus delta put equals 1, and the min of `scenario()` P&L equals minus max loss where the strategy has a defined loss.
- **Sizing.** For defined-risk option strategies, max loss in dollars never exceeds capital times the risk slider's `max_risk_pct` (shares, cash-secured puts and covered calls size by collateral today; see HANDOFF "Decisions to review"); contracts round down, never up; a budget too small for one contract yields no trade, not a 1-lot. Familiarity never changes size.
- **Edges.** Zero or negative spot, strike, IV or capital; expiry day (t = 0) and past expiry; deep ITM and OTM; missing, zero or crossed bid/ask; IV missing from the chain. Expect a clear `None` or no trade, never NaN, inf, a negative max loss or a crash.
- **Units.** Per-share vs per-contract (x100), IV as a decimal not a percent, days vs years, theta per day, vega per vol point.
- **Both engines.** The Pyodide demo runs the same Python, so one golden suite covers both; if any risk math is ever ported to JS, the same golden table runs against it.

### Also for qa-tdd
- Unit suite: `CHARLIE_DATA=mock CHARLIE_LLM=off python -m pytest -q`. Browser suite: `CHARLIE_E2E=1` on a built demo (`tests/e2e/`).
- A test gated on `CHARLIE_E2E` outside `tests/e2e` must be named in CI's e2e job, or the CHL-R3 guard fails (`docs/eng/LESSONS.md`).

## engineer
- One engine. `charlie/handlers.py` serves both the FastAPI app and the Pyodide demo (`Api.route`). Don't fork scoring or strategy logic into JS (CLAUDE.md).
- The prebuilt demo answers in `prebuilt.json` must match the engine; a test checks for drift, so rebuild rather than hand-edit.

## ux-reviewer
- "Not financial advice. Paper trading only." on every trade surface, and max loss in dollars, breakeven and an exit plan on every trade (CLAUDE.md hard rules). A finding that hides any of them is P0.
- Demo copy says sample data plainly; the demo has one notice, the studio demo bar (CHL-DEMO-R1).

## privacy-security
- Resumes are personal data (CLAUDE.md). Check that none reach logs, tests, fixtures, git, an API response in full, or Anthropic without the opt-in.
- The public demo makes no network calls beyond its own site (`tools/check_site.py --no-cdn`). Any new host is a finding.
- Commit author emails aren't covered by the CI privacy check (CHL-PS16 in `docs/eng/LESSONS.md`).

## architect
- Any change to `ci.yml` or `pages.yml` keeps the PS17 deploy guard (push event from this repository) and the Playwright and ubuntu-latest guard (`docs/eng/LESSONS.md`).
