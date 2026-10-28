# System overview

_What Charlie is made of, which vendors it uses, and where each piece of data lives. Rules and status labels: [README](README.md)._

Charlie turns a resume and interests into a "circle of competence" profile, ranks companies in it with a Charlie Munger-style score, and proposes 1 to 3 paper-trade ideas a day. It is for paper trading and education only: no code places, routes or simulates a real brokerage order. It runs in two modes that share one Python engine:

- **Local app**: a single-user FastAPI server bound to 127.0.0.1, with a SQLite file on the user's own disk.
- **Static demo**: the same Python running in the visitor's browser through Pyodide (CPython compiled to WebAssembly), on fictional sample data, with no backend.

## Components

| Component | What it does | Where it runs | Status |
|---|---|---|---|
| Local server | Thin FastAPI wrappers around the shared handlers, plus file upload and the optional Claude resume read (`charlie/server.py`). Run with `--host 127.0.0.1`. | User's machine | **Built** |
| Request guard, `LocalOnly` | Pure ASGI middleware: loopback-only Host, Origin and port check on writes, 9 MB body cap, security headers and a page CSP (`charlie/server.py`). Replaces the older same-origin middleware that is in `main`. | User's machine | **Built (release branches, not yet merged)** |
| Shared handlers, `Api` | Every endpoint's logic, called by the server and by the demo's in-browser router `Api.route()` (`charlie/handlers.py`). | User's machine or visitor's browser | **Built** |
| Engine | Profile building (`charlie/profile.py`), scoring (`charlie/scoring.py`), strategy picking (`charlie/strategies.py`, `charlie/options_math.py`), daily ideas (`charlie/engine.py`), paper P&L (`charlie/portfolio.py`), the ticker universe (`charlie/universe.py`). | Both | **Built** |
| Market data facade | `auto` / `mock` / `live` modes (`CHARLIE_DATA`), per-call fallback to labeled demo data, an on-disk cache and a 5-minute offline backoff (`charlie/data/market.py`). | User's machine (mock only in the demo) | **Built** |
| Cboe adapter | Delayed quotes, option chains and daily history from Cboe's public delayed-quotes endpoint (`charlie/data/cboe.py`). Verified live from the cloud on Oct 28. | User's machine | **Built** |
| SEC EDGAR adapter | XBRL company facts (`charlie/data/sec.py`). Refuses to run until `CHARLIE_SEC_UA` is set to something other than the `you@example.com` placeholder. Not yet verified live. | User's machine | **Built** (unverified live) |
| Mock data | Deterministic demo prices, chains and fundamentals (`charlie/data/mock.py`). | Both | **Built** |
| Store | SQLite: key-value table (profile, resume intake), saved screens, daily idea snapshots, paper positions (`charlie/store.py`). | User's machine | **Built** |
| Optional Claude | Chat with tools (`charlie/chat.py`) and a resume read for implied industry knowledge (`charlie/llm_profile.py`), through the Anthropic API. Off unless a key is in the environment; never in the demo. | User's machine to Anthropic | **Built** |
| Web UI | One vanilla-JS single-page app shared by both modes (`web/index.html`, `web/app.js`, `web/styles.css`). | Browser | **Built** |
| Demo runtime | `web/static.js` loads Pyodide and `charlie.zip` and serves the app's API calls in the browser; `charlie/browser.py` is the Pyodide entry point (mock data, rule-based chat, no network or Claude imports); `charlie/browser_store.py` (`BrowserStore`) stores data in `localStorage`. | Visitor's browser | **Built** |
| Demo build | `tools/build_demo.py` writes `site/`: the web files, a zip of only the modules the browser needs, `prebuilt.json` (the sample person's answers for every risk level, so the first screen needs no engine), and optionally a self-hosted Pyodide copy. | CI | **Built** |
| Demo meta CSP | `build_demo.csp()` writes a strict Content-Security-Policy into the built `index.html`. | Visitor's browser | **Built (release branches, not yet merged)** |
| Demo checker | `tools/check_site.py` scans the built `site/` and `charlie.zip` for API-key patterns and off-allowlist URL hosts. The CSP and `?pyodide=` checks in it are on the release branches. | CI | **Built** (scan); **Built (release branches, not yet merged)** (CSP checks) |
| Publishing | `.github/workflows/pages.yml` builds the self-hosted demo and runs `check_site.py --no-cdn` after CI passes on `main`, only when the repo is public. The repo is private, so it has never deployed. | GitHub Actions | **Built** (inactive); deploy **Planned** (PLAN M1.5, M1.6) |

## Where data lives

| Data | Stored in | Who can read it (us, each vendor) | Status |
|---|---|---|---|
| Resume text (local app) | SQLite `kv` table, key `intake`, in `data/charlie.db` at the repo root (gitignored; `CHARLIE_DB` overrides). At most 50,000 characters kept. | The user's own machine. Not returned by any API: `GET /api/profile` returns only `resume_chars` (`charlie/handlers.py`). Anthropic sees it only on the explicit opt-in (see Vendors). | **Built**; anchoring the default path to the repo root whatever the current directory is **Built (release branches, not yet merged)** (in `main` it is relative to the current directory) |
| Profile (domains, tickers, evidence, capital, risk level, holdings) | SQLite `kv`, key `profile` and `intake` | The user's machine. Anthropic sees parts of it when Claude chat is on (see Vendors). | **Built** |
| Saved screens | SQLite `screens` | The user's machine | **Built** |
| Cached daily ideas | SQLite `daily` | The user's machine | **Built** |
| Paper trades | SQLite `positions` | The user's machine. Anthropic sees a summary when Claude chat calls its portfolio tool. | **Built** |
| Market cache (quotes, chains, history, filings) | JSON files in `data/cache/<kind>/` at the repo root (`CHARLIE_CACHE` overrides); file names are tickers | The user's machine | **Built**; repo-root anchoring is **Built (release branches, not yet merged)** |
| API key, SEC contact string | Environment variables only (`ANTHROPIC_API_KEY`, `CHARLIE_SEC_UA`) | The user's machine; the SEC contact string is sent to the SEC as the User-Agent | **Built** |
| Demo data | The visitor's `localStorage`, keys starting `charlie:` (`charlie/browser_store.py`); kept in memory for the visit if storage is blocked (`web/static.js`) | Only the visitor's browser. No server of ours receives it. | **Built** |

## Vendors

One row per outside service, matching [`docs/product/ACCOUNTS.md`](../product/ACCOUNTS.md).

| Vendor | When it's used | What it receives | Status |
|---|---|---|---|
| Anthropic API | Local app only, only when `ANTHROPIC_API_KEY` (or an auth token, or `CHARLIE_LLM=on`) is set and `CHARLIE_LLM` isn't `off`. Never in the demo (`charlie/browser.py` forces `CHARLIE_LLM=off`; the router passes `allow_llm=False`). | **Resume read**: only when the user ticks the opt-in (unchecked by default, `use_ai` defaults to false): up to 20,000 characters of resume plus interests and brands (`charlie/llm_profile.py`). **Chat**: the conversation, risk level and capital, and tool results: profile summary, domains with their keyword evidence, top tickers, holdings, ideas, screens and a paper-portfolio summary (`charlie/chat.py`). Not the resume text. | **Built** |
| Cboe (`cdn.cboe.com`) | Local app in `auto` or `live` mode | The ticker symbols requested, from the user's IP address. No account, no key. | **Built** |
| SEC EDGAR (`www.sec.gov`, `data.sec.gov`) | Local app, only when `CHARLIE_SEC_UA` is set | CIK lookups and company-facts requests, with the user's own contact string as User-Agent, from the user's IP. | **Built** (unverified live) |
| npm registry / Pyodide | Build time only: `pages.yml` runs `npm pack pyodide@0.28.3` (integrity-checked) and self-hosts it in `site/pyodide/`. The CDN build used in CI and local testing loads Pyodide from `cdn.jsdelivr.net`. | Nothing about users. A visitor to the self-hosted build calls no third party. | **Built** |
| GitHub (Actions, Pages) | CI on every push; Pages only once public | Code. The demo would be served by GitHub Pages, which sees visitors' requests like any web host. | CI **Built**; Pages **Planned** (PLAN M1.6) |

Last checked against code: 2026-10-28, branch `claude/project-thread-hpanpa-blocks` (6c91015)
