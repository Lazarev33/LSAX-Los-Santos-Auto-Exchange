"""Disposable Phase 0 evidence tool. NOT LSAX code.
Checks that named natives exist in alloc8or natives.json and in SHVDN's GTA.Native.Hash enum,
and prints native DB comments (truncated) for the save/load/session-related ones."""
import json
import re
import sys

db = json.load(open(sys.argv[1]))
hash_src = open(sys.argv[2], encoding="utf-8", errors="replace").read()
enum_names = set(re.findall(r"^\s*([A-Z0-9_]+)\s*=\s*0x[0-9A-Fa-f]+", hash_src, re.M))

by_name = {}
for ns, entries in db.items():
    for h, info in entries.items():
        by_name[info["name"]] = (ns, h, info)

WANT = [l.strip() for l in open(sys.argv[3]) if l.strip() and not l.startswith("#")]
verbose = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else set()
for n in WANT:
    if n in by_name:
        ns, h, info = by_name[n]
        params = ", ".join(f"{p['type']} {p['name']}" for p in info.get("params", []))
        print(f"DB  {'ENUM' if n in enum_names else '----'} {ns}::{n} {h} -> {info.get('return_type')}({params})")
        if n in verbose and info.get("comment"):
            c = info["comment"].replace("\n", " ")
            print(f"      comment: {c[:400]}")
    else:
        print(f"MISSING-IN-DB {'ENUM' if n in enum_names else '----'} {n}")
