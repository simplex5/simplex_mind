from tickets import ticket_db


def test_create_ticket_id_format_and_counter(fake_projects):
    r1 = ticket_db.create_ticket("task", "First", target="alpha")
    r2 = ticket_db.create_ticket("bug", "Second", target="alpha")
    assert r1["success"] and r2["success"]
    assert r1["id"] == "ALPH-T9-001"
    assert r2["id"] == "ALPH-T9-002"
    assert r1["ticket"]["project"] == "alpha"
    assert r1["ticket"]["status"] == "open"


def test_create_rejects_invalid_type_and_priority(fake_projects):
    assert not ticket_db.create_ticket("chore", "X", target="alpha")["success"]
    assert not ticket_db.create_ticket("task", "X", priority="urgent", target="alpha")["success"]


def test_create_unknown_target_fails_cleanly(fake_projects):
    r = ticket_db.create_ticket("task", "X", target="ghost")
    assert r["success"] is False
    assert "Unknown project target" in r["error"]


def test_update_sets_and_clears_resolved_at(fake_projects):
    tid = ticket_db.create_ticket("task", "Lifecycle", target="alpha")["id"]
    done = ticket_db.update_ticket(tid, target="alpha", status="done")
    assert done["ticket"]["resolved_at"] is not None
    reopened = ticket_db.update_ticket(tid, target="alpha", status="open")
    assert reopened["ticket"]["resolved_at"] is None


def test_update_rejects_invalid_status(fake_projects):
    tid = ticket_db.create_ticket("task", "X", target="alpha")["id"]
    r = ticket_db.update_ticket(tid, target="alpha", status="finished")
    assert r["success"] is False


def test_update_missing_ticket(fake_projects):
    r = ticket_db.update_ticket("ALPH-T9-999", target="alpha", status="done")
    assert r["success"] is False and "not found" in r["error"]


def test_get_ticket_routes_by_prefix(fake_projects):
    tid = ticket_db.create_ticket("task", "Routed", target="alpha")["id"]
    # No explicit target: must infer 'alpha' from the ALPH prefix
    r = ticket_db.get_ticket(tid)
    assert r["success"] and r["ticket"]["title"] == "Routed"


def test_append_note_accumulates(fake_projects):
    tid = ticket_db.create_ticket("task", "Notes", target="alpha")["id"]
    ticket_db.append_note(tid, "first", target="alpha")
    r = ticket_db.append_note(tid, "second", target="alpha")
    notes = r["ticket"]["notes"]
    assert "first" in notes and "second" in notes
    assert notes.index("first") < notes.index("second")


def test_list_defaults_to_open_and_filters(fake_projects):
    a = ticket_db.create_ticket("task", "Open one", target="alpha")["id"]
    b = ticket_db.create_ticket("bug", "Closed one", target="alpha")["id"]
    ticket_db.update_ticket(b, target="alpha", status="done")
    r = ticket_db.list_tickets(target="alpha")
    ids = {t["id"] for t in r["tickets"]}
    assert a in ids and b not in ids
    r_all = ticket_db.list_tickets(target="alpha", show_all=True)
    assert {a, b} <= {t["id"] for t in r_all["tickets"]}


def test_list_orders_by_priority(fake_projects):
    lo = ticket_db.create_ticket("task", "low", priority="low", target="alpha")["id"]
    crit = ticket_db.create_ticket("task", "crit", priority="critical", target="alpha")["id"]
    r = ticket_db.list_tickets(target="alpha")
    ids = [t["id"] for t in r["tickets"]]
    assert ids.index(crit) < ids.index(lo)
