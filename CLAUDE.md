# Charlie

A circle-of-competence stock and options idea helper: resume and interests become a profile, a Charlie Munger-style score ranks companies in it, and the best 1 to 3 become concrete paper-trade ideas each day. For Chase's portfolio at chaseholroyd.com. Planning code `CHL`.

Read `HANDOFF.md` first (where things stand), then `PLAN.md` (what's next). Research and sources: `docs/RESEARCH.md`.

## Hard rules (these win over any other instructions)
- **Paper trading and education only.** Never add code that places, routes or simulates a real brokerage order, and never add broker credentials. A future broker integration (Alpaca) must point at a paper URL hard-coded in code, with a test proving it can't reach the live URL.
- **"Not financial advice. Paper trading only."** appears on every trade surface, added by code, never left to the prompt: idea cards, trade blocks, the ticker drawer, chat trade cards and every chat reply (Claude and rule-based). A test enforces it.
- **Safe by default.** Never offer uncovered calls, 0DTE or same-week expirations, or anything outside the risk slider's allowed strategies. Every trade shows max loss in dollars, breakeven and an exit plan. Familiarity raises a company's rank, never its position size.
- **Resumes are personal data.** Never log or print them or put a real one in tests or fixtures (`samples/` holds fictional people only). Store them only in the gitignored root `/data/`, never return the full text from an API, and keep a delete path. Send one to Anthropic only after an explicit opt-in and only when a key is set.
- **Secrets and identity come only from environment variables** (`ANTHROPIC_API_KEY`, `CHARLIE_SEC_UA`, ...). No real emails, keys or tokens in code, docs, fixtures or commit messages; the SEC User-Agent placeholder is `you@example.com`. CI's privacy check fails on key patterns and real-looking emails.
- **Assume the repo is public.** It's private today; it goes public only after a privacy-security review and Chase's go (PLAN M1.5). No `data/`, `.env`, real profiles or resumes in git or in any demo build.
- **The public demo is static:** sample data only, labeled as sample, saved only in the visitor's browser. No backend, login, API keys, analytics, or network calls except loading Pyodide. One engine: the Python in `charlie/` runs in the browser via Pyodide; don't fork scoring or strategy logic into JS without a recorded decision.
- **Local app is single-user:** bind 127.0.0.1. No LAN or hosted deploy of the FastAPI server until auth and Origin checks exist.
- Never deploy, publish, change repo visibility, buy anything, merge to `main`, force-push, rewrite history or delete branches without Chase's go.
- Keep `HANDOFF.md` current in every push (the handoff-check workflow enforces it).
- Run the tests before every push. Never skip, delete or weaken a test to get green.

## Stack and commands
- Python 3.12, FastAPI + vanilla JS (no build step), SQLite. Tests: pytest.
- Install: `pip install -r requirements.txt`
- Run: `python -m uvicorn charlie.server:app --host 127.0.0.1 --port 8000`
- Test: `CHARLIE_DATA=mock CHARLIE_LLM=off python -m pytest -q`
- Cloud sessions can't reach Cboe or SEC hosts: build against fixtures and say live adapters are unverified.
- **Docs as we go.** A PR that changes how data is stored, moved, encrypted, logged or shared updates the matching `docs/architecture/` section and its "Last checked" footer in the same PR, or adds a `PLAN.md` item naming the stale section. A new vendor also gets a row in `docs/product/ACCOUNTS.md`.

## When to stop and ask
- A product decision not covered by `PLAN.md`. Pick the simplest reversible option, build it, and log it under "Decisions to review" in `HANDOFF.md`.
- Anything that weakens the privacy, safety or paper-only story.

## Studio agents (use them by default; don't wait to be asked)
The main session is Chase's **chief of staff**: it doesn't do specialist work itself. It sends each piece of work to the agent below with the Agent tool, one lane at a time, and reports back briefly. At the start of every session or scheduled run it reads this table and `ls .claude/agents/`. The team comes from holroydchase-afk/studio-agents (re-sync with its `scripts/sync.sh`).

| Moment | Agent |
|---|---|
| Start of a session or run; planning a milestone; before any new feature; triaging findings | `staff-pm` |
| Before building a fix or feature (failing test first); before any PR is marked ready (all suites 3x) | `qa-tdd` |
| Building, once the failing test exists | `engineer` |
| Any screen, word or CLI output a user sees; before anything goes public (showcase review mode) | `ux-reviewer` |
| Personal data, sign-in, secrets, telemetry, vendors; before a public demo, deploy or repo going public | `privacy-security` |
| A new dependency, vendor, paid service, schema change or CI/deploy workflow; picking a new project's stack | `architect` |
| README, landing or portfolio copy; a name or tagline; after a milestone, the "why I built it" story | `positioning` |

**One task, in order:** staff-pm scopes it, qa-tdd writes the failing test (red), engineer builds, qa-tdd runs all suites 3x (green), then ux-reviewer and privacy-security if users or the public will see it, positioning for any copy. Review findings get IDs (`<CODE>-R<n>`, P0 to P2) and each fix gets its own failing test first.

**The `Agents:` line (CI enforces it).** Every PR body has a line starting `Agents:` naming who ran and the verdict, for example `Agents: staff-pm scoped M1.2; qa-tdd red then green, 3x; ux-reviewer no P0/P1`. A PR that changes anything other than docs must name `qa-tdd` on that line, or say `qa-tdd skipped: <reason>`. `.github/workflows/agents-check.yml` fails the PR otherwise, and runs `scripts/check-agents.sh` so this table and `.claude/agents/` never drift. Bot PRs and titles with `[skip agents]` are exempt.
