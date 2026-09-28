# LSAX — Testing Strategy

Document: LSAX-TEST-STRATEGY.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

## 1. Structure

| Layer | Runs where | Depends on GTA? | Framework |
|---|---|---|---|
| L1 Pure / offline | CI (Linux/Windows), every commit | no | xUnit on `LSAX.Core` (netstandard2.0, no SHVDN reference) |
| L2 Integration / harness | CI | no — fake ports (`FakeWorldPort`, `FakeWalletPort`, `FakeClockPort`, `FakeSaveSystem`) + real SQLite | xUnit + real `Microsoft.Data.Sqlite` |
| L3 Runtime | target PC, per stage | yes | `LSAX.RuntimeTests` debug-only SHVDN script: scripted scenarios, JSON result log; plus manual protocols with pass criteria |

Oracles: the Phase 0 Python reference models (`phase0-probes/sim/*.py`) export golden vectors as JSON; C# must match
exactly (cross-implementation determinism). Property tests use SplitMix64-seeded generators (no external property
testing dependency) with printed seeds for reproduction.

CI gate: all L1 + L2 green, localisation parity green, forbidden-native IL scan green, before any merge.
Stage gates additionally require the listed L3 runs (LSAX-STAGE-ACCEPTANCE.md).

## 2. L1 — pure / offline

| ID | Area | Test | Pass |
|---|---|---|---|
| T-ARCH-1 | architecture | reference-graph check: `LSAX.Core` references only BCL assemblies (no SHVDN, SQLite, renderer) | 0 forbidden references |
| T-MATH-1 | arithmetic | `rdiv`, `interp`, `round_money`, SplitMix64 seed-0 output, rejection sampling vectors | exact equality with Python reference |
| T-VAL-1..4 | valuation | 12 golden vectors (FMV, BUV, CAV, A, dealer, fence, chop, export) | exact equality with `valuation_ref.py` |
| T-VAL-5 | valuation | breakdown reconciliation | recompute from lines == FMV, 100 % of grid |
| T-VAL-6 | valuation | properties P1–P7 over the 4 704-case grid | 0 failures |
| T-VAL-SIM-1..5 | valuation tuning | LSAX-VALUATION-MODEL.md §9 | as specified |
| T-HEAT-1..6 | Heat | LSAX-HEAT-AND-UNDERGROUND-MODEL.md §9 | as specified |
| T-TIME-1 | time | AT from synthetic GT streams (negative Δ, 5 s stall, 10 FPS, pause toggles) | exact expected AT |
| T-TIME-2 | time | MT base rate, skip credit caps (12 h sleep → 720; 3 sleeps/day → ≤ 1 440), negative GC jump → 0, offline → 0 | exact |
| T-COND-1 | condition calibration | runtime wear model vs generation model: COMMUTER, 100 000 km, scheduled services | final M within ±5 % (MASTER §07) |
| T-GEN-1..7 | NPC generation | LSAX-NPC-GENERATION-MODEL.md §8 | as specified |
| T-TX-1 | idempotency | same key twice on the active path → second returns DUPLICATE with identical outcome, no effect | 100 % |
| T-TX-2 | validation | each precommit rule (TSM §6) has a failing and a passing case | 100 % |
| T-TX-3 | state machine | exhaustive transition table: only allowed transitions succeed | 100 % |
| T-ID-1 | identity scoring | collision matrix C1–C20 as table-driven cases with fake fingerprints | expected state for each row |
| T-ID-2 | identity | thresholds: score 85 unique → BIND; 84 → AMBIGUOUS; gap 19 → AMBIGUOUS; never auto-merge | 100 % |
| T-L10N-1..8 | localisation | LSAX-LOCALIZATION-CONTRACT.md §7 | as specified |
| T-ECO-1 | fees | fee formulas with min/max caps, rounding | exact |
| T-ECO-2 | arbitrage | T-VAL-SIM-2 | as specified |

## 3. L2 — integration / harness

| ID | Area | Test | Pass |
|---|---|---|---|
| T-SL-1 | save/load model | C# port of `journal_timeline_ref.py`: 800 episodes, both mixes, G = 1 ms and 1 000 ms | 0 safety-invariant failures; tripwire as in the reference |
| T-SL-2 | anchoring | table cases: continuation, in-session load of each slot kind, ghost slot with pending txn, NO_MATCH new game, AMBIGUOUS coincidences | expected verdict per case |
| T-TX-4 | recovery | crash injection at C0–C3 × {script reload, game crash + load, offline window} (TSM §10 matrix) | matrix outcomes, 100 % |
| T-TX-5 | concurrency | fake Crime-Jobs cash write between PREPARE and apply | ABORTED_CONCURRENT_CASH |
| T-DB-1 | schema | create from scratch; all CHECK constraints reject out-of-range values | 100 % |
| T-DB-2 | migrations | each migration from its fixture DB; golden projection dump equality; pre-migration backup exists | 100 % |
| T-DB-3 | projection | rebuild from journal == incremental projection (bit-for-bit dump) after random 5 000-commit histories | 100 % |
| T-DB-4 | integrity | corrupted DB file → read-only mode + localised prompt; no transactions | 100 % |
| T-DB-5 | newer schema | DB with higher schema_version → refuse to open | 100 % |
| T-ID-3 | reacquisition | fake world: store/retrieve, stream out/in, plate change while bound/dormant, clones, handle reuse | matrix outcomes |
| T-MKT-1 | legal market | end-to-end via debug adapter: list → offers → counter → accept → commit; expiry in MT; stale offer rejected after vehicle state change | as specified in Stage 7 acceptance |

## 4. L3 — runtime (target PC)

| ID | Area | Test | Pass |
|---|---|---|---|
| P-SL-01/02, P-ID-01, P-DB-01 | Phase 0 probes | `phase0-probes/README-PROBES.md` | PC-1…PC-5 (B-01) |
| T-RT-ID-1 | binding | 20 × each: garage store/retrieve, 1 km stream-out/in, save/load, impound retrieve | correct VehicleId 100 %; 0 wrong binds; ambiguous cases refused |
| T-ODO-1 | odometer accuracy | drive a fixed 5.0 km route (measured by summed waypoint distance) ×5 | within ±2 % |
| T-ODO-2 | teleport rejection | trainer teleport 2 km ×10; script teleport (fade + set position) ×10 | 0 m added; `TELEPORT_REJECTED` logged |
| T-ODO-3 | low FPS | FPS limited to 15 on the same route | within ±3 % |
| T-ODO-4 | pause / loading / cutscene | 10 min pause menu, load screen | 0 m added |
| T-ODO-5 | stream gaps / handle reuse | vehicle despawned and respawned; unrelated vehicle reusing handle | no distance transferred |
| T-ODO-6 | carried vehicles | vehicle on a trailer / flatbed / cargobob | 0 m added while attached |
| T-RT-TX-1 | wallet | 100 buy/sell via debug adapter per protagonist | wallet deltas exactly = committed amounts |
| UI-S1 | renderer feasibility spike | 8 pass/fail items in LSAX-MASTER-SPEC-v1.0.md §20 (glyphs, cost, input, isolation, reload, layouts, soak) | all 8 pass for the chosen renderer |
| T-RT-UI-1 | UI spike | LSAX-MASTER-SPEC §20 UI-S1 | pass/fail criteria there |
| T-COMP-1..7 | compatibility | LSAX-COMPATIBILITY-CONTRACT.md §5 | as specified |
| T-PERF-1..8 | performance | LSAX-PERFORMANCE-BUDGET.md §6 | as specified |

## 5. Adversarial pass (Stage 11)

Attempts to break: duplicate VIN, replayed commits, trainer mutation (plate/colour/mod/odometer via trainer),
save/load/reload/crash mid-deal, stale listing, destroyed-vehicle sale, sold-vehicle respawn, stolen→legal bypass,
market farming. Each attack has a scripted reproduction and an expected refusal (anti-exploit invariants AX-1…AX-12
in LSAX-MASTER-SPEC §24). Pass: 0 successful value duplication or title laundering.

## 6. What counts as evidence

A test result is evidence only with: build hash, game build, SHVDN version, modpack list, seed (if any), and the raw
result file. "Looks logical" / "ran for a long time" are not acceptance criteria.
