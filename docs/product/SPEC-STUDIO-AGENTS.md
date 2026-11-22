# Spec: wire Charlie to studio-agents (issue #51)

Branch `claude/project-thread-qs9drd`. One small PR. Docs, scripts and CI only: nothing under `charlie/`, `web/`, `samples/`, `tools/` or `pages.yml`, so no live demo change and it merges on green.

## Bet
Chase can trust the `Agents:` line: every agent it names really ran, and in cloud threads (where agents run as `general-purpose`) that is still provable. Signal: the next code PR's `Agents:` line shows `qa-tdd red then green` and agents-check passes against a committed `.claude/agent-runs/<branch>.log` with no hand edits.

## In scope
1. Run studio-agents `scripts/sync.sh` and `scripts/install-rules.sh`. Expected: `ux-reviewer.md` updated, new `release-captain.md`, new `scripts/agent-prompt.sh`.
2. Hand-merge the "kept existing" files from `templates/`:
   - `scripts/log-agent-run.sh`: add the `--as <agent>` mode.
   - `scripts/check-agent-runs.sh`: accept `<agent> via-general-purpose` lines.
   - `.github/workflows/agents-check.yml`: add the "qa-tdd cannot be skipped" step logic and the "Agents line matches the run log" step. Keep `actions/checkout@v7`.
   - Keep as is: `handoff-check.yml` (only checkout@v7 vs v4), `studio-checks.json` (repo-specific; `agents.verify` already set, runs 3).
3. Replace CLAUDE.md's "Studio agents" section with `templates/CLAUDE-agents.md`. No project-only rows exist (story-keeper is in the template). This removes the "not wired yet" note.
4. HANDOFF.md: close the two "run-log CI step not wired" items under Decisions to review; add a status line. `docs/eng/LESSONS.md`: note the lesson is resolved by `--as`.
5. Never hand-edit `.claude/agents/` or `.claude/agent-runs/`.

## Acceptance criteria (qa-tdd: pytest in `tests/test_studio_checks.py`)
- **SA-1 (auto)** Given the repo root, when `bash scripts/agent-prompt.sh qa-tdd "test"` runs, then it exits 0 and stdout contains `You are acting as the studio agent qa-tdd`, `log-agent-run.sh --as qa-tdd` and ends with `test`.
- **SA-2 (auto)** Given an unknown agent (`ghost`) or a bad name (`../x`), when `agent-prompt.sh` runs, then it exits non-zero.
- **SA-3 (auto)** Given a temp git repo on branch `feat/x` with `.claude/agents/qa-tdd.md`, when `log-agent-run.sh --as qa-tdd` runs, then `.claude/agent-runs/feat-x.log` gains exactly one line matching `^\S+Z qa-tdd via-general-purpose$`.
- **SA-4 (auto)** Given `--as ghost` (no agent file) or `--as "Bad Name"`, then it exits non-zero and writes no log line.
- **SA-5 (auto)** Given a log containing `qa-tdd via-general-purpose` and `BODY="Agents: qa-tdd red then green"`, when `check-agent-runs.sh` runs, then it passes; given a log without qa-tdd, then it fails naming `qa-tdd`. Run it in a temp dir with copied `scripts/` and `.claude/agents/` and no `studio-checks.json`, so it does not rerun the suite (the script has no skip switch).
- **SA-6 (auto)** `.github/workflows/agents-check.yml` contains `qa-tdd cannot be skipped` and runs `scripts/check-agent-runs.sh`, and every `actions/checkout@` is `v7`.
- **SA-7 (auto)** CLAUDE.md contains no `is not wired yet`, contains `scripts/agent-prompt.sh` and `log-agent-run.sh --as`, and its Studio agents section equals `templates/CLAUDE-agents.md` (check via key sentences, since the template is not vendored). Existing `test_agent_roster_matches_claude_md` stays green with `release-captain`.
- **SA-8 (manual)** The PR body's `Agents:` line names staff-pm and qa-tdd (red then green, 3x), and agents-check passes on the PR with the committed log.

## Not doing
- Changing `studio-checks.json`, `handoff-check.yml` or `ci.yml`.
- Any app, demo or `web/` change; README or copy changes.
- Using `release-captain` (no releases here yet; the row is only for roster parity).

## Risks
- **Conflicts with open PRs #49/#50 (restyle/nav).** They touch `web/` and likely HANDOFF.md. This PR touches no `web/` file; HANDOFF.md is the only likely conflict. Keep HANDOFF edits to a new status line plus the two Decisions-to-review lines, and rebase whichever lands second. Merge order: this PR can merge on green before them (docs/CI only).
- **CI cost.** The new step reruns the full pytest suite 3x on every PR (`agents.verify`, runs 3). Accepted: it is the studio rule; watch run time.
- **Self-check.** This PR's own agents-check will run the new step, so its log must already contain staff-pm and qa-tdd `via-general-purpose` lines.
