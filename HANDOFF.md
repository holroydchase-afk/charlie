# Handoff: Charlie

_Read this before starting work on this repo. Update it in the same commit whenever you make progress. It is the single source of truth for where things stand._
_Studio-wide status (what's done, what's waiting on Chase): [`STUDIO-STATUS.md`](https://github.com/holroydchase-afk/pm-tools/blob/main/STUDIO-STATUS.md) in holroydchase-afk/pm-tools._

Updated: 2026-10-24 (Polish Freeze; M2 parked)

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
- M1.4 demo guardrails (same branch, PR #2):
  - In the demo, a banner says the resume and market data are made up and anything entered stays in this browser. It links back to chaseholroyd.com and has a "Reset demo" button that clears the `charlie:*` keys. The banner, link and button are `.static-only`, so the local app doesn't show them.
  - The chat panel shows "Not financial advice. Paper trading only." in its markup, on top of every reply.
  - The Today nudge in the demo now says the ideas are for Alex Rivera, a fictional sample person. Before, it wrongly said "generic starter circle".
  - `tools/check_site.py` fails on key patterns or any URL host other than the Pyodide CDN, chaseholroyd.com and the SVG namespace. It also scans inside `charlie.zip`. CI builds the site and runs it.
  - `tests/e2e/` holds Playwright (Python) tests on the built demo: the disclaimer on every idea card, the chat panel and the reply; the banner, back link and sample nudge; and the reset. They run with `CHARLIE_E2E=1` in a new CI `e2e` job, which loads Pyodide from the CDN. They passed 3x here with Pyodide served locally. The CI job itself hasn't run yet.
  - README has a "Static demo" section. Unit tests: 101 pass 3x, and the e2e module is skipped without `CHARLIE_E2E`.
  - The CI `e2e` job passed on GitHub (a0efcc3). There, Pyodide loaded from the jsDelivr CDN and the chat answered, so the public CDN path is now verified.
- M1.7 phone, desktop and accessibility (same branch, PR #2):
  - axe (WCAG 2.2 AA) across every tab, the notice and the ticker drawer, in light and dark, found one issue: the tab bar was `role="tablist"` with plain buttons inside. The tabs now follow the ARIA tabs pattern, with `role="tab"`, `aria-selected`, `aria-controls`, tab panels, roving tabindex, and arrow, Home and End keys. axe now passes.
  - `tests/e2e` runs axe on every tab at 390x844 and 1280x800 in light and dark. It also checks for horizontal overflow and clipped payoff charts. CI installs axe-core for the e2e job.
  - `tests/test_a11y.py` covers the tab wiring and fails on TODO or placeholder text or a link that goes nowhere. The one `href="#"` now points at `#profile`.
  - 104 unit tests pass 3x. The 8 browser tests passed 3x here with Pyodide served locally.
- M1.8 README (same branch, PR #2): the top now has the CI badge, a "Try the demo" line (coming soon; it becomes a link when M1.6 is live), a phone screenshot of the built demo (`docs/screenshots/demo-phone.png`, fictional sample person), and a "Why I built it" paragraph. The project layout and status are refreshed. The MIT license was already there.
- M1.9 recruiter-ready review (same branch, PR #2): `docs/reviews/2026-10-24-recruiter-ready.md` ranks 10 findings. All 4 P1s are fixed: the nudge copy, the tab ARIA, the orphaned "…or paste it" label in the demo, and "Alex Rivera (sample)'s circle". There's also a P2 fix: a demo-only "Use the sample resume" button. Open P2s are the engine wait for interactive features on slow phones, SRI or self-hosting for Pyodide, and real-phone checks. 107 unit tests pass 3x and 9 browser tests pass.
- M1.5 part 1, pre-public privacy review (same branch, PR #2): `docs/reviews/2026-10-24-pre-public-privacy.md`. No keys, real resumes, data files or real emails were found in any file across all 13 commits on the 3 branches. One P2 is Chase's call: his two original commits carry his personal Gmail address as the commit author. Part 2, deciding to make the repo public, is Chase's.
- M1.6 prep (same branch, PR #2). Nothing deploys yet:
  - `.github/workflows/pages.yml` builds the demo and deploys it to Pages after CI passes on `main`. It skips itself while the repo is private (`github.event.repository.private == false`), so merging it is safe before Chase decides to go public.
  - The public build self-hosts Pyodide 0.28.3. `build_demo.py --pyodide-dir` copies the 5 runtime files the demo fetches (about 12 MB, served gzipped) into `site/pyodide/` and points `static.js` at them, so visitors' browsers never call a third-party CDN. `check_site.py --no-cdn` enforces that, flagging any extra file in `site/pyodide/`. The CI e2e job uses the same self-hosted build (npm-packed Pyodide), and a browser test asserts zero requests leave the site. That job passed on GitHub on d3b7c1b.
  - Review finding 7 (SRI or self-host) and finding 9 (cut-off Screener placeholder) are fixed.
  - Chat starter chips: `prebuilt.json` also holds each risk level's answers to the four chips, and `static.js` serves them when a chip is the first question, so a recruiter's first chat click is instant (finding 6, partly). Tests check the answers equal the engine's and that the chips work with Pyodide blocked. `prebuilt.json` is now 397 KB (60 KB gzipped).
  - 116 unit tests and 10 browser tests pass 3x.
- Phone tab bar (M1.7 P2): the right edge fades so the cut-off tab reads as "more", the scrollbar is hidden, and the active tab scrolls into view. Checked with Playwright at 390 and 1280, light and dark, with no errors or overflow. The footer "overlap" was a false alarm: the page already pads 72px below content.

## In progress
- Engine call still open (below). M1.3's prebuilt first screen covers the phone load time PLAN worried about (Today in under 2 s on throttled phones), which supports staying on Pyodide. M1.2 is built on the recommended Pyodide path; if Chase picks the JS port instead, `handlers.py` and `BrowserStore` still serve the local app and only `static.js` changes.

## Exact next step
Oct 25: Chase approved merging, so PR #2 merged into main with a merge commit, and that landed #1 too. Main has everything through M1.9. Next, under the Polish Freeze: UI polish toward 8/10 (baseline 2/10), scored by ux-reviewer at 390 and 1280 px, after the day's job-hunt gate is met. Still Chase's: the engine card and the decision to go public (Pages stays off while the repo is private).
Oct 25 to 26: Chase said "merge dependabot". Merged #3, #4, #6, #7, #9, #10 and #12. The rest (#5, #8 and #13: checkout v7, upload-pages-artifact v5, anthropic>=2.1.0) conflicted or hadn't run CI, so they're applied in one PR instead. The handoff check fails on every Dependabot PR because they don't touch HANDOFF.md, so expect that.

## Parked (Polish Freeze)
Polish Freeze since Oct 24 (Chase): no new scope; harden and polish the UI toward 8/10 (baseline 2/10); never merge, deploy or publish.
- "Chase uses it daily", laptop first (Chase's pick on Oct 24): M2.1 live data verified on his laptop, plus a README "use it yourself" setup; M2.2 an earnings and ex-dividend check before any short-option idea; M2.3 a morning summary of the day's ideas; M2.4 an idea track record. A phone version with hosting and a login would come after that.

## Decisions to review
- Oct 24, decided by Chase: Charlie is also a real product he'll use, laptop first. Parked minutes later by the Polish Freeze (see below).
- M1.6 prep: the public demo self-hosts Pyodide instead of loading it from jsDelivr. That's more privacy (no third party sees visitors) for about 12 MB of hosting on Pages. To undo, drop `--pyodide-dir` in `pages.yml` and use `check_site.py` without `--no-cdn`.
- M1.5: the history review recommends leaving the two original commits as they are (a rewrite would change every SHA). Chase decides whether the author email on them matters to him.
- M1.8: the README's "Why I built it" paragraph is written in Chase's voice from the project's stated goals (Munger's circle of competence, research first, safe by default). Chase should edit it before the repo goes public.
- M1.4: the back link and Reset demo sit in a banner strip right under the header, not in the header row, because the phone header is already full.
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
- 2026-10-24: `pages.yml` is ready to publish the demo at chaseholroyd.com/charlie/ once the repo is public. The demo serves Pyodide itself and makes no third-party calls (not deployed).
- 2026-10-24: recruiter-ready review done with no open P0 or P1 (`docs/reviews/2026-10-24-recruiter-ready.md`). The demo now has "Use the sample resume" (M1.9, not deployed).
- 2026-10-24: README now opens with the demo line, a phone screenshot and "Why I built it" (M1.8).
- 2026-10-24: the demo build passes axe WCAG 2.2 AA on every tab, with keyboard-navigable tabs (M1.7, not deployed).
- 2026-10-24: the demo build has a sample-data banner with a link back to chaseholroyd.com and a Reset demo button (M1.4, not deployed).
- 2026-10-24: the demo build (`tools/build_demo.py`, not deployed) now opens on the sample person's prebuilt ideas in under 2 s on a throttled phone, with data pinned to the build date.
- Studio status: [STUDIO-STATUS.md](https://github.com/holroydchase-afk/pm-tools/blob/main/STUDIO-STATUS.md).
- 2026-10-23: studio onboarding (M0.1). No public changes yet.
- 2026-10-23: night shift M0.2 + M0.3 (PR #2). No public changes; the demo isn't live yet.
- 2026-10-23: M1.1 Pyodide spike page (`spike/`, test page only, not deployed). No public changes.
