# Session 2026-09-02 (b) — Sustain call-outs: name + detail page, ticket no, impact, filter bar, inbox push

Archived session summary — written once, never updated, not a source of
truth. Current docs: `docs/claude/sustain.md`, `docs/claude/inbox.md`,
`docs/claude/components/notes.md`, `docs/screens.html`,
`docs/database_schema.html`. Click-through:
`docs/marina_notes/SessionTest_2026-09-02_b.html`.

## What changed

Marina's ask, in her words: filters on the call-out list by channel, type
and status; a short **name** next to the topic, with topic moving into a
details view "like ECOM and Delegated Testing" where the notes are seen
too; a free-text **ticket no**; an **impact** field; and pushing inbox
notes into a call-out. Built as one plan in six verified steps, one
commit each:

- `2ef70f3` — **step 1, storage**: `name`, `ticket_no`, `impact` on
  `sustain_callouts` (guarded ALTERs in a `_MIGRATIONS` list, `name`
  back-filled from `topic` on `init_schema`). `create_callout` /
  `update_callout` take the name positionally and mirror it into `topic`
  when no topic is given, so old callers and the list-page add form keep
  working. Schema card updated (the docs test demands it in the same
  step).
- `6e6f8ad` — **step 2, detail page** `/sustain/callouts/<id>` (GET +
  POST save), blocker-detail shape: form, status chip, next step with
  ↻/🕘, the shared notes component. Inline edit row and `/update` route
  removed; list + summary switched from topic to name. Notes registry
  entry gets the detail endpoint; `_notes_section.html` gained the
  optional `notes_return_to='list'`.
- `8f1bcdf` — **step 3, list**: Name + Ticket columns, name links to the
  detail page, quick-add takes name / ticket no / responsible.
- `5c0f61c` — **step 4, filter bar**: channel + status selects, one
  checkbox per type (combinable), text over name + ticket, Clear,
  counter. Client-side; rows carry `data-*`.
- `9d31db6` — **step 5, inbox push**: filing target "Sustain call-out"
  (existing, by name/ticket, open first) plus a "new call-out from this
  note" form → `POST /inbox/<id>/file-to-callout`.
- `5deb67b` — **step 6, docs**; wrap-up commit after this file.

Suite: 877 → 891 tests, green at every step.

## Decisions and WHY

- **`topic` stays a column and mirrors `name` when absent.** Marina
  first said "duplicate topic into name for now", then "topic moves to
  details view". Keeping topic NOT NULL and mirroring the name avoids a
  destructive migration and means a call-out made from the quick-add
  form (name only) never has an empty detail page. The rule lives in
  storage, not in the routes, so the inbox path gets it for free.
- **Detail PAGE, not a modal.** Marina said "pop up", but the ECOM and
  Delegated examples she named are separate detail pages. Same shape
  (blocker_detail.html) → same breadcrumb, notes redirects and
  next-step wiring as every other entity.
- **Type filter as checkboxes, channel/status as selects.** Her explicit
  ask was combinable types. Inline checkboxes (six values) rather than
  the Contacts dialog pattern, which exists for long option lists.
- **No global-search registration for ticket numbers.** Proposed, then
  dropped on her call: tickets live only in this list, unlike order
  numbers that appear in ten views; the filter bar's text box is enough.
- **Two inbox paths in one picker** (existing vs. new call-out). The
  shelf pattern (create + file) fits "push a note to a call-out"; the
  standard search fits "this belongs to the one I already have". Both
  are one screen, no new dialog.
- **`notes_return_to` on the shared include instead of a sustain-only
  hack.** Registering the detail endpoint rerouted the list page's note
  adds; the fix is an optional include parameter any list page with
  inline notes can use — promoted to `lessons_learned.md`.
- **Delete stays on the list only.** Not asked for on the detail page;
  listed in MarinaCheckSoon rather than assumed.

## Considered and rejected

- **Impact as a second line under the name in the list** (first plan) —
  rejected by Marina: she wants the list short and a details view for
  everything else.
- **Renaming `topic` → keeping only `name`** — would lose the longer
  text she explicitly wants on the detail page.
- **Making the status filter load closed rows server-side** — would
  turn a client-side bar into a round-trip and duplicate the existing
  show-closed toggle; noted as a question instead.
- **Per-row inline edit kept alongside the detail page** — two edit
  paths for the same row invite drift; the detail page is the one place.
- **Remembering filters in localStorage** — not asked; one sentence to
  add if reloads annoy her (MarinaCheckSoon).

## Open threads

- Six MarinaCheckSoon questions (old names = old topics, delete on the
  detail page, closed rows vs. status filter, filters not remembered,
  note edit lands on detail, inbox topic = name).
- Sustainphase Issues (`/sustain-issues/`) still has its own textarea
  "call-outs" per imported issue — a different thing (annotations on
  imported rows) with the same word; nothing links the two yet.
- Screens were verified by tests + reasoning only; Marina's click-through
  (`SessionTest_2026-09-02_b.html`) is the eye check.
