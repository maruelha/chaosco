"""Copy critical_for_signoff and comment_for_signoff from one database to another.

Matches rows by excel_row so it works regardless of which match-key format
either database was using.  Only the two named fields are touched; all other
annotation fields (importance_for_signoff, next_step, comment_history) in the
destination database are left unchanged.

Usage:
    # Preview what would change
    python -m scripts.merge_spillover_annotations --src data/new.db --dst data/old.db --dry-run

    # Apply
    python -m scripts.merge_spillover_annotations --src data/new.db --dst data/old.db
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True, metavar="PATH",
                        help="Source database (new — contains the annotations you want to keep)")
    parser.add_argument("--dst", required=True, metavar="PATH",
                        help="Destination database (old — will be updated)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing anything")
    args = parser.parse_args()

    src_path = Path(args.src)
    dst_path = Path(args.dst)

    if not src_path.exists():
        print(f"ERROR: source database not found: {src_path}")
        raise SystemExit(1)
    if not dst_path.exists():
        print(f"ERROR: destination database not found: {dst_path}")
        raise SystemExit(1)

    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(dst_path))

    # Pull every spillover annotation from the source that has at least one of
    # the two fields set, joined with the spillover table to get excel_row.
    candidates = src.execute("""
        SELECT s.excel_row,
               a.critical_for_signoff,
               a.comment_for_signoff
        FROM   spillover_annotations a
        JOIN   spillover s ON s.spillover_id = a.spillover_id
        WHERE  a.critical_for_signoff IS NOT NULL
            OR a.comment_for_signoff  IS NOT NULL
        ORDER  BY s.excel_row
    """).fetchall()

    print(f"Source rows with annotations : {len(candidates)}")
    print(f"Dry run                      : {args.dry_run}")
    print()

    n_updated = 0
    n_skipped = 0

    for excel_row, critical, comment_for_signoff in candidates:
        match = dst.execute(
            "SELECT spillover_id FROM spillover WHERE excel_row = ?", (excel_row,)
        ).fetchone()

        if match is None:
            print(f"  SKIP  row {excel_row:>4} — not found in destination DB")
            n_skipped += 1
            continue

        dst_spillover_id = match[0]
        print(f"  {'WOULD UPDATE' if args.dry_run else 'UPDATE'} row {excel_row:>4}  "
              f"critical={critical!r}  comment_for_signoff={comment_for_signoff!r}")

        if not args.dry_run:
            dst.execute(
                """
                INSERT INTO spillover_annotations (spillover_id, critical_for_signoff, comment_for_signoff)
                VALUES (?, ?, ?)
                ON CONFLICT(spillover_id) DO UPDATE SET
                    critical_for_signoff = excluded.critical_for_signoff,
                    comment_for_signoff  = excluded.comment_for_signoff
                """,
                (dst_spillover_id, critical, comment_for_signoff),
            )

        n_updated += 1

    if not args.dry_run:
        dst.commit()

    src.close()
    dst.close()

    print()
    print(f"{'Would update' if args.dry_run else 'Updated'} : {n_updated}")
    print(f"Skipped (no matching row)    : {n_skipped}")
    if args.dry_run:
        print("\nRe-run without --dry-run to apply.")


if __name__ == "__main__":
    main()
