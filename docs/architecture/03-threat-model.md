# Threat model

_What we protect, from whom, and the limits we know about. Rules and status labels: [README](README.md)._

Charlie runs as a single-user **local app** (a FastAPI server on 127.0.0.1 with a SQLite file in the gitignored `data/` folder) and as a **static demo** (the same Python engine in the visitor's browser through Pyodide, on sample data only). There is no hosted backend and no login. The repo is private today and is written as if it were public (CLAUDE.md), because it goes public after a privacy-security review (PLAN M1.5).

## Assets

| Asset | Why it matters |
|---|---|
| Resume text | Personal data: work history, employers, often contact details. A leak exposes the user. |
| Profile, holdings and paper trades | Reveal what the user knows, owns and is considering; holdings hint at net worth. |
| Anthropic API key (`ANTHROPIC_API_KEY`) | Billable credential; a leak lets anyone spend on the owner's account. |
| SEC contact string (`CHARLIE_SEC_UA`) | Usually the owner's real email; must never be committed. |
| Demo visitors' browsers | A demo that loads third-party code or leaks a key harms visitors and the owner's reputation. |
| The user's trust that output is educational | Acting on an idea as advice could lose real money. |

## Adversaries

| Adversary | Can do | Defense | Status |
|---|---|---|---|
| A malicious web page the user visits while the local app runs (DNS rebinding) | Rebind its own hostname to 127.0.0.1 and read or write the local API as a "same-origin" page | `LocalOnly` refuses any request whose Host isn't 127.0.0.1, localhost or [::1], on every method, with 400 (`charlie/server.py`). The Host check is hand-written because Starlette's `TrustedHostMiddleware` can't parse `[::1]:8000`. | **Built (release branches, not yet merged)** |
| A malicious web page (CSRF) | Send cross-site POST or DELETE requests to `127.0.0.1:8000`, for example to wipe data or plant a profile | A write that carries an Origin must be a loopback host on the server's own port, else 403 (`LocalOnly`). In `main`, the older `same_origin_only` middleware refuses cross-site writes but allows any loopback port. | **Built** (older check); **Built (release branches, not yet merged)** (port-exact) |
| A malicious page framing or sniffing the local app | Clickjack the UI or get a response run as script | `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff` on every response, `Cache-Control: no-store` on `/api/*`, and a strict page CSP with `frame-ancestors 'none'` on `/` (`LocalOnly`, `PAGE_CSP`). | **Built (release branches, not yet merged)** |
| Oversized or hostile uploads (the user, or a CSRF that got past the checks) | Exhaust memory, disk or CPU with a huge body, a zip bomb DOCX or a PDF whose content streams inflate to gigabytes | Bodies over 9 MB get 413 before form parsing, by Content-Length or by counting a chunked body; uploads stay in memory. DOCX: refused over 200 members, 20 MB unpacked or 100:1. PDF: 30 pages at most, content streams over 2 MB decoded refused, pypdf's own decode caps lowered to 10 MB. Text capped at 100,000 characters, the profile built from at most 50,000. Parsing runs in a worker thread (`charlie/server.py`, `extract_text` in `charlie/profile.py`). A 0.17 MB PDF with a 60 MB stream is refused in under 0.1 s. | **Built (release branches, not yet merged)**; the 8 MB file cap is **Built** |
| Bad input to the API | Crash handlers or store absurd values | Capital must be finite, over 0, at most 1e9; holdings over 1e9 shares dropped; screen names, notes and chat sizes capped; bad criteria and legs return 422 naming the field (`charlie/handlers.py`). | **Built (release branches, not yet merged)** |
| A shared demo link | Point the demo at another site's script (`?pyodide=`) | The override is removed; Pyodide loads only from the base `tools/build_demo.py` sets (`web/static.js`). `check_site.py` fails a build that reads `?pyodide=` without a same-origin check. | **Built (release branches, not yet merged)** |
| The demo build itself | Ship a key, call a third party, or let injected script run | `tools/check_site.py` scans every text file in `site/` and inside `charlie.zip` for key patterns (`sk-ant-`, `AKIA`, GitHub `gh?_`, Slack `xox?-`) and for any URL host outside an allowlist (the Pyodide CDN, chaseholroyd.com, the SVG namespace; `--no-cdn` drops the CDN), and checks the vendored `pyodide/` folder holds only the expected runtime files. It runs in CI and in `pages.yml`. | **Built** |
| The demo build itself (script injection, third-party loads) | Run inline or third-party script in visitors' browsers | A meta CSP: `default-src 'self'`, scripts and fetches from `'self'` plus `'wasm-unsafe-eval'` (and jsDelivr only in the CDN test build), `object-src 'none'`, `base-uri 'none'`, no `'unsafe-inline'` (`build_demo.csp()`). `check_site.py` fails a build with a missing or looser CSP. The public build self-hosts Pyodide, fetched with `npm pack` (integrity-checked) in `pages.yml`. | **Built (release branches, not yet merged)** (CSP and its check); **Built** (self-hosting) |
| Anyone reading the repo once it's public | Find a key, a real email, a real resume or the owner's data | CI's privacy step fails on `sk-ant-…`, `AKIA…` and any email outside the placeholder allowlist (`.github/workflows/ci.yml`). `data/` and `.env` are gitignored (and `*.db*` files anywhere, on the release branches); `samples/` holds fictional people only; secrets come only from environment variables. A full pre-public review is a gate (PLAN M1.5). | **Built**; the review is **Planned** (PLAN M1.5) |
| Anthropic, as a vendor | Read what Charlie sends it | The resume read needs an explicit, unchecked-by-default opt-in and a key; chat uses Claude only with a key set; the demo never calls it (`charlie/llm_profile.py`, `charlie/chat.py`, `charlie/browser.py`). | **Built** |
| Logs | Keep a copy of the resume | No code logs resume text; an end-to-end test checks the server's logs never hold resume lines (`tests/test_harden.py`). | **Built (release branches, not yet merged)** |
| The user acting on output as advice | Lose real money on a misunderstood idea | Paper trading only, no broker code; "Not financial advice. Paper trading only." added by code on every trade surface and chat reply (`charlie/strategies.py`, `charlie/chat.py`); no uncovered calls, 0DTE or same-week expirations; every trade shows max loss, breakeven and an exit plan; familiarity changes rank, never size. | **Built** |

## Not defended yet

- **No authentication.** Any process on the user's machine can call the local API; there is no login. That is by design for a single-user 127.0.0.1 app, and CLAUDE.md forbids a LAN or hosted deploy until auth and Origin checks exist. Closes with: auth plus Origin checks before any hosted version (Later in HANDOFF).
- **SQLite is unencrypted at rest.** `data/charlie.db` is a plain file readable by the user's account, backups and anything with disk access. `secure_delete` and `VACUUM` help on delete only. Closes with: SQLCipher or OS-keychain-backed encryption, an architect decision (not planned).
- **Requests with no Origin header are allowed.** Browsers send Origin on cross-site writes, so this doesn't open CSRF, but any local non-browser client (curl, a script, another app) can write. Closes with: auth, or a per-session token the page sends on every write.
- **Cboe's delayed-quotes endpoint is unofficial.** It's public and keyless but undocumented; it can change, rate-limit or disappear, and Cboe sees which tickers the user requests and from which IP. Charlie falls back to labeled demo data. Closes with: a licensed data vendor (architect).
- **Claude chat has no opt-in of its own.** Setting the key turns it on, and tool results (profile summary, keyword evidence, holdings, portfolio summary) reach Anthropic. Closes with: a chat disclosure line and an explicit key check before the resume read (CHL-PS9, deferred).
- **The demo keeps pasted resume text in `localStorage`** until the visitor resets or deletes (CHL-PS10, deferred).
- **Dependency pinning.** No hashed lock file or `pip-audit` in CI yet (CHL-PS13, deferred to architect).

Last checked against code: 2026-10-28, branch `claude/project-thread-hpanpa-blocks` (6c91015)
