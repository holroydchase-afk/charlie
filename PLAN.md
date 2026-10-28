# Charlie plan

Planning code `CHL`. IDs follow studio-agents `docs/planning-ids.md`: each task is one PR, branch `m1.N-slug`, PR title `M1.N: short name`. Status words: todo, doing, blocked, done, dropped.

The bet: a recruiter on a phone opens chaseholroyd.com/charlie/, sees a sample person's circle of competence turn into 1 to 3 scored, explained trade ideas within 90 seconds, and gets that Chase can take a fuzzy idea to a working, careful product. The demo is static, has no login and runs on sample data only. FastAPI can't run on GitHub Pages, so the existing Python engine runs in the browser.

**Engine decision: Pyodide, not a JS port.** The engine is about 2,000 lines of mostly stdlib Python with 35 tests, and Pyodide keeps it as the one source of truth with test reuse, while a prebuilt first screen covers the phone load time (M1.3). Stop condition: if M1.1 shows the interactive app takes over 10 seconds on a throttled mid-range phone even with the prebuilt first screen, port `scoring.py` and `strategies.py` to JS and keep pytest as the reference for golden-output tests.

## M0: Studio setup and a green main

- **M0.1** Studio setup. Status: doing. Branch: `claude/project-thread-dlm2ig`.
  - [x] CLAUDE.md (hard rules + Studio agents), HANDOFF.md (with Portfolio / public presence), PLAN.md, `.claude/agents/`, `.claude/settings.json`, handoff-check, `ci.yml` (pytest + privacy check), dependabot, MIT LICENSE, README CI badge.
- **M0.2** Restore `charlie/data/` and green CI. Status: done (branch `claude/project-thread-74d6f6`).
  - [x] `charlie/data/` (market facade, Cboe and SEC adapters, mock generator) is committed and no longer gitignored.
  - [x] `python -m pytest -q` passes all 35 tests on a clean clone, and the M0.1 `ci.yml` is green on every PR.
  - [x] `CHARLIE_SEC_UA` is read only from env with a `you@example.com` placeholder, and live SEC calls refuse to run while it's unset.
- **M0.3** Privacy fixes from the M0.1 privacy-security review. Status: done (shipped with M0.2 on `claude/project-thread-74d6f6`, PR #2).
  - [x] Every chat reply (Claude and rule-based, including the fallback) ends with "Not financial advice. Paper trading only." added in code, not by the prompt. Test enforces it.
  - [x] Every idea card, trade block, chat trade card and the ticker drawer show the same line. Test enforces it.
  - [x] "Use Claude to read my resume" is opt-in (unchecked, `Form(False)`), with a line saying the resume goes to Anthropic's API.
  - [x] `GET /api/profile` returns the resume length, not its text; `DELETE /api/profile` exists; README says bind 127.0.0.1 only.
  - [x] `POST /api/profile` rejects cross-site form posts (Origin check), and errors return generic text.

## M1: Recruiter-demoable v1

Done means the recruiter-ready bar in pm-tools `docs/ONBOARDING.md` section 5 is met at chaseholroyd.com/charlie/.

- **M1.1** Pyodide spike. Status: done; engine call waiting on Chase (see `docs/decisions/engine-in-browser.md`). Shipped on `claude/project-thread-74d6f6`, PR #2.
  - [x] A static page loads the `charlie` package in Pyodide with mock data and shows today's ideas for the sample resume.
  - [x] Those ideas match what pytest produces for the same profile, date and risk level.
  - [x] Cold and warm load times on a throttled phone profile are written in `docs/decisions/engine-in-browser.md`, with a go or switch-to-JS call.
- **M1.2** Browser adapter. Status: done (built on the recommended Pyodide path; shipped on `claude/project-thread-74d6f6`, PR #2).
  - [x] In static mode, `api()` in `web/app.js` calls Python handlers in Pyodide instead of `fetch`, and the same UI file serves both modes.
  - [x] A `BrowserStore` with the same interface as `Store` saves profile, screens and paper trades to `localStorage` only.
  - [x] Static mode forces mock data, uses rule-based chat, and never imports `anthropic`, `requests` or the live adapters.
  - [x] New pytest tests cover the handler router and `BrowserStore` parity with `Store`.
- **M1.3** Instant first screen. Status: done (shipped on `claude/project-thread-74d6f6`, PR #2).
  - [x] `tools/build_demo.py` writes `site/` with the web app, the Python package, and the sample profile with its ideas prebuilt as JSON.
  - [x] On a throttled phone, Today shows the sample person's ideas in under 3 seconds while Pyodide loads behind them.
  - [x] Controls that need Pyodide show a short loading state, never a dead button.
- **M1.4** Demo guardrails. Status: done (shipped on `claude/project-thread-74d6f6`, PR #2; the CI e2e job's first run is pending).
  - [x] A banner says the data and the resume are samples and that everything stays in this browser.
  - [x] "Not financial advice. Paper trading only." shows on every idea card and in the chat panel.
  - [x] The header links back to chaseholroyd.com, and a "Reset demo" button clears local data.
  - [x] A CI privacy check fails on API key patterns or calls to hosts other than the Pyodide CDN.
  - [x] Playwright tests assert the disclaimer on each idea and in chat, and the back link.
- **M1.5** Pre-public privacy review. Status: review done (`docs/reviews/2026-10-24-pre-public-privacy.md`, PR #2); waiting on Chase's decision to go public. Branch: `m1.5-public-review`.
  - [x] privacy-security reviews the whole git history, `samples/` and docs for secrets or real personal data, and logs findings.
  - [ ] Chase decides to make the repo public (needed for Pages). Until then M1.6 is blocked.
- **M1.6** Pages deploy. Status: blocked on M1.5; `pages.yml` is written and gated on the repo being public (PR #2). Branch: `m1.6-pages-deploy`.
  - [x] `pages.yml` builds `site/` and deploys from `main` only after CI passes.
  - [ ] The demo loads at chaseholroyd.com/charlie/ with relative paths and no console errors.
- **M1.7** Phone, desktop and accessibility. Status: done (shipped on `claude/project-thread-74d6f6`, PR #2).
  - [x] Playwright screenshots at 390x844 and 1280x800, light and dark, show no overflow or clipped payoff charts.
  - [x] An axe check passes WCAG 2.2 AA on every tab, and there are no dead links or TODO text.
- **M1.8** README and one story. Status: done except the live demo link (it arrives with M1.6) and Chase's edit of "Why I built it" (shipped on `claude/project-thread-74d6f6`, PR #2).
  - [ ] README opens with the CI badge, a "Try the demo" link, a phone screenshot and why Chase built it, and has an MIT license.
  - [x] HANDOFF.md has the Portfolio / public presence section, and README, demo and portfolio copy agree on stage and features.
- **M1.9** Recruiter-ready review. Status: review done and all P0/P1 fixed; the portfolio ask waits on M1.6 (shipped on `claude/project-thread-74d6f6`, PR #2).
  - [x] ux-reviewer, qa-tdd and privacy-security findings are ranked in `docs/reviews/<date>-recruiter-ready.md`.
  - [ ] All P0 and P1 findings are fixed, then Chase is asked to add Charlie to the portfolio.

### Release run (Oct 28, `docs/plans/2026-10-28-release.md`; the Polish Freeze was lifted by Chase)

- **M1.10** Works for real: fix CHL-R1 to R8, each with a failing qa-tdd test first. Status: done (branch `claude/project-thread-hpanpa`; `tests/test_works_for_real.py` green; all suites 3x green; PR "M1.10: works for real"). New copy gets its ux-reviewer pass in M1.11.
  - [x] Every R-item's test is green.
  - [x] Fresh-DB walkthrough in mock and `CHARLIE_DATA=auto` with no 5xx and no console errors; 157 unit + 10 browser tests green 3x.
- **M1.11** UI to 8/10: ux-reviewer scores the local app and the demo at 390 and 1280 px, light and dark; fix every P0/P1 and P2s until 8/10. Status: done (branch `claude/project-thread-hpanpa-ui`; ux-reviewer 5 → 7 → 8/10; CHL-UX1 to UX35 built in three rounds, UX36 optional; `tests/e2e/test_ui_polish_e2e.py` green; unit 170 and e2e 61 green; reviews in `docs/reviews/2026-10-28-ux-*.md`).
- **M1.12** Harden: a pytest for every core endpoint (happy path and bad input), profile validation 422s, chat refusal wording, no resume in logs, SQLite `secure_delete`, `check-logs` over `charlie/`. Status: done, not pushed (branch `claude/project-thread-hpanpa-harden`; `tests/test_harden.py` green, all suites 3x; privacy-security findings CHL-PS1 to PS8, PS11, PS12 fixed and re-checked, GO for the public demo; re-check findings PS14 PDF content-stream bomb and PS15 holdings parse fixed; review in `docs/reviews/2026-10-28-hardening-privacy.md`; `handlers.py` coverage 98%). PS9, PS10 and PS13 move to M1.13 or later. `check-logs` scans only JS, and `charlie/` has none, so the Python log check is the no-resume-in-logs tests instead.
- **M1.13** Enhancements: A, idea track record vs SPY; B, exit-plan alerts on paper positions. Status: todo.
- **M1.14** Demo verified: rebuild `site/`, e2e, axe, `check_site.py --no-cdn`, prebuilt-drift test, throttled-phone timing, recruiter-ready re-review. Status: todo.
- **M1.15** Reusable blocks: pm-tools architecture templates and ACCOUNTS.md, studio privacy check or an INTAKE. Status: done (branch `claude/project-thread-hpanpa-blocks`; `docs/architecture/` with "Last checked" footers, `docs/product/ACCOUNTS.md`, `docs/REUSE.md`, the "Docs as we go" rule in CLAUDE.md; 3 INTAKEs in `docs/intakes/2026-10-28-product-studio.md` handed to Chase). The CI privacy-check swap to the shared `check-private.mjs` waits on INTAKE 1.

Not in M1: resume file upload in the demo (paste and the sample resume are enough), Claude chat, live data, accounts.

## Later (M2+)

- "Chase uses it daily" items not in the Oct 28 release: earnings and ex-dividend check (needs a data source and architect), morning summary (cut; M1.13 B covers most of it). See `docs/plans/2026-10-28-release.md`.

- A private hosted version with a login, so Chase can check ideas on his phone (needs auth and Origin checks first, per CLAUDE.md).
- Alpaca paper orders from "Paper trade this" (paper URL hard-coded, with a test that it can't reach the live URL).
