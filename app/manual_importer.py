"""Parse the two "Manual Test Cases | …" tabs — Retail and ECOM.

The tabs are close siblings but NOT identical (the Retail one mirrors the
Retail tab + Store No. / Sales Status; the ECOM one mirrors the ECOM tab
with Jira ID / Description Change), so each has its own header map — but
one shared parse routine. NOTE: the workbook also still contains two older
EMPTY stub tabs WITHOUT the pipe in the name ("Manual Test Cases Retail") —
the sheet names below deliberately target the pipe versions only.

Match key for BOTH verticals = test case + country (like Retail). The ECOM
tab's Jira ID column is stored as a plain field — it is blank in the real
data, so it cannot carry the match (unlike the ECOM board).

Usage:
    python -m app.manual_importer            # parses both tabs, prints rows
    python -m app.manual_importer --config path/to/settings.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from app.config_loader import load_config
from app.read_defects import ParseError, _clean, _find_latest_xlsx, _normalise_header

# ---------------------------------------------------------------------------
# Header maps — normalised source header → clean field name
# Verified against: DTC_UAT_testtracking_ROE(46).xlsx (2026-08-05)
# ---------------------------------------------------------------------------

_HEADER_MAP_RETAIL: dict[str, str] = {
    "test case":                                 "test_case_id",           # match key
    "country":                                   "country",                # match key
    # name column under either spelling (same rule as the Retail tab)
    "test case description":                     "testcase_name",
    "testcase name":                             "testcase_name",
    "testcase scenario":                         "testcase_scenario",
    "status":                                    "status",
    "assigned to":                               "assigned_to",
    "key user responsible":                      "key_user_responsible",
    "execution started":                         "execution_started",
    "execution completed":                       "execution_completed",
    "store no.":                                 "store_no",
    "sales status":                              "sales_status",
    "order number/transaction number":           "order_number",
    # bare duplicate column at the far right of the tab — alias; the
    # first-wins rule keeps the /Transaction column
    "order number":                              "order_number",
    "old order numbers/transaction numbers":     "old_order_numbers",
    "defect id (if applicable)":                 "defect_id_ref",
    "old defect ids":                            "old_defect_ids",
    "s4 sales order":                            "s4_sales_order",
    "s4 billing documents":                      "s4_billing_documents",
    "s4 journal invoice entry":                  "s4_journal_invoice_entry",
    "delivery note":                             "delivery_note",
    "comment":                                   "comment",
    "reason for pass with reservation":          "reason_for_pass_with_reservation",
    # recognised but intentionally ignored
    "concatenate":                               "__ignored__",
}

_HEADER_MAP_ECOM: dict[str, str] = {
    "test case id":                              "test_case_id",           # match key
    "test case":                                 "test_case_id",
    "country":                                   "country",                # match key
    "testcase name":                             "testcase_name",
    "testcase scenario":                         "testcase_scenario",
    "status":                                    "status",
    "assigned to":                               "assigned_to",
    "jira id":                                   "jira_id",
    "description change":                        "description_change",
    "date execution started":                    "execution_started",
    "execution started":                         "execution_started",
    "order number/transaction number":           "order_number",
    "old order numbers/transaction numbers":     "old_order_numbers",
    "defect id (if applicable)":                 "defect_id_ref",
    "old defect ids":                            "old_defect_ids",
    "s4 sales order":                            "s4_sales_order",
    "s4 billing documents":                      "s4_billing_documents",
    "s4 journal invoice entry":                  "s4_journal_invoice_entry",
    "delivery note (for tradeco)":               "delivery_note",
    "delivery note":                             "delivery_note",
    "comments":                                  "comment",
    "comment":                                   "comment",
    "reason for pass with reservation":          "reason_for_pass_with_reservation",
}

_SPECS: dict[str, dict] = {
    "manual_retail": {
        "cfg_key":       "manual_retail_sheet_name",
        "default_sheet": "Manual Test Cases | Retail",
        "header_map":    _HEADER_MAP_RETAIL,
    },
    "manual_ecom": {
        "cfg_key":       "manual_ecom_sheet_name",
        "default_sheet": "Manual Test Cases | ECOM",
        "header_map":    _HEADER_MAP_ECOM,
    },
}


def output_fields(vertical: str) -> list[str]:
    """De-duplicated field list for a vertical (aliases collapse to one)."""
    header_map = _SPECS[vertical]["header_map"]
    return list(dict.fromkeys(
        v for v in header_map.values() if not v.startswith("__")))


def parse_manual(cfg: dict, vertical: str, xlsx_path: Path | None = None) -> dict:
    """Parse one manual tab. Same contract as parse_retail:

    Returns {xlsx_path, sheet_name, rows, unmapped_headers, missing_fields};
    each row dict has excel_row, all output fields and _skip_reason
    ("" | "incomplete key"). Fully blank rows are dropped silently.
    Raises ParseError on fatal errors.
    """
    spec = _SPECS[vertical]
    sheet_name = cfg.get(spec["cfg_key"], spec["default_sheet"])
    fields = output_fields(vertical)

    if xlsx_path is None:
        folder = Path(cfg["downloads_folder"])
        stem = cfg["filename_stem"]
        if not folder.exists():
            raise ParseError(f"downloads_folder does not exist: {folder}")
        xlsx_path = _find_latest_xlsx(folder, stem)
        if xlsx_path is None:
            raise ParseError(
                f"No matching .xlsx file found in {folder}\n"
                f"  Expected name matching: {stem}[optional (n)].xlsx"
            )

    with pd.ExcelFile(xlsx_path) as xf:
        if sheet_name not in xf.sheet_names:
            raise ParseError(
                f"Sheet '{sheet_name}' not found in workbook.\n"
                f"  Sheets present: {xf.sheet_names}"
            )
        df = xf.parse(sheet_name, header=0, dtype=str)

    header_map = spec["header_map"]
    col_rename: dict[str, str] = {}
    unmapped: list[str] = []

    for raw in df.columns:
        norm = _normalise_header(raw)
        if norm.startswith("unnamed:"):
            continue  # blank Excel header cell — pandas placeholder, ignore
        field = header_map.get(norm)
        if field is None:
            unmapped.append(raw)
        elif field == "__ignored__":
            pass
        elif field in col_rename.values():
            # alias whose field an earlier header already filled — first wins
            # (renaming both would duplicate a column name and the row loop
            # would read a pandas Series instead of a value)
            unmapped.append(raw)
        else:
            col_rename[raw] = field

    df = df.rename(columns=col_rename)
    present_fields = [f for f in fields if f in df.columns]
    missing_fields = [f for f in fields if f not in df.columns]
    df_out = df[present_fields].copy()

    rows: list[dict] = []
    for excel_row, (_, pandas_row) in enumerate(df_out.iterrows(), start=2):
        row: dict = {"excel_row": excel_row}
        for field in present_fields:
            row[field] = _clean(pandas_row[field])
        for field in missing_fields:
            row[field] = ""

        if all(row[f] == "" for f in fields):
            continue  # fully blank — ignore silently

        has_key = bool(row.get("test_case_id")) and bool(row.get("country"))
        row["_skip_reason"] = "" if has_key else "incomplete key"
        rows.append(row)

    return {
        "xlsx_path": xlsx_path,
        "sheet_name": sheet_name,
        "rows": rows,
        "unmapped_headers": unmapped,
        "missing_fields": missing_fields,
    }


def parse_manual_retail(cfg: dict, xlsx_path: Path | None = None) -> dict:
    return parse_manual(cfg, "manual_retail", xlsx_path)


def parse_manual_ecom(cfg: dict, xlsx_path: Path | None = None) -> dict:
    return parse_manual(cfg, "manual_ecom", xlsx_path)


def main(config_path: str | None = None) -> None:
    cfg = load_config(config_path)
    for vertical in _SPECS:
        try:
            result = parse_manual(cfg, vertical)
        except ParseError as exc:
            print(f"ERROR [{vertical}]: {exc}", file=sys.stderr)
            continue
        rows = result["rows"]
        ok = [r for r in rows if not r["_skip_reason"]]
        skip = [r for r in rows if r["_skip_reason"]]
        print(f"[{vertical}] {result['sheet_name']}: "
              f"{len(rows)} parsed | {len(ok)} ok | {len(skip)} would-skip")
        if result["unmapped_headers"]:
            print(f"  WARN unmapped columns: {result['unmapped_headers']}")
        if result["missing_fields"]:
            print(f"  WARN missing expected fields: {result['missing_fields']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse both Manual Test Cases tabs and print a summary (no DB writes)."
    )
    parser.add_argument("--config", default=None, help="Path to settings.yaml")
    args = parser.parse_args()
    main(config_path=args.config)
