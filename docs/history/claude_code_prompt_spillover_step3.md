# Spillover — Step 3: Integrate into the import run, gated by config

## Context
Builds on Steps 1–2. The dashboard already has an "Import DTC ROE Tracking" button that runs the
defects import. We now add the Spillover import to that SAME run — but in a way that can be turned
OFF later via config, because Spillover will eventually stop being relevant and should then be
ignored without code changes.

Respect all principles. Archiving and source-file safety already exist for the defects run; reuse
them — the file is archived once per the existing `once_per_file` logic, then BOTH importers read
the same archived copy.

## Config-driven "which tabs are active"
Add a config section listing which tabs/importers run on import. Example shape (adapt to the
existing YAML style):

```yaml
imports:
  defects:
    enabled: true
    sheet_name: "Defects"
  spillover:
    enabled: true
    sheet_name: "Core South Spillover"
```

The import run iterates over enabled importers. Setting `spillover.enabled: false` cleanly removes
Spillover from the run (no parsing, no warnings, no DB writes) with zero code edits. Existing data
stays in the DB untouched. The defects entry should be expressed the same way so the pattern is
uniform and future tabs slot in identically.

If the config section is missing entirely, default to current behavior (defects on) so nothing
breaks for an old config.

## Wiring
- The single import action: locate + archive file once (existing logic) → for each enabled
  importer, parse its sheet and upsert via its storage methods.
- The inline result summary the button already shows must now report BOTH verticals, e.g.:
  "Defects: 4 new, 12 updated, 1 skipped. Spillover: 2 new, 9 updated, 0 skipped (import disabled →
  shown as skipped/off)." When Spillover is disabled, say so plainly rather than showing zeros.
- Do not change the button label or make Spillover its own button — the user chose to extend the
  existing run.

## Acceptance
- One import click runs both, archives the source once, never modifies the source.
- Flipping `spillover.enabled: false` removes Spillover from the run with no code change and leaves
  existing Spillover + annotation data intact in the DB.
- Defects behavior unchanged when Spillover is enabled or disabled.
