# Lessons

Post mortems, newest first. Write one after any lost evening, broken demo or wrong call. Read this before picking a version or calling a build ready (studio-agents `docs/studio-standard.md`, section 3).

Each entry: what happened, why, and the rule or guard it added. Cite the PR, commit or finding ID.

## 2026-10-31: Playwright couldn't install its browser on the new ubuntu-latest (PR #29, PR #36)
- **What happened.** CI's e2e job broke when `ubuntu-latest` moved to Ubuntu 26.04. Playwright 1.56.0 had no browser build for it.
- **Why.** The runner image moved under us, and the Playwright version was older than the OS.
- **Stopgap.** PR #29 pinned the job to `ubuntu-24.04` (commit b13486e).
- **Fix and guard.** PR #36 upgraded to Playwright 1.64.1, whose browser registry includes 26.04, and removed the pin. `tests/test_harden.py::test_e2e_job_runs_on_latest_ubuntu_with_supported_playwright` fails if the job is pinned again or Playwright drops below 1.64.
- **Rule.** A runner pin is a stopgap. Upgrade the tool instead, and add a test that keeps it upgraded.

## 2026-10-31: Dependabot bumps conflict one by one (PR #14, PR #37)
- **What happened.** On Oct 25 to 26, #5, #8 and #13 conflicted or hadn't run CI. On Oct 31, #30 to #34 all edited neighboring lines of `requirements.txt` and conflicted with each other. The handoff check also fails on every Dependabot PR, since they don't touch HANDOFF.md.
- **Why.** Each bump is its own PR against the same few lines.
- **Rule.** Apply a batch of bumps in one PR (#14, then #37) and close the originals as superseded. Expect the handoff check to fail on raw Dependabot PRs.

## 2026-10-30: CI never ran a browser test it looked like it ran (CHL-R3, PR #29)
- **What happened.** `test_CHL_PS1_e2e_pyodide_param_never_reaches_another_host` sits in `tests/test_harden.py` and needs `CHARLIE_E2E=1`. The pytest job doesn't set it, and the e2e job only collects `tests/e2e`. So the test skipped everywhere in CI. Running it in the same process as `tests/e2e` then failed, because Playwright refuses a second sync loop.
- **Why.** A gated test outside `tests/e2e` falls between the two jobs, and a skip looks like a pass.
- **Guard.** The e2e job runs that test by node id in its own pytest process. `tests/test_harden.py::test_CHL_R3_ci_e2e_job_runs_every_browser_gated_test_outside_tests_e2e` fails if any `CHARLIE_E2E`-gated test outside `tests/e2e` isn't named there.
- **Rule.** Every gated test must be named by a CI job, and a test checks it.

## 2026-10-29: Agent runs can't be checked by name in cloud sessions
- **What happened.** `scripts/check-agent-runs.sh` was installed but not added to `agents-check.yml`.
- **Why.** In cloud sessions the studio agents aren't registered Agent types. They run as `general-purpose`, and the hook logs that name, not `qa-tdd`. Turning the step on would fail every PR whose `Agents:` line names qa-tdd.
- **Rule.** Leave the step off until project agents load as real Agent types, or the hook reads the agent name from the prompt. The `Agents:` line check still runs. (HANDOFF "Decisions to review", Oct 29.)

## 2026-10-29: Pages could deploy from a fork PR (CHL-PS17, PR #27)
- **What happened.** `pages.yml` deployed after any successful CI run whose head branch was named `main`. A fork PR from its own branch called `main` qualified.
- **Why.** The trigger checked the branch name, not where the run came from (OWASP CICD-SEC-4).
- **Guard.** Deploys now also need a `push` event from this repository. `tests/test_pages.py::test_CHL_PS17_a_fork_pull_request_from_a_branch_named_main_does_not_deploy` covers it. The weekly rebuild is gated on `github.repository` too, so forks never deploy.
- **Rule.** A deploy workflow checks event type and repository, never just a branch name.

## 2026-10-29: The repo was public before the go
- **What happened.** The review found the repo already public, since at least Oct 28 14:26Z when Pages first deployed. The go to make it public (PLAN M1.5 part 2) was still listed as Chase's.
- **Why.** The repo doesn't record how visibility changed. `pages.yml` was built to skip while private, so it deployed as soon as the repo flipped.
- **Damage.** None found. The full-history review (Oct 24) and the pre-public demo review (Oct 28, GO) had already run. The one exposure was the author email (next entry).
- **Rule.** CLAUDE.md: assume the repo is public, and never change visibility without Chase's go. Chase was asked to confirm it was intended (HANDOFF "Decisions to review").

## 2026-10-29: Personal email in commit authors (CHL-PS16)
- **What happened.** 23 commits carry Chase's personal email as author: his 2 original commits plus 21 merges made in GitHub's web UI.
- **Why.** Web-UI merges use the account's email unless GitHub's email privacy setting is on. The CI privacy check scans files, not commit metadata.
- **Rule.** History is left as is (CHL-DEC-10). Chase turns on "Keep my email addresses private" and "Block command line pushes that expose my email" (HANDOFF "Blockers"). Until then, every web-UI merge adds another.

## 2026-10-28: Risk math crashed on edge inputs (CHL-RM1 to RM8, PR #23, PR #24)
- **What happened.** New golden-value tests found 8 real bugs. Zero or negative spot, strike or IV crashed `bs_price`, `greeks` and `prob_above`. `build('shares')` crashed on zero capital or price. Crossed quotes counted as liquid, and a missing bid or ask crashed `_liquid`.
- **Why.** The math was tested against its own output, and edge inputs weren't covered.
- **Guard.** `tests/test_risk_math.py` (RM1 to RM34) checks hand-derived answers. The bugs were strict xfails until PR #24 fixed them.
- **Rule.** The qa-tdd risk math checklist in `docs/eng/AGENT-NOTES.md` (CHL-DEC-8).

## 2026-10-28: A test-only override was a P0 in the public build (CHL-PS1)
- **What happened.** `web/static.js` read `?pyodide=` from the URL, so a shared link could load another site's script on the demo's origin and read what the visitor saved.
- **Why.** A local testing shortcut shipped in the public build.
- **Guard.** The override was removed. The built `index.html` carries a strict Content-Security-Policy, and `tests/test_harden.py` checks both (CHL-PS1 tests). Review: `docs/reviews/2026-10-28-hardening-privacy.md`.
- **Rule.** No debug or test overrides in shipped code. Tests self-host instead.

## 2026-10-28: First live Cboe run found bugs fixtures hid (PR #15)
- **What happened.** The adapter's first live run (CHL-DEC-5) showed thin weekly chains, so cash-secured puts and put spreads never appeared. One unknown symbol's 403 took all live data offline for 5 minutes. Prices were cached forever in a running server.
- **Why.** The adapter had been built only against fixtures.
- **Guard.** `tests/test_cboe_live.py` runs on a trimmed real response in `tests/fixtures/cboe/`.
- **Rule.** CLAUDE.md: say live adapters are unverified until they've run live. SEC is still unverified.

## 2026-10-23: `charlie/data/` never reached git (M0.2)
- **What happened.** The `.gitignore` rule `data/` also matched `charlie/data/`. The market data package never reached git or the project zip, and every import failed on a clean clone.
- **Why.** An unanchored ignore pattern meant for the root data folder.
- **Cost.** M0.2 rebuilt the package from the tests and callers (commit 028492e). The mock numbers differ from the Oct 22 screenshots.
- **Guard.** The ignore rule is now `/data/`. CI runs pytest on a clean checkout, so a missing package fails the build.
- **Rule.** Anchor ignore rules, and judge "it works" from a clean clone, not the working folder.
