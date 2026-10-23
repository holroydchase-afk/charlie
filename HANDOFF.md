# Handoff: Charlie

_Read this before starting work on this repo. Update it in the same commit whenever you make progress. It is the single source of truth for where things stand._
_Studio-wide status (what's done, what's waiting on Chase): [`STUDIO-STATUS.md`](https://github.com/holroydchase-afk/pm-tools/blob/main/STUDIO-STATUS.md) in holroydchase-afk/pm-tools._

Updated: 2026-10-23 (night shift, M0.2)

## Done
- MVP (Oct 22): resume + interests → circle-of-competence profile → Munger-style score → 1-3 daily stock/options ideas, risk slider (1-5, default Conservative), screener with saved screens, chat (Claude with tools if `ANTHROPIC_API_KEY` is set, rule-based otherwise), paper portfolio, Learn page. Python FastAPI + vanilla JS, no build step. Paper trading and education only.
- M0.1 studio setup (PR "M0.1: studio setup", branch `claude/project-thread-dlm2ig`): CLAUDE.md with hard rules and Studio agents, PLAN.md (M0 to M1, Pyodide static demo), `.claude/agents/` (staff-pm, qa-tdd, engineer, ux-reviewer, privacy-security, positioning), `.claude/settings.json`, `handoff-check.yml`, `ci.yml` (pytest + privacy check), dependabot (pip + Actions), MIT LICENSE, README CI badge. privacy-security review findings became PLAN M0.3.

- M0.2 restored `charlie/data/` (branch `claude/project-thread-74d6f6`, stacked on M0.1): `market.py` facade (auto / mock / live, per-call fallback, on-disk cache, 5-minute offline backoff), `cboe.py` and `sec.py` adapters, `mock.py` deterministic demo data (mean-reverting prices keyed by date, Black-Scholes chains on a put-skew smile, weeklies + monthlies + January LEAPS). `.gitignore` now ignores only the root `/data/`. `CHARLIE_SEC_UA` comes only from env; live SEC calls refuse while it's unset or still the `you@example.com` placeholder. 42 tests pass 3x (35 original + 7 new in `tests/test_data.py`).

## In progress
- M0.3 privacy fixes (same branch, next commits).

## Exact next step
M0.3 (disclaimers in code on every idea and chat reply, resume AI opt-in), then M1.1 Pyodide spike (see PLAN.md).

## Decisions to review
- M0.2 rebuilt `charlie/data/` from the tests and callers because the original never reached git or the project zip. The mock numbers differ from the Oct 22 screenshots (same universe fundamentals, new price paths). Undo: none needed; it's demo data.
- Static demo engine: Pyodide running the existing Python, not a JS port (one source of truth, reuse the tests). Switch to a JS port of scoring and strategies if M1.1 shows over 10 seconds to usable on a throttled phone. Undo: edit PLAN.md M1.1.
- Repo stays private until M1.5 (privacy-security pre-public review), then Chase decides to make it public for Pages.
- Build Slate: add Charlie, or keep it as a side project? (Asked Oct 22. Product Studio has since added Charlie to STUDIO-STATUS and Build Slate.)
- Next feature after M1: earnings-date warnings, or Alpaca paper orders? (Recommended: earnings first.)

## Known limits
- About 95 curated large-cap tickers. Banks and insurers score low on ROIC-style metrics.
- No earnings calendar. Single user, local SQLite, no auth (bind 127.0.0.1).
- Live data adapters (Cboe delayed options, SEC EDGAR) only tested against fixtures; the cloud blocks market-data hosts. The M0.2 rewrite of both adapters is unverified against the real endpoints.
- Screening all ~95 tickers in mock mode takes about 6 seconds (chain generation in pure Python). Fine locally; worth caching or trimming strikes before the Pyodide demo (M1.1).

## Blockers
- None for Chase tonight. Live-data check needs Chase's laptop (later, PLAN M2+).
- Before going public (M1.5): the two existing commits have Chase's personal email as author. Rewriting history needs Chase's go; future commits use a noreply author.

## Portfolio / public presence
- Portfolio page: not yet (added after the demo passes the recruiter-ready bar, via an INTAKE to Product Studio).
- Live demo: not yet. Planned at chaseholroyd.com/charlie/, a static Pyodide build deployed by `pages.yml` from `main` after CI passes (PLAN M1.6, needs the repo public).
- Demo data: the fictional sample resume in `samples/` and the built-in mock market data, saved only in the visitor's browser.
- Studio status: [STUDIO-STATUS.md](https://github.com/holroydchase-afk/pm-tools/blob/main/STUDIO-STATUS.md).
- 2026-10-23: studio onboarding (M0.1). No public changes yet.
