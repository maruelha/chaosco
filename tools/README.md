# tools/ — helpers for WORKING on chaosco, not part of the app

Nothing in this folder is imported by `app/`, runs in the Flask process, or
touches the database. The app must keep working if this folder is deleted.

These are small utilities that make the workflow with Claude Code (or the
terminal) easier — clipboard handling, file wrangling, that kind of thing.

Full documentation: **`docs/dev_tools.md`** — one section per tool, what it
is for, how to run it, and its limits.

## What lives where

| Folder | Holds |
|---|---|
| `app/` | the application |
| `tests/` | the pytest suite |
| `tools/` | **workflow helpers** — this folder |
| `scripts/` | one-off data/migration scripts (annotation export/import, the notes migration, the table-clearing GUI) |

The difference between `tools/` and `scripts/`: a tool here is something you
reach for repeatedly while working; a script in `scripts/` is a one-off job
against the data, run once and kept for the record.

## Current tools

| Tool | What it does |
|---|---|
| `clip_image.ps1` | Saves the image in the Windows clipboard to a PNG and prints the path, so a screenshot can be handed to Claude without saving it by hand |
| `gen_docs_map.py` | Regenerates `docs/docs_map.html` — the documentation index (job lines hand-written in its registry, file list + last-touched from git). Run after adding/removing a doc; the suite fails until you do |
