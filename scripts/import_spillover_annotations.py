"""Import spillover annotations from a JSON export file into a database."""
from __future__ import annotations

import json
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext


def _compute_offset(conn: sqlite3.Connection, source_ids: list[int]) -> int | None:
    row = conn.execute("SELECT MIN(spillover_id) FROM spillover").fetchone()
    dest_min = row[0] if row else None
    if dest_min is None:
        return None
    src_min = min(source_ids)
    return dest_min - src_min


def _run_import(db_path: Path, export_data: dict, dry_run: bool,
                log: "callable") -> tuple[int, int, int]:
    annotations = export_data["annotations"]
    if not annotations:
        log("No annotations in file.\n")
        return 0, 0, 0

    conn = sqlite3.connect(str(db_path))

    source_ids = [a["spillover_id"] for a in annotations]
    offset = _compute_offset(conn, source_ids)

    if offset is None:
        conn.close()
        raise RuntimeError(
            "Destination spillover table is empty.\n"
            "Please run an import in the web app first to restore the spillover rows,\n"
            "then try again."
        )

    log(f"Source spillover_id range : {min(source_ids)} – {max(source_ids)}\n")
    dest_min = conn.execute("SELECT MIN(spillover_id) FROM spillover").fetchone()[0]
    dest_max = conn.execute("SELECT MAX(spillover_id) FROM spillover").fetchone()[0]
    log(f"Destination range          : {dest_min} – {dest_max}\n")
    log(f"Computed offset            : {offset}  (source_id + {offset} → destination_id)\n\n")

    n_ok = n_skip = n_conflict = 0

    for a in annotations:
        new_id = a["spillover_id"] + offset

        exists = conn.execute(
            "SELECT 1 FROM spillover WHERE spillover_id = ?", (new_id,)
        ).fetchone()
        if not exists:
            log(f"  SKIP  source_id={a['spillover_id']} → dest_id={new_id} "
                f"(no matching spillover row)\n")
            n_skip += 1
            continue

        label = a.get("name") or f"excel_row {a.get('excel_row', '?')}"
        log(f"  {'WOULD UPDATE' if dry_run else 'UPDATE'} dest_id={new_id}  [{label}]\n")

        if not dry_run:
            conn.execute("""
                INSERT INTO spillover_annotations
                    (spillover_id, critical_for_signoff, comment_for_signoff)
                VALUES (?, ?, ?)
                ON CONFLICT(spillover_id) DO UPDATE SET
                    critical_for_signoff = excluded.critical_for_signoff,
                    comment_for_signoff  = excluded.comment_for_signoff
            """, (new_id,
                  a.get("critical_for_signoff"),
                  a.get("comment_for_signoff")))
        n_ok += 1

    if not dry_run:
        conn.commit()
    conn.close()
    return n_ok, n_skip, n_conflict


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Import Spillover Annotations")
        self.resizable(False, False)
        self._export_data: dict | None = None
        self._build()

    def _build(self):
        pad = dict(padx=14, pady=4)

        tk.Label(self, text="Destination database (annotations will be written here):",
                 anchor="w", font=("", 10)).grid(row=0, column=0, columnspan=2,
                                                   sticky="w", padx=14, pady=(12, 2))
        self._db_var = tk.StringVar()
        tk.Entry(self, textvariable=self._db_var, width=58).grid(
            row=1, column=0, padx=(14, 4), pady=2, sticky="ew")
        tk.Button(self, text="Browse…", command=self._pick_db).grid(
            row=1, column=1, padx=(0, 14), pady=2)

        tk.Label(self, text="Annotation export file (JSON from export script):",
                 anchor="w", font=("", 10)).grid(row=2, column=0, columnspan=2,
                                                   sticky="w", padx=14, pady=(10, 2))
        self._json_var = tk.StringVar()
        tk.Entry(self, textvariable=self._json_var, width=58).grid(
            row=3, column=0, padx=(14, 4), pady=2, sticky="ew")
        tk.Button(self, text="Browse…", command=self._pick_json).grid(
            row=3, column=1, padx=(0, 14), pady=2)

        self._dry_run = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Dry run (preview only — no changes written)",
                       variable=self._dry_run).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 2))

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(4, 8))
        tk.Button(btn_frame, text="Run", width=18, command=self._run,
                  bg="#0071e3", fg="white", activebackground="#005bb5",
                  relief="flat", pady=4).pack()

        self._log = scrolledtext.ScrolledText(self, width=72, height=18,
                                              state="disabled",
                                              font=("Courier", 10))
        self._log.grid(row=6, column=0, columnspan=2, padx=14, pady=(0, 14))

    def _pick_db(self):
        p = filedialog.askopenfilename(
            title="Select destination database",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")])
        if p:
            self._db_var.set(p)

    def _pick_json(self):
        p = filedialog.askopenfilename(
            title="Select annotation export file",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not p:
            return
        self._json_var.set(p)
        try:
            self._export_data = json.loads(Path(p).read_text(encoding="utf-8"))
            n = len(self._export_data.get("annotations", []))
            src = self._export_data.get("source_db", "unknown")
            self._log_write(f"Loaded {n} annotation(s) from:\n  {src}\n\n")
        except Exception as exc:
            messagebox.showerror("Error reading file", str(exc))
            self._export_data = None

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
        db = self._db_var.get().strip()
        if not db:
            messagebox.showerror("Missing", "Please select a destination database.")
            return
        if not self._export_data:
            messagebox.showerror("Missing", "Please select a JSON export file.")
            return

        db_path = Path(db)
        if not db_path.exists():
            messagebox.showerror("Not found", f"Database not found:\n{db_path}")
            return

        dry_run = self._dry_run.get()
        self._log_clear()

        lines = []
        def log(msg):
            lines.append(msg)

        try:
            n_ok, n_skip, _ = _run_import(db_path, self._export_data, dry_run, log)
        except RuntimeError as exc:
            self._log_write(str(exc) + "\n")
            messagebox.showerror("Cannot import", str(exc))
            return
        except Exception as exc:
            self._log_write(f"ERROR: {exc}\n")
            messagebox.showerror("Error", str(exc))
            return

        verb = "Would update" if dry_run else "Updated"
        lines.append(f"\n{verb}  : {n_ok}\n")
        lines.append(f"Skipped    : {n_skip}\n")
        if dry_run:
            lines.append("\nUncheck 'Dry run' and click Run again to apply.\n")
        else:
            lines.append("\nDone.\n")

        self._log_write("".join(lines))
        if not dry_run:
            messagebox.showinfo("Done", f"Imported {n_ok} annotation(s).")


if __name__ == "__main__":
    App().mainloop()
