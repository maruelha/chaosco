"""Re-link orphaned spillover annotations after the match-key migration.

What happened:
  The match-key migration incorrectly used DELETE instead of UPDATE, removing
  all spillover rows and orphaning their annotations.  After re-importing, new
  rows received higher auto-increment IDs.  This script computes the ID offset
  and remaps the orphaned annotations to the correct new rows.

Usage:
    python -m scripts.repair_spillover_annotation_ids --dry-run
    python -m scripts.repair_spillover_annotation_ids

    # If your database is not at the default path:
    python -m scripts.repair_spillover_annotation_ids --db path/to/your.db
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/test_coordination.db",
                        metavar="PATH",
                        help="Path to the SQLite database")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing anything")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        raise SystemExit(1)

    conn = sqlite3.connect(str(db_path))

    # ── Diagnose ──────────────────────────────────────────────────────────────
    orphaned_ids = [r[0] for r in conn.execute("""
        SELECT spillover_id FROM spillover_annotations
        WHERE spillover_id NOT IN (SELECT spillover_id FROM spillover)
        ORDER BY spillover_id
    """).fetchall()]

    row = conn.execute(
        "SELECT MIN(spillover_id), MAX(spillover_id), COUNT(*) FROM spillover"
    ).fetchone()
    current_min, current_max, current_count = row

    print(f"Orphaned annotation IDs : {orphaned_ids or 'none'}")
    print(f"Current spillover range : {current_min} – {current_max}  ({current_count} rows)")

    if not orphaned_ids:
        print("\nNothing to repair — no orphaned annotations found.")
        conn.close()
        return

    if current_min is None:
        print("\nERROR: spillover table is empty. Run an import first, then re-run this script.")
        conn.close()
        raise SystemExit(1)

    # ── Compute offset ────────────────────────────────────────────────────────
    offset = current_min - min(orphaned_ids)
    remapped = [oid + offset for oid in orphaned_ids]
    print(f"Computed offset         : {offset}  (old_id + {offset} → new_id)")
    print(f"Remapped IDs would be   : {remapped}")

    # Safety 1: all remapped IDs must exist in the spillover table
    ph = ",".join("?" * len(remapped))
    found = conn.execute(
        f"SELECT COUNT(*) FROM spillover WHERE spillover_id IN ({ph})", remapped
    ).fetchone()[0]
    if found != len(remapped):
        print(f"\nERROR: only {found}/{len(remapped)} remapped IDs exist in spillover.")
        print("The two imports may have had a different number of rows. Cannot safely remap.")
        conn.close()
        raise SystemExit(1)

    # Safety 2: none of the remapped IDs must already have an annotation
    # (would happen if you added new annotations after the re-import)
    conflicts = conn.execute(
        f"SELECT spillover_id FROM spillover_annotations WHERE spillover_id IN ({ph})", remapped
    ).fetchall()
    if conflicts:
        print(f"\nERROR: {len(conflicts)} target ID(s) already have annotations: "
              f"{[r[0] for r in conflicts]}")
        print("You added annotations after the re-import that would be overwritten.")
        print("Resolve manually before running this script.")
        conn.close()
        raise SystemExit(1)

    print(f"\nAll checks passed — safe to remap {len(orphaned_ids)} annotation(s).")

    if args.dry_run:
        print("Dry run — no changes written. Re-run without --dry-run to apply.")
        conn.close()
        return

    # ── Apply ─────────────────────────────────────────────────────────────────
    # Update highest IDs first to avoid transient PK collisions
    for old_id in sorted(orphaned_ids, reverse=True):
        conn.execute(
            "UPDATE spillover_annotations SET spillover_id = ? WHERE spillover_id = ?",
            (old_id + offset, old_id),
        )
    conn.commit()
    conn.close()
    print(f"Done — remapped {len(orphaned_ids)} annotation(s).")


if __name__ == "__main__":
    main()
