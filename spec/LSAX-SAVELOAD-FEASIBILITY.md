# LSAX — Save/Load Persistence Feasibility & Decision Record

Document: LSAX-SAVELOAD-FEASIBILITY.md · Spec: LSAX MASTER SPEC v1.0 DRAFT2 · Status: DRAFT for independent re-audit

DRAFT2 change summary (Correction Pass 1, findings P0-01/P0-02/P0-03): wallet equality is no longer evidence that
a transaction was applied; files that changed while LSAX was not observing them are UNTRUSTED; INFERRED/ghost
downtime lineage is removed; continuation requires a session token instead of play-time/wallet correlation; slot
anchoring is hypothesis exclusion (correlation may exclude, never include). Decisions D-SL-13…D-SL-17, D-TX-4,
D-TX-5 (decisions.md).

## 0. Status in one paragraph

**BLOCKER B-01 is open — status BLOCKED_RUNTIME_VALIDATION.** Phase 0 runs in a Linux container without GTA V,
so no GTA runtime signal could be observed. Established offline: (1) from pinned SHVDN source, how the script
domain behaves on a new game session and on console reload (E1); (2) from the native DB, that no native exposes a
save slot id, generation, checksum or save timestamp (E4-4); (3) by an offline reference model with a real SQLite
journal and a deterministic regression suite, that the DRAFT2 rules keep LSAX state equal to the LSAX effects
present in the loaded world **or refuse (RECONCILE_REQUIRED)**, including every audit counterexample (§5). Not
established: the runtime assumptions of §9 (A-SL-1, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14). Model D is therefore a
**DESIGN DECISION conditional on B-01**; the exact runtime experiment is §6 and `phase0-probes/README-PROBES.md`.

## 1. Problem statement

GTA V single-player state (per-protagonist cash, garaged vehicles, clock, stats) lives in save files the
player can reload at any time. LSAX state (vehicle identity, history, ownership, listings, transactions,
Heat) lives in LSAX's own SQLite database. Loading an earlier save rewinds GTA but not the database. Without a
synchronisation model:

- buy via LSAX (cash −), load earlier save (cash restored) → LSAX believes the player owns the car: **free car**;
- sell via LSAX (cash +), load earlier save → car and cash both restored in GTA, LSAX believes it is sold;
- mid-transaction crash → money moved but ownership not recorded, or vice versa;
- a save copied in from elsewhere, or written while LSAX was not running, has an LSAX history LSAX never saw.

## 2. Signal inventory (what exists, with evidence labels)

| # | Signal | Evidence | Label | Used by model D as |
|---|---|---|---|---|
| S1 | SHVDN reloads the whole script domain when ScriptHookV starts a new script fiber ("game creates a new session"); `Aborted` handlers run, then constructors run again | `DllMain.cpp` ScriptMain/ClrThreadProc; `ScriptDomain.cs` Unload/Abort (E1-1, E1-2) | VERIFIED (source) | session-start trigger |
| S2 | Whether SP save load / new game makes ScriptHookV start a new fiber | closed-source ScriptHookV | ASSUMPTION A-SL-1 | — (PC-1) |
| S3 | Console `Reload`/reload key trigger the same domain reload | `DllMain.cpp` (E1-3) | VERIFIED (source) | distinguished from a load by the session token (S14) |
| S4 | `Aborted` runs after the new session started | code ordering (E1-4) | VERIFIED (source); timing ASSUMPTION A-SL-3 | never read game state in `Aborted`; only flush LSAX memory |
| S5 | Scripts start only after the loading screen (SHV ≥ 1.0.3351.0) | `Game.Obsolete.cs` (E1-6) | VERIFIED (source note + version order) | constructor sees the loaded world |
| S6 | `SP0/1/2_TOTAL_CASH` via `STAT_GET_INT` (what `Player.Money` reads) | `Player.cs` (E2-1) | VERIFIED (source) | wallet vector — **exclusion only** |
| S7 | Cash restored exactly from the save on load | common knowledge only | ASSUMPTION A-SL-5 | exclusion soundness (PC-3) |
| S8 | A persisted play-time stat, restored exactly on load, non-decreasing within a session, reset on new game | none; candidate names only | ASSUMPTION A-SL-6, A-SL-13 | anchor coordinate — **exclusion only**; never gameplay time (TIME-MODEL §2.3) |
| S9 | Save files `Documents/Rockstar Games/GTA V/Profiles/<id>/SGTA*` change when GTA saves; content hash computable | none in Phase 0 | ASSUMPTION A-SL-7 | save ledger (content identity) |
| S10 | `IS_AUTO_SAVE_IN_PROGRESS`, `GET_STATUS_OF_MANUAL_SAVE`, `HAS_CODE_REQUESTED_AUTOSAVE`, `GET_SAVE_HOUSE_DETAILS_AFTER_SUCCESSFUL_LOAD` exist | native DB + Hash enum (E4-1) | VERIFIED (existence only) | save-event candidates (S15) |
| S11 | Save slot id / generation / checksum / save timestamp natives | name scan of 101 save-related natives (E4-4) | VERIFIED **absent** | not usable |
| S12 | `GET_GAME_TIMER` across load | unknown | not assumed | not used for anchoring |
| S13 | SHVDN main-thread blocking while scripts run → one LSAX tick is not interleaved with a GTA save snapshot | `DllMain.cpp` comment/code (E1-8) | VERIFIED (source); ASSUMPTION A-SL-4 at runtime | single-tick transaction core |
| S14 | Session token: an int decorator on the player ped set by LSAX; survives script-domain reloads within a game session, never survives a load / new game / new process | DECOR natives exist (E4-1); SHVDN decorator API present (E5); behaviour across reload/load unknown | ASSUMPTION A-SL-10 | the **only** continuation evidence (PC-5, PC-7) |
| S15 | Game save event observable (S10 flags and/or save-UI state) within 2 s of every game save; a file copy raises none | none | ASSUMPTION A-SL-12 | corroborates an OBSERVED ledger row (PC-4) |
| S16 | Process identity: `Process.GetCurrentProcess()` Id + StartTime; SHVDN runs inside the game process | .NET BCL; ASI loading (E1) | VERIFIED (source/BCL) | excludes the LIVE hypothesis after a game restart |
| S17 | Loaded file still present and unchanged when LSAX's startup scan runs; GTA loads only profile slot files | none | ASSUMPTION A-SL-8 | hypothesis enumeration is exhaustive (PC-8) |

## 3. Candidate models

| Model | Mechanism | Needs | Evidence verdict | Decision |
|---|---|---|---|---|
| **A** Save-scoped DB (one LSAX DB per GTA save slot) | swap DB file with the slot | the loaded slot id at load time | S11: no slot id native; file access does not reveal which file was *read* | **Rejected** — not implementable without a slot-id signal |
| **B** Snapshot/rollback | snapshot LSAX DB at each GTA save; restore snapshot on load | know which save was loaded → same problem as A | needs an anchor; snapshots redundant with a journal | **Subsumed** into D (rewind = branch, no copies) |
| **C** Independent DB + reconciliation | LSAX never rewinds; reconcile entities that "reappear" | reliable detection of each divergence per entity | money is save-coupled (S6/S7): LSAX-only ledger allows buy-reload exploits | **Rejected alone** (unsafe for money) |
| **D** Anchored Timeline (hybrid) | append-only journal organised as a tree of timelines; each session start either proves continuation (session token) or excludes every alternative explanation of the loaded world against a content-identified save ledger; rewind = new branch; anything unproven → refuse | S1/S2, S6/S7, S8, S9, S13, S14, S15, S16, S17 | logic VERIFIED (sim + regressions, §5); runtime assumptions open | **Selected, conditional on B-01** |

## 4. Model D — normative specification

### 4.1 Evidence rule and concepts

**Evidence rule (normative):** *no positive evidence → no automatic acceptance.* Positive evidence is only
(a) LSAX's own durable knowledge of its own actions (apply status flushed in `Aborted`), (b) the session token
(S14) proving the same live game session, (c) byte-identical content (SHA-256) of a save LSAX observed being written
(S9 + S15). Play-time, wallets, wall-clock proximity and slot names are **correlations**: they may **exclude** a
hypothesis (a mismatch proves "the world was not loaded from that file", given A-SL-5/A-SL-6), never include one.

- **Campaign / Timeline / Commit / Path(t)** — as in DRAFT1: append-only journal organised as a tree of timelines
  (`timeline(id, parent_txn, fork_p, reason ∈ {ROOT, ANCHOR, RESOLVED, NEW_CAMPAIGN})`); a commit is one committed
  LSAX transaction (business or system, TRANSACTION-STATE-MACHINE §3/§3a); Path(t) = ancestors' commits up to each
  fork point, then t's own.
- **State key** — `H:<head txn | EMPTY>` (the LSAX state whose path ends in that commit) or `R:<txn>` (the active
  head plus the pending transaction rolled forward). EMPTY = no LSAX effects (new campaign semantics, §4.8).
- **Save ledger** (`save_ledger`, global, never rewinds): one row per content hash LSAX has positive knowledge of.
  `kind=OBSERVED`: written while running and anchored, corroborated by exactly one game save event; stores
  `head_txn` (active head at observation), play-time bracket `p_lo..p_hi`, wallet vector or NULL, MT state `mt_obs`, `gc_obs`.
  `kind=PRE_INSTALL`: file present at the first-ever start; state EMPTY, fingerprint unknown (NULL).
- **Slot state** (`slot_state`, per current slot file): `(slot file, sha256, status ∈ {TRUSTED, PRE_INSTALL,
  UNTRUSTED}, reason)`. TRUSTED/PRE_INSTALL iff the file's hash is in the ledger. UNTRUSTED reasons:
  `CHANGED_WHILE_DOWN`, `FOREIGN_WHILE_RUNNING` (changed without a save event), `AMBIGUOUS_EVENT` (event cannot be
  attributed to one file), `DURING_RECONCILE`.
- **Session token** — fresh random 31-bit int written at every successful anchoring to the player ped's decorator
  and to `runtime.session_token`; re-tagged every tick if the player ped changed (character switch while running).
- **Session identity** — `runtime.proc` (process Id + StartTime, S16) and `runtime.p_last` (highest play-time LSAX
  observed live in the session; flushed from memory in `Aborted`, otherwise last persisted value — a lower bound).
- **MISSED_START marker** — written by LSAX's catch-all when a script-domain start fails before anchoring (A-SL-9).

### 4.2 Ledger maintenance (while LSAX runs and is not in RECONCILE)

- Poll slot-file metadata every 2 s wall, every tick while a save-event signal is active, and immediately before
  every transaction apply (≤ 16 files; hash only files whose size/mtime changed). The poll keeps a **bracket**:
  play-time and wallet vector at the previous poll; LSAX's own wallet writes restart the wallet bracket (D-SL-17).
- A changed file is **TRUSTED(KNOWN_CONTENT)** if its hash is already in the ledger (byte-identical restore).
- Else it is **TRUSTED(OBSERVED)** only if exactly one game save event (S15) lies within ±2 s of the file write and
  no other changed file competes for it. The new ledger row records `head_txn = active head`, `p_lo = P at previous
  poll`, `p_hi = P now`, wallets = current vector **only if unchanged across the bracket** (else NULL), the MT
  state `mt_obs` (sampled after skip detection in that tick, TIME-MODEL §2.2) and `gc_obs`. Correctness of
  `head_txn`: every transaction polls immediately before its apply and commits in the same tick (A-SL-4), so the
  head cannot change between the save and the observing poll without a poll in between.
- Every other changed file is **UNTRUSTED** (`FOREIGN_WHILE_RUNNING` or `AMBIGUOUS_EVENT`).
- At startup (before anchoring): every file whose hash differs from `slot_state` is TRUSTED/PRE_INSTALL if its hash
  is in the ledger (`RESTORED_COPY`), else **UNTRUSTED(CHANGED_WHILE_DOWN)**. Events raised while LSAX was down are
  discarded. Removed files leave `slot_state`.
- During RECONCILE_REQUIRED no ledger rows are written; at resolution every changed file is re-scanned as
  UNTRUSTED(`DURING_RECONCILE`) unless its hash is known.
- First-ever start (no database): every present file → ledger `PRE_INSTALL` + slot `PRE_INSTALL`.

### 4.3 Anchoring algorithm (normative; mirrors `phase0-probes/sim/journal_timeline_ref.py::anchor`)

```
ANCHOR (at every LSAX start after the startup scan; the first-ever start creates ROOT and anchors EMPTY):
  if runtime.reconcile: stay in RECONCILE_REQUIRED (restarts never clear it); return
  pending = the PREPARED transaction, if any (≤ 1 by construction)
  if player_ped.decorator == runtime.session_token:            -- (b) same live session PROVEN (A-SL-10)
      resolve pending from LSAX's own flushed apply status (TRANSACTION-STATE-MACHINE §7 table A)
      state = active head (+ rolled-forward pending)
  else:
      if runtime.missed_start == this process: RECONCILE(MISSED_START); return
      H = hypotheses():
        LIVE      if runtime.proc == this process and P >= runtime.p_last
                  state: H:head (pending NOT_STARTED/none) | R:pending (APPLIED, prev == head) | unknown (APPLYING)
        NEW_GAME  if P <= NEWGAME_P_MAX (A-SL-13)                         state: H:EMPTY
        per present slot file f:
          UNTRUSTED                                                        state: unknown, never excluded
          TRUSTED/PRE_INSTALL: excluded if f.p_lo is known and P ∉ [f.p_lo, f.p_hi]
                               excluded if f.wallets is known and f.wallets ≠ current wallet vector
                               otherwise                                   state: H:<f.head | EMPTY>
      if any state unknown            → RECONCILE(UNTRUSTED_PRESENT if an UNTRUSTED file, else PENDING_UNKNOWN)
      if no FILE/PRE_INSTALL remains  → RECONCILE(SESSION_UNPROVEN if LIVE remains, else NO_MATCH)
      if distinct states ≠ 1          → RECONCILE(AMBIGUOUS)
      state = the single state; ABORT the pending transaction (TRANSACTION-STATE-MACHINE §7 table B)
  ALWAYS fork a new active timeline at state (parent = its head txn, fork_p = P); new session token;
  runtime.proc = this process; runtime.p_last = P; clear MISSED_START
RECONCILE(reason): persist reason and the list of known candidate states; projection untouched (I6)
```

Why each rule is sound (and what it costs):

| Rule | Soundness argument | Cost |
|---|---|---|
| Token ⇒ continuation | a load/new game/new process destroys all entities, so an equal token proves no load happened since LSAX last anchored (A-SL-10) | none |
| UNTRUSTED ⇒ unknown | the content of an unobserved file is unknown; its LSAX history cannot be derived from play-time or wallets | every token-less start refuses while an UNTRUSTED file exists, until the player overwrites it with an observed save or resolves (R-SL-3) |
| Bracket exclusion | the file was written between two polls and play-time is non-decreasing within a session (A-SL-6); a load restores it exactly | none |
| Wallet exclusion | wallets unchanged across the bracket (A-SL-14) ⇒ they are the file's wallets; a load restores them exactly (A-SL-5) | unknown wallets ⇒ play-time exclusion only |
| LIVE hypothesis | a token can be lost without a load (character switched while LSAX was not running); such a live world has P ≥ p_last | forward loads across branches in the same process refuse (AMBIGUOUS) |
| MISSED_START | a load LSAX did not see may have been followed by play that crosses another file's fingerprint | rare (LSAX start failures only) |
| PRE_INSTALL = EMPTY | this journal has no effects in files that predate it; effects of a former install are foreign (UNKNOWN provenance, DOMAIN §5) | loads while pre-install files exist refuse once LSAX has commits (R-SL-3) |
| ≥ 1 positive file | acceptance needs positive lineage; LIVE/NEW_GAME alone are never proven | new game and token loss need an explicit choice |
| Always fork | rewinds never overwrite history; orphaned branches stay auditable | storage (§4.10) |

### 4.4 PREPARED transaction recovery

Defined in LSAX-TRANSACTION-STATE-MACHINE.md §7 (D-TX-4, D-TX-5). Wallet values are never recovery evidence.

### 4.5 What is timeline-coupled

| Timeline-coupled (rewinds with the save) | Global (never rewinds) |
|---|---|
| vehicle identity registrations, ownership, provenance, odometer/condition checkpoints, modification snapshots, history events, listings, offers, negotiations, market inventory & indices, Heat, mail messages, market step index, MT | configuration, catalogue, localisation, logs, the journal itself (all branches kept for audit), anti-exploit audit trail, save ledger, slot state, runtime/session identity, schema/migration state |

Rationale: everything the player could exploit by reloading is coupled to the same save the money comes from;
deterministic seeding (NPC generation, market events) is keyed on timeline position, so reloading does not
re-roll outcomes (LSAX-NPC-GENERATION-MODEL.md §2).

### 4.6 Odometer and other high-frequency state

Odometer/condition are integrated in memory and checkpointed as system transactions `SYS_ODO_CHECKPOINT`
(TRANSACTION-STATE-MACHINE §3a) at bounded cadence (every ≥ 1 km or ≥ 60 s of driving, and at every lifecycle
checkpoint). A rewind restores the last checkpoint on the anchored path; maximum loss is one checkpoint interval
(≤ 1 km). Documented, not hidden.

### 4.7 RECONCILE_REQUIRED

Entered only by §4.3 or by TRANSACTION-STATE-MACHINE §7. Effects: every market/transaction/ownership operation is
refused with a localised reason (TX-I8); tracking continues read-only (odometer integrates in memory, is not
committed); the projection is untouched (sim invariant I6); restarts keep it (I6). The UI lists the reason and the
known candidate states with their evidence (slot, save time, LSAX head summary). **Exit only by an explicit player
action:** choose a listed candidate, or start a **new LSAX campaign** for this world. Auto-selection is forbidden.

| Reason | Typical cause | Candidates offered |
|---|---|---|
| PENDING_UNKNOWN | crash inside a transaction apply (APPLYING) | "purchase completed" (`R:txn`) / "not completed" (`H:head`) |
| UNTRUSTED_PRESENT | a save copied in, or written while LSAX was not observing, exists in the profile | known candidates + new campaign |
| AMBIGUOUS | two positively lineaged explanations disagree (forward load in the same process; pre-install files) | all known states |
| NO_MATCH | new game; foreign world | EMPTY / new campaign |
| SESSION_UNPROVEN | token lost without evidence of a load | LIVE state |
| MISSED_START | LSAX failed to start at a session start in this process | new campaign or known states |

### 4.8 Why "new campaign" is safe

A new campaign has an EMPTY LSAX state. Vehicles present in the world are then unregistered (UNKNOWN provenance,
LSAX-DOMAIN-MODEL.md §5, never CLEAN — D-PROV-1), which can reduce value but can never duplicate it. Money is
untouched: LSAX never credits cash on anchoring or resolution.

### 4.9 Threat model TM-1 and residual risk

LSAX defends against accidental and incidental inconsistency: crashes at any point, reloads, other mods and
trainers writing cash, saves copied in, restored, downloaded or written while LSAX was not running. It does **not**
defend against deliberate tampering aimed at LSAX: editing LSAX's database, or loading a forged save and swapping the
file back to trusted bytes before LSAX's startup scan (violates A-SL-8) while the forged save reproduces a trusted
file's exact play-time bracket and wallet vector. That residual is **R-SL-7** and is demonstrated exactly by
regression case P0-03/23 (reported separately from the safety PASS count).

### 4.10 Retention

All timelines are kept (audit). Orphaned branches older than 30 MT days and not referenced by any ledger row are
compacted into a summary row (count, value moved) after 1 000 orphaned commits; compaction is itself a journaled
system transaction. Ledger rows whose hash is no longer present in any slot are kept (a restore may bring them
back) up to 256 rows, then oldest-first eviction (an evicted content becomes UNTRUSTED if restored). Bounds in
LSAX-PERFORMANCE-BUDGET.md.

## 5. Verification status

| Claim | Status | Evidence |
|---|---|---|
| Audit counterexamples A (P0-02) and B (P0-03) no longer commit unsafe history | VERIFIED (sim) | `regress_audit_repro.py` runs the auditor's script byte-identical: A → RECONCILE(PENDING_UNKNOWN), B → RECONCILE(UNTRUSTED_PRESENT) |
| Wallet equality never decides a recovery | VERIFIED (sim) | `regress_p0_02_txn_recovery.py`: 432 scenarios (BUY/SELL × 3 wallets × C1/CA/CB/C2 × 5 stop modes × 3 external-cash variants, + after-load variants); decision identical across wallet variants; roll-forward only on own APPLIED evidence + token |
| Unobserved / foreign files never become lineage; legitimate continuation and rollback still anchor | VERIFIED (sim) | `regress_p0_03_save_lineage.py`: 23 cases incl. copied foreign/older/newer, play-time and wallet collisions, forged fingerprint, multiple slots, repeated restart, continuation, rollback, missed start, pre-install, new game |
| Model D keeps LSAX state = effects present in the loaded world, or refuses, under random adversarial histories | VERIFIED (sim) | `journal_timeline_ref.py` (numbers in `evidence/sim/journal_timeline_ref.out.md`), 0 safety-invariant failures, full path coverage |
| RECONCILE frequency acceptable | **OPEN (R-SL-3)** | sim default run (60 episodes per mix × granularity): realistic mix 15.2 % (G = 1 ms) / 16.7 % (G = 1 s) of non-first session starts refuse — driven by the crash-heavy mix (every injected crash lands inside a transaction), pre-install files and forward loads; adversarial 58–60 % |
| Load detection, cash restore, play-time stat, file observability, save events, token semantics | **BLOCKER B-01** | §6 |

## 6. Exact experiment required before SPEC_APPROVED

Run **P-SL-01** (`phase0-probes/shvdn/LsaxPhase0Probe`, passive except for its own decorator; procedure, logs and
cleanup in `phase0-probes/README-PROBES.md`) on the target runtime (GTA V Legacy 1.0.3725.0, ScriptHookVDotNet 3.7.x,
full LSAX target modpack) and once with a minimal setup. **B-01 closes only when PC-1, PC-2, PC-3, PC-4, PC-5,
PC-7 and PC-8 all pass 10/10 on the target runtime**, and P-DB-01 passes. PC-6 is informative.

| PC | Assumption | Pass rule (summary; exact log rows in README-PROBES) |
|---|---|---|
| PC-1 | A-SL-1, A-SL-9 | every load path (pause-menu load, mission-fail load if any, new game, game start) produces a new script-domain CTOR; death/arrest/switch/mission retry-in-place produce none |
| PC-2 | A-SL-6, A-SL-13 | a play-time stat exists; after every load it equals the loaded file's save-time value exactly (bracket from the probe's own polls contains it); non-decreasing within a session through pause, loading, switch, fades, sleep; ≤ 60 000 ms at the first tick of a new game; granularity G recorded |
| PC-3 | A-SL-5 | `SP0/1/2_TOTAL_CASH` after every load equal the save-time values recorded by the probe (all three, incl. non-active protagonists) |
| PC-4 | A-SL-7, A-SL-12, A-SL-4 | every save kind (bed, phone quick-save, mission autosave, autosave) changes exactly one slot file within 2 s and raises the save-event signal within ±2 s of the write; copying/restoring a file raises none; no save file write occurs between the probe's tick-start and tick-end markers |
| PC-5 | A-SL-10 | the token decorator on the player ped survives console `Reload` and script-exception restarts (10/10) and is absent after every load, new game and game restart (10/10 each) |
| PC-6 | A-SL-3 | informative: whether `Aborted` sees pre- or post-load state |
| PC-7 | A-SL-10 | decorator registration succeeds at probe start; set/get round-trips on the player ped; after a character switch the new ped has no token and a re-tag succeeds |
| PC-8 | A-SL-8, A-SL-14 | for every load: exactly one present slot file's probe-recorded fingerprint (bracket + wallets) matches the loaded world; its hash is unchanged at the probe's start; on the full modpack, no wallet change and restore is observed between two consecutive probe ticks |

Also run **P-DB-01** (SQLite load/reload, attach + online backup of the projection DB; R-DB-1/2, D-DB-4).

## 7. Decision table if P-SL-01 fails (every fallback degrades toward refusal, never toward acceptance)

| Failure | Consequence | Pre-agreed fallback |
|---|---|---|
| PC-1 (no domain reload on load) | loads not signalled by SHVDN | poll every 1 s: a token disappearance while running triggers ANCHOR in-session (token loss = session change); requires PC-5/PC-7 |
| PC-2 (no persisted play-time stat / not exact on load) | bracket exclusion unsound | exclusion by wallets only if PC-3 and PC-8 hold; otherwise every token-less start → RECONCILE; re-run sim with the reduced exclusion before any approval |
| PC-3 (cash not restored exactly) | wallet exclusion unsound; money not save-coupled | disable wallet exclusion; re-evaluate money coupling (model C for money) → new sim required |
| PC-4 (no save event / file not observable) | no OBSERVED rows → no positive lineage | persistence BLOCKED (every load refuses) unless P-SL-02 proves an in-save carrier; a carrier stays a DESIGN DECISION conditional on its own probe |
| PC-5/PC-7 (token unreliable) | continuation unprovable | disable continuation: every restart uses hypotheses; same-session restarts refuse (SESSION_UNPROVEN) |
| PC-8 (loaded file not identifiable / transient wallet writes) | hypothesis set not exhaustive or wallet bracket unsound | disable wallet exclusion; if the loaded file can be absent at startup → persistence BLOCKED |

## 8. Decision record (ADR-SL-001, revised in DRAFT2)

- **Context:** §1–§2. No slot identity signal exists (S11). DRAFT1 accepted continuation and PREPARED recovery on
  play-time/wallet correlation (audit P0-02, P0-03).
- **Decision:** Model D "Anchored Timeline" with content-identified save ledger (D-SL-13), session-token
  continuation (D-SL-14), hypothesis-exclusion anchoring (D-SL-15/16), poll brackets (D-SL-17), own-evidence
  transaction recovery (D-TX-4/5), always-fork, RECONCILE_REQUIRED with explicit player resolution.
- **Alternatives rejected:** A (no slot id), C alone (money exploit), B alone (needs the same anchor); DRAFT1
  INFERRED/ghost downtime lineage and wallet evidence (correlation, audit P0-02/P0-03); a STANDARD policy that
  accepts despite unexcludable UNTRUSTED files (correlation); an in-save watermark/carrier (unproven persistence —
  may only be added after P-SL-02 proves it).
- **Consequences:** implementation (after SPEC_APPROVED only) must treat the journal as the source of truth and
  the projection as derived state; the transaction core runs PREPARE/APPLY/COMMIT in one tick (2 fsync'd commits);
  players meet RECONCILE_REQUIRED more often than in DRAFT1 (R-SL-3) and need a resolution UI.
- **Status:** PROPOSED — conditional on B-01 (BLOCKED_RUNTIME_VALIDATION). Owner of the experiment: project owner.
- **Revisit if:** any PC fails (→ §7); P-SL-01 shows play-time granularity > 1 s (re-run sim with the measured G);
  PC-5/PC-7 prove the token also survives character switches (then LIVE can be excluded by token absence — optimisation
  O-SL-1, evaluated only after runtime evidence).

## 9. Assumptions referenced

| ID | Assumption | Closed by |
|---|---|---|
| A-SL-1 | SP save load, new game and game start restart SHVDN's script domain | P-SL-01 PC-1 |
| A-SL-3 | `Aborted` sees post-load game state | P-SL-01 PC-6 (informative; design already safe) |
| A-SL-4 | a save snapshot never interleaves an LSAX tick | source E1-8; P-SL-01 PC-4 tick markers |
| A-SL-5 | `SPx_TOTAL_CASH` restored exactly from the save | P-SL-01 PC-3 |
| A-SL-6 | persisted play-time stat exists, restored exactly on load, non-decreasing within a session | P-SL-01 PC-2 |
| A-SL-7 | save-file writes observable while running; content hash readable | P-SL-01 PC-4 |
| A-SL-8 | GTA loads only profile slot files; the loaded file is unchanged at LSAX's startup scan | P-SL-01 PC-8 |
| A-SL-9 | LSAX is constructed at every script-domain start; a failed start can write MISSED_START | source (ScriptDomain) + P-SL-01 PC-1 |
| A-SL-10 | the session-token decorator survives reloads within a session and never survives load/new game/new process | P-SL-01 PC-5, PC-7 |
| A-SL-12 | every game save raises an observable save event within ±2 s of the file write; a copy raises none | P-SL-01 PC-4 |
| A-SL-13 | a new game starts with play-time ≤ 60 000 ms at LSAX's first tick | P-SL-01 PC-2 |
| A-SL-14 | no other mod changes a wallet and restores it strictly between two LSAX polls | P-SL-01 PC-8 (full modpack) |
| A-ENV-1 | user's SHVDN 3.7.x lifecycle code equals pinned source | P-SL-01 logs version |
