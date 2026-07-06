# Teams end-of-day review list — concept (2026-07-06, not built)

Marina's ask: save Teams chat/channel links, see them as a clickable list,
and mark ("check") the ones she wants in her end-of-day sweep — so she can
run through the relevant chats without hunting for them in Teams.

## Decisions already made [USER 2026-07-06]

1. **Plain clickable list — NO walkthrough automation.** No "open next"
   button, no open-all. Just links that open in the Teams client.
2. **Filterable by the check mark.** Each saved link gets a "check" flag;
   the list default shows CHECKED ONLY, with a toggle to see all.
3. Chat links AND channel links both supported (the existing validation —
   URL starts with `https://teams.microsoft.com/` — already accepts both;
   only the labels say "channel" today).

## Open decision — placement (discuss before building)

- **Option A (Claude's recommendation): separate dashboard card** "Teams
  Review" in the dashboard grid. Checked chats render directly on the card
  as buttons; "show all / manage" expands the full list (add, check/uncheck,
  delete). Badge = checked count. Rationale: the dashboard is the launchpad;
  this is a launch-things activity.
- **Option B: section on the Inbox page** — fits the end-of-day inbox
  ritual, but the inbox is the capture-and-file place; external chat
  shortcuts are a different kind of thing.
- **Hybrid**: the component is AJAX-driven like `_teams_channels.html`, so
  it can render in BOTH places for free. Also possible bonus: the existing
  📺 Teams-channels dialog (Defects/Spillover) sorts checked links first.

## What already exists (reuse, don't duplicate)

- Teams links are stored as **Links with tool = "Teams Channel"**
  (`web_teams.py`, `TEAMS_CHANNEL_TOOL`) — no parallel table; they are also
  manageable on `/links`.
- AJAX component `_teams_channels.html` (add / list / delete via
  `/teams-ping/channels.json`, `/channels/add`, `/channels/<id>/delete`) —
  included on Defects and Spillover; any card can include it without route
  changes.

## Implementation sketch (when built)

1. Additive migration: `pinned INTEGER DEFAULT 0` (or `review_check`) column
   on the `links` table (`app/db/reference.py` — guarded ALTER like the
   others). Toggle route `/teams-ping/channels/<id>/check` (AJAX).
2. `channels.json` returns the flag; list component renders checked-first,
   filter default = checked only.
3. New list component (or extended `_teams_channels.html`) rendered at the
   chosen placement; add form identical to today's (name + teams.microsoft.com
   URL), relabelled "chat or channel link".
4. Tests: flag toggle + filter in the JSON route; route smoke for the page.
5. Docs: screens.html (dashboard/inbox section), coordination.md, build_plan.
