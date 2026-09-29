# LSAX Phase 0 — Runtime Validation Pack: report

**Final status: RUNTIME_VALIDATION_PACK_READY + OWNER_RUNTIME_ACTION_REQUIRED.**
**BLOCKER B-01: OPEN** (closes only after the owner's runtime evidence is reviewed by the independent reviewer).

This task was web/cloud packaging and offline verification only. **No GTA V runtime was available.** Nothing in this
pack has been installed on the owner's PC, no game was launched, no probe was loaded in SHVDN, no save/load test was
executed, and no helper script has run on Windows. Results below are labelled **SOURCE VERIFIED**,
**OFFLINE VERIFIED**, **OWNER_RUNTIME_ACTION_REQUIRED** or **INCONCLUSIVE**. The label "RUNTIME VERIFIED" is not used.
SPEC_APPROVED is not granted, no production LSAX code was written and Stage 1 has not started.

## 1. Source baseline

| Item | Value | Label |
|---|---|---|
| Repository | `Lazarev33/LSAX-Los-Santos-Auto-Exchange` | SOURCE VERIFIED |
| Source branch | `claude/phase0-correction-1` (remote head `a3701019a3c64dd859fb1e00577db47360f64066`, unchanged) | SOURCE VERIFIED |
| Baseline commit | `a3701019a3c64dd859fb1e00577db47360f64066` — "Correction pass 1 C0-18/C0-19: record push result and final status" | SOURCE VERIFIED |
| Baseline status | OFFLINE_CORRECTION_COMPLETE — RUNTIME_VALIDATION_REQUIRED; remaining blocker P0-01 / B-01 | SOURCE VERIFIED (`00-INDEX.md`, `risks.md`) |

No baseline fact differed from the task statement.

## 2. Branch

`claude/phase0-runtime-validation-pack`, created from exactly `a3701019a3c64dd859fb1e00577db47360f64066`.
Not modified: `main` (`ec56878a5a4f2fd13cffc2d04c76feb71f81058e`), `claude/phase0-correction-1` (`a3701019…`),
`claude/focused-thompson-ilnspm` (`f6aff47d1dbea94576d6aae1f60bd17102d549cc`), PR #1, the DRAFT1 and DRAFT2 releases.
No PR was opened and nothing was merged.

## 3. Final commit

A file cannot contain the SHA of the commit that adds it. The pack, its builder/tests and this report are added by
one commit on `claude/phase0-runtime-validation-pack`; its SHA is the branch head and is given in the session's final
status message. `release/LSAX-PHASE0-RUNTIME-VALIDATION-PACK.zip` is committed in that same commit.

## 4. DRAFT2 hash verification

| File | Expected SHA-256 | Observed | Label |
|---|---|---|---|
| `release/LSAX-MASTER-SPEC-v1.0-DRAFT2.zip` | `4c1e5ed5e54a4418a440ff4600c7faea86b5fa801fce21c59c8dbd943a93aa12` | identical (before work, at every build, after work) | OFFLINE VERIFIED |
| `release/LSAX-MASTER-SPEC-v1.0-DRAFT1.zip` | `281f52f6e989ed7de93d4af7d61e25e9a2369fa7d74856f5d666357896cccd16` | identical | OFFLINE VERIFIED |

The builder refuses to run if the DRAFT2 hash differs or if `phase0-probes/shvdn/`, `probe.ini.sample`,
`README-PROBES.md` or the DRAFT1/DRAFT2 release files differ from the baseline commit
(`git diff --quiet a3701019… -- …`).

## 5. Probe sources inspected (byte-identical to the baseline; copied unchanged into `source/`)

| File | SHA-256 |
|---|---|
| `LsaxPhase0Probe/AnchorCarrierProbe.cs` | `35f9aefbc71c273f3e193a5bb034eb1e12536884a5494d1bee8a606a9384851d` |
| `LsaxPhase0Probe/IdentityProbe.cs` | `349ce3806c1bf6d106f58fd763acff54aae5555d37f0c5c38de8dc184462d063` |
| `LsaxPhase0Probe/ProbeCore.cs` | `6a7ab321ffdd4c21044e9b9efb124b0ec80afef96fc937b6f10183701d5b6aeb` |
| `LsaxPhase0Probe/SessionSignalProbe.cs` | `579dbda2970ef16cac5fa350371507db6d78567ffdc90c849ddf0b1a8f549136` |
| `LsaxPhase0Probe/LsaxPhase0Probe.csproj` | `7e3c3e8b1e92600670645ebbcdf746cce411e6cccf91bf6869b2881db1d727d0` |
| `LsaxPhase0SqliteProbe/SqliteReloadProbe.cs` | `d61fce241983df231cc91795cd9fa63af669df95fe47315dafc0a1271e02b68f` |
| `LsaxPhase0SqliteProbe/LsaxPhase0SqliteProbe.csproj` | `09db1206827b0f81825f1643302d17b7f27868cd2fe6d7ffd74ca11468eea6dd` |
| `probe.ini.sample` | `4592c9dba26719bb5ea50cce8db7d703e3cd244a540101f4121555028b91b02d` |
| `README-PROBES.md` (copied to `upstream/`) | `d749e57c63fdc0df9c1235a6b5cfa9a18293db60155f4a86807c884ac513ce93` |

Facts taken from the sources (SOURCE VERIFIED): probes log to `AppDomain.BaseDirectory\LSAXProbe\` (= the SHVDN
scripts folder); `P-SL-02` is enabled only with `AnchorProbe.Enabled=true` **and** `AnchorProbe.Consent=I_USE_A_DISPOSABLE_SAVE`;
the `CTOR` row logs `saveRoot` (contains the Windows user name) and `SQL_CTOR` logs `baseDir`/`asmLocation`.
SHVDN facts at pinned `scripthookvdotnet@56ba3bfb`: recursive loading of every managed `*.dll` and every `*.cs`/`*.vb`
under the scripts folder (`ScriptDomain.cs` 1236–1241), deletion of `ScriptHookVDotNet*.dll` copies there, native DLLs
skipped (`IsManagedAssembly`), `ShadowCopyFiles="true"` with `ShadowCopyDirectories=scriptPath` (425–427), relative
`ScriptsLocation` resolved against the working directory, `AutoLoadScripts`, console key F4, no reload key by
default, console commands `Help`, `Clear`, `Reload`, `Start`, `StartAllScripts`, `Abort`, `AbortAll`, `ListScripts`
(`DllMain.cpp`).

## 6. Build environment

Cloud Linux container (no Windows, no GTA V): .NET SDK 8.0.131, PowerShell 7.4.6 (portable copy in the session
scratchpad, used only for tests), Python 3.11.15 with `pefile` and `dnfile`, NuGet cache with the packages restored
from nuget.org. PowerShell Gallery was not reachable (proxy 403), so PSScriptAnalyzer could not be used.

## 7. Build results (OFFLINE VERIFIED)

- Build commands (both probes): `dotnet build <csproj> -c Release -p:DebugType=none -p:ContinuousIntegrationBuild=true
  -p:IncludeSourceRevisionInInformationalVersion=false -o <out>`; the SQLite probe additionally
  `-p:RuntimeIdentifier=win-x64`. No warnings are allowed (`TreatWarningsAsErrors=true` in both projects).
- Two clean builds from separate copies are byte-identical. `IncludeSourceRevisionInInformationalVersion=false` was
  added after finding that the .NET 8 SDK appends the git commit to `AssemblyInformationalVersion` when the sources sit in a
  git repository (in-repo builds differed from temp builds only by `1.0.0+a3701019…`); with the flag, in-repo and
  out-of-repo builds are identical.
- Output file set is exactly the expected 1 + 10 files (checked; nothing invented, nothing missing).
- PE checks: both probe DLLs PE32+ AMD64 managed; all 8 dependency DLLs managed; `e_sqlite3.dll` native PE32+ AMD64.
  Both probes reference `ScriptHookVDotNet3 3.6.0.0` (resolves on SHVDN 3.7.x: same major, installed ≥ referenced —
  SOURCE VERIFIED); no `ScriptHookVDotNet*.dll` is in the payload.
- Every dependency is byte-identical to a file inside its NuGet package (`microsoft.data.sqlite.core 8.0.11`,
  `sqlitepclraw.* 2.1.6`, `system.buffers 4.4.0`, `system.memory 4.5.3`, `system.numerics.vectors 4.4.0`,
  `system.runtime.compilerservices.unsafe 4.5.2`); `e_sqlite3.dll` = `sqlitepclraw.lib.e_sqlite3/2.1.6/runtimes/win-x64/native/e_sqlite3.dll`.
- `dotnet nuget verify --all`: exit 0 for all nine packages, nuget.org repository signature present on all, Microsoft
  author signature on three; certificate revocation could not be checked offline (NU3018/NU3028) → **INCONCLUSIVE**
  for revocation only. Details per package in `install/BUILD-INFO.txt`.
- The pack ZIP is reproducible: rebuilding from the same tree gives the same ZIP bytes (checked twice).

## 8. Windows binaries included?

**Yes** — `install/` contains the Windows payload (net48 x64 probe DLLs, their managed dependencies and the upstream
win-x64 `e_sqlite3.dll`). Label: **OFFLINE VERIFIED (build)** — compiled from the unchanged DRAFT2 sources with the real
.NET SDK, dependencies byte-identical to signed nuget.org packages. This does **not** show that they load or work in
GTA V / SHVDN: **OWNER_RUNTIME_ACTION_REQUIRED**. The owner can also rebuild locally
(`scripts\BUILD-PROBES-WINDOWS.cmd`, .NET SDK 8+) and install that build with `-UseLocalBuild`.

## 9. Exact deployment file list (destination relative to the SHVDN scripts folder)

| Destination | SHA-256 |
|---|---|
| `LsaxPhase0Probe.dll` | `5644012cbef50d538f6d239347dc6d289b061c7f910af9fc9afac73feb08e10f` |
| `LSAXProbeSql/LsaxPhase0SqliteProbe.dll` | `616daf27b41cc117a66557689b8f70176e9f68902824f217a0a61043a1ed5a3e` |
| `LSAXProbeSql/Microsoft.Data.Sqlite.dll` | `742291e9f1953949c05ae9325b8454c962bdf1992197078f8acea2c81d14e033` |
| `LSAXProbeSql/SQLitePCLRaw.batteries_v2.dll` | `ff8ba48fba8c4c75af4d2cea16eb236e02b811ed20f8e36e7d04c79cb98a45df` |
| `LSAXProbeSql/SQLitePCLRaw.core.dll` | `c33995427edd44fa641cf702df8b63cc82cb7054dd984dc8277d15ee7c958874` |
| `LSAXProbeSql/SQLitePCLRaw.provider.dynamic_cdecl.dll` | `6c5a7905456018eb99c214644a25f2a93542e52aa0083a18f76ffeff408d33fc` |
| `LSAXProbeSql/System.Buffers.dll` | `9444b5a41a816b193c033bec199d74cdfc8298ed8300a3c39a4e953dec137494` |
| `LSAXProbeSql/System.Memory.dll` | `41b5e1a4c59abdb1ce1467f58c3d9fd06d39dff4fc61d500a2410fece8037f4b` |
| `LSAXProbeSql/System.Numerics.Vectors.dll` | `a044d77edb6e8db4053bf67cc671e7687c226c1b9b0963a81ebe359ce79dfdf7` |
| `LSAXProbeSql/System.Runtime.CompilerServices.Unsafe.dll` | `1ad2dd7225d5162a0fd3a3b337a1949448520e3130a4bc8e010ec02f76097500` |
| `LSAXProbeSql/e_sqlite3.dll` | `dccbabb2bc7e7d4302c44d9ce41b70721a7d0914fa4d289e2f340d39766ad102` |
| `LSAXProbe/probe.ini` | generated from `install/config/probe.<profile>.ini` (PSL01, PDB01-STEP1, PDB01, PDB01-LEAK, PID01) |

Bookkeeping written only inside `LSAXProbe/`: `LSAX-PACK-INSTALL-MANIFEST.tsv`, `install-report-<UTC>.txt`,
`install-backup/<UTC>/*.lsaxbak` (only when a same-name probe file is replaced), `runs/<label>-<UTC>/` (START-NEW-RUN).
Layout follows DRAFT2 README §3 (main DLL in the scripts root, SQLite probe isolated in `LSAXProbeSql/`).
Profiles differ from the DRAFT2 `probe.ini.sample` only in the keys listed (checked by the builder):
PSL01 none; PDB01-STEP1 `SqliteProbe.Enabled=true`; PDB01 + `NativePath=<scripts>\LSAXProbeSql\e_sqlite3.dll`;
PDB01-LEAK + `CloseOnAbort=false`; PID01 `IdentityProbe.Enabled=true`. `AnchorProbe` is disabled in every profile.

## 10. Helper scripts

All are `.cmd` wrappers (ASCII, CRLF) calling Windows PowerShell 5.1 scripts in `scripts\lib\` (ASCII,
StrictMode 2). Every script refuses to run while a GTA process is running, asks for the GTA path (or takes
`-GtaRoot`) and never guesses it, only reads `ScriptHookVDotNet.ini`, and exits non-zero on failure.

| Script | Behaviour |
|---|---|
| `HASH-PROBES.cmd` | verifies the extracted pack against `SHA256SUMS.txt`; with `-GtaRoot`, the installed files against the install manifest; prints both DLL hashes; writes nothing |
| `PREPARE-EVIDENCE-FOLDER.cmd` | copies `evidence-template\` to `evidence-work\` in the pack folder; never overwrites |
| `BUILD-PROBES-WINDOWS.cmd` | optional local build into `build-local\`; compares with the pack payload (MATCH / DIFFERENT) |
| `INSTALL-PROBES.cmd` | verifies payload hashes; requires `GTA5.exe` (rejects Enhanced-only), `ScriptHookV.dll`, `ScriptHookVDotNet.asi`; honours `ScriptsLocation` (explicit YES if non-default), stops on `AutoLoadScripts=false`; refuses if another `LsaxPhase0*.dll` exists elsewhere under scripts or a `.cs`/`.vb` is in the probe folders; prints every destination, asks YES; copies only the payload and `probe.ini`; backs up same-name probe files as `*.lsaxbak`; verifies each copy; unblocks only its own copied files; records same-name dependency DLLs of other mods (relative path + file version) for R-COMP-2 |
| `SET-PROBE-CONFIG.cmd` | switches `probe.ini` to a profile; backs up the previous one; refuses any profile that enables `AnchorProbe` |
| `START-NEW-RUN.cmd` | moves (never deletes) the current run's probe files into `LSAXProbe\runs\<label>-<UTC>\` |
| `CHECK-LOG.cmd` | read-only; smoke gates S4–S10 in order, or `SUMMARY`; reads logs with `FileShare.ReadWrite` so a probe writing at the same moment never loses a line; never issues PASS/FAIL |
| `COLLECT-EVIDENCE.cmd` | collects only the listed evidence into `LSAX-PHASE0-RUNTIME-EVIDENCE-YYYYMMDD-HHMM.zip`; redacts paths (GTA, scripts, Documents, profile, `C:\Users\<name>`) and records each file's original SHA-256; optional SHVDN log excerpt (probe/SQLite lines only); ZipArchive with `/` entry names, `Compress-Archive` fallback |
| `REMOVE-PROBES.cmd` | deletes exactly the manifest files whose SHA-256 is unchanged; keeps changed files (exit 8); removes only empty folders; evidence deleted only with `-DeleteEvidence` and the typed phrase `DELETE EVIDENCE`; never touches saves |

Offline tests (`phase0-probes/tools/test_runtime_pack.py`, run by `build_runtime_pack.py --verify` on the extracted
ZIP): **116/116 passed** with PowerShell 7.4.6 on Linux against a fake GTA tree (fake `GTA5.exe`, SHV/SHVDN files,
another mod with its own `System.Memory.dll` and `.cs`, fake saves). Covered: pack verification and tamper detection;
missing/invalid GTA path, Enhanced-only, missing SHVDN, `AutoLoadScripts=false`, declined confirmation, unknown
profile, duplicate probe DLL, game process running (a process named `GTA5`); installation writes only the three
destinations and changes no existing file; hashes; idempotent reinstall; same-name backup; all profiles incl.
refusal of an AnchorProbe profile; smoke gates S4–S10 positive, 12 negative fixtures, step-order enforcement and the
S10 profile check (synthetic log lines in the probes' format, used only as test fixtures); START-NEW-RUN; COLLECT-EVIDENCE content, exclusions, redaction,
checksums, Cyrillic owner text; local build (all 11 files MATCH) and `-UseLocalBuild`; REMOVE (decline, changed
file kept, typed evidence deletion); after removal the fake tree and saves are byte-identical to the start; custom
`ScriptsLocation`; `.cmd` wrappers statically; a static AST scan finding no PowerShell 6+/7-only syntax or API.
Two defects found by these tests were fixed before packaging (a `$null` answer to the path prompt; an empty-result
`.Count` under StrictMode).
**INCONCLUSIVE:** execution under Windows PowerShell 5.1 and `cmd.exe` (not available here); behaviour with real
GTA/SHVDN files.

## 11. Package

| Item | Value |
|---|---|
| ZIP | `release/LSAX-PHASE0-RUNTIME-VALIDATION-PACK.zip` (1 303 409 bytes, 65 entries = 64 files + `SHA256SUMS.txt`) |
| ZIP SHA-256 | `b0e4ac392ae7b9ded07df065341e54e693a33ab0d44621f28dbdc67d4c3b8232` (also in `.zip.sha256`) |
| Builder | `phase0-probes/tools/build_runtime_pack.py [--verify]` |
| Pack sources | `runtime-validation-pack/` (docs, scripts, profiles, templates) |

## 12. Clean-extraction verification (OFFLINE VERIFIED)

`build_runtime_pack.py --verify` extracts the ZIP into a fresh temporary folder, checks `testzip()`, that every
entry is under the single root folder with `/` separators, that all 64 `SHA256SUMS.txt` lines match (64/64) and that
the list covers exactly the extracted files; then runs the 116 helper tests on that extraction. Existing repository
checks after the work: `regress/run_regressions.py` PASS, `tools/xref_check.py` PASS.

## 13. Owner actions (OWNER_RUNTIME_ACTION_REQUIRED; nothing was asked of the owner during this task)

1. Download `LSAX-PHASE0-RUNTIME-VALIDATION-PACK.zip`, check its SHA-256, extract outside the GTA folder.
2. Read `00-RUN-ME-FIRST-RU.md`; close GTA; back up the profile/save folder and the scripts folder; keep important
   saves in two or more copies; record GTA build, ScriptHookV, exact SHVDN version and FULL MODPACK / MINIMAL.
3. `HASH-PROBES.cmd`, `PREPARE-EVIDENCE-FOLDER.cmd`, (optional) `BUILD-PROBES-WINDOWS.cmd`, `INSTALL-PROBES.cmd`.
4. Smoke test S1–S10 per configuration (`01-SMOKE-TEST-RU.md`). **If any smoke step fails: stop, do not continue
   through T1–T17, run `COLLECT-EVIDENCE.cmd -Phase SMOKE` and return the archive to the independent reviewer.**
5. Full validation T1–T17, every step 10× per configuration, T17 per U-01 (`02-…`).
6. P-DB-01 (`06-…`), P-ID-01 (`07-…`); UI-S1 is plan only (`05-…`); P-SL-02 optional, disabled (`08-…`).
7. `COLLECT-EVIDENCE.cmd` after each stage; send the ZIPs and their SHA-256 to the independent reviewer (`04-…`).
8. `REMOVE-PROBES.cmd`; restore saves from the owner's backup (`09-…`).

## 14. Unresolved items

| ID | Item | Label |
|---|---|---|
| U-01 | T17 repetition count (×10 or one session); pack default ×10 unless the reviewer rules otherwise | INCONCLUSIVE |
| U-02 | B-01 closure worded differently in README §6, SAVELOAD §6, RISK-REGISTER; pack presents the conjunction | SOURCE VERIFIED |
| U-03 | R-COMP-2 "`SQL_DEPENDENCY` location inside `LSAXProbeSql`" vs SHVDN shadow copying; `CHECK-LOG` prints, never gates | INCONCLUSIVE |
| U-04 | DRAFT2 `NativePath …\runtimes\win-x64\native\e_sqlite3.dll` does not exist in the RID build output; pack uses `…\LSAXProbeSql\e_sqlite3.dll` | OFFLINE VERIFIED |
| U-05 | SAVELOAD §6 PC-4/PC-5 summary wording vs README log rules (script-exception restarts; ≤ 2 s vs ≤ 10 s) | SOURCE VERIFIED |
| U-06 | Conditional steps T3 / T9 | SOURCE VERIFIED |
| U-07 | Console syntax `Reload()` (README writes `Reload`) | SOURCE VERIFIED |
| U-08 | P-DB-01 step 1 needs a fresh game process (preloaded native DLL stays loaded) | ASSUMPTION |
| U-09 | SQLite dependencies are loaded during T1–T17 because README §3 installs both components (kept) | SOURCE VERIFIED |
| U-10 | T14 is the only manual save-file action (owner only) | SOURCE VERIFIED |
| U-11 | P-ID-01 configuration not stated in DRAFT2 | SOURCE VERIFIED |
| — | UI-S1: no spike implemented (any spike would pick an OD-1 renderer); OD-1 and R-UI-1 stay OPEN | decision |
| — | Windows PowerShell 5.1 / `cmd.exe` execution of the helpers | INCONCLUSIVE |
| — | NuGet certificate revocation (offline) | INCONCLUSIVE |
| — | Whether the probes load and produce the expected rows in GTA V + SHVDN 3.7.x + modpack | OWNER_RUNTIME_ACTION_REQUIRED |
| — | B-01, R-DB-1/2/3, R-COMP-1/2, R-ENV-1, R-ECO-1, R-ID-4, R-UI-1 | OPEN |

Full text of U-01…U-11 with sources: `03-PASS-FAIL-RULES.md` in the pack.

## 15. Explicit statement

**The GTA V target runtime was NOT available to this task.** Claude had no access to the owner's Windows PC, GTA
installation or executable, scripts folder, saves, ScriptHookV, SHVDN, modpack, registry, processes or logs. Nothing
was installed on the owner's PC, GTA was not launched, no probe was loaded in SHVDN, no save/load test was executed,
no Windows helper script was executed on the owner's machine, and no runtime compatibility or runtime validation
result is claimed. Every cloud result above is OFFLINE VERIFIED at most. B-01 remains OPEN.

## Execution log RV-01 … RV-19

| Step | Result |
|---|---|
| RV-01 verify baseline (branch, commit, DRAFT2 hash, status) | done — all matched |
| RV-02 create `claude/phase0-runtime-validation-pack` from `a3701019…` | done |
| RV-03 inspect probe sources, README-PROBES, SAVELOAD §6, RISK-REGISTER, MASTER §20, SHVDN source | done |
| RV-04 inspect build environment and actual build output | done |
| RV-05 decide: Windows payload can be built trustworthily offline | yes (OFFLINE VERIFIED build) |
| RV-06 install/source layout, builder | done |
| RV-07 Russian smoke instructions S1–S10 | done (`01-SMOKE-TEST-RU.md`) |
| RV-08 Russian T1–T17 checklist + verbatim PASS/FAIL rules | done (`02-…`, `03-…`) |
| RV-09 P-DB-01 instructions | done (`06-…`) |
| RV-10 P-ID-01 instructions, LEGACY_TRUSTED = EMPTY | done (`07-…`) |
| RV-11 UI-S1 plan (no renderer chosen, no spike) | done (`05-…`) |
| RV-12 safe helper scripts | done (9 wrappers, 10 PowerShell files) |
| RV-13 ENVIRONMENT.txt / TEST-LOG.tsv templates (no pre-filled results) | done |
| RV-14 offline self-verification | done — 116/116 tests, lint, regressions PASS, xref PASS |
| RV-15 deterministic ZIP | done — reproducible |
| RV-16 extract and verify | done — 64/64 |
| RV-17 this report | done |
| RV-18 commit and push the branch | see the final status message |
| RV-19 final status | RUNTIME_VALIDATION_PACK_READY + OWNER_RUNTIME_ACTION_REQUIRED; B-01 OPEN |
