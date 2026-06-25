"""Reusable PDF rendering helpers.

Usage — Flask download response:
    from app.pdf_utils import render_pdf
    html = render_template("my_report_download.html", ...)
    return render_pdf(html, "my_report_2026-06-25.pdf")

Usage — write to disk (report export):
    from app.pdf_utils import save_pdf
    from pathlib import Path
    save_pdf(html, Path("report_export/retail_2026-06-25.pdf"))
"""
from __future__ import annotations

from pathlib import Path

from flask import Response


def _weasyprint_html():
    try:
        from weasyprint import HTML
        return HTML
    except ImportError:
        raise RuntimeError(
            "WeasyPrint is not installed. Run:  pip install weasyprint"
        )


def render_pdf(html: str, filename: str) -> Response:
    """Convert an HTML string to a PDF and return a Flask download Response."""
    HTML = _weasyprint_html()
    pdf_bytes = HTML(string=html).write_pdf()
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def save_pdf(html: str, filepath: Path) -> None:
    """Convert an HTML string to a PDF and write it to *filepath* on disk."""
    HTML = _weasyprint_html()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(str(filepath))
