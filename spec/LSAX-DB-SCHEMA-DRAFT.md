# LSAX — Persistence Contract & SQLite Schema Draft

Document: LSAX-DB-SCHEMA-DRAFT.md · Spec: LSAX MASTER SPEC v1.0 DRAFT2 · Status: DRAFT for independent re-audit

DRAFT2: two database files (D-DB-4, audit P2-01), save ledger/slot state (D-SL-13), `apply_status` (D-TX-4), system
transactions (D-JRN-1), lossless identity indexes (D-ID-7), MT state in the ledger (D-TIME-2), no LEGACY title (D-PROV-1).

## 1. Engine and connection contract

| Item | Decision | Label |
|---|---|---|
| Engine | SQLite 3 via `Microsoft.Data.Sqlite` (netstandard2.0 on net48) + `SQLitePCLRaw` bundle | DESIGN DECISION; loading inside SHVDN = OPEN RISK R-DB-1 (E6-4) |
| Native library | pre-loaded with `LoadLibraryW(<scripts>/LSAX/native/x64/e_sqlite3.dll)` before first use; loaded module path verified and logged | DESIGN DECISION D-DB-3 → P-DB-01 |
| Files (D-DB-4) | `<scripts>/LSAX/data/lsax.db` = schema `main`: journal + global tables + `applied_idem` (authoritative); `<scripts>/LSAX/data/lsax_proj.db` ATTACHed as schema `proj`: projection tables + `projection_meta` watermark (derived, rebuildable). Each with `-wal`, `-shm` | DESIGN DECISION (regression verified) |
| Pragmas | both: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=2000`, `cache_size=-8192` (8 MiB), `temp_store=MEMORY`, `wal_autocheckpoint=1000`; `main.synchronous=FULL` (every journal commit fsync'd); `proj.synchronous=NORMAL` (derived data: a lost projection commit is detected by the watermark and replayed) | DESIGN DECISION |
| Commit order (normative) | **journal transaction first** (txn/commit_log/journal_event/applied_idem/reservation rows, one SQLite transaction on `main`), **then** the projection transaction on `proj` (projection rows + watermark = journal position). SQLite does not make a WAL-mode transaction atomic across attached files, so none is assumed: the projection may lag the journal, never lead it. Any watermark ≠ active-path head → catch-up replay before the next transaction (§8 step 3) | DESIGN DECISION (regression B3) |
| Threading | one **DB worker thread** owns the only read-write connection; the script thread submits jobs; money-path jobs (PREPARE, COMMIT) are awaited synchronously with a 250 ms timeout (timeout before apply → abort; timeout/failure on COMMIT after the apply → same-tick compensation, else FAULT — TSM §4 step 6) | DESIGN DECISION |
| Shutdown | `Aborted`: flush LSAX's own memory (apply status of a PREPARED txn, MT state, p_last), close the connection; queued coalescible checkpoints may be lost — bounded to one checkpoint interval (TSM §3a) | DESIGN DECISION |
| Time columns | `*_mt` INTEGER (MT minutes), `*_p` INTEGER (play-time ms), `*_wall` INTEGER (UTC ms) | per LSAX-TIME-MODEL.md |
| Money columns | INTEGER whole dollars, `CHECK (x BETWEEN -2000000000 AND 2000000000)` (GTA wallet is int32) | DESIGN DECISION |

## 2. Layers

1. **Journal (authoritative, file `lsax.db`, schema `main`):** campaigns, timelines, transactions, commits with
   ordered domain events, save ledger, slot state, runtime markers, the active-path idempotency set `applied_idem`
   (maintained in the same SQLite transaction as each commit; recomputed on every fork). Append-only except
   transaction state transitions.
2. **Projection (derived, rebuildable, file `lsax_proj.db`, schema `proj`):** current state of the active timeline
   path (vehicles, ownership, listings, …). Rebuilt from the nearest valid snapshot + replay of events along the
   path. Carries a watermark `(timeline_id, seq, head_txn)`.
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
  parent_txn TEXT REFERENCES txn(txn_id), fork_p INTEGER NOT NULL, fork_mt INTEGER NOT NULL,
  reason TEXT NOT NULL CHECK (reason IN ('ROOT','ANCHOR','RESOLVED','NEW_CAMPAIGN')), created_wall INTEGER NOT NULL);
CREATE TABLE txn (txn_id TEXT PRIMARY KEY, idem_key TEXT NOT NULL, kind TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PREPARED','COMMITTED','ABORTED')),
  apply_status TEXT NOT NULL CHECK (apply_status IN ('NOT_STARTED','APPLYING','APPLIED')),  -- PREPARE writes APPLYING (D-TX-4)
  actor TEXT NOT NULL, wallet_slot INTEGER CHECK (wallet_slot IN (0,1,2)),
  wallet_before INTEGER, wallet_after INTEGER, p_prepare INTEGER NOT NULL, mt INTEGER NOT NULL,
  prev_txn TEXT, plan_json TEXT NOT NULL, created_wall INTEGER NOT NULL, resolved_wall INTEGER,
  resolution TEXT CHECK (resolution IN ('COMMITTED_IN_TICK','ABORTED_IN_TICK','COMPENSATED','OWN_EVIDENCE_ROLL_FORWARD',
    'OWN_EVIDENCE_ABORT','ANCHORED_TO_EARLIER_SAVE','PLAYER_CHOICE')));
CREATE TABLE commit_log (timeline_id INTEGER NOT NULL REFERENCES timeline, seq INTEGER NOT NULL,
  txn_id TEXT NOT NULL UNIQUE REFERENCES txn, idem_key TEXT NOT NULL, kind TEXT NOT NULL, p_ms INTEGER NOT NULL, mt INTEGER NOT NULL,
  wallet_before INTEGER, wallet_after INTEGER, PRIMARY KEY (timeline_id, seq));
CREATE TABLE journal_event (txn_id TEXT NOT NULL REFERENCES txn, ord INTEGER NOT NULL, type TEXT NOT NULL,
  schema_v INTEGER NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY (txn_id, ord));
  -- every event belongs to exactly one business or system txn (TSM §3a); system txns: kind LIKE 'SYS_%'
CREATE TABLE reservation (subject TEXT PRIMARY KEY, txn_id TEXT NOT NULL REFERENCES txn);  -- 'veh:<id>' | 'lst:<id>' | 'off:<id>'
-- save ledger (global, never rewinds; SAVELOAD §4.1/§4.2): positive knowledge of save CONTENT only
CREATE TABLE save_ledger (sha256 TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('OBSERVED','PRE_INSTALL')),
  campaign_id TEXT NOT NULL REFERENCES campaign, head_txn TEXT,              -- NULL = EMPTY state
  p_lo INTEGER, p_hi INTEGER,                                                -- poll bracket; NULL for PRE_INSTALL
  w0 INTEGER, w1 INTEGER, w2 INTEGER,                                        -- NULL = wallets unknown (changed in bracket)
  mt_obs INTEGER, mt_base INTEGER, mt_credits_json TEXT, gc_obs INTEGER,   -- MT state at the observing poll (TIME §2.2)
  observed_wall INTEGER NOT NULL,
  CHECK ((kind = 'PRE_INSTALL' AND p_lo IS NULL AND head_txn IS NULL) OR (kind = 'OBSERVED' AND p_lo <= p_hi)));
CREATE TABLE slot_state (slot_file TEXT PRIMARY KEY, mtime_wall INTEGER NOT NULL, size INTEGER NOT NULL,
  sha256 TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('TRUSTED','PRE_INSTALL','UNTRUSTED')),
  reason TEXT NOT NULL CHECK (reason IN ('OBSERVED','KNOWN_CONTENT','RESTORED_COPY','PRE_INSTALL','CHANGED_WHILE_DOWN',
    'FOREIGN_WHILE_RUNNING','AMBIGUOUS_EVENT','DURING_RECONCILE')), updated_wall INTEGER NOT NULL);
CREATE TABLE applied_idem (idem_key TEXT PRIMARY KEY, txn_id TEXT NOT NULL);   -- main: active-path idem set (TSM §3a)
CREATE TABLE runtime_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
  -- active_timeline, reconcile (0|1), reconcile_reason, reconcile_candidates, session_token, proc_id, proc_start,
  -- p_last, stop_clean, missed_start (process identity of a failed start), fault (D-TX-5)
CREATE TABLE deal (deal_id TEXT PRIMARY KEY, state TEXT NOT NULL, listing_id TEXT, offer_id TEXT, txn_id TEXT,
  hold_expires_mt INTEGER, retry_left INTEGER NOT NULL, params_json TEXT NOT NULL);  -- timeline-coupled via events

-- ===== projection (schema proj, file lsax_proj.db; derived; rebuilt per active path) =====
CREATE TABLE projection_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);           -- head_txn, timeline_id, rebuilt_wall
CREATE TABLE vehicle (vehicle_id TEXT PRIMARY KEY, lsax_vin TEXT NOT NULL UNIQUE, model_hash INTEGER NOT NULL,
  model_name TEXT, birth_mt INTEGER NOT NULL,
  lifecycle TEXT NOT NULL CHECK (lifecycle IN ('VIRTUAL','ACTIVE','DORMANT','MISSING','DESTROYED','RETIRED','MODEL_UNAVAILABLE')),
  flags INTEGER NOT NULL DEFAULT 0,                                                  -- CLONE_SUSPECT, GAME_RESPAWN_OF_SOLD, ...
  last_seen_mt INTEGER, last_seen_x REAL, last_seen_y REAL, last_seen_z REAL, last_seen_ctx TEXT);
CREATE TABLE vehicle_title (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle,
  status TEXT NOT NULL CHECK (status IN ('CLEAN','SALVAGE','STOLEN','RECOVERED','UNDERGROUND','UNKNOWN')),  -- no LEGACY (D-PROV-1)
  since_txn TEXT, since_mt INTEGER NOT NULL);
CREATE TABLE vehicle_ownership (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle, owner_kind TEXT NOT NULL,
  owner_id TEXT, since_txn TEXT, since_mt INTEGER NOT NULL, owner_count INTEGER NOT NULL CHECK (owner_count BETWEEN 0 AND 99));
CREATE TABLE vehicle_registration (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle, plate TEXT NOT NULL,
  plate_style INTEGER NOT NULL, lsax_issued INTEGER NOT NULL CHECK (lsax_issued IN (0,1)));
CREATE INDEX ix_registration_plate ON vehicle_registration(plate);
CREATE TABLE vehicle_fingerprint (vehicle_id TEXT PRIMARY KEY REFERENCES vehicle, model_hash INTEGER NOT NULL,
  plate_norm TEXT NOT NULL, colour_sig INTEGER NOT NULL,                     -- 4 colour components packed
  fp_json TEXT NOT NULL, fp_hash TEXT NOT NULL);
CREATE INDEX ix_fp_k1 ON vehicle_fingerprint(model_hash, plate_norm);       -- complete K1 (DOMAIN §4.4, D-ID-7)
CREATE INDEX ix_fp_k2 ON vehicle_fingerprint(model_hash, colour_sig);       -- complete K2 (context filter in memory)
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

`journal_event.payload_json` is canonical JSON (UTF-8, sorted keys, integers only, no floats). Every event belongs to
exactly one transaction — business (TSM §3) or system (TSM §3a). Types (schema_v=1) and the transaction kinds that
emit them:

| Event type | Emitted by | Payload (absolute values; deltas only as audit fields) |
|---|---|---|
| `VehicleRegistered`, `TitleChanged`, `OwnershipChanged`, `HistoryAppended`, `ModsChanged`, `WalletDelta`, `FeeCharged`, `ListingOpened`, `ListingStateChanged`, `OfferCreated`, `OfferStateChanged`, `DealStateChanged`, `MailQueued` | business transactions | resulting row values |
| `MtCheckpoint(state)` | `SYS_MT_CHECKPOINT` | MT state `(mt, base_mt, recent_credits)` |
| `OdometerCheckpoint`, `ConditionChanged` | `SYS_ODO_CHECKPOINT` | `odo_m`, condition vector |
| `MarketStep(step, indices, generated)` | `SYS_MARKET_STEP` | segment indices after the step; generated vehicle rows (NPC-GEN §2) |
| `HeatDelta(values)` | `SYS_HEAT_DECAY`, `SYS_HEAT_EVENT`, underground business transactions | Heat values after the change |
| `ListingStateChanged(EXPIRED)` | `SYS_LISTING_EXPIRY` | new state + version |

Replaying events of a path in `(timeline, seq, ord)` order reproduces the projection bit-for-bit (T-DB-3); replaying
twice gives the same result.

## 5. Snapshots, backups and rebuild (normative, D-DB-4; audit P2-01)

| Artefact | Mechanism (exact) | When | Retention |
|---|---|---|---|
| **Projection snapshot** | SQLite online backup of schema `proj` only: `live.BackupDatabase(snapshotConn, "main", "proj")` (Microsoft.Data.Sqlite overload `BackupDatabase(SqliteConnection destination, string destinationName, string sourceName)`, present in the netstandard2.0 build 8.0.11; P-DB-01 executes it) into `data/snapshots/<timeline>-<seq>.db`. Because the projection is its own database file, the backup contains exactly the projection tables and its watermark — nothing else | every 200 commits on a path, and at session end (DB worker thread) | 8 newest + every snapshot that is the nearest ancestor of a save-ledger head |
| **Journal backup** (disaster recovery) | SQLite online backup of schema `main`: `live.BackupDatabase(backupConn, "main", "main")` into `data/backup/lsax-<wall>.db` | at session end, before every migration (§7) | 3 newest |
| **Rebuild after anchoring** | if the projection watermark is not on the target path: choose the newest snapshot whose watermark is an ancestor of the target head (a snapshot off the target path is never used), restore it into `proj` (`snapshotConn.BackupDatabase(live, "proj", "main")`), then replay journal events from the watermark to the target head; no usable snapshot → rebuild from an empty projection | during the session-start grace period; market frozen until done | — |
| **Catch-up** | watermark on the path but behind the head (crash between the two commits, lost `synchronous=NORMAL` commit) → replay the missing positions | startup; before any transaction | — |
| **Projection loss** | `lsax_proj.db` missing or failing `quick_check` → delete, recreate, rebuild from the journal | startup | — |

Consistency of an online backup: SQLite restarts a backup step when the source is modified by another connection
and updates the backup when it is modified through the same connection, so every snapshot equals the projection at
its own watermark. Regression `phase0-probes/regress/regress_p2_01_backup.py` (11 checks, real SQLite backup API):
snapshot contains only projection tables + watermark; journal backup contains only journal tables; crash between
the commits → watermark lags (never leads) and catch-up equals a full rebuild; deleted projection rebuilt
identically; snapshot restore + replay on an ancestor path equals rebuild; off-path snapshot rejected; snapshot
taken during concurrent writes is self-consistent; pragmas as specified. Bound: ≤ 200 commits replay ≈ < 1 s.

## 6. Growth and retention

| Item | Estimate | Bound / policy |
|---|---:|---|
| Commit + events | ~1.5 KiB per transaction | 50 000 commits ≈ 75 MiB |
| Odometer/MT checkpoints | 1 row/min driving → ~60 rows/h | coalesced: keep 1 per 10 km per vehicle older than 30 MT days |
| NPC virtual vehicles | ≤ 600 live listings + ≤ 3 000 retired within 30 MT days | retired VIRTUAL vehicles older than 30 MT days compacted to summary rows |
| Orphaned branches | variable | compacted after 30 MT days if not referenced by the save ledger (LSAX-SAVELOAD-FEASIBILITY.md §4.10) |
| Projection snapshots | ≤ 8 (+ ledger-referenced) × projection size | pruned |
| Journal backups | 3 × journal size | oldest deleted |
| Audit log | ~200 B/entry | ring: newest 100 000 |

Target: DB < 250 MiB after 200 h of play (T-PERF-6). `VACUUM` never during play; offered as a debug command.

## 7. Migrations

- `schema_version` integer; migrations are forward-only, numbered, idempotent SQL scripts embedded as resources
  with SHA-256; applied in one transaction each, recorded in `schema_migration`.
- Before any migration: journal backup (§5) to `data/backup/lsax-v<from>-<wall>.db` (retain 3); the projection
  is simply rebuilt after the migration.
- Opening a DB with a **newer** `schema_version` than the build knows → refuse to open, disable LSAX with a
  localised message (safe refusal). Downgrades are not supported.
- Every migration ships with a fixture DB of the previous version and a test that migrates it and compares a
  golden projection dump (T-DB-2).

## 8. Integrity and crash recovery at startup

1. Open → `PRAGMA quick_check` (bounded to 2 s; if longer, continue and schedule a full check at next start).
2. Failure → open read-only, LSAX transactions disabled, localised prompt to restore the newest backup.
3. Projection watermark ≠ journal head of the active path → catch-up or rebuild (§5); no transaction is accepted
   until the watermark equals the head.
4. Anchoring (LSAX-SAVELOAD-FEASIBILITY.md §4.3) and PREPARED-txn resolution (TSM §7).
5. Clamp-on-read for legacy/corrupt values is **not** silent: out-of-range values fail CHECK constraints; the
   repair tool logs `DATA_REPAIR` audit entries (clamping odometer to 0…10 M km, condition to 0…1000).
