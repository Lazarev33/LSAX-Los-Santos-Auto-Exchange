"""Audit reproduction imported as a regression (findings P0-02 case A and P0-03 case B).

audit/repro_findings.py is the auditor's script, byte-identical to the audit bundle
(SHA-256 ad8fe27a452b1c501c497a55aebe1f3ca8ebdde293f7600b4007ee507696755e, listed in the bundle's SHA256SUMS.txt).
It is executed UNCHANGED against the DRAFT2 reference model: its hard-coded sys.path entry does not exist here, so
the import resolves to phase0-probes/sim/journal_timeline_ref.py placed on sys.path by regress_common.
audit/REPRO-OUTPUT-DRAFT1.txt is the auditor's output against DRAFT1 (the defect being corrected).

Pass rule (per the correction brief): each case must NOT silently commit unsafe history, i.e. it must either enter
RECONCILE_REQUIRED or end with LSAX state equal to the effects present in the game world.
"""
import contextlib
import hashlib
import io
import os
import sys

from regress_common import HERE, Suite

AUDIT_SHA = "ad8fe27a452b1c501c497a55aebe1f3ca8ebdde293f7600b4007ee507696755e"


def run():
    s = Suite("AUDIT-REPRO (P0-02 A, P0-03 B)")
    path = os.path.join(HERE, "audit", "repro_findings.py")
    src = open(path, "rb").read()
    s.check("audit script byte-identical to bundle", hashlib.sha256(src).hexdigest() == AUDIT_SHA)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(src, path, "exec"), {"__name__": "__audit_repro__"})
    out = dict()
    for line in buf.getvalue().splitlines():
        parts = line.split(" ", 2)
        if len(parts) == 3:
            out[(parts[0], parts[1])] = parts[2]
    print("---- auditor script output against DRAFT2 ----")
    print(buf.getvalue().rstrip())
    print("----------------------------------------------")
    for case in ("A", "B"):
        rec = out.get((case, "reconcile")) == "1"
        match = out.get((case, "safety_match")) == "True"
        s.check(f"case {case}: RECONCILE_REQUIRED or safety_match (no silent unsafe history)", rec or match,
                f"reconcile={out.get((case, 'reconcile'))} safety_match={out.get((case, 'safety_match'))}")
    s.check("case A: no roll-forward on wallet equality", "roll_forward" not in out.get(("A", "stats"), ""),
            out.get(("A", "stats")))
    s.check("case A: t1 not on the active path", out.get(("A", "active_ids")) == "[]", out.get(("A", "active_ids")))
    s.check("case A: v1 not in projection", out.get(("A", "projection")) == "[]", out.get(("A", "projection")))
    s.check("case B: no automatic slot anchoring onto the foreign save", "anchored_slot" not in out.get(("B", "stats"), ""),
            out.get(("B", "stats")))
    return s


def main():
    return run().report()


if __name__ == "__main__":
    sys.exit(main())
