"""GUI tool to selectively clear tables from a chosen database."""
from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox


AUTHORED_TABLES = {
    "spillover_annotations",
    "retail_annotations",
    "defect_notes",
    "known_prod_defects",
}


def _load_tables(db_path: Path) -> list[tuple[str, int]]:
    conn = sqlite3.connect(str(db_path))
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    result = []
    for name in names:
        count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        result.append((name, count))
    conn.close()
    return result


def _clear_tables(db_path: Path, table_names: list[str]) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    deleted = {}
    for name in table_names:
        count = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        conn.execute(f"DELETE FROM [{name}]")
        deleted[name] = count
    conn.commit()
    conn.close()
    return deleted


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Clear Database Tables")
        self.resizable(False, False)
        self._db_path: Path | None = None
        self._checkboxes: dict[str, tk.BooleanVar] = {}
        self._build()

    def _build(self):
        # DB picker
        tk.Label(self, text="Database to clear:", anchor="w",
                 font=("", 10)).grid(row=0, column=0, columnspan=2,
                                      sticky="w", padx=14, pady=(12, 2))
        self._db_var = tk.StringVar()
        tk.Entry(self, textvariable=self._db_var, width=60,
                 state="readonly").grid(row=1, column=0, padx=(14, 4),
                                        pady=2, sticky="ew")
        tk.Button(self, text="Browse…",
                  command=self._pick_db).grid(row=1, column=1,
                                               padx=(0, 14), pady=2)

        # Table list (populated after DB pick)
        self._table_frame = tk.LabelFrame(self, text="Tables  (tick to clear)",
                                           padx=10, pady=8)
        self._table_frame.grid(row=2, column=0, columnspan=2,
                                padx=14, pady=(12, 4), sticky="ew")

        self._placeholder = tk.Label(self._table_frame,
                                      text="Select a database to see its tables.",
                                      fg="#888")
        self._placeholder.pack(anchor="w")

        # Clear button
        self._btn_clear = tk.Button(self, text="Clear selected tables",
                                     command=self._confirm_clear,
                                     bg="#c0392b", fg="white",
                                     activebackground="#922b21",
                                     relief="flat", pady=5,
                                     state="disabled")
        self._btn_clear.grid(row=3, column=0, columnspan=2,
                              padx=14, pady=(8, 14), sticky="ew")

    def _pick_db(self):
        p = filedialog.askopenfilename(
            title="Select database to clear",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")])
        if not p:
            return
        self._db_path = Path(p)
        self._db_var.set(p)
        self._load_table_list()

    def _load_table_list(self):
        # Clear existing checkboxes
        for w in self._table_frame.winfo_children():
            w.destroy()
        self._checkboxes.clear()

        try:
            tables = _load_tables(self._db_path)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        if not tables:
            tk.Label(self._table_frame, text="No tables found.",
                     fg="#888").pack(anchor="w")
            return

        for name, count in tables:
            var = tk.BooleanVar(value=False)
            self._checkboxes[name] = var

            is_authored = name in AUTHORED_TABLES
            colour = "#c0392b" if is_authored else "#1a1a1a"
            label = f"{name}  ({count} rows)"
            if is_authored:
                label += "  ⚠ authored data"

            tk.Checkbutton(self._table_frame, text=label,
                           variable=var, fg=colour,
                           activeforeground=colour).pack(anchor="w", pady=1)

        self._btn_clear.config(state="normal")

    def _confirm_clear(self):
        selected = [name for name, var in self._checkboxes.items() if var.get()]
        if not selected:
            messagebox.showinfo("Nothing selected",
                                "Tick at least one table to clear.")
            return

        authored = [t for t in selected if t in AUTHORED_TABLES]
        warning = ""
        if authored:
            warning = (f"\n\n⚠ WARNING: {', '.join(authored)} contain "
                       f"hand-entered data that cannot be recovered!")

        msg = (f"This will permanently delete ALL rows from:\n\n"
               f"  " + "\n  ".join(selected) +
               f"\n\nin:\n  {self._db_path.name}{warning}"
               f"\n\nThis cannot be undone. Continue?")

        if not messagebox.askyesno("Confirm delete", msg, icon="warning"):
            return

        try:
            deleted = _clear_tables(self._db_path, selected)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        summary = "\n".join(f"  {t}: {n} rows deleted"
                            for t, n in deleted.items())
        messagebox.showinfo("Done", f"Cleared:\n\n{summary}")

        # Refresh counts
        self._load_table_list()


if __name__ == "__main__":
    App().mainloop()
