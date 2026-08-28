"""Core South Sustainphase Monitoring (build plan step 1, 2026-08-27):
storage — replace per (day, stream), task/detail linkage, the recomputed
Excel-faithful classification (overall rollup, country-cell rollup) and
summary counts (due/completed/pending/attention)."""
from app import database
from app.db import sustain as db_sustain


def _task(excel_row, task_id, due_today="Yes", cadence="Daily",
          results=(None, "N/A", "N/A", "N/A"), details=None, provider="Adyen"):
    fr, it, pt, es = results
    return {
        "excel_row": excel_row, "task_id": str(task_id),
        "taxonomy": "Processing of Settlement Files",
        "process": f"Task {task_id}", "cadence": cadence,
        "due_today": due_today, "country": None, "provider": provider,
        "result_fr": fr, "result_it": it, "result_pt": pt, "result_es": es,
        "overall": None, "details": details or [],
    }


def _detail(excel_row, country="France", due_today="Yes",
            value=None, provider="Adyen for cards"):
    col = {"France": "result_fr", "Italy": "result_it",
           "Portugal": "result_pt", "Spain": "result_es"}[country]
    d = {
        "excel_row": excel_row, "cadence": "Daily", "due_today": due_today,
        "country": country, "provider": provider,
        "result_fr": "N/A", "result_it": "N/A", "result_pt": "N/A",
        "result_es": "N/A", "overall": None,
    }
    d[col] = value
    return d


def _setup(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_sustain.init_schema(db_path)
    return database.get_connection(db_path)


def test_replace_day_stream_links_details_and_keeps_other_tabs(tmp_path):
    conn = _setup(tmp_path)
    try:
        counts = db_sustain.replace_day_stream(
            conn, "2026-09-01", "Retail",
            [_task(7, 1), _task(10, 2, details=[_detail(11), _detail(12)])])
        assert counts == {"tasks": 2, "details": 2}
        db_sustain.replace_day_stream(conn, "2026-09-01", "eCom", [_task(7, 1)])

        # re-import of the same tab replaces, other tab untouched
        db_sustain.replace_day_stream(
            conn, "2026-09-01", "Retail", [_task(7, 1)])
        retail = db_sustain.list_tasks(conn, "2026-09-01", "Retail")
        ecom = db_sustain.list_tasks(conn, "2026-09-01", "eCom")
        assert len(retail) == 1 and len(ecom) == 1
        # replaced parent's detail rows are gone too
        orphan = conn.execute(
            "SELECT COUNT(*) FROM sustain_task_details").fetchone()[0]
        assert orphan == 0
    finally:
        conn.close()


def test_list_tasks_orders_by_excel_row_with_details(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_sustain.replace_day_stream(
            conn, "2026-09-01", "Retail",
            [_task(27, 5), _task(10, 4, details=[_detail(12), _detail(11)])])
        tasks = db_sustain.list_tasks(conn, "2026-09-01", "Retail")
        assert [t["task_id"] for t in tasks] == ["4", "5"]
        assert [d["excel_row"] for d in tasks[0]["details"]] == [11, 12]
        assert tasks[1]["details"] == []
    finally:
        conn.close()


def test_list_tabs(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_sustain.replace_day_stream(conn, "2026-09-02", "Retail", [_task(7, 1)])
        db_sustain.replace_day_stream(conn, "2026-09-01", "eCom",
                                      [_task(7, 1), _task(8, 2)])
        tabs = db_sustain.list_tabs(conn)
        assert [(t["day"], t["stream"], t["task_count"]) for t in tabs] == [
            ("2026-09-01", "eCom", 2), ("2026-09-02", "Retail", 1)]
    finally:
        conn.close()


def test_empty_db_is_tolerated(tmp_path):
    db_path = tmp_path / "bare.db"
    database.init_db(db_path).close()   # no sustain init_schema
    conn = database.get_connection(db_path)
    try:
        assert db_sustain.task_count(conn) == 0
        assert db_sustain.list_tabs(conn) == []
        assert db_sustain.list_tasks(conn, "2026-09-01", "Retail") == []
    finally:
        conn.close()


# --- classification: mirrors the workbook's L7 / H10 formulas -----------

def test_derive_overall_mirrors_L_formula():
    f = db_sustain.derive_overall
    assert f("No", ["OK", "OK", "OK", "OK"]) == "Not due"
    # On occurrence: nothing entered / review / partial / complete
    assert f("On occurrence", [None, None, None, None]) == "No occurrence"
    assert f("On occurrence", ["Review", None, None, None]) == "Review"
    assert f("On occurrence", ["OK", None, None, None]) == "Pending"
    assert f("On occurrence", ["OK", "OK", "OK", "OK"]) == "OK"
    # Due: precedence Review > Pending > OK; all-N/A; blank fallback
    assert f("Yes", ["Review", "OK", "OK", "OK"]) == "Review"
    assert f("Yes", ["Pending", "OK", "N/A", "N/A"]) == "Pending"
    assert f("Yes", ["OK", "N/A", "N/A", "N/A"]) == "OK"
    assert f("Yes", ["N/A", "N/A", "N/A", "N/A"]) == "N/A"
    assert f("Yes", [None, None, None, None]) == "Pending"
    # free text alone falls through to Pending (Excel-faithful)
    assert f("Yes", ["missing file 123", "N/A", "N/A", "N/A"]) == "Pending"
    # COUNTIF is case-insensitive → so are we
    assert f("Yes", ["ok", "n/a", "n/a", "n/a"]) == "OK"


def test_derive_country_cell_rolls_up_details():
    f = db_sustain.derive_country_cell
    ok = _detail(11, "France", value="OK")
    blank = _detail(12, "France", value=None)
    issue = _detail(13, "France", value="acct 4711 unclear")
    notdue = _detail(14, "France", due_today="No", value="Not due")
    italy = _detail(15, "Italy", value="OK")
    assert f([italy], "France") == "N/A"          # no due French rows
    assert f([ok, blank], "France") == "Pending"  # any blank due row
    assert f([ok, issue], "France") == "Review"   # free text ⇒ Review
    assert f([ok, notdue], "France") == "OK"      # not-due rows ignored
    parent = _task(10, 4, details=[ok, issue, italy])
    cells = db_sustain.derive_cells(parent)
    assert cells == ["Review", "OK", "N/A", "N/A"]
    # a parent without details uses its own literal cells
    simple = _task(7, 1, results=("OK", "N/A", "N/A", "N/A"))
    assert db_sustain.derive_cells(simple) == ["OK", "N/A", "N/A", "N/A"]


def test_task_status_and_free_text_attention():
    f = db_sustain.task_status
    assert f(_task(7, 1, results=("OK", "N/A", "N/A", "N/A"))) == "done"
    assert f(_task(7, 1, results=("N/A", "N/A", "N/A", "N/A"))) == "done"
    assert f(_task(7, 1, results=(None, "N/A", "N/A", "N/A"))) == "pending"
    assert f(_task(7, 1, due_today="No")) == "not_due"
    # free text on a simple parent ⇒ attention (even though Excel's L
    # would let it fall through to Pending/OK)
    assert f(_task(7, 1, results=("file missing", "OK", "N/A", "N/A"))) \
        == "attention"
    # free text inside a detail row ⇒ Review rollup ⇒ attention
    assert f(_task(10, 4, details=[_detail(11, value="diff 12,50 EUR")])) \
        == "attention"


def test_attention_items_collects_verbatim_notes(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_sustain.replace_day_stream(conn, "2026-09-01", "Retail", [
            _task(7, 1, results=("file missing", "N/A", "N/A", "N/A"),
                  provider="Adyen (POS)"),
            _task(8, 2, results=("OK", "N/A", "N/A", "N/A")),
            _task(10, 4, details=[
                _detail(11, "Italy", value="diff 12,50 EUR",
                        provider="Cash"),
                _detail(12, "Spain", value="Review", provider="Cash"),
                _detail(13, "France", value="OK"),
                _detail(14, "France", due_today="No", value="odd but not due"),
            ]),
        ])
        items = db_sustain.attention_items(conn, "2026-09-01", "Retail")
        assert [(i["task_id"], i["country"], i["provider"], i["text"])
                for i in items] == [
            ("1", "France", "Adyen (POS)", "file missing"),
            ("4", "Italy", "Cash", "diff 12,50 EUR"),
            ("4", "Spain", "Cash", "Review"),
        ]
        assert items[0]["process"] == "Task 1"
    finally:
        conn.close()


def test_overview_counts_per_tab_and_repeat_offenders(tmp_path):
    conn = _setup(tmp_path)
    try:
        for day in ("2026-09-01", "2026-09-02", "2026-09-03"):
            db_sustain.replace_day_stream(conn, day, "Retail", [
                _task(7, 1, results=(
                    "same issue" if day != "2026-09-02" else "OK",
                    "N/A", "N/A", "N/A"), provider="Adyen (POS)"),
                _task(8, 2, results=(
                    "one-day thing" if day == "2026-09-01" else "OK",
                    "N/A", "N/A", "N/A"), provider="Cash"),
            ])
        overview = db_sustain.overview(conn)
        assert [(o["day"], o["stream"], o["counts"]["attention"])
                for o in overview] == [
            ("2026-09-01", "Retail", 2), ("2026-09-02", "Retail", 0),
            ("2026-09-03", "Retail", 1)]

        offenders = db_sustain.repeat_offenders(conn)
        assert len(offenders) == 1   # task 1 on 2 days; task 2 only once
        off = offenders[0]
        assert off["task_id"] == "1" and off["stream"] == "Retail"
        assert off["days"] == ["2026-09-01", "2026-09-03"]
        assert off["texts"] == ["same issue"]   # deduped verbatim notes
    finally:
        conn.close()


def test_summary_counts(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_sustain.replace_day_stream(conn, "2026-09-01", "Retail", [
            _task(7, 1, results=("OK", "N/A", "N/A", "N/A")),      # completed
            _task(8, 2, results=("N/A", "N/A", "N/A", "N/A")),     # completed
            _task(9, 3, results=(None, "N/A", "N/A", "N/A")),      # pending
            _task(10, 4, details=[_detail(11, value=None)]),       # pending
            _task(27, 5, results=("odd diff", "N/A", "N/A", "N/A")),  # attention
            _task(28, 6, due_today="No"),                          # not due
            _task(29, 7, due_today="On occurrence",
                  results=("Review", None, None, None)),           # attention, not due
        ])
        counts = db_sustain.summary_counts(conn, "2026-09-01", "Retail")
        assert counts == {"due": 5, "completed": 2, "pending": 2,
                          "attention": 2}
    finally:
        conn.close()
