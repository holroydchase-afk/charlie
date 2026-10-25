# Pre-public privacy review: 2026-10-24 (PLAN M1.5)

privacy-security (played inline by the night shift) scanned everything that would become public if the repo went public: all commits on `main`, `claude/project-thread-dlm2ig` and `claude/project-thread-74d6f6` (13 commits), every file ever added, `samples/`, `docs/` and the built demo.

## What was checked

- **Keys and tokens in any commit:** Anthropic, AWS, GitHub and Slack token patterns, plus private key blocks. None found.
- **Email addresses in any diff:** only placeholders (`you@example.com`, `test@example.org`, plus an "AppName your-email" placeholder in the original README) and `noreply@anthropic.com` in co-author lines.
- **Personal data in files:** `samples/sample_resume.txt` and `.docx` are the fictional Alex Rivera. `docs/` and the README contain no personal details beyond Chase's name and his portfolio domain.
- **Data files:** no `data/`, `.env`, database, cache or real profile has ever been committed. The `/data/` rule has been in place since M0.2.
- **The built demo:** `tools/check_site.py` passes, so there are no keys and no hosts beyond the Pyodide CDN, the portfolio link and the SVG namespace.

## Findings

| # | Sev | Finding | Recommendation |
|---|---|---|---|
| 1 | P2 | Chase's two original commits (the MVP and "Add HANDOFF.md") carry his personal Gmail address as the commit author. A public repo shows author emails to anyone who looks at the history. | **Chase's call.** Either accept it, since it's two commits and not in any file, or turn on GitHub's "Keep my email addresses private" for future commits. Removing it from these two commits means rewriting history, which changes every SHA and needs Chase's go. Not recommended. |
| 2 | P3 | Commit trailers and PR bodies link to private claude.ai sessions and project threads. The links need Chase's login to open, so they leak nothing beyond their existence. | Accept. |

## Verdict

From a privacy standpoint, nothing blocks making the repo public, apart from Chase's call on finding 1. The second M1.5 step, deciding to make the repo public, is Chase's.
