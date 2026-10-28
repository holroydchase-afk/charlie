# Accounts and names

_Template from pm-tools (proved in Hearth), adopted in M1.15._

Every outside account Charlie uses, which login it's under, and where the name "Charlie" is baked in. Use it for a rename, a handover, or moving off a personal email. **No keys, tokens or passwords here, ever**; they live in the environment secrets or the service itself. Name a secret by its variable name only (`ANTHROPIC_API_KEY`), never its value. This repo is written as if public: no project ids, account names or personal emails here; write "owner's personal email", not the address.

**Rule for Claude:** when the owner sets up a new account or a new name, add a row in the same session.

| Service | What it's for | Login | Where "Charlie" is | Rename cost |
|---|---|---|---|---|
| Claude (claude.ai) | Project, cloud environment (names its secrets by variable), published pages | Owner's personal email | Project and environment names, page titles | Easy (rename in settings) |
| GitHub | Code, CI (`ci.yml`, `handoff-check.yml`, `agents-check.yml`), Dependabot, Pages (`pages.yml`, inactive while private) | Owner's GitHub account | Repo name `charlie`, README, workflow names | Easy (GitHub redirects old links) |
| Anthropic API | Optional Claude chat and opt-in resume read, local app only, never the demo | Not set up for the project; the owner's own key, if any, lives only in the local environment as `ANTHROPIC_API_KEY` | Nowhere (no project or app name registered) | Easy |
| SEC EDGAR | Company fundamentals, local app only (`charlie/data/sec.py`) | No account. The SEC asks for a contact in the User-Agent, read only from `CHARLIE_SEC_UA` (placeholder `you@example.com`; live calls refuse while unset or still the placeholder) | The User-Agent's app name, set by the user | Easy |
| Cboe delayed quotes | Delayed quotes, option chains and history, local app only (`charlie/data/cboe.py`) | No account, no key (public, unofficial endpoint) | Nowhere | Easy |
| npm registry (Pyodide) | Pyodide 0.28.3 fetched at build time with `npm pack` and self-hosted in the demo (`pages.yml`); the CDN test build loads it from jsDelivr | No account | Nowhere | Easy |
| chaseholroyd.com/charlie/ | Planned home of the public demo, served by GitHub Pages from this repo; the domain belongs to the owner's portfolio site | The portfolio's existing setup; Pages is off while the repo is private | The `/charlie/` path, the demo's back link | Easy until the demo link is shared |
| Alpaca | Possible future paper-order integration (Chase's call, PLAN Later) | Not set up yet. If added: paper URL hard-coded in code, with a test proving it can't reach the live URL (CLAUDE.md) | Would be an app name | Easy until set up |

**Rename cost** says what makes the name expensive to change: "Easy" (a display name), "Easy until <event>", or **Permanent once <event>** in bold.

## Decide the name before

**Name final:** no

While this says no, nothing that locks the name in may run. Only the owner changes it to yes. **Rule for Claude:** before any step below, or anything else that makes the name hard to change, stop and warn the owner first, even if they asked for the step.

1. Buying the domain.
2. The first app store build or upload (the app ID is permanent).
3. Publishing a package under the name (npm, PyPI).
4. Telling users or testers the name.
5. Printed or paid material: business cards, ads, a trademark filing.

Before those, a full rename of the product's words, emails and docs is usually an afternoon of work. Check the name for trademark conflicts (USPTO search, same class) before any of them.
