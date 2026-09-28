# LSAX Phase 0 — progress.md (durable task state)

Recovery rule: on restart/compaction, read progress.md, decisions.md, risks.md,
feasibility.md and continue from the first item not marked [x]. Do not restart Phase 0.

## Status log

- 2026-09-28 S0: Session start. Repo empty (only .git). Branch target: claude/focused-thompson-ilnspm.
  Uploaded archives (read-only inputs):
  - 183fb72c-LSAX-PHASE0-V3-PACK.zip (authoritative Phase 0 pack)
  - 5763f60a-1cf350-Sell_Vehicles_v1.2.zip (READ-ONLY reference)
  - 9261e306-db5c90-SellCars.zip (READ-ONLY reference)

- 2026-09-28 S0b: BLOCKED transiently — Bash auto-mode classifier returned "no verdict (error)"
  on 8 consecutive calls; archives cannot be unzipped with read-only tools. Self-resume scheduled.
  Next action on resume: P0-01 (unzip pack to scratchpad/pack, read files in mandated order).
- 2026-09-28 S0c: User said "try again"; classifier still returned no verdict on 3 more Bash calls.
  Still blocked at P0-01. Nothing has been extracted or read yet; no spec work started.
- 2026-09-28 S1: Resumed with auto mode off (Bash via normal approval). Confirmed branch
  claude/focused-thompson-ilnspm (no commits yet), progress.md preserved. Committing checkpoint,
  then continuing from P0-01.
- 2026-09-28 S2: P0-01..P0-08 completed in session S1 (see checklist). Archive packaged; push pending (P0-09).

## Checklist

- [x] P0-01 Extract + read pack files in mandated order (00, 02, 01, 03, 04, 05)
      Pack extracted to scratchpad/pack; `sha256sum -c SHA256SUMS.txt` = all 6 OK.
      Input archive SHA-256:
        PACK 3ed73d4045db246468d5453904eeff5aabbf1dbf682ef752e29643a28e536d48
        SellVehicles v1.2 110362ea5213400d23567ad595256748e4e33e2e8f154da4b61295f03ce61322
        SellCars d6dca5cef76a0c39ee81a4974abe320881610e37c7c576ce2f74d5a243206a10
- [x] P0-02 Derive full deliverable list from 05-CLAUDE-OPUS-PHASE0-PROMPT.txt
      Deliverables (all inside LSAX-MASTER-SPEC-v1.0-DRAFT1.zip) — inventory only; the single
      authoritative STATUS list is under P0-06 / P0-08 below:
      LSAX-MASTER-SPEC-v1.0.md (sections 00..30 + appendices per 03-*.md), LSAX-DOMAIN-MODEL.md,
      LSAX-SAVELOAD-FEASIBILITY.md, LSAX-TIME-MODEL.md, LSAX-DB-SCHEMA-DRAFT.md, LSAX-VALUATION-MODEL.md,
      LSAX-NPC-GENERATION-MODEL.md, LSAX-HEAT-AND-UNDERGROUND-MODEL.md, LSAX-TRANSACTION-STATE-MACHINE.md,
      LSAX-COMPATIBILITY-CONTRACT.md, LSAX-PERFORMANCE-BUDGET.md, LSAX-LOCALIZATION-CONTRACT.md,
      LSAX-TEST-STRATEGY.md, LSAX-STAGE-ACCEPTANCE.md, LSAX-RISK-REGISTER.md, LSAX-REFERENCE-REVIEW.md,
      progress.md, decisions.md, risks.md, feasibility.md, SHA-256 manifest.
      Appendices required: domain/state diagrams, DB schema draft, valuation formula + >=8 vectors,
      Heat examples, mileage/generation examples, identity collision matrix, save/load decision
      record, transaction interruption/recovery matrix, localization key examples, perf budget
      table, compatibility ownership matrix, SPEC_APPROVED checklist.
      Rule: no self-granted SPEC_APPROVED; no production C#/DLLs in the archive.
- [x] P0-03 Inspect reference archives (observations only, no copying)
      Both are compiled DLLs only (SellVehicle: SHVDN3 3.3.2 + PDB; SellCars: SHVDN2 2.11.6).
      Metadata dump + native-hash IL scan + partial IL decode via scratchpad/tools/*.py (dnfile 0.18.0).
      Written: spec/LSAX-REFERENCE-REVIEW.md (R1..R13).
- [x] P0-04 Environment inventory (dotnet/mono/SHVDN availability for probes)
      Linux container, NO GTA runtime. Python 3.11 + dnfile; dotnet-sdk-8.0 (8.0.131) via apt
      (MS download hosts 403). SHVDN source cloned read-only at /home/user/scripthookvdotnet/scripthookvdotnet
      (@56ba3bf); native DB at /home/user/alloc8or/gta5-nativedb-data (@424fb51). See feasibility.md E0.
- [ ] P0-05 Feasibility probes
      [x] F-a SHVDN lifecycle/money/decorator/API source evidence (feasibility.md E1..E5)
      [x] F-b Native existence + save-native absence scan (evidence/*.txt)
      [x] F-c Disposable SHVDN probes (phase0-probes/shvdn): P-SL-01 save/load signals,
              P-SL-02 save-anchor carrier, P-ID-01 decorator/handle survival, P-DB-01 SQLite reload;
              compile-check vs ScriptHookVDotNet3 3.6.0 NuGet (net48) -> both Build succeeded, 0 warnings.
              NOT executed (no GTA). Procedure + pass criteria: phase0-probes/README-PROBES.md.
              New evidence E6 (shadow copy + SQLitePCLRaw Location-based native lookup), E7.
      [ ] F-d Offline sims (phase0-probes/sim): valuation vectors, heat, NPC gen, journal crash-injection
          [x] lsax_ref_math.py (rdiv half-away, bp, interp, SplitMix64 ref-checked) PASS
          [x] valuation_ref.py 12 vectors, golden ranges, 4704-case property grid PASS
              (sim-driven change: V10 golden range widened -> decisions D-VAL-9)
          [x] npcgen_ref.py 6 segments x 20k, 0 violations, determinism digest PASS
              (sim-driven: age-wear cap 180 mo D-GEN-4, owner constraint C9 D-GEN-5)
          [x] heat_ref.py decay/tiers/farming PASS (sim-driven: floor decay D-HEAT-3 fixed-point bug,
              retention 9911/9949, velocity haircut D-HEAT-6)
          [x] journal_timeline_ref.py (Model D anchored timeline + txn journal, crash/load injection) PASS
              800 episodes, 0 safety failures, RECONCILE 2-4% of anchorings. Went through 5 sim-driven
              redesigns (decisions D-SL-2, D-SL-8..11, D-TX-1). trace_journal.py = debug tracer.
          [x] run_all.py -> evidence/sim/*.out.md + SUMMARY.md (all PASS, ~2m15s)
      [x] F-e Record results in feasibility.md (E8); decisions.md D-SL-*/D-TX-*/D-VAL/D-GEN/D-HEAT
- [x] P0-05 (closed; runtime proof pending = BLOCKER B-01, owner must run phase0-probes on target PC)
- [x] P0-06 Spec documents (spec/) — all 16 drafted
      [x] LSAX-REFERENCE-REVIEW.md  [x] LSAX-SAVELOAD-FEASIBILITY.md  [x] LSAX-TIME-MODEL.md
      [x] LSAX-DOMAIN-MODEL.md      [x] LSAX-TRANSACTION-STATE-MACHINE.md  [x] LSAX-DB-SCHEMA-DRAFT.md
      [x] LSAX-VALUATION-MODEL.md   [x] LSAX-NPC-GENERATION-MODEL.md  [x] LSAX-HEAT-AND-UNDERGROUND-MODEL.md
      [x] LSAX-LOCALIZATION-CONTRACT.md  [x] LSAX-COMPATIBILITY-CONTRACT.md  [x] LSAX-PERFORMANCE-BUDGET.md
      [x] LSAX-TEST-STRATEGY.md     [x] LSAX-STAGE-ACCEPTANCE.md  [x] LSAX-RISK-REGISTER.md
      [x] LSAX-MASTER-SPEC-v1.0.md (sections 00-30 + appendices, SPEC_APPROVED checklist)
- [x] P0-07 Self-audit / consistency pass
      Mechanical: phase0-probes/tools/xref_check.py (IDs defined, paths exist, risk sets equal, sections 00-30,
      appendices A-L). First run: 32 problems (7 decision IDs, 8 assumption IDs, T-ARCH-1, UI-S1 and one stray probe label undefined +
      checker range handling) -> fixed (decisions.md architecture block, RISK-REGISTER §4 assumption register,
      TEST-STRATEGY rows) -> PASS (230 IDs).
      Semantic: fixed R-TIME-1 cap wording; added T-COND-1 calibration (runtime wear vs generation wear mismatch
      1.9 vs 1.2 M-points/1000 km); labelled in-session anchoring as PC-1 fallback not covered by the sim; fixed
      master §29 P1 count (12). Stale-constant grep clean. Sim source hashes == evidence/sim/SUMMARY.md.
      Hygiene: no personal paths in tracked files (only container clone paths in this file); no binaries tracked.
- [x] P0-08 SHA-256 manifest + LSAX-MASTER-SPEC-v1.0-DRAFT1.zip
      Built by phase0-probes/tools/package.py -> release/LSAX-MASTER-SPEC-v1.0-DRAFT1.zip (+ .zip.sha256);
      MANIFEST.sha256 inside covers every packaged file (git-tracked files only; bin/obj never packaged).
- [x] P0-09 Commit + push to claude/focused-thompson-ilnspm — performed after packaging; the repository copy
      of this file (not the archived copy) records the push result.
      Pushed 6118472 (release commit); `git ls-remote` head == local HEAD. Archive in repo:
      release/LSAX-MASTER-SPEC-v1.0-DRAFT1.zip, SHA-256 281f52f6e989ed7de93d4af7d61e25e9a2369fa7d74856f5d666357896cccd16
      (two builds byte-identical; extracted copy: manifest 55/55 OK, xref PASS, sims regenerate identical evidence).
      Note: the archived progress.md shows P0-09 open because it was snapshotted before this push.

## Final state for the reviewer
- SPEC_APPROVED is NOT self-granted. Gate item "save/load persistence model proven feasible" = FAIL (BLOCKER B-01).
- Next action for the project owner: run phase0-probes (P-SL-01 required, P-DB-01 required, P-ID-01/P-SL-02 optional)
  on the target PC per phase0-probes/README-PROBES.md, then send logs back for B-01 closure.

---

# PHASE 0 — CORRECTION PASS 1 (durable state)

Recovery rule: continue from the first C0 item not marked [x]; do NOT restart the correction pass; never modify
the audited branch `claude/focused-thompson-ilnspm`, DRAFT1 files, PR #1 or `main`.

- Correction baseline (audited head): f6aff47d1dbea94576d6aae1f60bd17102d549cc
- Correction branch: claude/phase0-correction-1 (created from exactly the baseline, 2026-09-28)
- DRAFT1 release SHA-256: 281f52f6e989ed7de93d4af7d61e25e9a2369fa7d74856f5d666357896cccd16
  (release/ file == uploaded copy == `git show f6aff47:release/...` — verified identical)
- Audit bundle: LSAX-PHASE0-INDEPENDENT-AUDIT.zip SHA-256 35d3c55d503ad398e574d267fdd59ea0d15882dcd2573548c7a3399b08995bb2
- Remote refs at start: audited branch f6aff47, refs/pull/1/head f6aff47, main ec56878 (untouched)
- Audit verdict: CORRECTION_REQUIRED — SPEC_APPROVED BLOCKED (4 P0, 6 P1, 1 P2)

## C0 checklist
- [x] C0-01 Verify audited baseline and create correction branch
- [x] C0-02 Read full independent audit bundle
      Bundle files (SHA256SUMS.txt 4/4 OK): LSAX-PHASE0-INDEPENDENT-AUDIT.md, repro_findings.py, REPRO-OUTPUT.txt,
      AUDIT-EVIDENCE.txt. Auditor could not finish the full 800-episode journal rerun (container timeout) -> DRAFT2
      must provide a fast mode and report run time.
- [x] C0-03 Reproduce/source-verify every finding (results in ledger below; all 11 confirmed, 0 disproven;
      2 related defects self-found: continuation accepted on P/W correlation; UNKNOWN→CLEAN via title verification)
- [x] C0-04 Correct P0-02 transaction recovery
      D-TX-4/D-TX-5: own-evidence recovery (durable APPLYING at PREPARE, in-memory status flushed in Aborted),
      roll-forward only with session token + own APPLIED; COMMIT-failure compensation / FAULT. Files: sim
      journal_timeline_ref.py (rewritten), spec TSM §1/§4/§7/§10, SAVELOAD §4.4. Regressions:
      regress/regress_audit_repro.py (auditor script byte-identical: 7/7 PASS),
      regress/regress_p0_02_txn_recovery.py (432 scenarios, 2304/2304 PASS).
- [x] C0-05 Correct P0-03 save lineage
      D-SL-13..17: content-hash ledger + save-event corroboration, session-token continuation, hypothesis exclusion
      (correlation only excludes), LIVE/NEW_GAME/PRE_INSTALL/MISSED_START, poll brackets. STANDARD/STRICT split
      rejected (STANDARD = correlation acceptance). Files: sim journal_timeline_ref.py, spec SAVELOAD (rewritten),
      decisions.md. Regressions: regress/regress_p0_03_save_lineage.py (23 cases, 73/73 PASS; residual R-SL-7
      demo reproduces). Random sim default run: 0 safety failures, full path coverage, 50 s; realistic RECONCILE
      15.2-16.7 % (R-SL-3 OPEN).
- [x] C0-06 Remove P0-04 Stage-1a exception
      D-GATE-1 applied: STAGE-ACCEPTANCE Phase-0 gate + single Stage 1 (entry SPEC_APPROVED), MASTER §28/§30/App. L,
      RISK-REGISTER (gate semantics: every open P0/P1 blocks SPEC_APPROVED; closure OFFLINE/RUNTIME column),
      risks.md, feasibility.md E7-3. Regression regress/regress_p0_04_gate.py 24/24 PASS (static scan; the same
      scan finds 22 carve-out lines in the DRAFT1 baseline texts, 0 in DRAFT2).
- [x] C0-07 Correct P1-01/P1-02 identity safety
      D-ID-6 (revised: no continuity/decorator fast path; every observation = full decision over the lossless set),
      D-ID-7 (K1/K2 lossless search, DEFER <= 256, OVERFLOW -> AMBIGUOUS; lemma L1/L2 exhaustively checked),
      D-ID-8 (explicit confirmation needs equal plate or occupied continuity — closes lookalike laundering by
      confirmation). Files: sim/identity_ref.py (new), DOMAIN §4.2-§4.4/§4.7 (C4, C6, C8, C11 rewritten; C21, C22
      added), MASTER glossary/§05 summary, PERFORMANCE §2/§3, TEST-STRATEGY T-ID-1/T-ID-3, STAGE-ACCEPTANCE,
      DB-SCHEMA (K1/K2 indexes; also save_ledger/slot_state/apply_status for C0-04/05), RISK-REGISTER R-ID-3,
      risks.md. Regression regress/regress_p1_01_02_identity.py 34/34 PASS (DRAFT1 defect reproduced in H1, H2, H4,
      H6, C1, C2; randomized 1500 dense populations: DRAFT2 == unbounded reference, DRAFT1 39 false BIND / 38 false
      NO MATCH).
- [x] C0-08 Correct P1-03 time model
      D-TIME-2 (refined): PT anchor-only; MT state (mt, base_mt, recent credits) restored only from LSAX records
      (Aborted flush / durable checkpoint / save-ledger row / campaign root); credit durable at grant; MT frozen while
      LSAX is down. Self-found during regression: the rolling-cap bookkeeping is timeline state and must be restored
      with MT (else reloading a pre-sleep save wrongly blocks a legitimate credit). Files: sim/time_ref.py (new),
      TIME-MODEL (header, §1, §2.2, §2.3, §3, §4, §5), MASTER §06/§07, SAVELOAD §4.2, DB-SCHEMA save_ledger MT state,
      decisions D-TIME-2. Regression regress/regress_p1_03_time.py 21/21 PASS (DRAFT1 MT(P) defect reproduced in T7
      and T8).
- [x] C0-09 Correct P1-04 system journal protocol
      D-JRN-1: TSM §3a (6 SYS_* kinds, deterministic keys, single commit through txn -> commit_log -> journal_event,
      active-path duplicate suppression via applied_idem PK, ordering gate vs PREPARED, retry, crash, replay, branch
      regeneration, coalescing only for MT/ODO checkpoints). OFFER_EXPIRE folded into SYS_LISTING_EXPIRY. Files:
      sim/sysjournal_ref.py (new), TSM §3/§3a, DB-SCHEMA (commit_log.kind, applied_idem, §4 event->kind table),
      TEST-STRATEGY T-TX-5/T-TX-4b, MASTER §07. Regression regress/regress_p1_04_sysjournal.py 68/68 PASS.
- [x] C0-10 Correct P1-05 NPC generation identity
      D-GEN-6 (refined to injective packing + bijective mix64 instead of hashing): uniqueness by construction.
      Files: sim/lsax_ref_math.py (mix64/unmix64), sim/npcgen_ref.py (identity functions; generate() signature is
      (campaign_seed, market_step_index, segment, generation_ordinal); determinism digest unchanged d63a888c...6afcb),
      NPC-GEN §2, DOMAIN §4.1, MASTER §10/AX-9/glossary, decisions. Regression regress/regress_p1_05_npc_identity.py
      17/17 PASS (DRAFT1 3/3 collision reproduced; 388 800 ids distinct; replenishment/sold/expired over 200 steps;
      rewind replay identical; branches never reuse an identity; avalanche 32.1 vs DRAFT1 10.6 bits).
- [x] C0-11 Correct P1-06 LEGACY provenance
      D-PROV-1 (refined): LEGACY title and TITLE_VERIFY withdrawn; first-run import UNKNOWN unless LEGACY_TRUSTED
      (empty until an unspoofable marker is runtime-proven); opt-in never changes the title; no path to CLEAN from
      UNKNOWN/STOLEN/UNDERGROUND. Files: sim/legacy_ref.py (new), sim/valuation_ref.py (LEGACY_OWNED removed; output
      byte-identical), DOMAIN §5.2 + first-run import rule + history events, TSM §3/§6, MASTER glossary/§12/§18/§21/
      AX-5, DB-SCHEMA title CHECK, decisions, RISK-REGISTER/risks R-PROV-1. Regression regress/regress_p1_06_legacy.py
      75/75 PASS (stolen, ambient, mission, trainer, add-on, legit pre-LSAX, trainer copy of a story car, each with/
      without opt-in and garage; exhaustive title reachability).
- [x] C0-12 Correct P2-01 backup architecture
      D-DB-4 (refined): lsax.db (journal, FULL) + lsax_proj.db attached as proj (projection, NORMAL); journal commit
      first, projection second (lag never lead; catch-up gate); snapshot = online backup of schema proj
      (BackupDatabase(dest,"main","proj") — overload verified in Microsoft.Data.Sqlite 8.0.11 netstandard2.0 XML docs;
      executed by P-DB-01 in C0-15); journal backup = online backup of main; rebuild from newest ancestor snapshot.
      applied_idem moved to main (dedupe must be atomic with the journal commit). Files: DB-SCHEMA §1/§2/§3/§5/§6/§7/§8,
      PERFORMANCE §2, decisions. Regression regress/regress_p2_01_backup.py 11/11 PASS (real SQLite backup API).
- [x] C0-13 Reconcile all affected documents
      Stale-term sweep (Stage 1a/S1a, wallet_after causal proof, INFERRED/ghost downtime lineage, handle fast path,
      <=32 uniqueness, PT/MT reconstruction, LEGACY -> CLEAN, old NPC seed formula, projection-only backup, stop
      markers, heartbeat, E8-5 claims): all spec headers DRAFT2; MASTER header/summary/glossary/§05/§06/§10/§16/§28/
      §29/App. L rewritten; TEST-STRATEGY aligned (T-SL-1/2, T-TX-4/4b/6, T-ID-4, T-TIME-3, T-GEN-8, T-PROV-1,
      T-DB-6, T-GATE-1; ID collisions avoided); PERFORMANCE rows (MT checkpoint, token re-tag, poll cadence);
      LOCALIZATION keys for new RECONCILE reasons + UNKNOWN title (RU/EN parity, no typographic glyphs); NPC-GEN
      example headings; feasibility E8-5/E8-6 marked SUPERSEDED; decisions: withdrawn rows marked inline,
      D-SL-1/D-SL-7 amended; RISK-REGISTER counts (13 P1, 14 P2).
- [x] C0-14 Add/run deterministic regression suite
      regress/run_regressions.py (10 suites, 2 634 checks, 14 s) + sim/run_all.py (fast default 60 episodes / --audit
      200 episodes; now also runs identity_ref, time_ref, sysjournal_ref, legacy_ref and the regressions; writes
      evidence/sim + evidence/regress with source hashes and run times). trace_journal.py ported to DRAFT2.
      Audit-grade run: ALL PASS, total 192.8 s (journal model 159.5 s: 800 episodes, 4 522 crashes, 0 safety
      failures, full coverage; realistic RECONCILE 17.1-18.3 %). feasibility.md E9-1..E9-12 added; SAVELOAD §5,
      RISK-REGISTER/risks R-SL-3/R-SL-5 updated to audit-grade numbers.
- [x] C0-15 Review/prepare P-SL-01 and P-DB-01
      Self-found SF-4/SF-5 (async save write) fixed first: D-SL-18 gate, D-SL-17 pre-signal bracket; model gained
      SAVE_ASYNC; regress_p0_03 26 cases / 84 checks. P-SL-01 rewritten (per-tick samples, pre-signal brackets, probe
      ledger + LOAD_MATCH, session-token decorator + re-tag, TICK_INTERLEAVE markers, WALLET_CHANGE, PT_DECREASED,
      process key); P-DB-01 extended with D-DB-4 (ATTACH proj, two-file commits, BackupDatabase snapshot/journal backup/
      restore, pragmas, dependency locations); P-ID-01 logs owning script; shared ProbeDecor helper. Clean builds:
      0 warnings / 0 errors (evidence/compile). D-DB-4 calls executed on .NET 8/Linux (dotnet-checks/backupcheck: PASS).
      README-PROBES rewritten as the runtime validation package: target runtime, backup, build, exact install paths,
      launch, T1-T17 with expected log rows, PASS/FAIL rules PC-1..PC-8, P-DB-01/P-ID-01/P-SL-02 procedures, evidence
      collection, cleanup. probe.ini.sample: SessionToken.Enabled. feasibility E9-13/E9-14.
- [ ] C0-16 Full xref/static/spec self-audit
- [ ] C0-17 Rebuild DRAFT2 package and hashes
- [ ] C0-18 Push correction branch
- [ ] C0-19 Report final status

## Finding ledger (verification → correction → regression → closure)

| Finding | Verification (C0-03) | Status |
|---|---|---|
| P0-01 | SOURCE VERIFIED: SAVELOAD §0/§6, MASTER App. L; B-01 open, no runtime here | open (runtime) |
| P0-02 | REPRODUCED: auditor repro_findings.py (ROOT path only changed) against baseline sim (sources == f6aff47) → output byte-identical to auditor REPRO-OUTPUT.txt (A: roll_forward on C1 + external cash == wallet_after). Root cause: sim `anchor()` continuation branch treats `cash == a and a != b` as APPLIED; TSM §7 row 1 normative. Why the 800-episode sim missed it: EXT changes only during OFFLINE windows, rarely landing exactly on wallet_after. | CORRECTED (C0-04): D-TX-4/5; regress_audit_repro A → RECONCILE(PENDING_UNKNOWN); regress_p0_02 2304/2304 PASS |
| P0-03 | REPRODUCED: same run, case B byte-identical. Root cause: changed-while-down files become INFERRED ghost entries matched by P-window only (SAVELOAD §4.2/§4.3; sim `mk_ghost`). R-SL-4 covered only running-time copies. Additional (self-found): continuation itself is accepted on P/W correlation (same process) — a foreign save loaded without process restart could also pass the continuation test. | CORRECTED (C0-05): D-SL-13..17; regress_audit_repro B → RECONCILE(UNTRUSTED_PRESENT); regress_p0_03 73/73 PASS; residual R-SL-7 (TM-1) documented |
| P0-04 | SOURCE VERIFIED: MASTER §28 L345, §30 L378, App. L L432-433; STAGE-ACCEPTANCE L19/34/39; RISK-REGISTER rows B-01, R-SL-2/3/4, R-DB-1, R-COMP-2, R-ENV-1, R-ID-1, R-UI-1, R-COMP-1, OD-3, OD-5, A-SL-4 reference S1a/S1b | CORRECTED (C0-06): D-GATE-1; regress_p0_04_gate 24/24 PASS |
| P1-01 | SOURCE VERIFIED: DOMAIN §4.2 L95-102 ("can never inherit"), C11 L161; mutation-while-bound accepts plate/colour change under handle+model+time+position continuity | CORRECTED (C0-07): D-ID-6/D-ID-8; regress_p1_01_02 H1–H8 PASS |
| P1-02 | SOURCE VERIFIED: DOMAIN §4.4 L125-128 "bounded to ≤ 32 candidates … nearest last-seen first" before uniqueness gap test | CORRECTED (C0-07): D-ID-7 lossless K1/K2; regress_p1_01_02 C1–C6 PASS |
| P1-03 | SOURCE VERIFIED: TIME L45-46 (MT(P) reconstruction from PT + accepted skip-credit loss) vs L57 (PT "only" anchoring); MASTER App. L L419 | CORRECTED (C0-08): D-TIME-2; regress_p1_03_time 21/21 PASS |
| P1-04 | SOURCE VERIFIED: DB-SCHEMA L48 `journal_event.txn_id NOT NULL REFERENCES txn`; L118 event types incl. OdometerCheckpoint/MarketStep/MtCheckpoint/HeatDelta; TSM §3 has no system kind | CORRECTED (C0-09): D-JRN-1, TSM §3a; regress_p1_04_sysjournal 68/68 PASS |
| P1-05 | SOURCE VERIFIED: NPC-GEN L17 and DOMAIN L69 `(campaign_seed, market_day, segment, slot)`; MASTER §11 market step every 60 MT min (24 steps/day); slot scope undefined. REPRODUCED with baseline `npcgen_ref.generate` + `derive_seed("vehicle",…)`: two steps of MT day 42 with step-local slots 0..2 → 3/3 identical VehicleIds and byte-identical vehicles. Also observed: raw FNV-1a ids differ only in a few hex digits (weak avalanche) → correction uses a mixing finaliser | CORRECTED (C0-10): D-GEN-6 injective identity; regress_p1_05_npc_identity 17/17 PASS |
| P1-06 | SOURCE VERIFIED: DOMAIN L191 LEGACY "treated as CLEAN / eligible", L203; TSM L104; MASTER L190. Additional (self-found): DOMAIN title diagram `UNKNOWN --> CLEAN: title verification passed` — verification only checks STOLEN records, so a pre-LSAX/unobserved theft also launders | CORRECTED (C0-11): D-PROV-1; regress_p1_06_legacy 75/75 PASS |
| P2-01 | SOURCE VERIFIED: DB-SCHEMA L127 "online backup API … (projection tables only)"; the backup API copies a whole database (schema), not tables | CORRECTED (C0-12): D-DB-4 two files + proj-schema backup; regress_p2_01_backup 11/11 PASS |
| SF-4 (self-found, C0-15) | REPRODUCED in the model: asynchronous save write + transaction between snapshot and write → ledger head after the transaction → wrong anchoring (31 I0 violations in 30 adversarial episodes with the gate off) | CORRECTED: D-SL-18 save-in-progress gate; regress_p0_03 cases 24/24b/26 |
| SF-5 (self-found, C0-15) | REPRODUCED in the model: bracket lower bound at the poll before the file change excludes an async save's own play-time → wrong exclusion → wrong state accepted | CORRECTED: D-SL-17 amended (bracket starts at the last poll before the save signal); regress_p0_03 case 25 |
