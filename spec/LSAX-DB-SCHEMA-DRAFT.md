# LSAX — Persistence Contract & SQLite Schema Draft

Document: LSAX-DB-SCHEMA-DRAFT.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

## 1. Engine and connection contract

| Item | Decision | Label |
|---|---|---|
| Engine | SQLite 3 via `Microsoft.Data.Sqlite` (netstandard2.0 on net48) + `SQLitePCLRaw` bundle | DESIGN DECISION; loading inside SHVDN = OPEN RISK R-DB-1 (E6-4) |
| Native library | pre-loaded with `LoadLibraryW(<scripts>/LSAX/native/x64/e_sqlite3.dll)` before first use; loaded module path verified and logged | DESIGN DECISION D-DB-3 → P-DB-01 |
| File | `<scripts>/LSAX/data/lsax.db` (+ `-wal`, `-shm`) | DESIGN DECISION |
| Pragmas | `journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, `busy_timeout=2000`, `cache_size=-8192` (8 MiB), `temp_store=MEMORY`, `wal_autocheckpoint=1000` | DESIGN DECISION |
| Threading | one **DB worker thread** owns the only read-write connection; the script thread submits jobs; money-path jobs (PREPARE, COMMIT) are awaited synchronously with a 250 ms timeout (timeout before apply → abort; timeout on COMMIT → state stays PREPARED → recovered by §7 of the TSM) | DESIGN DECISION |
| Shutdown | `Aborted`: flush stop marker (memory values only), close connection; queued non-critical writes (odometer checkpoints) may be lost — bounded to one checkpoint interval | DESIGN DECISION |
| Time columns | `*_mt` INTEGER (MT minutes), `*_p` INTEGER (play-time ms), `*_wall` INTEGER (UTC ms) | per LSAX-TIME-MODEL.md |
| Money columns | INTEGER whole dollars, `CHECK (x BETWEEN -2000000000 AND 2000000000)` (GTA wallet is int32) | DESIGN DECISION |

## 2. Layers

1. **Journal (authoritative):** campaigns, timelines, transactions, commits with ordered domain events, save-slot
   ledger, runtime markers. Append-only except transaction state transitions.
2. **Projection (derived, rebuildable):** current state of the active timeline path (vehicles, ownership,
   listings, …). Rebuilt from the nearest snapshot + replay of events along the path. Carries a watermark.
3. **Global (never timeline-coupled):** schema meta, catalogue overrides, audit log, counters.

## 3. DDL draft

```sql
-- ===== meta =====
CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);           -- schema_version, app_version, created_wall
CREATE TABLE schema_migration (version INTEGER PRIMARY KEY, applied_wall INTEGER NOT NULL,
  description TEXT NOT NULL, sha256 TEXT NOT NULL);

-- ===== journal (authoritative) =====
CREATE TABLE campaign (campaign_id TEXT PRIMARY KEY, seed INTEGER NOT NULL, created_wall INTEGER NOT NULL,
  created_reason TEXT NOT NULL CHECK (created_reason IN ('FIRST_RUN','NEW_CAMPAIGN_CHOICE')));
CREATE TABLE timeline (timeline_id INTEGER PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaign,
  parent_txn TEXT REFERENCES txn(txn_id), fork_p INTEGER NOT NULL, fork_mt INTEGER NOT NULL, last_p INTEGER NOT NULL,
  reason TEXT NOT NULL CHECK (reason IN ('ROOT','ANCHOR','DOWNTIME','RECOVERY')), created_wall INTEGER NOT NULL);
CREATE TABLE txn (txn_id TEXT PRIMARY KEY, idem_key TEXT NOT NULL, kind TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PREPARED','COMMITTED','ABORTED','RECONCILE')),
  actor TEXT NOT NULL, wallet_slot INTEGER CHECK (wallet_slot IN (0,1,2)),
  wallet_before INTEGER, wallet_after INTEGER, p_prepare INTEGER NOT NULL, mt INTEGER NOT NULL,
  prev_txn TEXT, plan_json TEXT NOT NULL, created_wall INTEGER NOT NULL, resolved_wall INTEGER, resolution TEXT);
CREATE TABLE commit_log (timeline_id INTEGER NOT NULL REFERENCES timeline, seq INTEGER NOT NULL,
  txn_id TEXT NOT NULL UNIQUE REFERENCES txn, idem_key TEXT NOT NULL, p_ms INTEGER NOT NULL, mt INTEGER NOT NULL,
  wallet_before INTEGER, wallet_after INTEGER, PRIMARY KEY (timeline_id, seq));
CREATE TABLE journal_event (txn_id TEXT NOT NULL REFERENCES txn, ord INTEGER NOT NULL, type TEXT NOT NULL,
  schema_v INTEGER NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY (txn_id, ord));
CREATE TABLE reservation (subject TEXT PRIMARY KEY, txn_id TEXT NOT NULL REFERENCES txn);  -- 'veh:<id>' | 'lst:<id>' | 'off:<id>'
CREATE TABLE slot_ledger (slot_file TEXT PRIMARY KEY, mtime_wall INTEGER NOT NULL, size INTEGER NOT NULL,
  sha256 TEXT NOT NULL, mode TEXT NOT NULL CHECK (mode IN ('OBSERVED','INFERRED','FOREIGN')),
  timeline_id INTEGER NOT NULL REFERENCES timeline, p_lo INTEGER NOT NULL, p_hi INTEGER NOT NULL,
  w0 INTEGER, w1 INTEGER, w2 INTEGER, pending_txn TEXT, observed_wall INTEGER NOT NULL);
CREATE TABLE runtime_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
  -- active_timeline, reconcile(0|1, reason), stop_clean, stop_p, stop_w0..2, stop_wall, stop_proc, heartbeat_p, heartbeat_wall
CREATE TABLE deal (deal_id TEXT PRIMARY KEY, state TEXT NOT NULL, listing_id TEXT, offer_id TEXT, txn_id TEXT,
  hold_expires_mt INTEGER, retry_left INTEGER NOT NULL, params_json TEXT NOT NULL);  -- timeline-coupled via events

-- ===== projection (derived; rebuilt per active path) =====
CREATE TABLE projection_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);           -- head_txn, timeline_id, rebuilt_wall
CREATE TABLE vehicle (vehicle_id TEXT PRIMARY KEY, lsax_vin TEXT NOT NULL UNIQUE, model_hash INTEGER NOT NULL,
  model_name TEXT, birth_mt INTEGER NOT NULL,
  lifecycle TEXT NOT NULL CHECK (lifecycle IN ('VIRTUAL','ACTIVE','DORMANT','MISSING','DESTROYED','RETIRED','MODEL_UNAVAILABLE')),
  flags INTEGER NOT NULL DEFAULT 0,                                                  -- CLONE_SUSPECT, GAME_RESPAWN_OF_SOLD, ...
  last_seen_mt INTEGER, last_seen_x REAL, last_seen_y REAL, last_seen_z REAL, last_seen_ctx TEXT);
CREATE TABLE vehicle_title (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle,
  status TEXT NOT NULL CHECK (status IN ('CLEAN','SALVAGE','STOLEN','RECOVERED','UNDERGROUND','UNKNOWN','LEGACY')),
  since_txn TEXT, since_mt INTEGER NOT NULL);
CREATE TABLE vehicle_ownership (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle, owner_kind TEXT NOT NULL,
  owner_id TEXT, since_txn TEXT, since_mt INTEGER NOT NULL, owner_count INTEGER NOT NULL CHECK (owner_count BETWEEN 0 AND 99));
CREATE TABLE vehicle_registration (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle, plate TEXT NOT NULL,
  plate_style INTEGER NOT NULL, lsax_issued INTEGER NOT NULL CHECK (lsax_issued IN (0,1)));
CREATE INDEX ix_registration_plate ON vehicle_registration(plate);
CREATE TABLE vehicle_fingerprint (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle, fp_json TEXT NOT NULL, fp_hash TEXT NOT NULL);
CREATE INDEX ix_fingerprint_hash ON vehicle_fingerprint(fp_hash);
CREATE TABLE vehicle_condition (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle,
  odo_m INTEGER NOT NULL CHECK (odo_m BETWEEN 0 AND 10000000000),                    -- ≤ 10 million km
  mech INTEGER NOT NULL CHECK (mech BETWEEN 0 AND 1000), body INTEGER NOT NULL CHECK (body BETWEEN 0 AND 1000),
  components_json TEXT NOT NULL, service_score INTEGER CHECK (service_score BETWEEN 0 AND 1000), updated_mt INTEGER NOT NULL);
CREATE TABLE vehicle_mods (vehicle_id TEXT NOT NULL REFERENCES vehicle, kind TEXT NOT NULL CHECK (kind IN ('BASELINE','CURRENT')),
  mods_json TEXT NOT NULL, mods_hash TEXT NOT NULL, mt INTEGER NOT NULL, PRIMARY KEY (vehicle_id, kind));
CREATE TABLE vehicle_history (event_id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL REFERENCES vehicle, kind TEXT NOT NULL,
  params_json TEXT NOT NULL, mt INTEGER NOT NULL, odo_m INTEGER, txn_id TEXT,
  source TEXT NOT NULL CHECK (source IN ('LSAX_TXN','OBSERVED','GENERATED','RECONCILED')));
CREATE INDEX ix_history_vehicle ON vehicle_history(vehicle_id, mt);
CREATE TABLE party (party_id TEXT PRIMARY KEY, kind TEXT NOT NULL, profile TEXT NOT NULL, budget INTEGER NOT NULL,
  params_json TEXT NOT NULL);
CREATE TABLE listing (listing_id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL REFERENCES vehicle,
  market TEXT NOT NULL CHECK (market IN ('LEGAL','UNDERGROUND')), seller_id TEXT NOT NULL, ask INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('DRAFT','ACTIVE','RESERVED','SOLD','EXPIRED','WITHDRAWN','INVALIDATED')),
  version INTEGER NOT NULL, created_mt INTEGER NOT NULL, expires_mt INTEGER NOT NULL, state_hash TEXT NOT NULL);
CREATE UNIQUE INDEX ux_listing_active ON listing(vehicle_id) WHERE state IN ('ACTIVE','RESERVED');
CREATE TABLE offer (offer_id TEXT PRIMARY KEY, listing_id TEXT NOT NULL REFERENCES listing, party_id TEXT NOT NULL,
  amount INTEGER NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, expires_mt INTEGER NOT NULL,
  counter_of TEXT, state_hash TEXT NOT NULL);
CREATE TABLE market_segment (segment TEXT PRIMARY KEY, demand_bp INTEGER NOT NULL, supply_bp INTEGER NOT NULL,
  liquidity_bp INTEGER NOT NULL, last_step_mt INTEGER NOT NULL);
CREATE TABLE heat_state (scope TEXT NOT NULL, subject TEXT NOT NULL, value INTEGER NOT NULL CHECK (value BETWEEN 0 AND 1000),
  laylow INTEGER NOT NULL DEFAULT 0, updated_mt INTEGER NOT NULL, PRIMARY KEY (scope, subject));
CREATE TABLE heat_event (event_id TEXT PRIMARY KEY, scope TEXT NOT NULL, subject TEXT NOT NULL, kind TEXT NOT NULL,
  delta INTEGER NOT NULL, mt INTEGER NOT NULL, txn_id TEXT);
CREATE TABLE fee_ledger (entry_id TEXT PRIMARY KEY, txn_id TEXT NOT NULL, kind TEXT NOT NULL, amount INTEGER NOT NULL, mt INTEGER NOT NULL);
CREATE TABLE mail (mail_id TEXT PRIMARY KEY, recipient TEXT NOT NULL, template_key TEXT NOT NULL, params_json TEXT NOT NULL,
  mt INTEGER NOT NULL, gc_display TEXT, read INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);

-- ===== global =====
CREATE TABLE catalogue_override (model_hash INTEGER PRIMARY KEY, model_name TEXT NOT NULL, class TEXT NOT NULL,
  msrp INTEGER NOT NULL CHECK (msrp > 0), rarity TEXT NOT NULL, annual_km INTEGER NOT NULL, flags INTEGER NOT NULL, source TEXT NOT NULL);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY, wall INTEGER NOT NULL, kind TEXT NOT NULL, detail_json TEXT NOT NULL);
```

Mail content is stored as **template key + parameters**, never as rendered text, so a locale switch re-renders it
(LSAX-LOCALIZATION-CONTRACT.md §6).

## 4. Journal events

`journal_event.payload_json` is canonical JSON (UTF-8, sorted keys, integers only, no floats). Types (schema_v=1):
`VehicleRegistered, TitleChanged, OwnershipChanged, OdometerCheckpoint, ConditionChanged, ModsChanged,
HistoryAppended, ListingOpened, ListingStateChanged, OfferCreated, OfferStateChanged, DealStateChanged,
WalletDelta, FeeCharged, HeatDelta, MarketStep(segment, seed, indices), MtCheckpoint(p, mt), MailQueued`.
Replaying events of a path in order reproduces the projection bit-for-bit (T-DB-3).

## 5. Snapshots and rebuild

- Every 200 commits on a path, and at session end, the DB worker writes a projection snapshot using the SQLite
  online backup API into `data/snapshots/<head_txn>.db` (projection tables only). Retain the 8 newest + any
  snapshot that is the nearest ancestor of a ledger-referenced state.
- Rebuild (after anchoring to a state ≠ current projection head): choose the nearest snapshot whose head is on the
  target path; restore; replay events forward. Bound: ≤ 200 commits replay ≈ < 1 s (budget in
  LSAX-PERFORMANCE-BUDGET.md; runs during the session-start grace period, market frozen until done).

## 6. Growth and retention

| Item | Estimate | Bound / policy |
|---|---:|---|
| Commit + events | ~1.5 KiB per transaction | 50 000 commits ≈ 75 MiB |
| Odometer/MT checkpoints | 1 row/min driving → ~60 rows/h | coalesced: keep 1 per 10 km per vehicle older than 30 MT days |
| NPC virtual vehicles | ≤ 600 live listings + ≤ 3 000 retired within 30 MT days | retired VIRTUAL vehicles older than 30 MT days compacted to summary rows |
| Orphaned branches | variable | compacted after 30 MT days if not referenced by the slot ledger (LSAX-SAVELOAD-FEASIBILITY.md §4.8) |
| Snapshots | ≤ 8 × projection size | pruned |
| Audit log | ~200 B/entry | ring: newest 100 000 |

Target: DB < 250 MiB after 200 h of play (T-PERF-6). `VACUUM` never during play; offered as a debug command.

## 7. Migrations

- `schema_version` integer; migrations are forward-only, numbered, idempotent SQL scripts embedded as resources
  with SHA-256; applied in one transaction each, recorded in `schema_migration`.
- Before any migration: online backup to `data/backup/lsax-v<from>-<wall>.db` (retain 3).
- Opening a DB with a **newer** `schema_version` than the build knows → refuse to open, disable LSAX with a
  localised message (safe refusal). Downgrades are not supported.
- Every migration ships with a fixture DB of the previous version and a test that migrates it and compares a
  golden projection dump (T-DB-2).

## 8. Integrity and crash recovery at startup

1. Open → `PRAGMA quick_check` (bounded to 2 s; if longer, continue and schedule a full check at next start).
2. Failure → open read-only, LSAX transactions disabled, localised prompt to restore the newest backup.
3. Projection watermark ≠ journal head of the active path → rebuild (§5).
4. Anchoring (LSAX-SAVELOAD-FEASIBILITY.md §4.3) and PREPARED-txn resolution (TSM §7).
5. Clamp-on-read for legacy/corrupt values is **not** silent: out-of-range values fail CHECK constraints; the
   repair tool logs `DATA_REPAIR` audit entries (clamping odometer to 0…10 M km, condition to 0…1000).
