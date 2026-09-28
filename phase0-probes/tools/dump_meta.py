"""Disposable read-only .NET metadata dumper for reference-archive inspection (Phase 0).
Prints assembly refs, type defs (with fields/methods), type refs, member refs and user strings.
Not LSAX code."""
import sys
import dnfile


def s(x):
    try:
        return str(x)
    except Exception:
        return repr(x)


def dump(path):
    pe = dnfile.dnPE(path)
    md = pe.net.mdtables
    print("=" * 80)
    print("FILE", path)
    if md.Assembly:
        for a in md.Assembly:
            print("ASSEMBLY", s(a.Name), a.MajorVersion, a.MinorVersion, a.BuildNumber, a.RevisionNumber)
    print("-- AssemblyRef")
    for r in md.AssemblyRef or []:
        print("  ", s(r.Name), r.MajorVersion, r.MinorVersion, r.BuildNumber, r.RevisionNumber)
    print("-- TypeDef (fields/methods)")
    for t in md.TypeDef or []:
        ext = ""
        try:
            if t.Extends and t.Extends.row:
                ext = s(getattr(t.Extends.row, "TypeName", ""))
        except Exception:
            pass
        print(f"  TYPE {s(t.TypeNamespace)}.{s(t.TypeName)} : {ext}")
        for f in t.FieldList or []:
            try:
                print(f"     field {s(f.row.Name)}")
            except Exception:
                pass
        for m in t.MethodList or []:
            try:
                print(f"     method {s(m.row.Name)}")
            except Exception:
                pass
    print("-- TypeRef")
    for t in md.TypeRef or []:
        print(f"   {s(t.TypeNamespace)}.{s(t.TypeName)}")
    print("-- MemberRef")
    seen = set()
    for m in md.MemberRef or []:
        parent = ""
        try:
            row = m.Class.row
            parent = f"{s(getattr(row, 'TypeNamespace', ''))}.{s(getattr(row, 'TypeName', getattr(row, 'Name', '')))}"
        except Exception:
            pass
        key = f"{parent}::{s(m.Name)}"
        if key not in seen:
            seen.add(key)
            print("  ", key)
    print("-- UserStrings")
    us = pe.net.user_strings
    if us:
        off = 1
        data = us.get_us if hasattr(us, "get_us") else None
        # iterate the #US heap
        buf = us.__data__
        i = 1
        while i < len(buf):
            ln = buf[i]
            hdr = 1
            if ln & 0x80 == 0:
                size = ln
            elif ln & 0xC0 == 0x80:
                size = ((ln & 0x3F) << 8) | buf[i + 1]
                hdr = 2
            else:
                size = ((ln & 0x1F) << 24) | (buf[i + 1] << 16) | (buf[i + 2] << 8) | buf[i + 3]
                hdr = 4
            if size == 0:
                i += hdr
                continue
            raw = buf[i + hdr:i + hdr + size - 1]
            try:
                txt = raw.decode("utf-16-le")
            except Exception:
                txt = repr(raw)
            print("   US:", repr(txt))
            i += hdr + size


if __name__ == "__main__":
    for p in sys.argv[1:]:
        dump(p)
