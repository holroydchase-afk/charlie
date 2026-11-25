# Spec: public repo standards (intake #61)

Planning ID: `CHL-M1.18`. One docs/config PR. It touches no demo build path (`charlie/`, `web/`, `samples/`, `tools/build_demo.py`, `tools/check_site.py`, `pages.yml`), so it merges on green. It adds a test, so it is not docs-only: qa-tdd runs red first, then 3x green.

## Bet
A recruiter or engineer who lands on github.com/holroydchase-afk/charlie sees a repo that looks maintained and careful: the paper-only line first, the usual community files, templates, a description and topics, and a root that isn't cluttered. Signal: the studio-agents repo-standards scorecard shows no fails, and every CHL-RS criterion below passes.

## Today (scorecard from the intake, checked in this tree Nov 25)
- Pass: README, LICENSE (MIT), `.github/dependabot.yml`, CI (`ci.yml`, badge on README line 3).
- Fail: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`, repo description, topics.
- README opens with `# Charlie`, the CI badge, then the tagline. The paper-only line is a blockquote on line 7 and reads "Education and paper trading only ... not financial advice", not the exact rule text.
- README still says "Try the demo: coming soon". The demo has been live since Oct 29 (PLAN M1.6), so this is stale.
- Root holds `CLAUDE.md`, `HANDOFF.md`, `PLAN.md` and `spike/`.

## Root clutter: what moves and what stays
- **`CLAUDE.md` stays.** Claude Code reads it only from the root.
- **`HANDOFF.md` stays.** `handoff-check.yml` and `scripts/check-handoff-status.sh` look for it at the root, and studio tooling (STUDIO-STATUS, the orchestrator) reads it there.
- **`PLAN.md` stays for now.** `CLAUDE.md` sends every session to it, `tests/test_hunch.py` cites it, and studio tooling this session can't read (studio-agents) may expect it at the root. The three files also show how Chase works, which helps on a PM portfolio. Moving it is a decision for Chase (below). If he says move, it is a separate PR: `git mv PLAN.md docs/internal/PLAN.md` and every reference updated in the same PR.
- **`spike/` moves to `tools/spike/`.** M1.1 is done; the spike is finished. It is code, not a doc, and it is still used: `tools/build_spike.py` builds it and `tests/test_demo.py::test_spike_zip_holds_everything_the_demo_imports` checks the demo imports. Update `tools/build_spike.py`, `studio-checks.json` (`logs.roots`), the comment in `tests/test_studio_checks.py`, and the `spike/` mentions in `HANDOFF.md` and `docs/decisions/engine-in-browser.md`. Move, never delete.

## Acceptance criteria
| ID | Given / When / Then | Type |
|---|---|---|
| CHL-RS-1 | Given the repo root, when the test lists it, then `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and `SECURITY.md` exist and are not empty. | auto |
| CHL-RS-2 | Given `README.md`, when the test reads it, then the first non-blank line after the `# Charlie` heading contains exactly "Not financial advice. Paper trading only." | auto |
| CHL-RS-3 | Given `README.md`, then it still has the CI badge linking to `actions/workflows/ci.yml`, and `LICENSE` and `.github/dependabot.yml` still exist. | auto |
| CHL-RS-4 | Given `.github/ISSUE_TEMPLATE/`, then it holds a bug report and an idea template (`.md` or `.yml`) and a `config.yml`. | auto |
| CHL-RS-5 | Given `.github/pull_request_template.md`, then it has a line starting `Agents:` and a reminder to update `HANDOFF.md` and run the tests, so it matches agents-check and handoff-check. | auto |
| CHL-RS-6 | Given `SECURITY.md` and `CODE_OF_CONDUCT.md`, then neither holds an email address; reports go through GitHub private vulnerability reporting. The CI privacy check passes. | auto |
| CHL-RS-7 | Given the root, then `spike/` is gone and `tools/spike/index.html` and `tools/spike/spike.js` exist; `test_spike_zip_holds_everything_the_demo_imports` and the `check-logs` run over `studio-checks.json` roots still pass. | auto |
| CHL-RS-8 | Given the repo, then `CLAUDE.md`, `HANDOFF.md` and `PLAN.md` are still at the root, and no file or workflow points at a path this PR moved. | auto |
| CHL-RS-9 | Given README, CONTRIBUTING and SECURITY copy, when positioning checks it against `docs/product/MARKETING.md`, then every claim is "OK to say" there, and the "coming soon" demo line is replaced by the live link. | manual (positioning) |
| CHL-RS-10 | Given CONTRIBUTING.md, then it says the project is paper trading and education only, that PRs adding real-order or broker-credential code are declined, and that resumes and personal data never go in issues, tests or fixtures. | auto (phrases) + manual (positioning) |
| CHL-RS-11 | Given GitHub settings, then the repo has a one-line description and 4 to 8 topics. | manual (Chase's go, see below) |

Tests go in `tests/test_repo_standards.py` (CHL-RS-1 to 8, 10).

## In scope (this PR)
- Minimal `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1, enforcement via GitHub's private reporting, no email), `SECURITY.md` (supported version: `main`; report privately; what's in scope: the local app and the static demo), issue templates, PR template. Written from GitHub conventions; studio-agents PR 132 has ready-made versions this session can't read, so re-sync from it later.
- README: the rule line first, the live demo link, nothing else rewritten.
- `spike/` to `tools/spike/` with every reference updated.
- `tests/test_repo_standards.py`.

## Not in scope (and why)
- Moving `CLAUDE.md` or `HANDOFF.md`: tooling and CI need them at the root.
- Moving `PLAN.md`: waits for Chase's call and a check of studio-agents tooling paths.
- A README rewrite or new claims: positioning only fixes what's stale; new claims need a MARKETING.md row first.
- Copying studio-agents PR 132 files verbatim: not readable from this session. Swap them in on the next studio sync.
- Changing repo description, topics or private vulnerability reporting from this PR: they are GitHub settings, not files.

## Only Chase (or a tool on his go)
- **Description and topics.** GitHub settings. A session can set them with `gh api -X PATCH repos/holroydchase-afk/charlie -f description=...` and `gh api -X PUT repos/holroydchase-afk/charlie/topics`, if its token has admin rights, so Chase only says go. Proposed description: "Circle-of-competence stock and options idea helper. Paper trading and education only." Topics: `paper-trading`, `options`, `investing-education`, `pyodide`, `fastapi`, `python`.
- **Private vulnerability reporting.** Same route: `gh api -X PUT repos/holroydchase-afk/charlie/private-vulnerability-reporting` on his go; otherwise one toggle under Settings, Code security.
- **PLAN.md move.** Recommendation: keep it at the root.

## Handoffs
- qa-tdd: `tests/test_repo_standards.py` red for CHL-RS-1 to 8 and 10. Done when it fails on this tree for the right reasons.
- engineer: the files, the README line, the spike move. Done when the tests pass.
- qa-tdd: all suites 3x green, `check-logs` and the privacy check included.
- positioning: CHL-RS-9 and 10 against MARKETING.md. privacy-security: SECURITY.md and CODE_OF_CONDUCT.md contact wording (CHL-RS-6).

Last checked: 2026-11-25.
