# Recruiter-ready review: 2026-10-24

The static demo (`tools/build_demo.py`, built for 2026-10-22) was walked through as a recruiter would see it: phone first (390x844), then desktop (1280x800), in light and dark. Pyodide was served locally, and CI also ran it from the public CDN. Roles were played inline by the night shift.

## Ranked findings

| # | Sev | Role | Finding | Status |
|---|---|---|---|---|
| 1 | P1 | ux-reviewer | The demo's Today nudge said the ideas came from "a generic starter circle", but they're the sample person's. | Fixed in M1.4: "These ideas are for Alex Rivera, a fictional sample person." |
| 2 | P1 | ux-reviewer | axe (WCAG 2.2 AA) flagged the tab bar: buttons inside `role="tablist"` without `role="tab"`, on every screen. | Fixed in M1.7: ARIA tabs pattern plus arrow, Home and End keys. axe is clean on every tab. |
| 3 | P1 | ux-reviewer | With upload hidden in the demo, the Profile form opened on an orphaned "…or paste it" label. | Fixed: the demo label reads "Paste a resume". |
| 4 | P1 | ux-reviewer | The Profile heading read "Alex Rivera (sample)'s circle". | Fixed: "Alex Rivera's circle (sample)". |
| 5 | P2 | ux-reviewer | A recruiter can't see which resume produced the sample ideas. | Fixed: a demo-only "Use the sample resume" button fills the form with the fictional resume. |
| 6 | P2 | qa-tdd | Interactive features (chat, screener, paper trades, your own resume) wait for Pyodide: about 20 s on a 4x-throttled phone over 4G, 39 s at 6x on slow 4G. Today and the risk slider are instant from prebuilt answers. | Open. A "Starting Charlie's engine" pill shows during the wait. Next lever: prebuild a few common chat answers, or warm Pyodide in a Web Worker. |
| 7 | P2 | privacy-security | `pyodide.js` loads from jsDelivr without a Subresource Integrity hash, and Pyodide then fetches its own runtime files. The CDN learns visitors' IPs, as with any CDN. | Fixed (Oct 24 morning): `pages.yml` self-hosts the runtime (`build_demo.py --pyodide-dir`, npm checks the tarball's integrity), and `check_site.py --no-cdn` plus a browser test confirm nothing leaves the site. |
| 8 | P2 | qa-tdd | Not checked on real phones (only Chromium emulation with CPU and network throttling). | Open. Chase can try it on his phone once M1.6 is live. |
| 9 | P3 | ux-reviewer | On phones, the Screener's "Name to save this screen" placeholder is cut off. | Fixed (Oct 24 morning): the placeholder is "Screen name", and the full wording moved to `aria-label`. |
| 10 | P3 | ux-reviewer | The demo's date is pinned to the build date (status and ideas say 2026-10-22 here). | By design (prebuilt answers). M1.6 can rebuild on a schedule. |

## Privacy and safety check (privacy-security)

- The demo makes no network calls except its own files and Pyodide. `tools/check_site.py` enforces this in CI, including inside `charlie.zip`.
- A pasted resume stays in the visitor's `localStorage` (`charlie:kv:intake`, up to 50,000 characters). It's never sent anywhere, and Reset demo or Delete my data removes it.
- No keys, analytics, login or backend. Static mode never imports `anthropic`, `requests`, `sqlite3` or the live adapters (tested).
- "Not financial advice. Paper trading only." appears on every idea card, trade block, chat reply, chat trade card, the chat panel and the ticker drawer (unit and browser tests).
- `samples/` and the demo hold only the fictional Alex Rivera.

## Verdict

There are no open P0 or P1 findings. The demo is ready to go public once Chase finishes M1.5 (the full-history privacy review and his decision to make the repo public) and M1.6 (the Pages deploy). After that, Charlie can be added to the portfolio.
