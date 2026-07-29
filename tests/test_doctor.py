"""Doctor: onboarding classification (the config-untracking seam) and exit
codes (SIMP-D2-021)."""
import doctor


def test_bare_root_is_fresh_clone(fake_repo):
    root = fake_repo()
    assert doctor.classify_onboarding(root) == "fresh_clone"


def test_dbs_without_config_is_lost_config(fake_repo):
    root = fake_repo(dbs=["database/memory/memory.db"])
    assert doctor.classify_onboarding(root) == "lost_config"


def test_projects_yaml_without_config_is_lost_config(fake_repo):
    root = fake_repo(projects_yaml=True)
    assert doctor.classify_onboarding(root) == "lost_config"


def test_config_true_is_onboarded(fake_repo):
    root = fake_repo(config={"onboarding_complete": True})
    assert doctor.classify_onboarding(root) == "onboarded"


def test_config_false_with_dbs_is_lost_config(fake_repo):
    # onboarding_complete: false + existing DBs = interrupted state, not fresh
    root = fake_repo(config={"onboarding_complete": False}, dbs=["database/tickets.db"])
    assert doctor.classify_onboarding(root) == "lost_config"


def test_corrupt_config_without_state_is_fresh_clone(fake_repo):
    root = fake_repo()
    (root / "database" / "config.json").write_text("{not json", encoding="utf-8")
    assert doctor.classify_onboarding(root) == "fresh_clone"


def _run_main(monkeypatch, argv):
    import sys
    monkeypatch.setattr(sys, "argv", ["doctor.py"] + argv)
    return doctor.main()


# --- DB integrity checks (SIMP-D2-040) ---

def test_db_integrity_fails_on_fk_violation(fake_repo):
    import sqlite3
    root = fake_repo(dbs=["database/memory/memory.db"])
    con = sqlite3.connect(root / "database" / "memory" / "memory.db")
    con.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    con.execute("CREATE TABLE child (id INTEGER PRIMARY KEY, "
                "parent_id INTEGER REFERENCES parent(id))")
    con.execute("INSERT INTO child (id, parent_id) VALUES (1, 999)")  # orphan
    con.commit()
    con.close()
    r = doctor.check_db_integrity(root)
    assert r["level"] == doctor.FAIL
    assert "foreign-key violation" in r["detail"]


def test_db_integrity_ok_on_healthy_dbs(fake_repo):
    import sqlite3
    root = fake_repo(dbs=["database/memory/memory.db", "database/tickets.db"])
    for db in ("database/memory/memory.db", "database/tickets.db"):
        con = sqlite3.connect(root / db)
        con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()
    r = doctor.check_db_integrity(root)
    assert r["level"] == doctor.OK
    assert "2 database(s)" in r["detail"]


def test_db_integrity_skips_missing_dbs(fake_repo):
    r = doctor.check_db_integrity(fake_repo())
    assert r["level"] == doctor.OK  # presence is other checks' business


def test_doctor_exits_1_on_fresh_clone(fake_repo, monkeypatch, capsys):
    root = fake_repo()
    rc = _run_main(monkeypatch, ["--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "fresh clone" in out
    assert "DEGRADED" in out


def test_doctor_reports_lost_config_remedy(fake_repo, monkeypatch, capsys):
    root = fake_repo(dbs=["database/memory/memory.db"])
    rc = _run_main(monkeypatch, ["--root", str(root)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "--mark-onboarded" in out
    assert "do NOT re-run onboarding" in out


def test_status_always_exits_0(fake_repo, monkeypatch, capsys):
    root = fake_repo()  # maximally degraded root
    rc = _run_main(monkeypatch, ["--root", str(root), "--status"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "failed" in out


def test_no_check_crash_goes_silent(fake_repo, monkeypatch):
    # A crashing check must surface as a FAIL result, never vanish
    def boom(root):
        raise RuntimeError("kaput")
    monkeypatch.setattr(doctor, "CHECKS", [boom])
    results = doctor.run_checks(fake_repo())
    assert len(results) == 1
    assert results[0]["level"] == "fail"
    assert "kaput" in results[0]["detail"]
