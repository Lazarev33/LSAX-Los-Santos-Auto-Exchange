"""P0-02 regression — wallet equality is never causal proof of a PREPARED transaction (decisions D-TX-4, D-TX-5).

Exhaustive deterministic matrix over
  direction      BUY, SELL
  wallet         protagonist wallet slot 0, 1, 2 (other two wallets perturbed by an unrelated mod)
  crash point    C1 (after PREPARE, before apply), CA (APPLYING marked, before native write),
                 CB (after native write, before APPLIED recorded), C2 (APPLIED recorded, before COMMIT)
  stop mode      RELOAD_CLEAN (console reload / script exception, Aborted flush, same session)
                 UNCLEAN_SAME_SESSION (no Aborted flush, same session)
                 DOWNTIME_TRAINER_RELOAD (clean stop, 30 s of play with trainer/other-mod cash writes, console reload)
                 SWITCH_WHILE_DOWN_RELOAD (clean stop, protagonist switched while LSAX is down -> session token lost)
                 GAME_CRASH_LOAD (process dies, the pre-transaction LSAX-observed save is loaded in a new process)
  external cash  NONE, TO_BEFORE (lands exactly on wallet_before), TO_AFTER (lands exactly on wallet_after)
                 applied during the downtime (for GAME_CRASH_LOAD also after the load, before LSAX's first tick)

Checks per scenario
  S1 safety        RECONCILE_REQUIRED, or LSAX active path == transactions present in the world and projection == garage
  S2 no fabrication  the transaction is on LSAX's active path only if its effects are present in the world
  S3 own evidence  a roll-forward happens exactly when LSAX's own flushed status is APPLIED and the session token proves
                   the same live session (crash C2 with a clean stop, same session); never otherwise
  S4 wallet-independent  the commit/abort/refuse decision is identical for NONE / TO_BEFORE / TO_AFTER
  S5 repeated restart  three further restarts change neither the decision nor the projection; RECONCILE persists
  S6 replay        committed -> the same idempotency key is DUPLICATE; aborted -> a retry is a fresh attempt;
                   RECONCILE -> every market operation is refused
"""
import itertools
import sys

from regress_common import Suite, tmpdb
from journal_timeline_ref import Crash, Gta, Lsax

KINDS = ("BUY", "SELL")
WALLETS = (0, 1, 2)
CRASHES = ("C1", "CA", "CB", "C2")
STOPS = ("RELOAD_CLEAN", "UNCLEAN_SAME_SESSION", "DOWNTIME_TRAINER_RELOAD", "SWITCH_WHILE_DOWN_RELOAD", "GAME_CRASH_LOAD")
EXTS = ("NONE", "TO_BEFORE", "TO_AFTER")


def scenario(kind, w, crash, stop, ext, ext_after_load=False):
    path, g, st = tmpdb("p002"), Gta(1), {}
    g.advance(3_600_000)                         # mid-campaign
    lx = Lsax(path, g, st)
    g.switch_char(w)
    g.advance(1000)
    lx.tick()                                    # re-tags the new player ped
    if kind == "SELL":
        assert lx.submit("BUY", "v0", 30_000, "k0", "t0") == "COMMITTED"
        g.advance(1000)
        lx.tick()
    g.save(0)                                    # an LSAX-observed save before the transaction
    g.advance(300)
    lx.poll_slots()
    g.advance(2000)
    lx.tick()
    vid = "v1" if kind == "BUY" else "v0"
    try:
        lx.submit(kind, vid, 20_000, "k1", "t1", crash_at=crash)
        raise AssertionError("crash point not reached")
    except Crash:
        pass
    before, after = lx.db.execute("SELECT cash_before, cash_after FROM txn WHERE txn_id='t1'").fetchone()

    def external():
        others = [x for x in range(3) if x != w]
        g.wallets[others[0]] += 12_345           # unrelated mod activity on the other wallets
        g.wallets[others[1]] = max(0, g.wallets[others[1]] - 777)
        if ext == "TO_BEFORE":
            g.wallets[w] = before
        elif ext == "TO_AFTER":
            g.wallets[w] = after

    if stop == "RELOAD_CLEAN":
        lx.close(clean=True)
        external()
    elif stop == "UNCLEAN_SAME_SESSION":
        lx.close(clean=False)
        external()
    elif stop == "DOWNTIME_TRAINER_RELOAD":
        lx.close(clean=True)
        g.advance(30_000)
        external()
        g.advance(30_000)
    elif stop == "SWITCH_WHILE_DOWN_RELOAD":
        lx.close(clean=True)
        g.advance(10_000)
        g.switch_char((w + 1) % 3)
        external()
    elif stop == "GAME_CRASH_LOAD":
        lx.close(clean=False)
        if not ext_after_load:
            external()
        g.process_crash()
        g.load(0)
        if ext_after_load:
            external()
    lx = Lsax(path, g, st)
    return path, g, st, lx


def decision(lx):
    if lx.rt("reconcile"):
        return "RECONCILE:" + lx.rt("reconcile_reason")
    return "COMMITTED" if "t1" in lx.active_ids() else "ABORTED"


def run():
    s = Suite("P0-02 transaction recovery")
    counts = {}
    decisions = {}
    for kind, w, crash, stop, ext in itertools.product(KINDS, WALLETS, CRASHES, STOPS, EXTS):
        for eal in ((False, True) if stop == "GAME_CRASH_LOAD" else (False,)):
            name = f"{kind} w{w} {crash} {stop} ext={ext}{' after-load' if eal else ''}"
            path, g, st, lx = scenario(kind, w, crash, stop, ext, eal)
            d = decision(lx)
            counts[d] = counts.get(d, 0) + 1
            decisions.setdefault((kind, w, crash, stop, eal), set()).add(d)
            in_world = "t1" in g.applied
            safe = lx.rt("reconcile") or (lx.active_ids() == g.applied and lx.projection() == g.garage)
            s.check(f"S1 safety  {name}", safe, f"{d} lsax={lx.active_ids()} world={g.applied}")
            s.check(f"S2 no fabrication  {name}", ("t1" not in lx.active_ids()) or in_world, d)
            rolled = st.get("roll_forward_on_own_evidence", 0) > 0
            expect_roll = crash == "C2" and stop in ("RELOAD_CLEAN", "DOWNTIME_TRAINER_RELOAD")
            s.check(f"S3 own-evidence roll-forward only  {name}", rolled == expect_roll, f"rolled={rolled}")
            proj = sorted(lx.projection())
            for k in range(3):                   # S5 repeated restart
                lx.close(clean=True)
                g.advance(500)
                lx = Lsax(path, g, st)
                lx.tick()
            s.check(f"S5 repeated restart stable  {name}", decision(lx) == d and sorted(lx.projection()) == proj,
                    f"{d} -> {decision(lx)}")
            if d.startswith("RECONCILE"):
                s.check(f"S6 refuse during RECONCILE  {name}",
                        lx.submit("BUY", "vz", 1, "kz", "tz") == "REFUSED_RECONCILE")
            elif d == "COMMITTED":
                s.check(f"S6 replay idempotent  {name}", lx.submit(kind, vid_of(kind), 20_000, "k1", "t1b") == "DUPLICATE")
            else:
                s.check(f"S6 retry after abort is a fresh attempt  {name}",
                        "k1" not in [r[3] for r in lx.commits(lx.rt("active"))])
            lx.close(clean=True)
    for key, ds in sorted(decisions.items()):
        s.check(f"S4 decision independent of wallet value  {key}", len(ds) == 1, str(sorted(ds)))
    print("decision distribution:", dict(sorted(counts.items())))
    return s


def vid_of(kind):
    return "v1" if kind == "BUY" else "v0"


def main():
    return run().report(verbose=False)


if __name__ == "__main__":
    sys.exit(main())
