# LSAX Phase 0 — feasibility.md (durable evidence log)

Labels: VERIFIED FEASIBILITY · DESIGN DECISION · ASSUMPTION · OPEN RISK · BLOCKER.
"VERIFIED (source)" = proven by reading pinned source/data. It is NOT proof of runtime behaviour in
GTA V 1.0.3725.0. "VERIFIED (compile)" = a disposable probe compiled against the named reference
assembly. "VERIFIED (sim)" = proven by an offline simulation in this repo. Nothing in this file is
"VERIFIED (runtime)": **no GTA V runtime is available in the Phase 0 environment.**

## E0 — Environment (VERIFIED)

| ID | Fact | Evidence |
|---|---|---|
| E0-1 | Phase 0 runs in a Linux container (Ubuntu 24.04.4, x86_64). No Windows, no GTA V, no ScriptHookV. | `/etc/os-release`, `uname -a` |
| E0-2 | Runtime GTA/SHVDN behaviour **cannot** be observed in Phase 0. Every runtime claim is ASSUMPTION until a probe is run by the project owner on the target PC. | E0-1 |
| E0-3 | Tools: Python 3.11.15 (+ `dnfile` 0.18.0, stdlib `sqlite3` = SQLite 3.45.1); .NET SDK 8.0.131 (Ubuntu archive) for compile-only checks. Microsoft .NET download hosts are blocked by the proxy (HTTP 403). | command output in progress.md S1 |
| E0-4 | NuGet `ScriptHookVDotNet3` offers only 3.0.0 … 3.6.0 (3.6.0 published 2022-12-29). SHVDN 3.7.x is not on NuGet; it is produced by CI as nightly builds (`.github/workflows/build.yml` derives `SHVDN_VERSION` from the `scripthookvdotnet-nightly` repo tags). | NuGet flat-container index; build.yml L14–53 |
| E0-5 | SHVDN source pinned: `scripthookvdotnet/scripthookvdotnet@56ba3bfb267a51431716bfbd92409228c718753d` (2026-09-27). The user's exact 3.7.x nightly commit is unknown → ASSUMPTION A-ENV-1: lifecycle code cited below is unchanged in the user's build (probe P-SL-01 logs the SHVDN file version to confirm). | `git log -1` |
| E0-6 | Native DB pinned: `alloc8or/gta5-nativedb-data@424fb51b089049a9fbcebcc641500b1d44d255b4`, `natives.json` SHA-256 `d13c7e8d627dfe4eab11ba1c25b3621562ceebfe68b0fb5cfc0644d47469b441` (6 701 natives, 45 namespaces). Existence in this DB ≠ runtime behaviour on build 3725. | `sha256sum` |

## E1 — SHVDN script lifecycle (save/load relevant)

| ID | Finding | Label | Evidence (SHVDN @56ba3bf) |
|---|---|---|---|
| E1-1 | ScriptHookV calls SHVDN's `ScriptMain` in a fiber. If `ScriptMain` is entered again with a new fiber (`sOldGameFiber != nullptr`), SHVDN sets `sScriptDomainRequestedToReload`. Code comment: "Break from the loop if ScriptHookV reloads scripts when the game creates a new session". | VERIFIED (source) | `source/core/DllMain.cpp` `ScriptMain()` ~L833–875 |
| E1-2 | On reload request the CLR thread calls `ScriptHookVDotNet_ManagedInit()`, which `ScriptDomain.Unload(old)` → `domain.Abort()` → every `Script.Abort()` → `Aborted` event invoked → `Thread.Abort()` of the script thread → `AppDomain.Unload`. A new AppDomain is then created, scripts are re-instantiated (constructors run again) and started. | VERIFIED (source) | `DllMain.cpp` `ClrThreadProc` ~L816–828, `ManagedInit` ~L491–660; `ScriptDomain.cs` `Unload` L386, `Abort` L1400; `Script.cs` `Abort` L477 |
| E1-3 | The same reload path is used for the console `Reload` command and the optional `ReloadKeyBinding`. So "constructor ran again" does NOT by itself mean "a save was loaded". | VERIFIED (source) | `DllMain.cpp` L115–128, L749–752 |
| E1-4 | For a game-session reload, `Aborted` handlers run **after** ScriptHookV has already started the new session (the new fiber is what triggers the reload). Game state read inside `Aborted` may therefore belong to the new session. LSAX must not snapshot game state in `Aborted`. | VERIFIED (source ordering); runtime timing = ASSUMPTION A-SL-3 | E1-1, E1-2 |
| E1-5 | Whether ScriptHookV actually creates a new session/fiber on **SP save load** (pause-menu Load, mission replay, `SHUTDOWN_AND_LOAD_MOST_RECENT_SAVE`) is ScriptHookV (closed-source) behaviour. | ASSUMPTION A-SL-1 → probe P-SL-01 | — |
| E1-6 | Since SHV v1.0.3351.0, SHV scripts never start before the game has finished the loading screen; `Game.IsLoading` is obsolete for that reason. SHV builds for game 1.0.3725.0 are ≥ 3351, so on the target runtime LSAX constructors run after the loading screen. | VERIFIED (source note) + version ordering | `GTA/Game.Obsolete.cs` L28–32 (issue #1549) |
| E1-7 | Default `ScriptTimeoutThreshold=5000` ms per tick; a script exceeding it is aborted ("Blocking script!"). An unhandled exception in `Tick` aborts the script. | VERIFIED (source) | `ScriptHookVDotNet.ini`; `ScriptDomain.cs` ~L1700–1730; `Script.cs` `DoTick` |
| E1-8 | While SHVDN executes, the game main thread is blocked ("This call blocks the main thread so GtaThread instances … won't be executed"). Consequence: a read-modify-write of a stat within one LSAX tick is not interleaved with ysc scripts. | VERIFIED (source comment + code); runtime = ASSUMPTION A-SL-4 | `DllMain.cpp` `ScriptMain` loop |
| E1-9 | Scripts run on dedicated threads by default (`Start(useThread=true)`); `Abort()` releases the wait event and calls `Thread.Abort()`. `Thread.Abort` is deferred while a thread executes unmanaged code (CLR semantics), so an in-flight native SQLite `COMMIT` completes or is not started; SQLite's own atomic commit covers power-loss/process-kill. | VERIFIED (source) + ASSUMPTION A-DB-2 (CLR/SQLite documented semantics, not probed) | `Script.cs` `Start`, `Abort` |

## E2 — Money API (economy relevant)

| ID | Finding | Label | Evidence |
|---|---|---|---|
| E2-1 | `Player.Money` getter reads stat `SP0_TOTAL_CASH` / `SP1_TOTAL_CASH` / `SP2_TOTAL_CASH` according to the player ped model (Michael/Franklin/Trevor); returns **0** for any other model. | VERIFIED (source) | `GTA/Player.cs` L79–106 |
| E2-2 | `Player.Money` setter performs an **absolute** `STAT_SET_INT(stat, value, 1)`; for a non-protagonist model it silently does nothing. | VERIFIED (source) | `GTA/Player.cs` L108–130 |
| E2-3 | Therefore: (a) wallets are per protagonist; (b) "0" is ambiguous for non-protagonist models; (c) a set must be verified by read-back; (d) read-modify-write must occur in one tick (E1-8). | DESIGN DECISION D-ECO-2 (derived) | E2-1, E2-2 |
| E2-4 | SP `SPx_TOTAL_CASH` values are restored from the save on load (money "reverts"). | ASSUMPTION A-SL-5 (widely observed; not probed) → P-SL-01 logs it | — |

## E3 — Decorators / entity metadata

| ID | Finding | Label | Evidence |
|---|---|---|---|
| E3-1 | SHVDN 3.7 API `GTA.DecoratorInterface` (added 2023, not in NuGet 3.6.0) exposes Set/Get Int/Float/Bool/Time, `ExistsOn`, `Register`, `IsRegisteredAsType`, `IsLocked` (memory patch). | VERIFIED (source) | `GTA/DecoratorInterface.cs` |
| E3-2 | **Bug at pinned HEAD:** `DecoratorInterface.Remove` calls `DECOR_EXIST_ON`, not `DECOR_REMOVE` → it never removes. LSAX must call `Hash.DECOR_REMOVE` directly or not depend on removal. | VERIFIED (source) | `GTA/DecoratorInterface.cs` `Remove` |
| E3-3 | Registering new decorators requires unlocking the decorator registry (`IsLocked=false` via `SHVDN.NativeMemory`, a memory-pattern dependent feature). If the pattern fails on a game build, registration fails. | VERIFIED (source) + OPEN RISK R-ID-3 | `DecoratorInterface.cs`; `NativeMemory` |
| E3-4 | Decorator values are 32-bit (int/float/bool/time). A decorator can carry a runtime binding token, not a full VehicleId string. | VERIFIED (native DB signatures) | `DECOR_SET_INT(Entity, const char*, int)` |
| E3-5 | Decorators are attached to an entity instance. Whether they survive stream-out/in, garage store/retrieve, save/load re-spawn or impound is unknown. Brief forbids assuming survival. | ASSUMPTION-NOT-MADE → probe P-ID-01 | — |

## E4 — Native existence (for API-invention guard)

Checked against native DB @424fb51 and SHVDN `GTA.Native.Hash` enum (`NativeHashes.cs`).
Full output: `evidence/native_check.txt`, `evidence/save_natives_scan.txt`.

| ID | Finding | Label |
|---|---|---|
| E4-1 | Present in DB **and** Hash enum: `GET_GAME_TIMER`, `GET_FRAME_COUNT`, `GET_FRAME_TIME`, `GET_CLOCK_*`, `GET_MILLISECONDS_PER_GAME_MINUTE`, `PAUSE_CLOCK`, `ADD_TO_CLOCK_TIME`, `GET_POSIX_TIME`, `GET_LOCAL_TIME`, `GET_UTC_TIME`, `GET_CLOUD_TIME_AS_INT`, `IS_PAUSE_MENU_ACTIVE`, `IS_SCREEN_FADED_OUT`, `IS_PLAYER_SWITCH_IN_PROGRESS`, `GET_IS_LOADING_SCREEN_ACTIVE`, `IS_AUTO_SAVE_IN_PROGRESS`, `GET_STATUS_OF_MANUAL_SAVE`, `HAS_CODE_REQUESTED_AUTOSAVE`, `GET_SAVE_HOUSE_DETAILS_AFTER_SUCCESSFUL_LOAD`, `SHUTDOWN_AND_LOAD_MOST_RECENT_SAVE`, `QUEUE_MISSION_REPEAT_LOAD`, `STAT_GET_INT`, `STAT_SET_INT`, `DECOR_*` (incl. `DECOR_REMOVE`, `DECOR_REGISTER_LOCK`), `GET_VEHICLE_NUMBER_PLATE_TEXT(_INDEX)`, `GET_VEHICLE_COLOURS`, `GET_VEHICLE_EXTRA_COLOURS`, `GET_VEHICLE_CUSTOM_PRIMARY_COLOUR`, `GET_VEHICLE_MOD(_KIT/_VARIATION)`, `IS_TOGGLE_MOD_ON`, `GET_VEHICLE_LIVERY`, `GET_VEHICLE_WINDOW_TINT`, `GET_VEHICLE_WHEEL_TYPE`, `IS_VEHICLE_EXTRA_TURNED_ON`, `GET_VEHICLE_BODY/ENGINE/PETROL_TANK_HEALTH`, `GET_VEHICLE_DIRT_LEVEL`, `IS_VEHICLE_TYRE_BURST`, `IS_VEHICLE_STOLEN`/`SET_VEHICLE_IS_STOLEN`, `IS_ENTITY_A_MISSION_ENTITY`, `GET_ENTITY_SCRIPT`, `GET_ENTITY_POPULATION_TYPE`, `GET_VEHICLE_CLASS`, `GET_DISPLAY_NAME_FROM_VEHICLE_MODEL`, `GET_MAKE_NAME_FROM_VEHICLE_MODEL`, `GET_VEHICLE_MODEL_VALUE`, `SET_VEHICLE_CAN_SAVE_IN_GARAGE`, `GET_ALL_VEHICLES`. | VERIFIED (API existence only) |
| E4-2 | `GET_VEHICLE_MODEL_VALUE(Hash)` returns handling.meta `nMonetaryValue` (DB comment). A plausible MSRP seed; its magnitude/meaning for add-ons is unverified. | VERIFIED (existence) + ASSUMPTION A-VAL-1 |
| E4-3 | `GET_VEHICLE_MODEL_MONETARY_VALUE` does **not** exist; `GET_GAME_POOL` is **not** a GTA native (FiveM). LSAX must not reference them. | VERIFIED (absence in DB) |
| E4-4 | No native in the DB returns an SP **save slot id, save generation id, save checksum or save timestamp**. `REGISTER_*_TO_SAVE` natives exist but register ysc script-global memory inside save-struct registration; not a usable channel for an external SHVDN script. | VERIFIED (absence by name scan of 101 save/slot/session natives) + DESIGN DECISION (not used) |
| E4-5 | `IS_VEHICLE_STOLEN` only reports the flag set by `SET_VEHICLE_IS_STOLEN` (DB comment); it is not a general "player stole this" signal. | VERIFIED (DB comment) |

## E5 — Managed API (SHVDN v3)

| ID | Finding | Label | Evidence |
|---|---|---|---|
| E5-1 | `Game.GameTime` = `GET_GAME_TIMER` (int ms), `Game.FrameCount`, `Game.LastFrameTime` exist. Behaviour of `GET_GAME_TIMER` across session reload is unknown. | VERIFIED (source) + ASSUMPTION-NOT-MADE → P-SL-01 | `GTA/Game.cs` L141–167 |
| E5-2 | `Game.IsPaused` = `IS_PAUSE_MENU_ACTIVE`. | VERIFIED (source) | `GTA/Game.cs` L326 |
| E5-3 | `World.GetAllVehicles`, `World.GetNearbyVehicles(pos, r)`, `World.VehicleCount`, `World.VehicleCapacity` exist (memory-pool based). | VERIFIED (source) | `GTA/World.cs` L366–572 |
| E5-4 | `GTA.Chrono.GameClock` (3.7 API): `Now`, `IsPaused`, `LastTimeMinAdded`, `MillisecondsPerGameMinute`, `AddToCurrentTime`. | VERIFIED (source) | `GTA.Chrono/GameClock.cs` |

## E6 — Script assembly loading / dependencies (SQLite relevant)

| ID | Finding | Label | Evidence |
|---|---|---|---|
| E6-1 | SHVDN creates the script AppDomain with `ShadowCopyFiles="true"`, `ShadowCopyDirectories=scriptPath`, `ApplicationBase=scriptPath`. Script assemblies load via `Assembly.LoadFrom` from a **shadow copy**; `Assembly.Location` therefore points into the shadow-copy cache, not `scripts/`. `AppDomain.CurrentDomain.BaseDirectory` = `scripts/`. | VERIFIED (source) | `source/core/ScriptDomain.cs` L415–433, L650 |
| E6-2 | Unresolved managed dependencies are resolved by scanning `scripts/` **recursively** and taking the first file whose name ends with `<AssemblyName>.dll` (`EndsWith`, first match). Dependencies may live in `scripts/LSAX/`. Two mods shipping different versions of the same dependency collide (first match wins; no version check on this path). | VERIFIED (source) + OPEN RISK R-COMP-2 | `ScriptDomain.cs` `HandleResolve` ~L2140–2150 |
| E6-3 | `Microsoft.Data.Sqlite` 8.0.11 on net48 pulls `SQLitePCLRaw.*` 2.1.6 + `System.Memory`, `System.Buffers`, `System.Numerics.Vectors`, `System.Runtime.CompilerServices.Unsafe` (8 managed DLLs) + native `e_sqlite3`. These BCL-extension DLLs are commonly shipped by other mods → R-COMP-2 is concrete. | VERIFIED (build output) | `phase0-probes/shvdn/LsaxPhase0SqliteProbe` build |
| E6-4 | SQLitePCLRaw.batteries_v2 2.1.6 `NativeLibrary.MakePossibilitiesFor` builds every candidate path from `Assembly.Location` (`runtimes/<rid>/native`, `<dir>/<arch>`, `<dir>`) plus the bare library name. It never uses `CodeBase` or `BaseDirectory`. Combined with E6-1, the default native lookup will search the shadow-copy cache (natives are not shadow-copied) and then the bare name (Windows search order: GTA exe dir, system dirs, PATH). **Expected default result inside SHVDN: native load fails unless e_sqlite3.dll is in the GTA root or already loaded.** | VERIFIED (IL of MakePossibilitiesFor) + expected-failure ASSUMPTION A-DB-3 → P-DB-01 | `il_disasm.py SQLitePCLRaw.batteries_v2.dll MakePossibilitiesFor` |
| E6-5 | Mitigation (DESIGN DECISION D-DB-3): LSAX pre-loads its native SQLite with `LoadLibraryW(<BaseDirectory>/LSAX/native/x64/e_sqlite3.dll)` once per process before first SQLite use, then verifies the loaded module path. A module already loaded in the process satisfies the bare-name `LoadLibrary`, and survives AppDomain reloads (native modules are process-wide). | DESIGN DECISION; runtime proof → P-DB-01 | — |

## E7 — Disposable probes (compile-verified, NOT run)

| ID | Probe | Status |
|---|---|---|
| E7-1 | `phase0-probes/shvdn/LsaxPhase0Probe` (net48, C# 7.3, `TreatWarningsAsErrors`): `SessionSignalProbe` (P-SL-01, passive), `AnchorCarrierProbe` (P-SL-02, opt-in stat writes behind consent phrase), `IdentityProbe` (P-ID-01, opt-in decorator). | VERIFIED (compile) against ScriptHookVDotNet3 **3.6.0** NuGet reference: `dotnet build -c Release` → Build succeeded, 0 warnings. References only mscorlib, SHVDN3 3.6.0, System, System.Core, System.Windows.Forms. 3.7-only `DecoratorInterface.IsLocked` is reached via reflection. |
| E7-2 | `phase0-probes/shvdn/LsaxPhase0SqliteProbe` (P-DB-01, opt-in). | VERIFIED (compile). A Windows deployment build must set `RuntimeIdentifier=win-x64` (the Linux build copied only linux natives). |
| E7-3 | None of the probes has been executed. Their outputs are the exact experiments required before Stage 1 (see LSAX-SAVELOAD-FEASIBILITY.md §6). | BLOCKER B-01 input |

(Simulations appended below as they complete.)
