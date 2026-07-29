"""WAL journal mode (SIMP-D2-035): memory.db and tickets.db must run WAL so
per-prompt read-only hook connections (protocol_gate) never collide with live
session writes. The explicit risk being pinned: a read-only URI open against a
WAL database needs the -shm sidecar handling to work on this platform."""
from memory import protocol_gate
from tickets import ticket_db


def test_memory_db_uses_wal_and_read_only_open_works(mem_db):
    mem_db.add_entry("wal round-trip", entry_type="fact")
    writer = mem_db.get_connection()
    assert writer.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

    # The live scenario: gate's read-only open while a writer is connected.
    ro = protocol_gate._read_only(mem_db.DB_PATH)
    assert ro.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0] == 1
    ro.close()
    writer.close()

    # And after all writers closed (checkpointed, sidecars possibly removed).
    ro2 = protocol_gate._read_only(mem_db.DB_PATH)
    assert ro2.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0] == 1
    ro2.close()


def test_tickets_db_uses_wal(fake_projects):
    conn = ticket_db.get_connection(target="alpha")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()
