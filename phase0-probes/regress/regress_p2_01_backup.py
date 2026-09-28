"""P2-01 regression — concrete persistence/backup architecture (decision D-DB-4), executed with the real SQLite
online-backup API through Python's sqlite3 (the same sqlite3_backup_* C API that Microsoft.Data.Sqlite's
`SqliteConnection.BackupDatabase(destination, destinationName, sourceName)` wraps).

Architecture under test:
  lsax.db       (schema main)  journal + global tables + applied_idem   synchronous=FULL, WAL — authoritative
  lsax_proj.db  (ATTACHed as proj) projection tables + projection_meta watermark   synchronous=NORMAL — derived
  commit order  journal transaction first, then projection transaction carrying the watermark (projection may lag,
                never lead); startup / pre-transaction gate: watermark != journal head -> catch-up replay
  snapshot      online backup of schema `proj` only  (Python: src.backup(dst, name="proj");
                .NET: src.BackupDatabase(dst, "main", "proj"))
  disaster copy online backup of schema `main` (journal) at session end
"""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile

from regress_common import Suite

JOURNAL = """
CREATE TABLE IF NOT EXISTS main.timeline(id INTEGER PRIMARY KEY, parent_seq INTEGER);
CREATE TABLE IF NOT EXISTS main.commit_log(timeline_id INTEGER, seq INTEGER, idem_key TEXT, PRIMARY KEY(timeline_id, seq));
CREATE TABLE IF NOT EXISTS main.journal_event(timeline_id INTEGER, seq INTEGER, ord INTEGER, payload TEXT);
CREATE TABLE IF NOT EXISTS main.applied_idem(idem_key TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS main.runtime_state(k TEXT PRIMARY KEY, v);
"""
PROJ = """
CREATE TABLE IF NOT EXISTS proj.projection_meta(k TEXT PRIMARY KEY, v);
CREATE TABLE IF NOT EXISTS proj.vehicle(vehicle_id TEXT PRIMARY KEY, owner TEXT, odo INTEGER);
"""


class Store:
    def __init__(self, d):
        self.d = d
        self.db = sqlite3.connect(os.path.join(d, "lsax.db"), isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("ATTACH DATABASE ? AS proj", (os.path.join(d, "lsax_proj.db"),))
        self.db.execute("PRAGMA proj.journal_mode=WAL")
        self.db.execute("PRAGMA proj.synchronous=NORMAL")
        self.db.executescript(JOURNAL + PROJ)
        if not self.db.execute("SELECT 1 FROM main.timeline").fetchone():
            self.db.execute("INSERT INTO main.timeline VALUES(1, NULL)")
            self.db.execute("INSERT INTO main.runtime_state VALUES('active', 1)")

    # ------------------------------------------------------------------ journal
    def active(self):
        return self.db.execute("SELECT v FROM main.runtime_state WHERE k='active'").fetchone()[0]

    def path(self):
        """[(timeline, seq)] of the active path (single-level forks suffice for this test)."""
        t = self.active()
        parent = self.db.execute("SELECT parent_seq FROM main.timeline WHERE id=?", (t,)).fetchone()[0]
        prefix = [] if parent is None else [(1, s) for (s,) in self.db.execute(
            "SELECT seq FROM main.commit_log WHERE timeline_id=1 AND seq<=? ORDER BY seq", (parent,))]
        return prefix + [(t, s) for (s,) in self.db.execute(
            "SELECT seq FROM main.commit_log WHERE timeline_id=? ORDER BY seq", (t,))]

    def journal_commit(self, idem, events):
        t = self.active()
        self.db.execute("BEGIN IMMEDIATE")
        if self.db.execute("SELECT 1 FROM main.applied_idem WHERE idem_key=?", (idem,)).fetchone():
            self.db.execute("ROLLBACK")
            return None
        seq = (self.db.execute("SELECT MAX(seq) FROM main.commit_log WHERE timeline_id=?", (t,)).fetchone()[0] or 0) + 1
        self.db.execute("INSERT INTO main.commit_log VALUES(?,?,?)", (t, seq, idem))
        for o, e in enumerate(events):
            self.db.execute("INSERT INTO main.journal_event VALUES(?,?,?,?)", (t, seq, o, json.dumps(e, sort_keys=True)))
        self.db.execute("INSERT INTO main.applied_idem VALUES(?)", (idem,))
        self.db.execute("COMMIT")
        return (t, seq)

    # ------------------------------------------------------------------ projection
    def watermark(self):
        r = self.db.execute("SELECT v FROM proj.projection_meta WHERE k='watermark'").fetchone()
        return json.loads(r[0]) if r else None

    def _apply(self, pos):
        for (payload,) in self.db.execute("SELECT payload FROM main.journal_event WHERE timeline_id=? AND seq=? ORDER BY ord", pos).fetchall():
            e = json.loads(payload)
            self.db.execute("INSERT OR REPLACE INTO proj.vehicle VALUES(?,?,?)", (e["vid"], e["owner"], e["odo"]))

    def projection_commit(self, upto):
        """Apply every journal position after the watermark up to `upto` (inclusive), one projection transaction."""
        p = self.path()
        wm = self.watermark()
        start = 0 if wm is None else p.index(tuple(wm)) + 1
        end = p.index(tuple(upto)) + 1
        self.db.execute("BEGIN IMMEDIATE")
        for pos in p[start:end]:
            self._apply(pos)
        self.db.execute("INSERT OR REPLACE INTO proj.projection_meta VALUES('watermark', ?)", (json.dumps(list(upto)),))
        self.db.execute("COMMIT")

    def catch_up(self):
        p = self.path()
        if p and (self.watermark() is None or tuple(self.watermark()) != p[-1]):
            self.projection_commit(p[-1])

    def rebuild_from_scratch(self):
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("DELETE FROM proj.vehicle")
        self.db.execute("DELETE FROM proj.projection_meta")
        self.db.execute("COMMIT")
        self.catch_up()

    def proj_rows(self):
        return self.db.execute("SELECT vehicle_id, owner, odo FROM proj.vehicle ORDER BY vehicle_id").fetchall()

    def commit(self, idem, events, crash_between=False):
        pos = self.journal_commit(idem, events)
        if pos is None:
            return None
        if crash_between:
            return pos                                   # projection transaction never ran
        self.projection_commit(pos)
        return pos

    # ------------------------------------------------------------------ backups
    def snapshot(self, path):
        dst = sqlite3.connect(path)
        self.db.backup(dst, name="proj")                # == BackupDatabase(dst, "main", "proj")
        dst.close()

    def journal_backup(self, path):
        dst = sqlite3.connect(path)
        self.db.backup(dst, name="main")
        dst.close()

    def restore_snapshot(self, path):
        """.NET: snapshotConnection.BackupDatabase(live, "proj", "main") writes into the attached schema directly.
        Python's API always writes the destination's main schema, so a second connection opens the projection file."""
        src = sqlite3.connect(path)
        dst = sqlite3.connect(os.path.join(self.d, "lsax_proj.db"))
        src.backup(dst)
        dst.close()
        src.close()

    def fork_at(self, seq):
        self.db.execute("INSERT INTO main.timeline(parent_seq) VALUES(?)", (seq,))
        self.db.execute("UPDATE main.runtime_state SET v=(SELECT MAX(id) FROM main.timeline) WHERE k='active'")
        self.db.execute("DELETE FROM main.applied_idem")
        for t, s in self.path():
            (idem,) = self.db.execute("SELECT idem_key FROM main.commit_log WHERE timeline_id=? AND seq=?", (t, s)).fetchone()
            self.db.execute("INSERT INTO main.applied_idem VALUES(?)", (idem,))
        wm = self.watermark()
        if wm is None or tuple(wm) not in self.path():  # anchoring off the projection's path -> rebuild
            self.rebuild_from_scratch()


def ev(i):
    return [{"vid": f"v{i % 17}", "owner": f"SP{i % 3}", "odo": i * 1000}]


def tables(path):
    c = sqlite3.connect(path)
    r = sorted(n for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    c.close()
    return r


def run():
    s = Suite("P2-01 backup architecture")
    d = tempfile.mkdtemp(prefix="lsaxbak")
    st = Store(d)
    for i in range(1, 101):
        st.commit(f"k{i}", ev(i))

    # B1 snapshot of schema proj contains exactly the projection tables + watermark, no journal table
    snap = os.path.join(d, "snap100.db")
    st.snapshot(snap)
    s.check("B1 snapshot contains only projection tables", tables(snap) == ["projection_meta", "vehicle"], tables(snap))
    c = sqlite3.connect(snap)
    wm = json.loads(c.execute("SELECT v FROM projection_meta WHERE k='watermark'").fetchone()[0])
    c.close()
    s.check("B1 snapshot carries its watermark", wm == [1, 100], wm)

    # B2 full journal backup contains the journal tables and no projection table
    jb = os.path.join(d, "journal_backup.db")
    st.journal_backup(jb)
    s.check("B2 journal backup contains journal tables only",
            tables(jb) == ["applied_idem", "commit_log", "journal_event", "runtime_state", "timeline"], tables(jb))

    # B3 crash between the journal commit and the projection commit -> projection lags, never leads; catch-up fixes it
    for i in range(101, 121):
        st.commit(f"k{i}", ev(i), crash_between=(i == 120))
    st.db.close()
    st = Store(d)
    s.check("B3 after the crash the watermark lags the journal head (never leads)", st.watermark() == [1, 119])
    st.catch_up()
    live = st.proj_rows()
    st.rebuild_from_scratch()
    s.check("B3 catch-up result == full rebuild from the journal", st.proj_rows() == live)

    # B4 projection file lost -> rebuilt from the journal
    st.db.close()
    os.remove(os.path.join(d, "lsax_proj.db"))
    for suffix in ("-wal", "-shm"):
        if os.path.exists(os.path.join(d, "lsax_proj.db" + suffix)):
            os.remove(os.path.join(d, "lsax_proj.db" + suffix))
    st = Store(d)
    st.catch_up()
    s.check("B4 deleted projection DB rebuilt identically from the journal", st.proj_rows() == live)

    # B5 anchoring to an earlier state: restore snapshot (watermark 100 is an ancestor) + replay to the target
    st.fork_at(110)
    for i in range(200, 205):
        st.commit(f"b{i}", ev(i))
    target = st.proj_rows()
    st.restore_snapshot(snap)
    wm = st.watermark()
    ok_anc = tuple(wm) in st.path()
    st.catch_up()
    via_snapshot = st.proj_rows()
    st.rebuild_from_scratch()
    s.check("B5 snapshot on the target path is usable (watermark is an ancestor)", ok_anc)
    s.check("B5 snapshot restore + replay == rebuild from scratch == live", via_snapshot == st.proj_rows() == target)

    # B6 a snapshot NOT on the target path is rejected
    st.fork_at(80)
    s.check("B6 snapshot whose watermark is not an ancestor of the target is rejected", tuple(wm) not in st.path())

    # B7 online backup interleaved with writes on the same connection: snapshot is self-consistent
    d2 = tempfile.mkdtemp(prefix="lsaxbak2")
    st2 = Store(d2)
    for i in range(1, 60):
        st2.commit(f"k{i}", ev(i))
    snap2 = os.path.join(d2, "snap.db")
    dst = sqlite3.connect(snap2)
    st2.db.backup(dst, name="proj", pages=1, progress=lambda status, rem, tot: st2.commit(f"x{rem}-{tot}", ev(rem + 500)))
    dst.close()
    c = sqlite3.connect(snap2)
    wm2 = tuple(json.loads(c.execute("SELECT v FROM projection_meta WHERE k='watermark'").fetchone()[0]))
    rows_snap = c.execute("SELECT vehicle_id, owner, odo FROM vehicle ORDER BY vehicle_id").fetchall()
    c.close()
    d3 = tempfile.mkdtemp(prefix="lsaxbak3")
    ref = Store(d3)
    for t, sq in st2.path():
        (idem,) = st2.db.execute("SELECT idem_key FROM main.commit_log WHERE timeline_id=? AND seq=?", (t, sq)).fetchone()
        evs = [json.loads(p) for (p,) in st2.db.execute("SELECT payload FROM main.journal_event WHERE timeline_id=? AND seq=? ORDER BY ord", (t, sq))]
        ref.commit(idem, evs)
        if (t, sq) == wm2:
            break
    s.check("B7 snapshot taken during concurrent writes equals the projection at its own watermark",
            rows_snap == ref.proj_rows(), (wm2, len(rows_snap)))

    # B8 durability configuration
    s.check("B8 journal synchronous=FULL, projection synchronous=NORMAL",
            st.db.execute("PRAGMA main.synchronous").fetchone()[0] == 2 and st.db.execute("PRAGMA proj.synchronous").fetchone()[0] == 1)
    return s


def main():
    return run().report()


if __name__ == "__main__":
    sys.exit(main())
