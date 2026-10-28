# Charlie UI: round 2 score for M1.11 (ux-reviewer, showcase mode)

Date: 2026-10-28. Build: `d267f22` (M1.11 round 2), static demo built in a throwaway worktree (`tools/build_demo.py --pyodide-dir <pyodide package>`), served on 127.0.0.1:8834. Server stopped and worktree removed afterwards.
Screenshots: not committed (they lived in the reviewer's session scratch space). File names below are kept for reference (`m-` = 390x844, `d-` = 1280x800, `m320-` = 320x700, `-light` / `-dark`, `-full` = full page). Raw measurements were not committed.
Bar: 8 = a staff-level PM would be comfortable showing it to a hiring manager.

## Verdict: Ready to show (overall 8/10). Fix UX27 first (a 1-line grammar bug)

- **Recruiter, phone, 90 s:** gets what it is in 3 s. Each card now gives a real reason with a number ("Abbott Laboratories earns 12% on the capital it invests. You'd only lose money below $124.17, about 6% down."). The one gap: no idea number shows in the first phone screen (card 1's metrics start at y=1045 of 844).
- **Hiring manager, laptop, 5 min:** card 1's three numbers are on screen at load (y 656-736 of 800). The thesis, chart and screener now read like a product. The "What is a buy shares?" heading is the one thing that looks careless.
- **Least tech-savvy user:** drawer tiles are plain words now. Jargon is left only one layer down: the checklist detail lines, "Expected move (±1σ)", and "~0.20 delta" on Learn.

Measured clean in all 4 combos (390/1280 × light/dark): 0 console errors, 0 failed requests, no horizontal scroll at 390 or 1280. Ack modal focuses its button. The drawer is `role=dialog aria-modal=true`, focus goes to a 44×44 close button and returns to the grade badge on Escape. SVG text is 12.0px on screen.

## Scores

| Dimension | Before | Round 1 | Now | Why (now) |
|---|---|---|---|---|
| Visual hierarchy | 4 | 7 | **8** | The thesis line says something new, there's no "—" in any hero tile (LULU shows "Money tied up $2,457"), and the 2-column desktop hero puts card 1's numbers in the first view. |
| Spacing / type consistency | 5 | 7 | **8** | Computed text sizes are exactly {12, 14, 16, 20, 28} on every screen (measured). Cards are 673px tall on desktop and 689-768px on phone. Left over: the orphan "Win rate —" tile on phone, and disabled chips wrapping oddly in Edit filters. |
| Empty / loading / error states | 5 | 7 | **8** | Paper empty state has no zero tiles above it and its button sits at y≈518. The phone screener shows results first (first card at y=452). |
| Mobile | 4 | 7 | **8** | All 6 tabs fit (right edge 383 of 390), the banner is one 30px line, and the screener form folds into a summary row with "Edit filters". Still fails reflow at 320px (scrollWidth 338). |
| Accessibility basics | 6 | 8 | **8** | Same strong base, and out-of-level strategy chips are now really `disabled` and say "(needs level 3)". Against: 320px reflow, and banner targets of 33×17 (Reset) and 15px tall (Back link). |
| Copy clarity | 5 | 7 | **8** | Engine-built reason plus breakeven on each card, "Close trade", plain drawer tiles, "Shown for ABT between $92 and $172 at expiry." Against: "What is a buy shares?", jargon in the detail lines, and a paper Entry of "-$83" for a credit. |
| First 90 s (recruiter) | 4 | 7 | **7 phone / 8 laptop** | Laptop: hero plus card 1's numbers with no scrolling. Phone: hero plus card 1's title only. |
| **Overall** | **5** | **7** | **8** | Showable now. What's left is polish, not structure. |

## UX16-UX26 status

| ID | Status | Evidence |
|---|---|---|
| UX16 thesis line | **Fixed** | All 3 `.thesis` lines give a reason with its number plus the loss point. None contains "Charlie score". (`m-light-01-today-full.png`) |
| UX17 "—" in hero | **Fixed** | Hero tiles: "Money tied up $2,457" on LULU. Phone screener cards show "Money tied up" for shares. The desktop table still has "—" in Chance / Yearly / Expires for shares (fine in a table, see UX36). |
| UX18 chart labels | **Fixed** | Signed P&L labels in a left gutter ("$0", "−$3,174", "+$737"), prices under the axis, and a caption giving the range. The ABT "+$83" top label is dropped because it would sit within 15px of $0, which is acceptable. The −$3,174 vs $12,417 max-loss gap is now explained by the range caption. |
| UX19 phone screener | **Fixed** | First result card top is y=452 at 390x844. Allowed types are ticked by default and levels 3-5 are disabled with "(needs level N)". The "Searched:" line now matches the ticks. |
| UX20 above the fold | **Fixed (laptop)** | Card 1's metrics at y 656-736 at 1280x800. On phone they're still below the fold (new UX28). |
| UX21 clipped tab | **Fixed** | "Portfolio", and the rightmost tab ends at 383px. |
| UX22 drawer jargon | **Partly** | Tiles fixed ("Return on capital", "Free-cash yield", "Price to earnings", "Expected price swings (IV)"). The checklist detail lines right above them still say "return on invested capital", "debt/equity 0.3", "free-cash-flow yield 5% vs ~4.2% Treasuries" (see UX32). |
| UX23 paper portfolio | **Partly** | Empty state fixed, and "Close trade" has a full aria-label. With a position open, the phone grid still leaves "Win rate (closed) —" as a full-width orphan tile (`m-light-22-paper-filled-full.png`). |
| UX24 type scale | **Fixed** | Font-size set = {12, 14, 16, 20, 28} on Today, desktop and phone. |
| UX25 sample link + banner | **Fixed** | "Paste a resume · or use the sample" on one row. Phone banner is one 30px line. |
| UX26 screener rows | **Fixed** | Sector ellipsis, nowrap Expires, price merged into Stock. Rows are about 63px. |

Score: 9 fixed, 2 partly, 0 not fixed.

## Remaining findings (ranked)

| ID | Pri | Screen | Problem | Fix (exact) |
|---|---|---|---|---|
| CHL-UX27 | **P1** | Card details and drawer explainer (`app.js:166`) | "What is a buy shares?" (and "What is a leaps call (stock replacement)?") is broken English in a showcase. A hiring manager will notice it. Nielsen #4 consistency. | Put a per-strategy heading on the strategy meta in Python, for example `explainer_title`: "How buying shares works", "What is a cash-secured put?", "What is a covered call?", "What is a LEAPS call?". Never lower-case the label. Acceptance: no summary/h3 text matches `/What is a buy/` and none contains "leaps". |
| CHL-UX28 | P2 | Today, phone first viewport | No idea number is visible on a phone at load. Card 1's first metric top is 1045 (viewport 844), so only "Abbott Laboratories" peeks out. | Under 600px: put the 3 proof chips on one wrapping line at 12px, or drop them (the H1 and sentence carry it), and cut hero padding to 16px. Or add a hero line: "Top idea today: **ABT** · 84% chance of profit · max loss $12,417 ›" that scrolls to card 1. Acceptance: at 390x844, card 1's first `.metric` bottom ≤ 844, or a `.hero-top-idea` link is visible. |
| CHL-UX29 | P2 | All tabs at 320px | Horizontal page scroll at 320: scrollWidth 338. "Copy order details" (right edge 338) and the risk pill (324) overflow. WCAG 1.4.10 Reflow. | `.trade-actions { flex-wrap: wrap }` with buttons at `flex: 1 1 auto; min-width: 0`, and let the risk control wrap. Acceptance: at 320x700 `scrollWidth ≤ 320` on every tab. |
| CHL-UX30 | P2 | Paper portfolio with a position | Entry "-$83" and Now "-$83" use a hyphen and a negative sign for a credit received, which a beginner reads as a loss. "Win rate (closed) —" is an orphan full-width tile on phone. | Columns "You received $83" / "Cost to close $83" (or "Credit $83"), with a real minus (−) wherever a sign stays. Hide the win-rate tile until at least 1 trade is closed, which also fixes the orphan. |
| CHL-UX31 | P2 | Demo banner, phone | "Reset" is 33×17 and "Back to chaseholroyd.com" is 15px tall. WCAG 2.5.8 asks for 24px targets. | `padding-block: 4px` and `min-height: 24px; display: inline-flex; align-items: center` on both. Acceptance: both ≥ 24px tall. |
| CHL-UX32 | P2 | Drawer and card checklist lines, card "More numbers", Learn | Jargon one layer down: "return on invested capital", "debt/equity 0.3", "free-cash-flow yield 5% vs ~4.2% Treasuries", "Expected move (±1σ)", "~0.20 delta". | In the Python factor reasons: "earns 12% on the money it invests", "debt is 0.3× what owners put in", "free cash is 5% of the price a year (Treasuries pay ~4.2%)". Tile: "Typical move by expiry". Learn: "…cash-secured puts about 20% likely to be assigned, 30-50 days out." |
| CHL-UX33 | P2 | Opened card, "Why this one" | The first bullet repeats the thesis line word for word, right below it. | Leave the headline out of the bullet list when it's the card's thesis (start the list at Competence). |
| CHL-UX34 | P2 | Grade badge, phone | "76/100 · A" with the noun hidden on phone. A number with no label. | Phone: "Score 76 · A" (keep the full aria-label). |
| CHL-UX35 | P2 | Screener "Edit filters", phone | 5 disabled chips take 5 rows, and "LEAPS call (stock replacement) (needs level 4)" wraps into 2 columns. | Show only the allowed chips, plus one line: "5 more trade types unlock at higher risk levels. Move the risk slider to see them." |
| CHL-UX36 | P2 | Screener, desktop | The results start at y=747 under the form, and 14 of 16 rows show "— — —". | Optional: fold the form after the first run on desktop too, or keep it open. Show "Shares" in the Expires cell for share rows. |

## The 3-5 fixes for a solid 8+

It's at 8 now. To lock it in for showing (the top three are under an hour total):
1. **UX27** "What is a buy shares?" → per-strategy heading (P1, the only careless-looking thing left).
2. **UX28** an idea number in the phone's first screen (the recruiter persona).
3. **UX30** paper credit shown as "You received $83", and hide win rate until there's a closed trade.
4. **UX29 + UX31** 320px reflow and 24px banner targets (a clean WCAG story).
5. **UX32** plain words in the checklist detail lines.

## Evidence

- `m-light-01-today-full.png`, `d-light-01-today.png`: thesis lines, hero tiles, card 1 numbers above the fold on desktop.
- `m-light-04-screener.png`, `d-light-04-screener.png`: folded phone screener, disabled chips with "(needs level N)".
- `d-light-24-screener-drawer.png`, `m-light-24-screener-drawer.png`: "What is a buy shares?" (UX27).
- `m-light-22-paper-filled-full.png`, `d-dark-22-paper-filled-full.png`: orphan win-rate tile, "-$83" entry (UX30).
- `m-light-26-screener-edit.png`: disabled chip wrap (UX35).
- Measured: console errors, failed requests, horizontal scroll at 390/1280/320, tab right edges, banner height, element boxes, computed font-size histogram, SVG text px, first-metric and first-result positions, chip disabled state, focus targets, drawer role, close size, banner target sizes.
- Inferred: recruiter and hiring-manager reactions (confirm with a real user).
- Not covered: the error state was not forced (code-verified in round 1). The mobile engine pass's screener wait timed out on an old selector (`.rcard`). The screens were still captured, and the phone row-card flow was re-run separately and is fine.

## Acceptance criteria for qa-tdd

- CHL-UX27: no `summary`/`h3` in any trade block matches `/What is a buy/i` or contains "leaps" in lowercase.
- CHL-UX28: at 390x844 after ack, card 1's first `.metric` bottom ≤ 844 (or a visible hero top-idea link).
- CHL-UX29: at 320x700, `documentElement.scrollWidth ≤ 320` on Today, Screener, Portfolio, Profile.
- CHL-UX30: a position's entry cell for a credit trade doesn't start with "-"; the win-rate tile is absent while closed count is 0.
- CHL-UX31: `#reset-demo` and `.demo-actions a` heights ≥ 24px at 390.
- CHL-UX33: an opened card's "Why this one" list doesn't contain the `.thesis` text.

## For Chase

1. Nothing needs you. The UI is at 8/10 (5 → 7 → 8) and fine to show.
2. Fix UX27 first ("What is a buy shares?"). It's tiny but it's the one thing that looks careless.
3. UX28 (a number in the phone's first screen) is the best next lift for recruiters on phones.
