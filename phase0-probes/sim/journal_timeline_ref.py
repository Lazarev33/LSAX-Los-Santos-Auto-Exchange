"""LSAX Phase 0 — Anchored-Timeline persistence + Transaction Core reference simulation (NOT PRODUCTION CODE).

Verifies the LOGIC of save/load model D (LSAX-SAVELOAD-FEASIBILITY.md §4, decisions D-SL-1..7, D-TX-1..3)
under the runtime ASSUMPTIONS that probe P-SL-01 must still prove on the target PC:
  A-SL-4 a GTA save snapshot never interleaves with one LSAX tick;
  A-SL-5 per-protagonist cash is restored from the save on load;
  A-SL-6 a persisted, monotonic play-time stat exists (granularity G);
  A-SL-7 save-file writes are observable (mtime/size/hash) while LSAX runs.
GTA is modelled as wallet + garage (GTA-side effects of LSAX transactions) + play-time P + wall clock W + save slots.
LSAX is a real SQLite database (WAL, synchronous=FULL). Crashes are injected at every protocol point
(C0 inside PREPARE, C1 after PREPARE, C2 after game-side apply, C3 after COMMIT); loads pick arbitrary slots;
LSAX-offline windows (script dead while the game continues) produce unobserved saves.

Ground truth: Gta.applied = ordered ids of LSAX transactions whose effects exist in the CURRENT game world.
I0: after every anchoring, LSAX's active path == Gta.applied, OR LSAX is RECONCILE_REQUIRED (refusing market
    operations, projection untouched). I1: projection == GTA garage. I2: idempotent replay on the active path.
I3: no double sell. I6: nothing is accepted while RECONCILE_REQUIRED.
"""
import os
import sqlite3
import sys
import tempfile

from lsax_ref_math import SplitMix64, derive_seed

LAT_MS = 2500     # max save-detection latency (P) for an OBSERVED slot to match
SLACK_MS = 2000   # slack on downtime windows
HB_MS = 3000      # heartbeat persistence interval for last_p/last_w (fallback after an unclean stop)
QUICK_MS = 10_000 # a restart faster than this must also match the last-tick wallet to count as continuation


class Crash(Exception):
    pass


class Gta:
    def __init__(self, g):
        self.G, self.P, self.W = g, 1, 1
        self.cash, self.garage, self.applied = 200_000, set(), []
        self.slots, self.ver = {}, 0
        self.proc = 1  # changes when the GTA process restarts

    def stat_p(self):
        return (self.P // self.G) * self.G

    def advance(self, ms):
        self.P += ms
        self.W += ms

    def save(self, slot):
        self.ver += 1
        self.slots[slot] = dict(P=self.stat_p(), cash=self.cash, garage=frozenset(self.garage), applied=tuple(self.applied), ver=self.ver,
                               mtime=self.W)

    def new_game(self):
        """GTA restarted with no save to load: a brand-new story (fresh play time, wallet, no LSAX effects)."""
        self.P, self.cash, self.garage, self.applied = 1, 200_000, set(), []

    def load(self, slot):
        s = self.slots[slot]
        self.P, self.cash, self.garage, self.applied = s["P"], s["cash"], set(s["garage"]), list(s["applied"])
        self.W += 20_000  # loading screen: wall time passes, play time does not


SCHEMA = """
CREATE TABLE IF NOT EXISTS timeline(id INTEGER PRIMARY KEY, parent_txn TEXT, fork_p INTEGER NOT NULL,
  last_p INTEGER NOT NULL, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commit_log(timeline_id INTEGER NOT NULL, seq INTEGER NOT NULL, txn_id TEXT NOT NULL UNIQUE,
  idem_key TEXT NOT NULL, kind TEXT NOT NULL, vehicle_id TEXT NOT NULL, cash_before INTEGER NOT NULL,
  cash_after INTEGER NOT NULL, p_ms INTEGER NOT NULL, PRIMARY KEY(timeline_id, seq));
CREATE TABLE IF NOT EXISTS txn(txn_id TEXT PRIMARY KEY, idem_key TEXT NOT NULL, state TEXT NOT NULL, kind TEXT NOT NULL,
  vehicle_id TEXT NOT NULL, cash_before INTEGER NOT NULL, cash_after INTEGER NOT NULL, p_prepare INTEGER NOT NULL,
  prev_txn TEXT);
CREATE TABLE IF NOT EXISTS reservation(vehicle_id TEXT PRIMARY KEY, txn_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS slot_obs(slot INTEGER PRIMARY KEY, ver INTEGER NOT NULL, mode TEXT NOT NULL,
  timeline_id INTEGER NOT NULL, p_lo INTEGER NOT NULL, p_hi INTEGER NOT NULL, cash INTEGER, pending_txn TEXT);
CREATE TABLE IF NOT EXISTS runtime(k TEXT PRIMARY KEY, v);
"""


class Lsax:
    def __init__(self, path, gta, stats):
        self.gta, self.stats = gta, stats
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
        self._cache = {}
        self.last_tick_p, self.last_tick_cash = gta.stat_p(), gta.cash
        if self.q1("SELECT COUNT(*) FROM timeline") == 0:
            def init():
                self.db.execute("INSERT INTO timeline VALUES(1,NULL,?,?,'ROOT')", (gta.stat_p(), gta.stat_p()))
                for k, v in (("active", 1), ("last_p", gta.stat_p()), ("last_w", gta.W), ("reconcile", 0), ("proc", gta.proc),
                             ("stop_clean", 1), ("stop_p", gta.stat_p()), ("stop_w", gta.W), ("stop_cash", gta.cash)):
                    self.set_rt(k, v)
            self.tx(init)
        self.anchor()

    # ---------------------------------------------------------------- helpers
    def q1(self, sql, args=()):
        r = self.db.execute(sql, args).fetchone()
        return r[0] if r else None

    def rt(self, k):
        return self.q1("SELECT v FROM runtime WHERE k=?", (k,))

    def set_rt(self, k, v):
        self.db.execute("INSERT INTO runtime(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    def tx(self, fn):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            fn()
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        finally:
            self._cache.clear()

    def tick(self):
        """Start of an LSAX tick: the only place game state is sampled for stop bookkeeping."""
        self.last_tick_p, self.last_tick_cash = self.gta.stat_p(), self.gta.cash

    def close(self, clean):
        if self.db.in_transaction:
            self.db.execute("ROLLBACK")  # script/process death: SQLite discards the uncommitted transaction
        if clean:  # Script.Aborted: flush LAST-TICK values from memory; never read game state here (E1-4, D-SL-7)
            self.tx(lambda: [self.set_rt(k, v) for k, v in (("stop_clean", 1), ("stop_p", self.last_tick_p),
                                                            ("stop_cash", self.last_tick_cash), ("stop_w", self.gta.W))])
        self.db.close()

    def commits(self, t):
        """Ordered commit rows on the path root..t: (tl, seq, txn_id, idem, kind, vid, before, after, p)."""
        if t in self._cache:
            return self._cache[t]
        parent_txn = self.q1("SELECT parent_txn FROM timeline WHERE id=?", (t,))
        prefix = []
        if parent_txn is not None:
            ptl, pseq = self.db.execute("SELECT timeline_id, seq FROM commit_log WHERE txn_id=?", (parent_txn,)).fetchone()
            prefix = [r for r in self.commits(ptl) if not (r[0] == ptl and r[1] > pseq)]
        own = [(t,) + r for r in self.db.execute(
            "SELECT seq, txn_id, idem_key, kind, vehicle_id, cash_before, cash_after, p_ms FROM commit_log WHERE timeline_id=? ORDER BY seq", (t,))]
        self._cache[t] = prefix + own
        return self._cache[t]

    def active_ids(self):
        return [r[2] for r in self.commits(self.rt("active"))]

    def projection(self):
        owned = set()
        for r in self.commits(self.rt("active")):
            (owned.add if r[4] == "BUY" else owned.discard)(r[5])
        return owned

    def heartbeat(self, force=False):
        g = self.gta
        if force or g.stat_p() - self.rt("last_p") >= HB_MS:
            self.tx(lambda: (self.set_rt("last_p", g.stat_p()), self.set_rt("last_w", g.W),
                             self.db.execute("UPDATE timeline SET last_p=? WHERE id=?", (g.stat_p(), self.rt("active")))))

    def poll_slots(self):
        """Observe changed save files while running (A-SL-7). Only the current content of each slot matters (D-SL-3)."""
        g = self.gta
        for slot, s in g.slots.items():
            if self.q1("SELECT ver FROM slot_obs WHERE slot=?", (slot,)) != s["ver"]:
                p = g.stat_p()
                self.tx(lambda: self.db.execute("INSERT OR REPLACE INTO slot_obs VALUES(?,?,'OBSERVED',?,?,?,?,NULL)",
                                                (slot, s["ver"], self.rt("active"), p - LAT_MS, p, g.cash)))

    # ---------------------------------------------------------------- transaction protocol (D-TX-1)
    def submit(self, kind, vid, price, idem, txn_id, crash_at=None):
        g = self.gta
        if self.rt("reconcile"):
            return "REFUSED_RECONCILE"
        if any(r[3] == idem for r in self.commits(self.rt("active"))):
            return "DUPLICATE"
        if self.q1("SELECT 1 FROM reservation WHERE vehicle_id=?", (vid,)):
            return "RESERVED_CONFLICT"
        owned = self.projection()
        if (kind == "BUY" and (vid in owned or g.cash < price)) or (kind == "SELL" and vid not in owned):
            return "REJECTED"
        before = g.cash
        after = before - price if kind == "BUY" else before + price
        ids = self.active_ids()
        prev = ids[-1] if ids else None

        def prepare():
            self.db.execute("INSERT INTO txn VALUES(?,?,'PREPARED',?,?,?,?,?,?)", (txn_id, idem, kind, vid, before, after, g.stat_p(), prev))
            self.db.execute("INSERT INTO reservation VALUES(?,?)", (vid, txn_id))
            if crash_at == "C0":
                raise Crash("C0")
        self.tx(prepare)
        if crash_at == "C1":
            raise Crash("C1")
        self.poll_slots()  # observation is exact right before the apply tick
        # ---- one game tick
        if g.cash != before:
            self._abort(txn_id)
            return "ABORTED_CONCURRENT_CASH"
        g.cash = after
        (g.garage.add if kind == "BUY" else g.garage.discard)(vid)
        g.applied.append(txn_id)
        self.last_tick_cash = after  # LSAX knows its own write: last KNOWN wallet (fix (a), D-SL-8)
        if crash_at == "C2":
            raise Crash("C2")
        self.tx(lambda: self._commit(txn_id, self.rt("active"), g.stat_p()))
        if crash_at == "C3":
            raise Crash("C3")
        return "COMMITTED"

    def _commit(self, txn_id, timeline, p):
        idem, kind, vid, b, a = self.db.execute("SELECT idem_key, kind, vehicle_id, cash_before, cash_after FROM txn WHERE txn_id=?", (txn_id,)).fetchone()
        seq = (self.q1("SELECT MAX(seq) FROM commit_log WHERE timeline_id=?", (timeline,)) or 0) + 1
        self.db.execute("INSERT INTO commit_log VALUES(?,?,?,?,?,?,?,?,?)", (timeline, seq, txn_id, idem, kind, vid, b, a, p))
        self.db.execute("UPDATE txn SET state='COMMITTED' WHERE txn_id=?", (txn_id,))
        self.db.execute("DELETE FROM reservation WHERE txn_id=?", (txn_id,))
        self.set_rt("last_p", max(self.rt("last_p"), p))
        self.set_rt("last_w", self.gta.W)

    def _abort(self, txn_id):
        self.tx(lambda: (self.db.execute("UPDATE txn SET state='ABORTED' WHERE txn_id=?", (txn_id,)),
                         self.db.execute("DELETE FROM reservation WHERE txn_id=?", (txn_id,))))

    # ---------------------------------------------------------------- anchoring (D-SL-2..6) and recovery (D-TX-2)
    def key_at(self, t, P, cash):
        rows = [r for r in self.commits(t) if r[8] <= P]
        inside, boundary = [r for r in rows if r[8] < P], [r for r in rows if r[8] == P]
        if not boundary:
            return tuple(r[2] for r in inside)
        # Commits in the same play-time granule as the save: exactly one prefix length k may explain the saved
        # wallet (expected wallet after k boundary commits); otherwise the position is ambiguous (D-SL-9).
        expected = [boundary[0][6]] + [r[7] for r in boundary]
        ks = [k for k, w in enumerate(expected) if w == cash]
        if len(ks) != 1:
            return None
        return tuple(r[2] for r in inside + boundary[:ks[0]])

    def anchor(self):
        """Session-start anchoring (D-SL-2..9) and PREPARED-transaction recovery (D-TX-2)."""
        g, st = self.gta, self.stats
        P, cash = g.stat_p(), g.cash
        clean = self.rt("stop_clean") == 1
        base_p = self.rt("stop_p") if clean else self.rt("last_p")
        base_w = self.rt("stop_w") if clean else self.rt("last_w")
        base_cash = self.rt("stop_cash") if clean else None
        down = max(0, g.W - base_w)
        same_proc = self.rt("proc") == g.proc
        before_proj = self.projection()
        pending = {r[0]: r[1:] for r in self.db.execute(
            "SELECT txn_id, cash_before, cash_after, p_prepare, prev_txn FROM txn WHERE state='PREPARED'").fetchall()}
        pend_id = next(iter(pending), None)
        ids = self.active_ids()
        head = ids[-1] if ids else None

        def reconcile(reason):
            st[f"reconcile_{reason}"] = st.get(f"reconcile_{reason}", 0) + 1
            self.tx(lambda: self.set_rt("reconcile", 1))
            assert self.projection() == before_proj, "I6: projection changed while entering RECONCILE"

        # (1) Saves written while LSAX was down belong to a DOWNTIME ghost timeline forked at the last known head.
        #     It never receives commits except the pending txn once evidence proves it was applied (D-SL-4, D-SL-10).
        changed = [(slot, s) for slot, s in sorted(g.slots.items()) if self.q1("SELECT ver FROM slot_obs WHERE slot=?", (slot,)) != s["ver"]]
        ghost = None
        if changed:
            def mk_ghost():
                self.db.execute("INSERT INTO timeline(parent_txn,fork_p,last_p,reason) VALUES(?,?,?,'DOWNTIME')", (head, base_p, base_p))
                gid = self.q1("SELECT MAX(id) FROM timeline")
                for slot, s in changed:
                    hi = base_p + max(0, s["mtime"] - base_w) + SLACK_MS  # play time <= wall time (D-SL-4)
                    self.db.execute("INSERT OR REPLACE INTO slot_obs VALUES(?,?,'INFERRED',?,?,?,NULL,?)", (slot, s["ver"], gid, base_p, hi, pend_id))
            self.tx(mk_ghost)
            ghost = self.q1("SELECT MAX(id) FROM timeline")

        # (2) Candidate world states.
        keys, decisions, matched, tainted = set(), {}, [], False
        for slot, ver, mode, t, lo, hi, ocash, ptx in self.db.execute("SELECT * FROM slot_obs").fetchall():
            if slot not in g.slots or g.slots[slot]["ver"] != ver or not (lo <= P <= hi) or (mode == "OBSERVED" and ocash != cash):
                continue
            matched.append((slot, t))
            k = self.key_at(t, P, cash)
            if ptx is not None:
                if ptx not in pending:
                    tainted = True  # the pending txn was resolved elsewhere; its status in this world is unknown
                    continue
                b, a, _, _ = pending[ptx]
                if cash == a and a != b and k is not None:
                    k, decisions[ptx] = k + (ptx,), ("APPLIED", t)
                elif cash == b:
                    decisions[ptx] = ("NOT_APPLIED", t)
                else:
                    tainted = True
                    continue
            keys.add(k)
        cash_ok = down > QUICK_MS or cash == base_cash or any(cash == v[1] for v in pending.values())
        continuation = same_proc and base_p <= P <= base_p + down + SLACK_MS and cash_ok
        if continuation:
            k = tuple(ids)  # the world went on from LSAX's last known state: full active path, no play-time cut
            for txn_id, (b, a, p_prep, prev) in pending.items():
                if txn_id in decisions:
                    continue
                if prev == head and cash == a and a != b:
                    decisions[txn_id] = ("APPLIED", ghost)
                    k = k + (txn_id,)
                elif cash == b:
                    decisions[txn_id] = ("NOT_APPLIED", ghost)
                else:
                    tainted = True
            keys.add(k)
        if tainted:
            return reconcile("TAINTED" if not continuation else "PENDING")
        if not keys:
            return reconcile("NO_MATCH")
        if None in keys or len(keys) != 1:
            return reconcile("AMBIGUOUS")
        key = keys.pop()
        kind = "anchored_continuation" if continuation and not matched else "anchored_slot"
        st[kind] = st.get(kind, 0) + 1

        # (3) Resolve PREPARED transactions with evidence only (D-TX-2).
        for txn_id, (b, a, p_prep, prev) in pending.items():
            verdict = decisions.get(txn_id, (None, None))[0]
            if verdict == "APPLIED" and key and key[-1] == txn_id:
                host = decisions[txn_id][1] or ghost
                if host is None:  # no ghost: host the commit on a RECOVERY timeline forked at its parent
                    self.tx(lambda: self.db.execute("INSERT INTO timeline(parent_txn,fork_p,last_p,reason) VALUES(?,?,?,'RECOVERY')", (prev, p_prep, p_prep)))
                    host = self.q1("SELECT MAX(id) FROM timeline")
                self.tx(lambda: (self._commit(txn_id, host, p_prep),  # applied in its PREPARE tick (D-TX-1)
                                 self.db.execute("UPDATE slot_obs SET pending_txn=NULL WHERE pending_txn=?", (txn_id,))))
                st["roll_forward"] = st.get("roll_forward", 0) + 1
            else:
                self._abort(txn_id)
                if verdict == "NOT_APPLIED":  # status in the downtime world is now known: untaint its saves
                    self.tx(lambda: self.db.execute("UPDATE slot_obs SET pending_txn=NULL WHERE pending_txn=?", (txn_id,)))
                st["abort_recovered"] = st.get("abort_recovered", 0) + 1

        # (4) Always fork the new active timeline at the anchored state (D-SL-5).
        def fork():
            self.db.execute("INSERT INTO timeline(parent_txn,fork_p,last_p,reason) VALUES(?,?,?,'ANCHOR')", (key[-1] if key else None, P, P))
            self.set_rt("active", self.q1("SELECT MAX(id) FROM timeline"))
            for k2, v in (("last_p", P), ("last_w", g.W), ("proc", g.proc), ("stop_clean", 0)):
                self.set_rt(k2, v)
        self.tx(fork)
        if len(matched) == 1 and not continuation and matched[0][1] != ghost:
            # exactly one save file explains the loaded world: learn its exact fingerprint (D-SL-11)
            self.tx(lambda: self.db.execute("UPDATE slot_obs SET mode='OBSERVED', p_lo=?, p_hi=?, cash=? WHERE slot=?",
                                            (P, P, cash, matched[0][0])))


ADVERSARIAL = [("BUY", 30), ("SELL", 20), ("EXT", 15), ("SAVE", 12), ("LOAD", 9), ("DUP", 5), ("DOUBLE", 3), ("CRASH", 8)]
REALISTIC = [("BUY", 25), ("SELL", 20), ("EXT", 35), ("SAVE", 10), ("LOAD", 2), ("DUP", 4), ("DOUBLE", 3), ("CRASH", 1)]


def episode(seed, gran, ops=160, mix=ADVERSARIAL):
    rng = SplitMix64(seed)
    g = Gta(gran)
    stats, fails = {}, []
    path = os.path.join(tempfile.mkdtemp(prefix="lsaxsim"), "lsax.db")
    lx, up = Lsax(path, g, stats), True
    nxt, bought = 0, []

    def check(where):
        if lx.rt("reconcile"):
            return
        if lx.active_ids() != g.applied:
            fails.append(f"I0 {where}: lsax={lx.active_ids()[-3:]} game={g.applied[-3:]}")
        if lx.projection() != g.garage:
            fails.append(f"I1 {where}")

    def restart(where):
        nonlocal lx, up
        lx = Lsax(path, g, stats)
        up = True
        check(where)

    for i in range(ops):
        if up and lx.rt("reconcile"):
            stats["episodes_ended_in_reconcile"] = stats.get("episodes_ended_in_reconcile", 0) + 1
            if lx.submit("BUY", "vX", 1, "kX", "tX") != "REFUSED_RECONCILE":
                fails.append("I6")
            break
        g.advance(rng.range_incl(1, 1500))
        if not up:  # LSAX offline window: the game continues without LSAX
            op = rng.pick_weighted([("EXT", 3), ("SAVE", 2), ("RESTART", 2), ("GAMECRASH", 1)])
            if op == "EXT":
                g.cash = max(0, g.cash + rng.range_incl(-20, 40) * 500)
            elif op == "SAVE":
                g.save(rng.below(4))
            elif op == "RESTART":
                restart(f"restart@{i}")
            elif op == "GAMECRASH":
                g.proc += 1
                g.W += 60_000
                if g.slots:
                    g.load(sorted(g.slots)[rng.below(len(g.slots))])
                else:
                    g.new_game()
                restart(f"gamecrash-offline@{i}")
            continue
        lx.tick()
        lx.heartbeat()
        lx.poll_slots()
        op = rng.pick_weighted(mix)
        crash_at = None
        if op == "CRASH":
            crash_at = rng.pick_weighted([("C0", 1), ("C1", 1), ("C2", 1), ("C3", 1)])
            op = "BUY" if rng.chance_bp(5000) else "SELL"
        try:
            if op == "BUY":
                nxt += 1
                vid = f"v{nxt}"
                if lx.submit("BUY", vid, rng.range_incl(5, 60) * 1000, f"k{nxt}", f"t{nxt}", crash_at) == "COMMITTED":
                    bought.append((vid, f"k{nxt}"))
            elif op == "SELL":
                owned = sorted(lx.projection())
                if owned:
                    nxt += 1
                    lx.submit("SELL", owned[rng.below(len(owned))], rng.range_incl(3, 50) * 1000, f"k{nxt}", f"t{nxt}", crash_at)
            elif op == "EXT":
                g.cash = max(0, g.cash + rng.range_incl(-20, 40) * 500)
            elif op == "SAVE":
                g.save(rng.below(4))
                g.advance(rng.range_incl(0, 1200))
                lx.poll_slots()
            elif op == "LOAD" and g.slots:
                g.load(sorted(g.slots)[rng.below(len(g.slots))])
                lx.close(clean=True)
                restart(f"load@{i}")  # SHVDN domain reload (E1-1/E1-2) -> constructor -> anchoring
            elif op == "DUP" and bought:
                vid, key = bought[rng.below(len(bought))]
                on_path = key in [r[3] for r in lx.commits(lx.rt("active"))]
                r = lx.submit("BUY", vid, 1000, key, f"dup{i}")
                if on_path and r != "DUPLICATE":
                    fails.append(f"I2 replay not idempotent: {r}")
            elif op == "DOUBLE":
                owned = sorted(lx.projection())
                if owned:
                    lx.submit("SELL", owned[0], 1000, f"dd{i}a", f"dd{i}a")
                    if lx.submit("SELL", owned[0], 1000, f"dd{i}b", f"dd{i}b") == "COMMITTED":
                        fails.append("I3 double sell")
        except Crash as c:
            stats[f"crash_{c}"] = stats.get(f"crash_{c}", 0) + 1
            mode = rng.pick_weighted([("SCRIPT_RELOAD", 2), ("GAME_CRASH", 2), ("OFFLINE", 1)])
            lx.close(clean=(mode != "GAME_CRASH"))  # exception abort runs Aborted; a game crash does not
            if mode == "OFFLINE":
                up = False  # script dead; game keeps running until a later RESTART/GAMECRASH
                continue
            if mode == "GAME_CRASH":
                g.W += 60_000
                g.proc += 1
                if g.slots:
                    g.load(sorted(g.slots)[rng.below(len(g.slots))])
                else:
                    g.new_game()
            restart(f"crash-{c}-{mode}@{i}")
            continue
        check(f"op{i}")
    if up:
        lx.close(clean=True)
    return stats, fails


def main():
    fails, n_ep = [], 200
    for mix_name, mix, ops in (("ADVERSARIAL", ADVERSARIAL, 160), ("REALISTIC", REALISTIC, 400)):
        total = {}
        for gran in (1, 1000):
            for e in range(n_ep):
                st, f = episode(derive_seed("journal-v2", mix_name, gran, e), gran, ops=ops, mix=mix)
                for k, v in st.items():
                    total[f"G={gran}ms {k}"] = total.get(f"G={gran}ms {k}", 0) + v
                fails += [f"{mix_name} G={gran} ep{e}: {x}" for x in f]
        print(f"\n### {mix_name} mix: {2 * n_ep} episodes (200 per stat granularity), up to {ops} operations each\n")
        print("| Counter | Value |\n|---|---:|")
        for k in sorted(total):
            print(f"| {k} | {total[k]} |")
        for gran in (1, 1000):
            anch = sum(v for k, v in total.items() if k.startswith(f"G={gran}ms anchored"))
            rec = sum(v for k, v in total.items() if k.startswith(f"G={gran}ms reconcile_"))
            print(f"\n{mix_name} G={gran}ms: successful anchorings={anch}, RECONCILE_REQUIRED={rec} ({100 * rec / max(anch + rec, 1):.2f}% of anchorings)")
            # Non-vacuity tripwire, NOT an acceptance criterion: it exists because an earlier revision "passed" while
            # every episode entered RECONCILE on its first anchoring. Thresholds were set after that incident.
            if mix_name == "ADVERSARIAL" and (anch < 10 * n_ep or rec * 100 > 6 * (anch + rec)):
                fails.append(f"NON-VACUITY {mix_name} G={gran}: anchorings={anch} reconcile={rec}")
    print(f"\nSafety invariant failures (I0 I1 I2 I3 I6) + tripwires: {len(fails)}")
    for f in fails[:15]:
        print("  -", f)
    print("RESULT:", "PASS" if not fails else "FAIL")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
