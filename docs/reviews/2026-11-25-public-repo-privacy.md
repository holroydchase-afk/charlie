# Public repo privacy review: 2026-11-25 (intake #65)

privacy-security, against what is already public: GitHub reports `holroydchase-afk/charlie` as public, and Chase confirmed on Nov 24 that it is meant to be. This review covers the whole git history, the current tree, and the public issue and PR text on GitHub. It follows the Oct 24 pre-public review (`2026-10-24-pre-public-privacy.md`) and CHL-PS16/PS17 (Oct 29).

## Scope

- **History:** `git log --all -p` on a full (not shallow) clone: 180 commits across `main` and every pushed branch (24 `claude/*` and 3 Dependabot branches), 1,385 objects. The local stash is not public and is out of scope.
- **Current tree:** `HEAD` of `claude/project-thread-0qykb0` (equal to `origin/main` when checked), plus the CI privacy grep from `.github/workflows/ci.yml` run locally.
- **GitHub text:** all 56 issues and PRs, their 74 bodies and comments, and PR review comments, read through the REST API.
- **Binaries:** every version of `samples/sample_resume.docx` (text and document metadata) and both versions of `docs/screenshots/demo-phone.png` (looked at, and checked for text and EXIF chunks).

## What is clean

- **Resumes and personal data:** `samples/` has only ever held `sample_resume.txt` and `sample_resume.docx`, both the fictional Alex Rivera (nurse, no email, phone or address). The docx metadata is python-docx's default (no author, no machine name). Both screenshots show sample data only and carry no metadata chunks. No other resume, profile or interest file has ever been committed.
- **`data/`, `.env`, databases:** no `data/`, `.env`, `*.db` or cache file appears in any commit. `.gitignore` covers `/data/`, `.env`, `*.db*` and `**/data/cache/`; the local `data/charlie.db` is ignored.
- **Keys and tokens:** no Anthropic, AWS, GitHub (`ghp_`, `github_pat_`), Slack, Google, Stripe, Resend or JWT-shaped strings and no private key blocks in any diff or commit message. `ANTHROPIC_API_KEY` and `CHARLIE_SEC_UA` are never assigned a value in code. The workflows use no repository secrets.
- **Emails in files:** only placeholders on example.com and example.org, plus an old README placeholder, `noreply@anthropic.com` co-author lines and Dependabot's sign-off. The owner's address never appears inside a file. The CI privacy grep passes on the current tree.
- **Private ids in files and commit messages:** no claude.ai artifact or project links, trigger ids, database ids, thread ids, Gmail or Google Docs links, phone numbers or UUIDs in any file in any commit. Commit messages carry only claude.ai session links in the required attribution trailer.
- **Docs:** `docs/` names Chase, his portfolio domain and studio tools (Product Studio, Hearth, pm-tools, studio-agents, the private story log by name). Nothing about his job search, employer, family, location or contacts. `docs/product/ACCOUNTS.md` names logins by role only ("Owner's personal email"), never by value.

## Findings

| ID | Sev | Finding | Standard | Fix and owner |
|---|---|---|---|---|
| CHL-PS-P1 | P1 | Issue #64's body (public) holds two claude.ai artifact links, a design mock and a preview. The studio rule (pm-tools CLAUDE.md, studio `check-private` patterns) is that artifact links stay in project memory, never in a public repo. Whether anyone can open them depends on each artifact's sharing setting, which this session can't see. Nothing in git is affected. | LINDDUN Disclosure; OWASP ASVS 4.0 V8.3 (sensitive data) | Edit issue #64 to drop both links (a body edit, no history change). **Needs Chase's go**, or a thread with issue write access does it on his go. Issues opened from intakes should link artifacts by name only. |
| CHL-PS-P2 | P2 | The owner's personal email is the author of 38 commits (2 originals and 36 web-UI merges), up from 23 when CHL-PS16 was accepted on Oct 29. Fifteen were added since, the latest on Nov 24, so GitHub's email privacy setting is still off. It is only in commit metadata, not in any file. | LINDDUN Identifiability | Keep history (no rewrite, per CHL-DEC-10). **Needs Chase:** GitHub Settings, Emails, tick "Keep my email addresses private" and "Block command line pushes that expose my email". New merges then use the noreply address. `docs/product/DECISIONS.md` CHL-DEC-10 still says 23 (story-keeper or staff-pm to update). |
| CHL-PS-P3 | P2 | GitHub secret scanning and push protection are both disabled (`security_and_analysis`), though they are free for public repos. The CI grep only catches `sk-ant-`, `AKIA` and emails, so a GitHub or Slack token, a private key block, an artifact link or a trigger id would merge without a warning. | Supply chain: secret scanning in CI (gitleaks class); OWASP ASVS 4.0 V14.1 | Turn on secret scanning and push protection (repo setting; **needs Chase's go**, a one-tap API call from a session). Widen the CI check by adopting the studio `check-private.mjs` once it ships (INTAKE 1 in `docs/intakes/2026-10-28-product-studio.md`); scheduled with M1.5 follow-ups, architect owns the workflow change. |
| CHL-PS-P4 | P2 | Twelve or more PR bodies link to claude.ai project threads with their thread ids, and commits and PRs carry about 120 claude.ai session links. All need Chase's login to open, so they leak only that the sessions exist and their ids. This is the Oct 24 finding 2, which was accepted. | LINDDUN Linkability | **Accepted** for what is already public: these links need a login, and editing old PR bodies brings little. Going forward, PR bodies drop project-thread links. The session trailer stays, because the attribution rule requires it. |
| CHL-PS-P5 | P2 | The repo's written rules still describe a private repo: CLAUDE.md ("It's private today; it goes public only after..."), and `docs/product/ACCOUNTS.md` ("Planned home", "Pages is off while the repo is private", "inactive while private"). Promises must match reality. | Surface review (promises match the code) | The CLAUDE.md and PLAN M1.5 wording is intake #65 step 1 (not this review). `ACCOUNTS.md` rows for GitHub and chaseholroyd.com need updating in the same PR. Wording goes to positioning. |

No P0. Nothing personal, no resume, no key and no data file has ever been in git.

## Verdict

**Safe to stay public: yes.** The git history and current tree are clean, and nothing in them needs a rewrite. One P1 sits outside git: the artifact links in issue #64's body. Removing them is a one-line issue edit that needs Chase's go. The P2s are two settings for Chase (email privacy, secret scanning and push protection), one accepted item and one docs update.

Remaining risks:
- **Fixed:** none in this review. It changed no code, settings or GitHub text.
- **Accepted:** CHL-PS-P4 (login-gated session and thread links); CHL-PS16 / CHL-PS-P2 history (no rewrite, CHL-DEC-10).
- **Needs Chase:** CHL-PS-P1 (edit issue #64), CHL-PS-P2 (GitHub email privacy settings), CHL-PS-P3 (turn on secret scanning and push protection).

_Checked 2026-11-25 against `origin/main` and all pushed branches._
