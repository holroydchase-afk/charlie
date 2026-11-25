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
| Hunches (demo): "Type a hunch; Charlie maps who it touches and which companies it can score." Uses "research leads" and "most exposed". Sample data. Built-in maps for two example hunches (hearing, AI power). The hunch stays in this browser. | OK to say once CHL-M3.2 ships to the demo | `charlie/hunch.py` (`HEARING`, `AI_POWER` playbooks, `RANKED_LABEL`, "research lead" label, `_FORBIDDEN`); `web/app.js` hunch view. Playbook evidence dates and facts checked against primary sources on 2026-11-23 (see Hunch evidence below). Re-verify before the demo PR merges. |
| Hunches pick "winners", give "recommendations", or tell you what to "buy". | Don't say | `charlie/hunch.py` `_FORBIDDEN` strips these words; leads are for research and paper practice only. Say "research leads" or "most exposed". |
| The demo uses AI (Claude) to map your hunch. | Don't say | The demo has no key and makes no network calls; it uses the two built-in playbooks only. Claude drafts exist only in the local app with a key, labeled "Claude's draft, sources not checked" (`CLAUDE_LABEL`). Any other hunch in the demo gets the "no map yet" message. |
| Hunches show live prices. | Don't say | Demo prices are mock (`charlie/browser.py`). |
| Charlie maps any hunch. | Don't say | Demo: two built-in maps. Local app: the same two, plus Claude drafts only with opt-in and a key. |

### Hunch demo strings (proposed, for the engineer to apply)

- Sample label on the Hunches view: `Sample data. Built-in maps for two example hunches.`
- Form note under the hunch box: `Your hunch stays in this browser.` (CHL-UX-H34: the built-in maps fact is said once, in the sample label.)
- Hunches subtitle: `Type a hunch. Charlie checks it and ranks the companies it touches.` (CHL-UX-H36: two lines at 360px, so the Search switch doesn't move.)
- Loading state: `Loading the engine…` (then, if over a few seconds on a phone: `Still loading. The first load takes longer on a phone.`)

### Hunch evidence (checked 2026-11-23)

| Item | Date in code | Verified | Source | Status |
|---|---|---|---|---|
| BMJ Global Health unsafe listening meta-analysis, about 24% of 12 to 34 year olds | 2022-11 | Nov 2022; pooled 23.81% | https://pubmed.ncbi.nlm.nih.gov/36379592/ | OK |
| WHO World Report on Hearing, about 2.5 billion by 2050 | 2021-03 | 2 Mar 2021 | https://www.who.int/news/item/02-03-2021-who-1-in-4-people-projected-to-have-hearing-problems-by-2050 | OK |
| FDA OTC hearing aid final rule | 2022-08-16 | Announced 16 Aug 2022 (Federal Register 17 Aug, effective 17 Oct) | https://www.govinfo.gov/content/pkg/FR-2022-08-17/html/2022-17230.htm | OK |
| FDA authorizes AirPods Pro hearing aid feature, first OTC hearing aid software | 2024-09-12 | 12 Sep 2024 | https://www.fda.gov/news-events/press-announcements/fda-authorizes-first-over-counter-hearing-aid-software | OK |
| JAMA Otolaryngology, NHANES 1988-2010 (Su and Chan) | 2017-09 | Issue Sep 2017 (online Jul 2017) | https://pmc.ncbi.nlm.nih.gov/articles/PMC5710291 | OK, wording nuance: "no overall change"; prevalence rose to 2007-08 then fell |
| LBNL data center report for DOE, 4.4% in 2023, 6.7% to 12% by 2028 | 2024-12 | Published 19 Dec 2024 | https://eta-publications.lbl.gov/publications/2024-lbnl-data-center-energy-usage-report | OK |
| IEA Energy and AI, about 945 TWh by 2030 | 2025-04 | 10 Apr 2025; IEA says "more than double" (Base Case) | https://www.iea.org/reports/energy-and-ai/executive-summary | OK |
| Constellation and Microsoft 20-year deal, Three Mile Island Unit 1 restart | 2024-09-20 | 20 Sep 2024 | https://www.constellationenergy.com/newsroom/2024/Constellation-to-Launch-Crane-Clean-Energy-Center-Restoring-Jobs-and-Carbon-Free-Power-to-The-Grid.html | OK |

Suggested wording fixes for the code owner (not applied here):
- `charlie/hunch.py` HEARING "added": "US teen hearing loss was not rising in NHANES surveys from 1988 to 2010" should read "US hearing loss in children and teens showed no overall change in NHANES surveys from 1988 to 2010". The evidence fact "did not rise across the NHANES surveys" should read "showed no overall change from 1988 to 2010", since it rose mid-period before falling.

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
