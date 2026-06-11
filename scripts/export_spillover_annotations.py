"""Export spillover annotations to a JSON file and preview in browser."""
from __future__ import annotations

import json
import sqlite3
import tempfile

import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox


def _read_annotations(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT
            a.spillover_id,
            s.excel_row,
            s.name,
            s.country,
            a.critical_for_signoff,
            a.comment_for_signoff
        FROM spillover_annotations a
        LEFT JOIN spillover s ON s.spillover_id = a.spillover_id
        WHERE a.critical_for_signoff IS NOT NULL
           OR a.comment_for_signoff  IS NOT NULL
        ORDER BY COALESCE(s.excel_row, a.spillover_id)
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _build_html(annotations: list[dict], db_path: Path) -> str:
    has_spillover = any(r["excel_row"] is not None for r in annotations)

    rows_html = ""
    for a in annotations:
        rows_html += f"""
        <tr>
            <td class="num">{a['spillover_id']}</td>
            <td class="num">{a['excel_row'] if a['excel_row'] is not None else '—'}</td>
            <td>{a['name'] or '—'}</td>
            <td>{a['country'] or '—'}</td>
            <td>{a['critical_for_signoff'] or ''}</td>
            <td>{a['comment_for_signoff'] or ''}</td>
        </tr>"""

    warning = ""
    if not has_spillover:
        warning = """<div class="warn">
            ⚠ Spillover rows not found in this database — excel_row and name columns are empty.
            The export still contains all annotation data and is safe to import.
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Spillover Annotations Export</title>
<style>
  body {{ font-family: system-ui, sans-serif; font-size: 13px; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.3rem; margin-bottom: 0.25rem; }}
  .meta {{ color: #666; margin-bottom: 1.5rem; font-size: 12px; }}
  .warn {{ background: #fff3cd; border: 1px solid #ffc107; padding: 0.75rem 1rem;
           border-radius: 4px; margin-bottom: 1rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th {{ background: #f0f0f0; text-align: left; padding: 6px 10px;
        border-bottom: 2px solid #ccc; white-space: nowrap; }}
  td {{ padding: 5px 10px; border-bottom: 1px solid #e8e8e8; vertical-align: top; }}
  tr:hover td {{ background: #fafafa; }}
  .num {{ color: #555; width: 60px; }}
  .dim {{ color: #888; font-size: 11px; white-space: nowrap; }}
  .comment {{ max-width: 320px; font-size: 12px; color: #444; }}
</style>
</head>
<body>
<h1>Spillover Annotations Export</h1>
<p class="meta">Database: {db_path}<br>Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;·&nbsp; {len(annotations)} annotation(s)</p>
{warning}
<table>
  <thead>
    <tr>
      <th>spillover_id</th>
      <th>excel_row</th>
      <th>Name</th>
      <th>Country</th>
      <th>Critical for sign-off</th>
      <th>Comment for sign-off</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>
</body>
</html>"""


def _save_json(annotations: list[dict], db_path: Path) -> Path:
    out_path = db_path.parent / f"spillover_annotations_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        "exported_at": datetime.now().isoformat(),
        "source_db": str(db_path),
        "annotations": [
            {
                "spillover_id": a["spillover_id"],
                "excel_row": a["excel_row"],
                "name": a["name"],
                "country": a["country"],
                "critical_for_signoff": a["critical_for_signoff"],
                "comment_for_signoff": a["comment_for_signoff"],
            }
            for a in annotations
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Export Spillover Annotations")
        self.resizable(False, False)
        self._build()

    def _build(self):
        pad = dict(padx=14, pady=6)

        tk.Label(self, text="Select the database to export from:",
                 anchor="w", font=("", 10)).grid(row=0, column=0, columnspan=2,
                                                   sticky="w", **pad)

        self._db_var = tk.StringVar()
        tk.Entry(self, textvariable=self._db_var, width=58).grid(
            row=1, column=0, padx=(14, 4), pady=2, sticky="ew")
        tk.Button(self, text="Browse…", command=self._pick_db).grid(
            row=1, column=1, padx=(0, 14), pady=2)

        self._status = tk.Label(self, text="", anchor="w", fg="#555",
                                wraplength=460, justify="left")
        self._status.grid(row=2, column=0, columnspan=2, sticky="w",
                          padx=14, pady=(8, 4))

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(4, 14))

        self._btn_preview = tk.Button(btn_frame, text="Preview in browser",
                                      width=20, command=self._preview,
                                      state="disabled")
        self._btn_preview.pack(side="left", padx=6)

        self._btn_export = tk.Button(btn_frame, text="Export to JSON",
                                     width=20, command=self._export,
                                     bg="#0071e3", fg="white",
                                     activebackground="#005bb5",
                                     relief="flat", pady=4,
                                     state="disabled")
        self._btn_export.pack(side="left", padx=6)

        self._annotations: list[dict] = []
        self._db_path: Path | None = None

    def _pick_db(self):
        p = filedialog.askopenfilename(
            title="Select source database",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")])
        if not p:
            return
        self._db_path = Path(p)
        self._db_var.set(p)
        self._status.config(text="Reading…")
        self.update()
        try:
            self._annotations = _read_annotations(self._db_path)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            self._status.config(text="")
            return
        orphaned = sum(1 for a in self._annotations if a["excel_row"] is None)
        msg = f"Found {len(self._annotations)} annotation(s)."
        if orphaned:
            msg += f"  ⚠ {orphaned} are orphaned (spillover rows missing — run import first for best results)."
        self._status.config(text=msg)
        state = "normal" if self._annotations else "disabled"
        self._btn_preview.config(state=state)
        self._btn_export.config(state=state)

    def _preview(self):
        if not self._annotations:
            return
        html = _build_html(self._annotations, self._db_path)
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                          mode="w", encoding="utf-8")
        tmp.write(html)
        tmp.close()
        webbrowser.open(f"file:///{tmp.name}")

    def _export(self):
        if not self._annotations:
            return
        out = _save_json(self._annotations, self._db_path)
        messagebox.showinfo("Exported",
                            f"Saved {len(self._annotations)} annotation(s) to:\n{out}")
        self._status.config(text=f"Saved → {out.name}")


if __name__ == "__main__":
    App().mainloop()
