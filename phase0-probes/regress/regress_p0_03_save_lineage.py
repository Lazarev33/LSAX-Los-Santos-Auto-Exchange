"""P0-03 regression — save files changed while LSAX is not observing them are UNTRUSTED; positive lineage or
RECONCILE_REQUIRED (decisions D-SL-13 content lineage, D-SL-14 session token, D-SL-15 hypothesis exclusion,
D-SL-16 LIVE / MISSED_START / NEW_GAME hypotheses).

Every case states the expected outcome. "anchor" cases prove liveness (a legitimate situation is accepted with the
correct lineage); "refuse" cases prove safety (RECONCILE_REQUIRED, projection untouched, market refused).
The last case documents the residual outside threat model TM-1 (deliberate file swap violating A-SL-8); it must
reproduce exactly so the documented residual stays accurate, and it is reported separately, not as a safety PASS.
"""
import sys

from regress_common import Suite, tmpdb
from journal_timeline_ref import Gta, Lsax, EMPTY, NEWGAME_P_MAX


class World:
    """Scripted scenario helper around the reference model."""

    def __init__(self, preinstall=0, G=1, P0=7_200_000):
        self.path, self.g, self.st = tmpdb("p003"), Gta(G), {}
        self.g.advance(P0)
        for k in range(preinstall):
            self.g.advance(60_000)
            self.g.save(10 + k)
        self.g.save_events.clear()
        self.g.advance(60_000)
        self.lx = Lsax(self.path, self.g, self.st)
        self.n = 0
        self.snap = {}

    def play(self, ms=2000):
        self.g.advance(ms)
        self.lx.tick()

    def buy(self, price=20_000):
        self.n += 1
        self.play()
        r = self.lx.submit("BUY", f"v{self.n}", price, f"k{self.n}", f"t{self.n}")
        assert r == "COMMITTED", r
        return f"t{self.n}"

    def sell(self, vid, price=10_000):
        self.n += 1
        self.play()
        r = self.lx.submit("SELL", vid, price, f"k{self.n}", f"t{self.n}")
        assert r == "COMMITTED", r
        return f"t{self.n}"

    def save(self, slot, name=None):
        self.play(1500)
        self.g.save(slot)
        self.snap[name or slot] = dict(self.g.slots[slot])
        self.g.advance(300)
        self.lx.poll_slots()

    def stop(self, clean=True):
        self.lx.close(clean=clean)

    def start(self):
        self.lx = Lsax(self.path, self.g, self.st)
        return self.lx

    def reload_load(self, slot):
        """Normal in-game load while LSAX runs: new session, old instance's Aborted, new instance anchors."""
        self.play()
        self.g.load(slot)
        self.stop(clean=True)
        return self.start()

    def outcome(self):
        lx = self.lx
        if lx.rt("reconcile"):
            return "RECONCILE:" + lx.rt("reconcile_reason")
        return "ANCHORED"

    def consistent(self):
        return self.lx.active_ids() == self.g.applied and self.lx.projection() == self.g.garage


def expect_refuse(s, name, w, reason=None):
    oc = w.outcome()
    ok = oc.startswith("RECONCILE") and (reason is None or oc == "RECONCILE:" + reason)
    s.check(f"{name}: RECONCILE_REQUIRED{'(' + reason + ')' if reason else ''}", ok, oc)
    s.check(f"{name}: market refused while RECONCILE", w.lx.submit("BUY", "vq", 1, "kq", "tq") == "REFUSED_RECONCILE")
    proj = sorted(w.lx.projection())
    w.stop()
    w.g.advance(500)
    w.start()
    s.check(f"{name}: RECONCILE persists across restart, projection untouched",
            w.outcome() == oc and sorted(w.lx.projection()) == proj, w.outcome())


def expect_anchor(s, name, w):
    oc = w.outcome()
    s.check(f"{name}: anchored automatically", oc == "ANCHORED", oc)
    s.check(f"{name}: LSAX state == world", w.consistent(), f"lsax={w.lx.active_ids()} world={w.g.applied}")


def run():
    s = Suite("P0-03 save lineage")

    # 1 foreign save copied during downtime into an empty slot, then loaded (new process)
    w = World()
    w.buy(); w.save(0); w.buy(); w.save(1); w.stop()
    w.g.advance(120_000)
    w.g.copy_foreign(2, w.g.stat_p() - 30_000, (200_000, 150_000, 100_000))
    w.g.process_crash(); w.g.load(2); w.start()
    expect_refuse(s, "01 foreign copy during downtime, loaded", w, "UNTRUSTED_PRESENT")

    # 2 foreign save copied during downtime, NOT loaded: the loaded world is a trusted save, but the foreign file
    #   cannot be excluded (content unknown) -> refuse. Safety over convenience (R-SL-3).
    w = World()
    w.buy(); w.save(0); w.stop()
    w.g.copy_foreign(3, w.g.stat_p() + 5000, (1, 2, 3))
    w.g.process_crash(); w.g.load(0); w.start()
    expect_refuse(s, "02 foreign copy present, trusted save loaded", w, "UNTRUSTED_PRESENT")

    # 3 copied older local save = byte-identical restore of an LSAX-observed save (rollback to an observed save)
    w = World()
    t1 = w.buy(); w.save(0, "s0_t1"); w.buy(); w.save(0, "s0_t2"); w.stop()
    w.g.restore_copy(0, w.snap["s0_t1"])
    w.g.process_crash(); w.g.load(0); w.start()
    expect_anchor(s, "03 byte-identical restore of an older observed save", w)
    s.check("03 anchored at the observed head", w.lx.head() == t1, w.lx.head())

    # 4 copied newer save (made by another install / unseen by LSAX) -> refuse
    w = World()
    w.buy(); w.save(0); w.stop()
    w.g.copy_foreign(0, w.g.stat_p() + 3_600_000, (900_000, 150_000, 100_000), garage=("vX",), applied=("tX",))
    w.g.process_crash(); w.g.load(0); w.start()
    expect_refuse(s, "04 copied newer foreign save loaded", w, "UNTRUSTED_PRESENT")

    # 5 newer save written by the game while LSAX was down (own play, unobserved) -> refuse
    w = World()
    w.buy(); w.save(0); w.stop()
    w.g.advance(60_000); w.g.cash += 5000; w.g.save(1)
    w.g.process_crash(); w.g.load(1); w.start()
    expect_refuse(s, "05 save written while LSAX was down, loaded", w, "UNTRUSTED_PRESENT")

    # 6 same play-time collision: foreign file with the trusted file's exact play-time, different wallets
    w = World()
    w.buy(); w.save(0); w.stop()
    P0 = w.snap[0]["P"]
    w.g.copy_foreign(1, P0, (1_000, 150_000, 100_000))
    w.g.process_crash(); w.g.load(1); w.start()
    expect_refuse(s, "06 same play-time collision (foreign loaded)", w, "UNTRUSTED_PRESENT")

    # 7 same wallet collision: foreign file with the trusted file's exact wallets, different play-time
    w = World()
    w.buy(); w.save(0); w.stop()
    w.g.copy_foreign(1, w.snap[0]["P"] + 777_000, w.snap[0]["wallets"])
    w.g.process_crash(); w.g.load(1); w.start()
    expect_refuse(s, "07 same wallet collision (foreign loaded)", w, "UNTRUSTED_PRESENT")

    # 8 full fingerprint forgery (play-time AND wallets equal a trusted file), foreign file loaded and still present
    w = World()
    w.buy(); w.save(0); w.stop()
    w.g.copy_foreign(1, w.snap[0]["P"], w.snap[0]["wallets"])
    w.g.process_crash(); w.g.load(1); w.start()
    expect_refuse(s, "08 forged fingerprint (P and W equal), present", w, "UNTRUSTED_PRESENT")

    # 9 multiple slots, all trusted, each loaded in turn in a new process -> each anchors at its own head
    w = World()
    heads = {}
    heads[0] = w.buy(); w.save(0)
    heads[1] = w.buy(); w.save(1)
    w.sell("v1"); heads[2] = w.lx.head(); w.save(2)
    heads[3] = w.buy(); w.save(3)
    ok = True
    for slot in (2, 0, 3, 1):
        w.stop(); w.g.process_crash(); w.g.load(slot); w.start()
        ok &= w.outcome() == "ANCHORED" and w.consistent() and w.lx.head() == heads[slot]
    s.check("09 multiple trusted slots: each load anchors at its own observed head", ok)

    # 10a two game saves within the event-correlation window between two polls (autosave + manual save):
    #     the event cannot be attributed to one file -> both UNTRUSTED (conservative)
    w = World()
    w.buy(); w.play()
    w.g.save(0); w.g.advance(500); w.g.save(1); w.g.advance(100); w.lx.poll_slots()
    sts = [w.lx.db.execute("SELECT status, reason FROM slot_state WHERE slot=?", (k,)).fetchone() for k in (0, 1)]
    s.check("10a two saves inside one correlation window -> both UNTRUSTED(AMBIGUOUS_EVENT)",
            sts == [("UNTRUSTED", "AMBIGUOUS_EVENT")] * 2, sts)
    # 10b two TRUSTED saves on different branches with identical fingerprints (same play-time bracket, same wallets:
    #     same price paid for different vehicles from the same base save) but different LSAX heads -> AMBIGUOUS
    w = World()
    w.buy(); w.save(2)
    w.reload_load(2); tA = w.buy(); w.save(0)
    w.reload_load(2); tB = w.buy(); w.save(1)
    rows = w.lx.db.execute("SELECT head_txn, p_lo, p_hi, w0, w1, w2 FROM save_ledger WHERE head_txn IN (?,?) ORDER BY head_txn",
                           (tA, tB)).fetchall()
    s.check("10b precondition: identical fingerprints, different heads",
            len(rows) == 2 and rows[0][1:] == rows[1][1:] and rows[0][0] != rows[1][0], rows)
    w.stop(); w.g.process_crash(); w.g.load(0); w.start()
    expect_refuse(s, "10b cross-branch trusted saves with identical fingerprints", w, "AMBIGUOUS")
    cands = w.lx.rt("reconcile_candidates")
    s.check("10b both branch heads listed for the explicit choice", f"H:{tA}" in cands and f"H:{tB}" in cands, cands)

    # 11 repeated restart after correct anchoring: continuation, state unchanged
    w = World()
    w.buy(); w.save(0); w.buy()
    ids = w.lx.active_ids()
    ok = True
    for _ in range(5):
        w.stop(clean=True); w.g.advance(500); w.start(); w.lx.tick()
        ok &= w.outcome() == "ANCHORED" and w.lx.active_ids() == ids and w.consistent()
    s.check("11 repeated script reloads: continuation, state unchanged", ok and w.st.get("anchored_continuation", 0) >= 5)

    # 12 legitimate continuation with protagonist switch while LSAX runs (tick re-tags the new player ped)
    w = World()
    w.buy(); w.g.switch_char(2); w.play(); w.buy(); w.stop(clean=False); w.start()
    expect_anchor(s, "12 switch while running, then unclean reload", w)
    s.check("12 continuation proven by session token", w.st.get("anchored_continuation", 0) == 1)

    # 13 rollback to an actual LSAX-observed save (normal in-game load of an older save, same process)
    w = World()
    t1 = w.buy(); w.save(0); w.buy(); w.buy()
    w.reload_load(0)
    expect_anchor(s, "13 in-game load of an older observed save", w)
    s.check("13 anchored at the save's head, later purchases not in the world", w.lx.head() == t1)
    # ... and forward again in a NEW process (game restarted, latest save loaded)
    w2 = World()
    w2.buy(); w2.save(0); tb = w2.buy(); w2.save(1)
    w2.reload_load(0); w2.buy(); w2.stop(); w2.g.process_crash(); w2.g.load(1); w2.start()
    expect_anchor(s, "13b forward load of a later observed save in a new process", w2)
    s.check("13b anchored at the later save's head", w2.lx.head() == tb)

    # 14 forward load across branches in the SAME process: LIVE cannot be excluded -> refuse (documented cost)
    w = World()
    w.buy(); w.save(0); w.buy(); w.play(600_000); w.save(1)   # slot 1 is 10 min of play-time ahead of slot 0
    w.reload_load(0); w.play(); w.play()
    w.reload_load(1)
    expect_refuse(s, "14 forward cross-branch load in the same process", w, "AMBIGUOUS")
    w = World()
    w.buy(); w.save(0); w.buy(); w.save(1)                    # slot 1 only seconds ahead of slot 0
    w.reload_load(0); w.play(); w.play()
    w.reload_load(1)
    expect_anchor(s, "14b load of a save older than LSAX's last live observation (LIVE excluded by play-time)", w)

    # 15 token lost without any load (switch while LSAX down, console reload) -> not continuation
    w = World()
    w.buy(); w.save(0); w.buy(); w.stop()
    w.g.advance(8000); w.g.switch_char(1); w.start()
    expect_refuse(s, "15 switch while LSAX down + console reload", w, "SESSION_UNPROVEN")

    # 16 missed script-domain start: load while LSAX could not start, later console reload in that session
    from journal_timeline_ref import mark_missed_start
    w = World()
    w.buy(); w.save(0); w.buy(); w.save(1); w.stop()
    w.g.load(0); mark_missed_start(w.path, w.g)
    w.g.advance(4000); w.start()
    expect_refuse(s, "16 missed start then console reload", w, "MISSED_START")

    # 17 pre-install saves: EMPTY state known, fingerprint unknown
    w = World(preinstall=2)
    w.save(0)
    w.reload_load(0)
    expect_anchor(s, "17a pre-install saves present, no LSAX commits yet: states agree (EMPTY)", w)
    w.buy(); w.save(1); w.reload_load(1)
    expect_refuse(s, "17b pre-install saves present after LSAX commits", w, "AMBIGUOUS")
    w = World(preinstall=1)
    w.stop(); w.g.process_crash(); w.g.load(10); w.start()
    s.check("17c loading a pre-install save with no trusted match: explicit choice only",
            w.outcome() in ("ANCHORED", "RECONCILE:AMBIGUOUS", "RECONCILE:NO_MATCH") and
            (w.outcome() != "ANCHORED" or (w.lx.head() is None and w.consistent())), w.outcome())

    # 18 new game with trusted saves present
    w = World()
    w.buy(); w.save(0); w.play(); w.g.new_game(); w.stop(); w.start()
    expect_refuse(s, "18 new game", w, "NO_MATCH")
    cands = w.lx.rt("reconcile_candidates")
    s.check("18 new game: EMPTY offered as an explicit candidate", ("H:" + EMPTY) in cands, cands)

    # 19 save immediately followed by another mod's payout before LSAX's poll: wallets unknown, play-time still excludes
    w = World()
    t1 = w.buy(); w.play(1500); w.g.save(0); w.g.cash += 4321; w.g.advance(200); w.lx.poll_slots()
    row = w.lx.db.execute("SELECT w0 FROM save_ledger WHERE kind='OBSERVED'").fetchone()
    s.check("19 wallets recorded as unknown when they changed inside the bracket", row[0] is None, row)
    w.buy(); w.stop(); w.g.process_crash(); w.g.load(0); w.start()
    expect_anchor(s, "19 load of that save still anchors via content lineage + play-time", w)
    s.check("19 anchored at the save's head", w.lx.head() == t1)

    # 20 file copied while LSAX runs (no save event) -> UNTRUSTED immediately
    w = World()
    w.buy(); w.save(0); w.play()
    w.g.copy_foreign(1, w.g.stat_p(), tuple(w.g.wallets)); w.play()
    st1 = w.lx.db.execute("SELECT status, reason FROM slot_state WHERE slot=1").fetchone()
    s.check("20 copy while running without save event -> UNTRUSTED", st1 == ("UNTRUSTED", "FOREIGN_WHILE_RUNNING"), st1)

    # 21 crash with a pending APPLIED transaction, game crash, most recent (pre-transaction) save loaded
    from journal_timeline_ref import Crash
    w = World()
    w.buy(); w.save(0); w.play()
    try:
        w.lx.submit("BUY", "vP", 10_000, "kP", "tP", crash_at="C2")
    except Crash:
        pass
    w.stop(clean=True); w.g.process_crash(); w.g.load(0); w.start()
    expect_anchor(s, "21 pending APPLIED + game crash + pre-transaction save loaded", w)
    s.check("21 pending transaction aborted (its effects are not in the loaded world)",
            "tP" not in w.lx.active_ids() and w.lx.q1("SELECT state FROM txn WHERE txn_id='tP'") == "ABORTED")

    # 22 explicit resolution: truthful player picks the listed candidate; LSAX never picks automatically
    from journal_timeline_ref import truthful_resolution
    w = World()
    w.buy(); w.save(0); w.buy(); w.play(600_000); w.save(1)
    w.reload_load(0); w.play(); w.reload_load(1)          # AMBIGUOUS (as case 14)
    s.check("22 precondition: RECONCILE_REQUIRED", w.outcome() == "RECONCILE:AMBIGUOUS", w.outcome())
    before = w.st.get("resolved_candidate", 0)
    truthful_resolution(w.lx, w.g)
    s.check("22 resolution by explicit player choice restores consistency",
            w.outcome() == "ANCHORED" and w.consistent() and w.st.get("resolved_candidate", 0) == before + 1)

    # 23 residual outside TM-1 (documented, not a safety PASS): the loaded foreign file is swapped back to trusted
    #    bytes before LSAX's startup scan (violates A-SL-8) AND reproduces the trusted fingerprint exactly.
    w = World()
    w.buy(); w.save(0, "orig"); w.buy(); w.stop()
    w.g.copy_foreign(0, w.snap["orig"]["P"], w.snap["orig"]["wallets"])
    w.g.process_crash(); w.g.load(0)
    w.g.restore_copy(0, w.snap["orig"])                    # file swapped back before LSAX starts
    w.start()
    residual = w.outcome() == "ANCHORED" and not w.consistent()
    print(f"RESIDUAL R-SL-7 (A-SL-8 violated by deliberate swap + forged fingerprint): reproduces={residual}")
    s.check("23 documented residual R-SL-7 reproduces exactly as documented (TM-1 boundary)", residual)
    return s


def main():
    return run().report()


if __name__ == "__main__":
    sys.exit(main())
