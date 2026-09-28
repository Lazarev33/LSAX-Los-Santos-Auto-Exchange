# LSAX — Compatibility Contract & Ownership Matrix

Document: LSAX-COMPATIBILITY-CONTRACT.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

The third-party mods were **not available** in Phase 0; their internal behaviour is stated as ASSUMPTION and must be
confirmed in Stage 12 (and earlier where marked). LSAX's own obligations are DESIGN DECISIONS with automated
enforcement (§4).

## 1. Ownership matrix

| Component | LSAX may observe | LSAX may modify / control | LSAX must NOT own |
|---|---|---|---|
| **GTA/RAGE** | entities in bounded scans, vehicle properties (E4-1 natives), stats `SPx_TOTAL_CASH`, play-time stat (A-SL-6), clock, pause/loading/fade flags, wanted level (read), population type, save-file metadata | protagonist cash **only inside the transaction core** (read-verify-write-verify, one tick); LSAX-spawned entities; plates of vehicles LSAX delivers; its own decorators | save system, story/mission logic, garages, impound, respawn of personal vehicles, time scale, weather, world density |
| **ScriptHookVDotNet** | its version, domain lifecycle (constructor/`Aborted`), console | its own script instances; dependency placement under `scripts/LSAX/` | other scripts' domains or threads; the reload key; `ScriptTimeoutThreshold` |
| **RDE / SixStarResponse** (ASSUMPTION: owns police dispatch, wanted escalation, police spawning and AI) | wanted level (read-only) as Heat input | nothing | wanted level, dispatch, cop spawning, relationship groups of cops, "stolen vehicle" police flag (`SET_VEHICLE_IS_STOLEN`), crime reports, incidents |
| **RealParamedics** (ASSUMPTION: owns EMS response and treatment of injured/dead peds) | whether a ped is dead/injured (to abort deals) | nothing | revive/resurrect, EMS dispatch, injured-ped handling |
| **Persist Corpses** (ASSUMPTION: keeps dead peds in the world) | nothing required | nothing | deletion/cleanup of dead peds; area clears |
| **Crime Scene Aftermath** (ASSUMPTION: creates aftermath scenes, props, peds) | nothing required | nothing | area clears; deletion of non-LSAX entities; scene props |
| **Lively World** (ASSUMPTION: owns scenarios/population behaviour) | population types of vehicles (identity/theft input) | nothing | density multipliers, scenario enable/disable, ambient population |
| **Unified Shadow Logger** (ASSUMPTION: may collect log files) | — | writes `LSAX.log` in the agreed format (§3) | other mods' logs |
| **Crime Jobs** (ASSUMPTION: pays cash and uses mission vehicles) | cash changes (as unexplained external changes), mission-entity flags | nothing | its mission vehicles (excluded from registration/sale), its payouts |
| **LSAX** | — | its SQLite DB, its journal, its catalogue, its UI surfaces, its spawned scene entities (bounded, short-lived), LSAX plates on delivered vehicles, protagonist cash inside committed LSAX transactions | police, EMS, corpses, aftermath, world population, missions, GTA saves |

Mission/script-owned vehicles are never silently registered, listed or sold (LSAX-DOMAIN-MODEL.md §4.6).

## 2. Entity-conflict rules

1. LSAX never calls `SET_ENTITY_AS_MISSION_ENTITY` on an entity it did not create (no "grabbing").
2. LSAX never deletes an entity it did not create; deletion of its own entities only via its registry, never by a
   handle remembered across a domain reload (D-WORLD-2).
3. LSAX-spawned peds use an LSAX relationship group only if needed for scenes; they never alter relationships
   between existing groups (police/gangs).
4. LSAX scene peds are never made invincible globally; they are released (`SET_ENTITY_AS_NO_LONGER_NEEDED`) after the
   scene or on abort, so EMS/corpse mods handle them normally if they die (contrast: reference SellCars sets
   `IsInvincible`, R11).
5. Deals abort (pre-commit) when a participant dies, the player gets a wanted level, or the player leaves — LSAX
   does not intervene in the cause.

## 3. Logging interface (for Unified Shadow Logger)

`scripts/LSAX/logs/LSAX.log`, UTF-8, one line per record:
`<ISO-8601 UTC ms>\t<LEVEL>\t<category>\t<event-code>\t<message>\t<json-context>`; rotation at 5 MiB, keep 5 files.
ASSUMPTION A-COMP-1: the logger can tail a UTF-8 line file; the exact expected path/format is confirmed in Stage 12
(config key `LogPath`).

## 4. Enforcement: forbidden natives (static check T-COMP-1)

A build step scans LSAX assemblies' IL (same technique as `phase0-probes/tools/il_natives.py`) and fails if any of
these native hashes appears outside an explicit allowlist (all names verified to exist in the native DB and SHVDN
`Hash` enum, `evidence/forbidden_natives_check.txt`):

Police/wanted (RDE/SixStar): `SET_PLAYER_WANTED_LEVEL`, `SET_PLAYER_WANTED_LEVEL_NOW`, `CLEAR_PLAYER_WANTED_LEVEL`,
`SET_MAX_WANTED_LEVEL`, `SET_WANTED_LEVEL_MULTIPLIER`, `SET_DISPATCH_COPS_FOR_PLAYER`, `ENABLE_DISPATCH_SERVICE`,
`SET_POLICE_IGNORE_PLAYER`, `SET_EVERYONE_IGNORE_PLAYER`, `REPORT_CRIME`, `SET_CREATE_RANDOM_COPS`, `CREATE_INCIDENT`,
`SET_PED_AS_COP`, `CLEAR_AREA_OF_COPS`, `SET_VEHICLE_IS_STOLEN`.
EMS (RealParamedics): `REVIVE_INJURED_PED`, `RESURRECT_PED`.
World (Lively World, Persist Corpses, Crime Scene Aftermath): `SET_PED_DENSITY_MULTIPLIER_THIS_FRAME`,
`SET_VEHICLE_DENSITY_MULTIPLIER_THIS_FRAME`, `SET_PARKED_VEHICLE_DENSITY_MULTIPLIER_THIS_FRAME`,
`SET_SCENARIO_TYPE_ENABLED`, `SET_SCENARIO_GROUP_ENABLED`, `CLEAR_AREA`, `CLEAR_AREA_OF_PEDS`, `CLEAR_AREA_OF_VEHICLES`,
`SET_RELATIONSHIP_BETWEEN_GROUPS`.
Death/arrest flow (GTA): `SET_FADE_OUT_AFTER_DEATH`, `IGNORE_NEXT_RESTART`, `PAUSE_DEATH_ARREST_RESTART`.
Restricted (allowlisted call sites only): `DELETE_ENTITY`/`DELETE_VEHICLE` (registry of LSAX-created entities),
`SET_ENTITY_AS_MISSION_ENTITY` (LSAX-created entities), `STAT_SET_INT` (wallet port in the transaction core only).

## 5. Compatibility tests (Stage 12, measurable)

| ID | Setup | Pass criterion |
|---|---|---|
| T-COMP-1 | static IL scan | 0 forbidden natives outside allowlist |
| T-COMP-2 | full modpack, 2 h scripted session incl. 3 police pursuits while driving a stolen car | LSAX never changes wanted level (log of wanted level transitions identical with LSAX disabled, same seed/route); 0 LSAX exceptions |
| T-COMP-3 | underground meeting interrupted by RDE police spawn | deal aborts pre-commit within 2 s; no money moved; all LSAX scene entities released within 5 s |
| T-COMP-4 | Persist Corpses + Crime Scene Aftermath, deal ped killed | LSAX does not delete the corpse; deal aborts; no errors |
| T-COMP-5 | Crime Jobs payout during an LSAX transaction tick window (forced by test hook) | transaction aborts with `ABORTED_CONCURRENT_CASH`; wallet ends at Crime Jobs' value |
| T-COMP-6 | 150 add-on vehicles installed | identity/valuation work; unpriced models listed in debug report; 0 crashes |
| T-COMP-7 | dependency collision: another mod ships older `System.Memory.dll` in scripts root | LSAX startup self-check detects version mismatch, disables persistence layer with localised message (safe refusal), no crash |
