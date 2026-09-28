# LSAX — Measurable Stage Acceptance Criteria

Document: LSAX-STAGE-ACCEPTANCE.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

Rules: a stage is accepted only with the evidence listed (LSAX-TEST-STRATEGY.md §6: build hash, game build, SHVDN
version, modpack list, seeds, raw result files) and an independent read-only review. Every criterion below is
pass/fail and measurable. Cross-cutting at **every** stage: 0 user-facing hardcoded strings (T-L10N-6), RU/EN parity
(T-L10N-1..5), forbidden-native scan clean (T-COMP-1), no unbounded collections (inspector counters), all world
actions bounded (TSM §9), idempotency/anti-exploit designed in (not deferred to Stage 11).

## Phase 0 gate (this document set)

SPEC_APPROVED requires the checklist in LSAX-MASTER-SPEC-v1.0.md Appendix L with every item PASS and no open P0/P1
**that blocks the next stage**. Current self-assessment: item "save/load persistence model proven feasible" = **FAIL
(BLOCKER B-01)** → this draft cannot be approved as-is. The author does not grant SPEC_APPROVED.

## Stage 1 — Foundation, Identity & Persistence (split by B-01)

**S1a (may start once the spec is approved with B-01 explicitly carried as a gated item):**

| Criterion | Measure |
|---|---|
| Solution builds reproducibly: `LSAX.Core` (netstandard2.0, no SHVDN/UI refs), `LSAX.Persistence`, `LSAX.Adapters.Shvdn` (net48), `LSAX.Localization`, `LSAX.Diagnostics` | two clean builds → identical assembly hashes (deterministic build) |
| Core purity | reference graph check: `LSAX.Core` references only BCL (T-ARCH-1) |
| VehicleId/LsaxVin, fingerprint scoring, collision matrix | T-ID-1, T-ID-2 green; 20/20 collision rows |
| TimeService AT/MT | T-TIME-1, T-TIME-2 green |
| SQLite layer, schema v1, migrations framework, journal + projection + snapshot | T-DB-1..5 green; P-DB-01 PASS on target PC |
| Transaction-core skeleton (no market) | T-TX-1..3 green |
| Logging | `LSAX.log` format per compatibility §3; rotation test |
| Localisation framework | T-L10N-1..8 green with ≥ 40 keys |
| Configuration | invalid config values → defaults + WARN, never crash (fuzz 1 000 random configs) |
| Debug Inspector API | `InspectVehicle(entity)` returns identity/confidence, mileage, condition, ownership/provenance, history, valuation breakdown (stub allowed), market state (stub), as `MessageRef`s; renderer-independent |

**S1b (save/load synchronisation) — entry requires B-01 closed (P-SL-01 PC-1…PC-5 PASS 10/10):**

| Criterion | Measure |
|---|---|
| Anchoring, ledger, stop markers, ghost timelines, RECONCILE gate | T-SL-1 (800 episodes, 0 safety failures), T-SL-2 table green |
| Runtime | P-SL-01 T1–T13 re-run with LSAX S1b: 0 RECONCILE in T1–T13; correct anchor in 10/10 loads per slot kind |
| Crash recovery | T-TX-4 matrix 100 %; runtime: 10 forced script aborts at C1/C2 → ABORT/ROLL-FORWARD as predicted, 10/10 |
| Identity runtime | T-RT-ID-1: 0 wrong binds in 80 events; ambiguous cases refused |

## Stage 2 — Odometer, Condition & Modification State

| Criterion | Measure |
|---|---|
| Odometer accuracy and filtering | T-ODO-1 (±2 %), T-ODO-2 (0 m on 20 teleports), T-ODO-3 (±3 % at 15 FPS), T-ODO-4/5/6 (0 m) |
| Condition model | component wear deterministic from logged inputs (replay test); native repair restores body only per §07 rules; trainer "fix" does not reset mech or odometer (10/10) |
| BaselineMods/CurrentMods/ModificationHistory | snapshot at each lifecycle checkpoint (registration, acquisition, garage store, listing, inspection, transaction, periodic ≤ 1/60 s); 10 LSC visits → exact mod diff events |
| LSC/Benny's signal | used only if a probe shows ≥ 95 % reliable entry/exit detection; otherwise disabled (snapshots remain authoritative) |

## Stage 3 — Ownership, Provenance & Vehicle History

| Criterion | Measure |
|---|---|
| Title state machine | only transitions in LSAX-DOMAIN-MODEL.md §5.2 possible (T-TX-3 style exhaustive) |
| Lifecycle | DESTROYED/RETIRED/MISSING transitions; records retained (§5.4) |
| Accident detection | scripted crashes at 30/60/100 km/h → severity MINOR/MODERATE/SEVERE classification ≥ 90 % agreement over 30 runs; dedupe: one event per collision sequence (≤ 1 per 3 s per vehicle) |
| Mission exclusions | 10 story missions played: 0 mission vehicles registered or sellable |
| Personal-vehicle rules | P-ID-01 outcome applied (R-ID-4 closed) |

## Stage 4 — Valuation & Economy Engine

| Criterion | Measure |
|---|---|
| Golden vectors | T-VAL-1..6 exact match / 0 failures |
| Tuning | T-VAL-SIM-1..5 pass; tuned constants recorded with the simulation report |
| GTA money adapter | wallet port only in transaction core (IL allowlist); T-RT-TX-1 exact deltas |
| Fees/sinks | T-ECO-1, T-ECO-2 |

## Stage 5 — Transaction Core (before any marketplace)

| Criterion | Measure |
|---|---|
| Protocol | single-tick PREPARE/APPLY/COMMIT; T-TX-1..5 green; T-SL-1 re-run with real core |
| Runtime | 100 transactions + 20 forced crashes (C0–C3 × modes): 0 duplicated money, 0 ownership without money, 0 double sales |
| Budget | T-PERF-2 (≤ 25 ms p95) |

## Stage 6 — NPC Market Simulation

| Criterion | Measure |
|---|---|
| Generation | T-GEN-1..7 |
| Market dynamics | 30 simulated MT days: live listings stay within [200, 600]; per-segment demand/supply indices within [7 000, 13 000]; same seed → identical market (digest) |
| Re-roll protection | rewind to day N and replay: identical listings/offers for identical player actions |

## Stage 7 — Legal Market Backend

| Criterion | Measure |
|---|---|
| Flows via debug adapter | T-MKT-1: list, search/filter, offers, counters (≤ 3 rounds), expiry (MT), accept, fees, legal-title checks (ineligible titles refused 100 %) |
| Stale protection | offer invalidated after vehicle state hash change (odometer bucket / condition bucket / mods) 100 % |
| Disclosure | inspection/remote disclosure shows GENERATED history flagged |

## Stage 8 — Player UI, Mail & Notifications

| Criterion | Measure |
|---|---|
| Renderer | UI-S1 spike passed; renderer behind `IUiRenderer`; Core has 0 references to the renderer |
| Screens | Buy / Sell / Garage / Listings / Messages / Market reachable; every string from localisation |
| Mail | persistent (timeline-coupled), re-renders on locale switch; ≤ 500 messages retained (archive beyond) |
| Notifications | transient, ≤ 1 per 3 s, never block input |
| Parity | full RU/EN screenshot audit of every screen (checklist signed) |

## Stage 9 — Underground & Heat

| Criterion | Measure |
|---|---|
| Heat | T-HEAT-1..6 |
| Access lifecycle | LOCKED/UNLOCKED/LAYLOW per protagonist, timeline-coupled |
| Anti-farm | farming script (steal+sell loop for 2 real hours): income per active hour within the band set by R-ECO-2 decision; 0 sales beyond caps |
| No police engine | T-COMP-2 |

## Stage 10 — Physical Inspection & Handover

| Criterion | Measure |
|---|---|
| Bounded actions | every action in TSM §9 has timeout/retry/fallback/abort tests; 50 deals with random interruptions: 0 corrupted transaction states, 0 leaked entities after 5 s |
| Interruption semantics | pre-commit interruptions move no money (100 %); post-commit delivery always completes or falls back to storage (100 %) |

## Stage 11 — Anti-Exploit Verification

All attacks in LSAX-TEST-STRATEGY.md §5 scripted; 0 successful value duplication or title laundering; findings fixed
or accepted with a written rationale.

## Stage 12 — Compatibility & Performance Hardening

T-COMP-1..7 and T-PERF-1..8 pass on the full target modpack; 4-hour soak with 0 LSAX exceptions and all caps respected.

## Stage 13 — Release Candidate

Reproducible clean build (hash match on two machines); all L1/L2 green; migration/recovery suites green; package
file list + SHA-256 manifest verified; RU/EN audit signed; 4-hour runtime test; independent read-only audit; final ZIP.
