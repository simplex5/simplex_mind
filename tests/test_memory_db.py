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
