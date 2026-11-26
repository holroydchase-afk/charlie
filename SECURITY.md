# Security policy

## Supported versions

Only `main` is supported. Fixes land there and the live demo redeploys from it.

## Reporting a vulnerability

Please report it privately through GitHub's private vulnerability reporting: open the repository's **Security** tab and choose **Report a vulnerability**. Don't open a public issue, and don't include real personal data (such as a resume) in the report. If that button isn't there, open a short issue that says only "security contact please", with no details, and you'll get a private way to send them.

This is a one-person project, so replies and fixes are best effort.

## In scope

- **The local app** (`charlie/`, `web/`): a single-user FastAPI server bound to 127.0.0.1. Of most interest: anything that leaks a stored resume, sends it anywhere without the opt-in, exposes the server beyond localhost, or leaks a key from environment variables.
- **The static demo** at chaseholroyd.com/charlie/: sample data only, saved in the visitor's browser. Of most interest: anything that makes it call a third party, carry a key, or run untrusted script.

## Out of scope

- Charlie is not a broker and places no real orders, so there is no order or account path to attack.
- Market-data accuracy and investment outcomes. Charlie is for education and paper trading only and is not financial advice.
