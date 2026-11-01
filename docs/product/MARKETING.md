# Marketing: claims register

This is the claims register for Charlie, owned by the `positioning` agent (studio standard, section 3). Public copy may only use claims listed here as "OK to say". That covers the README, the demo, the portfolio page at chaseholroyd.com/charlie.html, and any post or pitch. Each claim needs proof in this repo: a file, a test or a review doc. If a claim is not here, add a row with its proof before you use it. If the code changes and a claim stops being true, change its status in the same PR. Privacy wording also needs a check from `privacy-security`.

## What Charlie is and isn't

Charlie is a trading product, so this comes first and stays plain.

- **It is** an education and paper-trading idea helper. It turns a resume and interests into a circle of competence, scores companies in it, and shows 1 to 3 example trades a day to practice with on paper.
- **It is not** investment advice, and its ideas are not recommendations to buy or sell anything.
- **It is not** a broker. It places no real orders and holds no broker credentials. The paper portfolio only marks positions to current prices.
- **The public demo** at chaseholroyd.com/charlie/ runs on a fictional sample person and simulated (mock) market data, pinned to a "Sample market day". Nothing a visitor enters leaves their browser.
- **Live prices** come from Cboe's delayed (about 15 minutes) public data, and only in the local app. The demo never uses them. The Cboe endpoint is unofficial and may change.
- **Fundamentals are still demo numbers.** The SEC EDGAR adapter is built and unit-tested but not yet verified live, so live prices sit next to demo fundamentals ("Live prices · demo fundamentals").

Proof: `charlie/strategies.py` (`NFA`), `charlie/handlers.py` (`DISCLAIMER`: "not a broker or a registered investment adviser"), `charlie/portfolio.py` ("nothing here talks to a broker"), `charlie/browser.py` and `tests/test_demo.py::test_demo_imports_no_server_network_or_llm_code`, `web/app.js` data badge, `HANDOFF.md` Known limits (Cboe verified live Oct 28, SEC unverified).

## Claims

| Claim | Status | Proof |
|---|---|---|
| Charlie is for education and paper trading only. | OK to say | `CLAUDE.md` hard rules; `charlie/handlers.py` `DISCLAIMER`; `charlie/portfolio.py` |
| Charlie never places real orders and holds no broker credentials. | OK to say | No broker or order code in `charlie/`; `charlie/portfolio.py` docstring; `CLAUDE.md` hard rules |
| "Not financial advice. Paper trading only." is on every idea card, trade block, ticker drawer, chat trade card and chat reply, added by code. | OK to say | `charlie/strategies.py` `NFA`, `charlie/chat.py` (appends it), `web/app.js` `nfa()`; `tests/test_privacy.py` (`test_every_trade_carries_disclaimer`, `test_ui_renders_disclaimer_on_every_trade_surface`, `test_every_rule_based_reply_ends_with_disclaimer`, `test_claude_reply_refusal_and_fallback_end_with_disclaimer`); `tests/test_ux.py::test_CHL_UX45_...` (drawer) |
| Every trade shows max loss in dollars, breakeven and an exit plan. | OK to say | `charlie/strategies.py` `_finish()` (`max_loss`, `breakeven`, `management`); `tests/test_core.py::test_daily_ideas_respect_slider`; `tests/test_risk_math.py` RM18 to RM24 golden trades |
| Paper positions are flagged when the exit plan says to act (50% of max profit, 21 days or fewer left, or below breakeven). | OK to say | `tests/test_enhancements.py` ALERT1 to ALERT7 |
| A risk slider (1 to 5) decides which strategies are allowed. It defaults to Conservative (covered calls and cash-secured puts). | OK to say | `charlie/strategies.py` `RISK_LEVELS`, `DEFAULT_RISK_LEVEL = 2`, `allowed()`; `tests/test_core.py::test_strategy_gating`, `test_daily_ideas_respect_slider` |
| Uncovered calls are never offered. | OK to say | `charlie/strategies.py` `STRATEGIES` has no uncovered call; `tests/test_core.py::test_strategy_gating` (level 5 equals the full set) |
| No 0DTE or same-week expirations. | OK to say | `charlie/strategies.py` docstring and `pick_expiry` (25 to 55 days, fallback 20 to 70). Gap: no dedicated test yet. |
| Each trade risks a capped share of paper capital (5% at most, 2% at Speculative). | OK to say | `charlie/strategies.py` `RISK_LEVELS.max_risk_pct`; `tests/test_risk_math.py::test_RM27_...`; `tests/test_core.py::test_spread_risk_within_budget` |
| Familiarity raises a company's rank, never its position size. | OK to say | `charlie/scoring.py` (competence in the score), sizing only from `RISK_LEVELS` in `charlie/strategies.py`; `tests/test_core.py::test_competence_moves_score`; `docs/RESEARCH.md` section 1. Gap: no test pins size against familiarity. |
| Companies are scored with a Charlie Munger-style checklist: competence, quality, moat, balance sheet, value, minus red flags found by inversion. | OK to say | `charlie/scoring.py`; `docs/RESEARCH.md` section 2; `tests/test_core.py::test_scoring_prefers_quality` |
| The option math (prices, Greeks, chance of profit) is checked against textbook (Hull) values. | OK to say | `tests/test_risk_math.py` RM1 to RM36 |
| The public demo uses sample data only, labeled as sample, and saves only in the visitor's browser. Reset demo clears it. | OK to say | `charlie/demo.py` (fictional sample person), `charlie/browser_store.py`; `tests/test_demo_bar.py`; `tests/e2e/test_demo_bar_e2e.py` |
| The demo makes no third-party calls and has no keys, login or analytics. It serves Pyodide itself under a strict Content-Security-Policy. | OK to say | `tools/check_site.py` (`--no-cdn` in `pages.yml`); `tests/test_guardrails.py::test_site_check_*`; `tests/test_pages.py`; `docs/reviews/2026-10-28-recruiter-ready.md` (no off-origin requests, no CSP violations) |
| One Python engine runs both the local app and the browser demo (via Pyodide). | OK to say | `charlie/handlers.py`, `charlie/browser.py`, `web/static.js`; `tests/test_first_screen.py::test_prebuilt_matches_what_pyodide_computes` |
| The demo passes axe WCAG 2.2 AA on every tab, at phone and laptop widths, in light and dark. | OK to say | `tests/e2e/test_demo_e2e.py::test_every_tab_passes_axe_and_fits` |
| On a 4x-throttled phone over slow 4G, Today's ideas paint in about 1.1 seconds (measured Oct 28 on a local build). | OK to say, with the conditions | `docs/reviews/2026-10-28-recruiter-ready.md` Timings; `tests/e2e/test_demo_verified_e2e.py::test_DEMO_PHONE_2S_...` (under 2 s) |
| The full engine is ready in seconds on a phone. | Don't say | Same review: about 35 s on the throttled phone (1.9 s on a laptop). Say "the first screen is instant; your own resume takes longer on a phone". |
| The track record compares each past idea's stock move with SPY's over the same days, and whether the stock is above breakeven. | OK to say | `charlie/track_record.py`; `web/app.js` track note; `HANDOFF.md` Decisions (M1.13 A) |
| The local app can use live, delayed Cboe prices. | OK to say | `charlie/data/cboe.py`; `tests/test_cboe_live.py`; `HANDOFF.md` (verified live Oct 28) |
| Live fundamentals from SEC EDGAR. | Not yet | `charlie/data/sec.py` is built and unit-tested (`tests/test_core.py::test_sec_metrics`, `tests/test_data.py`), not verified live. Fundamentals are demo numbers. |
| Your resume stays on your machine; it is sent to Anthropic only if you tick the opt-in and set a key. Delete my data removes it. | OK to say (local app) | `tests/test_privacy.py::test_ai_resume_reading_is_opt_in`, `test_profile_get_hides_resume_text_and_delete_clears_it`, `test_profile_post_defaults_to_no_ai`; `docs/reviews/2026-10-28-hardening-privacy.md` |
| Chat with Claude (tools) in the local app with your own API key; rule-based chat otherwise. | OK to say | `charlie/chat.py`; `tests/test_chat_llm.py`. The demo's chat is rule-based only. |
| Paper trading through Alpaca. | Not yet | Future idea only (`README.md` Next steps). It must use a hard-coded paper URL with a test (`CLAUDE.md`). |
| Earnings and ex-dividend checks before short options. | Not yet | `PLAN.md` M2.2; `README.md` Known limits |
| Beats the market, or outperforms SPY. | Don't say | No evidence. The track record is sample data in the demo and grades the stock, not the trade. |
| Charlie recommends stocks or tells you what to buy. | Don't say | Contradicts `DISCLAIMER` and `NFA`. Say "example ideas to practice with on paper". |
| AI picks stocks for you. | Don't say | Scoring is a rule-based checklist (`charlie/scoring.py`). Claude is optional, local-only, and only for chat and an opt-in resume read. |
| Real-time data, or live prices in the demo. | Don't say | The demo is mock data (`charlie/browser.py`). Local live prices are delayed about 15 minutes. |
| The track record proves the scoring works, or shows trade profits. | Don't say | The demo's track record is sample data on simulated prices. It grades the underlying's move, not options P&L ("Options aren't re-priced", `web/app.js`). |
| Safe, risk-free, guaranteed income. | Don't say | Options carry real risk (`DISCLAIMER`). Say "defined worst case" or "max loss shown in dollars". |
| Broker-ready order ticket. | Don't say | Sounds like order routing. The UI says "Copy trade details" (`tests/test_ux.py::test_CHL_UX50_...`). |
| Works for any company you know. | Don't say | The universe is about 95 curated large caps across 17 sectors (`charlie/universe.py`, `README.md` Known limits). |

### Copy that is out of date today

Logged for the owner of each file. This doc does not change them.

- `README.md` says the demo is "coming soon". It has been live at chaseholroyd.com/charlie/ since Oct 29 (`HANDOFF.md`).
- `README.md` Known limits says the live adapters "couldn't be exercised". Cboe was verified live on Oct 28; only SEC is unverified.
- `README.md` "What's in the MVP" says "broker-ready order ticket". See the Don't say row above.
- `README.md` Next steps lists "track idea outcomes over time", which the track record now partly does (stock move, not trade P&L).

## Required wording

The exact string, character for character:

> Not financial advice. Paper trading only.

Where code adds it (never left to a prompt):

- `charlie/strategies.py`: `NFA` constant, set as `disclaimer` on every trade by `_finish()`.
- `charlie/chat.py`: appended to every chat reply, Claude and rule-based, if it isn't already the last line.
- `charlie/track_record.py` and `charlie/demo.py`: set as `disclaimer` on the track record and demo summary.
- `web/app.js`: `NFA` and `nfa()`, rendered on idea cards, trade blocks, the ticker drawer header, chat trade cards, screener results, the paper positions list and the track record.
- Tests that enforce it: `tests/test_privacy.py` (four disclaimer tests), `tests/test_guardrails.py::test_chat_panel_shows_the_disclaimer_in_markup`, `tests/test_ux.py::test_CHL_UX45_...`.

The longer notice in `charlie/handlers.py` (`DISCLAIMER`) also says Charlie "is not a broker or a registered investment adviser" and that "data may be delayed, incomplete, or simulated". Public copy that describes Charlie should match it.

_Last checked against code: 2026-11-01 (main at fff5508)._
