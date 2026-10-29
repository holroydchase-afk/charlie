# Recruiter-ready re-review: 2026-10-28 (M1.14 Demo verified)

Branch `claude/project-thread-hpanpa-demo` (M1.10 to M1.13 stacked). Roles played in turn: qa-tdd, ux-reviewer (showcase mode), privacy-security (pre-public-demo). Findings ranked by severity.

**What this verifies, and what it doesn't.** Everything here is the **locally built** site. chaseholroyd.com isn't reachable from the cloud sandbox, and the demo isn't deployed (the repo is private and Pages is off), so nothing was checked on the live host or on a real phone. The site was built exactly as `pages.yml` builds it (`python tools/build_demo.py site --pyodide-dir <pyodide 0.28.3 npm package>`, then `python tools/check_site.py site --no-cdn`, which passed), served on 127.0.0.1 under a `/charlie/` subpath, and driven in Chromium 1243 with Playwright.

## Scores

- **ux-reviewer showcase score: 8.5/10** (8/10 before M1.13). The track record gives a hiring manager a reason to stay, and the M1.14 fixes cleared the one visible typo and the disclaimer gaps. It isn't 9 yet because of CHL-UX42 (a visitor never sees an alert chip), CHL-R11 (the free-form features wait about 35 s on a throttled phone) and the stale README screenshot (CHL-UX44).
- **Verdict: Ready** for the portfolio ask once M1.5 (repo public) and M1.6 (Pages) are done. No open P0 or P1.
  - Recruiter on a phone, 90 s: what it is, who it's for and a proof point ("Top idea today: ABT · 84% chance of profit · max loss $12,417") are on the first screen in about 1.1 s; Back to chaseholroyd.com and Reset are in the banner.
  - Hiring manager on a laptop, 5 min: ideas, payoff charts, track record vs SPY, screener, chat, a paper trade and your own resume all work on sample data; the engine is ready in under 2 s.

## Timings (median of 3 cold-cache runs, served under /charlie/)

| Profile | First paint | Today's first idea card | Track record | Engine ready | Transfer |
|---|---|---|---|---|---|
| Laptop 1280x800, no throttle, gzip | 52 ms | 69 ms | 85 ms | 1.86 s | 5.7 MB |
| Phone 390x844, 4x CPU, slow 4G (150 ms RTT, 1.6 Mbps down, 750 kbps up), gzip | 460 ms | **1.12 s** (1.12, 1.10, 1.12) | 1.17 s | 35.2 s | 5.7 MB |
| Phone profile, no compression | 616 ms | 3.26 s | 3.31 s | 71.4 s | 12.9 MB |
| Laptop, no compression | 60 ms | 72 ms | 92 ms | 1.66 s | 12.9 MB |

**Done-when met:** Today paints in 1.1 s on the 4x phone profile, under the 2 s bar, *when text files are gzipped*, which GitHub Pages does for HTML, CSS, JS and JSON (unverified live; see CHL-R10). The gzip runs also compressed the wasm; if Pages doesn't, engine-ready on the phone profile rises (about 8.6 MB instead of 2.8 MB for that file), and Today is unaffected. Gzipped sizes: `prebuilt.json` 423 KB to 64 KB, `app.js` 59 KB to 19 KB, `pyodide.asm.wasm` 8.6 MB to 2.8 MB, `python_stdlib.zip` 2.4 MB (already compressed).

## Verified (qa-tdd)

Walkthrough in Chromium at 390x844 under `/charlie/` (scripts in the session scratchpad, not in git):

- No console errors or warnings, no CSP violations (`securitypolicyviolation` listener), no failed requests, and zero requests outside the site's origin, across every step below.
- Today: 3 idea cards, each with "Not financial advice. Paper trading only."; ack modal on first visit; banner "Sample data." with Back to chaseholroyd.com (`https://chaseholroyd.com/`) and Reset.
- Demo date: `prebuilt.json` is pinned to the build day (2026-10-28) and Today reads "2026-10-28 · Conservative". Track-record idea days (2026-09-30, 10-14, 10-21) are all before it. Sensible on the build day; see CHL-UX43 for drift after that.
- Track record: 9 past ideas (6 shown, 3 folded), SPY column, Sample badge, the not-re-priced note and the disclaimer.
- Ticker drawer: opens, shows the disclaimer, every trade block shows max loss (or money tied up), breakeven and the exit plan; Escape closes it.
- Paper trade: "Paper trade this" turns to "Opened ✓", the position is listed on Portfolio, Close trade shows "Closed ABT cash-secured put. Paper P&L: $0.00".
- Alert chips: a seeded near-expiry put and a below-breakeven share position show "Near expiry", "Take profit?" and "Below breakeven" at 390 and 1280, light and dark. A trade opened from today's ideas shows none (CHL-UX42).
- Screener: runs on open with 16 results. Chat: a starter chip and a typed question ("Tell me about Visa") both answer with the disclaimer. Learn renders.
- Paste your own resume (a fictional text): the profile becomes "Your circle", Today says "Showing ideas for your profile." Reset demo clears every `charlie:` key and returns to Alex Rivera.
- Subpath: the site works at `/charlie/` with relative paths only; `/charlie` redirects to `/charlie/`.
- Disclaimer on every trade surface: idea cards, trade blocks, drawer, chat replies and chat trade cards, track record, and now the screener results and portfolio list (CHL-R9), plus the fixed footer.
- Local app parity (uvicorn, `CHARLIE_DATA=mock CHARLIE_LLM=off`, scratch `CHARLIE_DB`/`CHARLIE_CACHE`): Today renders; the track record shows "No past ideas yet. Come back tomorrow." on a fresh database and 3 rows (SPY, disclaimer, no Sample badge) after a past day's snapshot is added; `/api/paper` positions carry `alerts`; `/api/track-record` returns `benchmark: SPY`, `sample: false`; no console messages. Same features as the demo.
- axe WCAG 2.2 AA on every tab at 390 and 1280, light and dark (existing e2e test, green).

New automated checks (`tests/e2e/test_demo_verified_e2e.py`, `tests/test_demo_verified.py`):
- `DEMO-SUBPATH`: the built site served under `/charlie/` loads, starts the engine, opens the drawer and answers chat with no failed request and nothing outside `/charlie/`. Passed on first run (no red: the build was already relative).
- `DEMO-PHONE-2S`: Today's first card paints in under 2 s on the 4x CPU, slow-4G phone profile with gzip and a cold cache. Passed on first run (about 1.1 s here).
- One failing test first for each fix below.

Not tested: the live host (gzip, headers, the real `/charlie/` path), real phones and Safari or Firefox, a scheduled rebuild, and the CDN build's CSP (jsDelivr is unreachable here).

## Ranked findings

| ID | Sev | Role | Screen | Finding | Status |
|---|---|---|---|---|---|
| CHL-UX37 | P1 | ux-reviewer | Banner, laptop | The banner read "Back to chaseholroyd.com · **Resetdemo**": the button is `inline-flex`, so the space at the start of the " demo" span collapsed. The first thing a hiring manager sees looked unfinished. (Nielsen: aesthetic and minimalist design.) | Fixed: the button's text is wrapped in one span. Test: `test_CHL_UX37_…` (red: `'Reset\ndemo'`). |
| CHL-R9 | P1 | qa-tdd | Screener results, Portfolio list | "Not financial advice. Paper trading only." was missing from the screener result list and the paper positions list (only the fixed footer had it). Both show trades, so the hard rule applies. | Fixed: the line now follows the screener results and the positions list (shared `web/`, so the local app too). Test: `test_CHL_R9_…` at 390 and 1280. |
| CHL-UX38 | P2 | ux-reviewer | Portfolio table, laptop | "2026-10-02" and "expires 2026-11-13" wrapped mid-date at 1280. | Fixed: `nowrap` on both. Test: `test_CHL_UX38_…`. |
| CHL-UX39 | P2 | ux-reviewer | Track record, laptop | The Then/Stock/SPY columns shifted 1 to 3 px from row to row because the last column was sized by each row's chip. | Fixed: a fixed 12rem chip column. Test: `test_CHL_UX39_…`. |
| CHL-UX40 | P2 | ux-reviewer | Delete my data | The local app's confirm says "saved ideas and saved market data"; the API's `deleted` list said "cached ideas", "cached market data". The demo's confirm rightly leaves market data out (the demo has none). | Fixed: the API now says "saved ideas", "saved market data". Test: `test_CHL_UX40_…`. |
| CHL-UX41 | P2 | ux-reviewer | Chat | The rule-based "Today's ideas" reply opened with "(mock (demo data, not real prices))": jargon and brackets inside brackets. | Fixed: "(sample data, not real prices)"; live reads "delayed real prices". Test: `test_CHL_UX41_…`. |
| CHL-UX42 | P2 | ux-reviewer | Portfolio, demo | A visitor never sees an alert chip: a trade opened today fires no rule on the pinned day, so M1.13 B is invisible in the demo. | Fixed Oct 29: a one-line explainer on Portfolio, shown once a trade exists. |
| CHL-UX43 | P2 | ux-reviewer | Today | The demo's data is pinned to the build day, and `pages.yml` rebuilds only on a push to main, so a visitor weeks later sees an old "Today" date. Labeled as sample, so not a contradiction. | Open. architect and Chase: add a weekly `schedule:` to `pages.yml`. |
| CHL-R10 | P2 | qa-tdd | First load | Today's 2 s bar depends on the host compressing `prebuilt.json` (423 KB raw, 64 KB gzipped): 3.3 s on the phone profile without compression. | Open. Check `content-encoding: gzip` on the live host after M1.6; if missing, split `prebuilt.json` per level. |
| CHL-R11 | P2 | qa-tdd | Free-form chat, Screener, own resume | These wait for the engine: about 35 s on the phone profile (1.9 s on a laptop) behind "Starting Charlie's engine". Known since M1.1. | Open (later: Pyodide in a Web Worker, lazy stdlib). |
| CHL-UX44 | P2 | ux-reviewer, positioning | README | The README phone screenshot predates M1.11 (no hero, no track record). | Open: positioning retakes it from the built demo. |

## Privacy and safety (privacy-security, pre-public demo)

**Verdict: GO for the public demo** (unchanged from the M1.12 re-check), with no new findings.

- Built site: `check_site.py --no-cdn` passes (no keys; hosts only chaseholroyd.com and the SVG namespace). pm-tools `check-private.mjs` is clean on the site files and the unpacked `charlie.zip`. A grep for emails, phone numbers, local paths and owner names found only the back link, the JPMorgan Chase ticker name and env-var names in help text.
- The only person in the build is the fictional Alex Rivera (`samples/`). The engine zip holds no server, SQLite, Anthropic or live-data modules.
- In the browser: zero off-origin requests, no CSP violations, the CSP meta is present; data lives only in `localStorage` (`charlie:*`), and Reset demo clears it. The track record and alerts are computed in the browser from the visitor's own `localStorage`; nothing new leaves it.
- Docs on `claude/project-thread-hpanpa-blocks` (`docs/architecture/03-threat-model.md`, `docs/product/ACCOUNTS.md`, `docs/intakes/2026-10-28-product-studio.md`): no keys, tokens, real emails (only the `you@example.com` placeholder), account names, project ids or private links; ACCOUNTS names secrets by variable only. `check-private.mjs` is clean on them. The threat model matches the code (it lists PS9, PS10 and PS13 as open, which is accurate).
- Required now, all met: the hard rules, no secrets or personal data in the build or docs, no analytics or third parties. Still scheduled (unchanged): PS9 chat disclosure, PS10 the demo keeping pasted resume text in `localStorage`, PS13 hashed lock file and pip-audit; history author email (M1.5, Chase).

## For Chase

1. Nothing blocks the portfolio ask beyond M1.5 (privacy review of history and your go to make the repo public) and M1.6 (Pages).
2. Your call (with architect): a weekly scheduled rebuild so the demo's date stays fresh (CHL-UX43).
3. After M1.6, open chaseholroyd.com/charlie/ on your phone once: it confirms gzip (CHL-R10) and real-device feel.

## Test runs (after the fixes, 3x)

Unit (`CHARLIE_DATA=mock CHARLIE_LLM=off python -m pytest -q`): 349 passed, 5 skipped, three times. Browser e2e on the self-hosted build (`CHARLIE_E2E=1 … pytest -q tests/e2e`): 72 passed, three times, no flakes. Before this phase: 347 unit and 65 e2e.
