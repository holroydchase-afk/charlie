# Charlie architecture docs

_Template from pm-tools (proved in Hearth), adopted in M1.15._

The living technical description of how Charlie works, written as we build. Any section here should lift into a white paper, a security page or a technical blog post with light editing, not a rewrite.

Charlie is a circle-of-competence stock and options idea helper for paper trading and education. It runs two ways: a single-user **local app** (a FastAPI server on 127.0.0.1 with a SQLite file) and a **static demo** (the same Python engine running in the visitor's browser through Pyodide, on sample data only).

**Reader.** An intelligent, privacy-focused engineer, most likely in the tech industry, who will check our claims against the code. Write for that person. User-facing words stay in the app and the user guide.

## Sections

| File | Covers | Later use |
|---|---|---|
| [01-system-overview.md](01-system-overview.md) | Components, vendors, where each piece of data lives | "Architecture" chapter; vendor appendix |
| [02-data-flow.md](02-data-flow.md) | Each flow step by step: resume to profile to ideas, paper trades, chat, demo visit, deletion | "How data moves" chapter |
| [03-threat-model.md](03-threat-model.md) | Assets, adversaries, what we defend, what we don't yet | "Security model" chapter; honest limits |

Add a section when a topic outgrows its file (encryption and keys, access control, retention and deletion), and give it a row here.

## Status labels used in these docs

- **Built**: in `main` today; the cited file is the proof.
- **Built (release branches, not yet merged)**: built and tested on the Oct 28 release branches (M1.10 to M1.12, ending at `claude/project-thread-hpanpa-blocks`), but not yet merged into `main`. Becomes **Built** when Chase merges the chain.
- **Planned**: in `PLAN.md` or `HANDOFF.md`, cited.
- **Gap**: a known shortfall, listed under "Not defended yet" where it matters.

## Writing rules

1. **True today, or labeled.** Every statement is one of **Built** (in `main`, cite the file), **Planned** (in a spec or the tracker, cite it) or **Gap** (known shortfall). No unlabeled future tense. Work that exists only on the release branches says so (see the labels above).
2. **Cite the code.** Name the file (`charlie/server.py`) so a reader can check. Code is the source of truth; when this doc and the code disagree, the doc is wrong.
3. **Claims match the register.** Anything a reader could quote as a promise must match what the README, landing page or marketing doc says is true today. Never write "end-to-end encrypted", "zero-knowledge" or "we can't see your data" about anything that isn't.
4. **Say what we can see.** For every flow, state what our servers and each vendor can read. The honest list of limits is the point; this audience distrusts docs without one.
5. **Each section stands alone.** Define terms on first use in that file, keep cross-links relative, and avoid "as discussed above" across files. Short paragraphs, tables for comparisons, no internal ticket jargon without a gloss (a planning ID is fine in parentheses).
6. **Plain names.** Use the product's words in prose and give the code name once in backticks ("saved data", `Store` in code).
7. **Footer.** Each file ends with `Last checked against code: <date>, <commit>`.

## Keeping it current

The rule below is in Charlie's `CLAUDE.md`:

> **Docs as we go.** A PR that changes how data is stored, moved, encrypted, logged or shared updates the matching `docs/architecture/` section and its "Last checked" footer in the same PR, or adds a `PLAN.md` item naming the stale section (Charlie has no TRACKER). A new vendor also gets a row in `docs/product/ACCOUNTS.md`.

- The PR author (usually `engineer`) makes the edit; `privacy-security` reviews changes to the threat model.
- At each milestone gate, `staff-pm` checks that every footer is newer than the last change to the code it describes.

Last checked against code: 2026-10-28, branch `claude/project-thread-hpanpa-blocks` (6c91015)
