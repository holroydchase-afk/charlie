# Charlie story log

Mirror of the private "Atlas Story: Charlie" log (studio standard section 3). The `story-keeper` agent appends an entry after any notable call, fix, pivot or lesson: date, title, problem, Chase's call, decision and why, result, and a one-line story angle. Under 120 words each, newest first, no secrets or personal data.

Earlier history lives in `docs/product/DECISIONS.md`, `docs/eng/LESSONS.md` and `HANDOFF.md`; this mirror starts with the studio standard (Nov 1, 2026).

### 2026-11-22 · Decision: Charlie adopts the studio design system
- Problem: Charlie had its own look, and Hearth's shared themes.css wasn't published.
- Chase's call: Adopt the studio design system (Paper theme, Atkinson Hyperlegible Next, 17px floor, 48px targets). On Nov 22: Profile comes off the main tabs because it's rarely updated and opens from a header button. Chat stays its own tab for now.
- Decision and why: Charlie computed its own themes.css from tokens.json using Hearth's algorithm rather than wait. Five tabs remain, with the rarely used screen out of primary navigation.
- Result: Three review rounds took the restyle from 7/10 to 8/10 (PR #49).
- Lesson: A design system's stricter numbers (17px, 48px) break old layout budgets, so those budgets become explicit calls for the owner.
- Story angle: Adopting a shared design system meant deciding what earns a main tab, not only changing colors.

## Entries
