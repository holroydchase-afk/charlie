# SPEC: Agent eval fixes (intake #60, EF-CH-1 to EF-CH-7)

Staff PM, Nov 25. Before state: `main` at 51265e4. Master list: studio-agents `docs/eval-findings.md` (IDs EF-CH-n).
Every PR here changes `charlie/` or `web/`, so it ships in the demo build and **waits for Chase's go** (CLAUDE.md "Merging").

## The bet
A recruiter or a new investor opens the demo at 390px and, in one glance, sees ideas that obey the risk slider they picked, ranked the way the app says it ranks, about a person they know is fictional. The safety story ("Safe by default ... Every trade shows max loss in dollars"; "Familiarity raises a company's rank, never its position size", CLAUDE.md) has to be true on the first card, not just in the code comments.

Signal: the eval agents rerun at the fixing commit report EF-CH-1 to EF-CH-5 closed, with no new P0/P1.

## Reproduced at this tree (mock data, sample profile, level 2 Conservative, $25,000)
`daily_ideas` returns ABT 76 (cash-secured put, max loss $11,654, collateral $11,750), MRK 59 (cash-secured put, max loss $7,832), LULU 78 (shares, $2,340). Both EF-CH-1 and EF-CH-2 confirmed. ABT's why-chips read "your resume mentions Abbott (Abbott Laboratories)" and "in your Healthcare Services & Devices circle" (EF-CH-3, EF-CH-5 confirmed).

Causes in code:
- **EF-CH-1**: `charlie/strategies.py` `build()`. `max_risk_pct` (5%) caps only defined-risk spreads and long options. Cash-secured puts size by `max_collateral_pct` (50%), shares by a hard-coded 10% (5% at level 1). Max loss on a put is breakeven x 100, so up to ~50% of capital at "Conservative". Known since Oct 28 (HANDOFF "Decisions to review", "Oct 28 risk math"; DECISIONS.md open item "Risk math sizing"; AGENT-NOTES risk math checklist, "Sizing" bullet, exempts them "for now").
- **EF-CH-2**: `charlie/engine.py` `daily_ideas()` fills in two passes (options, then shares) with one idea per domain, and `rank` is the order filled. Search (`screen()`) sorts by score.
- **EF-CH-3**: `charlie/profile.py` `build_profile()` writes "your resume mentions ..." into `ticker_why` and domain evidence for every profile, including the demo's fictional sample (Alex Rivera, `charlie/demo.py`). `#profile-nudge` ("a fictional sample person") sits below `#ideas` (CHL-NAV-8 moved it there so card 1's numbers make the phone's first screen).
- **EF-CH-4**: `web/app.js` `runScreen()` row cards show `x.symbol` only; `x.name` is already in each row.
- **EF-CH-5**: `web/app.js` `ideaCard()`.

## Scope

### EF-CH-1 (P0): cash-tying trades follow the risk slider
**Sizing rule (product call, simplest reversible option; flagged for Chase below).** One new per-level number, `max_position_pct`, in `RISK_LEVELS`: level 1 5%, levels 2 to 5 10% (today's shares rule, so shares don't change). Shares and cash-secured puts size so the money tied up is at most `capital x max_position_pct`; that also caps their worst case (stock to $0). `max_risk_pct` still caps spreads and long options. Covered calls and collars write against shares the user already owns, so they stay sized by holdings and say so ("on shares you already own"). `max_collateral_pct` is removed or no longer used for puts.

Consequence, stated plainly: at $25,000 and 10%, a put ties up at most $2,500, so only strikes at or under $25 fit; in the 93-name mock universe that is one name (F, $13.89). Conservative demo ideas become mostly shares. See Decision 1.

- **CHL-EF1-1** (auto) Given capital C and level L in 1 to 5, when `build("cash_secured_put", ...)` returns a trade, then `capital_required` and `max_loss` are each at most C x `max_position_pct[L]`; contracts round down; a budget below one contract raises `Infeasible` with a reason naming the dollar collateral, the percent and the level label (e.g. "one put ties up $11,750, more than 10% of your $25,000 at Conservative"). Golden values worked by hand in a comment, in `tests/test_risk_math.py`.
- **CHL-EF1-2** (auto) Given the same, when `build("shares", ...)`, then `max_loss` = cost at most C x `max_position_pct[L]` (unchanged numbers at levels 1 and 2: a regression guard).
- **CHL-EF1-3** (auto) Given the sample profile at every level 1 to 5 on the pinned demo day, when `daily_ideas` runs, then every idea except covered calls and collars has `max_loss <= capital x max(max_position_pct, max_risk_pct)` for its level. Covered calls and collars carry `on_owned_shares: true`.
- **CHL-EF1-4** (auto) Every trade dict carries `capital` (the paper capital it was sized against) and `loss_pct_of_capital` (`max_loss / capital`, 4 dp, `None` when capital is 0). Edges: capital 0 or negative gives no trade and a clear reason, never NaN or inf.
- **CHL-EF1-5** (auto, e2e at 390) Given the demo's first idea card, then the Max loss metric reads "<money> · <n>% of your $25,000" (stated capital, from code), and the hero row still shows max loss, breakeven reachable in one tap, and the exit plan (hard rule).
- **CHL-EF1-6** (auto) Given any surface showing a chance of profit (idea card hero metric, trade block, ticker drawer, chat trade card, rule-based chat reply in `charlie/chat.py`, Search row card and table), then "estimate, not a promise" sits beside it, added by code. Server-side strings checked in pytest; web surfaces in e2e.
- **CHL-EF1-7** (auto) `prebuilt.json` rebuilt; the existing drift test passes. The AGENT-NOTES risk math checklist "Sizing" bullet is updated in the same PR to drop the shares and cash-secured put exemption (covered calls and collars stay exempt, sized by holdings).

### EF-CH-2 (P1): Today's ideas are in score order
Keep both passes and the one-per-domain rule (they decide *which* ideas); sort the chosen ideas by the same key as `ranked` (score plus the date jitter) and renumber `rank`.
- **CHL-EF2-1** (auto) Given the sample profile at levels 1 to 5, when `daily_ideas` runs, then the ideas' Charlie scores are non-increasing and `rank` is 1..n in that order.
- **CHL-EF2-2** (auto) Given the same inputs, the *set* of symbols chosen is the same as before the sort (the fix reorders, it doesn't change picks). Record the 51265e4 set in the test.

### EF-CH-3 (P1): no "your resume" for a visitor who gave none
- **CHL-EF3-1** (auto) Given `build_profile(..., owner="Alex")` (new optional argument, default `None` meaning "your"), then every evidence and why string says "Alex's resume mentions ..." and none says "your resume". The demo's `sample_profile` passes the sample's first name. A saved user profile is unchanged ("your resume mentions ...").
- **CHL-EF3-2** (auto, e2e at 390) Given a first visit to the demo (no saved profile), then a one-line "Sample: ideas for Alex Rivera, a fictional person" note sits **above** the first idea card, static mode only, and card 1's Max loss is still inside the first 844px screen after the disclaimer notice is dismissed. The fuller `#profile-nudge` line below the cards stays. The local app shows no sample note.
- **CHL-EF3-3** (auto) No resume text, and no real person's name, enters the strings; the sample stays fictional (`samples/` rule). privacy-security confirms.

### EF-CH-4 (P2): Search cards name the company
- **CHL-EF4-1** (auto, e2e at 390) Given Search results, then each row card shows "<SYMBOL> <Company name>" (name truncates with ellipsis, full name in the accessible name), and the table's Stock cell shows the name too.

### EF-CH-5 (P1): Today card reads at a glance
Copy goes through positioning; the visual pass through ux-reviewer at 390 and 1280. Max loss, breakeven, exit plan and the disclaimer stay visible (hard rules; hiding any is P0).
- **CHL-EF5-1** (auto) Every why-chip starts with a capital letter (generated in `profile.py`/`engine.py`, not CSS).
- **CHL-EF5-2** (auto) The industry is named once per card: when the card sub-line already names the domain, the "in your <domain> circle" chip is dropped; a card whose only reason was that chip shows "Inside your circle".
- **CHL-EF5-3** (auto, e2e) The rank reads as a label, not a stray number before the name: "Idea 1 of 3" (or a "#1" badge) with an accessible name; no "1 Abbott Laboratories" text run.
- **CHL-EF5-4** (auto, e2e) Above the fold the card shows: name line, at most two why-chips, one headline sentence (`_headline`, already one line), the three hero metrics, the exit plan line and one primary action, "Paper trade this", styled primary on every card (today only card 1 is tinted). Longer text stays inside "Plan, risks and order details".
- **CHL-EF5-5** (manual) ux-reviewer 390 and 1280, light and dark: score not below the 51265e4 before-score, no P0/P1.

### EF-CH-7 (P2 set, unconfirmed): confirm or close
ux-reviewer checks each of CHL-R5 to R25 at 390 on the current tree. Each is closed as not-a-bug with a screenshot, or gets its own CHL-EF7-n criterion and failing test before any fix. Quick fixes in this intake only: price and change run together ("$121.74–0.7%": add a separator and sign, CHL-EF7-1, auto), risk slider end labels (CHL-EF7-2, auto), double-outline button that looks like stuck focus (CHL-EF7-3, auto: no outline without `:focus-visible`). Jargon (Stalwart, Slow grower), "Details" and Level 1 "Learn" vs the Learn tab go to positioning in the EF-CH-5 PR. Anything about the first-open modal or the count of disclaimer copies is out of scope (EF-CH-6).

## Not doing
- **EF-CH-6 (first-run disclaimer dialog)**: already specced as CHL-DARK-11 to 13 (`docs/product/SPEC-DARK-LAYERS.md`, D5). Chase has paused that work. Out of scope; close the box on the intake with a pointer to D5. CHL-R items about the modal's copy or stacked disclaimers ride with it.
- A real stop-loss engine or position-sizing calculator. The cap above is the loss limit.
- Changing the scoring or the diversity rule.

## PRs, in order (each waits for Chase's go)
1. **PR A, EF-CH-1 (P0)**: CHL-EF1-1 to 7. qa-tdd red in `tests/test_risk_math.py` and e2e, engineer builds, qa-tdd 3x, ux-reviewer (card copy), privacy-security not needed. About 2 sessions.
2. **PR B, EF-CH-2 + EF-CH-3 + EF-CH-4 (P1/P2, small engine and copy)**: CHL-EF2, EF3, EF4. privacy-security on EF3. About 1 session.
3. **PR C, EF-CH-5 + EF-CH-7 confirms**: CHL-EF5, EF7. positioning, ux-reviewer before and after. About 1 to 2 sessions.

Evidence per item: the red test at 51265e4 (or a 390px screenshot for manual ones) and green at the fixing commit, in the PR body. Tick each EF-CH box on intake #60 with the PR link.

## Decisions for Chase
1. **Sizing rule for cash-tying trades.** Recommend A: shares and cash-secured puts tie up at most 10% of paper capital (5% at Learn), one number per level, reversible in one line. Cost: at the demo's $25,000, Conservative shows almost no puts. B: same cap and raise the sample capital to $100,000 so $100 strikes fit (changes the sample person). C: keep 50% collateral and only state it (doesn't fix the P0).
2. **Covered calls and collars stay sized by shares you already own**, labeled as such. Recommend yes.

## PLAN items to add
- `CHL-M1.19 Eval fixes (intake #60)`, doing. PR A EF-CH-1 sizing (P0), PR B EF-CH-2/3/4, PR C EF-CH-5/7. Spec `docs/product/SPEC-EVAL-FIXES.md`. Each waits for Chase's go (demo change).
- `CHL-M1.19.1` todo: Chase picks the sizing rule (Decision 1); closes HANDOFF "Oct 28 risk math" and DECISIONS "Risk math sizing" when built.
- `CHL-M1.19.2` todo: EF-CH-6 parked with CHL-DARK-11 to 13 (paused by Chase).
