# Session Test — 2026-08-11 — Deadlines & Burning

Click-through checklist for the new red nag module.
App at `http://127.0.0.1:8010`.

> **Before clicking through:** restart the app once (`run_web.bat`) so the
> `urgent_items` table is created. It starts empty.

## ① The list

- [ ] Dashboard → red **🔥 Deadlines & Burning** card, first in the grid →
      **Open the list** (or go to `/urgent/`).
- [ ] Add one of each kind with the form at the top:
      - **Deadline** with a date in the past → shows red with "N days over"
      - **Burning** with no date → shows "no date", never overdue
      - **Uncomfortable** with today's date + a note → amber "today"
- [ ] The three sections are colour-coded and keep the kinds apart.
- [ ] Within a section, the closest date is listed first; undated last.
- [ ] **Edit** opens an inline form (category, title, date, note) and saves.
- [ ] **☐** ticks an entry off — it leaves the list.
- [ ] **Show done** reveals the done ones; the ☑ there reopens an entry.
- [ ] **✕** deletes after a confirm.

## ② The popup — the actual point

- [ ] Go to the Dashboard (or restart the app). A red **"🔥 Before anything
      else"** modal opens over it, listing the open entries, most urgent first,
      each with its category chip and overdue/today marker.
- [ ] Tick one off **in the popup** → it strikes through immediately, and the
      card badge behind it goes down.
- [ ] **Got it** (or Esc, or a click on the dark backdrop) closes it.
- [ ] Reload the dashboard → **it does not come back today**.
- [ ] Tomorrow (or: clear the browser's localStorage key
      `urgent-popup-seen`) → it nags again.
- [ ] Tick off everything → no popup at all, and the card loses its badge.

## Notes / decisions to confirm

- **Dismissal lasts one day.** I chose per-day rather than per-visit, so it
  really does push your nose in each morning without becoming wallpaper. Say
  if you want it every visit, or a "snooze until date" instead.
- **Deliberately not a to-do module.** No notes section, no detail page — the
  value is that this list stays short. To-Do and Topics are unchanged.
- **Undated entries never go red.** Burning items usually have no date; they
  still nag, they just don't claim to be overdue.

## No clicking needed

- Full suite green: **401 tests** (16 new).
- Verified in the real browser: popup appears centred, ticking off works,
  dismissal survives a reload, counts update. Demo entries I created while
  testing have been deleted — the list starts empty for you.
- Docs updated: `screens.html` · `database_schema.html` · `architecture.html`
  · `dashboard_cards.html` · `claude/coordination.md` · `CLAUDE.md` ·
  `build_plan.md`.
