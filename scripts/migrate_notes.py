"""One-time migration: copy defect_notes → shared notes table.

Run once after deploying the notes refactor:

    python -m scripts.migrate_notes

Safe to run multiple times — skips rows already migrated (by checking
whether a note with the same entity_type/entity_id/created_at/heading/note
already exists, or by using INSERT OR IGNORE on a unique constraint).
Actually we use a simple approach: if notes already has rows with
entity_type='defect', we assume the migration already ran and abort.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make sure app/ is importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config_loader import load_config
from app.database import init_db


def run(dry_run: bool = False) -> None:
    cfg = load_config()
    db_path = Path(cfg["database_path"])
    conn = init_db(db_path)

    existing = conn.execute(
        "SELECT COUNT(*) FROM notes WHERE entity_type = 'defect'"
    ).fetchone()[0]
    if existing > 0:
        print(f"Migration already done — {existing} defect note(s) already in notes table. Aborting.")
        conn.close()
        return

    rows = conn.execute("SELECT * FROM defect_notes ORDER BY id").fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM defect_notes LIMIT 0").description]
    if not rows:
        print("defect_notes is empty — nothing to migrate.")
        conn.close()
        return

    print(f"Found {len(rows)} row(s) in defect_notes:")
    for r in rows:
        d = dict(zip(cols, r))
        print(f"  id={d['id']}  defect_id={d['defect_id']!r}  heading={d['heading']!r}  created_at={d['created_at']!r}")

    if dry_run:
        print("\nDry-run — no changes written.")
        conn.close()
        return

    with conn:
        for r in rows:
            d = dict(zip(cols, r))
            conn.execute(
                "INSERT INTO notes (entity_type, entity_id, created_at, heading, note) VALUES (?, ?, ?, ?, ?)",
                ("defect", d["defect_id"], d["created_at"], d["heading"], d["note"]),
            )

    migrated = conn.execute(
        "SELECT COUNT(*) FROM notes WHERE entity_type = 'defect'"
    ).fetchone()[0]
    print(f"\nMigrated {migrated} note(s) into notes table.")
    print("The defect_notes table is kept as a backup — you can drop it manually when satisfied:")
    print("  sqlite3 data/test_coordination.db 'DROP TABLE defect_notes;'")
    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate defect_notes → shared notes table.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be migrated without writing.")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
