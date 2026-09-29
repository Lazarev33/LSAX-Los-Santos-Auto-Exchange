"""Builds LSAX-PHASE0-RUNTIME-VALIDATION-PACK.zip deterministically (Phase 0 tooling, NOT PRODUCTION CODE).

Offline only: this runs in the cloud/Linux build environment. Nothing here touches GTA V or the owner's PC, and no
result of this script is runtime evidence (label: OFFLINE VERIFIED).

Steps
  1. baseline guards: DRAFT2 release ZIP hash, probe sources/README/probe.ini.sample byte-identical to the baseline
     commit a3701019a3c64dd859fb1e00577db47360f64066;
  2. two clean builds of both probe projects from copies of the sources (-c Release -p:DebugType=none
     -p:ContinuousIntegrationBuild=true; the SQLite probe with -p:RuntimeIdentifier=win-x64); the two builds must be
     byte-identical (determinism) and must produce exactly the expected file set (no invented or missing files);
  3. payload checks: PE machine/CLR header of every DLL, assembly references of the probe DLLs, every dependency
     byte-identical to a file inside a package of the local NuGet cache, optional `dotnet nuget verify` summary;
  4. staging: docs/scripts/templates from runtime-validation-pack/, payload into install/, sources into source/,
     DRAFT2 README into upstream/, generated DEPLOYMENT-MANIFEST.tsv, BUILD-INFO.txt, PACK-INFO.txt, SHA256SUMS.txt;
     text normalisation (.cmd .ps1 .ini .txt .tsv -> CRLF, .md -> LF); lint (ASCII scripts, profiles vs DRAFT2
     sample, verbatim DRAFT2 text in 02/03, forbidden claims);
  5. ZIP with sorted entries, fixed timestamps and permissions -> release/LSAX-PHASE0-RUNTIME-VALIDATION-PACK.zip
     (+ .sha256);
  6. --verify: extract into a fresh temporary folder, re-check SHA256SUMS.txt from the extracted files only, and run
     the helper-script tests (test_runtime_pack.py) against the extracted pack when PowerShell is available.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
NAME = "LSAX-PHASE0-RUNTIME-VALIDATION-PACK"
STAMP = (2026, 9, 29, 0, 0, 0)
BASELINE = "a3701019a3c64dd859fb1e00577db47360f64066"
DRAFT2_ZIP = "release/LSAX-MASTER-SPEC-v1.0-DRAFT2.zip"
DRAFT2_SHA = "4c1e5ed5e54a4418a440ff4600c7faea86b5fa801fce21c59c8dbd943a93aa12"
SRC_PACK = os.path.join(ROOT, "runtime-validation-pack")
PROBES = os.path.join(ROOT, "phase0-probes")
EXPECTED_MAIN = ["LsaxPhase0Probe.dll"]
EXPECTED_SQL = sorted([
    "LsaxPhase0SqliteProbe.dll", "Microsoft.Data.Sqlite.dll", "SQLitePCLRaw.batteries_v2.dll", "SQLitePCLRaw.core.dll",
    "SQLitePCLRaw.provider.dynamic_cdecl.dll", "System.Buffers.dll", "System.Memory.dll", "System.Numerics.Vectors.dll",
    "System.Runtime.CompilerServices.Unsafe.dll", "e_sqlite3.dll"])
PROFILES = ["PSL01", "PDB01-STEP1", "PDB01", "PDB01-LEAK", "PID01"]
PROFILE_DIFF = {  # expected differences from the DRAFT2 probe.ini.sample (active keys only)
    "PSL01": {},
    "PDB01-STEP1": {"SqliteProbe.Enabled": "true"},
    "PDB01": {"SqliteProbe.Enabled": "true", "SqliteProbe.NativePath": "@@SQLITE_NATIVE_PATH@@"},
    "PDB01-LEAK": {"SqliteProbe.Enabled": "true", "SqliteProbe.NativePath": "@@SQLITE_NATIVE_PATH@@",
                   "SqliteProbe.CloseOnAbort": "false"},
    "PID01": {"IdentityProbe.Enabled": "true"},
}
CRLF_EXT = (".cmd", ".ps1", ".ini", ".txt", ".tsv")


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run(cmd, cwd=None, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def fail(msg):
    print("BUILD FAILED:", msg)
    sys.exit(2)


# ---------------------------------------------------------------------------------------------------- 1. guards
def guards():
    if sha(os.path.join(ROOT, DRAFT2_ZIP)) != DRAFT2_SHA:
        fail("DRAFT2 release ZIP hash differs from the baseline")
    protected = ["phase0-probes/shvdn", "phase0-probes/probe.ini.sample", "phase0-probes/README-PROBES.md",
                 "release/LSAX-MASTER-SPEC-v1.0-DRAFT1.zip", "release/LSAX-MASTER-SPEC-v1.0-DRAFT1.zip.sha256",
                 "release/LSAX-MASTER-SPEC-v1.0-DRAFT2.zip", "release/LSAX-MASTER-SPEC-v1.0-DRAFT2.zip.sha256"]
    rc, out = run(["git", "diff", "--quiet", BASELINE, "--"] + protected, cwd=ROOT)
    if rc != 0:
        fail("probe sources, README-PROBES.md, probe.ini.sample or the DRAFT1/DRAFT2 releases differ from baseline " + BASELINE)
    rc, _ = run(["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"], cwd=ROOT)
    if rc != 0:
        fail("HEAD does not descend from the baseline commit")
    print("guards ok: DRAFT2 zip", DRAFT2_SHA, "; probe sources identical to", BASELINE)


# ---------------------------------------------------------------------------------------------------- 2. build
def source_files(project):
    d = os.path.join(PROBES, "shvdn", project)
    return sorted(f for f in os.listdir(d) if f.endswith((".cs", ".csproj")))


def build_once(work):
    outs = {}
    for project, extra, key in (("LsaxPhase0Probe", [], "main"),
                                ("LsaxPhase0SqliteProbe", ["-p:RuntimeIdentifier=win-x64"], "sql")):
        src = os.path.join(work, "src", project)
        os.makedirs(src)
        for f in source_files(project):
            shutil.copyfile(os.path.join(PROBES, "shvdn", project, f), os.path.join(src, f))
        out = os.path.join(work, key)
        cmd = ["dotnet", "build", os.path.join(src, project + ".csproj"), "-c", "Release", "-p:DebugType=none",
               "-p:ContinuousIntegrationBuild=true", "-p:IncludeSourceRevisionInInformationalVersion=false",
               "-nologo"] + extra + ["-o", out]
        rc, log = run(cmd)
        if rc != 0:
            print(log[-4000:])
            fail("dotnet build failed for " + project)
        warn = re.findall(r"warning [A-Z]+\d+", log)
        outs[key] = (out, " ".join(cmd[1:]).replace(work, "<work>"), len(set(warn)))
    return outs


def listing(d):
    res = []
    for base, dirs, files in os.walk(d):
        for f in files:
            res.append(os.path.relpath(os.path.join(base, f), d).replace(os.sep, "/"))
    return sorted(res)


def build():
    t1 = tempfile.mkdtemp(prefix="lsax-rvp-b1-")
    t2 = tempfile.mkdtemp(prefix="lsax-rvp-b2-")
    b1 = build_once(t1)
    b2 = build_once(t2)
    for key, expected in (("main", EXPECTED_MAIN), ("sql", EXPECTED_SQL)):
        l1, l2 = listing(b1[key][0]), listing(b2[key][0])
        if l1 != sorted(expected) or l2 != sorted(expected):
            fail(f"unexpected {key} build output: {l1} (expected {sorted(expected)})")
        for f in l1:
            if sha(os.path.join(b1[key][0], f)) != sha(os.path.join(b2[key][0], f)):
                fail(f"non-deterministic output {key}/{f}")
    print("build ok: two clean builds byte-identical; file sets exactly as expected")
    return b1, t1, t2


# ---------------------------------------------------------------------------------------------------- 3. payload checks
def pe_info(path):
    import pefile  # available in the Phase 0 build environment
    pe = pefile.PE(path, fast_load=True)
    machine = {0x14c: "i386", 0x8664: "AMD64"}.get(pe.FILE_HEADER.Machine, hex(pe.FILE_HEADER.Machine))
    kind = "PE32+" if pe.OPTIONAL_HEADER.Magic == 0x20b else "PE32"
    clr = pe.OPTIONAL_HEADER.DATA_DIRECTORY[14]
    managed = clr.VirtualAddress != 0 and clr.Size != 0
    pe.close()
    return kind, machine, managed


def asm_refs(path):
    import dnfile
    pe = dnfile.dnPE(path)
    md = pe.net.mdtables
    refs = sorted(f"{r.Name} {r.MajorVersion}.{r.MinorVersion}.{r.BuildNumber}.{r.RevisionNumber}" for r in (md.AssemblyRef or []))
    asm = md.Assembly[0]
    own = f"{asm.Name} {asm.MajorVersion}.{asm.MinorVersion}.{asm.BuildNumber}.{asm.RevisionNumber}"
    pe.close()
    return own, refs


def nuget_origin(path):
    cache = os.path.expanduser("~/.nuget/packages")
    h = sha(path)
    name = os.path.basename(path)
    hits = []
    for base, dirs, files in os.walk(cache):
        if name in files and sha(os.path.join(base, name)) == h:
            hits.append(os.path.relpath(os.path.join(base, name), cache).replace(os.sep, "/"))
    return sorted(hits)


def nuget_verify():
    cache = os.path.expanduser("~/.nuget/packages")
    res = []
    for pkg, ver in (("microsoft.data.sqlite.core", "8.0.11"), ("sqlitepclraw.bundle_e_sqlite3", "2.1.6"),
                     ("sqlitepclraw.core", "2.1.6"), ("sqlitepclraw.lib.e_sqlite3", "2.1.6"),
                     ("sqlitepclraw.provider.dynamic_cdecl", "2.1.6"), ("system.buffers", "4.4.0"),
                     ("system.memory", "4.5.3"), ("system.numerics.vectors", "4.4.0"),
                     ("system.runtime.compilerservices.unsafe", "4.5.2")):
        nupkg = os.path.join(cache, pkg, ver, f"{pkg}.{ver}.nupkg")
        try:
            rc, out = run(["dotnet", "nuget", "verify", "--all", nupkg], timeout=180)
        except subprocess.TimeoutExpired:
            res.append(f"{pkg} {ver}\tverify=TIMEOUT (INCONCLUSIVE)")
            continue
        codes = sorted(set(re.findall(r"NU3\d{3}", out)))
        author = re.search(r"Signature type: Author\s+Subject Name: CN=([^,\n]+)", out)
        repo = re.search(r"Signature type: Repository\s+Subject Name: CN=([^,\n]+)", out)
        other = [c for c in codes if c not in ("NU3018", "NU3028")]  # NU3018/NU3028 here = revocation server unreachable
        res.append(f"{pkg} {ver}\tverify_exit={rc} author_signature={author.group(1) if author else 'none'} "
                   f"repository_signature={repo.group(1) if repo else 'NONE'} "
                   f"revocation={'INCONCLUSIVE (offline: ' + ','.join(codes) + ')' if codes else 'checked'}"
                   f"{' OTHER_CODES=' + ','.join(other) if other else ''}")
        # required: exit 0, the nuget.org repository signature, no warning other than offline revocation
        if rc != 0 or not repo or "NuGet.org Repository" not in repo.group(1) or other:
            fail(f"nuget signature check failed for {pkg} {ver}: exit {rc}, codes {codes}")
    return res


def payload_checks(b1, skip_verify):
    rows = []
    info = []
    for key, expected in (("main", EXPECTED_MAIN), ("sql", EXPECTED_SQL)):
        out = b1[key][0]
        for f in expected:
            p = os.path.join(out, f)
            kind, machine, managed = pe_info(p)
            if f == "e_sqlite3.dll":
                if managed or machine != "AMD64" or kind != "PE32+":
                    fail("e_sqlite3.dll is not a native x64 PE32+ DLL")
            elif not managed:
                fail(f + " has no CLR header")
            if f.startswith("LsaxPhase0") and machine != "AMD64":
                fail(f + " is not x64 (PlatformTarget x64 expected)")
            if f.lower().startswith("scripthookvdotnet"):
                fail("SHVDN assembly in the payload")
            origin = "probe (built from source/)"
            if not f.startswith("LsaxPhase0"):
                hits = nuget_origin(p)
                if not hits:
                    fail(f + " is not byte-identical to any file in the local NuGet cache")
                origin = "nuget:" + hits[0] + (f" (+{len(hits) - 1} identical)" if len(hits) > 1 else "")
            rows.append((key, f, sha(p), f"{kind} {machine} {'managed' if managed else 'native'}", origin))
            if f.startswith("LsaxPhase0"):
                own, refs = asm_refs(p)
                info.append(f"{f}: assembly {own}; references " + "; ".join(refs))
    check_shvdn_refs(info)
    verify = [] if skip_verify else nuget_verify()
    return rows, info, verify


def check_shvdn_refs(info):
    # Both probes must reference the SHVDN v3 API assembly at 3.6.0.0 (compile-time reference; SHVDN 3.7.x resolves
    # it because the major version matches and the installed version is >= the referenced one - SOURCE VERIFIED).
    for line in info:
        if "ScriptHookVDotNet3 3.6.0.0" not in line:
            fail("probe does not reference ScriptHookVDotNet3 3.6.0.0: " + line)


# ---------------------------------------------------------------------------------------------------- 4. staging
def norm_text(data, ext):
    text = data.decode("utf-8")
    text = text.replace("\r\n", "\n")
    if ext in CRLF_EXT:
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def ini_active(text):
    d = {}
    for line in text.replace("\r\n", "\n").split("\n"):
        s = line.strip()
        if not s or s[0] in ";#" or "=" not in s:
            continue
        k, v = s.split("=", 1)
        d[k.strip()] = v.strip()
    return d


def lint(stage, sample_text):
    errors = []
    sample = ini_active(sample_text)
    for p in PROFILES:
        prof = ini_active(open(os.path.join(stage, "install", "config", f"probe.{p}.ini"), encoding="ascii").read())
        diff = {k: v for k, v in prof.items() if sample.get(k) != v}
        missing = [k for k in sample if k not in prof]
        if diff != PROFILE_DIFF[p] or missing:
            errors.append(f"profile {p}: differs from DRAFT2 sample by {diff}, missing {missing}")
        if prof.get("AnchorProbe.Enabled", "false").lower() != "false" or prof.get("AnchorProbe.Consent", "") != "":
            errors.append(f"profile {p}: P-SL-02 not disabled")
    for base, dirs, files in os.walk(stage):
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, stage).replace(os.sep, "/")
            data = open(p, "rb").read()
            if f.endswith((".cmd", ".ps1")):
                if any(b > 127 for b in data):
                    errors.append(rel + ": non-ASCII in a script")
                if f.endswith(".cmd") and b"\n" in data.replace(b"\r\n", b""):
                    errors.append(rel + ": bare LF in a .cmd file")
            if f.endswith((".cs", ".vb")) and not rel.startswith("source/"):
                errors.append(rel + ": source file outside source/")
            if f.endswith(".dll") and not rel.startswith("install/"):
                errors.append(rel + ": DLL outside install/")
            if f.endswith((".md", ".txt", ".tsv", ".ps1", ".cmd", ".ini")):
                text = data.decode("utf-8")
                for i, line in enumerate(text.splitlines(), 1):
                    if line.startswith(">"):
                        continue  # verbatim DRAFT2 quotation, checked separately for exactness
                    if "RUNTIME VERIFIED" in line and not re.search(r"не используется|not used|NEVER|никогда|\*\*не\*\*", line):
                        errors.append(f"{rel}:{i}: unnegated RUNTIME VERIFIED")
                    if re.search(r"SPEC_APPROVED", line) and not re.search(r"не выдаёт|not grant|NOT|не |\*\*не\*\*", line):
                        errors.append(f"{rel}:{i}: SPEC_APPROVED outside a negation")
                if f == "TEST-LOG.tsv":
                    for i, line in enumerate(text.splitlines()[1:], 2):
                        cols = line.split("\t")
                        if len(cols) != 7:
                            errors.append(f"{rel}:{i}: {len(cols)} columns")
                        elif cols[5].strip():
                            errors.append(f"{rel}:{i}: result pre-filled")
    # verbatim DRAFT2 text in 02 and 03
    readme = open(os.path.join(PROBES, "README-PROBES.md"), encoding="utf-8").read()
    doc02 = open(os.path.join(stage, "02-FULL-VALIDATION-T1-T17-RU.md"), encoding="utf-8").read()
    n = 0
    for line in readme.splitlines():
        m = re.match(r"^\| (T\d+) \| (.*) \| (.*) \|$", line)
        if m:
            n += 1
            if f"| {m.group(2)} | {m.group(3)} |" not in doc02:
                errors.append(f"02: {m.group(1)} not verbatim")
    if n != 17:
        errors.append(f"README table rows found: {n}")
    doc03 = open(os.path.join(stage, "03-PASS-FAIL-RULES.md"), encoding="utf-8").read()
    for start, end in ((r"^## 6\. PASS / FAIL rules", r"^## 7\. "), (r"^## 7\. P-DB-01", r"^## 8\. "),
                       (r"^## 8\. P-ID-01", r"^## 9\. "), (r"^## 9\. P-SL-02", r"^## 10\. ")):
        L = readme.split("\n")
        s = next(i for i, l in enumerate(L) if re.match(start, l))
        e = next(i for i, l in enumerate(L) if i > s and re.match(end, l))
        block = "\n".join(("> " + l) if l else ">" for l in "\n".join(L[s:e]).rstrip("\n").split("\n"))
        if block not in doc03:
            errors.append("03: README section not verbatim: " + L[s])
    for pattern, path in ((r"^## 6\. Exact experiment", "spec/LSAX-SAVELOAD-FEASIBILITY.md"),):
        L = open(os.path.join(ROOT, path), encoding="utf-8").read().split("\n")
        s = next(i for i, l in enumerate(L) if re.match(pattern, l))
        e = next(i for i, l in enumerate(L) if i > s and l.startswith("## "))
        block = "\n".join(("> " + l) if l else ">" for l in "\n".join(L[s:e]).rstrip("\n").split("\n"))
        if block not in doc03:
            errors.append("03: SAVELOAD §6 not verbatim")
    if errors:
        for e in errors:
            print("LINT:", e)
        fail(f"{len(errors)} lint error(s)")
    print("lint ok: profiles vs DRAFT2 sample, scripts ASCII/CRLF, verbatim 02/03, no forbidden claims, templates empty")


def stage_pack(b1, rows, info, verify, sdk):
    stage_parent = tempfile.mkdtemp(prefix="lsax-rvp-stage-")
    stage = os.path.join(stage_parent, NAME)
    os.makedirs(stage)
    # docs, scripts, config profiles, templates
    for base, dirs, files in os.walk(SRC_PACK):
        for f in files:
            src = os.path.join(base, f)
            rel = os.path.relpath(src, SRC_PACK)
            dst = os.path.join(stage, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            ext = os.path.splitext(f)[1].lower()
            with open(src, "rb") as fh:
                data = fh.read()
            if ext in CRLF_EXT or ext == ".md":
                data = norm_text(data, ext)
            with open(dst, "wb") as fh:
                fh.write(data)
    # payload
    manifest = ["# " + NAME + " deployment manifest: payload file -> destination relative to the SHVDN scripts folder",
                "component\tsource\tdestination\tsha256"]
    for key, f, h, pe, origin in rows:
        src = os.path.join(b1[key][0], f)
        if key == "main":
            rel_src, dest = "install/" + f, f
        else:
            rel_src, dest = "install/LSAXProbeSql/" + f, "LSAXProbeSql/" + f
        os.makedirs(os.path.dirname(os.path.join(stage, rel_src)), exist_ok=True)
        shutil.copyfile(src, os.path.join(stage, rel_src))
        manifest.append(f"{key}\t{rel_src}\t{dest}\t{h}")
    write(os.path.join(stage, "install", "DEPLOYMENT-MANIFEST.tsv"), "\r\n".join(manifest) + "\r\n")
    # sources (byte-identical to the baseline) + DRAFT2 README + sample
    src_hash = []
    for project in ("LsaxPhase0Probe", "LsaxPhase0SqliteProbe"):
        for f in source_files(project):
            s = os.path.join(PROBES, "shvdn", project, f)
            d = os.path.join(stage, "source", project, f)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copyfile(s, d)
            src_hash.append(f"{sha(s)}  source/{project}/{f}")
    shutil.copyfile(os.path.join(PROBES, "probe.ini.sample"), os.path.join(stage, "source", "probe.ini.sample"))
    os.makedirs(os.path.join(stage, "upstream"), exist_ok=True)
    shutil.copyfile(os.path.join(PROBES, "README-PROBES.md"), os.path.join(stage, "upstream", "README-PROBES.md"))
    write(os.path.join(stage, "source", "README-SOURCE.txt"), "\r\n".join([
        "LSAX Phase 0 disposable probe sources - NOT LSAX PRODUCTION CODE.",
        f"Byte-identical to phase0-probes/shvdn/ at baseline commit {BASELINE} (DRAFT2).",
        "NEVER copy this folder into the GTA scripts folder: SHVDN compiles every .cs file under scripts.",
        "Build on Windows with scripts\\BUILD-PROBES-WINDOWS.cmd (.NET SDK 8+).", ""] + src_hash) + "\r\n")
    # build info
    lines = [
        f"{NAME} - BUILD-INFO (OFFLINE VERIFIED build; NOT runtime evidence)",
        "",
        "build environment\tcloud Linux container, no GTA V, no Windows",
        f"dotnet sdk\t{sdk}",
        f"source baseline commit\t{BASELINE}",
        f"main build command\tdotnet {b1['main'][1]}",
        f"sql build command\tdotnet {b1['sql'][1]}",
        "determinism\ttwo clean builds from separate copies are byte-identical (checked by build_runtime_pack.py)",
        "location independence\t-p:IncludeSourceRevisionInInformationalVersion=false stops the .NET 8 SDK from appending a git "
        "commit to AssemblyInformationalVersion, so the output does not depend on whether the sources sit in a git repository",
        "",
        "payload\tsha256\tpe\torigin",
    ]
    for key, f, h, pe, origin in rows:
        lines.append(f"{'install/' if key == 'main' else 'install/LSAXProbeSql/'}{f}\t{h}\t{pe}\t{origin}")
    lines += ["", "assembly metadata:"] + ["  " + i for i in info]
    lines += ["", "nuget package signature check (dotnet nuget verify --all; revocation cannot be checked offline -> "
              "NU3018/NU3028 = INCONCLUSIVE, not a failure of the file hashes above):"]
    lines += ["  " + v for v in verify] if verify else ["  skipped (--skip-nuget-verify)"]
    lines += ["", "Labels: OFFLINE VERIFIED = checked here without GTA. Whether the probes load and work in GTA V is",
              "OWNER_RUNTIME_ACTION_REQUIRED."]
    write(os.path.join(stage, "install", "BUILD-INFO.txt"), "\r\n".join(lines) + "\r\n")
    # pack info
    write(os.path.join(stage, "PACK-INFO.txt"), "\r\n".join([
        f"{NAME}",
        "status\tRUNTIME_VALIDATION_PACK_READY / OWNER_RUNTIME_ACTION_REQUIRED",
        "B-01\tOPEN (closes only after the owner's runtime evidence is reviewed by the independent reviewer)",
        "prepared by\tClaude, in the cloud, without access to the owner's PC, GTA V, saves, ScriptHookV, SHVDN or modpack",
        "runtime\tNOTHING in this pack has been run in GTA V. No result here is runtime evidence.",
        f"spec baseline\tLSAX-MASTER-SPEC-v1.0-DRAFT2.zip sha256 {DRAFT2_SHA}",
        f"source baseline commit\t{BASELINE}",
        "target runtime\tGTA V Legacy 1.0.3725.0, ScriptHookV, ScriptHookVDotNet 3.7.x, .NET Framework 4.8, Windows x64",
        "configurations\tFULL-MODPACK and MINIMAL, each run completely",
        "labels\tSOURCE VERIFIED, OFFLINE VERIFIED, OWNER_RUNTIME_ACTION_REQUIRED, INCONCLUSIVE",
        "production code\tnone (disposable Phase 0 probes only)",
        "start here\t00-RUN-ME-FIRST-RU.md",
    ]) + "\r\n")
    lint(stage, open(os.path.join(PROBES, "probe.ini.sample"), encoding="utf-8").read())
    # SHA256SUMS last
    entries = []
    for base, dirs, files in os.walk(stage):
        for f in files:
            rel = os.path.relpath(os.path.join(base, f), stage).replace(os.sep, "/")
            if rel != "SHA256SUMS.txt":
                entries.append(rel)
    sums = [f"{sha(os.path.join(stage, r))}  {r}" for r in sorted(entries)]
    write(os.path.join(stage, "SHA256SUMS.txt"), "\r\n".join(sums) + "\r\n")
    return stage_parent, stage


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


# ---------------------------------------------------------------------------------------------------- 5. zip
def make_zip(stage):
    files = []
    for base, dirs, fs in os.walk(stage):
        for f in fs:
            files.append(os.path.relpath(os.path.join(base, f), stage).replace(os.sep, "/"))
    out = os.path.join(ROOT, "release", NAME + ".zip")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in sorted(files):
            info = zipfile.ZipInfo(f"{NAME}/{rel}", date_time=STAMP)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(stage, rel), "rb") as fh:
                z.writestr(info, fh.read())
    digest = sha(out)
    write(out + ".sha256", f"{digest}  {NAME}.zip\n")
    print(f"zip: release/{NAME}.zip entries={len(files)} sha256={digest}")
    return out, digest


# ---------------------------------------------------------------------------------------------------- 6. verify
def verify(zip_path, pwsh):
    tmp = tempfile.mkdtemp(prefix="lsax-rvp-verify-")
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        if bad:
            fail("corrupt zip entry " + bad)
        names = z.namelist()
        if any(not n.startswith(NAME + "/") or ".." in n or "\\" in n for n in names):
            fail("zip entry outside the root folder")
        z.extractall(tmp)
    root = os.path.join(tmp, NAME)
    n = 0
    for line in open(os.path.join(root, "SHA256SUMS.txt"), encoding="utf-8").read().splitlines():
        h, rel = line[:64], line[66:]
        if sha(os.path.join(root, rel)) != h:
            fail("extracted file hash mismatch: " + rel)
        n += 1
    listed = {l[66:] for l in open(os.path.join(root, "SHA256SUMS.txt"), encoding="utf-8").read().splitlines()}
    present = set(listing(root)) - {"SHA256SUMS.txt"}
    if listed != present:
        fail(f"SHA256SUMS.txt does not cover exactly the extracted files: {sorted(listed ^ present)}")
    print(f"verify ok: clean extraction, {n}/{n} SHA256SUMS lines match, no extra or missing files")
    if pwsh:
        rc = subprocess.run([sys.executable, os.path.join(ROOT, "phase0-probes", "tools", "test_runtime_pack.py"),
                             "--pack", root, "--pwsh", pwsh]).returncode
        if rc != 0:
            fail("helper-script tests failed on the extracted pack")
    else:
        print("helper-script tests skipped: no PowerShell given (--pwsh)")
    return root


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--pwsh", default=os.environ.get("LSAX_PWSH") or shutil.which("pwsh"))
    ap.add_argument("--skip-nuget-verify", action="store_true")
    a = ap.parse_args()
    guards()
    rc, sdk = run(["dotnet", "--version"])
    sdk = sdk.strip()
    b1, t1, t2 = build()
    rows, info, ver = payload_checks(b1, a.skip_nuget_verify)
    for r in rows:
        print("payload", r[0], r[1], r[2][:16], r[3], r[4])
    stage_parent, stage = stage_pack(b1, rows, info, ver, sdk)
    zip_path, digest = make_zip(stage)
    for t in (t1, t2, stage_parent):
        shutil.rmtree(t, ignore_errors=True)
    if a.verify:
        verify(zip_path, a.pwsh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
