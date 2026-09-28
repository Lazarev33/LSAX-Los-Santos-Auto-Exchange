# LSAX Phase 0 — Runtime Validation Package (disposable feasibility probes), DRAFT2

**These are NOT LSAX production code.** They exist only to produce the runtime evidence that the Phase 0
environment (Linux container, no GTA V) cannot produce. Do not ship them, do not copy their code into LSAX.
They are compile-verified against `ScriptHookVDotNet3` 3.6.0 (NuGet; `evidence/compile/`) and have **never been
executed in GTA V**. Status of every assumption they test: ASSUMPTION until the owner returns the logs below.
**BLOCKER B-01 closes only with these results; the correction pass ends at BLOCKED_RUNTIME_VALIDATION.**

| Probe | Project | Writes game state? | Resolves |
|---|---|---|---|
| P-SL-01 SessionSignalProbe | `shvdn/LsaxPhase0Probe` | only a runtime int decorator `lsax_p0_sess` on the player ped (session token; `SessionToken.Enabled=false` disables it) | A-SL-1, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, A-ENV-1 → **B-01** (PC-1…PC-8); R-SL-2, R-SL-7 (PC-8), R-ECO-1, R-ENV-1, R-COMP-1 (full modpack) |
| P-DB-01 SqliteReloadProbe | `shvdn/LsaxPhase0SqliteProbe` | No (own files under `scripts/LSAXProbe/` only); opt-in | R-DB-1, R-DB-2, R-COMP-2, D-DB-4 |
| P-ID-01 IdentityProbe | `shvdn/LsaxPhase0Probe` | registers one decorator, tags one vehicle; opt-in | R-ID-4, OD-4 (LEGACY_TRUSTED research), A-ID-1…3 |
| P-SL-02 AnchorCarrierProbe | `shvdn/LsaxPhase0Probe` | **Yes (SP stats)**, opt-in + consent phrase, disposable save only | optional fallback research only (SAVELOAD §7 row PC-4); **not** part of B-01 |
| UI-S1 renderer spike | — (no code prepared in Phase 0) | — | R-UI-1; pass/fail list in LSAX-MASTER-SPEC §20 |

## 1. Target runtime and prerequisites

- GTA V **Legacy 1.0.3725.0** (Story Mode), ScriptHookV for 1.0.3725.0, **ScriptHookVDotNet 3.7.x** (record the exact
  nightly), .NET Framework 4.8. Two configurations, each run completely: **(A) full LSAX target modpack** (RDE/SixStar,
  RealParamedics, Persist Corpses, Crime Scene Aftermath, Lively World, Unified Shadow Logger, Crime Jobs, add-ons) and
  **(B) minimal** (ScriptHookV + SHVDN + probes only).
- **Back up the whole profile folder first:** `%USERPROFILE%\Documents\Rockstar Games\GTA V\Profiles\<id>\` → a copy
  outside the game folders. Every step below may be repeated from this backup.
- A Windows PC with .NET SDK ≥ 8 (build) — or build on any machine and copy the DLLs.

## 2. Build

```
cd phase0-probes\shvdn\LsaxPhase0Probe        && dotnet build -c Release
cd phase0-probes\shvdn\LsaxPhase0SqliteProbe  && dotnet build -c Release -p:RuntimeIdentifier=win-x64
```

Outputs: `LsaxPhase0Probe\bin\Release\net48\LsaxPhase0Probe.dll`;
`LsaxPhase0SqliteProbe\bin\Release\net48\win-x64\` (probe DLL + Microsoft.Data.Sqlite + SQLitePCLRaw + native
`runtimes\win-x64\native\e_sqlite3.dll`). Record the SHA-256 of both DLLs in the evidence folder.

## 3. Install (exact paths; `<GTA>` = the GTA V Legacy install folder)

| File | Destination |
|---|---|
| `LsaxPhase0Probe.dll` | `<GTA>\scripts\LsaxPhase0Probe.dll` |
| whole `win-x64` output of the SQLite probe | `<GTA>\scripts\LSAXProbeSql\` (keeps its dependencies out of the scripts root) |
| `phase0-probes\probe.ini.sample` | `<GTA>\scripts\LSAXProbe\probe.ini` (create the folder) |

`probe.ini` for B-01 runs: keep `PlaytimeStatCandidates` (hypotheses), `SessionToken.Enabled=true`,
`AnchorProbe.Enabled=false`, `IdentityProbe.Enabled=false`, `SqliteProbe.Enabled=false`. Logs are written to
`<GTA>\scripts\LSAXProbe\probe-YYYYMMDD.log` (tab-separated: UTC time, event, data); the probe also writes
`probe-ledger.tsv`, `session-token.txt` and `domains-<process>.count` there.

## 4. Launch

Start GTA V Story Mode normally. Confirm in the SHVDN console (F4, or the configured key) that
`LsaxPhase0Probe.dll` loaded and in the log that `CTOR` and `CTOR_FP` rows exist. The probe runs every tick;
expected overhead is a few natives per tick plus a metadata scan of ≤ 64 files every 2 s (every tick for 10 s after
any save-flag change).

## 5. P-SL-01 scenarios (each step 10 times per configuration unless stated; note the wall time of every action)

| Step | Action | Expected log evidence (what to look for) |
|---|---|---|
| T1 | Start the game; Story Mode loads the latest save | `CTOR domainInstanceInProcess=1`, `TOKEN_AT_CTOR present=0`, `TOKEN_SET setOk=1 readBack=1`, `SAVEFILE_INITIAL` per file, `LOAD_MATCH` per play-time candidate |
| T2 | Manual save at a safehouse bed into slot S | `FLAGS` transition(s) with `preSignal=[…]`, then `SAVEFILE_CHANGED … signalSeen=1 bracketLo=[…] bracketHi=[…]`; no `TICK_INTERLEAVE` |
| T3 | Phone quick-save (if available) into slot S2 | as T2 |
| T4 | Finish a mission / activity that autosaves | as T2 (autosave slot) |
| T5 | Change cash (buy something), drive ≥ 1 km, wait ≥ 2 in-game hours | `WALLET_CHANGE` rows; no `PT_DECREASED` |
| T6 | Pause → Game → Load Game → slot S | `ABORTED` (informative) then `CTOR domainInstanceInProcess=+1`, `TOKEN_AT_CTOR present=0`, `LOAD_MATCH … matches=1 [S…:W=]` for the working play-time candidate |
| T7 | Load slot S again (×2) | as T6 each time |
| T8 | Die, then get arrested | **no** `CTOR`; wallet changes only |
| T9 | Fail a mission → Retry | record whether `CTOR` occurs (informs PC-1 for mission retry) |
| T10 | Switch character Michael → Franklin → Trevor → Michael | `TOKEN_PED_CHANGED newPedHadToken=0 retagOk=1` for each switch; **no** `CTOR`; no `PT_DECREASED` |
| T11 | SHVDN console (F4) `Reload` | `CTOR domainInstanceInProcess=+1` with the **same** process key, `TOKEN_AT_CTOR present=1 value=<persisted token>` |
| T12 | Quit to desktop without saving; restart the game; load slot S | `CTOR domainInstanceInProcess=1` with a **new** process key, `TOKEN_AT_CTOR present=0`, `LOAD_MATCH matches=1` |
| T13 | Sleep in a safehouse bed (≥ 6 in-game hours), then save immediately into slot S3 | `FLAGS fadedOut=1…`; no `PT_DECREASED`; then `SAVEFILE_CHANGED signalSeen=1` for S3 |
| T14 | While the game runs, copy a backed-up save file over slot S4 in the profile folder (Explorer) | `SAVEFILE_CHANGED file=S4 … signalSeen=0` (no save flag transition within 10 s before) |
| T15 | Load slot S4 (the copied file) | `CTOR`, `TOKEN_AT_CTOR present=0`; `LOAD_MATCH` must **not** attribute the world to another file unless its bracket and wallets really match (record) |
| T16 | Start a New Game (on a disposable profile or after backing up saves) | `CTOR`; `CTOR_FP pt=…` value of each candidate at the first tick (PC-2 new-game bound) |
| T17 | Configuration (A) only: 30 min normal play with Crime Jobs and other cash-writing mods active, 10 saves and 10 loads interleaved | `WALLET_CHANGE` rows (look for change-and-restore across consecutive frames), all T2/T6 expectations |

## 6. PASS / FAIL rules (decided offline from the logs; every rule 10/10 on configuration (A) and (B))

- **PC-1 load detectability (A-SL-1, A-SL-9):** T6, T7, T12, T16 (and T9 if it reloads) each produce exactly one new
  `CTOR`; T8 and T10 produce none. Any missing `CTOR` after a load = FAIL.
- **PC-2 play-time anchor (A-SL-6, A-SL-13):** at least one candidate stat exists (appears in `CTOR_FP pt=`), never
  appears in a `PT_DECREASED` row within one domain (T2–T5, T8, T10, T13, T17), and after every load (T6, T7, T12) its
  value lies inside the `bracketLo … bracketHi` recorded for the loaded slot at save time (`LOAD_MATCH` lists that
  file). At T16 its first value is ≤ 60 000 ms. Record the granularity G (smallest observed increment).
- **PC-3 cash restore (A-SL-5):** after every load, `CTOR_FP cash=` equals the three wallets of the loaded file's
  bracket (`LOAD_MATCH … :W=`), including the non-active protagonists.
- **PC-4 save observability and timing (A-SL-7, A-SL-12, A-SL-4):** every save in T2–T4, T13, T17 yields exactly one
  `SAVEFILE_CHANGED` with `signalSeen=1` (a save-flag transition ≤ 10 s before the file change); T14 yields
  `signalSeen=0`; loads yield no `SAVEFILE_CHANGED`; zero `TICK_INTERLEAVE` rows.
- **PC-5 reload discrimination (A-SL-10):** T11 → `TOKEN_AT_CTOR present=1` with the persisted value; T6, T7, T12, T16
  → `present=0`.
- **PC-6 Aborted timing (informative, A-SL-3):** record whether `ABORTED` shows the pre-load or post-load state.
  Not a gate; LSAX never reads game state in `Aborted`.
- **PC-7 token mechanics (A-SL-10):** `TOKEN_DECOR_REGISTER ok=1` (or already registered), `TOKEN_SET setOk=1
  readBack=1` at every `CTOR`; T10 → `newPedHadToken=0 retagOk=1` for every switch.
- **PC-8 load attribution (A-SL-8, A-SL-12, A-SL-14):** for every load of an LSAX-observed slot (T6, T7, T12),
  `LOAD_MATCH matches=1` for the working candidate, the match is the loaded slot, and its wallet flag is `:W=` or
  `:W?`; the loaded file's `SAVEFILE_INITIAL` hash equals its last `SAVEFILE_CHANGED` hash; in T17 no wallet shows a
  change and an exact restore across two consecutive frames (`WALLET_CHANGE` pairs).

B-01 closes only if PC-1, PC-2, PC-3, PC-4, PC-5, PC-7 and PC-8 all PASS. Any FAIL → apply
LSAX-SAVELOAD-FEASIBILITY.md §7 (every fallback degrades toward refusal) and re-run the simulation before any
approval request. Also record the SHVDN version logged at `CTOR` (R-ENV-1) and any `PROBE_ERROR` rows.

## 7. P-DB-01 procedure (R-DB-1, R-DB-2, R-COMP-2, D-DB-4)

1. `SqliteProbe.Enabled=true`, no `NativePath` → record `SQL_FAIL` (expected by E6-4) or `SQL_OPEN`.
2. `SqliteProbe.NativePath=<GTA>\scripts\LSAXProbeSql\runtimes\win-x64\native\e_sqlite3.dll` → `SQL_OPEN` with
   `nativeModule` = that path.
3. Console `Reload` × 20, then save loads × 5: every `CTOR` shows `SQL_OPEN`, `SQL_COMMIT_US`, `SQL_DEPENDENCY` rows,
   `SQL_PRAGMAS main.synchronous=2 proj.synchronous=1 proj.journal=wal`, `SQL_TWO_FILE_COMMIT_US`,
   `SQL_SNAPSHOT tables=[projection_meta,vehicle]`, `SQL_JOURNAL_BACKUP tables=[probe_row]`, `SQL_RESTORE projRows=…
   watermark=…` equal to the snapshot's watermark, `SQL_WATERMARK_AT_START`; zero `SQL_FAIL`.
4. `SqliteProbe.CloseOnAbort=false`, `Reload` × 5: record whether `database is locked` appears (R-DB-3, informative).

**Pass:** steps 2–3 succeed 20/20 and 5/5 on configuration (A) and (B); `SQL_COMMIT_US` journal p95 ≤ 10 000 µs
(R-DB-2); every `SQL_DEPENDENCY` location is inside `<GTA>\scripts\LSAXProbeSql\` (R-COMP-2); snapshot and journal
backup table lists exactly as above (D-DB-4). The same calls were executed on .NET 8/Linux in Phase 0
(`dotnet-checks/backupcheck`, `evidence/compile/backupcheck-net8.out.txt`) — that is not target-runtime evidence.

## 8. P-ID-01 procedure (R-ID-4, OD-4; informative for the identity model, required for R-ID-4)

`IdentityProbe.Enabled=true`. Enter a personal vehicle, press F10 (tag). Then: drive ≥ 600 m away and back; store it
in a safehouse garage and retrieve it; save/load; get it impounded and retrieve it; modify it at LS Customs (respray,
plate); leave it, let a same-model traffic car pass nearby. Also enter each protagonist's story personal vehicle, a
stolen street car, a trainer-spawned car and an add-on car. For every event record `IDENTITY_*` rows,
`PLAYER_VEHICLE_CHANGED` (handle reuse: `oldStillExists`), and the `mission=`, `pop=`, `script=` fields. Outcome feeds
R-ID-4 (mission-entity rule) and OD-4: a LEGACY_TRUSTED rule may be proposed **only** if one field distinguishes
legitimately owned vehicles and cannot be reproduced by theft, trainers or garage storage — and then needs an
independent review. Identity never depends on the decorator (D-ID-6).

## 9. P-SL-02 (optional research, not part of B-01; writes SP stats — disposable save only)

Unchanged from DRAFT1: choose ≤ 8 candidate SP integer stats that exist, persist in SP saves, are not shown in the
Stats menu and are not read by story scripts (Phase 0 names none as safe); `AnchorProbe.Enabled=true`,
`AnchorProbe.Consent=I_USE_A_DISPOSABLE_SAVE`, `AnchorProbe.CandidateStats=…`; F9 → save → F9 → load →
`ANCHOR_READBACK … matchesJournalSeq=n`; F11 restores originals. A carrier stays a DESIGN DECISION conditional on this
probe and a new review (SAVELOAD §7); DRAFT2 does not use one.

## 10. Evidence collection (send all of it to the independent reviewer)

1. Zip `<GTA>\scripts\LSAXProbe\` (all `probe-*.log`, `sqlite-probe.log`, `probe-ledger.tsv`, `session-token.txt`,
   `domains-*.count`) separately for configuration (A) and (B).
2. A text file with: game build (from the launcher/exe properties), ScriptHookV version, SHVDN version string, the
   full modpack list with versions, Windows version, the SHA-256 of the probe DLLs, and a table of every step with
   repetition number and local wall time.
3. The profile-folder backup used (hashes of the save files at the start).
4. Do not edit logs; annotate in the separate text file.

## 11. Cleanup

1. Delete `<GTA>\scripts\LsaxPhase0Probe.dll`, `<GTA>\scripts\LSAXProbeSql\` and (after collecting evidence)
   `<GTA>\scripts\LSAXProbe\`.
2. Restore the profile folder from the backup (removes the files written in T2–T4, T13–T17).
3. The session-token decorator exists only at runtime (it does not persist in saves — that is what PC-5 tests);
   restarting the game removes it. P-SL-02 only: press F11 before removing the probe (restores the original stat
   values) and discard the disposable save.
