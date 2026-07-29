def test_add_and_get_entry(mem_db):
    r = mem_db.add_entry("The sky is blue", entry_type="fact", importance=7)
    assert r["success"]
    got = mem_db.get_entry(r["entry"]["id"])
    assert got["success"]
    assert got["entry"]["content"] == "The sky is blue"
    assert got["entry"]["importance"] == 7


def test_duplicate_content_not_duplicated(mem_db):
    first = mem_db.add_entry("same thing twice")
    second = mem_db.add_entry("same thing twice")
    # Content-hash dedup: second call must not create a distinct new entry
    assert first["success"]
    assert not (second.get("success") and second["entry"]["id"] != first["entry"]["id"])


def test_invalid_type_rejected(mem_db):
    r = mem_db.add_entry("x", entry_type="vibe")
    assert r["success"] is False


def test_update_entry(mem_db):
    eid = mem_db.add_entry("original", entry_type="fact")["entry"]["id"]
    r = mem_db.update_entry(eid, content="edited")
    assert r["success"]
    assert mem_db.get_entry(eid)["entry"]["content"] == "edited"


def test_soft_delete_hides_from_list(mem_db):
    eid = mem_db.add_entry("to be deleted")["entry"]["id"]
    assert mem_db.delete_entry(eid)["success"]
    listed = mem_db.list_entries()
    assert all(e["id"] != eid for e in listed.get("entries", []))


def test_list_filters_by_type(mem_db):
    mem_db.add_entry("a preference", entry_type="preference")
    mem_db.add_entry("a fact", entry_type="fact")
    r = mem_db.list_entries(entry_type="preference")
    assert r["success"]
    assert {e["type"] for e in r["entries"]} == {"preference"}


def test_search_underscore_matches_literally(mem_db):
    # '_' is a LIKE any-one-char wildcard; unescaped, snake_case queries
    # match imposters (SIMP-D2-034)
    mem_db.add_entry("using memory_write for notes", entry_type="fact")
    mem_db.add_entry("using memoryXwrite imposter", entry_type="fact")
    r = mem_db.search_entries("memory_write")
    contents = [e["content"] for e in r["entries"]]
    assert any("memory_write" in c for c in contents)
    assert all("memoryXwrite" not in c for c in contents)


def test_search_percent_matches_literally(mem_db):
    # '%' is a LIKE any-run wildcard; unescaped, it matched everything
    mem_db.add_entry("progress at 100% done", entry_type="fact")
    mem_db.add_entry("unrelated entry about cats", entry_type="fact")
    r = mem_db.search_entries("100%")
    contents = [e["content"] for e in r["entries"]]
    assert contents and all("100%" in c for c in contents)


def _set_fake_embedding(mem_db, eid):
    conn = mem_db.get_connection()
    conn.execute(
        "UPDATE memory_entries SET embedding = ?, embedding_model = ? WHERE id = ?",
        (b"\x00\x01\x02", "test-model", eid))
    conn.commit()
    conn.close()


def _raw_embedding(mem_db, eid):
    conn = mem_db.get_connection()
    row = conn.execute(
        "SELECT embedding, embedding_model FROM memory_entries WHERE id = ?",
        (eid,)).fetchone()
    conn.close()
    return row["embedding"], row["embedding_model"]


def test_content_update_clears_stale_embedding(mem_db):
    # The stored vector describes the old text — a content edit must clear it
    # so semantic search can't rank new content by the old meaning (SIMP-D2-034)
    eid = mem_db.add_entry("old content", entry_type="fact")["entry"]["id"]
    _set_fake_embedding(mem_db, eid)
    assert mem_db.update_entry(eid, content="new content")["success"]
    embedding, model = _raw_embedding(mem_db, eid)
    assert embedding is None
    assert model is None


def test_non_content_update_keeps_embedding(mem_db):
    eid = mem_db.add_entry("stable content", entry_type="fact")["entry"]["id"]
    _set_fake_embedding(mem_db, eid)
    assert mem_db.update_entry(eid, importance=9)["success"]
    embedding, model = _raw_embedding(mem_db, eid)
    assert embedding is not None
    assert model == "test-model"


# --- project-scoped recall + centralized expiry (SIMP-D2-037) ---

def test_scope_isolation_in_search(mem_db):
    mem_db.add_entry("alpha secret plans", scope="alpha")
    mem_db.add_entry("beta secret plans", scope="beta")
    mem_db.add_entry("global secret plans", scope="global")
    r = mem_db.search_entries("secret plans", project_scope="alpha")
    assert {e["content"] for e in r["entries"]} == {"alpha secret plans", "global secret plans"}
    r_all = mem_db.search_entries("secret plans", project_scope="*")
    assert len(r_all["entries"]) == 3
    r_glob = mem_db.search_entries("secret plans", project_scope="global")
    assert {e["content"] for e in r_glob["entries"]} == {"global secret plans"}


def test_scope_isolation_in_list_and_recent(mem_db):
    mem_db.add_entry("alpha fact", scope="alpha")
    mem_db.add_entry("global fact", scope="global")
    listed = mem_db.list_entries(project_scope="beta")
    assert {e["content"] for e in listed["entries"]} == {"global fact"}
    recent = mem_db.get_recent(hours=24, project_scope="beta")
    assert {e["content"] for e in recent["entries"]} == {"global fact"}


def test_expired_entry_invisible_everywhere(mem_db):
    # expiry was honored by list but ignored by search — the shared predicate
    # must make every read path agree
    mem_db.add_entry("stale entry", expires_at="2000-01-01 00:00:00", scope="global")
    mem_db.add_entry("fresh entry", scope="global")
    searched = {e["content"] for e in mem_db.search_entries("entry", project_scope="*")["entries"]}
    listed = {e["content"] for e in mem_db.list_entries(project_scope="*")["entries"]}
    assert "stale entry" not in searched and "fresh entry" in searched
    assert "stale entry" not in listed and "fresh entry" in listed


def test_add_entry_auto_scope_resolves_active_project(mem_db, fake_projects, on_branch):
    on_branch("alpha-branch")
    r = mem_db.add_entry("written during alpha session")
    assert r["entry"]["scope"] == "alpha"
    on_branch("develop")
    r2 = mem_db.add_entry("written on brain branch")
    assert r2["entry"]["scope"] == "global"


def test_migration_backfills_scope_from_tags(tmp_path, monkeypatch):
    """A legacy (pre-v3) DB gets scope backfilled from its project:<name> tags."""
    import json as _json
    import sqlite3
    from memory import memory_db

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    memory_db._migration_1_base_schema(conn)
    conn.execute(
        "INSERT INTO memory_entries (type, content, content_hash, tags) VALUES ('fact', 'tagged entry', 'h1', ?)",
        (_json.dumps(["project:alpha", "SIMP-D2-001"]),))
    conn.execute(
        "INSERT INTO memory_entries (type, content, content_hash) VALUES ('fact', 'untagged entry', 'h2')")
    conn.execute("PRAGMA user_version = 2")
    conn.commit()
    conn.close()

    monkeypatch.setattr(memory_db, "DB_PATH", db_path)
    monkeypatch.setattr(memory_db, "_schema_ready", False)
    conn = memory_db.get_connection()
    rows = {r["content"]: r["scope"]
            for r in conn.execute("SELECT content, scope FROM memory_entries")}
    conn.close()
    assert rows == {"tagged entry": "alpha", "untagged entry": "global"}


def test_bm25_corpus_respects_scope(mem_db):
    from memory import hybrid_search as hs
    mem_db.add_entry("quantum widget alpha", scope="alpha")
    mem_db.add_entry("quantum widget beta", scope="beta")
    mem_db.add_entry("quantum widget global", scope="global")
    contents = {e["content"] for e in hs.get_all_entries_for_bm25(project_scope="alpha")}
    assert contents == {"quantum widget alpha", "quantum widget global"}
