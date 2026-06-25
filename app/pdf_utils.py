"""Reusable PDF rendering helper.

Usage in any Flask route:
    from app.pdf_utils import render_pdf
    html = render_template("my_report_download.html", ...)
    return render_pdf(html, "my_report_2026-06-25.pdf")
"""
from __future__ import annotations

from flask import Response


def render_pdf(html: str, filename: str) -> Response:
    """Convert an HTML string to a PDF and return a Flask download Response.

    WeasyPrint is imported lazily so the app starts normally even if it is not
    installed — the error only surfaces when a PDF route is actually called.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        raise RuntimeError(
            "WeasyPrint is not installed. Run:  pip install weasyprint"
        )

    pdf_bytes = HTML(string=html).write_pdf()
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
