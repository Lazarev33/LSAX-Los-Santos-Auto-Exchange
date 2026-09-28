# LSAX — Phase 0 Correction Pass 1 — Report

Project: LSAX — Los Santos Auto Exchange (GTA V Legacy 1.0.3725.0 · ScriptHookVDotNet 3.7.x · C# / .NET Framework 4.8).
Mode: specification / reference-model / feasibility correction only. **No production LSAX code was written; no stage
was started.** The author does not and cannot grant SPEC_APPROVED.

## 1. Audited baseline

| Item | Value |
|---|---|
| Repository | `Lazarev33/LSAX-Los-Santos-Auto-Exchange` |
| Audited branch / head | `claude/focused-thompson-ilnspm` @ **`f6aff47d1dbea94576d6aae1f60bd17102d549cc`** (unchanged; PR #1 unchanged; `main` unchanged) |
| Correction branch | `claude/phase0-correction-1`, created from exactly `f6aff47` (C0-01) |
| Audit input | `LSAX-PHASE0-INDEPENDENT-AUDIT.zip`, SHA-256 `35d3c55d503ad398e574d267fdd59ea0d15882dcd2573548c7a3399b08995bb2`; its SHA256SUMS.txt verified 4/4 |
| Audit verdict | CORRECTION_REQUIRED — SPEC_APPROVED BLOCKED (4 × P0, 6 × P1, 1 × P2) |

## 2. DRAFT1 release

`release/LSAX-MASTER-SPEC-v1.0-DRAFT1.zip` SHA-256 **`281f52f6e989ed7de93d4af7d61e25e9a2369fa7d74856f5d666357896cccd16`**
(repository file == uploaded copy == `git show f6aff47:release/…`, verified identical; not modified, not rebuilt).

## 3. Findings — verification, correction, regression, result

Every finding was first located in the DRAFT1 text and reference model, then reproduced or source-verified
independently (C0-03), then corrected with a stated architecture choice, then proven by deterministic regressions.
The auditor's suggestions were treated as evidence, not as design authority. Where the chosen fix differs from the
suggestion, the reason is given. Regression files are under `phase0-probes/regress/`; run all with
`python3 phase0-probes/regress/run_regressions.py` (10 suites, 2 645 checks, ≈ 15 s) or everything with
`python3 phase0-probes/sim/run_all.py [--audit]`.

### P0-01 — B-01 runtime feasibility still open

| Aspect | Content |
|---|---|
| Verification | SOURCE VERIFIED: SAVELOAD §0/§6 and MASTER App. L of DRAFT1 rest on A-SL-1/5/6/7; no GTA runtime exists in this environment. |
| Correction | B-01 kept as a real BLOCKER with status **BLOCKED_RUNTIME_VALIDATION**. The runtime assumption set was re-derived from the corrected model (A-SL-1, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14; SAVELOAD §9) and the pass criteria were redefined as **PC-1…PC-8** (SAVELOAD §6), each tied to exact log rows. P-SL-01 was rewritten to collect exactly that evidence (per-tick samples, pre-signal save brackets, a probe ledger with `LOAD_MATCH` load attribution, the session-token decorator with ped-change re-tag, tick-interleave markers, wallet transitions, process identity). P-DB-01 now exercises the DRAFT2 persistence stack (D-DB-4). `README-PROBES.md` is an executable validation package: target runtime and backup, build, exact install paths, launch, scenarios T1–T17 with expected log rows, PASS/FAIL rules, evidence collection and cleanup. The fallback table (SAVELOAD §7) now degrades only toward refusal. No assumption is marked VERIFIED without runtime evidence. |
| Files | `spec/LSAX-SAVELOAD-FEASIBILITY.md` (§0, §2, §6, §7, §9), `phase0-probes/README-PROBES.md`, `phase0-probes/shvdn/LsaxPhase0Probe/SessionSignalProbe.cs`, `phase0-probes/shvdn/LsaxPhase0Probe/ProbeCore.cs`, `phase0-probes/shvdn/LsaxPhase0Probe/IdentityProbe.cs`, `phase0-probes/shvdn/LsaxPhase0SqliteProbe/SqliteReloadProbe.cs`, `phase0-probes/probe.ini.sample`, `spec/LSAX-RISK-REGISTER.md`, `risks.md`, `feasibility.md` (E9-13/14) |
| Regression / probe | Probes compile clean (0 warnings, 0 errors, TreatWarningsAsErrors) against SHVDN3 3.6.0 / Microsoft.Data.Sqlite 8.0.11 (`evidence/compile/`); the D-DB-4 backup calls execute correctly on .NET 8 (`dotnet-checks/backupcheck`). **Never executed in GTA V.** |
| Result | **OPEN — BLOCKED_RUNTIME_VALIDATION** (correct outcome of this pass; closes only with the owner's P-SL-01 / P-DB-01 logs). |

### P0-02 — wallet equality is not causal proof

| Aspect | Content |
|---|---|
| Verification | REPRODUCED: the auditor's `repro_findings.py` against the baseline model gave output byte-identical to the auditor's REPRO-OUTPUT (case A: roll-forward of t1 after C1 + external cash = wallet_after). Root cause: `anchor()` treated `cash == after ≠ before` as APPLIED; TSM §7 row 1 normative. |
| Correction | Chosen principle: recovery uses **only LSAX's own evidence** (D-TX-4). PREPARE durably writes `apply_status = APPLYING` (pessimistic); LSAX's in-memory status (NOT_STARTED → APPLYING → APPLIED) is flushed in `Aborted`. Roll-forward only when the **session token** proves the same live session **and** the own flushed status is APPLIED; NOT_STARTED → abort; APPLYING / no flush → RECONCILE_REQUIRED(PENDING_UNKNOWN) with an explicit player choice. Token-less starts abort a pending transaction only when the world is anchored to a content-identified save, which by construction predates any unrecorded apply (D-TX-5: COMMIT failure → same-tick compensation, else FAULT and stop observing saves). No watermark/carrier was introduced (its persistence is unproven). Wallet values are never an input. |
| Files | `phase0-probes/sim/journal_timeline_ref.py`, `spec/LSAX-TRANSACTION-STATE-MACHINE.md` (§1, §4, §7, §10), `spec/LSAX-SAVELOAD-FEASIBILITY.md` §4.4, `spec/LSAX-DB-SCHEMA-DRAFT.md` (`apply_status`, `resolution`), `decisions.md` (D-TX-4, D-TX-5; D-TX-2 withdrawn) |
| Regression | `regress_audit_repro.py` (auditor script byte-identical, SHA-256 `ad8fe27a…6755e`): case A → RECONCILE(PENDING_UNKNOWN), t1 not committed — 7/7. `regress_p0_02_txn_recovery.py`: 432 scenarios = BUY/SELL × 3 wallets × crash C1/CA/CB/C2 × 5 stop modes (clean reload, unclean same session, downtime with trainer writes, character switched while down, game crash + load) × external cash {none, = wallet_before, = wallet_after} (+ after-load variants), each with 3 further restarts and replay — **2 304/2 304 PASS**; decision identical for every wallet value; roll-forward exactly in the 36 own-evidence cases. |
| Result | **PASS** |

### P0-03 — foreign/copied save during downtime

| Aspect | Content |
|---|---|
| Verification | REPRODUCED: case B byte-identical to the auditor's output. Root cause: files changed while LSAX was down became INFERRED ghost entries matched by play-time window only. **Self-found SF-1:** continuation itself was accepted on play-time/wallet correlation. |
| Correction | Evidence rule: *no positive evidence → no automatic acceptance*; correlations may **exclude**, never include. Save lineage = **content identity** (SHA-256 of a save LSAX observed being written, corroborated by exactly one save-event signal; or a byte-identical restore) — D-SL-13. Every other file (changed while down, pre-existing, copied while running, ambiguous event) is **UNTRUSTED** and never lineage. Continuation needs the **session token** (D-SL-14). Token-less anchoring = **hypothesis exclusion** (D-SL-15/16): FILE per slot, LIVE (same process and play-time ≥ LSAX's own last observation), NEW_GAME; accept only if every non-excluded hypothesis has a known state, they agree, and one is a content-identified file; otherwise RECONCILE_REQUIRED (UNTRUSTED_PRESENT, AMBIGUOUS, NO_MATCH, SESSION_UNPROVEN, MISSED_START, PENDING_UNKNOWN). The auditor-style STANDARD/STRICT split was **rejected** (STANDARD would accept by correlation). Exclusion uses poll brackets starting at the last poll before the save signal (D-SL-17) and a **save-in-progress gate** (D-SL-18) — both from self-found SF-4/SF-5 (asynchronous save writes). Residual outside threat model TM-1 (deliberate swap of a forged file back to trusted bytes before LSAX's scan) documented as R-SL-7 and demonstrated exactly. |
| Files | `phase0-probes/sim/journal_timeline_ref.py`, `spec/LSAX-SAVELOAD-FEASIBILITY.md` (rewritten), `spec/LSAX-DB-SCHEMA-DRAFT.md` (`save_ledger`, `slot_state`, runtime keys), `spec/LSAX-TRANSACTION-STATE-MACHINE.md` §4 gate, `spec/LSAX-MASTER-SPEC-v1.0.md` (§01, §05, App. L), `spec/LSAX-LOCALIZATION-CONTRACT.md` (RECONCILE keys), `decisions.md` (D-SL-13…18; D-SL-3/4/8/9/10/11 withdrawn), `risks.md`, `spec/LSAX-RISK-REGISTER.md` (R-SL-3, R-SL-4, R-SL-7) |
| Regression | `regress_audit_repro.py` case B → RECONCILE(UNTRUSTED_PRESENT), no slot anchoring. `regress_p0_03_save_lineage.py`: 26 cases — foreign copy during downtime (loaded / present), copied older local save (byte-identical restore → anchors at its head), copied newer foreign save, save written while LSAX was down, same play-time collision, same wallet collision, full forged fingerprint, multiple slots (all anchor correctly), two saves in one event window, cross-branch identical fingerprints (AMBIGUOUS), repeated restart, legitimate continuation (incl. switch while running), rollback to an observed save, forward load (new process anchors; same process refuses), token lost without load, missed start, pre-install saves, new game, wallets unknown, copy while running, pending APPLIED + game crash, explicit resolution, asynchronous save (gate on correct / gate off defect reproduced), async bracket, random async histories (gate on 0 / off > 0 violations), residual R-SL-7 demo — **84/84 PASS**. Random model `journal_timeline_ref.py --episodes 200`: see §5 (0 safety failures). |
| Result | **PASS** (runtime assumptions → B-01) |

### P0-04 — Stage 1a carve-out

| Aspect | Content |
|---|---|
| Verification | SOURCE VERIFIED: MASTER §28/§30/App. L, STAGE-ACCEPTANCE S1a/S1b, RISK-REGISTER "Due" column, OD-3/OD-5, A-SL-4, risks.md B-01. |
| Correction | D-GATE-1: no stage and no part of any stage starts before SPEC_APPROVED; every open P0/P1 blocks SPEC_APPROVED; only disposable probes and Phase-0 corrections are allowed. The risk register's DRAFT1 rule "P1 must close before the stage that depends on it" was itself a deferral and was replaced by a closure column (OFFLINE / RUNTIME). Single Stage 1 table, entry = SPEC_APPROVED. |
| Files | `spec/LSAX-STAGE-ACCEPTANCE.md`, `spec/LSAX-MASTER-SPEC-v1.0.md`, `spec/LSAX-RISK-REGISTER.md`, `risks.md`, `feasibility.md`, `decisions.md` |
| Regression | `regress_p0_04_gate.py` static scan (tokens S1a/S1b, un-negated "Stage 1a/1b", carve-out phrases; gate statements present) — **24/24 PASS**; the same scan finds 22 carve-out lines in the DRAFT1 texts. `xref_check.py` sweeps the same terms. |
| Result | **PASS** |

### P1-01 — handle reuse can inherit a VehicleId

| Aspect | Content |
|---|---|
| Verification | SOURCE VERIFIED: DOMAIN §4.2 continuity rule (same handle + model + ≤ 2 s + plausible position keeps the binding and records plate/colour changes as mutations) and the decorator fast path (model + plate). |
| Correction | D-ID-6: handle, decorator and binding cache are **scheduling hints only**; every observation re-runs the full multifactor decision over the lossless candidate set; a binding survives only if that decision BINDs the same record. Self-found **SF-3**: explicit confirmation could launder a lookalike → D-ID-8 (exactly one candidate ≥ 60 and equal plate, or occupied continuity since the last BIND). |
| Files | `phase0-probes/sim/identity_ref.py` (new), `spec/LSAX-DOMAIN-MODEL.md` §4.2/§4.3/§4.7, `spec/LSAX-MASTER-SPEC-v1.0.md`, `spec/LSAX-PERFORMANCE-BUDGET.md`, `spec/LSAX-TEST-STRATEGY.md` (T-ID-4), `decisions.md` |
| Regression | `regress_p1_01_02_identity.py` H1–H8: same handle + model + nearby different vehicle; nearly identical appearance; reuse after despawn; two legitimate similar vehicles with swapped handles; stale cache across streaming; decorator collision / stale hint; respray liveness; in-place plate change (confirmable only with occupied continuity). The DRAFT1 rule is reproduced as defective in H1, H2, H4, H6. |
| Result | **PASS** (34/34 for P1-01 + P1-02) |

### P1-02 — candidate cap can create false uniqueness

| Aspect | Content |
|---|---|
| Verification | SOURCE VERIFIED: DOMAIN §4.4 "bounded to ≤ 32 candidates … nearest last-seen first" before the uniqueness test. |
| Correction | D-ID-7: lossless bounded search. Lemma (exhaustively checked): a record with a different plate scores ≤ 64 and can neither BIND nor break a BIND's uniqueness; a record outside K1 reaches ≥ 60 only with all colours equal and context 15. Hence K1 = (model, plate) decides BIND/uniqueness, K2 = (model, colour signature) ∩ context-15 decides AMBIGUOUS vs NO MATCH. Both evaluated completely from persistent indexes; K1 > 32 time-sliced (Deferred) up to 256, beyond → AMBIGUOUS(OVERFLOW); K2 > 64 → AMBIGUOUS(OVERFLOW). Truncation never yields BIND or NO MATCH. |
| Files | `phase0-probes/sim/identity_ref.py`, `spec/LSAX-DOMAIN-MODEL.md` §4.4, `spec/LSAX-DB-SCHEMA-DRAFT.md` (`ix_fp_k1`, `ix_fp_k2`), `decisions.md` |
| Regression | `regress_p1_01_02_identity.py` C1–C6: > 32 same-model records with a far plate-twin (DRAFT1 false BIND reproduced); > 32 at a spawn point with a far colour-twin (DRAFT1 false NO MATCH reproduced); K1 = 100 (4 slices, verdict = reference); K1 = 300 (OVERFLOW); K2 = 80 (OVERFLOW); 1 500 randomized dense populations (up to 400 records) equal to the unbounded reference. `identity_ref.py`: 3 000/3 000 equal; DRAFT1 79 false BIND, 71 false NO MATCH. |
| Result | **PASS** |

### P1-03 — PT / MT contract inconsistency

| Aspect | Content |
|---|---|
| Verification | SOURCE VERIFIED: TIME §2.2 reconstructed MT(P) from PT while §2.3 declared PT anchor-only; skip credit persisted only by the periodic checkpoint. |
| Correction | D-TIME-2: PT is an anchor coordinate only; **MT is never reconstructed from PT**. The MT state `(mt, base_mt, recent_credits)` is restored exclusively from LSAX's own records (Aborted flush, durable checkpoint, save-ledger row sampled after skip detection, campaign root). Every skip credit is durable at grant (immediate `SYS_MT_CHECKPOINT`). Self-found **SF-6**: the rolling-cap bookkeeping is timeline state and must be restored with MT. PT semantics during pause/loading/switch/fades are no longer required. |
| Files | `phase0-probes/sim/time_ref.py` (new), `spec/LSAX-TIME-MODEL.md`, `spec/LSAX-MASTER-SPEC-v1.0.md` §06/§07, `spec/LSAX-SAVELOAD-FEASIBILITY.md` §4.2, `spec/LSAX-DB-SCHEMA-DRAFT.md`, `decisions.md` |
| Regression | `regress_p1_03_time.py`: pause, loading, protagonist switch, short/long fades, GT stall, sleep (credit durable at grant), save immediately after sleep (restored exactly), crash before the periodic checkpoint (no credit lost), save/load around a time skip (incl. rolling cap carried), offline freeze, rolling cap, PT-semantics independence; DRAFT1 MT(P) defect reproduced — **21/21 PASS**. |
| Result | **PASS** |

### P1-04 — system journal event protocol missing

| Aspect | Content |
|---|---|
| Verification | SOURCE VERIFIED: `journal_event.txn_id NOT NULL REFERENCES txn` while OdometerCheckpoint/MarketStep/MtCheckpoint/HeatDelta had no transaction kind. |
| Correction | D-JRN-1 / TSM §3a: kinds SYS_MT_CHECKPOINT, SYS_ODO_CHECKPOINT, SYS_MARKET_STEP, SYS_HEAT_DECAY, SYS_HEAT_EVENT, SYS_LISTING_EXPIRY; random txn id + deterministic idempotency key per family; one durable commit through txn → commit_log (same per-timeline sequence) → journal_event; active-path duplicate suppression via `applied_idem` PRIMARY KEY inside that commit; ordering gate against a PREPARED business transaction; retry, crash, replay, branch-regeneration and coalescing rules (coalescing only for MT/ODO checkpoints). |
| Files | `phase0-probes/sim/sysjournal_ref.py` (new), `spec/LSAX-TRANSACTION-STATE-MACHINE.md` §3/§3a, `spec/LSAX-DB-SCHEMA-DRAFT.md` (§3, §4 event → kind table), `spec/LSAX-TEST-STRATEGY.md` (T-TX-6), `decisions.md` |
| Regression | `regress_p1_04_sysjournal.py`: for each of the 6 families — crash before commit, lost acknowledgement + reopen, rebuild = live, double replay, rewind + branch regeneration, ordering gate, coalescing rule; plus market-step catch-up after rewind — **68/68 PASS**. |
| Result | **PASS** |

### P1-05 — NPC VehicleId uniqueness across market steps

| Aspect | Content |
|---|---|
| Verification | REPRODUCED: baseline `derive_seed("vehicle", campaign, market_day, segment, slot)` with step-local slots → two steps of MT day 42 gave 3/3 identical VehicleIds and identical vehicles; weak avalanche of raw FNV-1a ids observed. |
| Correction | D-GEN-6: generation identity `(campaign, market_step_index, segment, generation_ordinal)`; VehicleId low 64 = `mix64(pack(step:40, segment:4, ordinal:20))` — **injective by construction** (packing injective, SplitMix64 finaliser bijective; out-of-range refused) instead of hashing (the suggested "hash of the tuple" would only be probabilistically unique); high 64 = campaign salt with a generated-namespace bit. |
| Files | `phase0-probes/sim/lsax_ref_math.py` (mix64/unmix64), `phase0-probes/sim/npcgen_ref.py`, `spec/LSAX-NPC-GENERATION-MODEL.md` §2/§7, `spec/LSAX-DOMAIN-MODEL.md` §4.1, `spec/LSAX-MASTER-SPEC-v1.0.md`, `decisions.md` |
| Regression | `regress_p1_05_npc_identity.py`: DRAFT1 collision reproduced; steps within one MT day distinct; injectivity round trip (20 000); 388 800 ids over 90 MT days distinct; 200 steps with replenishment, sales and expiry; rewind replay identical; two branches never reuse an identity; deterministic regeneration; campaign namespaces; avalanche 32.1 vs 10.6 bits — **17/17 PASS**. Generation digest unchanged (`d63a888c…6afcb`). |
| Result | **PASS** |

### P1-06 — LEGACY import can launder provenance

| Aspect | Content |
|---|---|
| Verification | SOURCE VERIFIED: DOMAIN LEGACY "treated as CLEAN"; self-found **SF-2**: `UNKNOWN → CLEAN` via title verification, which only checks STOLEN records. |
| Correction | D-PROV-1: LEGACY title and TITLE_VERIFY withdrawn. First-run import → UNKNOWN unless a LEGACY_TRUSTED rule holds; the set is **empty** until a runtime probe proves an unspoofable ownership marker (never model, plate, garage or opt-in); mission/script-owned vehicles are not imported; no transition leads to CLEAN from UNKNOWN, STOLEN or UNDERGROUND. P-ID-01 now logs research fields (`mission`, `pop`, owning `script`). Accepted cost R-PROV-1. |
| Files | `phase0-probes/sim/legacy_ref.py` (new), `phase0-probes/sim/valuation_ref.py` (LEGACY_OWNED removed; output byte-identical), `spec/LSAX-DOMAIN-MODEL.md` §5.2, `spec/LSAX-TRANSACTION-STATE-MACHINE.md`, `spec/LSAX-MASTER-SPEC-v1.0.md`, `spec/LSAX-DB-SCHEMA-DRAFT.md`, `decisions.md`, risk registers |
| Regression | `regress_p1_06_legacy.py`: stolen car, ambient traffic car, mission/script-owned vehicle, trainer-spawned vehicle, add-on, legitimately owned pre-LSAX vehicle and a trainer copy of a story car — each with/without opt-in and garage → never CLEAN or legal-eligible; hypothetical proven-marker rule vs spoofable rule; exhaustive title reachability — **75/75 PASS**. |
| Result | **PASS** |

### P2-01 — SQLite online backup wording / architecture

| Aspect | Content |
|---|---|
| Verification | SOURCE VERIFIED: "online backup API … (projection tables only)" — the API copies a whole database (schema), not tables. |
| Correction | D-DB-4: two database files — journal + global + `applied_idem` in `lsax.db` (`main`, synchronous=FULL); projection in `lsax_proj.db` ATTACHed as `proj` (synchronous=NORMAL); journal commit first, projection commit second with a watermark (may lag, never lead; catch-up gate); snapshot = online backup of schema `proj` (`BackupDatabase(dest, "main", "proj")`, overload verified in Microsoft.Data.Sqlite 8.0.11 netstandard2.0); journal backup = online backup of `main`; rebuild from the newest snapshot whose watermark is an ancestor of the target. |
| Files | `spec/LSAX-DB-SCHEMA-DRAFT.md` (§1, §2, §3, §5–§8), `spec/LSAX-PERFORMANCE-BUDGET.md`, `decisions.md`, `phase0-probes/shvdn/LsaxPhase0SqliteProbe/SqliteReloadProbe.cs`, `phase0-probes/dotnet-checks/backupcheck/` |
| Regression | `regress_p2_01_backup.py` (real SQLite backup API): proj-only snapshot, journal-only backup, crash between the two commits (lag, catch-up = rebuild), projection loss, ancestor-snapshot restore + replay, off-path snapshot rejected, snapshot during concurrent writes, pragmas — **11/11 PASS**; .NET 8 check of the exact calls PASS. |
| Result | **PASS** |

### Self-found defects (recorded in `progress.md`)

| ID | Found | Defect | Correction | Regression |
|---|---|---|---|---|
| SF-1 | C0-03 | continuation accepted on play-time/wallet correlation | D-SL-14 session token | P0-03 cases 11, 12, 15 |
| SF-2 | C0-03 | `UNKNOWN → CLEAN` via title verification | D-PROV-1 | P1-06 reachability |
| SF-3 | C0-07 | explicit confirmation could launder a lookalike | D-ID-8 | P1-01 H2, H8, H8b |
| SF-4 | C0-15 | asynchronous save write: a transaction between snapshot and file gives the ledger a wrong head | D-SL-18 save-in-progress gate | P0-03 cases 24, 24b, 26 |
| SF-5 | C0-15 | bracket starting at the poll before the file change excludes an async save's own play-time | D-SL-17 amended (pre-signal bracket) | P0-03 case 25 |
| SF-6 | C0-08 | rolling skip-credit bookkeeping not restored with MT | D-TIME-2 MT state | P1-03 T9 |

## 4. Cross-document consistency

All 16 spec documents carry the DRAFT2 header; stale DRAFT1 rules were removed or explicitly marked historical
(withdrawn decisions are flagged inline in `decisions.md`; DRAFT1 journal-sim evidence E8-5 is marked SUPERSEDED).
`phase0-probes/tools/xref_check.py` (IDs defined, paths exist, deliverables, master sections, DRAFT2 headers, risk
counts, cited scripts exist, stale-term sweep in 13 categories: Stage 1a/S1a, wallet_after proof, INFERRED/ghost
lineage, fast path, ≤ 32 candidates, MT(P), LEGACY, title verification, market_day seed, projection-only backup,
stop markers, heartbeat) → **PASS** on DRAFT2; the same checker reports 72 problems on the DRAFT1 tree (non-vacuous).

## 5. Reference simulations (audit grade)

`python3 phase0-probes/sim/run_all.py --audit` — results in `evidence/sim/SUMMARY.md` and `evidence/regress/SUMMARY.md`:

| Item | Result |
|---|---|
| Reference models (`lsax_ref_math`, `valuation_ref`, `npcgen_ref`, `heat_ref`, `identity_ref`, `time_ref`, `sysjournal_ref`, `legacy_ref`) | all PASS |
| `journal_timeline_ref.py --episodes 200` (DRAFT2, incl. asynchronous saves) | PASS — 800 episodes (2 mixes × 2 play-time granularities × 200), 4 447 injected crashes (C0/C1/CA/CB/C2/C3), 79 missed script-domain starts, 22 668 observed saves, 2 725 transactions deferred by the save gate, 6 614 automatic anchorings after the first run (1 445 continuation, 5 169 slot), 290 own-evidence roll-forwards, 324 own-evidence aborts, 654 slot-anchored aborts, **0 safety-invariant failures** (I0 ground truth, I1 garage, I2 idempotent replay, I3 no double sale, I6 refusal and persistence), every recovery/refusal path exercised; 158.6 s |
| RECONCILE_REQUIRED rate (R-SL-3, OPEN) | realistic mix 24.7 % (G = 1 ms) / 22.8 % (G = 1 s); adversarial 59.7–60.8 % of non-first session starts — the price of refusing whenever positive lineage is missing; a model property under a crash-heavy mix, not a runtime measurement |
| Correction regressions (10 suites) | **2 645/2 645 PASS** (21.1 s) |
| Total run time | 199.1 s on one CPU (Python 3.11.15); fast mode (`run_all.py` without flags) ≈ 1.5 min |

DRAFT1's journal result (800 episodes, 0 failures) is withdrawn as evidence (feasibility E8-5): its random adversary
never produced the audit counterexamples, which is why DRAFT2 relies on directed regressions in addition to random
histories.

## 6. Unresolved runtime assumptions (all ASSUMPTION; closed only by target-runtime evidence)

| ID | Assumption | Probe / criterion |
|---|---|---|
| A-SL-1 | SP load, new game and game start restart SHVDN's script domain | P-SL-01 PC-1 |
| A-SL-3 | `Aborted` timing (informative; design already safe) | PC-6 |
| A-SL-4 | a save snapshot never interleaves an LSAX tick | PC-4 tick markers |
| A-SL-5 | all three wallets restored exactly on load | PC-3 |
| A-SL-6 | persisted play-time stat, exact on load, non-decreasing within a session | PC-2 |
| A-SL-7 | save-file writes observable, content hash readable | PC-4 |
| A-SL-8 | GTA loads only profile slot files; loaded file unchanged at LSAX's scan | PC-8 |
| A-SL-9 | LSAX constructed at every domain start; failed start can write MISSED_START | PC-1 + source |
| A-SL-10 | session-token decorator survives reloads, never survives load/new game/new process | PC-5, PC-7 |
| A-SL-12 | save-event signal active from no later than the snapshot until the file write; copies raise none | PC-4, PC-8 |
| A-SL-13 | new game starts with play-time ≤ 60 000 ms | PC-2 (T16) |
| A-SL-14 | no mod changes and restores a wallet between two polls | PC-8 (T17) |
| A-ENV-1 | user's SHVDN 3.7.x lifecycle code equals the pinned source | P-SL-01 version log |
| R-DB-1/2, R-COMP-2 | native SQLite load, commit latency, dependency resolution in SHVDN | P-DB-01 |
| R-ID-4 (+ OD-4) | mission-entity status of story vehicles; any LEGACY_TRUSTED marker | P-ID-01 |
| R-UI-1 | renderer feasibility (UI-S1; no probe code prepared in Phase 0) | MASTER §20 |
| R-COMP-1, R-ECO-1 | third-party mod behaviour, cash writes near transactions | full-modpack P-SL-01 / P-ID-01 runs |

Owner decisions also required before SPEC_APPROVED (not runtime facts): acceptance of the RECONCILE profile (R-SL-3)
and of the TM-1 boundary (R-SL-7), OD-1…OD-6.

## 7. Final correction-pass status

Every audit finding P0-02…P2-01 is corrected offline and proven by deterministic regressions (all PASS); P0-01 is
preserved as a BLOCKER with a complete runtime validation package; no Stage-1 work was started; SPEC_APPROVED is not
claimed.

**OFFLINE_CORRECTION_COMPLETE — RUNTIME_VALIDATION_REQUIRED**

The DRAFT2 package is `release/LSAX-MASTER-SPEC-v1.0-DRAFT2.zip`; its SHA-256 is published in
`release/LSAX-MASTER-SPEC-v1.0-DRAFT2.zip.sha256` and in the final hand-over message (a file inside the ZIP cannot
contain the ZIP's own hash). Only a later independent reviewer may issue SPEC_APPROVED, after the runtime evidence
of §6 exists.
