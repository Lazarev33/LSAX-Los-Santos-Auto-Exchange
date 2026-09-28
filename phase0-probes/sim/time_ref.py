"""LSAX Phase 0 — AT / MT time reference model, DRAFT2 (NOT PRODUCTION CODE).

Normative mirror of LSAX-TIME-MODEL.md §2 as corrected for audit finding P1-03 (decision D-TIME-2):
  * PT (persisted play-time stat) is an ANCHOR COORDINATE ONLY (save/load exclusion). MT is never computed from PT.
  * MT is LSAX-internal: integrated from AT (1 MT min per 2 000 ms AT) plus capped time-skip credits.
  * Durability: SYS_MT_CHECKPOINT (system transaction, D-JRN-1) every 60 s AT **and immediately at every skip
    credit**; the in-memory MT is flushed in Aborted (clean stop); every observed save records mt_obs (MT sampled at
    the observing poll, after skip detection in that tick).
  * The persisted MT STATE is (mt, base_mt, recent credits) — the rolling skip-credit cap is timeline state too.
  * Restore at anchoring: continuation -> flushed MT state (clean) or last durable checkpoint (unclean; loses at most
    one checkpoint interval of BASE MT, never a credit); slot anchoring -> the ledger row's MT state (mt_obs);
    EMPTY -> campaign root MT state.
  * MT does not advance while LSAX is not running.
`draft1_mt_from_pt` reproduces the DRAFT1 rule MT(P) = mt_cp + rdiv(P - p_cp, 2000) (audit P1-03 defect).
"""
import sys

from lsax_ref_math import rdiv

TICK_MS = 33
MT_MS = 2000
STALL_MS = 1000
FADE_COUNT_MS = 5000
CHECKPOINT_AT_MS = 60_000
SKIP_MIN, SKIP_EVENT_CAP, SKIP_WINDOW = 30, 720, 1440


class Game:
    """Game-side clocks. PT semantics are a parameter (pt_counts_pause / pt_counts_loading) because they are
    unproven; the model shows MT does not depend on them."""

    def __init__(self, pt_counts_pause=False, pt_counts_loading=False):
        self.gt, self.gc_min, self.P = 0, 8 * 60, 1
        self.paused = self.loading = self.switching = False
        self.faded_ms = 0                   # consecutive faded-out time
        self.pt_counts_pause, self.pt_counts_loading = pt_counts_pause, pt_counts_loading
        self.gc_ms_acc = 0

    def frame(self, ms=TICK_MS):
        self.gt += ms
        active_for_pt = (not self.paused or self.pt_counts_pause) and (not self.loading or self.pt_counts_loading)
        if active_for_pt:
            self.P += ms
        if not self.paused and not self.loading:
            self.gc_ms_acc += ms                             # GTA clock: 2 000 ms per game minute (default)
            self.gc_min += self.gc_ms_acc // 2000
            self.gc_ms_acc %= 2000


class TimeService:
    def __init__(self, store, state=(0, 0, ())):
        self.store = store                                   # durable: list of ("CKPT", mt, reason, state)
        self.mt, self.base_mt, credits = state               # base MT accrued (rolling cap), recent credits
        self.credits = list(credits)                         # (base_mt_at_grant, credit)
        self.at_rem = 0
        self.at_since_ckpt = 0
        self.prev_gt = self.prev_gc = None

    def state(self):
        recent = tuple((b, c) for b, c in self.credits if self.base_mt - b < SKIP_WINDOW)
        return (self.mt, self.base_mt, recent)

    def _ckpt(self, reason):
        self.store.append(("CKPT", self.mt, reason, self.state()))

    def _active(self, g):
        return not g.paused and not g.loading and not g.switching and g.faded_ms <= FADE_COUNT_MS

    def tick(self, g):
        if self.prev_gt is None:
            self.prev_gt, self.prev_gc = g.gt, g.gc_min      # first tick after start: no delta, no detection
            return
        d = g.gt - self.prev_gt
        self.prev_gt = g.gt
        base = 0
        if 0 <= d <= STALL_MS and self._active(g):
            self.at_rem += d
            self.at_since_ckpt += d
            base, self.at_rem = self.at_rem // MT_MS, self.at_rem % MT_MS
            self.mt += base
            self.base_mt += base
        dgc = g.gc_min - self.prev_gc
        self.prev_gc = g.gc_min
        skip = dgc - base
        if skip >= SKIP_MIN:                                 # negative GC jumps are ignored (dgc < 0)
            window = sum(c for b, c in self.credits if self.base_mt - b < SKIP_WINDOW)
            base_window = min(self.base_mt, SKIP_WINDOW)
            credit = max(0, min(skip, SKIP_EVENT_CAP, base_window - window))
            if credit:
                self.mt += credit
                self.credits.append((self.base_mt, credit))
                self._ckpt("SKIP_CREDIT")                    # durable immediately (D-TIME-2)
                self.at_since_ckpt = 0
        if self.at_since_ckpt >= CHECKPOINT_AT_MS:
            self._ckpt("PERIODIC")
            self.at_since_ckpt = 0

    def flush_on_stop(self):
        self._ckpt("ABORTED_FLUSH")

    @staticmethod
    def restore_continuation(store):
        return store[-1][3] if store else (0, 0, ())


class Draft1Time(TimeService):
    """DRAFT1: credit persisted only by the periodic MtCheckpoint; restore MT(P) from PT."""

    def tick(self, g):
        before = len(self.store)
        super().tick(g)
        if len(self.store) > before and self.store[-1][2] == "SKIP_CREDIT":
            self.store.pop()                                  # DRAFT1 had no immediate credit persistence


def draft1_mt_from_pt(checkpoints_with_p, P):
    """DRAFT1 TIME §2.2: MT(P) = mt_cp + rdiv(P - p_cp, 2000) using the last checkpoint with p_cp <= P."""
    cands = [(p, mt) for p, mt in checkpoints_with_p if p <= P]
    if not cands:
        return 0
    p_cp, mt_cp = max(cands)
    return mt_cp + rdiv(P - p_cp, MT_MS)


def run_frames(g, ts, ms_total, **flags):
    for k, v in flags.items():
        setattr(g, k, v)
    t = 0
    while t < ms_total:
        g.frame()
        if g.faded_ms or flags.get("fading"):
            g.faded_ms += TICK_MS
        ts.tick(g)
        t += TICK_MS
    for k in flags:
        if k != "fading":
            setattr(g, k, False)
    g.faded_ms = 0


def sleep(g, ts, hours, fade_ms=8000):
    """Bed sleep: screen faded out, GTA clock jumps by `hours` during the fade."""
    t, jumped = 0, False
    while t < fade_ms:
        g.frame()
        g.faded_ms += TICK_MS
        if not jumped and t >= fade_ms // 2:
            g.gc_min += hours * 60
            jumped = True
        ts.tick(g)
        t += TICK_MS
    g.faded_ms = 0


def main():
    g, store = Game(), []
    ts = TimeService(store)
    ts.tick(g)
    run_frames(g, ts, 30 * 60 * 1000)
    ok = ts.mt in (899, 900)
    print(f"30 min active play -> MT {ts.mt} (expected 900 +/- 1)")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
