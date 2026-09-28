"""LSAX Phase 0 — Anchored-Timeline persistence + Transaction Core reference simulation, DRAFT2 (NOT PRODUCTION CODE).

Corrected after the independent audit (findings P0-02, P0-03). Normative mirror of LSAX-SAVELOAD-FEASIBILITY.md §4
and LSAX-TRANSACTION-STATE-MACHINE.md §7 (decisions D-SL-13, D-SL-14, D-SL-15, D-SL-16, D-TX-4, D-TX-5).

Evidence rule: NO POSITIVE EVIDENCE -> NO AUTOMATIC ACCEPTANCE. Accepted positive evidence is only
  (a) LSAX's own durable knowledge of its own actions (apply status flushed in Aborted),
  (b) runtime-scoped proof that the game session did not change (session token decorator on the player ped),
  (c) byte-identical content of a save LSAX observed being written (SHA-256), corroborated by a game save event.
Play-time, wallets, wall-clock proximity and slot names are CORRELATIONS. In this model they are used only to
EXCLUDE a hypothesis (a mismatch proves "the world was not loaded from that file", given A-SL-5/A-SL-6); they never
INCLUDE one. Anchoring without a session token enumerates every hypothesis for where the current world came from and
accepts only if every non-excluded hypothesis has a known LSAX state, all of them agree, and at least one of them is
a positively lineaged (content-identified) save file. Everything else is RECONCILE_REQUIRED.

Runtime assumptions this model depends on (closed only by P-SL-01 on the target PC, BLOCKER B-01):
  A-SL-1 load restarts the script domain; A-SL-4 a save never interleaves one LSAX tick; A-SL-5 wallet vector restored
  exactly on load; A-SL-6 persisted play-time stat, restored exactly on load, non-decreasing within a session;
  A-SL-7 save files observable (metadata + content hash); A-SL-8 GTA loads only from the profile slot files and the
  loaded file is unchanged when LSAX's startup scan runs; A-SL-9 LSAX is constructed at every script-domain start (a
  failed start leaves a durable MISSED_START marker); A-SL-10 the session-token decorator survives script reloads
  within a session and never survives a load, new game or new process; A-SL-12 every game save emits an observable
  save event near the file write and a file copy does not; A-SL-13 a new game starts with play-time <= NEWGAME_P_MAX;
  A-SL-14 no other mod changes a wallet and restores it strictly between two LSAX polls.

GTA model attributes stay compatible with the DRAFT1 names used by the audit reproduction (cash, P, W, G, proc, ver,
slots[s] = dict(P, cash, garage, applied, ver, mtime), load(), advance(), stat_p()).
Ground truth: Gta.applied = ordered ids of LSAX transactions whose effects exist in the CURRENT game world.
I0: when not RECONCILE_REQUIRED, LSAX active path == Gta.applied.  I1: projection == garage.  I2 idempotent replay.
I3 no double sell.  I6 while RECONCILE_REQUIRED: projection untouched, every market operation refused, restarts keep it.
"""
import argparse
import os
import sqlite3
import sys
import tempfile
import time

from lsax_ref_math import SplitMix64, derive_seed

EVENT_WINDOW_MS = 2000      # save event <-> file write correlation window (wall ms); only used to REJECT, see poll
NEWGAME_P_MAX = 60_000      # A-SL-13
EMPTY = "EMPTY"             # state key of "no LSAX commits"


class Crash(Exception):
    pass


class Gta:
    def __init__(self, g):
        self.G, self.P, self.W, self.proc = g, 1, 1, 1
        self.wallets = [200_000, 150_000, 100_000]
        self.char = 0
        self.garage, self.applied = set(), []
        self.slots, self.ver = {}, 0
        self.session = 1
        self.ped_token = None      # LSAX session decorator on the current player ped (runtime only)
        self.save_events = []      # wall times of game save events not yet consumed by LSAX

    @property
    def cash(self):
        return self.wallets[self.char]

    @cash.setter
    def cash(self, v):
        self.wallets[self.char] = v

    def stat_p(self):
        return (self.P // self.G) * self.G

    def advance(self, ms):
        self.P += ms
        self.W += ms

    def _snapshot(self, source):
        self.ver += 1
        return dict(P=self.stat_p(), cash=self.cash, wallets=tuple(self.wallets), char=self.char,
                    garage=frozenset(self.garage), applied=tuple(self.applied), ver=self.ver, mtime=self.W, source=source)

    def save(self, slot):
        """A genuine game save: writes the file and raises the observable save event (A-SL-12)."""
        self.slots[slot] = self._snapshot("GAME")
        self.save_events.append(self.W)

    def copy_foreign(self, slot, P, wallets, garage=(), applied=()):
        """A file copied into the profile folder (download, other install, editor). No save event."""
        self.ver += 1
        self.slots[slot] = dict(P=P, cash=wallets[0], wallets=tuple(wallets), char=0, garage=frozenset(garage),
                                applied=tuple(applied), ver=self.ver, mtime=self.W, source="FOREIGN")

    def restore_copy(self, slot, snapshot):
        """Byte-identical copy of an earlier file (backup restore): same content => same hash (ver)."""
        s = dict(snapshot)
        s["mtime"] = self.W
        self.slots[slot] = s

    def delete_slot(self, slot):
        self.slots.pop(slot, None)

    def _new_session(self):
        self.session += 1
        self.ped_token = None

    def load(self, slot):
        s = self.slots[slot]
        wallets = s.get("wallets") or tuple([s["cash"]] + self.wallets[1:])
        self.P, self.garage, self.applied = s["P"], set(s["garage"]), list(s["applied"])
        self.wallets, self.char = list(wallets), s.get("char", 0)
        self.W += 20_000
        self._new_session()

    def new_game(self):
        self.P, self.wallets, self.char, self.garage, self.applied = 1, [200_000, 150_000, 100_000], 0, set(), []
        self.W += 20_000
        self._new_session()

    def process_crash(self):
        self.proc += 1
        self.W += 60_000
        self._new_session()

    def switch_char(self, c):
        self.char = c
        self.ped_token = None      # a different ped entity becomes the player ped


SCHEMA = """
CREATE TABLE IF NOT EXISTS timeline(id INTEGER PRIMARY KEY, parent_txn TEXT, fork_p INTEGER NOT NULL, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commit_log(timeline_id INTEGER NOT NULL, seq INTEGER NOT NULL, txn_id TEXT NOT NULL UNIQUE,
  idem_key TEXT NOT NULL, kind TEXT NOT NULL, vehicle_id TEXT NOT NULL, wallet_slot INTEGER NOT NULL,
  cash_before INTEGER NOT NULL, cash_after INTEGER NOT NULL, p_ms INTEGER NOT NULL, PRIMARY KEY(timeline_id, seq));
CREATE TABLE IF NOT EXISTS txn(txn_id TEXT PRIMARY KEY, idem_key TEXT NOT NULL, state TEXT NOT NULL, kind TEXT NOT NULL,
  vehicle_id TEXT NOT NULL, wallet_slot INTEGER NOT NULL, cash_before INTEGER NOT NULL, cash_after INTEGER NOT NULL,
  p_prepare INTEGER NOT NULL, prev_txn TEXT, apply_status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reservation(vehicle_id TEXT PRIMARY KEY, txn_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS save_ledger(sha INTEGER PRIMARY KEY, kind TEXT NOT NULL, head_txn TEXT,
  p_lo INTEGER, p_hi INTEGER, w0 INTEGER, w1 INTEGER, w2 INTEGER);
CREATE TABLE IF NOT EXISTS slot_state(slot INTEGER PRIMARY KEY, sha INTEGER NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runtime(k TEXT PRIMARY KEY, v);
"""


def mark_missed_start(path, gta):
    """A-SL-9: LSAX was constructed at a script-domain start but could not start (exception before anchoring).
    Its catch-all writes only this marker (no game-state read, no anchoring)."""
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("INSERT INTO runtime(k,v) VALUES('missed_start',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (gta.proc,))
    db.close()
    gta.save_events.clear()


class Lsax:
    def __init__(self, path, gta, stats, policy=None):   # policy: accepted for DRAFT2-early call compatibility, unused
        self.gta, self.stats = gta, stats
        first_run = not os.path.exists(path)
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
        self._cache = {}
        self.mem_apply = {}                    # in-memory apply status of this instance's pending txn
        self.p_last = None                     # highest play-time observed live in this session (flushed on stop)
        self.p_prev = self.w_prev = None       # poll bracket: P and wallets at the previous poll / own write
        gta.save_events.clear()                # events raised while LSAX was down cannot be correlated
        if first_run:
            self._first_run()
        else:
            self._startup_slot_scan()
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

    def bump(self, k, n=1):
        self.stats[k] = self.stats.get(k, 0) + n

    def commits(self, t):
        if t in self._cache:
            return self._cache[t]
        parent_txn = self.q1("SELECT parent_txn FROM timeline WHERE id=?", (t,))
        prefix = []
        if parent_txn is not None:
            ptl, pseq = self.db.execute("SELECT timeline_id, seq FROM commit_log WHERE txn_id=?", (parent_txn,)).fetchone()
            prefix = [r for r in self.commits(ptl) if not (r[0] == ptl and r[1] > pseq)]
        own = [(t,) + r for r in self.db.execute(
            "SELECT seq, txn_id, idem_key, kind, vehicle_id FROM commit_log WHERE timeline_id=? ORDER BY seq", (t,))]
        self._cache[t] = prefix + own
        return self._cache[t]

    def active_ids(self):
        return [r[2] for r in self.commits(self.rt("active"))]

    def head(self):
        ids = self.active_ids()
        return ids[-1] if ids else None

    def projection(self):
        owned = set()
        for r in self.commits(self.rt("active")):
            (owned.add if r[4] == "BUY" else owned.discard)(r[5])
        return owned

    def _observe(self, P, W=None):
        """LSAX's own in-memory knowledge of the live session (never read in Aborted)."""
        self.p_last = P if self.p_last is None else max(self.p_last, P)
        self.p_prev = P
        if W is not None:
            self.w_prev = W

    # ---------------------------------------------------------------- lifecycle
    def _first_run(self):
        """First-ever start (no database): the world cannot contain effects of THIS journal. Existing save files are
        recorded as PRE_INSTALL: LSAX state EMPTY (known), fingerprint unknown (never excludable)."""
        g = self.gta

        def init():
            self.db.execute("INSERT INTO timeline VALUES(1,NULL,?,'ROOT')", (g.stat_p(),))
            self.set_rt("active", 1)
            self.set_rt("reconcile", 0)
            self.set_rt("reconcile_reason", "")
            self.set_rt("reconcile_candidates", "")
            for slot, s in g.slots.items():
                self.db.execute("INSERT OR IGNORE INTO save_ledger VALUES(?,'PRE_INSTALL',NULL,NULL,NULL,NULL,NULL,NULL)",
                                (s["ver"],))
                self.db.execute("INSERT OR REPLACE INTO slot_state VALUES(?,?,?,?)", (slot, s["ver"], "PRE_INSTALL", "PRE_INSTALL"))
        self.tx(init)
        self._started()
        self.bump("anchored_first_run")

    def _started(self):
        """Successful anchoring: new session token on the player ped, session identity, fresh poll bracket."""
        g = self.gta
        tok = (derive_seed("token", g.proc, g.session, g.W, g.P) & 0x7FFFFFFF) or 1
        g.ped_token = tok
        P, W = g.stat_p(), tuple(g.wallets)
        self.p_last = None
        self._observe(P, W)

        def persist():
            self.set_rt("session_token", tok)
            self.set_rt("proc", g.proc)
            self.set_rt("p_last", P)
            self.set_rt("stop_clean", 0)
            self.db.execute("DELETE FROM runtime WHERE k='missed_start'")
        self.tx(persist)

    def tick(self):
        """Start of an LSAX tick while running: re-tag the player ped if it changed (same session), poll saves."""
        g = self.gta
        if self.rt("reconcile"):
            return
        if g.ped_token is None:
            g.ped_token = self.rt("session_token")
        self.poll_slots()

    def close(self, clean):
        if self.db.in_transaction:
            self.db.execute("ROLLBACK")
        if clean:  # Script.Aborted: flush LSAX's own in-memory knowledge; never read game state here (D-SL-7)
            def flush():
                for txn_id, st in self.mem_apply.items():
                    self.db.execute("UPDATE txn SET apply_status=? WHERE txn_id=? AND state='PREPARED'", (st, txn_id))
                if self.p_last is not None and not self.rt("reconcile"):
                    self.set_rt("p_last", max(self.p_last, self.rt("p_last") or 0))
                self.set_rt("stop_clean", 1)
            self.tx(flush)
        self.db.close()

    # ---------------------------------------------------------------- save ledger (D-SL-13)
    def poll_slots(self):
        g = self.gta
        P, W = g.stat_p(), tuple(g.wallets)
        changed = [(slot, s) for slot, s in sorted(g.slots.items())
                   if self.q1("SELECT sha FROM slot_state WHERE slot=?", (slot,)) != s["ver"]]
        events = list(g.save_events)
        g.save_events.clear()
        for slot, s in changed:
            near_events = [e for e in events if abs(e - s["mtime"]) <= EVENT_WINDOW_MS]
            rivals = [x for x, xs in changed if x != slot and any(abs(e - xs["mtime"]) <= EVENT_WINDOW_MS for e in near_events)]
            kind = self.q1("SELECT kind FROM save_ledger WHERE sha=?", (s["ver"],))
            if kind is not None:                         # byte-identical to content LSAX already knows
                status, reason = ("PRE_INSTALL" if kind == "PRE_INSTALL" else "TRUSTED"), "KNOWN_CONTENT"
            elif len(near_events) == 1 and not rivals and self.p_prev is not None:
                # The file was written between the previous poll and now: P_file in [p_prev, P] (A-SL-6 monotonic).
                # Wallets are recorded only if unchanged across the bracket (A-SL-14); otherwise unknown (NULL).
                w = W if self.w_prev == W else (None, None, None)
                head, p_lo = self.head(), self.p_prev
                self.tx(lambda: (self.db.execute("INSERT OR IGNORE INTO save_ledger VALUES(?,'OBSERVED',?,?,?,?,?,?)",
                                                 (s["ver"], head, p_lo, P) + tuple(w)),
                                 self.set_rt("p_last", max(P, self.rt("p_last") or 0))))
                status, reason = "TRUSTED", "OBSERVED"
                self.bump("ledger_observed")
                if w[0] is None:
                    self.bump("ledger_wallets_unknown")
            else:
                status, reason = "UNTRUSTED", "FOREIGN_WHILE_RUNNING" if not near_events else "AMBIGUOUS_EVENT"
            self.tx(lambda: self.db.execute("INSERT OR REPLACE INTO slot_state VALUES(?,?,?,?)", (slot, s["ver"], status, reason)))
        for slot, in self.db.execute("SELECT slot FROM slot_state").fetchall():
            if slot not in g.slots:
                self.tx(lambda: self.db.execute("DELETE FROM slot_state WHERE slot=?", (slot,)))
        self._observe(P, W)

    def _scan_unobserved(self, reason_new):
        """Files changed while LSAX was not observing are UNTRUSTED unless byte-identical to content LSAX knows."""
        g = self.gta
        for slot, s in sorted(g.slots.items()):
            if self.q1("SELECT sha FROM slot_state WHERE slot=?", (slot,)) == s["ver"]:
                continue
            kind = self.q1("SELECT kind FROM save_ledger WHERE sha=?", (s["ver"],))
            if kind is None:
                status, reason = "UNTRUSTED", reason_new
            else:
                status, reason = ("PRE_INSTALL" if kind == "PRE_INSTALL" else "TRUSTED"), "RESTORED_COPY"
            self.tx(lambda: self.db.execute("INSERT OR REPLACE INTO slot_state VALUES(?,?,?,?)", (slot, s["ver"], status, reason)))
        for slot, in self.db.execute("SELECT slot FROM slot_state").fetchall():
            if slot not in g.slots:
                self.tx(lambda: self.db.execute("DELETE FROM slot_state WHERE slot=?", (slot,)))

    def _startup_slot_scan(self):
        self._scan_unobserved("CHANGED_WHILE_DOWN")

    # ---------------------------------------------------------------- transaction protocol (D-TX-1, D-TX-4)
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
        slot = g.char
        before = g.cash
        after = before - price if kind == "BUY" else before + price
        prev = self.head()

        def prepare():
            self.db.execute("INSERT INTO txn VALUES(?,?,'PREPARED',?,?,?,?,?,?,?, 'APPLYING')",
                            (txn_id, idem, kind, vid, slot, before, after, g.stat_p(), prev))
            self.db.execute("INSERT INTO reservation VALUES(?,?)", (vid, txn_id))
            if crash_at == "C0":
                raise Crash("C0")
        self.tx(prepare)
        self.mem_apply = {txn_id: "NOT_STARTED"}
        if crash_at == "C1":
            raise Crash("C1")
        self.poll_slots()                      # a save observed from here on predates the apply (A-SL-4)
        if g.wallets[slot] != before:          # verify-before-apply (another mod wrote cash)
            self.mem_apply = {}
            self.tx(lambda: (self.db.execute("UPDATE txn SET state='ABORTED', apply_status='NOT_STARTED' WHERE txn_id=?", (txn_id,)),
                             self.db.execute("DELETE FROM reservation WHERE txn_id=?", (txn_id,))))
            return "ABORTED_CONCURRENT_CASH"
        self.mem_apply = {txn_id: "APPLYING"}
        if crash_at == "CA":                   # dies after marking APPLYING, before the native write
            raise Crash("CA")
        g.wallets[slot] = after
        (g.garage.add if kind == "BUY" else g.garage.discard)(vid)
        g.applied.append(txn_id)
        self.w_prev = tuple(g.wallets)         # LSAX's own write is known; the bracket restarts after it
        if crash_at == "CB":                   # dies after the native write, before recording APPLIED
            raise Crash("CB")
        self.mem_apply = {txn_id: "APPLIED"}
        if crash_at == "C2":
            raise Crash("C2")
        self.tx(lambda: self._commit(txn_id, self.rt("active"), g.stat_p()))
        self.mem_apply = {}
        if crash_at == "C3":
            raise Crash("C3")
        return "COMMITTED"

    def _commit(self, txn_id, timeline, p):
        idem, kind, vid, ws, b, a = self.db.execute(
            "SELECT idem_key, kind, vehicle_id, wallet_slot, cash_before, cash_after FROM txn WHERE txn_id=?", (txn_id,)).fetchone()
        seq = (self.q1("SELECT MAX(seq) FROM commit_log WHERE timeline_id=?", (timeline,)) or 0) + 1
        self.db.execute("INSERT INTO commit_log VALUES(?,?,?,?,?,?,?,?,?,?)", (timeline, seq, txn_id, idem, kind, vid, ws, b, a, p))
        self.db.execute("UPDATE txn SET state='COMMITTED', apply_status='APPLIED' WHERE txn_id=?", (txn_id,))
        self.db.execute("DELETE FROM reservation WHERE txn_id=?", (txn_id,))
        self.set_rt("p_last", max(p, self.rt("p_last") or 0))

    def _abort(self, txn_id):
        self.tx(lambda: (self.db.execute("UPDATE txn SET state='ABORTED' WHERE txn_id=?", (txn_id,)),
                         self.db.execute("DELETE FROM reservation WHERE txn_id=?", (txn_id,))))

    # ---------------------------------------------------------------- anchoring (D-SL-14/15/16) + recovery (D-TX-4)
    def _reconcile(self, reason, before_proj, candidates=()):
        self.bump(f"reconcile_{reason}")
        self.tx(lambda: (self.set_rt("reconcile", 1), self.set_rt("reconcile_reason", reason),
                         self.set_rt("reconcile_candidates", ",".join(sorted(set(candidates))))))
        assert self.projection() == before_proj, "I6 violated: projection changed while entering RECONCILE"

    def _pending(self):
        return {r[0]: r[1:] for r in self.db.execute(
            "SELECT txn_id, prev_txn, p_prepare, apply_status FROM txn WHERE state='PREPARED'").fetchall()}

    def hypotheses(self):
        """Every explanation of where the current world came from (no session token). Returns a list of
        (label, state, candidates): state is a key 'H:<head|EMPTY>' / 'R:<txn>' or None when unknown."""
        g = self.gta
        P, W = g.stat_p(), tuple(g.wallets)
        head = self.head() or EMPTY
        hyps = []
        # LIVE: the world LSAX last ran in, reached without any load (e.g. character switched while LSAX was down).
        # Excluded only by a new process or by play-time lower than LSAX's own last live observation.
        if self.rt("proc") == g.proc and P >= (self.rt("p_last") or 0):
            pend = self._pending()
            if not pend or all(st == "NOT_STARTED" for _, _, st in pend.values()):
                hyps.append(("LIVE", "H:" + head, ["H:" + head]))
            else:
                ((t, (prev, _, st)),) = pend.items()
                if st == "APPLIED" and (prev or EMPTY) == head:
                    hyps.append(("LIVE", "R:" + t, ["R:" + t]))
                else:
                    hyps.append(("LIVE", None, ["H:" + head, "R:" + t]))
        # NEW_GAME: excluded only by play-time above the new-game bound (A-SL-13).
        if P <= NEWGAME_P_MAX:
            hyps.append(("NEW_GAME", "H:" + EMPTY, ["H:" + EMPTY]))
        # FILE: every present slot file (A-SL-8).
        for slot, sha, status in self.db.execute("SELECT slot, sha, status FROM slot_state ORDER BY slot").fetchall():
            if status == "UNTRUSTED":
                hyps.append((f"UNTRUSTED:{slot}", None, []))       # content unknown: never excludable
                continue
            kind, h, p_lo, p_hi, w0, w1, w2 = self.db.execute(
                "SELECT kind, head_txn, p_lo, p_hi, w0, w1, w2 FROM save_ledger WHERE sha=?", (sha,)).fetchone()
            if p_lo is not None and not (p_lo <= P <= p_hi):
                continue                                          # excluded: play-time mismatch
            if w0 is not None and (w0, w1, w2) != W:
                continue                                          # excluded: wallet mismatch
            label = "PREINSTALL" if kind == "PRE_INSTALL" else "FILE"
            hyps.append((f"{label}:{slot}", "H:" + (h or EMPTY), ["H:" + (h or EMPTY)]))
        return hyps

    def anchor(self):
        g = self.gta
        before_proj = self.projection()
        if self.rt("reconcile"):
            # stays refused until an explicit player resolution; restarts cannot clear it
            self.bump("reconcile_persisted")
            return
        pending = self._pending()
        token = self.rt("session_token")

        if g.ped_token is not None and g.ped_token == token:
            # (b) same live session proven: resolve the pending transaction from LSAX's own evidence (D-TX-4)
            head = self.head()
            for txn_id, (prev, p_prep, status) in pending.items():
                if status == "APPLIED" and prev == head:
                    self.tx(lambda: self._commit(txn_id, self.rt("active"), p_prep))
                    self.bump("roll_forward_on_own_evidence")
                elif status == "NOT_STARTED":
                    self._abort(txn_id)
                    self.bump("abort_on_own_evidence")
                else:                          # APPLYING (unclean stop / crash inside the apply) -> unknown
                    return self._reconcile("PENDING_UNKNOWN", before_proj,
                                           ["H:" + (head or EMPTY), "R:" + txn_id])
            anchored_head = self.head()
            self.bump("anchored_continuation")
        else:
            missed = self.rt("missed_start")
            if missed is not None and missed == g.proc:
                # a script-domain start in this process was missed: the world may descend from an unseen load
                return self._reconcile("MISSED_START", before_proj, [])
            hyps = self.hypotheses()
            cands = [c for _, _, cs in hyps for c in cs]
            if any(st is None for _, st, _ in hyps):
                reason = "UNTRUSTED_PRESENT" if any(l.startswith("UNTRUSTED") for l, st, _ in hyps if st is None) \
                    else "PENDING_UNKNOWN"
                return self._reconcile(reason, before_proj, cands)
            if not any(l.startswith(("FILE", "PREINSTALL")) for l, _, _ in hyps):
                return self._reconcile("SESSION_UNPROVEN" if any(l == "LIVE" for l, _, _ in hyps) else "NO_MATCH",
                                       before_proj, cands)
            states = {st for _, st, _ in hyps}
            if len(states) != 1:
                self.bump("ambiguous_by:" + "+".join(sorted({l.split(":")[0] for l, _, _ in hyps})))
                return self._reconcile("AMBIGUOUS", before_proj, cands)
            (state,) = states
            anchored_head = None if state == "H:" + EMPTY else state[2:]
            for txn_id in pending:             # the accepted world is a save file's world: every TRUSTED save
                self._abort(txn_id)            # predates any unrecorded apply (D-TX-5); LIVE agreed => NOT_STARTED
                self.bump("abort_slot_anchored")
            self.bump("anchored_slot" if not any(l == "LIVE" for l, _, _ in hyps) else "anchored_slot_live_agrees")
        self._fork(anchored_head, "ANCHOR")

    def _fork(self, parent_txn, reason):
        g = self.gta

        def fork():
            self.db.execute("INSERT INTO timeline(parent_txn, fork_p, reason) VALUES(?,?,?)", (parent_txn, g.stat_p(), reason))
            self.set_rt("active", self.q1("SELECT MAX(id) FROM timeline"))
        self.tx(fork)
        self._started()

    # ---------------------------------------------------------------- explicit player resolution (§4.6)
    def resolve(self, choice):
        """Player-chosen exit from RECONCILE_REQUIRED: a listed candidate ('H:<head|EMPTY>' or 'R:<txn>') or
        'NEW_CAMPAIGN'. Never automatic. Files changed during RECONCILE are UNTRUSTED (their lineage is unknown)."""
        assert self.rt("reconcile")
        cands = (self.rt("reconcile_candidates") or "").split(",")
        assert choice == "NEW_CAMPAIGN" or choice in cands, "resolution must pick a listed candidate"
        self.gta.save_events.clear()
        self._scan_unobserved("DURING_RECONCILE")
        pending = self._pending()
        parent = None
        if choice.startswith("R:"):
            t = choice[2:]
            self.tx(lambda: self._commit(t, self.rt("active"), pending[t][1]))
            parent = t
        elif choice.startswith("H:"):
            parent = None if choice == "H:" + EMPTY else choice[2:]
        for t in pending:
            if not choice == "R:" + t:
                self._abort(t)
        self.tx(lambda: (self.set_rt("reconcile", 0), self.set_rt("reconcile_reason", ""),
                         self.set_rt("reconcile_candidates", "")))
        self._fork(parent, "NEW_CAMPAIGN" if choice == "NEW_CAMPAIGN" else "RESOLVED")
        self.bump("resolved_" + ("new_campaign" if choice == "NEW_CAMPAIGN" else "candidate"))


def truthful_resolution(lx, g):
    """The player (who knows what they loaded) picks the true candidate when it is listed, else starts a new
    campaign (existing LSAX effects in the world become foreign: UNKNOWN provenance, D-PROV-1)."""
    truth_head = g.applied[-1] if g.applied else EMPTY
    cands = (lx.rt("reconcile_candidates") or "").split(",")
    pend = lx._pending()
    for c in ("R:" + truth_head, "H:" + truth_head):
        if c in cands and (c.startswith("H:") or truth_head in pend):
            lx.resolve(c)
            return c
    lx.resolve("NEW_CAMPAIGN")
    g.applied, g.garage = [], set()
    return "NEW_CAMPAIGN"


# ======================================================================================= random episode driver
ADVERSARIAL = [("BUY", 26), ("SELL", 18), ("EXT", 12), ("EXT_COLLIDE", 4), ("SAVE", 12), ("SAVE_THEN_EXT", 2), ("LOAD", 9),
               ("DUP", 4), ("DOUBLE", 3), ("CRASH", 8), ("SWITCH", 2), ("COPY_FOREIGN", 2), ("RESTORE_COPY", 2),
               ("NEW_GAME", 1)]
REALISTIC = [("BUY", 25), ("SELL", 20), ("EXT", 34), ("SAVE", 10), ("LOAD", 2), ("DUP", 4), ("DOUBLE", 3), ("CRASH", 1), ("SWITCH", 1)]
OFFLINE_OPS = [("EXT", 3), ("EXT_COLLIDE", 2), ("SAVE", 2), ("COPY_FOREIGN", 1), ("RESTORE_COPY", 1), ("LOAD", 2),
               ("NEW_GAME", 1), ("SWITCH", 1), ("RESTART", 3), ("GAMECRASH", 1)]
CRASH_POINTS = [("C0", 1), ("C1", 1), ("CA", 1), ("CB", 1), ("C2", 1), ("C3", 1)]


def episode(seed, gran, ops=160, mix=ADVERSARIAL, preinstall=True):
    rng = SplitMix64(seed)
    g = Gta(gran)
    if not rng.chance_bp(1250):                          # LSAX installed mid-campaign (1/8: installed on a new game)
        g.advance(rng.range_incl(NEWGAME_P_MAX + 1, 36_000_000))
    if preinstall:                                       # saves that exist before LSAX is installed
        for s in range(rng.below(3)):
            g.advance(rng.range_incl(1000, 50_000))
            g.save(s + 2)
        g.save_events.clear()
        g.advance(rng.range_incl(1000, 90_000))
    stats, fails = {}, []
    path = os.path.join(tempfile.mkdtemp(prefix="lsaxsim2"), "lsax.db")
    lx, up = Lsax(path, g, stats), True
    nxt, bought, history, pending_hint = 0, [], [], []

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

    def ext_cash(collide):
        w = rng.below(3)
        if collide:                                      # adversarial: land exactly on a pending txn's before/after
            row = lx.db.execute("SELECT wallet_slot, cash_before, cash_after FROM txn WHERE state='PREPARED'").fetchone() if up else None
            if row is None and not up:
                row = pending_hint[0] if pending_hint else None
            if row:
                g.wallets[row[0]] = row[1 + rng.below(2)]
                return
        g.wallets[w] = max(0, g.wallets[w] + rng.range_incl(-20, 40) * 500)

    def load_or_new(op):
        if op == "NEW_GAME" or not g.slots:
            g.new_game()
        elif mix is REALISTIC and rng.chance_bp(8000):   # players mostly (re)load their most recent save
            g.load(max(g.slots, key=lambda s: g.slots[s]["mtime"]))
        else:
            g.load(sorted(g.slots)[rng.below(len(g.slots))])

    for i in range(ops):
        if up and lx.rt("reconcile"):
            if lx.submit("BUY", "vX", 1, "kX", "tX") != "REFUSED_RECONCILE":
                fails.append("I6 market op accepted during RECONCILE")
            before = sorted(lx.projection())
            if rng.chance_bp(3000):                      # a restart must not clear RECONCILE_REQUIRED
                lx.close(clean=True)
                restart(f"reconcile-restart@{i}")
                if not lx.rt("reconcile") or sorted(lx.projection()) != before:
                    fails.append(f"I6 RECONCILE cleared or projection changed by restart @{i}")
            else:
                truthful_resolution(lx, g)
                check(f"resolved@{i}")
            continue
        g.advance(rng.range_incl(1, 1500))
        if not up:                                      # LSAX offline: the game keeps running without LSAX
            op = rng.pick_weighted(OFFLINE_OPS)
            if op in ("EXT", "EXT_COLLIDE"):
                ext_cash(op == "EXT_COLLIDE")
            elif op == "SAVE":
                g.save(rng.below(4))
            elif op == "COPY_FOREIGN":
                g.copy_foreign(rng.below(4), g.stat_p() + rng.range_incl(-3000, 3000),
                               (rng.range_incl(0, 400) * 500, g.wallets[1], g.wallets[2]))
            elif op == "RESTORE_COPY" and history:
                g.restore_copy(rng.below(4), history[rng.below(len(history))])
            elif op in ("LOAD", "NEW_GAME"):
                load_or_new(op)                          # a new script domain starts (A-SL-1) ...
                if rng.chance_bp(7500):
                    restart(f"offline-{op}@{i}")        # ... and LSAX starts normally
                else:
                    mark_missed_start(path, g)           # ... but LSAX's start fails (A-SL-9 marker)
                    stats["missed_start_injected"] = stats.get("missed_start_injected", 0) + 1
            elif op == "SWITCH":
                g.switch_char(rng.below(3))
            elif op == "RESTART":                        # console Reload in the same session
                restart(f"restart@{i}")
            elif op == "GAMECRASH":
                g.process_crash()
                load_or_new("LOAD")
                restart(f"gamecrash-offline@{i}")
            continue
        lx.tick()
        op = rng.pick_weighted(mix)
        crash_at = None
        if op == "CRASH":
            crash_at = rng.pick_weighted(CRASH_POINTS)
            op = "BUY" if rng.chance_bp(5000) else "SELL"
        try:
            if op == "BUY":
                nxt += 1
                if lx.submit("BUY", f"v{nxt}", rng.range_incl(5, 60) * 1000, f"k{nxt}", f"t{nxt}", crash_at) == "COMMITTED":
                    bought.append((f"v{nxt}", f"k{nxt}"))
            elif op == "SELL":
                owned = sorted(lx.projection())
                if owned:
                    nxt += 1
                    lx.submit("SELL", owned[rng.below(len(owned))], rng.range_incl(3, 50) * 1000, f"k{nxt}", f"t{nxt}", crash_at)
            elif op in ("EXT", "EXT_COLLIDE"):
                ext_cash(op == "EXT_COLLIDE")
            elif op in ("SAVE", "SAVE_THEN_EXT"):
                slot = rng.below(4)
                g.save(slot)
                history.append(dict(g.slots[slot]))
                history[:] = history[-12:]
                if op == "SAVE_THEN_EXT":               # another mod pays out between the save and LSAX's poll
                    ext_cash(False)
                g.advance(rng.range_incl(0, 400))
                lx.poll_slots()
            elif op == "COPY_FOREIGN":
                g.copy_foreign(rng.below(4), g.stat_p() + rng.range_incl(-3000, 3000),
                               (rng.range_incl(0, 400) * 500, g.wallets[1], g.wallets[2]))
                lx.poll_slots()
            elif op == "RESTORE_COPY" and history:
                g.restore_copy(rng.below(4), history[rng.below(len(history))])
                lx.poll_slots()
            elif op == "SWITCH":
                g.switch_char(rng.below(3))
            elif op in ("LOAD", "NEW_GAME") and (g.slots or op == "NEW_GAME"):
                load_or_new(op)
                lx.close(clean=True)                     # old instance's Aborted runs after the new session started
                restart(f"{op.lower()}@{i}")
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
            row = lx.db.execute("SELECT wallet_slot, cash_before, cash_after FROM txn WHERE state='PREPARED'").fetchone()
            pending_hint[:] = [row] if row else []
            mode = rng.pick_weighted([("SCRIPT_RELOAD", 2), ("UNCLEAN_SAME_PROCESS", 1), ("GAME_CRASH", 2), ("OFFLINE", 1)])
            lx.close(clean=mode in ("SCRIPT_RELOAD", "OFFLINE"))
            if mode == "OFFLINE":
                up = False
                continue
            if mode == "GAME_CRASH":
                g.process_crash()
                load_or_new("LOAD")
            restart(f"crash-{c}-{mode}@{i}")
            continue
        check(f"op{i}")
    if up:
        lx.close(clean=True)
    return stats, fails


REQUIRED_PATHS = ["roll_forward_on_own_evidence", "abort_on_own_evidence", "anchored_continuation", "anchored_slot",
                  "abort_slot_anchored", "reconcile_PENDING_UNKNOWN", "reconcile_UNTRUSTED_PRESENT", "reconcile_NO_MATCH",
                  "reconcile_AMBIGUOUS", "reconcile_MISSED_START", "reconcile_SESSION_UNPROVEN", "reconcile_persisted",
                  "resolved_candidate", "resolved_new_campaign", "ledger_wallets_unknown"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=60, help="episodes per (mix, granularity); audit-grade run: 200")
    args = ap.parse_args()
    t0 = time.time()
    fails, n, grand = [], args.episodes, {}
    for mix_name, mix, ops in (("ADVERSARIAL", ADVERSARIAL, 160), ("REALISTIC", REALISTIC, 400)):
        total = {}
        for gran in (1, 1000):
            for e in range(n):
                st, f = episode(derive_seed("journal-draft2", mix_name, gran, e), gran, ops=ops, mix=mix)
                for k, v in st.items():
                    total[f"G={gran}ms {k}"] = total.get(f"G={gran}ms {k}", 0) + v
                    grand[k] = grand.get(k, 0) + v
                fails += [f"{mix_name} G={gran} ep{e}: {x}" for x in f]
        print(f"\n### {mix_name}: {2 * n} episodes ({n} per stat granularity), {ops} operations each\n")
        print("| Counter | Value |\n|---|---:|")
        for k in sorted(total):
            print(f"| {k} | {total[k]} |")
        for gran in (1, 1000):
            anch = sum(v for k, v in total.items() if k.startswith(f"G={gran}ms anchored") and "first_run" not in k)
            rec = sum(v for k, v in total.items() if k.startswith(f"G={gran}ms reconcile_") and "persisted" not in k)
            print(f"\n{mix_name} G={gran}ms: automatic anchorings (excl. first run)={anch}, RECONCILE_REQUIRED entries={rec} "
                  f"({100 * rec / max(anch + rec, 1):.2f}% of session starts)")
            # Non-vacuity tripwire (not an acceptance criterion): the model must still anchor sessions automatically.
            if anch < 3 * n:
                fails.append(f"NON-VACUITY {mix_name} G={gran}: automatic anchorings={anch} < {3 * n}")
    missing = [k for k in REQUIRED_PATHS if not grand.get(k)]
    if missing:
        fails.append(f"COVERAGE: paths never exercised: {missing}")
    print(f"\nSafety invariant failures (I0 I1 I2 I3 I6) + tripwires: {len(fails)}")
    for f in fails[:15]:
        print("  -", f)
    print(f"Run time: {time.time() - t0:.1f} s")
    print("RESULT:", "PASS" if not fails else "FAIL")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
