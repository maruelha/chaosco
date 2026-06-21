# Inbox Module — Build Plan (next session)

> **Status:** designed, not built. Design is settled — this doc is the handoff so the
> next session can build without re-litigating decisions.
>
> **One-liner:** a daily capture inbox. Paste free-text notes + screenshots during the day;
> at end of day each item is either **filed** (moved onto a Defect / Retail / Spillover /
> Test Learning) or **deleted**. No backlog — an item leaves the inbox the moment it's filed.

---

## Build approach: quick & disposable ⚡

This ships **today, in the old app** — build it **fast, not clean**. The routes and template are
**throwaway**: v2 rebuilds Inbox on the new stack (see `v2_blueprint.md` §10). What survives is the
**data design** — `notes` rows with `entity_type='input'` — and that's already right. So:

- **Get the DATA right** — the design below + the entity_id mapping table. The only part that
  carries into v2, and the only silent-failure risk.
- **Build the CODE fast** — clone the nearest existing vertical, reuse shared infra, ship.

**Clone from these exact spots (don't invent code):**

| Need | Copy from | Change |
|---|---|---|
| Note add/edit/delete routes | the **defect note block**, `app/web.py:1279–1363` | `entity_type` `"defect"`→`"input"`; redirect to `/inbox` |
| Inbox page + attachment/paste JS | **`app/templates/spillover_detail.html`** (note section + JS ~lines 114–217) | point the add-box at `/inbox/add` |
| Note + attachment DB calls | existing `database.add_note` / `update_note` / `delete_note` / `list_notes` / `add_attachment` / `delete_attachment` | reuse as-is (all already exist) |
| Image upload / paste / serve | existing `/notes/<id>/attachments/…` + `/uploads/<f>` | **reuse unchanged** |

**Deliberately DON'T (it's v2's job, not today's):**
- ❌ extract a shared `_note_log.html` partial
- ❌ touch or refactor the existing 9 note-route blocks
- ❌ build any generic CRUD / entity helper

Copy-paste is the *correct* choice for code you're about to retire.

---

## Decisions locked (do NOT re-open)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Reuse the `notes` table.** No new table. | An inbox item *is* a note that hasn't been told where it belongs yet. CLAUDE.md mandates one notes table. |
| 2 | Unfiled item = `entity_type='input'`, `entity_id='inbox'` (sentinel). | `entity_id` is NOT NULL on the shared table; `'inbox'` is a placeholder for "no parent yet." |
| 3 | **Filing = one UPDATE.** Flip `entity_type` + `entity_id` to the target. | The row's `id` never changes, so screenshots stay attached. "Move," not copy. |
| 4 | **Delete = remove the note + its attachments (rows + disk files).** | Item is either filed or deleted. Nothing else. |
| 5 | Screenshots reuse the existing `attachments` infrastructure as-is. | `attachments.note_id` already points at `notes.id`; an inbox item is a note, so it works for free. |
| 6 | **No `source='inbox'` provenance marker.** Dropped. | Marginal benefit; once filed, how it arrived doesn't matter. |
| 7 | **No DB migration.** | `notes` already has every needed column; `'input'` is just a new *value*. |
| 8 | One target per item. | Confirmed by the "file or delete" framing. |

The soft/polymorphic FK on `notes.entity_id` is fine and intentional — it's the correct
shape for one log attached to many entity types. Integrity is enforced in `database.py`
(see the gotcha below), not by the DB.

---

## Lifecycle (the whole feature in one picture)

```
  capture          unfiled                       filed (moved)
  ───────    entity_type='input'      ──►   entity_type='defect'
             entity_id  ='inbox'             entity_id  ='D-123'
                  │
                  └──► delete  ──►  note + attachments removed
```

Both fields flip together at file-time: `('input','inbox') → (real_type, real_pk)`.

---

## ⚠ The critical gotcha — entity_id MUST match the target's `list_notes` key

Each target detail page reads its notes with `list_notes(conn, entity_type, entity_id)`.
If the filed note's `entity_id` doesn't match the exact key that page uses, the note
**silently disappears** (no error). This table is the single most important thing to get right:

| Target | `entity_type` to store | `entity_id` to store | NOT |
|--------|------------------------|----------------------|-----|
| Defect | `defect` | `defect_id` (TEXT) | — |
| Retail | `retail` | `retail_id` (the PK) | **not** `match_key` |
| Spillover | `spillover` | `spillover_id` | — |
| Test Learning | `test_learning` | the row `id` | — |

Phase 1 exists specifically to prove this table works before any UI is built on it.

---

## What's reused (free) vs new

**Free — write zero new code:**
- Screenshot upload/delete: `POST /notes/<note_id>/attachments/add` and `.../delete`
- Image serving: `GET /uploads/<filename>`
- Ctrl+V paste-into-note JS
- Rendering on the target — every target detail page already calls `list_notes()`

**New — the actual work:** ~6 DB functions, ~6 routes, 1 template, 1 dashboard card.

---

## Build plan — 4 phases, each with a checkpoint

### Phase 1 — Data layer + prove the move (headless)
**Files:** `app/database.py`

Add:
- `add_inbox_item(conn, heading, text) -> id` — INSERT note `entity_type='input'`, `entity_id='inbox'`.
- `list_inbox_items(conn)` — unfiled items + attachment count, newest first.
- `count_inbox_items(conn)` — for the dashboard badge.
- `file_inbox_item(conn, note_id, target_type, target_id)` — validate `target_type` is in
  the allowed set **and that the target row exists**, then
  `UPDATE notes SET entity_type=?, entity_id=? WHERE id=? AND entity_type='input'`.
- `delete_inbox_item(conn, note_id)` — collect attachment filenames (for disk unlink in the
  route), delete attachment rows, delete the note.
- `search_targets(conn, target_type, q)` — return `[(value, label), …]` per the gotcha table.

**Done when (verify headless, no UI):** in a REPL/scratch script —
```python
nid = add_inbox_item(conn, "test", "hello")
file_inbox_item(conn, nid, "defect", "<an existing defect_id>")
assert any(n["id"] == nid for n in list_notes(conn, "defect", "<that defect_id>"))
```
Repeat for `retail`→`retail_id`, `spillover`→`spillover_id`, `test_learning`→`id`.
✅ This proves the entity_id mapping before a single line of UI.

### Phase 2 — Inbox page (capture only, no picker)
**Files:** `app/web.py`, `app/templates/inbox.html` (new)

Routes:
- `GET  /inbox` — render `inbox.html` from `list_inbox_items`.
- `POST /inbox/add` — `add_inbox_item`, redirect.
- `POST /inbox/<id>/edit` — update note heading/text (reuse the existing note-update DB
  function if one exists; otherwise add a minimal `update_note`).
- `POST /inbox/<id>/delete` — `delete_inbox_item` + unlink the returned disk files.

Template:
- Add-box on top (heading + textarea), then one card per pending item.
- **Copy the note-log + attachment/paste markup wholesale** from `spillover_detail.html`
  (note section + the JS at ~lines 114–217) so screenshots, add/delete, and Ctrl+V paste are
  identical. **Do not extract a partial** — clone it; this code is disposable (see §Build approach).
- Note: an item must be **saved first** (exist as a note row) before screenshots can attach —
  same constraint as everywhere else, since attachments need a `note_id`.

**Done when:** add a note → paste a Snipping Tool screenshot into it → edit its text →
delete it (confirm the file is gone from `data/uploads/`).

### Phase 3 — Filing UI (the picker — the only real design work)
**Files:** `app/web.py`, `app/templates/inbox.html`

- `GET /inbox/targets?type=&q=` — AJAX endpoint returning JSON candidates (defects/retail can
  be hundreds, so search beats a giant dropdown). Values/labels per the gotcha table.
- File control per item: **type selector** (Defect / Retail / Spillover / Test Learning) →
  search box (calls the AJAX endpoint) → pick one → **Move** button → `POST /inbox/<id>/file`.
- `POST /inbox/<id>/file` — call `file_inbox_item`, flash `Filed to <type> <label>`, redirect
  (the item vanishes from `/inbox`).

**Done when:** for **all four** target types, filing makes the item disappear from `/inbox`
**and** appear — screenshots intact — on that target's detail page. End-to-end proof of the gotcha.

### Phase 4 — Dashboard card + badge
**Files:** `app/templates/base.html` / dashboard template

- Add an **"Inbox" card** to the home grid with a **pending-count badge** (`count_inbox_items`).
- Optional: a nav link.

**Done when:** the card shows the correct pending count and links to `/inbox`.

---

## Deliverables checklist

| Kind | Item |
|------|------|
| DB | `add_inbox_item`, `list_inbox_items`, `count_inbox_items`, `file_inbox_item`, `delete_inbox_item`, `search_targets` |
| Route | `GET /inbox`, `POST /inbox/add`, `POST /inbox/<id>/edit`, `POST /inbox/<id>/delete`, `POST /inbox/<id>/file`, `GET /inbox/targets` |
| Template | `app/templates/inbox.html` (new); Inbox card in dashboard/`base.html` |
| Attachments | **none** — fully reused |
| Migration | **none** |

---

## Out of scope (future, but free later)

- Filing to **other** modules (To-Do, Follow-up, Meeting Prep) — the notes table is
  type-agnostic, so this is trivial to add later. Not in v1.
- Multi-target filing — one target per item by design.
- Provenance marker — dropped (decision #6); one-line add later if ever wanted.
