# Handoff: Charlie

_Read this before starting work on this repo. Update it in the same commit whenever you make progress._
_Studio-wide status (what's done, what's waiting on Chase): `STUDIO-STATUS.md` in holroydchase-afk/pm-tools._

Updated: 2026-10-23

## Current state
- MVP built Oct 22 in the "Charlie" project: resume + interests → circle-of-competence profile → Munger-style score → 1-3 daily stock/options ideas, risk slider (1-5, default Conservative), screener with saved screens, chat (Claude with tools if `ANTHROPIC_API_KEY` is set, rule-based otherwise), paper portfolio, Learn page.
- Python FastAPI + vanilla JS, no build step. `python -m pytest -q`: 35 tests pass.
- Paper trading and education only. No real order execution.
- Research and sources: `docs/RESEARCH.md`.

## Not verified yet
- The live data adapters (Cboe delayed options, SEC EDGAR fundamentals) have only been tested against fixtures. The cloud build machine blocks market-data hosts, so every idea so far has come from demo data. A first run on Chase's laptop is the check (Power Hour item 3, Oct 22).

## Decisions to review (asked Oct 22, Power Hour)
- Build Slate: add Charlie, or keep it as a side project? (Recommended: side. The slate is at 5 of 5.)
- Next feature: earnings-date warnings, or Alpaca paper orders? (Recommended: earnings first.)

## Known limits
- About 95 curated large-cap tickers. Banks and insurers score low on ROIC-style metrics.
- No earnings calendar. Single user, local SQLite, no auth.

## Exact next step
Wait for Chase's laptop run with real data, then fix whatever the live Cboe/SEC responses break.

## Blockers
- None in the repo. The live-data check needs Chase's laptop.
