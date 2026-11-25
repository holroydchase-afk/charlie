# Decision log

Every call Chase makes about Charlie gets an entry here, in the same PR as the call. This is the studio standard (studio-agents `docs/studio-standard.md`, section 3).

Each entry has:
- **ID**: `CHL-DEC-n`, numbered oldest first. Never reuse or renumber an ID.
- **Date** the call was made.
- **The call**, in Chase's words when the repo has them. If it doesn't, the entry paraphrases and says so.
- **Why** he made it.
- **What it beat**: the option he didn't pick.
- **Detail**: a link to the long write-up in `docs/decisions/` when one exists.

Only Chase's calls go here. Product calls an agent makes on its own (the simplest reversible option, per CLAUDE.md) go under "Decisions to review" in `HANDOFF.md` until Chase confirms or reverses them. Once he does, they get an entry here.

## Index of `docs/decisions/`

| File | Topic | Status |
|---|---|---|
| [`engine-in-browser.md`](../decisions/engine-in-browser.md) | Run the engine in the browser with Pyodide or port it to JS (M1.1 spike) | Proposed, needs Chase's call. M1.2 to M1.4 were built on the recommended Pyodide path in the meantime. See "Open calls" below. |

## Decisions

### CHL-DEC-1: Charlie is a real product he'll use, laptop first
- Date: 2026-10-24
- The call: paraphrased (his words aren't in the repo). Charlie is also a real product Chase will use, and his own daily use comes laptop first.
- Why: live data on his laptop is the shortest path to using it every day; a phone version needs hosting and a login first.
- What it beat: a phone or hosted version first (moved after the laptop phase, per CLAUDE.md's "no hosted deploy until auth").
- Evidence: commit 2b311a3 ("Chase picked laptop first"), HANDOFF "Later" and "Decisions to review".

### CHL-DEC-2: Polish Freeze
- Date: 2026-10-24
- The call: paraphrased. No new scope; finish and polish what exists. The "Chase uses it daily" phase was parked minutes after CHL-DEC-1.
- Why: get the recruiter demo to done before adding features.
- What it beat: starting M2 right away.
- Evidence: commit ed132c9 ("Chase's Polish Freeze (Oct 24): no new scope"). Lifted by CHL-DEC-6.

### CHL-DEC-3: Merge PR #2 (M0.1 to M1.9) into main
- Date: 2026-10-25
- The call: paraphrased. Chase approved merging, so PR #2 merged with a merge commit and brought #1 with it.
- Why: PR #2 carried everything through M1.9 with tests green, and the Pages work needed it on main.
- What it beat: keeping the stacked branches open.
- Evidence: commit 8031626, HANDOFF "Exact next step" (Oct 25).

### CHL-DEC-4: "merge dependabot"
- Date: 2026-10-25 to 26
- The call: "merge dependabot" (his words, as quoted in HANDOFF).
- Why: keep dependencies current while the repo is small.
- What it beat: leaving the bumps open. #3, #4, #6, #7, #9, #10 and #12 merged; #5, #8 and #13 conflicted and were applied together in PR #14.
- Evidence: HANDOFF "Exact next step" (Oct 25 to 26), commit c0ae97d.

### CHL-DEC-5: Allow live Cboe hosts in the cloud environment
- Date: 2026-10-28
- The call: paraphrased. Chase allowed `cdn.cboe.com` and `cdn-api.cboe.com` in the cloud environment.
- Why: the Cboe adapter had only ever run against fixtures; this let a session run it live.
- What it beat: building against fixtures only. SEC hosts are still not allowed, so fundamentals stay demo numbers.
- Evidence: HANDOFF "Done" (Oct 28, live Cboe prices), PR #15.

### CHL-DEC-6: Lift the Polish Freeze; run the Oct 28 release
- Date: 2026-10-28
- The call: paraphrased. Chase lifted the Polish Freeze. The parked work became the release plan M1.10 to M1.15.
- Why: the demo had cleared its reviews; the next goal was Chase running Charlie daily with labels he can trust.
- What it beat: staying frozen. Merges to main still needed his go.
- Evidence: `docs/plans/2026-10-28-release.md`, HANDOFF "Later", PRs #17 to #22.

### CHL-DEC-7: Studio agents by default, main session as chief of staff
- Date: 2026-10-28
- The call: paraphrased. The main session acts as Chase's chief of staff and sends each piece of work to the studio agents without being asked.
- Why: one lane at a time (staff-pm, qa-tdd red, engineer, qa-tdd green 3x, reviewers) keeps quality up on an hour a night.
- What it beat: one general session doing all the work itself.
- Evidence: commit d507232, PR #16, CLAUDE.md "Studio agents".

### CHL-DEC-8: Risk math checklist in qa-tdd, not an actuary agent
- Date: 2026-10-28
- The call: paraphrased. Chase chose a risk math checklist inside qa-tdd over a separate actuary agent, for now.
- Why: one checklist plus golden-value tests covers the risk math without a new agent to keep in sync.
- What it beat: a dedicated actuary agent. Revisit once Charlie suggests sizes Chase actually trades.
- Evidence: HANDOFF "Done" (risk math checklist), PR #23, `tests/test_risk_math.py`. The checklist now lives in [`docs/eng/AGENT-NOTES.md`](../eng/AGENT-NOTES.md).

### CHL-DEC-9: Public repo and live demo
- Date: 2026-10-29
- The call: paraphrased. Charlie is public and the demo goes live at chaseholroyd.com/charlie/, through Product Studio's intake (PLAN M1.5 and M1.6).
- Why: Pages needs a public repo, and the demo is the portfolio piece.
- What it beat: staying private. Note: the repo was found already public before this was confirmed (see `docs/eng/LESSONS.md`), and HANDOFF still lists Chase's confirmation that it was intended as asked.
- Evidence: PLAN M1.5 ("Chase decides to make the repo public", ticked), HANDOFF "Done" (Oct 29), PR #27.

### CHL-DEC-10: Leave the author email in history (CHL-PS16)
- Date: 2026-10-29
- The call: paraphrased, and the repo doesn't record Chase making it (privacy-security recommended it; HANDOFF says "accepted as is"). Accept the personal email on commit authors as is, with no history rewrite (23 commits on Oct 29; 38 as of Nov 25, `docs/reviews/2026-11-25-public-repo-privacy.md` CHL-PS-P2, because GitHub's email privacy setting is still off). Treat as provisional until Chase confirms.
- Why: the repo is already public, and a rewrite changes every SHA and needs a force-push.
- What it beat: rewriting history. Still open: Chase ticks GitHub's email privacy settings so new web merges don't add more (HANDOFF "Blockers").
- Evidence: HANDOFF "Done" (Oct 29) and "Blockers", `docs/reviews/2026-10-24-pre-public-privacy.md` finding 1.

### CHL-DEC-11: Merge CHL-R3 (PR #29) and the minus-sign fix with Dependabot #30 to #34 (PR #37)
- Date: 2026-10-31
- The call: paraphrased. Chase gave his go to merge both after all suites passed 3x.
- Why: CI wasn't running one browser test (CHL-R3); the five Dependabot bumps conflict one by one, so they went in one PR.
- What it beat: merging the Dependabot PRs one at a time; #30 to #34 were closed as superseded.
- Evidence: commit 90f99cf ("CHL-R3 merge with Chase's go"), HANDOFF "Exact next step" (Oct 31).

### CHL-DEC-12: Playwright 1.64.1 and e2e back on ubuntu-latest (PR #36)
- Date: 2026-10-31
- The call: paraphrased. Chase gave his go to merge after CI passed on ubuntu-latest.
- Why: upgrading fixes the cause; the ubuntu-24.04 pin from PR #29 was a stopgap.
- What it beat: keeping the runner pinned to 24.04.
- Evidence: commit e63231d ("Playwright upgrade merges with Chase's go"), HANDOFF "Exact next step".

### CHL-DEC-13: Adopt the studio demo bar (intake #35, PR #38)
- Date: 2026-10-31
- The call: paraphrased. The static demo uses the studio demo bar from pm-tools `docs/DEMO-BANNER.md`, merged with Chase's go.
- Why: one demo notice that looks the same across studio projects.
- What it beat: Charlie's own warn-tinted banner.
- Evidence: HANDOFF "Done" (studio demo bar), commit aa28323.

### CHL-DEC-14: Adopt the studio standard (issue #40)
- Date: 2026-11-01
- The call: paraphrased. Charlie adopts studio-agents `docs/studio-standard.md`, including this log, `docs/eng/LESSONS.md` and `docs/eng/AGENT-NOTES.md`.
- Why: every studio repo keeps the same docs, so agents and Chase find things in the same place.
- What it beat: Charlie's own conventions (decisions only in HANDOFF, the qa-tdd addendum inside `.claude/agents/`).
- Evidence: GitHub issue #40.

### CHL-DEC-15: Merge own PRs on green (studio standard section 5)
- Date: 2026-11-02
- The call: Chase's word, "adopt", answering "keep never-merge-without-Chase, or adopt merge-on-green with a live-demo gate?"
- Why: fewer asks of Chase; docs, tests and CI changes don't touch what visitors see.
- What it beat: "never merge to `main` without Chase's go" (CLAUDE.md since Oct 23). A PR that changes what the demo build ships still waits for his go, because every merge redeploys the demo.
- Evidence: the project thread for intake #40; CLAUDE.md "Merging"; PR #41.

## Open calls (waiting on Chase)

These are in HANDOFF "Decisions to review". They get an entry above once he decides.
- **Engine for the static demo.** Pyodide (recommended, and what's built) or a JS port. Detail: `docs/decisions/engine-in-browser.md`.
- **Next feature after M1.** Earnings-date warnings or Alpaca paper orders (recommended: earnings first).
- **Risk math sizing.** Whether shares, cash-secured puts and covered calls should also be capped by `max_risk_pct` (HANDOFF "Oct 28 risk math").

Other asks waiting on him are in HANDOFF "Blockers" (paste the INTAKE blocks, GitHub email settings) and PLAN M1.8 (his edit of "Why I built it").
