"""simplex backup (SIMP-D2-027): consistent copies land in a timestamped dir,
missing sources skip with a note, corrupt sources fail the run."""
import sqlite3
import sys

import backup_db


def _make_db(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (v TEXT)")
    con.executemany("INSERT INTO t (v) VALUES (?)", [(r,) for r in rows])
    con.commit()
    con.close()


def _run(monkeypatch, tmp_path, root):
    monkeypatch.setattr(backup_db, "REPO_ROOT", root)
    dest = tmp_path / "backups"
    monkeypatch.setattr(sys, "argv", ["backup_db.py", "--dest", str(dest)])
    rc = backup_db.main()
    stamps = list(dest.iterdir()) if dest.exists() else []
    return rc, (stamps[0] if stamps else None)


def test_backup_copies_all_present_dbs(fake_projects, monkeypatch, tmp_path, capsys):
    root = fake_projects["root"]
    _make_db(root / "database" / "memory" / "memory.db", ["a", "b"])
    _make_db(root / "database" / "tickets.db", ["c"])
    _make_db(fake_projects["proj_dir"] / "database" / "tickets.db", ["d", "e", "f"])
    rc, snap = _run(monkeypatch, tmp_path, root)
    assert rc == 0
    copied = sqlite3.connect(snap / "memory.db")
    assert copied.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2
    copied.close()
    copied = sqlite3.connect(snap / "tickets" / "alpha.db")
    assert copied.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 3
    copied.close()
    out = capsys.readouterr().out
    assert "skip   conversation_history.db" in out  # absent source is a note, not a failure


def test_corrupt_source_fails_the_run(fake_projects, monkeypatch, tmp_path, capsys):
    root = fake_projects["root"]
    bad = root / "database" / "memory" / "memory.db"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"definitely not sqlite")
    rc, _snap = _run(monkeypatch, tmp_path, root)
    assert rc == 1
    assert "FAIL   memory.db" in capsys.readouterr().err
