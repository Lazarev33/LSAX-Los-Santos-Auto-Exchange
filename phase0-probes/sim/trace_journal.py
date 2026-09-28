"""Debug tracer for the DRAFT2 journal_timeline_ref.py (Phase 0 tooling, NOT PRODUCTION CODE).
Usage: python3 trace_journal.py <granularity_ms> <episode> [ops] [tail] [ADVERSARIAL|REALISTIC]
Replays exactly the episode that journal_timeline_ref.main() runs for (mix, granularity, episode)."""
import sys

import journal_timeline_ref as J
from lsax_ref_math import derive_seed

log = []


def wrap(cls, name, fmt):
    orig = getattr(cls, name)

    def f(self, *a, **k):
        pre = fmt(self, "pre", a)
        try:
            r = orig(self, *a, **k)
        except Exception as e:
            log.append((name, pre, "EXC", repr(e)))
            raise
        log.append((name, pre, r, fmt(self, "post", a)))
        return r
    setattr(cls, name, f)


def rtd(s):
    return {k: v for k, v in s.db.execute("select k,v from runtime")}


wrap(J.Lsax, "submit", lambda s, w, a: (a[0], a[1], a[4], s.gta.stat_p(), s.gta.cash) if w == "pre" else (s.rt("active"), s.active_ids()[-3:]))
wrap(J.Lsax, "anchor", lambda s, w, a: (s.gta.stat_p(), s.gta.cash, s.gta.W, s.gta.proc, rtd(s),
                                        [tuple(r) for r in s.db.execute("select * from slot_state")],
                                        [tuple(r) for r in s.db.execute("select sha, kind, head_txn, p_lo, p_hi from save_ledger")],
                                        [tuple(r) for r in s.db.execute("select txn_id,cash_before,cash_after,p_prepare,prev_txn from txn where state='PREPARED'")])
       if w == "pre" else (s.rt("active"), s.active_ids()[-4:], {k: v for k, v in s.stats.items() if "anch" in k or "recon" in k or "roll" in k}))
wrap(J.Lsax, "close", lambda s, w, a: (a, s.p_last, dict(s.mem_apply)) if w == "pre" else None)
wrap(J.Gta, "save", lambda s, w, a: (a[0], s.stat_p(), s.cash, list(s.applied)[-3:]) if w == "pre" else s.ver)
wrap(J.Gta, "load", lambda s, w, a: (a[0],) if w == "pre" else (s.stat_p(), s.cash, list(s.applied)[-3:]))

if __name__ == "__main__":
    gran, ep = int(sys.argv[1]), int(sys.argv[2])
    ops = int(sys.argv[3]) if len(sys.argv) > 3 else 160
    tail = int(sys.argv[4]) if len(sys.argv) > 4 else 25
    mix_name = sys.argv[5] if len(sys.argv) > 5 else "ADVERSARIAL"
    mix = J.ADVERSARIAL if mix_name == "ADVERSARIAL" else J.REALISTIC
    st, f = J.episode(derive_seed("journal-draft2", mix_name, gran, ep), gran, ops=ops, mix=mix)
    for e in log[-tail:]:
        print(e)
    print("FAILS:", f[:2])
