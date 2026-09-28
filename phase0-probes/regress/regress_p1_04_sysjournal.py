"""P1-04 regression — system transaction / journal protocol (decision D-JRN-1; model phase0-probes/sim/sysjournal_ref.py).

For EACH system family (MT checkpoint, odometer checkpoint, market step, heat decay, heat event, listing expiry):
  F1 crash before commit -> nothing durable; retry with the same key commits exactly once
  F2 crash after commit (acknowledgement lost) -> reopen, retry -> DUPLICATE; exactly one commit on the path
  F3 projection rebuilt by replaying the journal == live projection
  F4 replaying the path twice == replaying once (absolute payloads)
  F5 rewind + branch: the same logical event on the new branch is regenerated deterministically with the same key and
     identical payload, commits once on the new path, and the old branch keeps its own single copy
  F6 ordering: never committed while a business transaction is PREPARED (deferred, then committed)
  F7 coalescing: allowed only for MT/ODO checkpoints (newest absolute value wins); rejected for every other family
Plus: a path never repeats a market-step index; journal_event rows always reference a txn and a commit_log row.
"""
import sys

from regress_common import Suite
from sysjournal_ref import (COALESCIBLE, CrashBeforeCommit, Journal, LostAck, heat_decay, heat_event, listing_expiry,
                            market_step, mt_checkpoint, new_journal, odo_checkpoint)


def builders(j):
    """(family, builder(j) -> (kind, idem, events)) — builders read the current path state (deterministic)."""
    return [
        ("SYS_MT_CHECKPOINT", lambda jj: mt_checkpoint(777, 3, [1234, 1200, [[100, 34]]])),
        ("SYS_ODO_CHECKPOINT", lambda jj: odo_checkpoint("veh-A", 777, 9, 152_340)),
        ("SYS_MARKET_STEP", lambda jj: market_step(jj, 7)),
        ("SYS_HEAT_DECAY", lambda jj: heat_decay(jj, 40)),
        ("SYS_HEAT_EVENT", lambda jj: heat_event(jj, "THEFT", "veh-B", 5_000, 120)),
        ("SYS_LISTING_EXPIRY", lambda jj: listing_expiry("npc-3-0", 2)),
    ]


def path_count(j, idem):
    return sum(1 for r in j.path() if r[3] == idem)


def integrity(j):
    orphans = j.db.execute("SELECT COUNT(*) FROM journal_event e LEFT JOIN txn t ON t.txn_id=e.txn_id "
                           "LEFT JOIN commit_log c ON c.txn_id=e.txn_id WHERE t.txn_id IS NULL OR c.txn_id IS NULL").fetchone()[0]
    return orphans == 0


def base_state(j):
    for step in range(3):
        j.commit(*market_step(j, step))
    j.commit(*heat_decay(j, 1))
    j.commit("BUSINESS", "LEGAL_BUY|SP0|lst:1|v1", [("Business", {"id": "t1", "value": 1})])


def run():
    s = Suite("P1-04 system journal protocol")
    for fam, build in builders(None):
        # F1 crash before commit
        j = new_journal(); base_state(j)
        kind, idem, ev = build(j)
        try:
            j.commit(kind, idem, ev, crash="BEFORE_COMMIT")
            s.check(f"{fam} F1 crash injected", False)
        except CrashBeforeCommit:
            pass
        s.check(f"{fam} F1 nothing durable after crash before commit", path_count(j, idem) == 0)
        s.check(f"{fam} F1 retry commits exactly once", j.commit(kind, idem, ev) == "COMMITTED" and path_count(j, idem) == 1)

        # F2 crash after commit (lost acknowledgement), reopen, retry
        j = new_journal(); base_state(j)
        kind, idem, ev = build(j)
        try:
            j.commit(kind, idem, ev, crash="LOST_ACK")
        except LostAck:
            pass
        j2 = Journal(j.dbpath)
        s.check(f"{fam} F2 retry after lost ack is DUPLICATE, one commit on the path",
                j2.commit(kind, idem, ev) == "DUPLICATE" and path_count(j2, idem) == 1)

        # F3 rebuild == live; F4 replay twice == once
        live = j2.projection()
        j2.rebuild()
        s.check(f"{fam} F3 rebuild from journal == live projection", j2.projection() == live)
        j2.rebuild()
        s.check(f"{fam} F4 replay idempotent (absolute payloads)", j2.projection() == live)
        s.check(f"{fam} integrity: every journal_event has txn + commit_log", integrity(j2))

        # F5 rewind + branch replay
        j = new_journal(); base_state(j)
        h = j.head()
        kind, idem, ev = build(j)
        j.commit(kind, idem, ev)
        old_tl = j.active()
        j.fork(h)                                            # anchored to the state before the event
        kind2, idem2, ev2 = build(j)
        same = (kind2, idem2, ev2) == (kind, idem, ev)
        s.check(f"{fam} F5 branch regenerates the identical event (key + payload)", same, (idem, idem2))
        s.check(f"{fam} F5 commits once on the new branch", j.commit(kind2, idem2, ev2) == "COMMITTED" and path_count(j, idem2) == 1)
        s.check(f"{fam} F5 old branch keeps exactly one copy", sum(1 for r in j.path(old_tl) if r[3] == idem) == 1)

        # F6 ordering gate
        j = new_journal(); base_state(j)
        kind, idem, ev = build(j)
        j.pending_business = True
        r1 = j.commit(kind, idem, ev)
        j.pending_business = False
        r2 = j.commit(kind, idem, ev)
        s.check(f"{fam} F6 deferred while a business txn is PREPARED, then committed", (r1, r2) == ("DEFERRED_BUSINESS_PREPARED", "COMMITTED"))

        # F7 coalescing
        j = new_journal()
        kind, idem, ev = build(j)
        try:
            j.enqueue(kind, idem, ev, coalesce_key="k")
            j.enqueue(kind, idem + "-newer", ev, coalesce_key="k")
            coalesced = len(j.queue) == 1 and j.queue[0][1].endswith("-newer")
        except ValueError:
            coalesced = False
        s.check(f"{fam} F7 coalescing {'allowed (newest wins)' if fam in COALESCIBLE else 'rejected'}",
                coalesced == (fam in COALESCIBLE))

    # market-step index never repeats on a path, across rewinds and catch-up
    j = new_journal()
    for step in range(6):
        j.commit(*market_step(j, step))
    ids = [r for r in j.path() if r[4] == "SYS_MARKET_STEP"]
    h3 = ids[2][2]
    j.fork(h3)                                               # rewind to after step 2
    results = [j.commit(*market_step(j, step)) for step in range(0, 6)]     # catch-up re-issues 0..5
    keys = [r[3] for r in j.path() if r[4] == "SYS_MARKET_STEP"]
    s.check("market steps: catch-up after rewind re-issues only missing steps (0..2 DUPLICATE, 3..5 COMMITTED)",
            results == ["DUPLICATE"] * 3 + ["COMMITTED"] * 3, results)
    s.check("market steps: a path never repeats a step index", len(keys) == len(set(keys)) == 6)
    return s


def main():
    return run().report(verbose=False)


if __name__ == "__main__":
    sys.exit(main())
