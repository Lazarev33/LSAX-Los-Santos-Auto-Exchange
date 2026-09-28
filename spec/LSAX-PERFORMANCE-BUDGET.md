# LSAX — Performance Budget & Cadence

Document: LSAX-PERFORMANCE-BUDGET.md · Spec: LSAX MASTER SPEC v1.0 DRAFT2 · Status: DRAFT for independent re-audit

All numbers are **design budgets** (DESIGN DECISION). None is measured yet (no GTA runtime in Phase 0); Stage 12
verifies them on the target PC (T-PERF-*). Hard platform limit: SHVDN aborts a script whose tick exceeds
`ScriptTimeoutThreshold` = 5 000 ms by default (E1-7). LSAX treats any script-thread operation > 100 ms as a defect.

## 1. Principles

- **No full-world scan per frame.** World queries are bounded by radius, count and cadence, time-sliced.
- Pure Core computation (valuation, market steps, NPC generation) runs on a worker thread; it never calls natives.
- All natives run on the script thread inside the tick. All SQLite I/O runs on the DB worker thread (except the
  synchronous money-path waits of the transaction core).
- Every collection, cache, queue and task is bounded and has an eviction/cleanup rule (§4).

## 2. Budget table (script thread, per tick unless stated)

| Subsystem | Cadence | Work bound | Budget avg / p99 |
|---|---|---|---|
| Active vehicle tracking (player vehicle + ≤ 8 recently driven) | every tick | ≤ 9 vehicles × ≤ 4 natives (position, speed, health) | 0.10 / 0.30 ms |
| Odometer integration | every tick | arithmetic on tracked vehicles | included above |
| Local reconciliation scan | every 1 000 ms wall | `World.GetNearbyVehicles(player, 120 m)`, process ≤ 64 nearest; full fingerprint (~40 natives) for ≤ 8 candidates per scan, time-sliced ≤ 2 per tick | 0.50 / 1.00 ms on scan ticks |
| Bound re-observation (D-ID-6) | each Bound entity ≤ every 2 000 ms, time-sliced ≤ 4 per tick | full fingerprint (~40 natives) + lossless decision over K1 (≤ 32 per slice) ∪ K2 (≤ 64) from DB indexes | 0.30 / 0.80 ms |
| Market simulation step | every 60 MT min (= 2 real min) | worker: ≤ 30 generated vehicles, ≤ 200 listings updated, ≤ 50 offers resolved; main thread only applies results | worker ≤ 50 ms; main 0.20 / 0.50 ms |
| Persistence enqueue (non-money) | on events | enqueue only | 0.05 / 0.10 ms |
| **Transaction tick** (atomic core) | ≤ 1 per tick, ≤ 6 per MT min | 2 synchronous fsync'd journal commits (PREPARE, COMMIT on `main`) + 1 projection commit (`proj`, synchronous=NORMAL, no fsync) + ≤ 10 natives | **≤ 25 ms p95, ≤ 50 ms max** (allowed spike; R-DB-2) |
| Save-file ledger poll | every 2 000 ms wall, every tick while a save-event signal is active, and before each transaction apply | metadata of ≤ 16 files + 3 wallet stats + PT; SHA-256 on the worker only for changed files | 0.20 / 0.50 ms |
| MT checkpoint (`SYS_MT_CHECKPOINT`) | every 60 s AT and at every skip credit (TIME §2.2) | enqueue 1 system transaction (coalescible) | 0.02 ms |
| Session token re-tag | every tick | 1 `DECOR_GET_INT` on the player ped; `DECOR_SET_INT` only after a character switch | 0.01 ms |
| Notifications | queue ≤ 32, show ≤ 1 per 3 s | | 0.05 / 0.10 ms |
| Physical world scene (Stage 10) | ≤ 1 concurrent deal scene | ≤ 16 LSAX entities; tasks bounded (TSM §9) | 0.50 / 1.00 ms while active |
| Debug inspector overlay (when open) | every tick | ≤ 40 text lines | 1.00 / 2.00 ms |
| **Total LSAX (excl. transaction ticks, inspector closed)** | | | **≤ 1.0 ms avg, ≤ 2.0 ms p99** |

Session start (anchoring, projection rebuild ≤ 200 commits, integrity quick_check ≤ 2 s) runs as a staged
start-up sequence spread over ticks; market and transactions are frozen until it completes (target ≤ 5 s wall).

## 3. High entity counts

- The scan cost is bounded by the 64-nearest cap regardless of `World.VehicleCount`; with more candidates the scan
  rotates through distance rings over successive scans.
- Fingerprint work per scan is capped (≤ 8); unresolved candidates wait for the next scan.
- If a tick's LSAX work exceeds 4 ms, the scheduler defers all non-critical subsystems to the next tick
  (back-pressure) and logs `PERF_DEFER` (rate-limited).

## 4. Bounded collections

| Collection | Cap | Eviction / cleanup |
|---|---|---|
| Runtime bindings | 256 | LRU, DORMANT first |
| Tracked (odometer) vehicles | 9 | least recently driven |
| Fingerprint cache (per handle, per session) | 128 | LRU; scheduling/ordering hint only, never a verdict; overwritten on every observation |
| Notification queue | 32 | drop oldest low-priority |
| DB write queue (non-money) | 10 000 items | back-pressure: coalesce odometer checkpoints; never drop money-path jobs |
| LSAX spawned-entity registry | 16 | released at deal end / abort / session start sweep |
| Missing-key diagnostics | 512 keys | stop recording after cap (counter continues) |
| Log files | 5 × 5 MiB | rotation |
| Snapshots | 8 (+ referenced) | LSAX-DB-SCHEMA-DRAFT.md §5 |
| NPC live listings | 600 | expiry in MT; oldest expire first |
| Audit log rows | 100 000 | ring |

## 5. Long sessions

- DB growth estimate ≈ 1 MiB per hour of play (transactions, checkpoints, market steps) → < 250 MiB after 200 h
  with compaction (LSAX-DB-SCHEMA-DRAFT.md §6).
- Managed memory target ≤ 64 MiB steady state; no growth trend > 1 MiB/h after the first hour.
- No per-frame allocations in tracking/odometer paths (struct buffers reused).

## 6. Tests (Stage 12; measurable)

| ID | Test | Pass |
|---|---|---|
| T-PERF-1 | 30 min city drive, inspector closed, full modpack | LSAX tick time avg ≤ 1.0 ms, p99 ≤ 2.0 ms (LSAX internal stopwatch histogram) |
| T-PERF-2 | 100 transactions in a scripted test | transaction tick p95 ≤ 25 ms, max ≤ 50 ms |
| T-PERF-3 | traffic density mod at maximum, 5 min | scan never processes > 64 entities; no tick > 4 ms attributable to LSAX |
| T-PERF-4 | 4 h session | managed heap slope ≤ 1 MiB/h after hour 1; all caps respected (inspector counters) |
| T-PERF-5 | session start with 50 000-commit DB | market/transactions available ≤ 5 s wall after first tick |
| T-PERF-6 | synthetic 200 h journal (simulator) | DB size < 250 MiB after compaction |
| T-PERF-7 | FPS impact: same route, LSAX on/off | average FPS difference ≤ 2 % |
| T-PERF-8 | P-DB-01 on target disk | SQLite commit p95 recorded; if > 10 ms, revisit R-DB-2 before Stage 5 |
