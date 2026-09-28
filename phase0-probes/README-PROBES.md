# LSAX Phase 0 — Disposable Feasibility Probes

**These are NOT LSAX production code.** They exist only to produce runtime evidence that the Phase 0
environment (Linux container, no GTA V) cannot produce. Do not ship them, do not copy their code into LSAX.
They were compile-checked against `ScriptHookVDotNet3` 3.6.0 (NuGet) and have **never been executed**.

| Probe | Project | Writes game state? | Resolves |
|---|---|---|---|
| P-SL-01 SessionSignalProbe | `shvdn/LsaxPhase0Probe` | No | A-SL-1, A-SL-3, A-SL-5, A-SL-6, A-SL-7 → BLOCKER B-01 |
| P-SL-02 AnchorCarrierProbe | `shvdn/LsaxPhase0Probe` | **Yes (SP stats)**, opt-in + consent phrase | optional fallback F1 (LSAX-SAVELOAD-FEASIBILITY.md §7) |
| P-ID-01 IdentityProbe | `shvdn/LsaxPhase0Probe` | Registers one decorator, tags one vehicle; opt-in | A-ID-1 .. A-ID-3 |
| P-DB-01 SqliteReloadProbe | `shvdn/LsaxPhase0SqliteProbe` | No (own DB file only); opt-in | A-DB-3, R-DB-1 |

## Build (Windows, owner PC)

```
cd phase0-probes/shvdn/LsaxPhase0Probe        && dotnet build -c Release
cd phase0-probes/shvdn/LsaxPhase0SqliteProbe  && dotnet build -c Release -p:RuntimeIdentifier=win-x64
```

Copy `LsaxPhase0Probe.dll` to `GTA V/scripts/`. For P-DB-01, copy the whole `bin/Release/net48/win-x64`
output into `GTA V/scripts/LSAXProbeSql/` (keeps dependencies out of the scripts root).
Create `GTA V/scripts/LSAXProbe/probe.ini` from `probe.ini.sample`. Logs go to `GTA V/scripts/LSAXProbe/`.

**Use a backup of your saves** (`Documents/Rockstar Games/GTA V/Profiles/<id>/`) before any test.
P-SL-02 must only be run on a disposable copy of a save.

Run every test twice: (a) full target modpack (RDE/SixStar, RealParamedics, Persist Corpses,
Crime Scene Aftermath, Lively World, Unified Shadow Logger, Crime Jobs, add-ons) and (b) minimal
(ScriptHookV + SHVDN + probe only). Record game build, ScriptHookV version and SHVDN version
(the probe logs the SHVDN assembly and file version at every CTOR).

## P-SL-01 procedure (passive, required)

| Step | Action | Expected log evidence |
|---|---|---|
| T1 | Start game, Story Mode loads the latest save | `CTOR domainInstanceInProcess=1`, `CTOR_FP`, `SAVEFILE_INITIAL` rows |
| T2 | Manual save at a safehouse bed into slot S | `SAVEFILE_CHANGED file=SGTA…` with `fpAtDetection` |
| T3 | Phone quick-save (if available) | `SAVEFILE_CHANGED` |
| T4 | Trigger an autosave (finish a mission/activity) | `FLAGS autosave=1…` transitions, `SAVEFILE_CHANGED` |
| T5 | Change cash (buy something), drive ≥ 1 km, wait ≥ 2 in-game hours | `STAT_CHANGED SPx_TOTAL_CASH` |
| T6 | Pause → Game → Load Game → slot S | either `ABORTED` + `CTOR domainInstanceInProcess=2` or `STAT_DECREASED`/`GAMETIMER_DECREASED` |
| T7 | Load slot S again (×2) | `CTOR_FP` identical in every stat to T6's `CTOR_FP` |
| T8 | Die, then get arrested | NO `CTOR`; cash `STAT_CHANGED` only |
| T9 | Fail a mission → Retry | observe whether `CTOR` occurs |
| T10 | Switch character Michael→Franklin→Trevor | `PLAYER_MODEL_CHANGED`, NO `CTOR` |
| T11 | SHVDN console (F4) `Reload` | `CTOR domainInstanceInProcess+1`, fingerprint **unchanged** |
| T12 | Quit to desktop without saving, restart, load slot S | `CTOR domainInstanceInProcess=1` with slot-S fingerprint |
| T13 | Sleep in bed (time skip) | clock jump; play-time candidate does **not** jump |

**Pass criteria (all must hold, 10/10 repetitions each, on the full modpack):**

- **PC-1 load detectability:** for T6, T7, T9 (if it reloads), T12 at least one of {new `CTOR` with a
  higher `domainInstanceInProcess`, `STAT_DECREASED` on the play-time stat} appears ≤ 2 s after
  player control returns; T8 and T10 produce neither (0 false positives).
- **PC-2 play-time anchor:** at least one play-time candidate exists (`STAT_GET_INT` true), increases
  at wall-clock rate ±10 % while unpaused, is unaffected by T13, and after a load equals the value in
  the matching `SAVEFILE_CHANGED fpAtDetection` minus at most the detection latency (≤ 2 500 ms).
- **PC-3 cash restore:** `SP0/1/2_TOTAL_CASH` after load equal the values in the matching
  `fpAtDetection` exactly (unless a cash change is logged between save and detection).
- **PC-4 save observability:** each save in T2–T4 yields `SAVEFILE_CHANGED` ≤ 4 s after the save UI
  closes; loads yield no `SAVEFILE_CHANGED`.
- **PC-5 reload discrimination:** T11 yields `CTOR` with an unchanged fingerprint.
- **PC-6 Aborted timing (informative):** record whether the `ABORTED` fingerprint equals the pre-load
  or post-load state (A-SL-3). Not a pass/fail gate; LSAX never reads game state in `Aborted`.

If PC-1…PC-5 pass, LSAX-SAVELOAD-FEASIBILITY.md model **D (Anchored Timeline, passive anchor)** becomes
VERIFIED (runtime) and BLOCKER B-01 closes. If PC-2 fails, the fallback anchor is P-SL-02.
If PC-1 fails, see the decision table in LSAX-SAVELOAD-FEASIBILITY.md §7.

## P-SL-02 procedure (optional, writes stats — disposable save only)

1. Choose ≤ 8 candidate SP integer stats that (a) exist, (b) are persisted in SP saves, (c) are not
   shown in the in-game Stats menu and (d) are not read by story scripts. Candidates must come from the
   game's own SP stat definitions; Phase 0 names **none** as safe.
2. `AnchorProbe.Enabled=true`, `AnchorProbe.Consent=I_USE_A_DISPOSABLE_SAVE`, `AnchorProbe.CandidateStats=…`.
3. F9 (write token seq=n) → save to slot S → F9 (seq=n+1) → load S → `ANCHOR_READBACK … matchesJournalSeq=n`.
4. Play 60 minutes including a mission; the token must be unchanged. F11 restores originals.

**Pass:** token of the last write before the save is read back exactly after load (10/10) and is never
altered by the game during 60 minutes of play.

## P-ID-01 procedure (informative)

`IdentityProbe.Enabled=true`. Enter a personal vehicle, press F10. Then: drive ≥ 600 m away and back;
store it in a safehouse garage and retrieve it; save/load; get it impounded and retrieve it; modify it at
LS Customs. Record for each event: `IDENTITY_TAG_OK` vs `SAME_PLATE_MODEL_WITHOUT_TAG`, and handle
changes. Outcome sets the expected hit-rate of the decorator fast path; identity never depends on it.

## P-DB-01 procedure

1. `SqliteProbe.Enabled=true`, no `NativePath` → expect `SQL_FAIL` (confirms E6-4) or `SQL_OPEN`.
2. `SqliteProbe.NativePath=<GTA V>/scripts/LSAXProbeSql/runtimes/win-x64/native/e_sqlite3.dll` →
   `SQL_OPEN` with `nativeModule` = that path.
3. Console `Reload` ×20, then SP load ×5: zero `SQL_FAIL`; `SQL_COMMIT_US p95` recorded.
4. `SqliteProbe.CloseOnAbort=false`, `Reload` ×5: record whether `database is locked` appears.

**Pass:** step 2–3 succeed 20/20 and 5/5; commit p95 recorded (budget in LSAX-PERFORMANCE-BUDGET.md).
