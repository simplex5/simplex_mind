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
