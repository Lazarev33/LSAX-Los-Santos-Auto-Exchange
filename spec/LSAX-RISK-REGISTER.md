# LSAX — Risk Register & Open Decisions

Document: LSAX-RISK-REGISTER.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

Severity: **P0** blocks Stage 1 (or makes the architecture unsafe); **P1** must close before the stage that depends
on it; **P2** tracked with mitigation. Owner "PO" = project owner (runs probes on the target PC); "S<n>" = stage team.
IDs match `risks.md`.

## 1. Blockers and P1 risks

| ID | Sev | Label | Risk | Trigger / evidence | Mitigation | Exit criterion | Owner | Due |
|---|---|---|---|---|---|---|---|---|
| B-01 | P0 | BLOCKER | Model D rests on A-SL-1/5/6/7 (load detectable, cash restored, persisted monotonic play-time stat, save-file writes observable) | no GTA runtime in Phase 0 | P-SL-01 ready (compile-verified); fallback table SAVELOAD §7 | P-SL-01 PC-1…PC-5 PASS 10/10 on full modpack | PO | before S1b |
| R-SL-2 | P1 | OPEN RISK | no suitable play-time stat | PC-2 fails | F1 watermark stat (P-SL-02) or F2 coordinate + re-simulation | PC-2 pass, or F1/F2 chosen with sim re-run | PO + S1 | before S1b |
| R-SL-3 | P1 | OPEN RISK | RECONCILE_REQUIRED too frequent for players | sim 2–3 % of anchorings under crash/load-heavy mix | conservative by design; measure real rate | 0 RECONCILE in P-SL-01 T1–T13 flows with S1b | S1 | S1b |
| R-SL-4 | P1 | OPEN RISK | foreign/copied save files recorded as saves of the current world | user copies saves into profile folder while playing | correlate file change with save-event flags; else FOREIGN | P-SL-01 shows reliable save-event flags (or rule defined without them) | PO + S1 | S1b |
| R-DB-1 | P1 | OPEN RISK | native SQLite fails to load in SHVDN shadow-copy domain | E6-4 IL evidence predicts default lookup failure | D-DB-3 explicit preload | P-DB-01 steps 1–3 PASS | PO | S1a |
| R-DB-2 | P1 | OPEN RISK | 2 fsync'd commits per transaction tick too slow | slow disks | budget 25 ms p95; measure | T-PERF-8 / P-DB-01 p95 ≤ 10 ms, or redesign before S5 | PO + S5 | S5 |
| R-COMP-2 | P1 | OPEN RISK | dependency DLL collisions (first `EndsWith` match wins) | another mod ships older System.Memory etc. | minimal deps under `scripts/LSAX/`; startup self-check → safe refusal | T-COMP-7 | S1a / S12 | S1a |
| R-ENV-1 | P1 | ASSUMPTION A-ENV-1 | user's SHVDN 3.7.x differs from pinned source | nightly drift | P-SL-01 logs version; target 3.6.0 API subset; reflection for 3.7-only | version recorded and lifecycle behaviour matches E1 | PO | S1a |
| R-ID-1 | P1 | OPEN RISK | identical vehicles not separable → temptation to merge | legacy cars with default plates | never auto-merge; LSAX plates; confirmation only with a single candidate | T-ID-1/2, T-RT-ID-1 | S1 | S1a |
| R-ID-4 | P1 | OPEN RISK | story personal vehicles may be mission entities → excluded wrongly / or included wrongly | unknown `IS_ENTITY_A_MISSION_ENTITY`/population type for personal vehicles | P-ID-01 logs flags; rule refined | P-ID-01 run; rule updated in DOMAIN §4.6 | PO + S3 | S3 |
| R-ECO-1 | P1 | OPEN RISK | other mods write cash (absolute set) near LSAX transactions | Crime Jobs payouts | verify-before-apply; abort | T-COMP-5 | S5 / S12 | S5 |
| R-UI-1 | P1 | OPEN RISK | no renderer proven on Legacy + SHVDN 3.7 + modpack | none tested | UI-S1 spike with pass/fail (MASTER §20) | UI-S1 pass | S8 (spike can run in S1a) | S8 |
| R-COMP-1 | P1 | ASSUMPTION | third-party mod behaviours (RDE, RealParamedics, Persist Corpses, Crime Scene Aftermath, Lively World, Unified Shadow Logger, Crime Jobs) assumed, not observed | mods unavailable in Phase 0 | conservative "never own" matrix + forbidden-native scan | T-COMP-2..6 | S12 (smoke in S1a) | S12 |

## 2. P2 risks

| ID | Label | Risk | Mitigation | Exit |
|---|---|---|---|---|
| R-SL-5 | OPEN RISK | coarse play-time granularity increases ambiguity | D-SL-9; measure G | G measured by P-SL-01 |
| R-SL-6 | ASSUMPTION A-SL-4 | a save snapshot could interleave an LSAX tick | source evidence E1-8; fallback: skip apply while save flags active | T-SL runtime crash tests |
| R-DB-3 | OPEN RISK | leaked connection locks DB after reload | close in `Aborted`; busy_timeout | P-DB-01 step 4 |
| R-ID-2 | OPEN RISK | decorators lost on recreation | hint only | P-ID-01 hit-rate recorded |
| R-ID-3 | OPEN RISK | decorator unlock fails on a game build | fast path optional | feature flag |
| R-ID-5 | ACCEPTED LIMITATION | trainer clone spawned while the original is Dormant can bind first (C9) | no value duplication (one VehicleId/title); original becomes AMBIGUOUS | documented |
| R-ECO-2 | OPEN RISK | underground income ceiling (sim ≈ $37.6k/MT day at $20k FMV) mis-balanced | tunable constants; Stage 9 economy sim | band decided (OD-2) |
| R-VAL-1 | ASSUMPTION A-VAL-1 | `GET_VEHICLE_MODEL_VALUE` not usable as MSRP seed for add-ons | catalogue overrides; class defaults | T-COMP-6 report |
| R-PERF-1 | OPEN RISK | pool-read cost at high entity counts | caps + time slicing | T-PERF-3 |
| R-TIME-1 | OPEN RISK | time-skip detection heuristic | capped credits | T-TIME-2 + runtime sleep test |
| R-L10N-1 | ASSUMPTION A-L10N-1 | GTA font glyph coverage for special characters | ASCII-safe formatting until UI-S1 | UI-S1 |
| R-ODO-1 | OPEN RISK | teleport vs. legitimate high-speed movement (jets carrying cars, cargobob) misclassified | attachment check + speed-consistency rule | T-ODO-2/6 |
| R-TX-1 | DESIGN CONSTRAINT | money-neutral transactions cannot use wallet evidence | they carry no game-side effects (pure DB) | T-TX-4 |

## 3. Open decisions

| ID | Decision needed | Options | Needed by | Input |
|---|---|---|---|---|
| OD-1 | UI renderer | LemonUI (SHVDN3 build) / NativeUI / custom Scaleform / in-house text overlay | S8 (spike earlier) | UI-S1 results |
| OD-2 | underground income target band | e.g. 0.6–1.2× legal flipping income per active hour | S9 | Stage 9 economy sim |
| OD-3 | anchor fallback if PC-2 fails | F1 watermark stat vs F2 coordinate | S1b | P-SL-01/02 |
| OD-4 | story personal vehicle policy | sellable (with respawn block) vs never sellable | S3 | P-ID-01 |
| OD-5 | legacy registration UX | opt-in wizard at first run vs on first entry | S1a/S3 | owner preference |
| OD-6 | underground unlock content | contact mission design | S9 | owner preference |

## 4. Assumption register

"Relied upon" = the design depends on it; "not relied upon" = a hypothesis measured only for tuning.

| ID | Assumption | Relied upon? | Closed by |
|---|---|---|---|
| A-SL-1 | SP save load restarts the SHVDN script domain (new ScriptHookV fiber) | yes (or polling fallback) | P-SL-01 PC-1 |
| A-SL-3 | `Aborted` runs with post-load game state visible | no (design never reads game state in `Aborted`) | P-SL-01 PC-6 |
| A-SL-4 | a GTA save snapshot never interleaves one LSAX tick | yes | source E1-8; runtime crash tests (S1b) |
| A-SL-5 | `SPx_TOTAL_CASH` restored from the save on load | yes | P-SL-01 PC-3 |
| A-SL-6 | a persisted, monotonic play-time stat exists | yes | P-SL-01 PC-2 |
| A-SL-7 | save-file writes observable (mtime/size/hash) while LSAX runs | yes | P-SL-01 PC-4 |
| A-ENV-1 | user's SHVDN 3.7.x lifecycle/money/decorator code equals pinned source @56ba3bf | yes | P-SL-01 logs version |
| A-DB-2 | CLR defers `Thread.Abort` during native SQLite calls; SQLite atomic commit survives process kill | yes | documented platform semantics; P-DB-01 reload tests |
| A-DB-3 | default SQLitePCLRaw native lookup fails inside SHVDN's shadow-copied domain | no (mitigated by D-DB-3 either way) | P-DB-01 step 1 |
| A-ID-1 | decorators survive stream-out/in of the same entity | no | P-ID-01 |
| A-ID-2 | decorators survive garage store/retrieve and save/load | no (expected false) | P-ID-01 |
| A-ID-3 | entity handles change when the game recreates a vehicle | no (design handles both) | P-ID-01 |
| A-VAL-1 | `GET_VEHICLE_MODEL_VALUE` (handling `nMonetaryValue`) is a usable MSRP seed for add-ons | partly (fallback only) | T-COMP-6 report |
| A-L10N-1 | GTA fonts render Cyrillic (official RU localisation) but NBSP/typographic glyphs are unproven | yes (Cyrillic) / no (typography) | UI-S1 |
| A-COMP-1 | Unified Shadow Logger can tail a UTF-8 line log at a configurable path | yes | Stage 12 |
| A-COMP-2 | third-party mod behaviours as stated in COMPATIBILITY §1 | yes (conservatively) | T-COMP-2..6 |
