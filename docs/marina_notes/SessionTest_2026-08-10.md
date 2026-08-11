# Session Test — 2026-08-10 (+ 11.08 corrections) — Meeting reports + Retrofits

Click-through checklist for the four things built while you were out, with
the 11.08 corrections folded in. App at `http://127.0.0.1:8010`.

> **Before clicking through:** restart the app once (`run_web.bat`) so the new
> `retrofits` and `meeting_types` tables are created. Nothing existing is
> changed or deleted — your 6 meetings are seeded exactly as they were.

## ① Two report buttons (corrected 11.08)

The first build had a button per meeting type — removed, as you asked.

- [ ] `/meeting-prep` → **no** per-meeting block, **no** "All meetings" button.
- [ ] **📄 DTC O2C Daily Agenda** in the page header → the full version
      (topics + defects + follow-ups), unchanged.
- [ ] Set the meeting filter to e.g. GPO → **📄 Agenda** next to the filters
      opens the plain sorted list for GPO — **no defects, no follow-ups**.
      The grey hint next to the buttons names the current filter.

## ①b Adding meetings to the dropdown (new 11.08)

- [ ] `/meeting-prep` → **Meetings in the dropdown (6)** panel under the add
      form → type a name → **+ Add meeting**.
- [ ] The new meeting appears in the add form and the filter…
- [ ] …and also in **Add to Meeting Prep** on a Defect and a Retail detail page.
- [ ] Adding the same name again (any casing) is refused with a red banner.
- [ ] A meeting **with** topics shows its topic count and no ✕ (can't be
      removed by accident); an unused one has a ✕ that removes it.
- [ ] Restart the app → your added/removed meetings stay as you left them.

## ② Bullets instead of numbers

- [ ] Agenda report: topics show **•**, no "1. 2. 3.".
- [ ] DTC O2C Daily Agenda: same.
- [ ] Worksheet: same.
- [ ] **Copy to clipboard** now pastes `- topic` instead of `1. topic`
      (flagged in MarinaCheckSoon — say if you want numbers back here).

## ③ Meeting worksheet (download + JSON)

- [ ] `/meeting-prep/worksheet` (or a Worksheet button) → each topic has a
      comment box under it.
- [ ] Type a few comments → **💾 Save comments (JSON)** downloads a `.json`;
      the status line says how many were saved.
- [ ] Reload the page (boxes empty again) → **📁 Load comments (JSON)** →
      pick that file → your comments come back, with a count.
- [ ] **⇓ Download HTML** → open the downloaded file from disk:
      - [ ] your typed comments are still in it
      - [ ] you can keep typing, and Save/Load JSON still work **offline**
            (this is the "take it into the meeting" case)

## ④ Retrofits

- [ ] Dashboard has a **Retrofits** card → `/retrofits/`.
- [ ] Add one for **Retail** (status *Confirmed*) and one for **ECOM**
      (status *Potential*), one of them linked to a Topic.
- [ ] List: Confirmed sorts above Potential; the Topic shows as a link;
      Edit expands an inline form; ✕ deletes after a confirm.
- [ ] Channel filter shows only that channel (with counts).
- [ ] `/retail/report` → bottom section **Retrofits — Retail**: only the
      Retail one, with the caveat line above it.
- [ ] `/ecom/report` → **Retrofits — ECOM**: only the ECOM one.
- [ ] Retail report → **Download HTML** → the section is in the file too.
- [ ] Delete both test entries → the section still appears on both reports
      with "No retrofits recorded…" — **that's intended**: the caveat is the
      point of the section.

## No clicking needed

- Full suite green: **384 tests** (22 for the meeting reports incl. the
  editable meeting list, 21 for retrofits, 1 regression test for the
  emailer bug).
- Every item above was also verified programmatically against temp DBs, and
  all pages were smoke-tested against your real data.
- Docs updated: `screens.html` · `database_schema.html` · `architecture.html`
  · `dashboard_cards.html` · `claude/coordination.md` · `CLAUDE.md` ·
  `build_plan.md` · `MarinaCheckSoon.html`.

## ⚠ One thing to read in MarinaCheckSoon

The emailed Retail report was claiming "No active Retail defects found" while
the live page listed them — a real bug in `emailer.render_retail_html`, now
fixed. Worth checking whether a recent emailed report misled anyone.
