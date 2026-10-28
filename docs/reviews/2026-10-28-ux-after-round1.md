# Charlie UI: AFTER score for M1.11 (ux-reviewer, showcase mode)

Date: 2026-10-28. Build: branch `claude/project-thread-hpanpa-ui` @ 5e3e5e5, static demo built to a scratch folder (`tools/build_demo.py --pyodide-dir`), served on 127.0.0.1:8824. The local app was run briefly too (uvicorn on 8823, mock data, LLM off, scratch DB). Both servers are stopped.
Screenshots: not committed (they lived in the reviewer's session scratch space). File names below are kept for reference (`m-`=390x844, `d-`=1280x800, `-light`/`-dark`, `-full`=full page, `local-`=FastAPI app).
Bar: Linear / Stripe-dashboard polish. Target 8/10.

## Verdict: Needs changes (no blockers). Overall 7/10, up from 5

- **Recruiter, phone, 90 s:** now gets it in 3 s: "Stock ideas from what you already know", one sentence and 3 proof chips. But the first screen shows no idea or number yet. Only the first card's title peeks at the bottom.
- **Hiring manager, laptop, 5 min:** the cards now have a clear focal row (chance / max profit / max loss), the details fold away, and the drawer behaves like a real dialog. What still reads as "engine output": the card's one-line thesis just repeats the score badge, buy-share ideas show a "—" in the hero row, and the payoff chart's axis labels are ambiguous.
- **Least tech-savvy user:** the modal and subtitle are plain now. The drawer still says ROIC / FCF yield / ATM IV, and the screener lists level 3-5 strategies as if they could be ticked.

Measured clean in all 4 combos (390/1280 × light/dark): no console errors, no failed requests, no horizontal scroll.

## Scores

| Dimension | Before | After | Why |
|---|---|---|---|
| Visual hierarchy | 4 | 7 | Hero row of 3 with 20px numbers; max loss in ink with a "only if ABT fell to $0" helper; the details fold away. Held back by the tautological thesis line, the "—" hero tile on share ideas, and a hero card that pushes every idea below the fold. |
| Spacing / type consistency | 5 | 7 | Tokens for type and spacing, 16px body, cards are 651px (desktop) and 692-767px (phone). Still 9 computed sizes in use (12/13/14/15/16/17/18/20/26-28; 13px on ~40 nodes is off the scale), an orphan "Win rate" tile, and the right half of the desktop hero is empty. |
| Empty / loading / error states | 5 | 7 | Skeleton cards, a typing indicator, Try again buttons (checked in code), a real paper empty state with a "See today's ideas" button, and the screener runs on its own. Five $0 tiles sit above the paper empty state, and on a phone the screener's results start ~1,050px down. |
| Mobile | 4 | 7 | Chat form bottom 701 vs footer top 804 (UX1 fixed). One-line 40px footer with no overflow. Sticky chrome cut from 291px to 89px (header 49 + footer 40; the banner scrolls away). Cards instead of tables. Still: the 6th tab is clipped ("Paper portfo"), the screener form comes before the results, and the banner is 2 lines. |
| Accessibility basics | 6 | 8 | Drawer has `role=dialog`, `aria-modal`, focus moves to a 44×44 close button and goes back to the opener on Escape; the ack modal focuses its button; `:focus-visible` uses the accent color (seen in `d-light-12-focus.png`); SVG chart text is 12px on screen. Still lots of 12-13px text, and the out-of-level strategy checkboxes aren't disabled. |
| Copy clarity | 5 | 7 | Modal "Practice only, no real money" with 3 bullets; plain subtitle; "Order details (for paper practice)"; "Charlie score 76/100 · A / Details". Still: the thesis line says nothing new, drawer metric jargon, "Close" on a paper position is unclear, and the chart axes are ambiguous. |
| First 90 s (recruiter) | 4 | 7 | Hero answers what / for whom / how, and "fictional sample person" is honest. No idea number is visible in the first viewport (desktop: metrics start at about 745 of 800px; phone: only the title of card 1). |
| **Overall** | **5** | **7** | A real step up. It now reads as a product, not an internal tool. Fixing UX16-UX19 is the path to 8. |

## UX1-UX15 status

| ID | Status | Evidence |
|---|---|---|
| UX1 chat input under footer | **Fixed** | 390: `#chat-form` bottom 701, footer top 804; 1280: 678 vs 760 (`m-light-09-chat-reply.png`). |
| UX2 no hero | **Fixed** | `m-light-01-today.png`: H1 + sentence + 3 chips + "fictional sample person" in the first viewport. |
| UX3 card focal point | **Fixed** | 3 hero metrics, max loss in ink with helper. (The "—" tile on share ideas is new finding UX17.) |
| UX4 card length | **Fixed** | Collapsed: 767 / 692 / 726px at 390 (acceptance ≤800 met; 2 of 3 miss the 700 design target), 651px at 1280. NFA stays outside the details. |
| UX5 chart labels | **Fixed** (size) | SVG text 12.0px on screen at 390 (measured); legend "Today $132.05 · Breakeven $124.17" above the chart. Axis ambiguity is new finding UX18. |
| UX6 mobile chrome | **Fixed** | Header 49px on one row, banner not sticky, risk control aligned. Banner is still 2 lines (53px), asked for 1 (see UX25). |
| UX7 footer leak | **Fixed** | Footer 40px, scrollHeight − clientHeight = 0, "Read more" opens the full text. |
| UX8 subtitle + modal copy | **Fixed** | `m-light-00-ack.png`, `m-light-11-readmore.png`. |
| UX9 screener | **Partly** | Runs on its own, 3 filters up front + "More filters", checkbox chips, "Find trades" on one line, phone cards. But on a phone the results start ~1,050px down below 8 chip rows; level 3-5 chips look tickable at Conservative; "none ticked" quietly means "all allowed"; desktop rows wrap to 83px. |
| UX10 paper portfolio | **Fixed** | Tiles on panels, empty state with "See today's ideas", position cards on a phone. Leftovers in UX23. |
| UX11 drawer | **Fixed** | role/aria-modal, focus on close (44×44), focus back to the badge on Escape, "Sample data, not real market prices", sticky header. |
| UX12 type/spacing system | **Partly** | Tokens exist and body is 16px, but the computed sizes still include 13, 15, 17, 18 and 26px outside the scale. |
| UX13 grade badge | **Fixed** | "Charlie score 76/100 · A / Details ›" with a full aria-label. |
| UX14 loading/error | **Fixed** (code-verified) | Skeletons, typing dots, plain errors with Try again (app.js 221-231, 453-464, 598). Error state not screenshotted. |
| UX15 focus/interactive | **Fixed** | Accent `:focus-visible` ring seen on "Reset demo" in `d-light-12-focus.png`. |

Score: 12 fixed, 2 partly (UX9, UX12), 0 not fixed.

## Remaining findings (ranked by score impact)

| ID | Pri | Screen | Problem | Fix |
|---|---|---|---|---|
| CHL-UX16 | P1 | Today card thesis | "Abbott Laboratories is a stalwart with a Charlie score of 76 (A)." repeats the badge and gives no reason. It's the one sentence a recruiter reads. | Make the line the strongest reason plus the risk, built in Python (`charlie/` thesis, one engine): "Earns 12% on its capital with little debt. You'd only lose money below $124.17, about 6% down." Acceptance: `.thesis` text doesn't contain "Charlie score". |
| CHL-UX17 | P1 | Hero metrics on share ideas; screener cards | "Chance of profit —" fills a third of the hero row on every Buy shares idea (LULU on Today, 14 of 16 screener cards). | For trades without a `pop`, swap the tile for "Money tied up $2,457". In screener cards, show "Money tied up" for shares. Acceptance: no hero `.metric` value is "—". |
| CHL-UX18 | P1 | Payoff chart | "−$3,174" (P&L) sits right above "$172" (price) in the same corner, and the chart's worst point (−$3,174) doesn't match the headline max loss of $12,417, with no explanation. | P&L labels on the left with signs ("+$83", "−$3,174", plus a "$0" baseline label). Price labels under the x-axis: "ABT at $92" … "$172". Caption at 12px: "Shown for ABT between $92 and $172." Acceptance: no P&L label and price label share an x and are within 20px vertically. |
| CHL-UX19 | P1 | Screener, phone + all | Results start ~1,050px down, below the form. Level 3-5 chips look tickable at Conservative. With nothing ticked it says "Searched: Buy shares, Cash-secured put, Covered call". | Under 600px, after the first run collapse the form to a summary row "My circle · score 50+ · 3 trade types · **Edit filters**" with results first. Tick the allowed types by default. Show higher-level types as disabled with "(needs level 3)". Acceptance: at 390x844, the first result card's top is under 844px after it runs on its own. |
| CHL-UX20 | P2 | Today, first viewport | No idea number is visible above the fold (desktop: first metrics at y≈745/800; phone: only card 1's title). The right half of the desktop hero is empty. | Desktop: a 2-column hero with the copy on the left and a "Top idea today: ABT · 84% chance · max loss shown" preview on the right that scrolls to card 1. Or move the risk control into the "Today's ideas" header row and trim the hero padding to 24px. Acceptance: at 1280x800, card 1's hero metrics are fully in the viewport. |
| CHL-UX21 | P2 | Tabs, 390px | The 6th tab is clipped ("Paper portfo") with no clear scroll cue. | Rename the tab to "Portfolio" (page H1 stays "Paper portfolio") so all six fit at 390, or add a right-edge fade with scroll-snap. Acceptance: every `[role=tab]` is fully within 0-390px. |
| CHL-UX22 | P2 | Drawer metric tiles | Jargon: ROIC, Op. margin, FCF yield, Debt/Equity, ATM IV. | Use "Return on capital", "Operating margin", "Free-cash yield", "Debt to equity", "Expected price swings (IV)", the same words as the checklist rows. |
| CHL-UX23 | P2 | Paper portfolio | The empty state has 5 zero tiles above it, so the CTA sits at y≈795 near the footer (`m-dark-06-paper.png`). The "Win rate" tile is an orphan. The "Close" button on a position is ambiguous. | Hide the stats while there are 0 positions. Use a 3+2 or 2+2+full-width grid. Rename the button "Close trade" with aria-label "Close paper trade ABT cash-secured put". |
| CHL-UX24 | P2 | Global type | Computed sizes 13px (~40 nodes), 15, 17, 18 and 26px fall outside the token scale. | Map 13 → 14 (or 12), 15 → 16, 17/18 → 16 or 20, 26 → 28. Acceptance: computed text sizes ⊂ {12, 14, 16, 20, 28}. |
| CHL-UX25 | P2 | Static profile + banner | "Use the sample resume" sits above the "Paste a resume" label and reads like a heading. The phone banner is 2 lines (53px). | Label row: "Paste a resume · *or use the sample*" (link on the right, 14px). Banner at <600px: "Sample data · Back to chaseholroyd.com · Reset" on one 13px line. |
| CHL-UX26 | P2 | Screener table, desktop | Sector names wrap, so rows are 83px, and "2026-12-04" wraps. | Sector on one line with ellipsis and a `title`; `white-space:nowrap` on Expires; drop the Price column or merge it into Stock. |

The order that most raises the score: UX16 + UX17 (the card reads smart), UX18 (the chart can be trusted), UX19 (the screener works on a phone), then UX20 for the first 90 seconds. Those four or five should reach an honest 8.

## Evidence

- Measured: element boxes (header/banner/tabs/footer/chat form/cards), footer overflow, SVG text px on screen, focus target after the drawer opens and after Escape, drawer role/aria, close button size, computed font-size histogram, console errors, failed requests, horizontal scroll. Raw output is in the reviewer's scratch log (not committed).
- Inferred: how a recruiter feels about the hero and thesis (confirm with a real user), and the error-state look (code only).
- Full-page and element screenshots show the sticky header and footer drawn mid-page. That's a Playwright artifact, not a bug.
- Local app (`local-m-light-*.png`): same hero with "Showing a starter circle. Add your resume", "Demo data" badge, file upload on Profile. No new issues seen. Only the mobile-light set was captured, because the static-only sample button stopped the script.

## Acceptance criteria for qa-tdd

- CHL-UX16: every `.thesis` on Today doesn't contain "Charlie score".
- CHL-UX17: no hero `.metric` value on Today equals "—".
- CHL-UX18: in each `.payoff`, no two labels overlap or sit within 20px vertically at the same edge; a "$0" label exists.
- CHL-UX19: at 390x844, after the screener runs on its own, the first result's top is under 844; chips for strategies above the current level are `disabled`.
- CHL-UX20: at 1280x800, card 1's three hero metrics are fully within the viewport.
- CHL-UX21: at 390, every tab button's right edge is ≤ 390.
- CHL-UX24: the set of computed text font sizes ⊂ {12, 14, 16, 20, 28}.

## For Chase

1. Nothing needs you. The UI went from 5 to 7. All 15 findings were addressed: 12 fixed, 2 partly, none skipped.
2. 8 needs four more fixes: a real one-line reason on each card, no "—" in the top numbers, clear chart labels, and results first on the phone screener.
3. UX16 changes engine text (Python), so it goes through qa-tdd like any other fix.
