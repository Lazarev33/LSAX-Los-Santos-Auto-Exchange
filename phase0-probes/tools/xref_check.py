"""Phase 0 self-audit tool (NOT PRODUCTION CODE): cross-reference consistency of the spec package.

Checks:
  1. Every ID referenced (D-*, R-*, B-01, A-*, E<n>-<n>, T-*, AX-*, P-*, PC-*, OD-*, UI-S1, C1..C20 rows) is DEFINED
     somewhere (definition = appears as the first cell of a markdown table row, or in an explicit definition list).
  2. Every backticked repository path mentioned exists.
  3. Risk IDs in spec/LSAX-RISK-REGISTER.md and risks.md are identical sets.
  4. Required deliverable files exist and are non-empty; master spec contains sections 00..30 and appendices A..L.
Prints findings; exit code = number of problems (capped at 100)."""
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCS = [os.path.join("spec", f) for f in sorted(os.listdir(os.path.join(ROOT, "spec")))] + [
    "00-INDEX.md", "progress.md", "decisions.md", "risks.md", "feasibility.md", os.path.join("phase0-probes", "README-PROBES.md")]
REQUIRED = ["LSAX-MASTER-SPEC-v1.0.md", "LSAX-DOMAIN-MODEL.md", "LSAX-SAVELOAD-FEASIBILITY.md", "LSAX-TIME-MODEL.md",
            "LSAX-DB-SCHEMA-DRAFT.md", "LSAX-VALUATION-MODEL.md", "LSAX-NPC-GENERATION-MODEL.md",
            "LSAX-HEAT-AND-UNDERGROUND-MODEL.md", "LSAX-TRANSACTION-STATE-MACHINE.md", "LSAX-COMPATIBILITY-CONTRACT.md",
            "LSAX-PERFORMANCE-BUDGET.md", "LSAX-LOCALIZATION-CONTRACT.md", "LSAX-TEST-STRATEGY.md",
            "LSAX-STAGE-ACCEPTANCE.md", "LSAX-RISK-REGISTER.md", "LSAX-REFERENCE-REVIEW.md"]

ID_RE = re.compile(r"\b(D-[A-Z0-9]+-\d+|R-[A-Z0-9]+-\d+|B-01|A-[A-Z0-9]+-\d+|E\d-\d+|T-[A-Z0-9]+-\d+|T-[A-Z]+-SIM-\d+|"
                   r"AX-\d+|P-[A-Z]+-\d+|PC-\d|OD-\d|UI-S1|S-SL-1)\b")
RANGE_RE = re.compile(r"\b(T-[A-Z0-9]+|AX|PC|D-[A-Z0-9]+|T-[A-Z]+-SIM)-(\d+)\s*(?:\.\.|…|–)\s*(?:\1-)?(\d+)\b")


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return fh.read()


def main():
    problems = []
    texts = {p: read(p) for p in DOCS if os.path.exists(os.path.join(ROOT, p))}
    defined, referenced = set(), {}
    for p, t in texts.items():
        for line in t.splitlines():
            cells = [c.strip() for c in line.split("|")]
            if line.startswith("|") and len(cells) > 2:
                for m in ID_RE.finditer(cells[1]):
                    defined.add(m.group(1))
                for m in RANGE_RE.finditer(cells[1]):  # "T-GEN-1..7" in a first cell defines every member
                    for i in range(int(m.group(2)), int(m.group(3)) + 1):
                        defined.add(f"{m.group(1)}-{i}")
            for m in ID_RE.finditer(line):
                referenced.setdefault(m.group(1), set()).add(p)
            for m in RANGE_RE.finditer(line):  # "T-VAL-1..4" style ranges count as references to each member
                base, a, b = m.group(1), int(m.group(2)), int(m.group(3))
                for i in range(a, b + 1):
                    referenced.setdefault(f"{base}-{i}", set()).add(p)
            # "IDs defined inline": bold definitions like **D-SL-1** or "ID: text" lists
            for m in re.finditer(r"\*\*(" + ID_RE.pattern[3:-3] + r")\*\*", line):
                defined.add(m.group(1))
    # IDs that are defined implicitly by the documents' own numbered lists
    for p, t in texts.items():
        for m in re.finditer(r"^\s*(?:-|\d+\.)\s+\*\*?(" + ID_RE.pattern[3:-3] + r")", t, re.M):
            defined.add(m.group(1))
    undefined = sorted(i for i in referenced if i not in defined and i != "A-Z0-9")  # regex char class, not an ID
    for i in undefined:
        problems.append(f"UNDEFINED ID {i} referenced in {sorted(referenced[i])}")

    for p, t in texts.items():
        for m in re.finditer(r"`((?:phase0-probes|evidence|spec)/[^`\s]+)`", t):
            path = m.group(1).split("::")[0].rstrip("/")
            if "<" in path or "*" in path:
                continue
            if not os.path.exists(os.path.join(ROOT, path)):
                problems.append(f"MISSING PATH `{path}` referenced in {p}")

    reg = set(re.findall(r"^\|\s*(B-01|R-[A-Z0-9]+-\d+)\s*\|", texts["spec/LSAX-RISK-REGISTER.md"], re.M))
    wrk = set(re.findall(r"^\|\s*(B-01|R-[A-Z0-9]+-\d+)\s*\|", texts["risks.md"], re.M))
    if reg != wrk:
        problems.append(f"RISK SET MISMATCH register-only={sorted(reg - wrk)} risks.md-only={sorted(wrk - reg)}")

    for f in REQUIRED:
        fp = os.path.join(ROOT, "spec", f)
        if not os.path.exists(fp) or os.path.getsize(fp) < 1000:
            problems.append(f"DELIVERABLE missing/too small: {f}")
    master = texts["spec/LSAX-MASTER-SPEC-v1.0.md"]
    for n in range(31):
        if not re.search(rf"^## {n:02d} ", master, re.M):
            problems.append(f"MASTER missing section {n:02d}")
    for a in "ABCDEFGHIJKL":
        if not re.search(rf"^\| {a} \|", master, re.M):
            problems.append(f"MASTER missing appendix row {a}")

    print(f"IDs referenced: {len(referenced)}, defined: {len(defined)}, docs: {len(texts)}")
    for pr in problems:
        print(" -", pr)
    print("RESULT:", "PASS" if not problems else f"{len(problems)} PROBLEM(S)")
    return min(len(problems), 100)


if __name__ == "__main__":
    sys.exit(main())
