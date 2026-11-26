# Contributing to Charlie

Thanks for looking. Charlie is a small portfolio project, so issues and focused pull requests are welcome, and big changes are best raised as an idea issue first.

## Ground rules

- **Paper trading and education only.** Charlie shows example ideas to practice with on paper. Pull requests that add code to place, route or simulate real orders, or that add broker credentials, are declined. A future broker integration must point at a paper URL hard-coded in code, with a test proving it can't reach the live URL.
- **"Not financial advice. Paper trading only."** stays on every trade surface, added by code. Don't remove it or move it into a prompt.
- **Safe by default.** No uncovered calls, no 0DTE or same-week expirations, and every trade shows max loss in dollars, breakeven and an exit plan.
- **Keep personal data out.** Never put a real resume or other personal data in an issue, a test, a fixture, a log or a screenshot. `samples/` holds fictional people only. No API keys, tokens or real email addresses anywhere in the repo.

## How to send a change

1. Fork, then branch from `main`.
2. Install: `pip install -r requirements.txt` (Python 3.12).
3. Write a failing test first, then the change.
4. Run the tests: `CHARLIE_DATA=mock CHARLIE_LLM=off python -m pytest -q`
5. Update `HANDOFF.md` if your change affects where things stand.
6. Open a pull request using the template. CI runs the tests, a privacy check and the demo site check.

## Security

Please don't open a public issue for a security problem. See [SECURITY.md](SECURITY.md).

## Conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
