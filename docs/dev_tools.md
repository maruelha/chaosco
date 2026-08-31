# Dev tools (`tools/`) — helpers for working ON chaosco

Small utilities that make the day-to-day workflow easier. **None of this is
part of the application**: nothing here is imported by `app/`, runs in the
Flask process, or touches the database. Delete the folder and chaosco still
runs.

Kept apart from the app code on purpose [USER 2026-08-31: "add a new folder
for such helper functions so it is clear that it is apart from the actual
code"].

## Where things live

| Folder | Holds |
|---|---|
| `app/` | the application |
| `tests/` | the pytest suite |
| **`tools/`** | **workflow helpers — documented here** |
| `scripts/` | one-off data/migration scripts (`migrate_notes.py`, the spillover annotation export/import, `clear_tables_gui.py`) |

`tools/` vs `scripts/`: a **tool** is something you reach for again and
again while working; a **script** is a one-off job against the data, run
once and kept for the record. Adding a tool = the file + a section here + a
row in `tools/README.md`.

---

## `clip_image.ps1` — screenshot from the clipboard to Claude

**The problem it solves:** `Ctrl+V` does not paste images into the Claude
Code prompt on this machine (tried 2026-08-31 — nothing arrives at all).

**How to use it:**

1. Take the screenshot with `Win+Shift+S` (it goes to the clipboard).
2. Say **"grab the clipboard"** in the chat.
3. Claude runs the script, it writes the image to
   `%TEMP%\claude_clip\clip_<timestamp>.png` and prints the path, and Claude
   reads that file.

By hand:

```
powershell -ExecutionPolicy Bypass -sta -NoProfile -File tools\clip_image.ps1
```

`-ExecutionPolicy Bypass` is required because script execution is disabled
on this machine. It applies to that ONE process — nothing is changed
system-wide, and no security setting is touched.

`-sta` matters too: the Windows clipboard API only works on a
single-threaded-apartment thread.

**Optional parameter:** `-OutDir <folder>` writes somewhere other than
`%TEMP%\claude_clip`.

**Limits — images only:**

| Clipboard holds | What happens |
|---|---|
| an image | saved as PNG, path printed, exit 0 |
| text | message "paste it into the chat directly", exit 1 |
| a file copied in Explorer | the file paths are printed — give Claude a path instead, it reads files directly |
| nothing | message "take the screenshot with Win+Shift+S first", exit 1 |

The image path is proven (used on 2026-08-31 to read a 2546×818 mockup);
the file-drop branch is a convenience message and has not been exercised.

## The other two ways to get something to Claude

Neither needs this tool:

- **Screenshots folder** — `Win+PrtScn` and the Snipping Tool's auto-save
  write to `Pictures\Screenshots\`. Name the file in the chat.
- **Any file at all** — give the path, or drag the file onto the terminal.
  Claude reads files directly; no clipboard involved.
