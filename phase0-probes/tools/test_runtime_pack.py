"""Offline tests of the runtime-validation-pack helper scripts (Phase 0 tooling, NOT PRODUCTION CODE).

Runs the PowerShell helpers of an EXTRACTED pack (scripts/lib/*.ps1) with PowerShell 7 against a FAKE GTA V folder
tree in a temporary directory. Label of every result: OFFLINE VERIFIED (pwsh 7 on Linux, fake tree). Windows
PowerShell 5.1, cmd.exe and the real GTA V / SHVDN runtime are not available here: their behaviour stays
INCONCLUSIVE / OWNER_RUNTIME_ACTION_REQUIRED. The probe log lines written for the CHECK-LOG tests are SYNTHETIC
FIXTURES in the probes' log format - they are not runtime evidence and are never packaged.

Usage: python3 test_runtime_pack.py --pack <extracted pack root> --pwsh <pwsh executable> [--skip-build]
"""
import argparse
import hashlib
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import zipfile

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(("  ok    " if cond else "  FAIL  ") + name + ("" if cond else "  :: " + str(detail)[:1500]))


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def snapshot(root):
    snap = {}
    for base, dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(base, f)
            snap[os.path.relpath(p, root).replace(os.sep, "/")] = sha(p)
    return snap


def changes(before, after):
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    return added, removed, changed


class Pack:
    def __init__(self, root, pwsh):
        self.root = root
        self.pwsh = pwsh

    def ps(self, script, *args, stdin="", env=None):
        e = dict(os.environ)
        if env:
            e.update(env)
        p = subprocess.run([self.pwsh, "-NoProfile", "-File", os.path.join(self.root, "scripts", "lib", script)] + list(args),
                           input=stdin, capture_output=True, text=True, env=e, timeout=900)
        return p.returncode, p.stdout + p.stderr


def make_gta(base, name="Grand Theft Auto V", exe="GTA5.exe", asi=True, ini=None, scripts_dir="scripts"):
    gta = os.path.join(base, name)
    os.makedirs(os.path.join(gta, scripts_dir, "OtherMod"))
    files = {exe: b"MZ fake game executable", "ScriptHookV.dll": b"MZ fake shv", "dinput8.dll": b"MZ fake asi loader",
             "ScriptHookVDotNet3.dll": b"MZ fake shvdn3",
             "ScriptHookVDotNet.log": b"[00:00:01] [INFO] Loading scripts from ...\n[00:00:02] [INFO] Found script LsaxPhase0Probe.SessionSignalProbe\n[00:00:03] [INFO] Unrelated mod message\n",
             os.path.join(scripts_dir, "OtherMod.dll"): b"MZ other mod",
             os.path.join(scripts_dir, "OtherMod", "System.Memory.dll"): b"MZ other mods copy of System.Memory",
             os.path.join(scripts_dir, "OtherMod", "OtherMod.ini"): b"[x]\nkey=1\n",
             os.path.join(scripts_dir, "OtherScript.cs"): b"// another mod's source script\n"}
    if asi:
        files["ScriptHookVDotNet.asi"] = b"MZ fake shvdn asi"
    if ini is not None:
        files["ScriptHookVDotNet.ini"] = ini.encode()
    for rel, data in files.items():
        with open(os.path.join(gta, rel), "wb") as fh:
            fh.write(data)
    saves = os.path.join(base, "Documents", "Rockstar Games", "GTA V", "Profiles", "ABCDEF01")
    os.makedirs(saves)
    for s in ("SGTA50000", "SGTA50001", "SGTA50003"):
        with open(os.path.join(saves, s), "wb") as fh:
            fh.write(os.urandom(256))
    return gta


# ------------------------------------------------------------------------------------------ synthetic log fixtures
UTC = [0]


def ts():
    UTC[0] += 1
    return f"2026-10-01T20:{UTC[0] // 60:02d}:{UTC[0] % 60:02d}.0000000Z"


def line(evt, data):
    return f"{ts()}\t{evt}\t{data}\n"


PROC1 = "4242-638650000000000000"
PROC2 = "5151-638650000900000000"


def fx_ctor(dom, proc, present, value, persisted, token, pt="TOTAL_PLAYING_TIME=120000", match=None):
    out = line("CTOR", f"domainInstanceInProcess={dom} process={proc} appDomain=SHVDN_ScriptDomain_1A shvdnAsm=3.7.0.0 "
                       f"shvdnFileVersion=3.7.0-nightly.fixture gameVersion=99 saveRoot=C:\\Users\\Alice\\Documents\\Rockstar Games\\GTA V\\Profiles")
    out += line("CTOR_FP", f"frame=10 gameTime=5000 cash=1000,2000,3000 pt={pt} clock=[2013-09-17 12:00:00 dow=2 msPerMin=2000] model=0x0D7114C9")
    out += line("CTOR_FLAGS", "autosave=0 manualSaveStatus=0 codeReqAutosave=0 pause=0 fadedOut=0 switch=0 loadingScreen=0 missionFlag=0")
    out += line("TOKEN_AT_CTOR", f"registered=1 present={present} value={value} persisted=[{persisted}] process={proc}")
    out += line("TOKEN_SET", f"token={token} setOk=1 readBack=1 ped=42")
    out += line("SAVEFILE_INITIAL", "file=SGTA50000 len=500000 mtimeUtc=2026-10-01T19:00:00.0000000Z sha256=AA inProbeLedger=0")
    if pt:
        m = match if match is not None else "matches=0 []"
        out += line("LOAD_MATCH", f"pt=TOTAL_PLAYING_TIME value=120000 {m} cash=[1000,2000,3000]")
    return out


def fx_save(file, signal_seen):
    return (line("FLAGS", "autosave=0 manualSaveStatus=1 codeReqAutosave=0 pause=1 fadedOut=0 switch=0 loadingScreen=0 missionFlag=0 frame=900 preSignal=[frame=899]")
            + line("SAVEFILE_CHANGED", f"file={file} len=500001 mtimeUtc=2026-10-01T20:10:00.0000000Z sha256=BB signalSeen={signal_seen} "
                                       f"msSinceFlagChange=800 bracketLo=[frame=899] bracketHi=[frame=950] walletsStable=1 flags=[x]"))


def fx_sql_block(native, scripts, fail=False):
    out = line("SQL_CTOR", f"baseDir={scripts}/ asmLocation={scripts}/LSAXProbeSql/LsaxPhase0SqliteProbe.dll codeBase=file:///{scripts}/LSAXProbeSql/LsaxPhase0SqliteProbe.dll")
    out += line("SQL_PRELOAD", f"path={native} ok=True win32err=0")
    if fail:
        return out + line("SQL_FAIL", "System.DllNotFoundException: fixture")
    out += line("SQL_OPEN", f"ms=12 sqlite=3.46.1 journal=wal nativeModule={native}")
    out += line("SQL_COMMIT_US", "n=20 p50=900 p95=2500 max=4000 rows=20")
    out += line("SQL_DEPENDENCY", f"Microsoft.Data.Sqlite version=8.0.11.0 location={scripts}/LSAXProbeSql/Microsoft.Data.Sqlite.dll")
    out += line("SQL_DEPENDENCY", "System.Memory version=4.0.1.1 location=C:\\Users\\Alice\\AppData\\Local\\assembly\\dl3\\X\\System.Memory.dll")
    out += line("SQL_PRAGMAS", "main.synchronous=2 proj.synchronous=1 proj.journal=wal")
    out += line("SQL_WATERMARK_AT_START", "journalMax=0 watermark=<none>")
    out += line("SQL_TWO_FILE_COMMIT_US", "n=20 journal(FULL) p50=1000 p95=3000 max=5000 projection(NORMAL) p50=300 p95=600 max=900")
    out += line("SQL_SNAPSHOT", "tables=[projection_meta,vehicle] watermark=40")
    out += line("SQL_JOURNAL_BACKUP", "tables=[probe_row]")
    out += line("SQL_RESTORE", "projRows=20 watermark=40")
    return out


def append(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as fh:
        fh.write(text)


# ------------------------------------------------------------------------------------------------------ tests
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--pwsh", required=True)
    ap.add_argument("--skip-build", action="store_true")
    a = ap.parse_args()
    work = tempfile.mkdtemp(prefix="lsax-rvp-test-")
    # tests run on a COPY so the verified extraction stays pristine
    pack_root = os.path.join(work, "pack", os.path.basename(a.pack.rstrip("/")))
    shutil.copytree(a.pack, pack_root)
    P = Pack(pack_root, a.pwsh)
    print("OFFLINE TESTS (pwsh 7 on Linux, fake GTA tree; NOT runtime evidence)")
    print("pwsh:", subprocess.run([a.pwsh, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
                                  capture_output=True, text=True).stdout.strip())

    # --- pack integrity
    rc, out = P.ps("Hash-Probes.ps1")
    check("HASH-PROBES verifies the extracted pack", rc == 0 and "problems: 0" in out, out)
    tam = os.path.join(work, "tampered", os.path.basename(pack_root))
    shutil.copytree(pack_root, tam)
    with open(os.path.join(tam, "install", "LsaxPhase0Probe.dll"), "ab") as fh:
        fh.write(b"x")
    rc, out = Pack(tam, a.pwsh).ps("Hash-Probes.ps1", "-VerifyPack")
    check("HASH-PROBES detects a changed payload file (exit 2)", rc == 2 and "CHANGED  install/LsaxPhase0Probe.dll" in out, out)
    fake = os.path.join(work, "t-bad")
    os.makedirs(fake)
    g_bad = make_gta(fake)
    rc, out = Pack(tam, a.pwsh).ps("Install-Probes.ps1", "-GtaRoot", g_bad, "-AssumeYes")
    check("INSTALL refuses a tampered payload (exit 2) and writes nothing", rc == 2 and not os.path.exists(os.path.join(g_bad, "scripts", "LsaxPhase0Probe.dll")), out)

    # --- input validation (nothing written)
    base = os.path.join(work, "t1")
    os.makedirs(base)
    gta = make_gta(base)
    scripts = os.path.join(gta, "scripts")
    before0 = snapshot(base)
    rc, out = P.ps("Install-Probes.ps1", stdin="")
    check("INSTALL without a GTA path and empty answer exits 1", rc == 1 and "No GTA folder given" in out, out)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", os.path.join(base, "Documents"), "-AssumeYes")
    check("INSTALL rejects a folder without GTA5.exe (exit 1)", rc == 1 and "GTA5.exe not found" in out, out)
    enh = make_gta(os.path.join(work, "t-enh"), exe="GTA5_Enhanced.exe")
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", enh, "-AssumeYes")
    check("INSTALL rejects an Enhanced-only folder (target is Legacy)", rc == 1 and "LEGACY" in out, out)
    noasi = make_gta(os.path.join(work, "t-noasi"), asi=False)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", noasi, "-AssumeYes")
    check("INSTALL rejects a folder without ScriptHookVDotNet.asi", rc == 1 and "ScriptHookVDotNet.asi not found" in out, out)
    al = make_gta(os.path.join(work, "t-autoload"), ini="[Settings]\nAutoLoadScripts=false\n")
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", al, "-AssumeYes")
    check("INSTALL stops on AutoLoadScripts=false and does not edit the SHVDN INI", rc == 1 and "AutoLoadScripts=false" in out
          and open(os.path.join(al, "ScriptHookVDotNet.ini")).read() == "[Settings]\nAutoLoadScripts=false\n", out)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, stdin="no\n")
    check("INSTALL shows destinations and aborts without YES (exit 4)", rc == 4 and "[NEW] " in out and "Every destination" in out, out)
    check("  ... and wrote nothing", snapshot(base) == before0)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-ProbeProfile", "NOPE", "-AssumeYes")
    check("INSTALL rejects an unknown profile (exit 1)", rc == 1, out)
    check("  ... and wrote nothing", snapshot(base) == before0)

    # --- game running
    fake_game = os.path.join(work, "GTA5")
    shutil.copyfile(shutil.which("sleep"), fake_game)
    os.chmod(fake_game, 0o755)
    proc = subprocess.Popen([fake_game, "60"])
    try:
        rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-AssumeYes")
        check("INSTALL refuses while a process named GTA5 runs (exit 3)", rc == 3 and "GTA V is running" in out, out)
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait()

    # --- duplicate probe DLL elsewhere
    dup = os.path.join(scripts, "OldStuff")
    os.makedirs(dup)
    with open(os.path.join(dup, "LsaxPhase0Probe.dll"), "wb") as fh:
        fh.write(b"MZ old copy")
    b = snapshot(base)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-AssumeYes")
    check("INSTALL refuses when another LsaxPhase0Probe.dll exists under scripts (exit 1)", rc == 1 and "OldStuff" in out, out)
    check("  ... writes nothing and deletes nothing", snapshot(base) == b)
    shutil.rmtree(dup)

    # --- real install
    manifest_rows = [l.split("\t") for l in open(os.path.join(pack_root, "install", "DEPLOYMENT-MANIFEST.tsv"), encoding="utf-8").read().splitlines()
                     if l and not l.startswith(("#", "component"))]
    before = snapshot(base)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-AssumeYes")
    check("INSTALL (All, PSL01) exits 0", rc == 0 and "[LSAX-OK]" in out, out)
    after = snapshot(base)
    added, removed, changed = changes(before, after)
    allowed = ("Grand Theft Auto V/scripts/LsaxPhase0Probe.dll", "Grand Theft Auto V/scripts/LSAXProbeSql/", "Grand Theft Auto V/scripts/LSAXProbe/")
    check("INSTALL only adds files under the three pack destinations", all(x.startswith(allowed) for x in added), added)
    check("INSTALL removes and changes no existing file (saves, GTA, SHV, SHVDN, other mods)", not removed and not changed, (removed, changed))
    for comp, src, dest, h in manifest_rows:
        p = os.path.join(scripts, *dest.split("/"))
        check(f"installed {dest} has the manifest SHA-256", os.path.exists(p) and sha(p) == h)
    check("payload has 11 files (1 main + 10 in LSAXProbeSql)", len(manifest_rows) == 11, len(manifest_rows))
    ini = open(os.path.join(scripts, "LSAXProbe", "probe.ini"), encoding="utf-8").read()
    check("probe.ini = profile PSL01 (B-01 settings, P-SL-02 off)", "SessionToken.Enabled=true" in ini and "AnchorProbe.Enabled=false" in ini
          and "SqliteProbe.Enabled=false" in ini and "IdentityProbe.Enabled=false" in ini, ini)
    man = open(os.path.join(scripts, "LSAXProbe", "LSAX-PACK-INSTALL-MANIFEST.tsv"), encoding="utf-8").read()
    check("install manifest lists 12 own files", len([l for l in man.splitlines() if l and not l.startswith(("#", "dest_rel"))]) == 12, man)
    reps = [f for f in os.listdir(os.path.join(scripts, "LSAXProbe")) if f.startswith("install-report-")]
    rep = open(os.path.join(scripts, "LSAXProbe", reps[0]), encoding="utf-8").read() if reps else ""
    check("install report names the other mod's same-name System.Memory.dll (R-COMP-2 input), relative path only",
          "same_name_dependency_of_other_mod\tOtherMod/System.Memory.dll" in rep and base not in rep, rep)
    check("INSTALL prints the SHA-256 of both probe DLLs", out.count("SHA-256 ") >= 2, out)

    rc, out = P.ps("Hash-Probes.ps1", "-GtaRoot", gta)
    check("HASH-PROBES -GtaRoot: installed files match (exit 0)", rc == 0, out)
    b = snapshot(base)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-AssumeYes")
    check("re-INSTALL of identical files: exit 0, all IDENTICAL, no backup", rc == 0 and "[NEW]" not in out and "[REPLACE]" not in out
          and not os.path.exists(os.path.join(scripts, "LSAXProbe", "install-backup")), out)
    # same-name probe file with other content -> backup first
    with open(os.path.join(scripts, "LsaxPhase0Probe.dll"), "wb") as fh:
        fh.write(b"MZ older probe build")
    rc, out = P.ps("Hash-Probes.ps1", "-GtaRoot", gta)
    check("HASH-PROBES -GtaRoot detects a changed installed DLL (exit 2)", rc == 2 and "CHANGED  LsaxPhase0Probe.dll" in out, out)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-AssumeYes")
    baks = []
    for bb, dd, ff in os.walk(os.path.join(scripts, "LSAXProbe", "install-backup")):
        baks += [os.path.join(bb, f) for f in ff]
    check("INSTALL backs up a same-name probe file before replacing it", rc == 0 and "[REPLACE]" in out and len(baks) == 1
          and open(baks[0], "rb").read() == b"MZ older probe build", (out, baks))
    check("  ... backup name ends in .lsaxbak (never *.dll/*.cs/*.vb for SHVDN)", baks and baks[0].endswith(".dll.lsaxbak"), baks)

    # --- profiles
    rc, out = P.ps("Set-ProbeConfig.ps1", "-GtaRoot", gta, "-ProbeProfile", "PDB01")
    ini = open(os.path.join(scripts, "LSAXProbe", "probe.ini"), encoding="utf-8").read()
    native = os.path.join(scripts, "LSAXProbeSql", "e_sqlite3.dll")
    check("SET-PROBE-CONFIG PDB01 writes the absolute NativePath of the installed e_sqlite3.dll", rc == 0 and f"SqliteProbe.NativePath={native}" in ini
          and "SqliteProbe.Enabled=true" in ini and "@@" not in ini, ini)
    rc, out = P.ps("Hash-Probes.ps1", "-GtaRoot", gta)
    check("  ... install manifest updated (HASH-PROBES still exit 0)", rc == 0, out)
    for prof, must in (("PDB01-STEP1", ["SqliteProbe.Enabled=true"]), ("PDB01-LEAK", ["SqliteProbe.CloseOnAbort=false", "SqliteProbe.NativePath=" + native]),
                       ("PID01", ["IdentityProbe.Enabled=true"])):
        rc, out = P.ps("Set-ProbeConfig.ps1", "-GtaRoot", gta, "-ProbeProfile", prof)
        ini = open(os.path.join(scripts, "LSAXProbe", "probe.ini"), encoding="utf-8").read()
        check(f"SET-PROBE-CONFIG {prof}", rc == 0 and all(m in ini for m in must) and "AnchorProbe.Enabled=false" in ini, ini)
    rc, out = P.ps("Set-ProbeConfig.ps1", "-GtaRoot", gta, "-ProbeProfile", "PSL02")
    check("SET-PROBE-CONFIG rejects an unknown profile (no P-SL-02 profile exists)", rc == 1, out)
    evil = os.path.join(work, "evil", os.path.basename(pack_root))
    shutil.copytree(pack_root, evil)
    pth = os.path.join(evil, "install", "config", "probe.PID01.ini")
    with open(pth, encoding="utf-8") as fh:
        t = fh.read()
    with open(pth, "w", encoding="utf-8") as fh:
        fh.write(t.replace("AnchorProbe.Enabled=false", "AnchorProbe.Enabled=true"))
    rc, out = Pack(evil, a.pwsh).ps("Set-ProbeConfig.ps1", "-GtaRoot", gta, "-ProbeProfile", "PID01")
    check("SET-PROBE-CONFIG refuses any profile that enables AnchorProbe (P-SL-02)", rc == 2 and "AnchorProbe" in out, out)
    rc, out = P.ps("Set-ProbeConfig.ps1", "-GtaRoot", gta, "-ProbeProfile", "PSL01")
    check("SET-PROBE-CONFIG back to PSL01", rc == 0, out)

    # --- evidence folder
    rc, out = P.ps("Prepare-Evidence.ps1")
    envf = os.path.join(pack_root, "evidence-work", "MINIMAL", "ENVIRONMENT.txt")
    check("PREPARE-EVIDENCE-FOLDER creates evidence-work copies", rc == 0 and os.path.exists(envf), out)
    with open(envf, "a", encoding="utf-8") as fh:
        fh.write("Notes: owner text \u0451\u0401\u044a\r\n")
    rc, out = P.ps("Prepare-Evidence.ps1")
    check("PREPARE-EVIDENCE-FOLDER never overwrites the owner's files", rc == 0 and "\u0451\u0401\u044a" in open(envf, encoding="utf-8").read(), out)

    # --- smoke gates with SYNTHETIC fixtures
    log = os.path.join(scripts, "LSAXProbe", "probe-20261001.log")
    sql = os.path.join(scripts, "LSAXProbe", "sqlite-probe.log")

    def gate(step, cfg="MINIMAL"):
        return P.ps("Check-Log.ps1", "-GtaRoot", gta, "-Config", cfg, "-Step", step)

    def new_run(label):
        return P.ps("New-Run.ps1", "-GtaRoot", gta, "-Label", label, "-AssumeYes")

    rc, out = new_run("SMOKE-MINIMAL")
    check("START-NEW-RUN with no run files exits 0", rc == 0, out)
    append(log, fx_ctor(1, PROC1, 0, 0, "<none>", 777))
    rc, out = gate("S4")
    check("CHECK-LOG S4 OK on a correct fixture", rc == 0 and "SMOKE S4: OK" in out, out)
    rc, out = gate("S6")
    check("CHECK-LOG enforces step order (S6 before S5 -> exit 1)", rc == 1, out)
    append(log, fx_save("SGTA50003", 1))
    rc, out = gate("S5")
    check("CHECK-LOG S5 OK (one SAVEFILE_CHANGED signalSeen=1)", rc == 0 and "SMOKE S5: OK" in out, out)
    append(log, line("ABORTED", "frame=1 gameTime=1 cash=1000,2000,3000 pt=TOTAL_PLAYING_TIME=120500 flags=[x]"))
    append(log, fx_ctor(2, PROC1, 0, 0, "777 " + PROC1, 888, match="matches=1 [SGTA50003:W=]"))
    rc, out = gate("S6")
    check("CHECK-LOG S6 OK (load: one CTOR, same process, present=0, LOAD_MATCH of the S5 file)", rc == 0 and "SMOKE S6: OK" in out, out)
    append(log, fx_ctor(3, PROC1, 1, 888, "888 " + PROC1, 999, match="matches=1 [SGTA50003:W=]"))
    rc, out = gate("S7")
    check("CHECK-LOG S7 OK (Reload: present=1 with the persisted token)", rc == 0 and "SMOKE S7: OK" in out, out)
    append(log, line("TOKEN_PED_CHANGED", "oldPed=42 newPed=43 newPedHadToken=0 value=0 expected=999 retagOk=1 model=0x9B22DBAF"))
    rc, out = gate("S8")
    check("CHECK-LOG S8 OK (switch: no CTOR, newPedHadToken=0 retagOk=1)", rc == 0 and "SMOKE S8: OK" in out, out)
    P.ps("Set-ProbeConfig.ps1", "-GtaRoot", gta, "-ProbeProfile", "PDB01")
    append(log, fx_ctor(1, PROC2, 0, 0, "999 " + PROC1, 1111))
    append(sql, fx_sql_block(native, scripts) + line("SQL_CLOSED_ON_ABORT", "") + fx_sql_block(native, scripts))
    rc, out = gate("S9")
    check("CHECK-LOG S9 OK (two complete SQL blocks, nativeModule = LSAXProbeSql\\e_sqlite3.dll)", rc == 0 and "SMOKE S9: OK" in out, out)
    check("  ... S9 prints R-COMP-2 locations without gating (shadow-copy path shown as NO)", "inside LSAXProbeSql=NO" in out and "inside LSAXProbeSql=yes" in out, out)
    rc, out = gate("S10")
    check("CHECK-LOG S10 fails while probe.ini is not PSL01", rc == 10, out)
    P.ps("Set-ProbeConfig.ps1", "-GtaRoot", gta, "-ProbeProfile", "PSL01")
    rc, out = gate("S10")
    check("CHECK-LOG S10 OK after returning to PSL01", rc == 0 and "Smoke test complete" in out and "NOT runtime acceptance" in out, out)
    rc, out = gate("SUMMARY")
    check("CHECK-LOG SUMMARY prints counts and no verdict", rc == 0 and "CTOR = 4" in out and "no PASS/FAIL" in out, out)

    # negative smoke fixtures (each in a fresh run)
    def neg(name, steps, bad_step, bad_text, sqltext=None):
        new_run("NEG")
        for st, txt in steps:
            append(log, txt)
            r, o = gate(st)
            if r != 0:
                check(name + " (setup step " + st + ")", False, o)
                return
        append(log, bad_text)
        if sqltext:
            append(sql, sqltext)
        r, o = gate(bad_step)
        check(name, r == 10 and "FAILED - STOP" in o and "Do NOT continue to T1-T17" in o, o)

    s4 = fx_ctor(1, PROC1, 0, 0, "<none>", 777)
    neg("S4 fails when the first CTOR has domainInstanceInProcess=2", [], "S4", fx_ctor(2, PROC1, 0, 0, "<none>", 777))
    neg("S4 fails when no play-time candidate exists (pt= empty)", [], "S4", fx_ctor(1, PROC1, 0, 0, "<none>", 777, pt=""))
    neg("S4 fails on a PROBE_ERROR row", [], "S4", s4 + line("PROBE_ERROR", "TICK: NullReferenceException: fixture"))
    neg("S5 fails when the save shows signalSeen=0", [("S4", s4)], "S5", fx_save("SGTA50003", 0))
    neg("S5 fails when a save changes two files", [("S4", s4)], "S5", fx_save("SGTA50003", 1) + fx_save("SGTA50000", 1))
    s5 = fx_save("SGTA50003", 1)
    neg("S6 fails when LOAD_MATCH does not name the saved file", [("S4", s4), ("S5", s5)], "S6",
        fx_ctor(2, PROC1, 0, 0, "777", 888, match="matches=1 [SGTA50000:W=]"))
    neg("S6 fails when the load produced two CTOR rows", [("S4", s4), ("S5", s5)], "S6",
        fx_ctor(2, PROC1, 0, 0, "777", 888, match="matches=1 [SGTA50003:W=]") + fx_ctor(3, PROC1, 0, 0, "888", 889, match="matches=1 [SGTA50003:W=]"))
    s6 = fx_ctor(2, PROC1, 0, 0, "777 " + PROC1, 888, match="matches=1 [SGTA50003:W=]")
    neg("S7 fails when the token is absent after Reload()", [("S4", s4), ("S5", s5), ("S6", s6)], "S7",
        fx_ctor(3, PROC1, 0, 0, "888", 999))
    neg("S7 fails when Reload() starts a different process key", [("S4", s4), ("S5", s5), ("S6", s6)], "S7",
        fx_ctor(3, PROC2, 1, 888, "888", 999))
    s7 = fx_ctor(3, PROC1, 1, 888, "888 " + PROC1, 999)
    neg("S8 fails when the new ped already had the token", [("S4", s4), ("S5", s5), ("S6", s6), ("S7", s7)], "S8",
        line("TOKEN_PED_CHANGED", "oldPed=42 newPed=43 newPedHadToken=1 value=999 expected=999 retagOk=1 model=0x0"))
    s8 = line("TOKEN_PED_CHANGED", "oldPed=42 newPed=43 newPedHadToken=0 value=0 expected=999 retagOk=1 model=0x0")
    neg("S9 fails on SQL_FAIL", [("S4", s4), ("S5", s5), ("S6", s6), ("S7", s7), ("S8", s8)], "S9", "",
        sqltext=fx_sql_block(native, scripts) + fx_sql_block(native, scripts, fail=True))
    neg("S9 fails when nativeModule is another sqlite DLL", [("S4", s4), ("S5", s5), ("S6", s6), ("S7", s7), ("S8", s8)], "S9", "",
        sqltext=fx_sql_block(native, scripts) + fx_sql_block(native, scripts).replace("nativeModule=" + native, "nativeModule=C:\\Other\\sqlite3.dll"))

    # --- START-NEW-RUN moves, never deletes
    rc, out = new_run("bad label!")
    check("START-NEW-RUN rejects an invalid label (exit 1)", rc == 1, out)
    run_files = sorted(f for f in os.listdir(os.path.join(scripts, "LSAXProbe")) if f.endswith((".log",)))
    content = {f: sha(os.path.join(scripts, "LSAXProbe", f)) for f in run_files}
    rc, out = new_run("KEEP-TEST")
    runs = os.path.join(scripts, "LSAXProbe", "runs")
    kept = [d for d in os.listdir(runs) if d.startswith("KEEP-TEST-")]
    moved_ok = kept and all(sha(os.path.join(runs, kept[0], f)) == h for f, h in content.items())
    check("START-NEW-RUN moves run files byte-identically into runs/<label>-<UTC>/", rc == 0 and moved_ok, out)
    check("  ... probe.ini, manifest and install reports stay in place",
          all(os.path.exists(os.path.join(scripts, "LSAXProbe", f)) for f in ("probe.ini", "LSAX-PACK-INSTALL-MANIFEST.tsv")))

    # --- COLLECT-EVIDENCE
    home = os.path.expanduser("~")
    append(log, fx_ctor(1, PROC2, 0, 0, "<none>", 5) + line("CTOR", f"domainInstanceInProcess=9 process=x saveRoot={home}/Documents/Rockstar Games/GTA V/Profiles baseDir={scripts}/ gta={gta}"))
    with open(os.path.join(scripts, "LSAXProbe", "private-notes.txt"), "w") as fh:
        fh.write("not evidence\n")
    before = snapshot(base)
    rc, out = P.ps("Collect-Evidence.ps1", "-GtaRoot", gta, "-Config", "MINIMAL", "-Phase", "SMOKE", "-IncludeShvdnLogExcerpt")
    zips = sorted(f for f in os.listdir(os.path.join(pack_root, "evidence-out")) if f.endswith(".zip"))
    check("COLLECT-EVIDENCE exits 0 and names the ZIP LSAX-PHASE0-RUNTIME-EVIDENCE-YYYYMMDD-HHMM.zip",
          rc == 0 and len(zips) == 1 and len(zips[0]) == len("LSAX-PHASE0-RUNTIME-EVIDENCE-20261001-2015.zip"), (out, zips))
    check("COLLECT-EVIDENCE changes nothing in the GTA tree or the saves", snapshot(base) == before)
    if zips:
        zp = os.path.join(pack_root, "evidence-out", zips[0])
        with zipfile.ZipFile(zp) as z:
            names = z.namelist()
            texts = {n: z.read(n).decode("utf-8", "replace") for n in names}
        root = zips[0][:-4] + "/"
        check("evidence ZIP entries use '/' and one root folder", all(n.startswith(root) and "\\" not in n for n in names), names[:5])
        rels = [n[len(root):] for n in names]
        must = ["probe-run/current/probe-20261001.log", "probe-bookkeeping/probe.ini", "probe-bookkeeping/LSAX-PACK-INSTALL-MANIFEST.tsv",
                "PROBE-DLL-SHA256.txt", "owner/ENVIRONMENT.txt", "owner/TEST-LOG.tsv", "owner/smoke-state.txt", "owner/check-log-output.txt",
                "pack/SHA256SUMS.txt", "pack/DEPLOYMENT-MANIFEST.tsv", "pack/PACK-INFO.txt", "AUTO-DETECTED.txt", "COLLECT-INFO.txt",
                "REDACTION.txt", "EVIDENCE-SHA256SUMS.txt", "shvdn-log-excerpt.txt"]
        check("evidence ZIP contains every required item", all(m in rels for m in must), sorted(set(must) - set(rels)))
        check("evidence ZIP contains the moved runs", any(r.startswith("probe-run/runs/KEEP-TEST-") for r in rels), rels)
        bad = [r for r in rels if "OtherMod" in r or "SGTA" in r or r.endswith((".dll", ".db", ".lsaxbak", ".exe", ".asi")) or "private-notes" in r]
        check("evidence ZIP contains no save, DLL, other mod, DB, backup or unrelated file", not bad, bad)
        alltext = "\n".join(texts.values())
        check("redaction: no absolute fake-tree path, home path or user name remains",
              base not in alltext and home not in alltext and "Alice" not in alltext,
              [n for n, t in texts.items() if base in t or home in t or "Alice" in t])
        check("redaction placeholders present", "<SCRIPTS>" in alltext and "<GTA>" in alltext and "C:\\Users\\<USER>" in alltext, "")
        check("REDACTION.txt lists original SHA-256 per file", "original_sha256" in texts[root + "REDACTION.txt"], "")
        check("SHVDN excerpt keeps only probe/SQLite lines", "LsaxPhase0Probe" in texts[root + "shvdn-log-excerpt.txt"]
              and "Unrelated mod message" not in texts[root + "shvdn-log-excerpt.txt"], texts.get(root + "shvdn-log-excerpt.txt"))
        check("owner Cyrillic text survives collection", "\u0451\u0401\u044a" in texts[root + "owner/ENVIRONMENT.txt"], "")
        sums_ok = True
        with zipfile.ZipFile(zp) as z:
            for l in texts[root + "EVIDENCE-SHA256SUMS.txt"].splitlines():
                h, rel = l[:64], l[66:]
                if hashlib.sha256(z.read(root + rel)).hexdigest() != h:
                    sums_ok = False
        check("EVIDENCE-SHA256SUMS.txt matches the ZIP content", sums_ok)
        stag = [d for d in os.listdir(os.path.join(pack_root, "evidence-out")) if d.startswith("_staging-")]
        check("COLLECT-EVIDENCE removed only its own staging folder", not stag, stag)

    # --- local build (optional)
    if not a.skip_build and shutil.which("dotnet"):
        rc, out = P.ps("Build-Probes.ps1")
        rep = os.path.join(pack_root, "build-local", "BUILD-LOCAL-REPORT.txt")
        txt = open(rep, encoding="utf-8").read() if os.path.exists(rep) else ""
        check("BUILD-PROBES-WINDOWS (run with pwsh on Linux) rebuilds all 11 payload files", rc == 0 and txt.count("\t") >= 33, out[-2000:])
        check("  ... same SDK -> every file MATCHes the pack payload", "DIFFERENT" not in txt and txt.count("MATCH") == 11, txt)
        rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-UseLocalBuild", "-AssumeYes")
        check("INSTALL -UseLocalBuild works with the local build", rc == 0 and "LOCAL build" in out, out)

    # --- REMOVE
    with open(os.path.join(scripts, "LSAXProbe", "probe.ini"), "a") as fh:
        fh.write("; owner edit\n")
    before = snapshot(base)
    rc, out = P.ps("Remove-Probes.ps1", "-GtaRoot", gta, stdin="no\n")
    check("REMOVE aborts without YES and deletes nothing", rc == 4 and snapshot(base) == before, out)
    rc, out = P.ps("Remove-Probes.ps1", "-GtaRoot", gta, "-AssumeYes")
    after = snapshot(base)
    added, removed, changed = changes(before, after)
    check("REMOVE keeps a changed own file and exits 8", rc == 8 and os.path.exists(os.path.join(scripts, "LSAXProbe", "probe.ini")), out)
    check("REMOVE deleted exactly the unchanged installed files", sorted(removed) == sorted(
        ["Grand Theft Auto V/scripts/" + r[2] for r in manifest_rows]), removed)
    check("REMOVE changed only the manifest", changed == ["Grand Theft Auto V/scripts/LSAXProbe/LSAX-PACK-INSTALL-MANIFEST.tsv"] and not added, (changed, added))
    check("REMOVE removed the now-empty LSAXProbeSql folder", not os.path.exists(os.path.join(scripts, "LSAXProbeSql")))
    check("REMOVE kept logs/evidence and the unrelated file in LSAXProbe", os.path.exists(os.path.join(scripts, "LSAXProbe", "runs"))
          and os.path.exists(os.path.join(scripts, "LSAXProbe", "private-notes.txt")))
    # second pass: restore the ini to the profile, reinstall, remove with evidence deletion
    os.remove(os.path.join(scripts, "LSAXProbe", "probe.ini"))
    os.remove(os.path.join(scripts, "LSAXProbe", "LSAX-PACK-INSTALL-MANIFEST.tsv"))
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-AssumeYes")
    check("re-INSTALL after partial removal", rc == 0, out)
    rc, out = P.ps("Remove-Probes.ps1", "-GtaRoot", gta, "-DeleteEvidence", "-AssumeYes", stdin="no thanks\n")
    check("REMOVE -DeleteEvidence -AssumeYes still asks and keeps evidence without the typed phrase",
          rc == 0 and "evidence kept" in out and os.path.exists(os.path.join(scripts, "LSAXProbe", "runs")), out)
    rc, out = P.ps("Remove-Probes.ps1", "-GtaRoot", gta, stdin="YES\n")
    check("REMOVE with nothing installed exits 6 and deletes nothing", rc == 6, out)
    # reinstall once more to exercise the typed evidence deletion
    P.ps("Install-Probes.ps1", "-GtaRoot", gta, "-AssumeYes")
    rc, out = P.ps("Remove-Probes.ps1", "-GtaRoot", gta, "-DeleteEvidence", stdin="YES\nDELETE EVIDENCE\n")
    left = sorted(os.listdir(os.path.join(scripts, "LSAXProbe"))) if os.path.exists(os.path.join(scripts, "LSAXProbe")) else []
    check("REMOVE -DeleteEvidence with the typed phrase deletes evidence file by file, keeps unknown files", rc == 0 and left == ["private-notes.txt"], (out[-1500:], left))
    os.remove(os.path.join(scripts, "LSAXProbe", "private-notes.txt"))
    os.rmdir(os.path.join(scripts, "LSAXProbe"))
    final = snapshot(base)
    check("after removal the fake GTA tree and saves equal the original byte for byte", final == before0,
          changes(before0, final))

    # --- custom ScriptsLocation
    cs_base = os.path.join(work, "t-custom")
    os.makedirs(cs_base)
    cs = make_gta(cs_base, ini="ScriptsLocation=\"scripts2\"\n")
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", cs, "-AssumeYes")
    check("custom ScriptsLocation that does not exist -> exit 1", rc == 1 and "does not exist" in out, out)
    os.makedirs(os.path.join(cs, "scripts2"))
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", cs, stdin="no\n")
    check("custom ScriptsLocation needs explicit YES", rc == 4 and "ScriptsLocation=" in out, out)
    rc, out = P.ps("Install-Probes.ps1", "-GtaRoot", cs, "-AssumeYes")
    check("custom ScriptsLocation: installs into <GTA>/scripts2", rc == 0 and os.path.exists(os.path.join(cs, "scripts2", "LsaxPhase0Probe.dll"))
          and not os.path.exists(os.path.join(cs, "scripts", "LsaxPhase0Probe.dll")), out)

    # --- static scan for PowerShell 6+/7-only syntax and APIs (Windows PowerShell 5.1 itself is not available)
    scan = r'''
$bad = New-Object System.Collections.ArrayList
foreach ($f in Get-ChildItem -LiteralPath $args[0] -Filter *.ps1) {
  $tokens = $null; $errs = $null
  $ast = [System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$errs)
  foreach ($e in $errs) { [void]$bad.Add("$($f.Name): parse error $($e.Message)") }
  foreach ($t in $tokens) {
    if ($t.Kind -in @('QuestionQuestion','QuestionQuestionEquals','QuestionDot','QuestionLBracket','AndAnd','OrOr')) {
      [void]$bad.Add("$($f.Name):$($t.Extent.StartLineNumber): PS7-only operator $($t.Text)") }
  }
  $found = $ast.FindAll({ param($n)
      $n -is [System.Management.Automation.Language.TernaryExpressionAst] -or
      $n -is [System.Management.Automation.Language.PipelineChainAst] }, $true)
  foreach ($n in $found) { [void]$bad.Add("$($f.Name):$($n.Extent.StartLineNumber): PS7-only syntax") }
  $text = [System.IO.File]::ReadAllText($f.FullName)
  foreach ($p in @('-Parallel','-AsHashtable','-AdditionalChildPath','-AsByteStream','-Encoding utf8NoBOM','$IsWindows','$IsLinux',
                   '$IsMacOS','GetRelativePath','Join-String','Get-Error','Test-Json','-SkipCertificateCheck','ConvertFrom-Json -Depth')) {
    if ($text.IndexOf($p, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { [void]$bad.Add("$($f.Name): PS6+/.NET Core-only API '$p'") }
  }
}
$bad | ForEach-Object { Write-Output $_ }
Write-Output ("SCANNED " + @(Get-ChildItem -LiteralPath $args[0] -Filter *.ps1).Count)
'''
    sp = os.path.join(work, "scan.ps1")
    with open(sp, "w") as fh:
        fh.write(scan)
    p = subprocess.run([a.pwsh, "-NoProfile", "-File", sp, os.path.join(pack_root, "scripts", "lib")], capture_output=True, text=True)
    lines = [l for l in p.stdout.splitlines() if l.strip()]
    check("static scan: no PowerShell 6+/7-only syntax or API in any scripts/lib/*.ps1 (Windows PowerShell 5.1 target)",
          p.returncode == 0 and lines and lines[-1] == "SCANNED 10" and len(lines) == 1, p.stdout + p.stderr)

    # --- .cmd wrappers (static only: cmd.exe is not available here)
    for f in sorted(os.listdir(os.path.join(pack_root, "scripts"))):
        if f.endswith(".cmd"):
            data = open(os.path.join(pack_root, "scripts", f), "rb").read()
            target = [l for l in data.decode("ascii").split("\r\n") if "-File" in l]
            ps1 = target[0].split("lib\\")[1].split('"')[0] if target else ""
            check(f"{f}: ASCII, CRLF, calls an existing scripts\\lib\\{ps1}", all(b < 128 for b in data) and b"\n" not in data.replace(b"\r\n", b"")
                  and ps1 and os.path.exists(os.path.join(pack_root, "scripts", "lib", ps1)) and "exit /b %LSAX_RC%" in data.decode())

    shutil.rmtree(work, ignore_errors=True)
    bad = [r for r in RESULTS if not r[1]]
    print(f"\nOFFLINE helper-script tests: {len(RESULTS) - len(bad)}/{len(RESULTS)} passed (pwsh 7 on Linux, fake GTA tree)")
    print("Windows PowerShell 5.1 / cmd.exe execution: INCONCLUSIVE (not available in this environment)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
