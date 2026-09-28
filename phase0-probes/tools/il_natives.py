"""Disposable read-only IL scanner (Phase 0 reference review). NOT LSAX code.
For each MethodDef body, scans IL for ldc.i8 (0x21) / ldc.i4 (0x20) operands and reports
those matching a native hash in alloc8or natives.json. Prints per-method native usage."""
import json
import struct
import sys
import dnfile

natives = {}
d = json.load(open(sys.argv[1]))
for ns, entries in d.items():
    for h, info in entries.items():
        natives[int(h, 16)] = f"{ns}::{info.get('name')}"


def method_bodies(pe):
    md = pe.net.mdtables
    for t in md.TypeDef or []:
        for mref in t.MethodList or []:
            m = mref.row
            rva = m.Rva
            if not rva:
                continue
            off = pe.get_offset_from_rva(rva)
            data = pe.__data__
            b0 = data[off]
            if b0 & 0x3 == 0x2:  # tiny
                size = b0 >> 2
                code = data[off + 1: off + 1 + size]
            else:
                flags_size = struct.unpack_from("<H", data, off)[0]
                hdr = (flags_size >> 12) * 4
                size = struct.unpack_from("<I", data, off + 4)[0]
                code = data[off + hdr: off + hdr + size]
            yield f"{t.TypeName}.{m.Name}", bytes(code)


def scan(path):
    pe = dnfile.dnPE(path)
    print("=" * 60, path)
    for name, code in method_bodies(pe):
        hits = []
        for i in range(len(code) - 8):
            if code[i] == 0x21:
                v = struct.unpack_from("<Q", code, i + 1)[0]
                if v in natives:
                    hits.append(natives[v])
            if code[i] == 0x20:
                v = struct.unpack_from("<I", code, i + 1)[0]
                if v in natives and v > 0xFFFF:
                    hits.append(natives[v] + " (i4)")
        if hits:
            print(f"  {name}:")
            for h in dict.fromkeys(hits):
                print(f"     {h}")


for p in sys.argv[2:]:
    scan(p)
