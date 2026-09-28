"""Shared harness for the Phase 0 correction regressions (disposable test code, NOT production LSAX code).

Every regression module exposes main() -> exit code and prints one line per check group plus a summary line
"<suite>: <passed>/<total> PASS". Deterministic: no wall clock, no randomness except seeded SplitMix64.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(os.path.dirname(HERE), "sim")
if SIM not in sys.path:
    sys.path.insert(0, SIM)


class Suite:
    def __init__(self, name):
        self.name = name
        self.results = []            # (case, ok, detail)

    def check(self, case, cond, detail=""):
        self.results.append((case, bool(cond), detail))
        return bool(cond)

    def report(self, verbose=True):
        fails = [r for r in self.results if not r[1]]
        if verbose:
            for case, ok, detail in self.results:
                print(f"{'PASS' if ok else 'FAIL'}  {case}" + (f"  -- {detail}" if detail and not ok else ""))
        else:
            for case, ok, detail in fails:
                print(f"FAIL  {case}  -- {detail}")
        print(f"{self.name}: {len(self.results) - len(fails)}/{len(self.results)} PASS")
        return 0 if not fails else 1


def tmpdb(prefix="lsaxreg"):
    return os.path.join(tempfile.mkdtemp(prefix=prefix), "lsax.db")
