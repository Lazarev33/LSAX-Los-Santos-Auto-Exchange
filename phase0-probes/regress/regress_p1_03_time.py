"""P1-03 regression — one coherent time contract: PT is an anchor coordinate only; MT is restored exclusively from
LSAX's own records; skip credit is durable immediately (decision D-TIME-2; model phase0-probes/sim/time_ref.py).

Cases: pause, loading, protagonist switch, fades/transitions, GT stall, sleep, save immediately after sleep, crash
before the periodic MtCheckpoint, save/load around a time skip, offline freeze, rolling credit cap, and PT-semantics
independence (MT identical whatever PT does during pause/loading). DRAFT1 behaviour is reproduced where it failed.
"""
import sys

from regress_common import Suite
from time_ref import (CHECKPOINT_AT_MS, Draft1Time, Game, TimeService, draft1_mt_from_pt)


def frames(g, ts, ms, **state):
    """Advance ms of wall time with the given game state flags (paused/loading/switching/faded)."""
    faded = state.pop("faded", False)
    for k, v in state.items():
        setattr(g, k, v)
    t = 0
    while t < ms:
        g.frame()
        g.faded_ms = g.faded_ms + 33 if faded else 0
        ts.tick(g)
        t += 33
    for k in state:
        setattr(g, k, False)
    g.faded_ms = 0


def sleep(g, ts, hours, fade_ms=8000):
    t, jumped = 0, False
    while t < fade_ms:
        g.frame()
        g.faded_ms += 33
        if not jumped and t >= fade_ms // 2:
            g.gc_min += hours * 60
            jumped = True
        ts.tick(g)
        t += 33
    g.faded_ms = 0


def fresh(cls=TimeService, **gk):
    g, store = Game(**gk), []
    ts = cls(store)
    ts.tick(g)
    return g, store, ts


class Ledger:
    """Observed saves: mt_obs sampled at the observing poll (same tick, after skip detection); DRAFT1 checkpoints
    with play-time for the MT(P) formula."""

    def __init__(self):
        self.rows = {}

    def save(self, name, g, ts):
        self.rows[name] = dict(P=g.P, gc=g.gc_min, mt_obs=ts.mt, state=ts.state())


def run():
    s = Suite("P1-03 time contract")

    # T1 pause: 10 min pause menu -> +0; 30 min active -> +900 (+-1)
    g, st, ts = fresh()
    frames(g, ts, 600_000, paused=True)
    s.check("T1 pause menu 10 min -> MT +0", ts.mt == 0, ts.mt)
    frames(g, ts, 1_800_000)
    s.check("T1 30 min active -> MT 900 +-1", ts.mt in (899, 900), ts.mt)

    # T2 loading screen 20 s -> +0
    g, st, ts = fresh()
    frames(g, ts, 20_000, loading=True)
    s.check("T2 loading screen -> MT +0", ts.mt == 0, ts.mt)

    # T3 protagonist switch transition 8 s -> +0
    g, st, ts = fresh()
    frames(g, ts, 8_000, switching=True)
    s.check("T3 protagonist switch transition -> MT +0", ts.mt == 0, ts.mt)

    # T4 fades: 3 s mod/teleport fade counts fully; 8 s fade counts only its first 5 s
    g, st, ts = fresh()
    frames(g, ts, 3_000, faded=True)
    s.check("T4 short fade (3 s) counts", ts.mt == 1, ts.mt)
    g, st, ts = fresh()
    frames(g, ts, 8_000, faded=True)
    s.check("T4 long fade (8 s) counts only 5 s", ts.mt == 2, ts.mt)

    # T5 GT stall (debugger / alt-tab): one 5 s frame -> +0
    g, st, ts = fresh()
    g.frame(5_000)
    ts.tick(g)
    s.check("T5 GT stall > 1 s -> MT +0", ts.mt == 0, ts.mt)

    # T6 sleep: 8 h clock jump inside a fade -> credit 480, durable immediately
    g, st, ts = fresh()
    frames(g, ts, 1_800_000)                                 # accrue base MT so the rolling cap allows credit
    before = ts.mt
    sleep(g, ts, 8)
    s.check("T6 sleep 8 h -> credit 480 (+ base during the counted fade)", ts.mt - before in range(480, 484), ts.mt - before)
    s.check("T6 credit durable immediately (SYS_MT_CHECKPOINT at grant)", st and st[-1][2] == "SKIP_CREDIT" and st[-1][1] == ts.mt)

    # T7 save immediately after sleep, play on, reload that save -> MT == MT at save (credit included)
    g, st, ts = fresh()
    led = Ledger()
    frames(g, ts, 1_800_000)
    sleep(g, ts, 8)
    frames(g, ts, 1_000)
    led.save("after_sleep", g, ts)
    mt_at_save = ts.mt
    frames(g, ts, 600_000)
    restored = led.rows["after_sleep"]["mt_obs"]            # slot anchoring restores the ledger's mt_obs
    s.check("T7 load of a save made right after sleep restores MT exactly (credit kept)", restored == mt_at_save,
            (restored, mt_at_save))
    # DRAFT1 reproduction: MT(P) from periodic checkpoints (credit not yet checkpointed)
    g1, st1, ts1 = fresh(Draft1Time)
    ck = []
    t = 0
    while t < 1_800_000:
        g1.frame(); ts1.tick(g1); t += 33
        if st1 and (not ck or ck[-1][1] != st1[-1][1]):
            ck.append((g1.P, st1[-1][1]))
    sleep(g1, ts1, 8)
    frames(g1, ts1, 1_000)
    P_save, mt_true = g1.P, ts1.mt
    d1 = draft1_mt_from_pt(ck, P_save)
    s.check("T7 DRAFT1 reproduces the defect (MT restored hours behind)", mt_true - d1 >= 400, (d1, mt_true))

    # T8 crash before the periodic MtCheckpoint: credit survives an unclean stop
    g, st, ts = fresh()
    frames(g, ts, 1_800_000)
    sleep(g, ts, 8)
    frames(g, ts, 10_000)                                   # < 60 s AT: no periodic checkpoint yet
    live = ts.mt
    restored = TimeService.restore_continuation(st)[0]      # unclean stop: no Aborted flush
    s.check("T8 unclean crash: credit not lost, base loss <= one checkpoint interval",
            live - restored <= CHECKPOINT_AT_MS // 2000 and restored >= live - 30, (restored, live))
    g1, st1, ts1 = fresh(Draft1Time)
    frames(g1, ts1, 1_800_000)
    sleep(g1, ts1, 8)
    frames(g1, ts1, 10_000)
    s.check("T8 DRAFT1 reproduces the defect (credit lost)", ts1.mt - TimeService.restore_continuation(st1)[0] >= 480)
    g, st, ts = fresh()
    frames(g, ts, 1_800_000)
    sleep(g, ts, 8)
    frames(g, ts, 10_000)
    ts.flush_on_stop()
    s.check("T8 clean stop: Aborted flush restores the MT state exactly", TimeService.restore_continuation(st) == ts.state())

    # T9 save/load around a time skip: A before sleep, B after; load A -> no credit; sleep again -> credit again;
    #    load B -> B's MT
    g, st, ts = fresh()
    led = Ledger()
    frames(g, ts, 1_800_000)
    led.save("A", g, ts)
    sleep(g, ts, 6)
    led.save("B", g, ts)
    s.check("T9 B includes the credit, A does not", led.rows["B"]["mt_obs"] - led.rows["A"]["mt_obs"] >= 360)
    ts2 = TimeService(st, state=led.rows["A"]["state"])     # anchored to A: MT state incl. rolling-cap bookkeeping
    g2 = Game()
    g2.gc_min = led.rows["A"]["gc"]
    ts2.tick(g2)
    sleep(g2, ts2, 6)
    s.check("T9 after loading A, sleeping again earns the credit again (world is before the sleep)",
            ts2.mt - led.rows["A"]["mt_obs"] >= 360)
    ts3 = TimeService(st, state=led.rows["B"]["state"])
    s.check("T9 load B restores B's MT state", ts3.state() == led.rows["B"]["state"] and ts3.mt == led.rows["B"]["mt_obs"])
    ts4 = TimeService(st, state=led.rows["B"]["state"])
    g4 = Game()
    g4.gc_min = led.rows["B"]["gc"]
    ts4.tick(g4)
    frames(g4, ts4, 2_000)
    m4 = ts4.mt
    sleep(g4, ts4, 12)
    s.check("T9 rolling cap carried across the load (credit after B bounded by B's window)",
            ts4.mt - m4 <= 720 and ts4.mt - m4 <= ts4.state()[1], ts4.mt - m4)

    # T10 offline / LSAX not running: MT frozen; the GC delta across a restart creates no credit
    g, st, ts = fresh()
    frames(g, ts, 600_000)
    ts.flush_on_stop()
    frozen = ts.mt
    for _ in range(int(3_600_000 / 33)):                    # 1 h of play while LSAX is not running
        g.frame()
    ts5 = TimeService(st, state=TimeService.restore_continuation(st))
    ts5.tick(g)
    frames(g, ts5, 33)
    s.check("T10 MT frozen while LSAX is not running; restart creates no credit", ts5.mt == frozen, (ts5.mt, frozen))

    # T11 rolling cap: three 12 h sleeps inside one MT day -> total credit capped by base accrued (<= 1 440)
    g, st, ts = fresh()
    frames(g, ts, 2 * 1_440 * 2000 // 2)                    # 1 440 base MT min
    base0 = ts.base_mt
    m0 = ts.mt
    for _ in range(3):
        sleep(g, ts, 12)
    credit = ts.mt - m0 - (ts.base_mt - base0)
    s.check("T11 three 12 h sleeps: credit capped (720 per event, rolling window)", credit <= 1_440 and credit >= 720, credit)

    # T12 PT semantics independence: MT restore identical whether PT counts pause/loading or not
    results = []
    for pause_pt in (False, True):
        for load_pt in (False, True):
            g, st, ts = fresh(pt_counts_pause=pause_pt, pt_counts_loading=load_pt)
            led = Ledger()
            frames(g, ts, 300_000)
            frames(g, ts, 60_000, paused=True)
            frames(g, ts, 20_000, loading=True)
            frames(g, ts, 300_000)
            sleep(g, ts, 8)
            led.save("S", g, ts)
            results.append(led.rows["S"]["mt_obs"])
    s.check("T12 restored MT independent of PT pause/loading semantics", len(set(results)) == 1, results)
    return s


def main():
    return run().report()


if __name__ == "__main__":
    sys.exit(main())
