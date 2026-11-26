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
- **M1.5** Pre-public privacy review. Status: done (repo public by Chase's decision, re-confirmed Nov 24, intake #65; reviewed Oct 29, PS16/PS17, and again Nov 25, CHL-PS-P1 to P5). Branch: `m1.5-public-review`.
  - [x] privacy-security reviews the whole git history, `samples/` and docs for secrets or real personal data, and logs findings.
  - [x] Chase decides to make the repo public (needed for Pages).
- **M1.6** Pages deploy. Status: done; live at https://chaseholroyd.com/charlie/ (Oct 29). Branch: `m1.6-pages-deploy`.
  - [x] `pages.yml` builds `site/` and deploys from `main` only after CI passes.
  - [x] The demo loads at chaseholroyd.com/charlie/ with relative paths and no console errors.
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
- **M1.13** Enhancements: A, idea track record vs SPY; B, exit-plan alerts on paper positions. Status: done pending qa-tdd 3x and reviews (branch `claude/project-thread-hpanpa-enhance`; `tests/test_enhancements.py` and `tests/e2e/test_enhancements_e2e.py` green).
- **M1.14** Demo verified: rebuild `site/`, e2e, axe, `check_site.py --no-cdn`, prebuilt-drift test, throttled-phone timing, recruiter-ready re-review. Status: done, not pushed (branch `claude/project-thread-hpanpa-demo`; locally built site only, not deployed; phone Today 1.1 s at 4x CPU and slow 4G; ux-reviewer 8.5/10; privacy GO; CHL-UX37 to UX41 and CHL-R9 fixed; review `docs/reviews/2026-10-28-recruiter-ready.md`).
- **M1.15** Reusable blocks: pm-tools architecture templates and ACCOUNTS.md, studio privacy check or an INTAKE. Status: done (branch `claude/project-thread-hpanpa-blocks`; `docs/architecture/` with "Last checked" footers, `docs/product/ACCOUNTS.md`, `docs/REUSE.md`, the "Docs as we go" rule in CLAUDE.md; 3 INTAKEs in `docs/intakes/2026-10-28-product-studio.md` handed to Chase). The CI privacy-check swap to the shared `check-private.mjs` waits on INTAKE 1.
- **M1.16** Dark-mode layering on the live demo (intake #55). Status: todo. Spec: `docs/product/SPEC-DARK-LAYERS.md`, criteria CHL-DARK-1 to 13. Cards, panels, the ack dialog and the drawer step to 1.15:1 or more over the page in dark via a local `--raised` token; input, select, textarea, choice and slider edges 3:1 or more via a local `--control-edge`; light and increased contrast unchanged. CHL-DARK-11 to 13 (first-open notice instead of the blocking dialog, design rule D5) wait for Chase's call. Changes `web/`, so it waits for Chase's go to merge. About 3 sessions, plus 1 to 2 for the notice.
- **M1.17** (P2) Dark-mode fills on raised cards (CHL-UX-DK2, deferred from M1.16; also CHL-UX-DK5: the Trades number tiles `.stats .metric` have no fill next to raised position cards, fix `background: var(--raised)`). Status: todo. Secondary buttons, chips and input fills use `--fill`, which is 1.02:1 on `--raised` in dark; labels and 3:1 edges still carry them, so no WCAG failure. Done when hearth ships a `raised-fill` token (or Chase asks) and Charlie adopts it with a test.
- **M1.18** Public repo standards (intake #61). Status: doing (PR open Nov 25). Spec: `docs/product/SPEC-REPO-STANDARDS.md`, criteria CHL-RS-1 to 11. One docs/config PR: CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue and PR templates, README leads with "Not financial advice. Paper trading only." and the live demo link, `spike/` moves to `tools/spike/`, `tests/test_repo_standards.py`. `CLAUDE.md` and `HANDOFF.md` stay at the root (tooling needs them); `PLAN.md` stays until Chase decides. Touches no demo build path, so it merges on green. Description, topics and private vulnerability reporting are GitHub settings a session sets via `gh api` on Chase's go. About 1 to 2 sessions.
- **M1.19** Eval fixes (intake #60). Status: todo. Spec: `docs/product/SPEC-EVAL-FIXES.md`. PR A EF-CH-1 sizing (P0; Chase picked a 10% per-trade cap for cash-secured puts and shares, 5% on Learn, Nov 25), PR B EF-CH-2/3/4, PR C EF-CH-5/7. EF-CH-6 parked with CHL-DARK-11 to 13 (paused by Chase). Each waits for Chase's go (demo change).
- **M1.20** Site header (intake #64). Status: todo. Spec: `docs/product/SPEC-SITE-HEADER.md`. Inject the shared header in the demo build only; CHL-BAR-R1 to R3 fixed in Charlie; R4 and the theme key filed for the portfolio site (pm-tools #77). Waits for Chase's go; merge after M1.19 PR C.

Not in M1: resume file upload in the demo (paste and the sample resume are enough), Claude chat, live data, accounts.

## M3: Hunch to supply chain

M2.1 to M2.3 stay reserved for "Chase uses it daily" (HANDOFF "Later"). Chase asked for this next (Nov 17): "I provide a hunch ...; break my hunch down into a supply chain, looking at stock price and details for players, determine highest winners in supply chain, make recommendations." It follows his hunch-to-trend-plan template: restate, premise check, who benefits (obvious, sleepers, losers), options to act, 3 confirm and 3 kill signals.

**The bet.** Chase types a fuzzy hunch and in under a minute gets a trail he can check: the sharper claim, what's true vs what he added, the supply chain in tiers, which players Charlie can actually price and score, and 1 to 3 research leads with a safe paper trade. Signal: Chase runs 5 of his own hunches in the 14 days after merge and keeps at least 3 maps without editing the chain by hand (he says so in the thread). Stop: if he runs fewer than 3, or the Claude path fails validation on more than 2 of 5, freeze at playbooks and don't build M3.2.

**Ranking, plainly.** `rank = exposure weight x Charlie score`, exposure weights pure play 1.0, meaningful 0.6, small slice 0.25; ties by symbol. The Charlie score already has a value factor, so there is no separate margin-of-safety multiplier (it would count value twice). Exposure is a labeled judgment from the playbook or Claude, never a measured number.

- **M3.1** Hunch pipeline v1, local app. Status: done (PR #48, merged Nov 23 on Chase's go; the 14-day signal is still open). Branch: `m3.1-hunch`. One PR, about 5 sessions. Touches `charlie/` and `web/`, so it waits for Chase's go to merge.
  - New `charlie/hunch.py`: stages restate, premise, chain, enrich, rank, ideas, signals; each returns a plain dict. Offline drafter = curated playbooks matched by keywords: hearing (Case 1) and AI power demand (NVDA, ANET, VST, NEE, GE, CAT are in the universe). Claude drafter when `llm_available()`: strict JSON schema, then our code validates, prices and ranks.
  - Surfaces: `POST /api/hunch` in `server.py` and `Api.route`; a Hunches tab in the local app, hidden in static mode.
  - Acceptance criteria (qa-tdd writes these red first):
    - **CHL-HUNCH-1** (auto) Given a hunch, when `run_hunch` runs with mock data and the LLM off, then the result is JSON-serializable with `restate`, `premise`, `chain`, `ranked`, `unscored`, `ideas`, `signals`, `source` (`playbook`, `claude` or `none`) and `disclaimer`.
    - **CHL-HUNCH-2** (auto) Given the Case 1 hearing hunch, then `restate.claim` and `restate.horizon` are non-empty and the claim names earbuds or OTC hearing aids.
    - **CHL-HUNCH-3** (auto) Given the hearing hunch, then `premise.verdict == "partial"`, `premise.true` and `premise.added` are separate non-empty lists, and `premise.evidence` cites the FDA OTC rule (Aug 2022) and Apple's AirPods Pro 2 hearing aid feature (Sep 2024), each with source name and date.
    - **CHL-HUNCH-4** (auto) Given the hearing hunch, then every player has name, role, tier (`obvious`, `sleeper` or `loser`), ticker or null, listing (`us`, `non_us`, `private`) and exposure; Knowles and Qualcomm are sleepers and at least one loser is premium clinic-sold hearing aids.
    - **CHL-HUNCH-5** (auto) Given players outside `charlie/universe.py`, non-US or private (KN, REGN, Sonova, Loop), then they stay in the map in `unscored` with a reason, and no `KeyError` or 5xx occurs in mock mode.
    - **CHL-HUNCH-6** (auto) Given a fake Claude client whose JSON includes `price`, `score` or `max_loss` fields or an unknown or malformed ticker, then those fields are dropped, the ticker is unscored, and every price shown equals `md.quote()` for that symbol.
    - **CHL-HUNCH-7** (auto) Given the same hunch, profile and date twice, then `ranked` order is identical and matches the formula above, ties broken by symbol.
    - **CHL-HUNCH-8** (auto) Given two profiles that differ only in familiarity, then the trade for the same symbol and risk level has the same quantity and max loss (familiarity moves rank, never size).
    - **CHL-HUNCH-9** (auto) Given ranked US universe names, then at most 3 ideas each carry why, key risk and an optional trade from `strategies.allowed(risk)`; every trade has max loss in dollars, breakeven and exit plan, no uncovered call, and expiry 20 days or more out.
    - **CHL-HUNCH-10** (auto) Then the result, every idea and every trade carry `NFA` added in code, and the Hunches tab shows it on the panel and each trade card (unit plus e2e).
    - **CHL-HUNCH-11** (auto) Then `signals.confirm` and `signals.kill` each hold exactly 3 non-empty items, each naming what to watch.
    - **CHL-HUNCH-12** (auto) Given a hunch no playbook matches with the LLM off, then `source == "none"`, the message says there is no playbook yet and names the closest universe domain (or none), and there are no players, ideas or trades.
    - **CHL-HUNCH-13** (auto) Given a fake Claude client that returns invalid JSON, misses the schema or raises, then the result falls back to playbook or `none` with a 200; given a valid response, `source == "claude"` and the premise is labeled "Claude's draft, sources not checked".
    - **CHL-HUNCH-14** (auto) Given a Claude call, then the request carries only the hunch text: no resume, profile, holdings or capital, and nothing is logged beyond the hunch length.
    - **CHL-HUNCH-15** (auto) Given an empty hunch or one over 600 characters, then the API returns 422; static mode never imports `anthropic` and hides the tab.
    - **CHL-HUNCH-16** (auto) Then no output string or tab copy says "winner", "buy", "recommend" or "guaranteed"; labels are "most exposed" and "research lead" (claims register).
    - **CHL-HUNCH-17** (auto) The Hunches tab fits at 390 and 1280 px, light and dark, with no overflow, and passes axe WCAG 2.2 AA.
    - **CHL-HUNCH-18** (manual) Chase runs the hearing hunch locally with `CHARLIE_DATA=auto`; AAPL, QCOM, COST and WMT show live Cboe prices, and he says whether the trail is one he'd keep.
  - Also in the PR: `docs/architecture/02-data-flow.md` (hunch text to Anthropic) with its "Last checked" footer, and ux-reviewer plus privacy-security passes.
- **M3.2** Hunches in the public demo. Status: todo. Chase's call (Nov 23, "can we get it to the demo?"): build it now; this overrides the gate above ("only if M3.1's signal is met"). The M3.1 signal still decides whether the Claude path and a third playbook get built. One PR, about 3 sessions. Touches `charlie/`, `web/`, `tools/build_demo.py`, so it waits for Chase's go to merge (it redeploys the demo).
  - How: in static mode `Api.hunch` runs `run_hunch(..., client=None)` (playbooks only, `claude_client()` never called) on mock data, the sample person's profile and the visitor's risk level. `charlie/hunch.py` joins the bundle. Search shows the Screener / Hunches switch in the demo. `prebuilt.json` carries the hearing hunch for each risk level so Hunches paints before Pyodide is ready.
  - Acceptance criteria (qa-tdd writes these red first; the static half of CHL-HUNCH-15 and its e2e twin are re-pinned to this spec, not weakened: "never imports anthropic" stays, "404 and no tab" becomes CHL-HUNCH-DEMO-1/3):
    - **CHL-HUNCH-DEMO-1** (auto) Given static mode, when `POST /api/hunch` runs the hearing hunch through `charlie.browser.request`, then it returns 200 with `source == "playbook"`, and `anthropic`, `charlie.llm_profile`, `requests` and `charlie.server` are not in `sys.modules` afterwards; `claude_client` is never called (spy).
    - **CHL-HUNCH-DEMO-2** (auto) `charlie/hunch.py` is in `tools/build_demo.MODULES`; `test_demo_imports_no_server_network_or_llm_code` covers it unchanged; `check_site.py --no-cdn` passes on the built site with no new host.
    - **CHL-HUNCH-DEMO-3** (auto, e2e) Given the demo, Search shows the Screener / Hunches switch, `#hunch` deep-links, the phone bar stays at five tabs, and CHL-HUNCH-SW-1 to SW-4 pass on the demo build.
    - **CHL-HUNCH-DEMO-4** (auto) `prebuilt.json` holds the hearing hunch result for levels 1 to 5, and each equals what Pyodide computes for the same day (drift test, like `test_prebuilt_matches_what_pyodide_computes`); any `invalid_if_keys` change (profile, resume) stops serving it.
    - **CHL-HUNCH-DEMO-5** (auto, e2e) Given a fresh demo load with the engine held back, when the visitor opens Search > Hunches, then the hearing example is filled and its map shows from prebuilt; Run hunch, the other example button and the textarea are disabled with a visible "Loading the engine…" state (never a silent dead button) and enable when the engine is ready.
    - **CHL-HUNCH-DEMO-6** (auto) Given the AI power example or free text matching a playbook, the map renders from the engine; given free text matching none, "No map for this hunch yet" with the two example buttons; no 5xx; empty or over 600 chars gives the 422 message.
    - **CHL-HUNCH-DEMO-7** (auto, e2e) The Hunches view shows a "Sample data" label, and its form note reads that the hunch stays in this browser and uses built-in maps (no "computer", no Claude mention). Copy comes from a MARKETING.md row added by positioning.
    - **CHL-HUNCH-DEMO-8** (auto, e2e) Given a research lead's "Paper trade this", the position lands in Paper from localStorage, survives reload, and Reset demo clears it; hunch text itself is never written to localStorage, the URL or the console.
    - **CHL-HUNCH-DEMO-9** (auto, e2e) NFA on every lead and trade block, banned words (CHL-HUNCH-16) absent, axe WCAG 2.2 AA and no overflow at 390 and 1280 light/dark, and the hearing result at 390 stays under the 4,500px budget with the demo bar showing.
    - **CHL-HUNCH-DEMO-10** (auto, e2e) Throttled phone (4x CPU, slow 4G): Today still paints under 2 s (DEMO-PHONE-2S unchanged) and Search > Hunches paints the prebuilt map under 2 s.
    - **CHL-HUNCH-DEMO-11** (manual) Every dated evidence line in both playbooks is checked against its source before merge (HANDOFF follow-up), and privacy-security and ux-reviewer (showcase mode) pass with no P0/P1.
  - Cut from M3.2: Claude in the demo (keys, network); a prebuilt AI power hunch (engine computes it; keeps prebuilt.json small); saved hunch history; hunch in chat; new playbooks; hunch text in the URL or shareable links; a Today entry point to Hunches.
  - Risks: the 4,500px phone budget has about 35px of margin before the demo bar (DEMO-9); prebuilt.json growth slows first paint (DEMO-10; drop the prebuilt to level 2 only if it blows the budget); public playbook evidence that is wrong is a claims problem, not a bug (DEMO-11).
  - Success: Chase opens chaseholroyd.com/charlie/ on his phone and gets a hearing map without waiting. Stop: if DEMO-10 or DEMO-9 can't pass without cutting the map, ship Hunches local-only and say so.

Not in M3.1: chat tool for hunches; saved hunch history (no schema change); a third playbook (GLP-1); web search or citation fetching (Claude has no browse tool, so its evidence is labeled unchecked); adding KN, REGN or other names to the universe (it changes daily ideas and the demo's prebuilt drift); live prices for US tickers outside the universe; non-US listings; position sizing from a hunch; any "buy" or "winner" wording.

## Later (M2+)

- "Chase uses it daily" items not in the Oct 28 release: earnings and ex-dividend check (needs a data source and architect), morning summary (cut; M1.13 B covers most of it). See `docs/plans/2026-10-28-release.md`.

- A private hosted version with a login, so Chase can check ideas on his phone (needs auth and Origin checks first, per CLAUDE.md).
- Alpaca paper orders from "Paper trade this" (paper URL hard-coded, with a test that it can't reach the live URL).
