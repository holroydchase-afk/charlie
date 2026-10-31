# Data flow

_Each user flow step by step, with what our servers and each vendor see at every step. Rules and status labels: [README](README.md)._

Charlie has no servers of its own. "The local app" is a FastAPI process the user runs on their own machine, bound to 127.0.0.1, storing data in a SQLite file in the gitignored `data/` folder. "The demo" is a static site whose Python engine runs in the visitor's browser through Pyodide (CPython compiled to WebAssembly). So in this file "we" never see user data; the parties that can are the user's machine, the visitor's browser and the vendors named at each step.

## Resume to profile (local app)

1. The user pastes resume text or uploads a PDF, DOCX or text file, adds interests, brands, holdings, capital and a risk level, and saves (`web/app.js`, `POST /api/profile` in `charlie/server.py`). Sees: the user's machine only. **Built**
2. The server refuses any request body over 9 MB before parsing it, and keeps the upload in memory rather than a temp file (`LocalOnly`, `MAX_BODY`, `MultiPartParser.spool_max_size` in `charlie/server.py`). Files over 8 MB are refused after reading. **Built** (8 MB file cap); **Built (release branches, not yet merged)** (9 MB pre-parse cap and in-memory spooling)
3. Text is extracted in a worker thread. A DOCX with over 200 zip members, over 20 MB unpacked or a ratio over 100:1 is refused before python-docx opens it; a PDF is read for at most 30 pages, and refused if those pages' content streams decode to over 2 MB; text stops at 100,000 characters (`extract_text`, `FileTooComplex` in `charlie/profile.py`). A refusal returns 413 with generic text that doesn't echo the file. **Built (release branches, not yet merged)**
4. Capital is checked (finite, over 0, at most 1e9) before anything is stored or sent anywhere (`check_capital` in `charlie/handlers.py`). **Built (release branches, not yet merged)**
5. **Optional Claude read.** Only if the user ticked the opt-in (unchecked by default; `use_ai` defaults to false) and an Anthropic key is set, up to 20,000 characters of the resume plus interests and brands go to the Anthropic API, which returns industry and ticker signals limited to Charlie's own domain keys and universe (`charlie/llm_profile.py`). Sees: Anthropic, for this request. Without the opt-in or the key, nothing leaves the machine. **Built**
6. The rule-based profile builder turns keyword matches (and any Claude signals) into domains, tickers and evidence lines such as `resume mentions "Kubernetes"`, from at most 50,000 characters of resume (`build_profile` in `charlie/profile.py`, `Api.save_profile` in `charlie/handlers.py`). **Built**
7. The profile is stored under `profile`, and the resume text with the other inputs under `intake`, in SQLite (`charlie/store.py`). The response carries the profile and `resume_chars`, never the text; `GET /api/profile` also drops `resume_text` (`Api.get_profile`). **Built**

**What we can see:** nothing; the resume stays on the user's machine unless they opt in to the Claude read, and then Anthropic receives it for that request.

## Daily ideas (local app)

1. The UI asks for today's ideas at the chosen risk level (`GET /api/ideas`); the count is clamped to 1 to 3 (`Api.ideas`). **Built** (clamp: **Built (release branches, not yet merged)**)
2. The engine scores companies in the profile and picks a safe-by-default strategy for each, with max loss in dollars, breakeven, an exit plan and the "Not financial advice. Paper trading only." line added by code (`charlie/engine.py`, `charlie/strategies.py`). Familiarity raises rank, never position size. **Built**
3. Prices: in `auto` or `live` mode the market facade requests delayed quotes, chains and history per ticker from Cboe; fundamentals come from SEC EDGAR only when `CHARLIE_SEC_UA` is set, otherwise from labeled demo numbers. Any failure falls back to labeled demo data, and each idea carries its `price_source` (`charlie/data/market.py`, `cboe.py`, `sec.py`). Sees: Cboe sees the ticker symbols and the user's IP address; the SEC sees CIK lookups, the user's IP and the user's own contact string as User-Agent. **Built** (per-idea `price_source`: **Built (release branches, not yet merged)**)
4. Responses are cached as JSON files under `data/cache/` and the day's ideas in the SQLite `daily` table, keyed by day, risk level and a hash of the profile. **Built**

**What we can see:** nothing; Cboe and, if configured, the SEC see which tickers the user looked up, from the user's IP.

## Paper trades (local app)

1. The user opens a paper trade from an idea, the screener, the ticker drawer or a chat card (`POST /api/paper`). The note is at most 500 characters. The same open trade (symbol, strategy and legs) is refused with 409, and a trade that pushes open max loss over capital comes back with a `warning` (`Api.paper_open` in `charlie/handlers.py`). **Built** (open); **Built (release branches, not yet merged)** (409, warning, note cap)
2. The position is stored in the SQLite `positions` table with its entry value; closing records the exit value at the current (mock or delayed) price (`charlie/store.py`, `charlie/portfolio.py`). No order is placed, routed or simulated with any broker; Charlie has no broker integration or credentials. **Built**

**What we can see:** nothing; paper trades exist only in the user's SQLite file.

## Chat (local app)

1. The user sends a message (`POST /api/chat`); at most 40 messages of at most 4,000 characters each are accepted, and the last 20 are used (`Api.chat`). **Built** (limits: **Built (release branches, not yet merged)**)
2. **Rule-based** (default when no key is set, or `CHARLIE_LLM=off`): answered on the machine (`chat_rules` in `charlie/chat.py`). Sees: nobody. **Built**
3. **Claude** (when a key is set): the conversation, the risk level and capital go to the Anthropic API, and Claude can call tools whose results also go to Anthropic: profile summary, domains with their keyword evidence, top tickers, holdings, daily ideas, ticker analysis, screens and a paper-portfolio summary (`ToolContext.run`, `chat_claude`). The resume text itself is not sent. If the call fails, the rule-based answer is used. **Built**
4. Every reply, from either path, ends with "Not financial advice. Paper trading only." appended by code (`with_disclaimer`), and trade cards carry it too. **Built**

**What we can see:** nothing; with a key set, Anthropic sees the chat and the tool results listed above. There is no separate opt-in for chat beyond setting the key (see the threat model).

## Demo visit (static site)

1. The visitor loads `index.html`, the web files and `prebuilt.json` from the site's own origin. The page carries a meta Content-Security-Policy allowing only its own origin plus WebAssembly (`'wasm-unsafe-eval'`) for scripts and fetches (`build_demo.csp()` in `tools/build_demo.py`). Sees: the static host (GitHub Pages) sees the request, like any web host. **Built** (static files); **Built (release branches, not yet merged)** (CSP)
2. The first screen is the fictional sample person's prebuilt ideas, pinned to the build date (rebuilt every Monday, labeled "Sample market day"), so nothing runs before Today appears (`web/static.js`, `prebuild` in `charlie/browser.py`). A banner says it's sample data and links back to chaseholroyd.com. **Built**
3. After the first render, `web/static.js` loads Pyodide and `charlie.zip`. In the public build both come from the same origin (`site/pyodide/`, self-hosted by `pages.yml`); only the CDN build used in CI and local testing loads Pyodide from `cdn.jsdelivr.net`. There is no URL parameter that changes where Pyodide loads from. **Built** (self-hosting); **Built (release branches, not yet merged)** (the `?pyodide=` override removed)
4. Everything runs in the browser: mock data, rule-based chat, no Claude, no upload, no network imports (`charlie/browser.py`). Anything the visitor saves goes to `localStorage` under `charlie:` keys (`charlie/browser_store.py`), or memory only if storage is blocked. **Built**

**What we can see:** nothing; the demo has no backend, analytics or API keys, and the self-hosted build calls no third party.

## Deletion

| What the user does | What is deleted | Status |
|---|---|---|
| Local app, **Delete my data** (sends `DELETE /api/profile?all=true` after a confirm listing what goes) | Every SQLite table: profile, resume intake, saved screens, cached ideas, paper trades (`Store.wipe`), then `VACUUM` rebuilds the file. `PRAGMA secure_delete=ON` is set on every connection, so deleted rows are overwritten with zeros. The market cache's own folders (`options`, `history`, `facts`, `ciks`) are removed too, since their file names are the tickers the profile pointed to (`Api.delete_profile`, `_clear_market_cache`). | **Built (release branches, not yet merged)** |
| Local app, plain `DELETE /api/profile` | Profile, resume intake, the sample risk setting and cached ideas; saved screens and paper trades stay (`Api.delete_profile`). | **Built** |
| Demo, **Delete my data** | Every `charlie:` key through `BrowserStore.wipe`. | **Built (release branches, not yet merged)** |
| Demo, **Reset demo** (in the demo bar's drawer; asks inline first, Keep changes nothing) | Every `localStorage` key starting `charlie:` (other keys on the shared Pages origin stay), then a reload. A one-shot `sessionStorage` flag, `charlie-demo-reset`, holds no data; it opens the drawer once after the reload to say "Sample data restored." and is removed on read (`web/app.js`, CHL-DEMO-BAR). The `charlie-ack` flag (hyphen, not `charlie:`) stays: it only records that the visitor saw the practice-only notice. | **Built** |

How long copies last:

- **Backups and logs:** Charlie makes no backups and writes no resume or profile text to logs (tests in `tests/test_harden.py` check that the resume never reaches logs). Backups the user's own OS or disk tools make are outside Charlie's control.
- **Gap: file-level copies.** `secure_delete` and `VACUUM` overwrite and rebuild the database file, but SSD wear-levelling, filesystem snapshots or a copied `data/` folder can still hold older bytes.
- **Gap: vendor copies.** Anything sent to Anthropic (opt-in resume read, Claude chat) is retained under Anthropic's API terms, not deletable from Charlie. Cboe and the SEC may log requested tickers and IP addresses.
- **Gap: demo visitors who never delete.** Demo data stays in the visitor's `localStorage` until they reset, delete or clear site data. That includes resume text a visitor pastes (CHL-PS10, deferred: staff-pm to choose session-only storage or not storing it).

Last checked against code: 2026-10-31, branch `claude/project-thread-0rhiwv` (Reset demo row, CHL-DEMO-BAR)
