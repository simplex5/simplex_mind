"""history purge (SIMP-D2-026): dry-run and missing --yes delete nothing,
deletion clears messages + FTS, preserves token usage by default, --project
selects by branch."""
import sqlite3
from types import SimpleNamespace

import pytest

from conversation import conversation_db, conversation_purge


def _args(**overrides):
    base = dict(project=None, older_than=None, session=None, all=False,
                dry_run=False, yes=False, with_usage=False, vacuum=False)
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def conv_db(tmp_path, monkeypatch):
    """Temp conversation DB seeded with two sessions on different branches:
    'old' (alpha-branch, ancient) and 'new' (other-branch, far future)."""
    db_path = tmp_path / "conversation_history.db"
    monkeypatch.setattr(conversation_db, "DB_PATH", db_path)
    conn = conversation_db.get_connection()  # migrations create the schema
    conn.execute("INSERT INTO sessions (session_id, git_branch, last_message_at, message_count) "
                 "VALUES ('old', 'alpha-branch', '2020-01-01T00:00:00Z', 2)")
    conn.execute("INSERT INTO sessions (session_id, git_branch, last_message_at, message_count) "
                 "VALUES ('new', 'other-branch', '2099-01-01T00:00:00Z', 1)")
    for uuid, sid, content in (("m1", "old", "hello one"), ("m2", "old", "hello two"),
                               ("m3", "new", "hello three")):
        conn.execute("INSERT INTO messages (uuid, session_id, role, content, timestamp) "
                     "VALUES (?, ?, 'user', ?, '2020-01-01T00:00:00Z')", (uuid, sid, content))
    for uuid, sid in (("u1", "old"), ("u2", "new")):
        conn.execute("INSERT INTO message_usage (uuid, session_id, timestamp, output_tokens) "
                     "VALUES (?, ?, '2020-01-01T00:00:00Z', 10)", (uuid, sid))
    conn.commit()
    conn.close()
    return db_path


def _counts(db_path):
    con = sqlite3.connect(db_path)
    try:
        return {
            "sessions": con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
            "messages": con.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "fts": con.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0],
            "usage": con.execute("SELECT COUNT(*) FROM message_usage").fetchone()[0],
        }
    finally:
        con.close()


def test_dry_run_deletes_nothing(conv_db):
    result = conversation_purge.purge(_args(all=True, dry_run=True))
    assert result["success"] and not result["deleted"]
    assert result["matched_sessions"] == 2
    assert result["matched_messages"] == 3
    assert _counts(conv_db)["messages"] == 3


def test_missing_yes_refuses(conv_db):
    result = conversation_purge.purge(_args(all=True))
    assert not result["success"]
    assert "--yes" in result["error"]
    assert _counts(conv_db)["messages"] == 3


def test_older_than_purges_only_old_and_preserves_usage(conv_db):
    result = conversation_purge.purge(_args(older_than=30, yes=True))
    assert result["deleted"]
    counts = _counts(conv_db)
    assert counts["messages"] == 1          # only 'new' session's message left
    assert counts["fts"] == 1               # messages_ad trigger cleaned the index
    assert counts["usage"] == 2             # token accounting preserved
    assert counts["sessions"] == 2          # 'old' tombstoned, not dropped
    con = sqlite3.connect(conv_db)
    assert con.execute("SELECT message_count FROM sessions WHERE session_id='old'"
                       ).fetchone()[0] == 0
    con.close()


def test_with_usage_drops_usage_and_session_rows(conv_db):
    result = conversation_purge.purge(_args(session="new", yes=True, with_usage=True))
    assert result["deleted"]
    counts = _counts(conv_db)
    assert counts["usage"] == 1             # only 'old' usage remains
    assert counts["sessions"] == 1          # 'new' row dropped entirely
    assert counts["messages"] == 2


def test_project_selects_by_branch(conv_db, fake_projects):
    result = conversation_purge.purge(_args(project="alpha", dry_run=True))
    assert result["matched_sessions"] == 1
    assert result["matched_messages"] == 2


def test_unknown_project_raises(conv_db, fake_projects):
    with pytest.raises(ValueError, match="not registered"):
        conversation_purge.purge(_args(project="nope", dry_run=True))
