# Coding Guidelines — the code-review checklist

**Job:** HOW code is written, wherever it lives. The complement of
`architecture.html`, which says WHERE code lives (layers, modules, data
flow). Litmus test: *"where may this SQL live?"* → architecture;
*"how must this SQL be written?"* → here.

**What does NOT belong here:** copies of the seven non-negotiable rules in
`CLAUDE.md` (importers/tables, SQL in the storage layer, one notes system,
config-driven, UI from components, tests before commit, portable SQL) —
those are pointed at, never restated. A guideline that names a specific
layer or module belongs in `architecture.html` instead.

**How a rule gets in here (story → rule → test):** a lesson that keeps
mattering (`lessons_learned.md` / `ways_of_working.md`) is promoted to a
guideline here; a guideline a machine can check is promoted to a test and
marked so below. Rules are harvested from real review findings — review
round 2 (full code review, agreed 2026-09-01) fills this file; speculative
rules are not written in advance.

---

## SQL & schema

- **Every table gets a technical primary key** [USER 2026-09-01].
  **Why:** the planned move to Postgres/Supabase needs stable row identity;
  UI edits, upserts and deletes reference rows; natural keys change — this
  project has already renamed SUS-nnn placeholder keys once. **Status
  2026-09-01:** 68 of 70 tables comply; `email_list_members` and
  `email_list_reports` (join tables, no PK at all) are to be fixed in
  review round 2, which also checks tables whose PK is a natural key
  rather than a technical one, and confirms the technical id is wanted on
  pure join tables too. **Test:** planned (round 2) — scan
  `CREATE TABLE` statements.

## Error handling

*(filled from review-round-2 findings)*

## Web layer patterns

*(filled from review-round-2 findings — e.g. the fetch/`X-Requested-With`
JSON-or-redirect convention currently described in
`docs/claude/email-reports.md`)*

## Naming

*(filled from review-round-2 findings)*
