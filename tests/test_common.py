import sqlite3

from _common import run_migrations, PRIORITY_ORDER, PRIORITY_SQL_CASE, utc_now_db, utc_now_iso_z


def test_migrations_run_once_and_in_order(tmp_path):
    db = tmp_path / "m.db"
    calls = []
    migrations = [
        (1, lambda c: calls.append(1) or c.execute("CREATE TABLE IF NOT EXISTS t (x)")),
        (2, lambda c: calls.append(2) or c.execute("ALTER TABLE t ADD COLUMN y")),
    ]
    conn = sqlite3.connect(db)
    assert run_migrations(conn, migrations) == 2
    assert calls == [1, 2]
    conn.close()

    # Second open: nothing re-runs
    conn = sqlite3.connect(db)
    assert run_migrations(conn, migrations) == 2
    assert calls == [1, 2]
    conn.close()


def test_migrations_resume_from_partial_version(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, [(1, lambda c: c.execute("CREATE TABLE t (x)"))])
    # Later release ships migration 2 — only 2 runs
    calls = []
    run_migrations(conn, [
        (1, lambda c: calls.append(1)),
        (2, lambda c: calls.append(2)),
    ])
    assert calls == [2]
    conn.close()


def test_priority_map_and_sql_case_agree():
    for name, rank in PRIORITY_ORDER.items():
        assert f"WHEN '{name}' THEN {rank}" in PRIORITY_SQL_CASE


def test_timestamp_formats():
    db_ts = utc_now_db()
    iso_ts = utc_now_iso_z()
    assert len(db_ts) == 19 and db_ts[10] == " "
    assert iso_ts.endswith("Z") and iso_ts[10] == "T"
