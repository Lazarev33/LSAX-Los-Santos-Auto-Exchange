"""LSAX Phase 0 — system transaction / journal protocol reference model, DRAFT2 (NOT PRODUCTION CODE).

Normative mirror of LSAX-TRANSACTION-STATE-MACHINE.md §3a (decision D-JRN-1, audit finding P1-04).

System transactions (kinds SYS_MT_CHECKPOINT, SYS_ODO_CHECKPOINT, SYS_MARKET_STEP, SYS_HEAT_DECAY, SYS_HEAT_EVENT,
SYS_LISTING_EXPIRY) use the SAME path as business transactions — txn row -> commit_log row (same per-timeline seq)
-> journal_event rows — in ONE SQLite transaction (no PREPARE: no game-side effect). Identity: random txn_id;
deterministic idempotency key per family; duplicate suppression by the active-path idempotency set (projection table
applied_idem, PRIMARY KEY) inside the same SQLite transaction. Payloads carry ABSOLUTE resulting values, so replay
and retry are idempotent. Coalescing: only SYS_MT_CHECKPOINT and SYS_ODO_CHECKPOINT (absolute, superseding) may be
coalesced while queued; every other family is never coalesced. Ordering: a system transaction is never committed
while a business transaction is PREPARED (single-tick core), and commits are serialised by the single DB writer.
"""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile

from lsax_ref_math import SplitMix64, derive_seed

SYS_KINDS = ("SYS_MT_CHECKPOINT", "SYS_ODO_CHECKPOINT", "SYS_MARKET_STEP", "SYS_HEAT_DECAY", "SYS_HEAT_EVENT",
             "SYS_LISTING_EXPIRY")
COALESCIBLE = {"SYS_MT_CHECKPOINT", "SYS_ODO_CHECKPOINT"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS timeline(id INTEGER PRIMARY KEY, parent_txn TEXT, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS txn(txn_id TEXT PRIMARY KEY, idem_key TEXT NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commit_log(timeline_id INTEGER NOT NULL, seq INTEGER NOT NULL, txn_id TEXT NOT NULL UNIQUE,
  idem_key TEXT NOT NULL, kind TEXT NOT NULL, PRIMARY KEY(timeline_id, seq));
CREATE TABLE IF NOT EXISTS journal_event(txn_id TEXT NOT NULL, ord INTEGER NOT NULL, type TEXT NOT NULL,
  payload_json TEXT NOT NULL, PRIMARY KEY(txn_id, ord));
CREATE TABLE IF NOT EXISTS runtime(k TEXT PRIMARY KEY, v);
CREATE TABLE IF NOT EXISTS applied_idem(idem_key TEXT PRIMARY KEY);          -- projection: active-path idem set
CREATE TABLE IF NOT EXISTS proj(k TEXT PRIMARY KEY, v TEXT NOT NULL);         -- projection: key -> canonical JSON
"""


class CrashBeforeCommit(Exception):
    pass


class LostAck(Exception):
    pass


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class Journal:
    def __init__(self, path, campaign_seed=42):
        self.dbpath, self.seed = path, campaign_seed
        new = not os.path.exists(path)
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.executescript(SCHEMA)
        self.n = 0
        self.pending_business = False
        self.queue = []
        if new:
            self.db.execute("INSERT INTO timeline VALUES(1,NULL,'ROOT')")
            self.db.execute("INSERT INTO runtime VALUES('active',1)")

    # ----------------------------------------------------------- path helpers
    def active(self):
        return self.db.execute("SELECT v FROM runtime WHERE k='active'").fetchone()[0]

    def path(self, t=None):
        t = self.active() if t is None else t
        parent = self.db.execute("SELECT parent_txn FROM timeline WHERE id=?", (t,)).fetchone()[0]
        prefix = []
        if parent is not None:
            ptl, pseq = self.db.execute("SELECT timeline_id, seq FROM commit_log WHERE txn_id=?", (parent,)).fetchone()
            prefix = [r for r in self.path(ptl) if not (r[0] == ptl and r[1] > pseq)]
        own = [(t,) + r for r in self.db.execute(
            "SELECT seq, txn_id, idem_key, kind FROM commit_log WHERE timeline_id=? ORDER BY seq", (t,))]
        return prefix + own

    def head(self):
        p = self.path()
        return p[-1][2] if p else None

    # ----------------------------------------------------------- projection
    def pget(self, k, default=None):
        r = self.db.execute("SELECT v FROM proj WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def _apply_event(self, etype, payload):
        """Absolute-value application: replaying an event twice yields the same projection."""
        if etype == "MtCheckpoint":
            self.db.execute("INSERT OR REPLACE INTO proj VALUES('mt', ?)", (canon(payload["state"]),))
        elif etype == "OdometerCheckpoint":
            self.db.execute("INSERT OR REPLACE INTO proj VALUES(?, ?)", ("odo:" + payload["vehicle"], canon(payload["odo_m"])))
        elif etype == "MarketStep":
            self.db.execute("INSERT OR REPLACE INTO proj VALUES('market', ?)",
                            (canon({"step": payload["step"], "demand": payload["demand"]}),))
            for vid in payload["generated"]:
                self.db.execute("INSERT OR REPLACE INTO proj VALUES(?, ?)", ("inv:" + vid, canon("LISTED")))
        elif etype == "HeatValue":
            self.db.execute("INSERT OR REPLACE INTO proj VALUES('heat', ?)", (canon(payload),))
        elif etype == "ListingExpired":
            self.db.execute("INSERT OR REPLACE INTO proj VALUES(?, ?)", ("inv:" + payload["listing"], canon("EXPIRED")))
        elif etype == "Business":
            self.db.execute("INSERT OR REPLACE INTO proj VALUES(?, ?)", ("biz:" + payload["id"], canon(payload["value"])))

    def projection(self):
        return {k: v for k, v in self.db.execute("SELECT k, v FROM proj ORDER BY k")}

    def rebuild(self):
        """Replay journal events of the active path in order into an empty projection."""
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("DELETE FROM proj")
        self.db.execute("DELETE FROM applied_idem")
        for _, _, txn_id, idem, _ in self.path():
            self.db.execute("INSERT INTO applied_idem VALUES(?)", (idem,))
            for etype, pj in self.db.execute("SELECT type, payload_json FROM journal_event WHERE txn_id=? ORDER BY ord", (txn_id,)).fetchall():
                self._apply_event(etype, json.loads(pj))
        self.db.execute("COMMIT")

    # ----------------------------------------------------------- the single commit path
    def commit(self, kind, idem, events, crash=None):
        """One SQLite transaction: dedupe on the active path, txn row, commit_log row, journal events, projection."""
        if kind in SYS_KINDS and self.pending_business:
            return "DEFERRED_BUSINESS_PREPARED"
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM applied_idem WHERE idem_key=?", (idem,)).fetchone():
                self.db.execute("ROLLBACK")
                return "DUPLICATE"
            self.n += 1
            txn_id = hashlib.sha256(f"{self.dbpath}|{self.n}|{idem}".encode()).hexdigest()[:26]
            t = self.active()
            seq = (self.db.execute("SELECT MAX(seq) FROM commit_log WHERE timeline_id=?", (t,)).fetchone()[0] or 0) + 1
            self.db.execute("INSERT INTO txn VALUES(?,?,?, 'COMMITTED')", (txn_id, idem, kind))
            self.db.execute("INSERT INTO commit_log VALUES(?,?,?,?,?)", (t, seq, txn_id, idem, kind))
            for ord_, (etype, payload) in enumerate(events):
                self.db.execute("INSERT INTO journal_event VALUES(?,?,?,?)", (txn_id, ord_, etype, canon(payload)))
                self._apply_event(etype, payload)
            self.db.execute("INSERT INTO applied_idem VALUES(?)", (idem,))
            if crash == "BEFORE_COMMIT":
                raise CrashBeforeCommit()
            self.db.execute("COMMIT")
        except CrashBeforeCommit:
            self.db.execute("ROLLBACK")
            raise
        if crash == "LOST_ACK":
            raise LostAck()
        return "COMMITTED"

    def fork(self, parent_txn):
        """Anchoring to an earlier state: new timeline + projection rebuilt for the new active path."""
        self.db.execute("INSERT INTO timeline(parent_txn, reason) VALUES(?, 'ANCHOR')", (parent_txn,))
        self.db.execute("UPDATE runtime SET v=(SELECT MAX(id) FROM timeline) WHERE k='active'")
        self.rebuild()

    # ----------------------------------------------------------- queue (coalescing)
    def enqueue(self, kind, idem, events, coalesce_key=None):
        if coalesce_key is not None:
            if kind not in COALESCIBLE:
                raise ValueError(f"{kind} is never coalesced")
            self.queue = [q for q in self.queue if q[3] != coalesce_key]
        self.queue.append((kind, idem, events, coalesce_key))

    def drain(self):
        out = [self.commit(k, i, e) for k, i, e, _ in self.queue]
        self.queue = []
        return out


# ------------------------------------------------------------------ deterministic system-event builders
def market_step(j, step):
    """SYS_MARKET_STEP for step index `step`: output depends only on (campaign_seed, step, path state)."""
    prev = j.pget("market", {"step": -1, "demand": 10_000})
    rng = SplitMix64(derive_seed("market", j.seed, step, prev["demand"]))
    demand = max(7_000, min(13_000, prev["demand"] + rng.range_incl(-200, 200)))
    gen = [f"npc-{step}-{k}" for k in range(rng.range_incl(1, 3))]
    return "SYS_MARKET_STEP", f"SYS_MKT|{j.seed}|{step}", [("MarketStep", {"step": step, "demand": demand, "generated": gen})]


def heat_decay(j, hour):
    prev = j.pget("heat", {"value": 500, "hour": -1})
    value = prev["value"] - (prev["value"] // 100 if prev["value"] > 0 else 0)
    return "SYS_HEAT_DECAY", f"SYS_HEATDECAY|{j.seed}|{hour}", [("HeatValue", {"value": value, "hour": hour})]


def heat_event(j, cause_kind, cause_id, mt_min, delta):
    prev = j.pget("heat", {"value": 500, "hour": -1})
    value = max(0, min(1000, prev["value"] + delta))
    return "SYS_HEAT_EVENT", f"SYS_HEAT|{cause_kind}|{cause_id}|{mt_min}", [("HeatValue", {"value": value, "hour": prev["hour"]})]


def listing_expiry(listing, version):
    return "SYS_LISTING_EXPIRY", f"SYS_EXPIRE|{listing}|{version}", [("ListingExpired", {"listing": listing, "version": version})]


def mt_checkpoint(session_token, seq, state):
    return "SYS_MT_CHECKPOINT", f"SYS_MT|{session_token}|{seq}", [("MtCheckpoint", {"state": state})]


def odo_checkpoint(vehicle, session_token, seq, odo_m):
    return "SYS_ODO_CHECKPOINT", f"SYS_ODO|{vehicle}|{session_token}|{seq}", [("OdometerCheckpoint", {"vehicle": vehicle, "odo_m": odo_m})]


def new_journal():
    return Journal(os.path.join(tempfile.mkdtemp(prefix="lsaxsys"), "lsax.db"))


def main():
    j = new_journal()
    for step in range(5):
        j.commit(*market_step(j, step))
    live = j.projection()
    j.rebuild()
    ok = j.projection() == live
    print("5 market steps; rebuild == live:", ok)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
