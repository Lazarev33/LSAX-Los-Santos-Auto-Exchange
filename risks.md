# LSAX Phase 0 — risks.md (durable working risk log)

Severity: P0 = blocks Stage 1 start or makes the architecture unsafe; P1 = must be closed before the stage
that depends on it; P2 = tracked, has mitigation. The formal register with owners, triggers and exit criteria
is `spec/LSAX-RISK-REGISTER.md` (same IDs).

| ID | Sev | Label | Risk | Mitigation / exact exit criterion |
|---|---|---|---|---|
| B-01 | P0 | **BLOCKER** | Save/load model D rests on runtime assumptions not provable in Phase 0 (no GTA here): A-SL-1 load detectable, A-SL-5 cash restored, A-SL-6 persisted monotonic play-time stat exists, A-SL-7 save writes observable. | Owner runs P-SL-01 on target PC; pass criteria PC-1…PC-5 in `phase0-probes/README-PROBES.md`. Until then Stage 1 may build only persistence-independent parts (see LSAX-STAGE-ACCEPTANCE.md S1-gate). |
| R-SL-2 | P1 | OPEN RISK | No play-time stat exists or it is not persisted/monotonic (PC-2 fails). | Fallback anchor carrier P-SL-02 (LSAX-written watermark stat) — only if a safe carrier stat is identified; else fallback F2 (anchor on wallet vector + GTA clock + save ledger; higher RECONCILE rate) — decision table LSAX-SAVELOAD-FEASIBILITY.md §7. |
| R-SL-3 | P1 | OPEN RISK | RECONCILE_REQUIRED frequency annoys players (sim: 2–3 % of anchorings under a crash/load-heavy mix). | Stage-1 runtime acceptance: 0 RECONCILE in P-SL-01 T1–T13 flows; RECONCILE only in injected mid-transaction crash tests. Resolution UX in debug inspector (Stage 1) and player UI (Stage 8). |
| R-SL-4 | P1 | OPEN RISK | Foreign/copied save files (downloaded 100 % saves, save editors) written while LSAX runs are mis-recorded as saves of the current world. | Require a save-event signal (autosave/manual-save status transition, P-SL-01 FLAGS) within a window of the file change, else mark slot FOREIGN (never matches → NO_MATCH → new-campaign choice). Needs P-SL-01 evidence of flag semantics. |
| R-SL-5 | P2 | OPEN RISK | Play-time stat granularity coarse (≥ 1 s) → more boundary ambiguity. | D-SL-9 prefix resolution; sim shows 4.3 % vs 3.8 % RECONCILE (adversarial) at 1 s vs 1 ms. |
| R-SL-6 | P2 | ASSUMPTION A-SL-4 | A GTA save snapshot could interleave with an LSAX tick. | Source evidence E1-8 (main thread blocked while SHVDN runs); not probed. If false, D-TX-1 must add a save-in-progress guard (`IS_AUTO_SAVE_IN_PROGRESS`, manual-save status) before apply. |
| R-DB-1 | P1 | OPEN RISK | Native SQLite fails to load inside SHVDN's shadow-copied AppDomain (E6-4 predicts default lookup fails). | D-DB-3 explicit `LoadLibraryW` preload; P-DB-01 steps 1–2. |
| R-DB-2 | P1 | OPEN RISK | Two fsync'd SQLite commits per transaction tick exceed tick budget on slow disks. | P-DB-01 measures commit p95; budget ≤ 25 ms per transaction tick (rare event). If exceeded: `synchronous=NORMAL` + WAL is NOT acceptable for the money path; instead keep FULL and move non-money writes off the transaction tick. |
| R-DB-3 | P2 | OPEN RISK | A leaked connection after domain reload holds locks (`database is locked`). | Close in `Aborted`; `busy_timeout`; P-DB-01 step 4 documents leak behaviour. |
| R-COMP-2 | P1 | OPEN RISK | Dependency DLL collisions (System.Memory, System.Buffers, SQLitePCLRaw, …) with other mods; SHVDN resolves by first `EndsWith` match. | Minimise dependencies; place under `scripts/LSAX/`; startup self-check logs the resolved path + version of every dependency and refuses to start the persistence layer on a mismatch (safe refusal). |
| R-ENV-1 | P1 | ASSUMPTION A-ENV-1 | User's SHVDN 3.7.x nightly differs from the pinned source commit in lifecycle/money/decorator code. | P-SL-01 logs SHVDN version; LSAX targets APIs present in 3.6.0 wherever possible; 3.7-only APIs behind reflection/feature flags. |
| R-ID-1 | P1 | OPEN RISK | Fingerprint fields insufficient to separate identical vehicles (same model, colour, plate) — auto-merge temptation. | Invariant: ambiguous → never merge; collision matrix LSAX-DOMAIN-MODEL.md §4.7; registration of lookalikes requires LSAX-issued plate or explicit player confirmation. |
| R-ID-2 | P2 | OPEN RISK | Decorators lost on recreation (expected). | Decorator is a hint only (invariant 2); P-ID-01 measures hit-rate. |
| R-ID-3 | P2 | OPEN RISK | Decorator registration requires memory-pattern unlock that may fail on a build. | Decorator fast path optional; feature-flagged off on failure. |
| R-ECO-1 | P1 | OPEN RISK | `Player.Money` is absolute set; other mods (Crime Jobs, trainers) may write cash in the same frame. | D-TX-1 re-read + verify inside the tick; abort on mismatch. Integration test with Crime Jobs in Stage 12. |
| R-ECO-2 | P2 | OPEN RISK | Underground income ceiling (sim: ≈ $37.6k per MT day at $20k FMV cars) may be too generous or too stingy. | Constants tunable; Stage 9 economy simulation with target bands (LSAX-HEAT-AND-UNDERGROUND-MODEL.md §8). |
| R-VAL-1 | P2 | ASSUMPTION A-VAL-1 | `GET_VEHICLE_MODEL_VALUE` (handling `nMonetaryValue`) is not a usable MSRP seed for add-ons. | LSAX catalogue overrides; class-default fallback; debug report of unpriced models. |
| R-UI-1 | P1 | OPEN RISK | No renderer proven on GTA Legacy + SHVDN 3.7 + current modpack. | UI spike UI-S1 with pass/fail criteria (LSAX-MASTER-SPEC §20); Core has no renderer dependency. |
| R-PERF-1 | P2 | OPEN RISK | `World.GetNearbyVehicles` / pool reads cost at high entity counts unknown. | Bounded cadence + caps in LSAX-PERFORMANCE-BUDGET.md; Stage 12 measurement. |
| R-TIME-1 | P2 | OPEN RISK | GTA time-skip detection (sleep) via clock jumps is heuristic. | Credit capped (≤ 12 MT h per event, ≤ 24 per 24 active hours); trainer clock changes can only add bounded credit. |
| R-ID-4 | P1 | OPEN RISK | Story personal vehicles may be mission entities (wrong exclusion/inclusion). | P-ID-01 logs mission flag + population type; rule refined before Stage 3 (OD-4). |
| R-ID-5 | P2 | ACCEPTED LIMITATION | Trainer clone spawned while original is Dormant may bind first (collision C9). | One VehicleId/title → no value duplication; original becomes AMBIGUOUS when seen. |
| R-COMP-1 | P1 | ASSUMPTION | Third-party mod behaviours assumed (mods unavailable in Phase 0). | Conservative "never own" matrix + forbidden-native IL scan; T-COMP-2..6 in Stage 12. |
| R-L10N-1 | P2 | ASSUMPTION A-L10N-1 | GTA font glyph coverage for NBSP/typographic characters unknown. | ASCII-safe formatting until UI-S1. |
| R-ODO-1 | P2 | OPEN RISK | Teleport vs legitimate fast transport (cargobob, trailer) misclassified. | Attachment check + speed consistency; T-ODO-2/6. |
| R-TX-1 | P2 | DESIGN CONSTRAINT | Money-neutral txns cannot use wallet evidence. | They carry no game-side effects (pure DB, atomic). |
