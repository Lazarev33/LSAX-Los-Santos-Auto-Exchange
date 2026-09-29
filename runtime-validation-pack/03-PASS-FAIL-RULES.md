# 03 — PASS / FAIL rules (DRAFT2 acceptance semantics, verbatim)

**Для владельца (RU):** вы **не** решаете PASS/FAIL. Вы выполняете шаги, записываете время и возвращаете логи.
Решение по каждому правилу ниже принимает **только независимый ревьюер** по возвращённым логам. «OK» от
`CHECK-LOG.cmd` в smoke-тесте — это не PASS, а только разрешение продолжать. Блокер **B-01 остаётся OPEN**, пока
ревьюер не подтвердит все условия его закрытия. Этот пакет не меняет и не ослабляет ни одного критерия DRAFT2.

**For the independent reviewer (EN):** this file reproduces the acceptance semantics of
`LSAX-MASTER-SPEC-v1.0-DRAFT2` **verbatim** (sections V-1…V-8, with source file, line numbers and the file SHA-256 at
baseline commit `a3701019a3c64dd859fb1e00577db47360f64066`). The pack adds no acceptance rule and removes none.
Nothing in this pack was executed on the target runtime; every result must come from the owner's returned logs.
Labels used: SOURCE VERIFIED, OFFLINE VERIFIED, OWNER_RUNTIME_ACTION_REQUIRED, INCONCLUSIVE.
The label "RUNTIME VERIFIED" is not used anywhere in this pack.

## How the three DRAFT2 statements of the B-01 closure condition combine

DRAFT2 states the B-01 closure condition in three places (V-1, V-2, V-3). They are not word-for-word identical.
The pack does **not** choose between them; it presents their **conjunction** as the condition the owner's evidence
must be able to satisfy (U-02):

1. PC-1, PC-2, PC-3, PC-4, PC-5, PC-7 and PC-8 all PASS, **every rule 10/10 on configuration (A) full modpack and
   (B) minimal** (V-1: README §6 heading and last paragraph);
2. **and** P-DB-01 passes (V-2: SAVELOAD §6);
3. **and** on the target runtime GTA V Legacy 1.0.3725.0 + ScriptHookVDotNet 3.7.x, full modpack (V-2, V-3).

PC-6 is informative. Any FAIL → LSAX-SAVELOAD-FEASIBILITY.md §7 (fallbacks degrade toward refusal) and a re-run of
the simulation before any approval request (V-1). UI-S1 and P-ID-01 are not part of B-01 but close R-UI-1 / R-ID-4
(V-3, V-5, V-8). P-SL-02 is not part of B-01 (V-7).

## Verbatim acceptance text

### V-1 README-PROBES §6 — PC-1…PC-8 and the B-01 closure rule

Source: `phase0-probes/README-PROBES.md` lines 80–107 (file SHA-256 `d749e57c63fdc0df9c1235a6b5cfa9a18293db60155f4a86807c884ac513ce93`), copied verbatim:

> ## 6. PASS / FAIL rules (decided offline from the logs; every rule 10/10 on configuration (A) and (B))
>
> - **PC-1 load detectability (A-SL-1, A-SL-9):** T6, T7, T12, T16 (and T9 if it reloads) each produce exactly one new
>   `CTOR`; T8 and T10 produce none. Any missing `CTOR` after a load = FAIL.
> - **PC-2 play-time anchor (A-SL-6, A-SL-13):** at least one candidate stat exists (appears in `CTOR_FP pt=`), never
>   appears in a `PT_DECREASED` row within one domain (T2–T5, T8, T10, T13, T17), and after every load (T6, T7, T12) its
>   value lies inside the `bracketLo … bracketHi` recorded for the loaded slot at save time (`LOAD_MATCH` lists that
>   file). At T16 its first value is ≤ 60 000 ms. Record the granularity G (smallest observed increment).
> - **PC-3 cash restore (A-SL-5):** after every load, `CTOR_FP cash=` equals the three wallets of the loaded file's
>   bracket (`LOAD_MATCH … :W=`), including the non-active protagonists.
> - **PC-4 save observability and timing (A-SL-7, A-SL-12, A-SL-4):** every save in T2–T4, T13, T17 yields exactly one
>   `SAVEFILE_CHANGED` with `signalSeen=1` (a save-flag transition ≤ 10 s before the file change); T14 yields
>   `signalSeen=0`; loads yield no `SAVEFILE_CHANGED`; zero `TICK_INTERLEAVE` rows.
> - **PC-5 reload discrimination (A-SL-10):** T11 → `TOKEN_AT_CTOR present=1` with the persisted value; T6, T7, T12, T16
>   → `present=0`.
> - **PC-6 Aborted timing (informative, A-SL-3):** record whether `ABORTED` shows the pre-load or post-load state.
>   Not a gate; LSAX never reads game state in `Aborted`.
> - **PC-7 token mechanics (A-SL-10):** `TOKEN_DECOR_REGISTER ok=1` (or already registered), `TOKEN_SET setOk=1
>   readBack=1` at every `CTOR`; T10 → `newPedHadToken=0 retagOk=1` for every switch.
> - **PC-8 load attribution (A-SL-8, A-SL-12, A-SL-14):** for every load of an LSAX-observed slot (T6, T7, T12),
>   `LOAD_MATCH matches=1` for the working candidate, the match is the loaded slot, and its wallet flag is `:W=` or
>   `:W?`; the loaded file's `SAVEFILE_INITIAL` hash equals its last `SAVEFILE_CHANGED` hash; in T17 no wallet shows a
>   change and an exact restore across two consecutive frames (`WALLET_CHANGE` pairs).
>
> B-01 closes only if PC-1, PC-2, PC-3, PC-4, PC-5, PC-7 and PC-8 all PASS. Any FAIL → apply
> LSAX-SAVELOAD-FEASIBILITY.md §7 (every fallback degrades toward refusal) and re-run the simulation before any
> approval request. Also record the SHVDN version logged at `CTOR` (R-ENV-1) and any `PROBE_ERROR` rows.

### V-2 LSAX-SAVELOAD-FEASIBILITY §6 — B-01 closure and the PC table

Source: `spec/LSAX-SAVELOAD-FEASIBILITY.md` lines 236–255 (file SHA-256 `c723cec1e7501c5c1e8d5fc6218e8111ec9c15e1f588529b992073743386cdd9`), copied verbatim:

> ## 6. Exact experiment required before SPEC_APPROVED
>
> Run **P-SL-01** (`phase0-probes/shvdn/LsaxPhase0Probe`, passive except for its own decorator; procedure, logs and
> cleanup in `phase0-probes/README-PROBES.md`) on the target runtime (GTA V Legacy 1.0.3725.0, ScriptHookVDotNet 3.7.x,
> full LSAX target modpack) and once with a minimal setup. **B-01 closes only when PC-1, PC-2, PC-3, PC-4, PC-5,
> PC-7 and PC-8 all pass 10/10 on the target runtime**, and P-DB-01 passes. PC-6 is informative.
>
> | PC | Assumption | Pass rule (summary; exact log rows in README-PROBES) |
> |---|---|---|
> | PC-1 | A-SL-1, A-SL-9 | every load path (pause-menu load, mission-fail load if any, new game, game start) produces a new script-domain CTOR; death/arrest/switch/mission retry-in-place produce none |
> | PC-2 | A-SL-6, A-SL-13 | a play-time stat exists; after every load it equals the loaded file's save-time value exactly (bracket from the probe's own polls contains it); non-decreasing within a session through pause, loading, switch, fades, sleep; ≤ 60 000 ms at the first tick of a new game; granularity G recorded |
> | PC-3 | A-SL-5 | `SP0/1/2_TOTAL_CASH` after every load equal the save-time values recorded by the probe (all three, incl. non-active protagonists) |
> | PC-4 | A-SL-7, A-SL-12, A-SL-4 | every save kind (bed, phone quick-save, mission autosave, autosave) changes exactly one slot file; the save-event signal is active in the tick before the file change is detected and the change is detected ≤ 2 s after the signal clears; copying/restoring a file raises no signal; no save file change is detected between the probe's tick-start and tick-end markers |
> | PC-5 | A-SL-10 | the token decorator on the player ped survives console `Reload` and script-exception restarts (10/10) and is absent after every load, new game and game restart (10/10 each) |
> | PC-6 | A-SL-3 | informative: whether `Aborted` sees pre- or post-load state |
> | PC-7 | A-SL-10 | decorator registration succeeds at probe start; set/get round-trips on the player ped; after a character switch the new ped has no token and a re-tag succeeds |
> | PC-8 | A-SL-8, A-SL-12, A-SL-14 | for every load: the loaded world's play-time lies inside the probe-recorded pre-signal bracket of exactly one present slot file and its wallets equal that file's recorded wallets (when recorded); that file's hash is unchanged at the probe's start; on the full modpack, no wallet change and restore is observed between two consecutive probe ticks |
>
> Also run **P-DB-01** (SQLite load/reload, attach + online backup of the projection DB; R-DB-1/2, D-DB-4).

### V-3 LSAX-RISK-REGISTER — rows closed by this validation

Source: `spec/LSAX-RISK-REGISTER.md` lines 16, 21, 22, 23, 26, 28, 37 (file SHA-256 `564b5d29f8a77fa78b961ea568d6a51bf177fb41154eb177b7dd5b81d33b393c`), copied verbatim:

> | B-01 | P0 | BLOCKER | Model D rests on runtime assumptions A-SL-1, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14 (SAVELOAD §9) | no GTA runtime in Phase 0 | P-SL-01 prepared (compile-verified, README-PROBES); fallback table SAVELOAD §7 degrades only toward refusal | P-SL-01 PC-1, PC-2, PC-3, PC-4, PC-5, PC-7, PC-8 PASS 10/10 on the target runtime, full modpack | RUNTIME (PO) | OPEN — BLOCKED_RUNTIME_VALIDATION |
> | R-DB-1 | P1 | OPEN RISK | native SQLite fails to load in SHVDN shadow-copy domain | E6-4 IL evidence predicts default lookup failure | D-DB-3 explicit preload | P-DB-01 steps 1–3 PASS | RUNTIME (PO) | OPEN |
> | R-DB-2 | P1 | OPEN RISK | 2 fsync'd commits per transaction tick too slow | slow disks | budget 25 ms p95; measure | P-DB-01 commit p95 ≤ 10 ms on the target PC | RUNTIME (PO) | OPEN |
> | R-COMP-2 | P1 | OPEN RISK | dependency DLL collisions (first `EndsWith` match wins) | another mod ships older System.Memory etc. | minimal deps in their own folder; startup self-check → safe refusal | P-DB-01 on the full modpack resolves every dependency from its own folder (logged path + version) | RUNTIME (PO) | OPEN |
> | R-ID-4 | P1 | OPEN RISK | story personal vehicles may be mission entities → excluded wrongly / or included wrongly; feeds LEGACY_TRUSTED (D-PROV-1) | unknown `IS_ENTITY_A_MISSION_ENTITY`/population type for personal vehicles | P-ID-01 logs flags; until then LEGACY_TRUSTED is empty and story vehicles are never sellable | P-ID-01 run; rule updated in DOMAIN §4.6/§5.3 | RUNTIME (PO) | OPEN |
> | R-UI-1 | P1 | OPEN RISK | no renderer proven on Legacy + SHVDN 3.7 + modpack | none tested | UI-S1 feasibility spike (disposable probe) with pass/fail (MASTER §20) | UI-S1 pass on the target runtime | RUNTIME (PO) | OPEN |
> | R-DB-3 | OPEN RISK | leaked connection locks DB after reload | close in `Aborted`; busy_timeout | P-DB-01 step 4 |

### V-4 README-PROBES §7 — P-DB-01 procedure and pass rule

Source: `phase0-probes/README-PROBES.md` lines 108–123 (file SHA-256 `d749e57c63fdc0df9c1235a6b5cfa9a18293db60155f4a86807c884ac513ce93`), copied verbatim:

> ## 7. P-DB-01 procedure (R-DB-1, R-DB-2, R-COMP-2, D-DB-4)
>
> 1. `SqliteProbe.Enabled=true`, no `NativePath` → record `SQL_FAIL` (expected by E6-4) or `SQL_OPEN`.
> 2. `SqliteProbe.NativePath=<GTA>\scripts\LSAXProbeSql\runtimes\win-x64\native\e_sqlite3.dll` → `SQL_OPEN` with
>    `nativeModule` = that path.
> 3. Console `Reload` × 20, then save loads × 5: every `CTOR` shows `SQL_OPEN`, `SQL_COMMIT_US`, `SQL_DEPENDENCY` rows,
>    `SQL_PRAGMAS main.synchronous=2 proj.synchronous=1 proj.journal=wal`, `SQL_TWO_FILE_COMMIT_US`,
>    `SQL_SNAPSHOT tables=[projection_meta,vehicle]`, `SQL_JOURNAL_BACKUP tables=[probe_row]`, `SQL_RESTORE projRows=…
>    watermark=…` equal to the snapshot's watermark, `SQL_WATERMARK_AT_START`; zero `SQL_FAIL`.
> 4. `SqliteProbe.CloseOnAbort=false`, `Reload` × 5: record whether `database is locked` appears (R-DB-3, informative).
>
> **Pass:** steps 2–3 succeed 20/20 and 5/5 on configuration (A) and (B); `SQL_COMMIT_US` journal p95 ≤ 10 000 µs
> (R-DB-2); every `SQL_DEPENDENCY` location is inside `<GTA>\scripts\LSAXProbeSql\` (R-COMP-2); snapshot and journal
> backup table lists exactly as above (D-DB-4). The same calls were executed on .NET 8/Linux in Phase 0
> (`dotnet-checks/backupcheck`, `evidence/compile/backupcheck-net8.out.txt`) — that is not target-runtime evidence.

### V-5 README-PROBES §8 — P-ID-01 procedure and outcome rule

Source: `phase0-probes/README-PROBES.md` lines 124–134 (file SHA-256 `d749e57c63fdc0df9c1235a6b5cfa9a18293db60155f4a86807c884ac513ce93`), copied verbatim:

> ## 8. P-ID-01 procedure (R-ID-4, OD-4; informative for the identity model, required for R-ID-4)
>
> `IdentityProbe.Enabled=true`. Enter a personal vehicle, press F10 (tag). Then: drive ≥ 600 m away and back; store it
> in a safehouse garage and retrieve it; save/load; get it impounded and retrieve it; modify it at LS Customs (respray,
> plate); leave it, let a same-model traffic car pass nearby. Also enter each protagonist's story personal vehicle, a
> stolen street car, a trainer-spawned car and an add-on car. For every event record `IDENTITY_*` rows,
> `PLAYER_VEHICLE_CHANGED` (handle reuse: `oldStillExists`), and the `mission=`, `pop=`, `script=` fields. Outcome feeds
> R-ID-4 (mission-entity rule) and OD-4: a LEGACY_TRUSTED rule may be proposed **only** if one field distinguishes
> legitimately owned vehicles and cannot be reproduced by theft, trainers or garage storage — and then needs an
> independent review. Identity never depends on the decorator (D-ID-6).

### V-6 decisions.md — D-PROV-1 (LEGACY_TRUSTED)

Source: `decisions.md` line 80 (file SHA-256 `892777d38e9ab9c6a0032b9469b1bb17c51f4748c3b4bbb3a2bf27bd81b9f2d7`), copied verbatim:

> | D-PROV-1 | **No title laundering.** LEGACY title withdrawn. First-run import → UNKNOWN unless a rule of LEGACY_TRUSTED holds; LEGACY_TRUSTED is EMPTY until a runtime probe proves an unspoofable ownership marker (never model/plate/garage/opt-in; P-ID-01, OD-4). Mission/script-owned vehicles are not imported. `TITLE_VERIFY` withdrawn: no transition UNKNOWN → CLEAN exists (UNKNOWN → STOLEN on identity match with a STOLEN record). Legal eligibility {CLEAN, SALVAGE, RECOVERED}; UNKNOWN trades only through underground channels (underground valuation, no vehicle Heat). | P1-06 (+ self-found verification path) | DESIGN DECISION (regression verified 75/75) |

### V-7 README-PROBES §9 — P-SL-02 (optional, not part of B-01)

Source: `phase0-probes/README-PROBES.md` lines 135–142 (file SHA-256 `d749e57c63fdc0df9c1235a6b5cfa9a18293db60155f4a86807c884ac513ce93`), copied verbatim:

> ## 9. P-SL-02 (optional research, not part of B-01; writes SP stats — disposable save only)
>
> Unchanged from DRAFT1: choose ≤ 8 candidate SP integer stats that exist, persist in SP saves, are not shown in the
> Stats menu and are not read by story scripts (Phase 0 names none as safe); `AnchorProbe.Enabled=true`,
> `AnchorProbe.Consent=I_USE_A_DISPOSABLE_SAVE`, `AnchorProbe.CandidateStats=…`; F9 → save → F9 → load →
> `ANCHOR_READBACK … matchesJournalSeq=n`; F11 restores originals. A carrier stays a DESIGN DECISION conditional on this
> probe and a new review (SAVELOAD §7); DRAFT2 does not use one.

### V-8 LSAX-MASTER-SPEC §20 — UI-S1 pass/fail

Source: `spec/LSAX-MASTER-SPEC-v1.0.md` lines 288–293 (file SHA-256 `1ac70b5760f1429e5a5f267c58ad560f0a66980b90af624d03d1f5f313aeb28b`), copied verbatim:

> - **Feasibility spike UI-S1 — pass/fail:** (1) renders ru-RU strings containing ё/Ё/ъ and 60+ characters and en-US
>   strings without missing glyphs; (2) documents NBSP/typographic glyph support (R-L10N-1); (3) ≤ 0.5 ms/frame for a
>   20-row list (LSAX stopwatch); (4) keyboard and gamepad navigation; (5) input isolation when another mod's menu is
>   open (no double actions in 20 trials); (6) survives SHVDN `Reload` 20× without exceptions or leaked handlers;
>   (7) 1080p, 1440p and 21:9 layouts legible; (8) 30 min open/close cycling with 0 exceptions. A renderer failing any
>   item is rejected.

## Open interpretation items for the reviewer (U-01 … U-11)

The pack found these points while preparing the owner procedure. It resolves **none** of them in a way that weakens
a criterion; where the owner needs a default to proceed, the default is the stricter reading.

| ID | Item | Evidence label | Pack default for the owner |
|---|---|---|---|
| U-01 | README §5 says "each step 10 times per configuration unless stated"; T17 states its own quantities (30 min, 10 saves, 10 loads). Whether T17 is itself repeated 10× is not stated unambiguously. | INCONCLUSIVE | T17 ×10 on FULL-MODPACK unless the reviewer rules otherwise in writing before T17 starts (no silent reduction). |
| U-02 | The B-01 closure condition is worded differently in README §6 (10/10 on (A) and (B)), SAVELOAD §6 (10/10 on the target runtime **and** P-DB-01 passes) and RISK-REGISTER B-01 (10/10 on the target runtime, full modpack). | SOURCE VERIFIED (texts quoted above) | Conjunction of all three (section above). |
| U-03 | P-DB-01 pass rule "every `SQL_DEPENDENCY` location is inside `<GTA>\scripts\LSAXProbeSql\`" (R-COMP-2). SHVDN creates the script domain with `ShadowCopyFiles = "true"`, `ShadowCopyDirectories = scriptPath` (`ScriptDomain.cs` lines 425–427 at pinned `scripthookvdotnet@56ba3bfb`). If shadow copying applies to `LSAXProbeSql\`, `Assembly.Location` (what `SQL_DEPENDENCY` logs) may be a shadow-copy cache path, and the probe logs `CodeBase` only for its own assembly (`SQL_CTOR`). Whether shadow copying applies to the subfolder is not decidable offline. | SOURCE VERIFIED (SHVDN settings) / INCONCLUSIVE (effect on the logged path) | The rule is unchanged. `CHECK-LOG` S9 only **prints** each location and never gates on it; `SQL_CTOR asmLocation`/`codeBase` in the returned log show whether shadow copying was active. The reviewer decides how R-COMP-2 is evaluated. |
| U-04 | README §7 step 2 and `probe.ini.sample` give `NativePath=<GTA>\scripts\LSAXProbeSql\runtimes\win-x64\native\e_sqlite3.dll`. The documented build (`-p:RuntimeIdentifier=win-x64`) emits `e_sqlite3.dll` at the root of the output folder; no `runtimes\` folder exists in the output. | OFFLINE VERIFIED (build output listing, `install\DEPLOYMENT-MANIFEST.tsv`) | Profiles PDB01/PDB01-LEAK set `NativePath=<scripts>\LSAXProbeSql\e_sqlite3.dll` (the only `e_sqlite3.dll` the build produces). The criterion "`SQL_OPEN` with `nativeModule` = that path" is applied to this path. |
| U-05 | SAVELOAD §6 PC-5 includes "script-exception restarts"; PC-4 summary says "detected ≤ 2 s after the signal clears". README T1–T17 has no script-exception restart step and its PC-4 log rule is "a save-flag transition ≤ 10 s before the file change". SAVELOAD calls its table a "summary; exact log rows in README-PROBES". | SOURCE VERIFIED | The owner runs README T1–T17 exactly. Whether extra evidence is needed for the SAVELOAD wording is for the reviewer. |
| U-06 | Conditional steps: T3 "(if available)"; PC-1 counts T9 "if it reloads". | SOURCE VERIFIED | The owner performs every step 10× and records `NOT_POSSIBLE` with a reason where the game does not offer the action. |
| U-07 | README §4/T11 write the console command as `Reload`; the SHVDN console evaluates C#-style calls: `Reload()` (`DllMain.cpp` console commands `Help`, `Clear`, `Reload`, `Start`, `StartAllScripts`, `Abort`, `AbortAll`, `ListScripts`). | SOURCE VERIFIED | Owner docs say `Reload()`; same command. |
| U-08 | P-DB-01 step 1 (no `NativePath`) must observe the *default* native lookup. A native DLL preloaded by step 2 (`LoadLibraryW`) stays loaded for the lifetime of the game process. | ASSUMPTION (Windows loader behaviour; not tested here) | Step 1 is run first in a freshly started game process (`06-P-DB-01-RU.md`). |
| U-09 | README §3 installs the SQLite probe folder together with the main probe. SHVDN loads every managed `*.dll` under the scripts folder recursively (`ScriptDomain.cs` lines 1236–1241), so the SQLite probe's managed dependencies are loaded during T1–T17 even with `SqliteProbe.Enabled=false`. | SOURCE VERIFIED | Kept as README §3 (both components installed for every run). `-Component Main` exists only as a diagnostic option and is not used for counted runs. |
| U-10 | T14 requires the owner to copy a backed-up save file over slot S4 while the game runs. | SOURCE VERIFIED | Only the owner does this, by hand, with backups; no pack script reads, copies or modifies save files. |
| U-11 | P-ID-01 (README §8) does not state on which configuration(s) it runs. | SOURCE VERIFIED | Templates list P-ID-01 rows for both configurations; at least FULL-MODPACK (the target runtime) is recommended. The reviewer decides what is required. |

## Pack additions that are NOT acceptance criteria

- **Smoke gates S4–S10** (`01-SMOKE-TEST-RU.md`, `CHECK-LOG.cmd`): one-pass checks of README expectations used only
  to decide whether the owner continues. A gate failure stops the owner and triggers evidence return (task rule);
  a gate success is not a PASS.
- **Install bookkeeping** (`LSAX-PACK-INSTALL-MANIFEST.tsv`, `install-report-*.txt`): lists installed files, their
  SHA-256, and same-name dependency DLLs of other mods found under the scripts folder (relative paths and file
  versions only) — informative input for R-COMP-2.
- **Redaction** in `COLLECT-EVIDENCE.cmd`: the GTA folder, the scripts folder, Documents, the user profile and any
  `C:\Users\<name>` path are replaced by placeholders in the collected text files; `REDACTION.txt` records each
  file's original SHA-256 and the number of replacements. No other change is made to any log.
