"""P0-04 regression — no Stage 1a / partial-Stage-1 carve-out anywhere in the specification set (D-GATE-1).

Static scan of every normative document shipped in the package (spec/*.md, state files, probe README). Fails on:
  * any token S1a / S1b (the withdrawn split);
  * "Stage 1a" / "Stage 1b" / "Stage-1a" except inside an explicit negation ("no Stage 1a", "no Stage 1a/1b");
  * phrases that historically granted a carve-out ("persistence-independent parts", "may start once the spec is
    approved with", "blocks the next stage", "before the stage that depends on it", "authorise Stage").
Also checks that the gate text is present in STAGE-ACCEPTANCE, MASTER §28/App. L and RISK-REGISTER.
progress.md / decisions.md are history logs and are scanned only for the gate statement, not for the tokens.
"""
import os
import re
import sys

from regress_common import HERE, Suite

ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DOCS = [os.path.join("spec", f) for f in sorted(os.listdir(os.path.join(ROOT, "spec"))) if f.endswith(".md")] + \
       ["risks.md", "feasibility.md", "00-INDEX.md", os.path.join("phase0-probes", "README-PROBES.md")]
TOKEN = re.compile(r"\bS1[ab]\b")
STAGE1A = re.compile(r"Stage[ -]1[ab]\b", re.I)
NEGATION = re.compile(r"\bno Stage[ -]1a", re.I)
CARVE = [re.compile(p, re.I) for p in (r"persistence-independent parts", r"may start once the spec is approved with",
                                       r"blocks the next stage", r"before the stage that depends on it",
                                       r"authori[sz]e \**Stage")]
GATE = {os.path.join("spec", "LSAX-STAGE-ACCEPTANCE.md"): "No stage — and no part of any stage — may start before SPEC_APPROVED",
        os.path.join("spec", "LSAX-MASTER-SPEC-v1.0.md"): "No stage — and no part of Stage 1 — starts before SPEC_APPROVED",
        os.path.join("spec", "LSAX-RISK-REGISTER.md"): "every open P0 and P1 blocks SPEC_APPROVED",
        "decisions.md": "D-GATE-1"}


def run():
    s = Suite("P0-04 no Stage-1a carve-out")
    for rel in DOCS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        for n, line in enumerate(open(path, encoding="utf-8"), 1):
            if TOKEN.search(line):
                s.check(f"{rel}:{n} no S1a/S1b token", False, line.strip()[:120])
            if STAGE1A.search(line) and not NEGATION.search(line):
                s.check(f"{rel}:{n} no Stage 1a/1b allowance", False, line.strip()[:120])
            for c in CARVE:
                if c.search(line):
                    s.check(f"{rel}:{n} no carve-out phrase '{c.pattern}'", False, line.strip()[:120])
        s.check(f"{rel}: scanned", True)
    for rel, text in GATE.items():
        body = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        s.check(f"{rel}: gate statement present", text in body, text)
    return s


def main():
    return run().report(verbose=False)


if __name__ == "__main__":
    sys.exit(main())
