"""Disposable minimal IL disassembler for a few named methods (Phase 0 reference review). NOT LSAX code.
Only a subset of opcodes is decoded; unknown opcodes are printed as hex."""
import struct
import sys
import dnfile

ONE = {
    0x00: ("nop", 0), 0x02: ("ldarg.0", 0), 0x03: ("ldarg.1", 0), 0x04: ("ldarg.2", 0), 0x05: ("ldarg.3", 0),
    0x06: ("ldloc.0", 0), 0x07: ("ldloc.1", 0), 0x08: ("ldloc.2", 0), 0x09: ("ldloc.3", 0),
    0x0A: ("stloc.0", 0), 0x0B: ("stloc.1", 0), 0x0C: ("stloc.2", 0), 0x0D: ("stloc.3", 0),
    0x11: ("ldloc.s", 1), 0x13: ("stloc.s", 1), 0x14: ("ldnull", 0),
    0x16: ("ldc.i4.0", 0), 0x17: ("ldc.i4.1", 0), 0x18: ("ldc.i4.2", 0), 0x19: ("ldc.i4.3", 0),
    0x1A: ("ldc.i4.4", 0), 0x1F: ("ldc.i4.s", 1), 0x20: ("ldc.i4", 4), 0x21: ("ldc.i8", 8),
    0x22: ("ldc.r4", 4), 0x23: ("ldc.r8", 8), 0x25: ("dup", 0), 0x26: ("pop", 0),
    0x28: ("call", 4), 0x2A: ("ret", 0), 0x2B: ("br.s", 1), 0x2C: ("brfalse.s", 1), 0x2D: ("brtrue.s", 1),
    0x2F: ("bge.s", 1), 0x30: ("bgt.s", 1), 0x31: ("ble.s", 1), 0x32: ("blt.s", 1),
    0x38: ("br", 4), 0x39: ("brfalse", 4), 0x3A: ("brtrue", 4),
    0x58: ("add", 0), 0x59: ("sub", 0), 0x5A: ("mul", 0), 0x5B: ("div", 0),
    0x69: ("conv.i4", 0), 0x6B: ("conv.r4", 0), 0x6C: ("conv.r8", 0),
    0x6F: ("callvirt", 4), 0x72: ("ldstr", 4), 0x73: ("newobj", 4), 0x7B: ("ldfld", 4), 0x7D: ("stfld", 4),
    0x8C: ("box", 4),
}


def token_name(pe, tok):
    table = tok >> 24
    idx = (tok & 0xFFFFFF) - 1
    md = pe.net.mdtables
    try:
        if table == 0x0A:
            m = md.MemberRef[idx]
            parent = m.Class.row
            return f"{getattr(parent, 'TypeName', '?')}::{m.Name}"
        if table == 0x06:
            return f"MethodDef::{md.MethodDef[idx].Name}"
        if table == 0x04:
            return f"Field::{md.Field[idx].Name}"
        if table == 0x70:
            return "str"
    except Exception:
        pass
    return hex(tok)


def disasm(path, names):
    pe = dnfile.dnPE(path)
    md = pe.net.mdtables
    for t in md.TypeDef or []:
        for mref in t.MethodList or []:
            m = mref.row
            if str(m.Name) not in names or not m.Rva:
                continue
            off = pe.get_offset_from_rva(m.Rva)
            data = pe.__data__
            b0 = data[off]
            if b0 & 0x3 == 0x2:
                size = b0 >> 2
                code = bytes(data[off + 1: off + 1 + size])
            else:
                fs = struct.unpack_from("<H", data, off)[0]
                hdr = (fs >> 12) * 4
                size = struct.unpack_from("<I", data, off + 4)[0]
                code = bytes(data[off + hdr: off + hdr + size])
            print(f"--- {t.TypeName}.{m.Name} ({len(code)} bytes)")
            i = 0
            while i < len(code):
                op = code[i]
                if op == 0xFE:
                    print(f"  {i:04x}: FE {code[i+1]:02x}")
                    i += 2
                    continue
                if op not in ONE:
                    print(f"  {i:04x}: ?? {op:02x}")
                    i += 1
                    continue
                name, n = ONE[op]
                arg = code[i + 1: i + 1 + n]
                s = ""
                if name == "ldc.r4":
                    s = str(struct.unpack("<f", arg)[0])
                elif name == "ldc.r8":
                    s = str(struct.unpack("<d", arg)[0])
                elif name in ("ldc.i4",):
                    s = str(struct.unpack("<i", arg)[0])
                elif name == "ldc.i4.s":
                    s = str(struct.unpack("<b", arg)[0])
                elif name in ("call", "callvirt", "newobj", "ldfld", "stfld"):
                    s = token_name(pe, struct.unpack("<I", arg)[0])
                elif n:
                    s = arg.hex()
                print(f"  {i:04x}: {name} {s}")
                i += 1 + n


disasm(sys.argv[1], set(sys.argv[2:]))
