# INTAKE blocks for Product Studio (2026-10-28)

_From M1.15 (reusable blocks). Chase pastes each block below into Product Studio as its own message. Facts re-checked against branch `claude/project-thread-hpanpa-blocks` on 2026-10-28. Context: [`docs/REUSE.md`](../REUSE.md)._

## INTAKE 1: shared privacy check (studio-agents)

```
INTAKE for Product Studio (from Charlie, 2026-10-28)
Repo: studio-agents
Ask: Ship the studio privacy check as templates/scripts/check-private.mjs, installed by install-rules.sh, with each repo's extra patterns and skips in a "private" section of studio-checks.json, and add API-key patterns to the shared base.
Why: STACK.md lists this block as "Now" with Charlie as a next user, and Charlie's PLAN M1.15 is waiting on it to replace its ad-hoc CI grep.
Facts: The only copy today is pm-tools scripts/check-private.mjs (emails with an allowlist, US phones, claude.ai artifact links, trig_ ids, Gmail links, optional PRIVATE_DENYLIST file outside the repo, --staged for a pre-commit hook); it has no API-key patterns and no per-repo config. studio-agents templates/ and install-rules.sh do not include it. It runs clean on the charlie repo today. Charlie's ci.yml grep checks sk-ant-, AKIA and emails (allowing example.com/org, anthropic.com, noreply) and skips .claude/agents; Charlie's tools/check_site.py also flags gh?_ and xox?- tokens. Node is preinstalled on ubuntu-latest, so no setup-node step is needed (Charlie already runs check-logs.mjs that way).
Done when: install-rules.sh installs scripts/check-private.mjs and a studio-checks.json "private" section; the base catches sk-ant-, AKIA, gh?_ and xox?- keys; it has a test; /onboard refresh lists it so Charlie can swap its grep in its own PR.
```

## INTAKE 2: pre-public-demo check (studio-agents privacy-security agent)

```
INTAKE for Product Studio (from Charlie, 2026-10-28)
Repo: studio-agents
Ask: Add one line to the privacy-security agent's pre-public-demo checks: scan the built demo output (not just the repo) for API keys and for URL hosts outside an allowlist, ship a Content-Security-Policy with no third-party hosts, and self-host runtimes instead of loading them from a CDN.
Why: A static demo can leak through its build output and third-party loads even when the repo is clean; Charlie found and closed this, and the other studio demos (pm-tools demo, portfolio, Crew Clock) go public the same way.
Facts: Charlie's tools/check_site.py (on main, 62 lines, stdlib Python) scans every text file in the built site/ and inside the zipped package for key patterns and off-allowlist hosts, and runs in CI and in pages.yml (--no-cdn). Charlie's pages.yml self-hosts Pyodide via npm pack (integrity-checked). The demo's meta CSP (build_demo.csp()) is on Charlie's M1.12 branch, not yet in main. The privacy-security agent today covers secrets in the repo and supply-chain scanning but not built output or third-party loads.
Done when: plugins/studio/agents/privacy-security.md has that check in its pre-public-demo list and sync.sh carries it to each repo.
```

## INTAKE 3: STACK.md facts (pm-tools)

```
INTAKE for Product Studio (from Charlie, 2026-10-28)
Repo: pm-tools
Ask: Update STACK.md "Reusable building blocks" with Charlie's facts: drop Charlie as a next user of the demo kit, add a stack-doc row for the "static demo of a server app" pattern, add Charlie's check_site.py and LocalOnly middleware to "Not extracting yet", and name Charlie's ci.yml and pages.yml as the seed for the Python variant in templates/repo/.
Why: The demo-kit row says Charlie will use fake-db.js, which no longer fits, and the Python ci.yml for templates/repo/ has one working example to copy.
Facts: Charlie's demo stores data with a Python BrowserStore in localStorage (charlie/browser_store.py) and runs its engine in the browser with self-hosted Pyodide 0.28.3; it opens on prebuilt sample ideas, pins data to the build date, and has a sample-data banner, a back link to chaseholroyd.com and a Reset demo button in web/. It does not use window.claude or fake-db.js. Charlie's ci.yml (Python 3.12): pytest, check-agents.sh, check-logs.mjs, privacy grep, demo build and scan, and a Playwright e2e job. Its pages.yml runs on workflow_run of CI on main, deploys only when CI succeeded and github.event.repository.private == false, and checks the build with check_site.py --no-cdn. LocalOnly (loopback Host, Origin and port check on writes, 9 MB body cap, nosniff, frame and cache headers, page CSP) is on Charlie's M1.12 branch, not yet in main. The repo is private and the demo isn't deployed.
Done when: STACK.md's table and "Not extracting yet" line reflect these facts, and the templates/repo/ row names Charlie's ci.yml and pages.yml as the Python seed.
```
