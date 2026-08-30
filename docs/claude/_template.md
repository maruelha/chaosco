# <Name>

**Type:** mini app · component · pattern (pick one)
**URL:** `/…` (or "no page — used by other modules")
**Storage:** `app/db/<module>.py` → `table`, `table`
**Routes:** `app/web_<module>.py` (Blueprint `…`)
**Templates:** `…html`
**Tests:** `tests/test_….py`

## Purpose

Why this exists and which problem it solves — in the user's terms, not the
code's. If it replaced or split off from something, say what and why.

## Architecture

How it is built: routes, storage tables and their meaning, importer (if any),
templates/includes, the key functions and where the logic lives. Whatever a
reader must know before changing the code.

## Rules & gotchas

The decisions that would otherwise be re-litigated or accidentally broken —
each with its `[USER <date>]` where there is one. Traps, deliberate
non-features, things that look like bugs but are not.

## Outputs

Reports, downloads, email attachments, exports it produces — or "none".

## Related

`[[other-doc]]` links: which apps feed it, which components it uses.

---
Skeleton for every file in `docs/claude/` (mini apps) and
`docs/claude/components/` (shared machinery). Keep the five headings, drop a
section only when it is genuinely empty. The one-line index of all files is
`docs/claude/mini-apps.md`.
