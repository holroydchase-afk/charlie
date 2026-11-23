# Spec: dark-mode layering on the live demo (intake #55)

Planning ID: `CHL-M1.16`. One PR for the layering (CHL-DARK-1 to 10). The first-open notice (CHL-DARK-11 to 13) is a separate small PR that waits for Chase's call (see Decisions). Both change `web/`, so both wait for Chase's go to merge (every merge to `main` redeploys the demo).

## Bet
A recruiter opening chaseholroyd.com/charlie/ on a phone in dark mode can tell a card from the page and a dialog from what's behind it, and can see where every field and control is. Signal: the ratios below, measured in the browser at 390 and 1280, plus ux-reviewer's dark pass with no P0/P1.

## What exists today (checked on main a50ab41 + a085469; `web/` matches `origin/main`, so the restyle #49 and nav #50 are in)
Computed from `web/themes.css` (Paper tokens, copied byte for byte from hearth `tokens.json`; `tests/test_design_system.py` CHL-DS-1 pins them and allows no other custom property):

| Pair (dark) | Ratio | Intake target |
|---|---|---|
| `--surface` #1C1A17 (cards, panels, modal, header) on `--bg` #131210 | 1.08:1 | 1.15:1 or more |
| `.modal-inner` (`--surface`) on `--bg` under `--scrim` 0.6 | 1.16:1 | step lighter, scrim behind |
| `.drawer-inner` uses `--bg`, the same as the page | 1.00:1 | (same problem, not in the intake) |
| `--line` #2E2B27 (card, panel, pill, badge, rank, risk-control borders) on `--surface` | 1.23:1 | decorative, fine |
| `--tab-line` #696661 (input, select, textarea, `.choice` borders) on `--surface` / `--bg` | 3.04 / 3.28 | 3:1, passes today |
| `--tab-line` on a card raised to 1.15:1 (#22201C) | 2.84 | fails once cards step up |

So the intake's 1.08:1 still holds after the restyle; it's the token pair, not a stale build. The scrim already exists (`.modal` and `.drawer` paint `--scrim`). Control edges pass today but **break the moment cards get lighter**, so the edge token must be derived against the raised surface too. Light mode: `--surface` on `--bg` is also 1.07:1, but light relies on the white card plus `--line` border (1.34:1) and the intake only asks for dark; light stays byte for byte.

The first-open dialog is `#ack` in `web/index.html` (a `div.modal`, not a native `<dialog>`), opened by `boot()` in `web/app.js` when `localStorage["charlie-ack"]` isn't `"1"`. It covers Today on first visit in both the local app and the demo. The persistent `#disclaimer-line` (CHL-NAV-3) and the code-added "Not financial advice. Paper trading only." on every idea card, trade block, drawer and chat reply already cover the hard rule without it.

Missing references: design rule D5, DARK-5 and CONTRAST-2 live in studio-agents `docs/references/ux/`, which this session can't read (no GitHub access to studio-agents), and `.claude/design-rules.md` here only has D1 to D3. `scripts/ux-refs.mjs` does not exist in this repo (only `ux-rules.mjs` and `ux-shots.mjs`). This spec works from the intake's wording of them.

## Approach (decided here; reversible)
Two Charlie-local tokens in `web/themes.css`, derived by rule, defined for light, dark, HC light and HC dark:
- `--raised`: dark = the first mix of `--surface` toward `--ink` (1% steps) with contrast vs `--bg` of 1.15 or more (about #22201C). Light = `--surface` (unchanged look).
- `--control-edge`: `edge()` from `--tab-line` toward `--ink` until 3:1 or more against `--raised`, `--surface` and `--bg`. HC uses the HC `--tab-line` as the start.

Use `--raised` for `.card`, `.panel`, `.modal-inner`, `.drawer-inner` (and `.drawer-head` on top of it stays one step: `--raised`); use `--control-edge` for input, select, textarea, `.choice` and `.risk-control` borders. The 16 studio tokens keep their `tokens.json` values; CHL-DS-1 gains an explicit allowlist of exactly these two local tokens (it gets stricter: the local ones are pinned to their rule). Upstream: suggest hearth adds a `raised` token so Charlie can drop the local one.

## Acceptance criteria (qa-tdd writes these red first)
Unit tests in `tests/test_dark_layers.py` (CSS parsed like `test_design_system.py`); e2e in `tests/e2e/test_dark_layers_e2e.py` (computed styles in Playwright at 390x844 and 1280x800, dark via `color_scheme` and via `data-theme=dark`).

- **CHL-DARK-1** (auto) Given `themes.css`, when each of the 8 states resolves (OS light/dark x in-app none/light/dark x HC), then `--raised` and `--control-edge` are defined, and in dark `--raised` equals the derivation rule above (within 1 per channel) and is 1.15:1 or more against `--bg`.
- **CHL-DARK-2** (auto) Given light mode (standard and HC), then all 16 studio tokens are byte for byte unchanged and `--raised` equals `--surface`. Every existing CHL-DS test stays green with no assertion loosened; CHL-DS-1's set check names the two local tokens explicitly.
- **CHL-DARK-3** (auto) Given dark mode at 390 and 1280, when Today, Screener, Chat, Portfolio, Learn and Profile render with the demo's sample data, then every visible `.card` and `.panel` whose parent background is `--bg` has a computed background 1.15:1 or more against the page (no nested card counted).
- **CHL-DARK-4** (auto) Given dark mode, when the ack dialog is open (via "Read more"), then `.modal` paints `--scrim`, and `.modal-inner` is 1.15:1 or more against both the page `--bg` and the scrimmed page (bg with the scrim composited).
- **CHL-DARK-5** (auto) Given dark mode, when the ticker drawer is open, then `.drawer-inner` is 1.15:1 or more against `--bg` and against the scrimmed page; its trades still sit on it, not in cards (UX11).
- **CHL-DARK-6** (auto) Given dark, light, HC dark and HC light at 390 and 1280, when every visible `input` (except range, checkbox, radio), `select`, `textarea` and `.choice` renders, then its border is 1px or more and 3:1 or more against the computed background directly outside it (walk up to the first non-transparent ancestor). This is the per-control check the intake asks for.
- **CHL-DARK-7** (auto) Given the same states, then the risk slider (`.risk-control input[type=range]`) keeps `accent-color: var(--accent)` and `--accent` is 3:1 or more against `--raised` and `--surface`; `.risk-control`'s outline uses `--control-edge`.
- **CHL-DARK-8** (auto) Given CHL-DS-3's contrast pairs, when they are re-run with `--raised` substituted for `--surface`, then every pair still passes in all 4 modes (ink 7:1, muted 4.5:1, accent 4.5:1 on raised, and so on).
- **CHL-DARK-9** (auto) Given the e2e suite, then axe WCAG 2.2 AA still passes on every tab, the ack dialog and the drawer at 390 and 1280 in light and dark, with no horizontal overflow; no new color literal in `styles.css`, `app.js` or `static.js` (CHL-DS-4 holds).
- **CHL-DARK-10** (manual) Given `node scripts/ux-shots.mjs` against the built demo before and after, then screenshots at 390 and 1280, light and dark, sit in the PR (not in git), and ux-reviewer's review has a `Hard rules checked:` line covering dark layers and control contrast with no P0/P1. `scripts/ux-refs.mjs` does not exist here, so the PR says so instead of running `ux-refs.mjs cite`; adding it is a studio-agents sync item, not this PR.

First-open notice (only after Chase picks option A below; separate PR):
- **CHL-DARK-11** (auto) Given a fresh visit (no `charlie-ack`) at 390 and 1280, when the page loads, then no dialog or scrim is shown, the top of Today (hero and first idea card) is visible without a tap, and an inline notice at the top of Today shows the three ack bullets and a "Got it" button.
- **CHL-DARK-12** (auto) Given that notice, when "Got it" is pressed, then `charlie-ack` is `"1"`, the notice is gone and stays gone on reload; Reset demo and Delete my data keep it, as today. "Read more" on the disclaimer line still opens the full disclaimer dialog with Close, Escape and focus return (D2, D3).
- **CHL-DARK-13** (auto) Given every trade surface (idea card, trade block, drawer, chat trade card, every chat reply), then "Not financial advice. Paper trading only." is still added by code, with the notice shown or dismissed; the existing disclaimer tests pass unchanged.

## Triage (staff-pm, Nov 23, on qa-tdd's red run)
These calls amend the criteria above; where they differ, this section wins.
- **QA-R1 (P1): fix in this PR, test change.** CHL-DS-4's `ok()` accepts `LOCAL_TOKENS` as well as `TOKENS`, the same explicit two-name tuple CHL-DS-1 uses. Nothing else in DS-4 changes. A tuple, never a pattern; any third local token still fails both tests. Lane: qa-tdd. Done when: DS-4 still fails a made-up `var(--foo)` in styles.css and passes `var(--raised)`.
- **QA-R2 (P1): HC dark `--raised` = `--surface`.** In HC the layers come from the `--line` card border at 4.5:1 (DS-3's HC pair), which is a stronger cue than a fill step. A fill step there would break that pair, and we change no studio token and exempt no pair. Rule: `--raised` steps up only in standard dark. Light, HC light and HC dark all use `--surface`. `--control-edge` follows its rule unchanged (in HC dark it resolves to the HC `--tab-line`). Effect on the criteria:
  - CHL-DARK-1: `want_raised` returns `--surface` for HC dark. The 1.15:1 check applies only to standard dark.
  - CHL-DARK-3/4/5: standard dark only, as written (the e2e already runs without HC).
  - CHL-DARK-8: unchanged and passes in all 4 modes. In HC dark it's DS-3 itself.
  - Add **CHL-DARK-8b** (auto): in HC dark, `.card`, `.panel` and `.modal-inner` have a 1px or wider `--line` border that is 3:1 or more against `--bg`.
  - Not doing: a step for HC-dark fills. If Chase wants one, it waits on hearth adding `raised` with an HC value.
- **QA-R3 (P2): in this PR.** The rule is simple: no `var(--tab-line)` is left in `styles.css`. Every use moves to `--control-edge`, which is the token built to keep 3:1 on raised. That covers `.row-card`, `.chip-check`, `.callout`, `.badge.mock` and `.payoff .zero`. Six lines of CSS. Same PR, no new screens.
  - Add **CHL-DARK-6b** (auto, unit): `styles.css` has no `var(--tab-line)`.
  - Add `.chip-check` to the CHL-DARK-6 e2e control list (it's a control, so it needs a 3:1 edge against what's outside it).
  - `.row-card`, `.callout`, `.badge.mock` and the zero line are covered by 6b. No per-element e2e.
- Lanes: qa-tdd → DS-4 allowlist, DARK-1 HC-dark rule, DARK-6b, 8b and the `.chip-check` e2e red. Done when: they fail for the stated reason and DS is otherwise green. engineer → HC-dark `--raised` and the `--tab-line` swaps. Done when: all suites are green with nothing else loosened.

## Not doing
- Changing any studio token value in `themes.css` (that's hearth's call; we suggest a `raised` token upstream).
- Light-mode card steps: light reads fine with borders and the intake asks for dark only.
- Borders on text buttons (`.btn-secondary`, `.btn-tinted`): WCAG 1.4.11 doesn't need a boundary when the label identifies the button. Decision for Chase below.
- Decorative edges (card, panel, pill, badge, rank, `.ticket`, `.edu`) stay `--line`.
- Moving `#ack` to a native `<dialog>` (D1): real, but separate; logged as a P2.
- Hunches tab (local-only), new screens, copy changes beyond the notice.

## Biggest risk
The token tests: CHL-DS-1 forbids extra properties and raising the surface drops `--tab-line` under 3:1. Handled by step 1 (qa-tdd writes CHL-DARK-1, 2, 6, 8 first) so the engineer can't "fix" it by editing a studio token or loosening a DS test.

## Critical path (about 3 sessions)
1. qa-tdd: re-measure on current main with Playwright (390 dark, cards and dialog), then CHL-DARK-1 to 9 red. Done when they fail for the stated reason and every CHL-DS test is still green. 1 session.
2. engineer: the two tokens and the CSS swaps in `web/themes.css` and `web/styles.css`; CHL-DS-1 allowlist. Done when CHL-DARK-1 to 9 pass and all suites pass. 1 session.
3. qa-tdd 3x green, then ux-reviewer dark/light/HC at 390 and 1280 (CHL-DARK-10). Done when no P0/P1 and before/after shots are in the PR. 1 session.
4. Only after Chase picks A: qa-tdd CHL-DARK-11 to 13 red, engineer builds, ux-reviewer plus privacy-security (safety story). About 1 to 2 sessions.

## Decisions for Chase
1. **D5, first-open disclaimer.** A (recommended): no modal on first open; an inline notice at the top of Today with the same three bullets and "Got it", the disclaimer line and per-card disclaimers unchanged, "Read more" still opens the dialog. Reversible in one commit. B: keep the blocking dialog and close D5 as won't-fix. It touches the paper-only story, so it's your call, not ours.
2. **Button edges.** Recommend WCAG scope (inputs, selects, textareas, choice chips, the slider get 3:1 edges; labelled text buttons don't need a border) over the intake's "every button edge".
3. **Local tokens vs upstream.** Recommend shipping `--raised` and `--control-edge` locally now and suggesting a `raised` token to hearth, over waiting on hearth.

## Handoffs
- qa-tdd → CHL-DARK-1 to 9 red (and the live re-measure) → fail for the right reason, DS suite green.
- engineer → tokens and CSS in `web/` → CHL-DARK-1 to 9 green, nothing loosened.
- ux-reviewer → dark/light/HC pass at 390 and 1280 → CHL-DARK-10 met.
- privacy-security → only for CHL-DARK-11 to 13 (disclaimer surface) → no weakening of the paper-only story.
