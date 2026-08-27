"""CORE SOUTH Smoke Testing (build plan step 1, 2026-08-27): storage —
replace-all import, scenario/step linkage, OMNI/ECOM split, overview counts."""
from app import database
from app.db import smoke as db_smoke


def _scenario(row_id, ws, package="Ship from Campus South", status="Not Started",
              steps=None):
    return {
        "row_id": row_id, "package": package, "ws": ws,
        "scenario": f"Scenario {row_id}", "comment": None, "status": status,
        "company_code": "1000", "sales_org": "1000", "plant": "DC01",
        "store_code": None, "steps": steps or [],
    }


def _step(row_id, text="Do the thing"):
    return {
        "row_id": row_id, "step": text, "expected_result": "It works",
        "comment": None, "owner_email": "a@b.com", "owner": "A B",
        "ws_executing": "eCOM", "aspen_ticket": None,
        "execution_status": None, "progress": None,
    }


def _setup(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()
    db_smoke.init_schema(db_path)
    return database.get_connection(db_path)


def test_replace_all_links_steps_to_their_scenario(tmp_path):
    conn = _setup(tmp_path)
    try:
        scenarios = [
            _scenario(1, "eCOM", steps=[_step(10), _step(11)]),
            _scenario(2, "Retail", steps=[_step(20)]),
        ]
        counts = db_smoke.replace_all(conn, scenarios)
        assert counts == {"scenarios": 2, "steps": 3}

        ecom = db_smoke.list_scenarios(conn, "eCOM")
        assert len(ecom) == 1
        assert [s["row_id"] for s in ecom[0]["steps"]] == [10, 11]

        retail = db_smoke.list_scenarios(conn, "Retail")
        assert len(retail) == 1
        assert [s["row_id"] for s in retail[0]["steps"]] == [20]
    finally:
        conn.close()


def test_replace_all_clears_previous_import(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_smoke.replace_all(conn, [_scenario(1, "eCOM", steps=[_step(10)])])
        db_smoke.replace_all(conn, [_scenario(2, "Retail", steps=[_step(20)])])
        assert db_smoke.list_scenarios(conn, "eCOM") == []
        retail = db_smoke.list_scenarios(conn, "Retail")
        assert len(retail) == 1 and retail[0]["row_id"] == 2
    finally:
        conn.close()


def test_get_scenario_returns_its_steps(tmp_path):
    conn = _setup(tmp_path)
    try:
        db_smoke.replace_all(conn, [_scenario(1, "eCOM", steps=[_step(10), _step(11)])])
        scenario_id = db_smoke.list_scenarios(conn, "eCOM")[0]["id"]
        scenario = db_smoke.get_scenario(conn, scenario_id)
        assert len(scenario["steps"]) == 2
        assert db_smoke.get_scenario(conn, 99999) is None
    finally:
        conn.close()


def test_is_omni_package_matches_the_three_omni_packages():
    assert db_smoke.is_omni_package("Click & Collect")
    assert db_smoke.is_omni_package("ship from store")  # case-insensitive
    assert db_smoke.is_omni_package("Return in Store")
    assert not db_smoke.is_omni_package("Ship from Campus South")
    assert not db_smoke.is_omni_package(None)


def test_overview_counts_splits_omni_from_ecom_and_folds_blank_status(tmp_path):
    conn = _setup(tmp_path)
    try:
        scenarios = [
            _scenario(1, "eCOM", package="Click & Collect", status="Not Started"),
            _scenario(2, "eCOM", package="Ship from Campus South", status="In Progress"),
            _scenario(3, "eCOM", package="Ship from Campus South", status=""),  # blank
            _scenario(4, "eCOM", package="Ship from Campus South", status="Completed"),
            _scenario(5, "Retail", package="Retail Silver Bullet", status="Not Started"),
        ]
        db_smoke.replace_all(conn, scenarios)
        counts = db_smoke.overview_counts(conn)

        assert counts["omni"] == {"total": 1, "not_started": 1, "in_progress": 0,
                                   "completed": 0}
        # blank status (scenario 3) folds into not_started
        assert counts["ecom"] == {"total": 3, "not_started": 1, "in_progress": 1,
                                   "completed": 1}
        assert counts["retail"] == {"total": 1, "not_started": 1, "in_progress": 0,
                                     "completed": 0}
    finally:
        conn.close()


def test_list_scenarios_tolerates_missing_table(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()  # smoke tables never created
    conn = database.get_connection(db_path)
    try:
        assert db_smoke.list_scenarios(conn, "eCOM") == []
    finally:
        conn.close()


def test_scenario_count_for_dashboard_badge(tmp_path):
    conn = _setup(tmp_path)
    try:
        assert db_smoke.scenario_count(conn) == 0
        db_smoke.replace_all(conn, [
            _scenario(1, "eCOM", steps=[_step(10)]),
            _scenario(2, "Retail", steps=[_step(20)]),
        ])
        assert db_smoke.scenario_count(conn) == 2
    finally:
        conn.close()


def test_scenario_count_tolerates_missing_table(tmp_path):
    db_path = tmp_path / "s.db"
    database.init_db(db_path).close()  # smoke tables never created
    conn = database.get_connection(db_path)
    try:
        assert db_smoke.scenario_count(conn) == 0
    finally:
        conn.close()
