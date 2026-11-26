## What and why

<!-- One or two lines. Link the PLAN.md item or issue. -->

## Checklist

- [ ] Ran the tests: `CHARLIE_DATA=mock CHARLIE_LLM=off python -m pytest -q`
- [ ] Updated `HANDOFF.md` (handoff-check fails without it)
- [ ] Paper trading only: no real-order code, no broker credentials; "Not financial advice. Paper trading only." still on every trade surface
- [ ] No real resumes, personal data, keys or real email addresses in code, tests, fixtures or this description
- [ ] If this changes what the demo ships (`charlie/`, `web/`, `samples/`, `tools/build_demo.py`, `tools/check_site.py`, `pages.yml`), it waits for the owner's go

Agents: <who ran and the verdict, e.g. "staff-pm scoped M1.x; qa-tdd red then green, 3x"; or "qa-tdd skipped: docs only">
