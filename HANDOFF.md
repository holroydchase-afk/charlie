# Handoff: Charlie

_Read this before starting work on this repo. Update it in the same commit whenever you make progress. It is the single source of truth for where things stand._
_Studio-wide status (what's done, what's waiting on Chase): [`STUDIO-STATUS.md`](https://github.com/holroydchase-afk/pm-tools/blob/main/STUDIO-STATUS.md) in holroydchase-afk/pm-tools._

Updated: 2026-10-24 (night shift, M1.3)

## Done
- MVP (Oct 22): resume + interests → circle-of-competence profile → Munger-style score → 1-3 daily stock/options ideas, risk slider (1-5, default Conservative), screener with saved screens, chat (Claude with tools if `ANTHROPIC_API_KEY` is set, rule-based otherwise), paper portfolio, Learn page. Python FastAPI + vanilla JS, no build step. Paper trading and education only.
- M0.1 studio setup (PR "M0.1: studio setup", branch `claude/project-thread-dlm2ig`): CLAUDE.md with hard rules and Studio agents, PLAN.md (M0 to M1, Pyodide static demo), `.claude/agents/` (staff-pm, qa-tdd, engineer, ux-reviewer, privacy-security, positioning), `.claude/settings.json`, `handoff-check.yml`, `ci.yml` (pytest + privacy check), dependabot (pip + Actions), MIT LICENSE, README CI badge. privacy-security review findings became PLAN M0.3.

- M0.2 restored `charlie/data/` (branch `claude/project-thread-74d6f6`, stacked on M0.1): `market.py` facade (auto / mock / live, per-call fallback, on-disk cache, 5-minute offline backoff), `cboe.py` and `sec.py` adapters, `mock.py` deterministic demo data (mean-reverting prices keyed by date, Black-Scholes chains on a put-skew smile, weeklies + monthlies + January LEAPS). `.gitignore` now ignores only the root `/data/`. `CHARLIE_SEC_UA` comes only from env; live SEC calls refuse while it's unset or still the `you@example.com` placeholder. 42 tests pass 3x (35 original + 7 new in `tests/test_data.py`).

- M0.3 privacy fixes (same branch, PR #2): "Not financial advice. Paper trading only." is now added by code to every chat reply (Claude, rule-based, refusal and fallback), to every trade dict (`disclaimer`), and in the UI on idea cards, trade blocks, chat trade cards and the ticker drawer. The Claude resume read is opt-in (unchecked, `Form(False)`), and the label says the text goes to Anthropic's API. `GET /api/profile` returns `resume_chars`, not the text. New `DELETE /api/profile` plus a "Delete my data" button. A same-origin middleware refuses cross-site POST and DELETE requests (403). Upload errors return generic text. README says to bind 127.0.0.1. 58 tests pass 3x.
- Night UX sweep (Playwright, 390x844 and 1280x800, light and dark, every tab plus the drawer): no console errors, no horizontal overflow. Fixed the raw `*finding*` markdown in the profile caution.

- M1.1 Pyodide spike (same branch, PR #2):
  - `charlie/demo.py` is the static demo's entry point (fictional sample person, mock data, no server, storage, chat or network imports).
  - The engine runs serially when there are no threads.
  - `spike/` + `tools/build_spike.py` build a test page that runs the real engine in Pyodide 0.28.3. Its ideas match `tests/golden/sample_ideas.json` exactly in Chromium.
  - Mock chains are about 2x faster (narrower strike range, one Black-Scholes pass per strike).
  - Timings and options are in `docs/decisions/engine-in-browser.md`: laptop about 2.5 s to ideas, phone at 4x CPU about 10 to 12 s plus about 5.5 MB to download on a first visit.
  - 65 tests pass 3x.

- M1.2 browser adapter (same branch, PR #2), built on the recommended Pyodide path while the engine call waits:
  - `charlie/handlers.py` holds every endpoint's logic. `server.py` is now thin FastAPI wrappers (uploads, Claude resume reading and the Origin check stay server-only), and the browser calls the same code through `Api.route()`.
  - `charlie/browser_store.py`: `BrowserStore` has Store's interface on `localStorage` (keys `charlie:*`, keeps only the latest day of ideas, reads corrupt entries as empty).
  - `charlie/browser.py` is the Pyodide entry point: mock data, rule-based chat, and none of anthropic, requests, sqlite3, fastapi or the Cboe/SEC adapters get imported (those and sqlite3 now load lazily).
  - `web/static.js` loads Pyodide plus `charlie.zip` and exposes `window.charlieStatic`; `api()` in `web/app.js` uses it when present, so one UI file serves both modes. Upload and the Claude opt-in are hidden in the demo.
  - `tools/build_demo.py` writes a minimal `site/` (gitignored); M1.3 adds the prebuilt first screen.
  - Checked in Chromium on the built site (phone viewport, local Pyodide): ideas, disclaimers, paper trade, chat, paste-a-resume, and reload persistence all work, with no console errors and no requests leaving the site. Pyodide from the CDN is untested here (jsDelivr is blocked in this sandbox).
  - 86 tests pass 3x (21 new in `tests/test_browser.py`, including the router matching the FastAPI responses and BrowserStore parity with Store).
- M1.3 instant first screen (same branch, PR #2):
  - `charlie.browser.prebuild()` runs the same handlers at build time and `tools/build_demo.py` writes `site/prebuilt.json`: the sample person's profile, ideas and each idea's ticker drawer for all 5 risk levels, plus meta, status, screens and paper (341 KB, 52 KB gzipped).
  - Until the visitor saves a profile, the demo shows the fictional sample person (Alex Rivera). Moving the slider in that state stores only `charlie:kv:sample_risk`, so the prebuilt answers stay valid.
  - `web/static.js` serves prebuilt answers instantly while nothing is changed (no profile, intake, positions or screens stored) and starts Pyodide after the first paint. Anything else waits for the engine behind a "Starting Charlie's engine" pill, and if it fails to load there's a toast and the next click retries.
  - A test checks every prebuilt answer against what the engine returns, so the two can't drift.
  - Chromium, built site, local Pyodide: Today shows in 0.1 s on a laptop, 0.8 s at 4x CPU on 4G and 1.6 s at 6x CPU on slow 4G. The slider stays instant on phones. The engine is up at about 20 s and 39 s on those phones, and chat waits behind the pill until then. There were no console errors and no requests left the site.
  - 96 tests pass 3x (10 new in `tests/test_first_screen.py`).
- Phone tab bar (M1.7 P2): the right edge fades so the cut-off tab reads as "more", the scrollbar is hidden, and the active tab scrolls into view. Checked with Playwright at 390 and 1280, light and dark, with no errors or overflow. The footer "overlap" was a false alarm: the page already pads 72px below content.

## In progress
- Engine call still open (below). M1.3's prebuilt first screen covers the phone load time PLAN worried about (Today in under 2 s on throttled phones), which supports staying on Pyodide. M1.2 is built on the recommended Pyodide path; if Chase picks the JS port instead, `handlers.py` and `BrowserStore` still serve the local app and only `static.js` changes.

## Exact next step
M1.4 demo guardrails: a sample-data banner ("everything stays in this browser"), a header link back to chaseholroyd.com, a "Reset demo" button that clears `charlie:*` keys, a CI check for key patterns and non-Pyodide hosts in `site/`, and Playwright tests for the disclaimer and back link. Needs Chase: the engine call (Decisions to review) and merging #1, then #2.

## Decisions to review
- M1.3: the demo's data is pinned to the build date (status, ideas and the drawer all say that date), because the prebuilt answers are made at build time. M1.6 should rebuild on a schedule if a fresh date matters. Also: before saving anything, the demo visitor is the fictional sample person, not a blank default.
- M1.2: the demo's daily-ideas cache keeps only the latest day in `localStorage`, and the demo hides resume upload and the Claude opt-in (PLAN: paste and the sample resume are enough). `chat()` gained `allow_llm`, which static mode sets to False.
- **Engine for the static demo (needs Chase's call).** M1.1 tripped PLAN's stop condition: about 10 to 12 s to interactive on a 4x-throttled phone, most of it Pyodide's own start-up. Recommended: stay on Pyodide and have M1.3 prebuild ideas for all 5 risk levels plus each idea's ticker drawer, so the recruiter path is instant and only "paste your own resume" and the screener wait on Python. Alternative: port scoring, strategies and mock data to JS (instant, but two engines). Details: `docs/decisions/engine-in-browser.md`.
- Mock option chains changed in M1.1 (strikes ±22% short-dated and ±45% LEAPS, weeklies 3 to 8 weeks out). Tests and the golden ideas are unchanged.
- M0.2 rebuilt `charlie/data/` from the tests and callers because the original never reached git or the project zip. The mock numbers differ from the Oct 22 screenshots (same universe fundamentals, new price paths). Undo: none needed; it's demo data.
- The Origin check allows requests with no Origin header (curl, scripts) and any localhost origin. That's enough for the single-user local app, but not for any hosted backend (CLAUDE.md already forbids one).
- Static demo engine: Pyodide running the existing Python, not a JS port (one source of truth, reuse the tests). Switch to a JS port of scoring and strategies if M1.1 shows over 10 seconds to usable on a throttled phone. Undo: edit PLAN.md M1.1.
- Repo stays private until M1.5 (privacy-security pre-public review), then Chase decides to make it public for Pages.
- Build Slate: add Charlie, or keep it as a side project? (Asked Oct 22. Product Studio has since added Charlie to STUDIO-STATUS and Build Slate.)
- Next feature after M1: earnings-date warnings, or Alpaca paper orders? (Recommended: earnings first.)

## Known limits
- About 95 curated large-cap tickers. Banks and insurers score low on ROIC-style metrics.
- No earnings calendar. Single user, local SQLite, no auth (bind 127.0.0.1).
- Live data adapters (Cboe delayed options, SEC EDGAR) only tested against fixtures; the cloud blocks market-data hosts. The M0.2 rewrite of both adapters is unverified against the real endpoints.
- Screening all ~95 tickers in mock mode took about 6 s before M1.1 sped up chain generation by about 2x. Still the slowest path in the browser; the screener needs a loading state there.

## Blockers
- None for Chase tonight. Live-data check needs Chase's laptop (later, PLAN M2+).
- Before going public (M1.5): the two existing commits have Chase's personal email as author. Rewriting history needs Chase's go; future commits use a noreply author.

## Portfolio / public presence
- Portfolio page: not yet (added after the demo passes the recruiter-ready bar, via an INTAKE to Product Studio).
- Live demo: not yet. Planned at chaseholroyd.com/charlie/, a static Pyodide build deployed by `pages.yml` from `main` after CI passes (PLAN M1.6, needs the repo public).
- Demo data: the fictional sample resume in `samples/` and the built-in mock market data, saved only in the visitor's browser.
- 2026-10-24: the demo build (`tools/build_demo.py`, not deployed) now opens on the sample person's prebuilt ideas in under 2 s on a throttled phone, with data pinned to the build date.
- Studio status: [STUDIO-STATUS.md](https://github.com/holroydchase-afk/pm-tools/blob/main/STUDIO-STATUS.md).
- 2026-10-23: studio onboarding (M0.1). No public changes yet.
- 2026-10-23: night shift M0.2 + M0.3 (PR #2). No public changes; the demo isn't live yet.
- 2026-10-23: M1.1 Pyodide spike page (`spike/`, test page only, not deployed). No public changes.
