# Dark-mode layering: ux-reviewer pass (CHL-DARK-10, intake #55)

Date: 2026-11-23. Spec: `docs/product/SPEC-DARK-LAYERS.md` (CHL-M1.16). Change under review: `git diff origin/main -- web/` (`web/themes.css` adds `--raised` and `--control-edge`; `web/styles.css` moves cards, panels, the dialog and the drawer to `--raised` and every `--tab-line` edge to `--control-edge`).
Build: static demo, `tools/build_demo.py --date 2026-11-23 --pyodide-dir ...`, before = `origin/main` (scratch worktree), after = this branch's working tree. Only `themes.css` and `styles.css` differ between the two builds.
Tier: Advisory (report only; nothing filed or fixed).

Hard rules checked: dark layers (card, panel, dialog and drawer fill against the page and the scrimmed page, measured) and control contrast (every visible input, select, textarea, `.choice` and `.chip-check` edge against the first opaque background outside it, measured), in light, dark and HC dark at 390 and 1280. "Not financial advice. Paper trading only." is still visible on the idea card, the drawer header and the disclaimer line in every after shot, and "Sample data" stays in the demo bar. The change is CSS only, so paper-only, safe-by-default and the static-demo rules are untouched. `scripts/ux-refs.mjs` does not exist in this repo (only `ux-rules.mjs` and `ux-shots.mjs`), so `ux-refs.mjs cite` was not run. Its references (D5, DARK-5, CONTRAST-2) live in studio-agents and couldn't be read here. Syncing the script is a studio-agents item. `scripts/check-ux-run.mjs` and `check-findings.mjs` are also missing, so the blocks below were checked by eye.

## Verdict: Needs changes. Visual score 7/10 (bar 8)

- **Recruiter, phone, dark, 90 s:** the main thing works. The idea card now reads as a card on the page (1.15:1, was 1.08:1), and the first-open dialog reads as a sheet above the dimmed page (1.24:1 on the scrimmed page, was 1.16:1). Nothing new to stumble on.
- **Hiring manager, laptop, dark, 5 min:** opens the drawer and sees the Munger checklist bars with no track. A 65 bar and a 55 bar float with nothing to measure them against (CHL-UX-DK1). That is the one regression this change introduces.
- **New investor (least tech-savvy), phone, dark:** every field and choice edge is 3.02:1 or more on what's around it. The worst is the Profile inputs on the raised panel, which pass. The Search and Profile forms are easy to scan.
- **Light mode:** unchanged except the two expected changes. The risk control's outline is now the `--tab-line` grey, and the drawer body is white like its header. Pixel diffs confirm nothing else moved: Profile is identical, and Today and Search differ only inside the risk-control box.
- **HC dark:** unchanged by design (QA-R2): `--raised` = `--surface`, and the layers come from the 4.60:1 `--line` border. Only the drawer body moved, from `--bg` to `--surface`.

Score evidence (above 5): one rule-derived elevation token used for every floating surface (`.card`, `.panel`, `.modal-inner`, `.drawer-inner`, `.drawer-head`). Control edges come from one derived token that holds 3:1 in all four modes, measured. Light mode is byte for byte the same apart from the two planned changes. It isn't 8 because the step exposed the `--fill` tones that now sit on `--raised` at 1.02:1 (DK1, DK2), and two "card on page" surfaces were left on the old elevation (DK3, DK4).

## The critic's line

Hiring manager who has seen a hundred AI demos, opening the drawer in dark: "Nice, the cards finally lift off the page. Shame the score bars lost their rails. Is 65 out of 100 or out of nothing?"

## Measured (computed styles in Chromium, contrast per WCAG)

| Pair | Mode | Before | After |
|---|---|---|---|
| `.card` fill on page | dark 390/1280 | 1.08 | **1.15** |
| `.panel` fill on page | dark | 1.08 | **1.15** |
| `.modal-inner` on page / on scrimmed page | dark | 1.08 / 1.16 | **1.15 / 1.24** |
| `.drawer-inner` on page / on scrimmed page | dark | 1.00 / 1.07 | **1.15 / 1.24** |
| `.drawer-inner` on scrimmed page | light | 2.82 | 3.03 (white body) |
| `.risk-control` fill on page | dark | 1.08 | 1.08 (still `--surface`) |
| `.risk-control` outline on its fill | light / dark | 1.34 / 1.23 | 3.26 / 3.22 |
| Card border `--line` on card fill | dark | 1.23 | 1.15 |
| Worst control edge on what's outside it | light / dark / HC dark | 3.04 / 3.04 / 4.60 | 3.04 / 3.02 / 4.60 |
| `.bar` track `--fill` on its background | dark drawer / dark profile | 1.18 / 1.09 | **1.02 / 1.02** |
| `.btn-secondary`, `span.chip` `--fill` on a card or panel | dark | 1.09 | **1.02** |

Measured: every row above (Playwright computed styles, plus token math for the last two rows, confirmed in the shots). Inferred: `.table-wrap`, `.row-card` and `.pos-card` stay on `--surface` (from the CSS; the Trades tab wasn't shot). `node scripts/ux-rules.mjs` gives the same 6 failures before and after (G3 on `#ack`, which is the known D1/D5 item, and two V9 card-in-card hits). The change adds no new failure.

## Changes

| ID | Pri | Rule | Screen and region | Problem | What the person would do | Fix |
|---|---|---|---|---|---|---|
| CHL-UX-DK1 | P1 | V7 / W5 (1.4.11 graphical objects), regression | Drawer "Munger checklist" bars; Profile circle bars (dark, 390 and 1280) | `.bar` paints `--fill` #24221E, which is now on `--raised` #22201D at 1.02:1, so the track is gone. It was 1.18:1 on the drawer's old `--bg`. Each bar reads as a bare line with no 0 to 100 scale. | Compares bar lengths across rows without knowing they're out of 100. The harsh critic notices the bars "float". | `.bar { background: var(--line); }`: 1.15:1 on `--raised` in dark, the same step as the card itself. In light it's #E3DED4 on white (1.34:1, was 1.18:1), slightly firmer. Re-shoot the light drawer. No new token. |
| CHL-UX-DK2 | P2 | V6 / V7 | Today card "Score 76 · A / Details" button and "Copy trade details"; Profile `span.chip` tags; Search and Profile input fills (dark) | `--fill` tones (`.btn-secondary`, `.chip`, input background) were 1.09:1 on `--surface`. On `--raised` they're 1.02:1, so the button's shape and the chips' pills vanish. The labels and the 3:1 input edges still carry them, so this isn't a WCAG fail. | Finds the score button by its words and chevron. The button just looks less like a button. | Preferred: on cards and panels use `--line` for these fills too (`.card .btn-secondary, .panel .chip { background: var(--line); }`), 1.15:1 in dark, and check light. Alternative: accept it for this PR and suggest hearth adds a `raised-fill` alongside `raised` upstream. Staff-pm call. |
| CHL-UX-DK3 | P2 | V1 / V5 | Risk control bar, Today and Search (all modes) | The pill still paints `--surface` (1.08:1) while the card under it paints `--raised` (1.15:1): two elevations for neighbouring containers. Its new 3:1 outline is also now the strongest container edge on the screen, louder than the idea card's border in both modes (light #928E87 against cards' #E3DED4), so the toolbar competes with the answer. | Eye lands on the risk box before the first idea. | `.risk-control { background: var(--raised); }`. And staff-pm: consider amending CHL-DARK-7 so the pill keeps `--line`. WCAG 1.4.11 applies to the slider's track and thumb (accent, already 3:1 or more), not the pill around it. |
| CHL-UX-DK4 | P2 | V5 | Search results `.table-wrap` and phone `.row-card`; Trades `.pos-card` (dark, inferred from CSS) | Same "card on the page" role, but they still paint `--surface` (1.08:1) while idea cards and panels paint `--raised` (1.15:1). | Barely visible step difference between Today cards and Search and Trades cards. | Move `.table-wrap`, `table`, `.row-card` and `.pos-card` backgrounds to `var(--raised)`. Light and HC are unaffected, since `--raised` = `--surface` there. |

## Cut list (C5)

- Nothing to cut: this change is two tokens and a set of CSS swaps that add no element, word or size, so the above-the-fold group and type counts are the same as on main. One optional subtraction: the risk control's new outline (DK3). Recommend going back to `--line` there, which buys a calmer Today with the first idea as the focal point.

## Evidence

Folder: `/mnt/project-files/charlie-dark-layers-2026-11-23/`. Each shot is named `<screen>-<width>-<mode>-<before|after>.png` (screens: `first-open-dialog`, `today`, `today-full`, `drawer`, `profile`, `profile-full`, `screener`, `screener-full`; modes: light, dark and dark-hc at 390). Side-by-side pairs (before left, after right) are in `pairs/`, and the raw computed colors are in `measure.json`.
- Cards and dialog step off the page: `pairs/today-390-dark-pair.png` and `pairs/first-open-dialog-390-dark-pair.png` (verified).
- DK1 bar tracks gone: `pairs/drawer-390-dark-pair.png` (Quality 65 and Moat 55 rows), `pairs/drawer-1280-dark-pair.png` and `pairs/profile-1280-dark-pair.png` (Healthcare and Software bars).
- DK2: `pairs/today-390-dark-pair.png` (the "Score 76 · A" button, top right of the card) and `pairs/profile-1280-dark-pair.png` (the "resume mentions" chips).
- DK3: `pairs/today-1280-light-pair.png` and `pairs/screener-390-dark-pair.png` (the risk box outline).
- Light is unchanged apart from the two planned changes: `pairs/drawer-390-light-pair.png` (white body) and `pairs/today-1280-light-pair.png` (risk outline). The pixel diff of `profile-*-light` before and after is empty.
- HC dark is unchanged: `pairs/today-390-dark-hc-pair.png`.
- After shots for DK1 to DK4 don't exist yet; they're "claimed" until re-shot.

## Acceptance criteria for qa-tdd

- **CHL-UX-DK1:** in standard dark at 390 and 1280, with the drawer open and on Profile, every visible `.bar` background is 1.15:1 or more against the first opaque ancestor background. In light, `.bar` stays 1.15:1 or more against its card or drawer.
- **CHL-UX-DK2** (if staff-pm takes the preferred fix): in standard dark, `.card .btn-secondary` and `.panel .chip` backgrounds are 1.15:1 or more against `--raised`. Light text contrast on them stays 4.5:1 or more.
- **CHL-UX-DK3:** `.risk-control` computed background equals `--raised` in all four modes. If CHL-DARK-7 is amended, its border equals `--line`, and the range input keeps `accent-color: var(--accent)` at 3:1 or more.
- **CHL-UX-DK4:** in standard dark, `.table-wrap`, `.row-card` and `.pos-card` are 1.15:1 or more against `--bg`. Light and HC are unchanged.

## For Chase

1. Nothing needed from you for this PR: one P1 (bar tracks) is a one-line CSS fix for the engineer, then a re-shoot.
2. Your call later, via staff-pm: keep the risk box's new grey outline, or calm it back to the hairline (DK3; I'd calm it).

```uxrun
date: 2026-11-23
product: charlie
tier: Advisory
model: claude-opus-5-5
tokens: not measured
cost: not measured
flows:
  - first-open dialog, today, drawer, profile, screener at 390x844 and 1280x800, light and dark, plus HC dark at 390 -> /mnt/project-files/charlie-dark-layers-2026-11-23/
findings:
  - CHL-UX-DK1 | P1 | V7/W5 | pairs/drawer-390-dark-pair.png
  - CHL-UX-DK2 | P2 | V6/V7 | pairs/today-390-dark-pair.png
  - CHL-UX-DK3 | P2 | V1/V5 | pairs/today-1280-light-pair.png
  - CHL-UX-DK4 | P2 | V5 | inferred from web/styles.css (Trades not shot)
verdict: Needs changes
rechecked: no (no fix yet)
escalated: no (DK3 needs a staff-pm call on CHL-DARK-7, not Chase)
checks: ux-rules.mjs run before and after (same 6 pre-existing failures); check-ux-run.mjs, check-findings.mjs and ux-refs.mjs not in this repo
```

```findings
verdict: Needs changes
score: 7/10
CHL-UX-DK1 | P1 | V7/W5 | Drawer checklist bars and Profile circle bars, dark | .bar --fill on --raised is 1.02:1, track invisible (was 1.18:1) | .bar { background: var(--line) }, re-shoot light
CHL-UX-DK2 | P2 | V6/V7 | Card score button, Copy trade details, Profile chips, input fills, dark | --fill on --raised is 1.02:1, button and chip shapes vanish | Use --line for .card .btn-secondary and .panel .chip, or accept and ask hearth for raised-fill
CHL-UX-DK3 | P2 | V1/V5 | Risk control, Today and Search, all modes | Pill stays --surface beside --raised cards; its 3:1 outline is the loudest container edge | .risk-control background var(--raised); staff-pm consider --line outline (amend CHL-DARK-7)
CHL-UX-DK4 | P2 | V5 | Search .table-wrap/.row-card, Trades .pos-card, dark | Still --surface at 1.08:1 while other cards are 1.15:1 | Move those backgrounds to var(--raised)
```

## Round 2

Recheck of the round 2 fix (commit `c693dd7`, `web/styles.css` only: `.bar` track on `--line`, `.risk-control` on `--raised` with a `--line` edge, `table`, `.table-wrap`, `.row-card` and `.pos-card` on `--raised`). DK2 is deferred to PLAN M1.17 and not rechecked here.
Build: `tools/build_demo.py --date 2026-11-23` into a scratch dir. "Before" is the round 1 after build; "after" is this branch. `diff -rq` of the two builds: only `styles.css` differs.
Shots: `/mnt/project-files/charlie-dark-layers-2026-11-23/round2/`. Each shot is named `<screen>-<width>-<mode>-<before|after>.png` (screens: `first-open-dialog`, `today`, `today-full`, `drawer`, `profile`, `profile-full`, `screener`, `screener-full`, `trades`, `trades-full`; trades has one sample paper position opened from the first idea). Modes: light and dark at 390 and 1280, plus HC dark at 390. Side-by-side pairs are in `round2/pairs/`.

Hard rules checked: "Not financial advice. Paper trading only." is visible in every after shot: idea card, drawer header, Trades footer line and the desktop sidebar. "Sample data" stays in the demo bar. The trades flow only opens a paper position in the browser (static demo, no network beyond Pyodide). The change is CSS only, so paper-only, safe-by-default, resume privacy and the static-demo rules are untouched. Every trade surface still shows max loss, breakeven and the exit plan (today and trades shots).

### Verdict: Ready for this PR. Visual score 8/10 (bar 8)

- **Recruiter, phone, dark:** Today, Search and Trades now share one card elevation, so nothing new to trip on. The risk box is calmer and the first idea is the focal point again.
- **Hiring manager, laptop, dark:** the Munger checklist bars have their 0 to 100 track back (65 and 55 read against a rail), in both the drawer and the Profile circle bars.
- **New investor, phone:** controls unchanged. Worst control edge is still 3.02:1 in dark and 3.04:1 in light, and 4.60:1 in HC dark.
- **Light and HC dark:** light matches round 1 apart from the firmer bar track (1.34:1) and the risk box edge going back to the hairline. HC dark cards are unchanged. The HC bar track is now `--line` (4.60:1 on the drawer), with the ink value 3.26:1 on that track. That's above 3:1, and the bars read more clearly as a scale than before.

Score evidence (8): every "card on the page" surface (`.card`, `.panel`, `.risk-control`, `.table-wrap`, `.row-card`, `.pos-card`, dialog and drawer) now paints `--raised` at 1.15:1 on the page in dark, measured. The bar tracks are back at 1.15:1 in dark and 1.34:1 in light. The risk box no longer has the loudest container edge on Today. Not 9, because DK2 (the `--fill` buttons and chips at 1.02:1 on raised) is still open by plan, and the Trades stat tiles sit on a different layer (DK5).

### The critic's line

Hiring manager, laptop, dark: "OK, the bars have rails and the cards line up now. Why are the four numbers on Trades just outlines when the trade under them is a card?"

### Recheck of round 1 findings (measured, Chromium computed styles)

| ID | Round 1 | Round 2 | Status | Evidence |
|---|---|---|---|---|
| CHL-UX-DK1 | `.bar` track 1.02:1 on raised (dark) | 1.15:1 dark, 1.34:1 light, 4.60:1 HC dark; value on track 12.16 / 12.79 / 3.26 | Fixed, verified | `pairs/drawer-390-dark-pair.png`, `pairs/drawer-390-dark-hc-pair.png`, `pairs/profile-1280-dark-pair.png` |
| CHL-UX-DK2 | `--fill` on raised 1.02:1 | 1.02:1 (unchanged) | Deferred, PLAN M1.17 | `pairs/today-390-dark-pair.png` |
| CHL-UX-DK3 | risk box `--surface` 1.08:1, edge 3.22:1 | `--raised` 1.15:1 on page (dark), edge `--line` 1.15:1 dark, 1.34:1 light, 4.60:1 HC | Fixed, verified | `pairs/today-1280-dark-pair.png`, `pairs/today-1280-light-pair.png` |
| CHL-UX-DK4 | `.table-wrap`, `.row-card`, `.pos-card` 1.08:1 | 1.15:1 on page in dark, at 390 and 1280; light and HC unchanged (1.07 / 1.08) | Fixed, verified (Trades now shot) | `pairs/screener-1280-dark-pair.png`, `pairs/trades-390-dark-pair.png`, `pairs/trades-1280-dark-pair.png` |

`node scripts/ux-rules.mjs` on the round 2 build gives the same 6 pre-existing failures as round 1 (the G3 on `#ack` and two V9 card-in-card hits). Report: `round2/ux-rules-report.md`. No new failure.

### New findings

| ID | Pri | Rule | Screen and region | Problem | What the person would do | Fix |
|---|---|---|---|---|---|---|
| CHL-UX-DK5 | P2 | V5 | Trades `.stats .metric` tiles (Open positions, Open P&L, Realized P&L, Most you could lose), all modes, clearest in dark | The tiles have no fill: a `--line` outline on the page (`--bg`). The `.pos-card` right under them is now `--raised` (1.15:1 in dark), so the same "card on the page" role gets two treatments on one screen. This isn't new in round 2, but DK4 made it visible. | Reads the four numbers as a lighter-weight thing than the position. That's mild, and arguably intended. | `.stats .metric { background: var(--raised); }`. No new token. Light and HC get `--surface`, which matches `.pos-card` there. Fold into M1.17 with DK2 if staff-pm prefers one follow-up. |

### Cut list (C5)

Nothing to cut: round 2 swaps backgrounds and one border, and adds no element, word or size.

### Acceptance criteria for qa-tdd

- **CHL-UX-DK5:** in standard dark at 390 and 1280 on Trades with one paper position, every visible `.stats .metric` computed background equals the `.pos-card` (or `.table-wrap`) background and is 1.15:1 or more against `--bg`. In light and HC dark it equals `--surface`.

### For Chase

1. Nothing needed from you: DK1, DK3 and DK4 are verified fixed with after shots, and the PR is at the 8/10 bar.
2. One new P2 (DK5, the Trades number tiles) can ride with DK2 in M1.17.

```uxrun
date: 2026-11-23
product: charlie
tier: Advisory
model: claude-opus-5-5
tokens: not measured
cost: not measured
flows:
  - first-open dialog, today, drawer, profile, screener, trades (one sample position) at 390x844 and 1280x800, light and dark, plus HC dark at 390 -> /mnt/project-files/charlie-dark-layers-2026-11-23/round2/
findings:
  - CHL-UX-DK1 | P1 | V7/W5 | fixed, round2/pairs/drawer-390-dark-pair.png
  - CHL-UX-DK2 | P2 | V6/V7 | deferred (PLAN M1.17), round2/pairs/today-390-dark-pair.png
  - CHL-UX-DK3 | P2 | V1/V5 | fixed, round2/pairs/today-1280-light-pair.png
  - CHL-UX-DK4 | P2 | V5 | fixed, round2/pairs/trades-390-dark-pair.png
  - CHL-UX-DK5 | P2 | V5 | round2/pairs/trades-390-dark-pair.png
verdict: Ready
rechecked: yes (round 1 after build vs round 2 build, same flows plus Trades)
escalated: no
checks: ux-rules.mjs run on round 2 build (same 6 pre-existing failures); check-ux-run.mjs, check-findings.mjs and ux-refs.mjs not in this repo
```

```findings
verdict: Ready
score: 8/10
CHL-UX-DK2 | P2 | V6/V7 | Card score button, Copy trade details, Profile chips, input fills, dark | --fill on --raised still 1.02:1 (deferred to PLAN M1.17) | Use --line for .card .btn-secondary and .panel .chip, or ask hearth for raised-fill
CHL-UX-DK5 | P2 | V5 | Trades .stats .metric tiles, all modes | Unfilled outline tiles on --bg next to a --raised .pos-card | .stats .metric { background: var(--raised) }
```
