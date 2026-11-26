# SPEC: Portfolio site header on the demo (intake #64)

Staff PM, Nov 25. Live demo change: **waits for Chase's go** (CLAUDE.md "Merging").

## The bet
A visitor who lands on chaseholroyd.com/charlie/ sees the same site header as every other demo and can get back to the portfolio, without losing any of Charlie's first screen, its disclaimer or its safety numbers.

## What the script does (read from the live file, Nov 25)
`https://chaseholroyd.com/assets/demo-bar.js` (same origin as the demo). It:
- inserts a `<header id="site-bar">` as the body's first child and loads `/assets/demo-bar.css`;
- the CSS makes the bar `position: fixed; top: 0; height: 52px; z-index: 2147483000`, sets `body { padding-top: 52px !important }`, `html { --site-bar-h: 52px }`, and `body > div:first-of-type { max-height: calc(100dvh - 52px) }`;
- with `data-page="white"` and not dark, adds `html.sb-white`, which forces `html, body { background: #fff !important }`;
- picks dark from `localStorage "theme"` (default light), **not** Charlie's `charlie-appearance` key;
- builds its nav with an inline `style="display:contents"`, which the demo's CSP (`style-src 'self'`, no `'unsafe-inline'`) blocks.

Findings this raises for Charlie (ID'd so each gets a test):
- **CHL-BAR-R1 (P1)** Charlie in dark (chosen, or Auto on a dark phone) gets a white `body` from `sb-white` and a light site bar. Fix in Charlie's CSS: `html.sb-white[data-theme="dark"] body` and the Auto-dark media query restore `var(--bg)` with `!important` (higher specificity wins).
- **CHL-BAR-R2 (P1)** The bar is above everything (z-index 2^31). Fixed things at `top: 0` slide under it: the phone's sticky `.top` header, the laptop sidebar (`position: fixed; top: 0`), the ticker drawer, the first-run modal, and `#engine-status` (`top: 12px`). Fix: offset each by `var(--site-bar-h, 0px)` and size by `calc(100dvh - var(--site-bar-h, 0px))`.
- **CHL-BAR-R3 (P2)** `body > div:first-of-type` is `#drawer` in Charlie, so its height is clipped by 52px; covered by R2's drawer offset.
- **CHL-BAR-R4 (P2)** The inline `display:contents` is blocked by CSP; the site nav may lay out slightly differently than on other demos. Not Charlie's to fix: note it for the portfolio repo (make it a class in demo-bar.css). Do **not** add `'unsafe-inline'` to Charlie's CSP.
- **CHL-BAR-R5 (P2)** Two "back to portfolio" links: the site bar and Charlie's own demo strip (CHL-DEMO-R1, "← Portfolio"). The intake keeps the strip for now; AGENT-NOTES says "the demo has one notice"; update that line in the same PR.

## Where the tag goes
Only in the **demo build**, injected by `tools/build_demo.py` before `</body>` (like `static.js`), never in `web/index.html`: the local FastAPI app has no `/assets/` and no portfolio. Exact tag: `<script src="/assets/demo-bar.js" data-page="white" defer></script>`.

`tools/check_site.py`: the URL scan only flags `https?://` hosts, so a root-relative path passes, and the CSP already allows same-origin scripts and styles. Add a guard so this stays the **only** root-relative script (a typo'd or new one fails the build).

Local and CI builds have no `/assets/demo-bar.js`. `tests/e2e/test_demo_verified_e2e.py::test_DEMO_SUBPATH_demo_works_when_served_under_charlie` fails today on any request outside `/charlie/` and on any 4xx. Don't weaken it: the test server serves a stub `tests/fixtures/demo-bar-stub.js` (and stub CSS) at `/assets/`, a copy of the live behavior that matters (52px fixed bar, body padding, `sb-white`), and the test allows exactly those two paths and nothing else. A note in the stub says it mirrors the live file as of Nov 25.

## Acceptance criteria
- **CHL-BAR-1** (auto) Given `build_demo.build()`, then `index.html` has exactly one `<script src="/assets/demo-bar.js" data-page="white" defer></script>`, immediately before `</body>`; `web/index.html` has none.
- **CHL-BAR-2** (auto) Given the built site, `check_site.py` passes with and without `--no-cdn`; given a site with an extra root-relative script (e.g. `/assets/other.js`) it fails with a clear message. The CSP is unchanged (`script-src 'self' 'wasm-unsafe-eval'`, `style-src 'self'`, no `'unsafe-inline'`).
- **CHL-BAR-3** (auto, e2e) Given the demo served under `/charlie/` with the stub at `/assets/`, then the only requests outside `/charlie/` are `/assets/demo-bar.js` and `/assets/demo-bar.css`, none return 4xx, and there are no page errors.
- **CHL-BAR-4** (auto, e2e at 390x844 and 1280x800) Given the bar, then nothing of Charlie's sits under it: the top of `.top` (phone) or the sidebar (laptop) is at y >= 52; the sidebar's bottom (Profile button, disclaimer line) is fully inside the viewport at 1280x800 and at 1280x720; the phone's bottom tab bar and disclaimer line are unchanged.
- **CHL-BAR-5** (auto, e2e at 390 and 1280) Given a first visit, then the first-run dialog's top edge is at y >= 52, its "Got it" button is visible without scrolling the page, and the scrim behind it covers Charlie (the site bar may stay above it). Same for the ticker drawer: its title and Close are at y >= 52, and Escape still closes it with focus returned.
- **CHL-BAR-6** (auto, e2e at 390) After dismissing the dialog, card 1's Max loss is still inside the first screen (CHL-NAV-8 regression guard with 52px less height).
- **CHL-BAR-7** (auto, e2e) Given `charlie-appearance` = dark, and separately Auto with `prefers-color-scheme: dark`, then `body`'s computed background equals Charlie's dark `--bg`, not white. Given light, body is white.
- **CHL-BAR-8** (auto) "Not financial advice. Paper trading only." on every trade surface is unchanged (existing tests pass unchanged).
- **CHL-BAR-9** (manual) ux-reviewer screenshots at 390 and 1280, light and dark, with the first-run dialog open and closed, in the PR. privacy-security confirms the demo still calls no host but its own (`check_site.py --no-cdn`).

## Not doing
- Folding Charlie's demo strip into an info drawer (Chase "may later"; the tag stays either way). Logged as a PLAN idea.
- Changing the shared script or CSS (portfolio repo). R4 and "read `charlie-appearance` too" go to that repo as notes.
- The first-run dialog's own redesign (CHL-DARK-11 to 13, paused by Chase).

## PR
One PR, about 1 session: qa-tdd red (CHL-BAR-1 to 8), engineer (build_demo injection, check_site guard, CSS offsets, test stub), qa-tdd 3x, ux-reviewer, privacy-security. Merge after the intake #60 PRs that touch the Today card (PR C), so the 390 first-screen guard is measured once on the final card.

## Decisions for Chase
1. **Two portfolio links for now** (site bar plus Charlie's strip). Recommend yes, as the intake says; fold later.
2. **White page only in light mode.** Charlie keeps its dark background when the visitor chose dark. Recommend yes (the shared script already skips white in its own dark mode).

## PLAN items to add
- `CHL-M1.20 Site header (intake #64)`, todo. Inject the shared header in the demo build only; R1 to R3 fixes; stub for CI. Spec `docs/product/SPEC-SITE-HEADER.md`. Waits for Chase's go; merge after M1.19 PR C.
- Idea, not now: fold the demo strip into an info drawer (Chase, intake #64 "may later").
- Note for the portfolio repo: demo-bar.js inline `style` is blocked under a strict CSP (CHL-BAR-R4); read each demo's own theme key.
