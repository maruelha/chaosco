# v2 Blueprint — Clean Rebuild of chaosco

> **Purpose:** the founding document for rebuilding chaosco cleanly, test-first, **reusing the
> existing database and schema**. The old `app/` keeps running as the daily tool until v2 is ready.
>
> **Why this is safe (not a risky rewrite):** the valuable asset — the **schema + data + importer
> logic** — survives. Only the messy, cheap-to-reproduce part (routes, templates, copy-pasted
> data-access) gets rebuilt. That inverts the usual "never rewrite" risk.

---

## 1. Goals (what "sustainable" means here)

Four axes — v2 must hit all four, where the old app only hit the first partially:

| Axis | Goal | How v2 delivers it |
|---|---|---|
| **Changeability** | Easy to modify | Layered architecture + one generic entity pattern (no per-entity copy-paste) |
| **Verifiability** | Change without fear | Test-first; characterization tests on ported importers |
| **Durability** | Data & env survive | Versioned migrations, startup DB backup, dev-on-a-copy, pinned deps |
| **Robustness** | Fails gracefully | Validation at the Excel boundary + the service layer |

**Restraint clause (equally important):** this is a **single-user local tool**. v2 deliberately
does **not** add auth, multi-user concurrency, containers, microservices, caching, or API
versioning. Knowing what to leave out is part of the architecture. Avoid the second-system
effect — clean ≠ over-abstracted.

---

## 2. Strategy: same repo, isolated `v2/` folder

```
chaosco/
  app/            ← OLD app, untouched, keeps running (+ Inbox + small view get added here)
  v2/             ← NEW app, built clean
  docs/
```

**Two hard rules:**
1. `v2/` **never imports from `app/`.** The old code is reference you *copy from*, never a dependency.
2. `v2/` runs against a **copy** of `test_coordination.db` during development. The live DB is only adopted at cutover.

**Cutover checklist (define "done" up front so you don't stall at 80%):**
- [ ] v2 imports the Excel and produces byte-identical DB rows to the old app (proven by tests)
- [ ] All daily-used screens exist in v2
- [ ] v2 points at the live DB; old `app/` archived (moved out, not deleted, for one safety period)

---

## 3. What carries over vs what gets rebuilt — THE manifest

Legend: 🟢 **copy ~verbatim** · 🟡 **adapt (logic stays, shape changes)** · 🔴 **rebuild clean (reference only)**

| Old | New | Treatment | Why |
|---|---|---|---|
| `read_defects.py` | `v2/app/importers/defects.py` | 🟢 | Holds fiddly edge-case knowledge (dates, blank rows, dedup, skiplog). Copy, then pin with tests. |
| `spillover_importer.py` | `v2/app/importers/spillover.py` | 🟢 | Same — match keys, blank handling. |
| `retail_importer.py` | `v2/app/importers/retail.py` | 🟢 | Same — match keys. |
| `database.py` → the `CREATE TABLE` DDL | `v2/app/db/schema.py` | 🟢 | The schema **is** the asset. Copy verbatim. |
| `database.py` → notes + attachments fns | `v2/app/db/notes.py` | 🟢 | Already unified & clean — the one part of the data layer done right. |
| `archiver.py` | `v2/app/services/archiver.py` | 🟢 | Excel archiving + dedup logic. |
| `config_loader.py` | `v2/app/config.py` | 🟡 | Small; tidy as you move it. |
| `reporter.py` | `v2/app/services/retail_report.py` | 🟡 | Bucket logic stays; wire to new layer. |
| `importer.py` (orchestrator) | `v2/app/services/imports.py` | 🟡 | Orchestration stays; becomes a service. |
| `database.py` → `database.py` → ALTER TABLE block | `v2/app/db/migrations.py` | 🟡 | Already in `schema.py` for fresh installs; migrations.py is for *future* changes. |
| `config/settings.yaml`, `config/status_mappings.yaml` | `v2/config/...` | 🟢 | Copy. |
| `data/test_coordination.db` | `v2/data/...` (a **copy** for dev) | 🟢 | Reuse the data. Copy, don't point at the live file. |
| `CLAUDE.md` | `v2/CLAUDE.md` | 🟡 | The best spec you have — adapt to describe v2. |
| `database.py` → per-entity CRUD (links/contacts/todos/followups/cs_followups/test_learnings/test_limitations/known_prod_defects) | `v2/app/db/repository.py` (generic) | 🔴 | ~60 near-identical functions collapse into ONE generic repository. |
| `web.py` (90 routes) | `v2/app/web/routes/*` | 🔴 | Split into thin route modules + generic entity routes. |
| all `templates/*.html` | `v2/app/web/templates/*` + macros | 🔴 | Rebuild with shared macros; the 4× attachment JS becomes ONE static file. |

**One-line summary:** copy the **importers, schema, notes/attachments, config, and the DB**;
rebuild the **routes, templates, and per-entity CRUD**.

---

## 4. Target structure

```
v2/
  app/
    __init__.py            # Flask app factory
    config.py              # ← port config_loader
    db/
      connection.py        # get_connection + transaction helper
      schema.py            # ← CREATE TABLE DDL, copied verbatim
      migrations.py        # ordered, versioned, future schema changes
      repository.py        # GENERIC CRUD — the duplication-killer
      notes.py             # ← port unified notes + attachments access
    importers/             # ← PORTED ~verbatim, then tested
      defects.py
      spillover.py
      retail.py
    services/              # the "orchestrator" — business logic, the middle layer
      imports.py           # ← port importer.py orchestration
      entities.py          # generic entity service over repository.py
      notes_service.py     # filing/move (incl. Inbox), note logic
      retail_report.py     # ← port reporter.py
      archiver.py          # ← port archiver.py
    models.py              # DECLARATIVE entity definitions (table, fields, filters)
    web/
      __init__.py          # blueprint registration
      routes/
        entities.py        # generic list/detail/create/edit/delete routes
        notes.py           # ONE note route set (replaces the 9 copies)
        imports.py
        dashboard.py
      templates/
        base.html
        _macros/           # shared: table, filters, note_log, attachments
        pages/             # per-screen templates that USE the macros
      static/
        js/attachments.js  # ONE copy of the paste/upload JS (was 4)
        css/
  tests/
    conftest.py
    test_importers/        # characterization — prove identical output FIRST
    test_services/
    test_web/
  data/                    # a COPY of the DB during dev
  config/                  # copied yaml
  requirements.txt         # PINNED versions
  CLAUDE.md
```

---

## 5. The layers (your "orchestrator in the middle")

```
  web/routes   →   services   →   db (repository / notes / schema)
  (thin: HTTP,     (business      (SQL only; no business logic)
   parse, render)   logic, the
                    orchestrator)
```

- **web/routes** — thin. Parse the request, call a service, render a template. No SQL, no logic.
- **services** — the middle layer you wanted. Validation, "what should happen," orchestration
  (e.g. filing an inbox note = `notes_service.file_item()`; running an import =
  `imports.run()`). This is where the rules live.
- **db** — SQL only. `repository.py` is generic; `notes.py` is the unified notes/attachments;
  `schema.py`/`migrations.py` own the structure.

---

## 6. The duplication-killer: one generic entity pattern

Instead of hand-writing list/get/create/update/delete for each of ~10 simple entities, **declare
each entity once** and let generic machinery do the rest:

```python
# models.py  (illustrative)
CONTACTS = Entity(
    table="contacts",
    fields=["name", "email", "area", "topic", "comments", "tags"],
    filters=["area", "topic", "tags"],
    search=["name", "email"],
)
```

`repository.py` (generic CRUD), `services/entities.py` (generic service), `routes/entities.py`
(generic routes), and the `_macros/` templates all read that definition. Adding a new simple
entity = one declaration, not 6 functions + 6 routes + a 250-line template.

**Where to STOP (anti-over-engineering):** the imported verticals (defects, spillover, retail)
have real bespoke logic — keep their importers and specialized queries hand-written. Use the
generic pattern for the simple CRUD entities and for *annotations*. Let special things be special;
don't force everything through one abstraction just to be clever.

---

## 7. Test-first plan

Tests come **before** the code they cover. Start where the risk and value are highest:

1. **Characterization tests on the ported importers first.** Feed a sample Excel, assert the
   resulting rows. Goal: prove v2 importers produce **identical** output to the old app. This is
   your safety net for the one part you copy rather than rewrite.
2. **Service tests** — filing logic, CRUD rules, report buckets.
3. **Web smoke tests** — each route returns 200 and the right data.

Not aiming for 100% coverage — aiming for *fearless change* on the critical paths.

---

## 8. Durability (folded in, not a phase)

- `db/migrations.py` — ordered & versioned; no more scattered ALTER TABLEs.
- **Startup DB backup** — copy the DB to a timestamped file on launch (cheap insurance).
- **Dev-on-a-copy** — protects real authored data during the messy build.
- **Pin `requirements.txt`** — reproducible environment a year from now.

---

## 9. Build order

1. **Scaffold** `v2/` (app factory, config, points at a DB copy) + one passing test.
2. **Port importers** + characterization tests → prove identical output.
3. **db layer** — `schema.py`, `connection.py`, generic `repository.py`, port `notes.py`.
4. **services** — `imports.py`, `entities.py`, `notes_service.py`, `retail_report.py`.
5. **web** — `base.html` + `_macros/` + generic entity pages + dashboard; one shared `attachments.js`.
6. **Migrate each vertical** onto the pattern, one at a time (tests stay green).
7. **Cutover** per the checklist in §2.

---

## 10. First feature in v2: Inbox (the clean version)

The Inbox you ship *today* in the old app is throwaway plumbing — but its **data design carries
over for free** (it's just `notes` rows with `entity_type='input'`). In v2, Inbox becomes the
**first real exercise of the clean stack**: a `notes_service.file_item()` + the generic note
routes + the shared note-log macro. Small, self-contained, perfect pilot. See `inbox_module_plan.md`
for the data design — that part is already right and unchanged.
