"""GUI wrapper for merge_spillover_annotations — double-click to run."""
from __future__ import annotations

import io
import sqlite3
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext


# ── inline the merge logic so the script is self-contained ──────────────────

def _run_merge(src_path: Path, dst_path: Path, dry_run: bool,
               log: io.StringIO) -> tuple[int, int]:
    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(dst_path))

    candidates = src.execute("""
        SELECT s.excel_row, a.critical_for_signoff, a.comment_for_signoff
        FROM   spillover_annotations a
        JOIN   spillover s ON s.spillover_id = a.spillover_id
        WHERE  a.critical_for_signoff IS NOT NULL
            OR a.comment_for_signoff  IS NOT NULL
        ORDER  BY s.excel_row
    """).fetchall()

    n_updated = n_skipped = 0

    for excel_row, critical, comment_for_signoff in candidates:
        match = dst.execute(
            "SELECT spillover_id FROM spillover WHERE excel_row = ?", (excel_row,)
        ).fetchone()

        if match is None:
            log.write(f"  SKIP  row {excel_row:>4} — not found in destination\n")
            n_skipped += 1
            continue

        dst_spillover_id = match[0]
        verb = "WOULD UPDATE" if dry_run else "UPDATED"
        log.write(f"  {verb} row {excel_row:>4}  "
                  f"critical={critical!r}  "
                  f"comment_for_signoff={comment_for_signoff!r}\n")

        if not dry_run:
            dst.execute(
                """
                INSERT INTO spillover_annotations
                    (spillover_id, critical_for_signoff, comment_for_signoff)
                VALUES (?, ?, ?)
                ON CONFLICT(spillover_id) DO UPDATE SET
                    critical_for_signoff = excluded.critical_for_signoff,
                    comment_for_signoff  = excluded.comment_for_signoff
                """,
                (dst_spillover_id, critical, comment_for_signoff),
            )
        n_updated += 1

    if not dry_run:
        dst.commit()

    src.close()
    dst.close()
    return n_updated, n_skipped


# ── GUI ──────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Merge Spillover Annotations")
        self.resizable(False, False)
        self._build()

    def _build(self):
        pad = dict(padx=10, pady=6)

        # Source
        tk.Label(self, text="Source DB  (new — has the annotations to copy):",
                 anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        self._src_var = tk.StringVar()
        tk.Entry(self, textvariable=self._src_var, width=55).grid(
            row=1, column=0, padx=(10, 4), pady=2, sticky="ew")
        tk.Button(self, text="Browse…", command=self._pick_src).grid(
            row=1, column=1, padx=(0, 10), pady=2)

        # Destination
        tk.Label(self, text="Destination DB  (old — will be updated):",
                 anchor="w").grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        self._dst_var = tk.StringVar()
        tk.Entry(self, textvariable=self._dst_var, width=55).grid(
            row=3, column=0, padx=(10, 4), pady=2, sticky="ew")
        tk.Button(self, text="Browse…", command=self._pick_dst).grid(
            row=3, column=1, padx=(0, 10), pady=2)

        # Dry-run checkbox
        self._dry_run = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Dry run (preview only — no changes written)",
                       variable=self._dry_run).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))

        # Run button
        tk.Button(self, text="Run", width=14, command=self._run,
                  bg="#0071e3", fg="white", activebackground="#005bb5",
                  relief="flat", pady=4).grid(
            row=5, column=0, columnspan=2, pady=(6, 10))

        # Log output
        self._log = scrolledtext.ScrolledText(self, width=72, height=16,
                                              state="disabled", font=("Courier", 10))
        self._log.grid(row=6, column=0, columnspan=2, padx=10, pady=(0, 10))

    def _pick_src(self):
        p = filedialog.askopenfilename(title="Select source database",
                                       filetypes=[("SQLite DB", "*.db"), ("All", "*.*")])
        if p:
            self._src_var.set(p)

    def _pick_dst(self):
        p = filedialog.askopenfilename(title="Select destination database",
                                       filetypes=[("SQLite DB", "*.db"), ("All", "*.*")])
        if p:
            self._dst_var.set(p)

    def _log_write(self, text: str):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _log_clear(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _run(self):
        src = self._src_var.get().strip()
        dst = self._dst_var.get().strip()
        if not src or not dst:
            messagebox.showerror("Missing path", "Please select both source and destination databases.")
            return
        src_path, dst_path = Path(src), Path(dst)
        if not src_path.exists():
            messagebox.showerror("Not found", f"Source not found:\n{src_path}")
            return
        if not dst_path.exists():
            messagebox.showerror("Not found", f"Destination not found:\n{dst_path}")
            return
        if src_path.resolve() == dst_path.resolve():
            messagebox.showerror("Same file", "Source and destination cannot be the same file.")
            return

        dry_run = self._dry_run.get()
        self._log_clear()
        buf = io.StringIO()
        buf.write(f"Source      : {src_path}\n")
        buf.write(f"Destination : {dst_path}\n")
        buf.write(f"Dry run     : {dry_run}\n\n")

        try:
            n_updated, n_skipped = _run_merge(src_path, dst_path, dry_run, buf)
        except Exception as exc:
            buf.write(f"\nERROR: {exc}\n")
            self._log_write(buf.getvalue())
            messagebox.showerror("Error", str(exc))
            return

        verb = "Would update" if dry_run else "Updated"
        buf.write(f"\n{verb}  : {n_updated}\n")
        buf.write(f"Skipped    : {n_skipped}\n")
        if dry_run:
            buf.write("\nUncheck 'Dry run' and click Run again to apply.\n")
        else:
            buf.write("\nDone.\n")

        self._log_write(buf.getvalue())
        if not dry_run:
            messagebox.showinfo("Done", f"Updated {n_updated} row(s).")


if __name__ == "__main__":
    App().mainloop()
