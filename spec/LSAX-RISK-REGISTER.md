# LSAX — Risk Register & Open Decisions

Document: LSAX-RISK-REGISTER.md · Spec: LSAX MASTER SPEC v1.0 DRAFT2 · Status: DRAFT for independent re-audit

Severity: **P0** makes the architecture unsafe or unproven; **P1** is a material specification/feasibility gap;
**P2** tracked with mitigation. **Gate (D-GATE-1, MASTER ROADMAP v3): every open P0 and P1 blocks SPEC_APPROVED, and no
stage — or any part of a stage — starts before SPEC_APPROVED.** There is no Stage 1a/1b split and no stage-deferred
P0/P1. Only disposable probes (`phase0-probes/`) and Phase-0 corrections are allowed while any P0/P1 is open.
"Closure" column: OFFLINE = can be closed by offline proof; RUNTIME = needs target-runtime evidence (GTA V Legacy
1.0.3725.0, SHVDN 3.7.x, full modpack) supplied by the project owner (PO). IDs match `risks.md`.

## 1. Blockers and P1 risks (all block SPEC_APPROVED while open)

| ID | Sev | Label | Risk | Trigger / evidence | Mitigation | Exit criterion | Closure | Status |
|---|---|---|---|---|---|---|---|---|
| B-01 | P0 | BLOCKER | Model D rests on runtime assumptions A-SL-1, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14 (SAVELOAD §9) | no GTA runtime in Phase 0 | P-SL-01 prepared (compile-verified, README-PROBES); fallback table SAVELOAD §7 degrades only toward refusal | P-SL-01 PC-1, PC-2, PC-3, PC-4, PC-5, PC-7, PC-8 PASS 10/10 on the target runtime, full modpack | RUNTIME (PO) | OPEN — BLOCKED_RUNTIME_VALIDATION |
| R-SL-2 | P1 | OPEN RISK | no persisted play-time stat restored exactly on load | PC-2 fails | SAVELOAD §7 row PC-2 (wallet-only exclusion or refuse; re-simulate) | PC-2 pass, or fallback chosen and re-simulated | RUNTIME (PO) | OPEN |
| R-SL-3 | P1 | OPEN RISK | RECONCILE_REQUIRED too frequent for players | DRAFT2 sim: realistic mix 15.2–16.7 % of non-first session starts (crash-heavy mix), adversarial 58–60 %; causes: in-transaction crashes, pre-install / unobserved files, forward loads in the same process | safety over convenience; explicit one-choice resolution UI; optimisation O-SL-1 only after runtime evidence | P-SL-01 logs replayed through the reference model: normal flows T1–T13 refuse only for documented causes; owner accepts the RECONCILE profile as a product decision | RUNTIME (PO) + owner decision | OPEN |
| R-SL-4 | P1 | OPEN RISK | foreign/copied save files taken as lineage | DRAFT1 INFERRED windows (audit P0-03) | D-SL-13: only observed + event-corroborated or byte-identical content is lineage; everything else UNTRUSTED; regression P0-03 | design closed (73/73 regression PASS); runtime part = A-SL-12 (PC-4) under B-01 | OFFLINE ✔ / RUNTIME via B-01 | MITIGATED BY DESIGN; runtime under B-01 |
| R-SL-7 | P1 | OPEN RISK | residual: forged save loaded and swapped back to trusted bytes before LSAX's scan, reproducing a trusted fingerprint | deliberate tampering outside TM-1 (SAVELOAD §4.9); regression P0-03/23 reproduces | documented threat model; A-SL-8 probed by PC-8 | owner accepts TM-1 boundary; PC-8 PASS | RUNTIME (PC-8) + owner decision | OPEN |
| R-DB-1 | P1 | OPEN RISK | native SQLite fails to load in SHVDN shadow-copy domain | E6-4 IL evidence predicts default lookup failure | D-DB-3 explicit preload | P-DB-01 steps 1–3 PASS | RUNTIME (PO) | OPEN |
| R-DB-2 | P1 | OPEN RISK | 2 fsync'd commits per transaction tick too slow | slow disks | budget 25 ms p95; measure | P-DB-01 commit p95 ≤ 10 ms on the target PC | RUNTIME (PO) | OPEN |
| R-COMP-2 | P1 | OPEN RISK | dependency DLL collisions (first `EndsWith` match wins) | another mod ships older System.Memory etc. | minimal deps in their own folder; startup self-check → safe refusal | P-DB-01 on the full modpack resolves every dependency from its own folder (logged path + version) | RUNTIME (PO) | OPEN |
| R-ENV-1 | P1 | ASSUMPTION A-ENV-1 | user's SHVDN 3.7.x differs from pinned source | nightly drift | P-SL-01 logs version; target 3.6.0 API subset; reflection for 3.7-only | version recorded and lifecycle behaviour matches E1 (PC-1, PC-5) | RUNTIME (PO) | OPEN |
| R-ID-1 | P1 | OPEN RISK | identical vehicles not separable → temptation to merge | legacy cars with default plates | never auto-merge; lossless bounded search (D-ID-7); handle never identity (D-ID-6); LSAX plates | identity regressions (P1-01/P1-02) PASS: no automatic bind without unique ≥ 85 and gap ≥ 20 over the complete candidate set | OFFLINE | MITIGATED BY DESIGN (regression) |
| R-ID-4 | P1 | OPEN RISK | story personal vehicles may be mission entities → excluded wrongly / or included wrongly; feeds LEGACY_TRUSTED (D-PROV-1) | unknown `IS_ENTITY_A_MISSION_ENTITY`/population type for personal vehicles | P-ID-01 logs flags; until then LEGACY_TRUSTED is empty and story vehicles are never sellable | P-ID-01 run; rule updated in DOMAIN §4.6/§5.3 | RUNTIME (PO) | OPEN |
| R-ECO-1 | P1 | OPEN RISK | other mods write cash (absolute set) near LSAX transactions | Crime Jobs payouts | verify-before-apply; abort; wallets never recovery evidence (D-TX-4) | P-SL-01 PC-8 wallet-change log on the full modpack shows no change-and-restore between two ticks (A-SL-14) | RUNTIME (PO) | OPEN |
| R-UI-1 | P1 | OPEN RISK | no renderer proven on Legacy + SHVDN 3.7 + modpack | none tested | UI-S1 feasibility spike (disposable probe) with pass/fail (MASTER §20) | UI-S1 pass on the target runtime | RUNTIME (PO) | OPEN |
| R-COMP-1 | P1 | ASSUMPTION | third-party mod behaviours (RDE, RealParamedics, Persist Corpses, Crime Scene Aftermath, Lively World, Unified Shadow Logger, Crime Jobs) assumed, not observed | mods unavailable in Phase 0 | conservative "never own" matrix + forbidden-native scan | P-SL-01 / P-ID-01 full-modpack runs log no violation of the COMPATIBILITY §1 matrix | RUNTIME (PO) | OPEN |

## 2. P2 risks

| ID | Label | Risk | Mitigation | Exit |
|---|---|---|---|---|
| R-SL-5 | OPEN RISK | coarse play-time granularity increases ambiguity | D-SL-9; measure G | G measured by P-SL-01 |
| R-SL-6 | ASSUMPTION A-SL-4 | a save snapshot could interleave an LSAX tick | source evidence E1-8; fallback: skip apply while save flags active | T-SL runtime crash tests |
| R-DB-3 | OPEN RISK | leaked connection locks DB after reload | close in `Aborted`; busy_timeout | P-DB-01 step 4 |
| R-ID-2 | OPEN RISK | decorators lost on recreation | hint only | P-ID-01 hit-rate recorded |
| R-ID-3 | OPEN RISK | decorator unlock fails on a game build | decorator is an ordering hint only; identity results unchanged without it | feature flag |
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
| OD-3 | anchor fallback if PC-2 fails | wallet-only exclusion vs refuse-always (SAVELOAD §7); an in-save carrier only if P-SL-02 proves it | before SPEC_APPROVED | P-SL-01/02 |
| OD-4 | story personal vehicle policy | sellable (with respawn block) vs never sellable | S3 | P-ID-01 |
| OD-5 | legacy registration UX (never changes provenance: import yields UNKNOWN unless LEGACY_TRUSTED, D-PROV-1) | opt-in wizard at first run vs on first entry | S3 | owner preference |
| OD-6 | underground unlock content | contact mission design | S9 | owner preference |

## 4. Assumption register

"Relied upon" = the design depends on it; "not relied upon" = a hypothesis measured only for tuning.

| ID | Assumption | Relied upon? | Closed by |
|---|---|---|---|
| A-SL-1 | SP save load restarts the SHVDN script domain (new ScriptHookV fiber) | yes (or polling fallback) | P-SL-01 PC-1 |
| A-SL-3 | `Aborted` runs with post-load game state visible | no (design never reads game state in `Aborted`) | P-SL-01 PC-6 |
| A-SL-4 | a GTA save snapshot never interleaves one LSAX tick | yes | source E1-8; P-SL-01 PC-4 tick markers |
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
