# LSAX — Save/Load Persistence Feasibility & Decision Record

Document: LSAX-SAVELOAD-FEASIBILITY.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

## 0. Status in one paragraph

**BLOCKER B-01 is open.** Phase 0 ran in a Linux container without GTA V, so no GTA runtime signal could be
observed. What *is* established: (1) from pinned SHVDN source, how script lifecycle behaves on a game-session
reload (E1); (2) from the native DB, that **no native exposes a save slot id, generation, checksum or save
timestamp** (E4-4); (3) by an offline simulation with a real SQLite journal, that the selected model's logic
keeps LSAX state equal to the effects present in the loaded world, or refuses, under 3 566 injected crashes
and thousands of loads (E8-5). What is **not** established: the four runtime assumptions A-SL-1, A-SL-5,
A-SL-6, A-SL-7 on which the model depends. The exact experiment that closes B-01 is §6 (probe P-SL-01,
compile-verified, ready to run). Model D is therefore a **DESIGN DECISION conditional on B-01**, not a
verified feasibility.

## 1. Problem statement

GTA V single-player state (per-protagonist cash, garaged vehicles, clock, stats) lives in save files the
player can reload at any time. LSAX state (vehicle identity, history, ownership, listings, transactions,
Heat) lives in LSAX's own SQLite database. Loading an earlier save rewinds GTA but not the database. Without a
synchronisation model:

- buy via LSAX (cash −), load earlier save (cash restored) → LSAX believes the player owns the car: **free car**;
- sell via LSAX (cash +), load earlier save → car and cash both restored in GTA, LSAX believes it is sold;
- mid-transaction crash → money moved but ownership not recorded, or vice versa.

## 2. Signal inventory (what exists, with evidence labels)

| # | Signal | Evidence | Label | Used by model D as |
|---|---|---|---|---|
| S1 | SHVDN reloads the whole script domain when ScriptHookV starts a new script fiber ("game creates a new session"); `Aborted` handlers run, then constructors run again | `DllMain.cpp` ScriptMain/ClrThreadProc; `ScriptDomain.cs` Unload/Abort (E1-1, E1-2) | VERIFIED (source) | session-start trigger |
| S2 | Whether SP **save load** makes ScriptHookV start a new fiber | closed-source ScriptHookV | ASSUMPTION A-SL-1 | — (PC-1) |
| S3 | Console `Reload`/reload key trigger the same domain reload | `DllMain.cpp` (E1-3) | VERIFIED (source) | must be distinguishable → stop marker |
| S4 | `Aborted` runs after the new session started | code ordering (E1-4) | VERIFIED (source); timing ASSUMPTION A-SL-3 | never read game state in `Aborted` |
| S5 | Scripts start only after the loading screen (SHV ≥ 1.0.3351.0) | `Game.Obsolete.cs` (E1-6) | VERIFIED (source note + version order) | constructor sees loaded world |
| S6 | `SP0/1/2_TOTAL_CASH` via `STAT_GET_INT` (what `Player.Money` reads) | `Player.cs` (E2-1) | VERIFIED (source) | wallet vector |
| S7 | Cash restored from the save on load | common knowledge only | ASSUMPTION A-SL-5 | anchor discriminator (PC-3) |
| S8 | A persisted, monotonic play-time stat exists | none; candidate names only | ASSUMPTION A-SL-6 | primary anchor coordinate (PC-2) |
| S9 | Save files `Documents/Rockstar Games/GTA V/Profiles/<id>/SGTA*` change when GTA saves | none in Phase 0 | ASSUMPTION A-SL-7 | save-slot ledger (PC-4) |
| S10 | `IS_AUTO_SAVE_IN_PROGRESS`, `GET_STATUS_OF_MANUAL_SAVE`, `HAS_CODE_REQUESTED_AUTOSAVE`, `GET_SAVE_HOUSE_DETAILS_AFTER_SUCCESSFUL_LOAD` exist | native DB + Hash enum (E4-1) | VERIFIED (existence only; semantics unknown) | corroboration only (R-SL-4) |
| S11 | Save slot id / generation / checksum / save timestamp natives | name scan of 101 save-related natives (E4-4) | VERIFIED **absent** | not usable |
| S12 | `GET_GAME_TIMER` across load | unknown | not assumed | not used for anchoring |
| S13 | SHVDN main-thread blocking while scripts run → one LSAX tick is not interleaved with a GTA save snapshot | `DllMain.cpp` comment/code (E1-8) | VERIFIED (source); ASSUMPTION A-SL-4 at runtime | single-tick transaction core |

## 3. Candidate models

| Model | Mechanism | Needs | Evidence verdict | Decision |
|---|---|---|---|---|
| **A** Save-scoped DB (one LSAX DB per GTA save slot) | swap DB file with the slot | the loaded slot id at load time | S11: no slot id native; file access does not reveal which file was *read* | **Rejected** — not implementable without a slot-id signal |
| **B** Snapshot/rollback | snapshot LSAX DB at each GTA save; restore snapshot on load | know which save was loaded → same problem as A; storage × saves | needs an anchor; snapshots redundant with a journal | **Subsumed** into D (rewind = branch, no copies) |
| **C** Independent DB + reconciliation | LSAX never rewinds; reconcile entities that "reappear" | reliable detection of each divergence per entity | money is save-coupled (S6/S7): LSAX-only ledger would allow buy-reload exploits; per-entity reconciliation cannot see cash | **Rejected alone** (unsafe for money) |
| **D** Anchored Timeline (hybrid) | independent append-only journal (C) organised as a tree of timelines; each session start anchors the loaded world to a journal position via a passive fingerprint + save-slot ledger; rewind = new branch (B without copies); ambiguity → refuse | S1/S2 or polling, S6/S7, S8, S9, S13 | logic VERIFIED (sim, E8-5); runtime assumptions open | **Selected, conditional on B-01** |

## 4. Model D — normative specification

### 4.1 Concepts

- **Campaign** — one GTA story playthrough as seen by LSAX (root timeline).
- **Timeline** — a branch of LSAX history. Row: `parent_txn` (last included commit; NULL = campaign start),
  `fork_p` (play-time at fork), `last_p`, `reason ∈ {ROOT, ANCHOR, DOWNTIME, RECOVERY}`.
- **Commit** — one committed LSAX logical transaction on a timeline: `(timeline_id, seq, txn_id, idem_key,
  wallet_before[3], wallet_after[3], p_ms, domain events)`.
- **Path(t)** — commits of t's ancestors up to each fork point, then t's own. Play-time is non-decreasing
  along every path (guaranteed by D-SL-5).
- **Fingerprint F** — `(P, W)`: P = persisted play-time stat (ms, granularity G), W = wallet vector
  `(SP0_TOTAL_CASH, SP1_TOTAL_CASH, SP2_TOTAL_CASH)`. The simulation uses one wallet; production uses the
  vector (strictly more discriminating). Also recorded: player model, GTA process id + start time, wall time.
- **Save-slot ledger** — per save file, the observation of its **current** content (D-SL-3):
  `(slot file, mtime, size, sha256, mode ∈ {OBSERVED, INFERRED, FOREIGN}, timeline, p_lo, p_hi, W?, pending_txn?)`.
- **Stop marker** — flushed from memory in `Aborted` (clean stop): last-tick P, last **known** wallet
  vector (includes LSAX's own writes in that tick, D-SL-8), wall time, process id. Heartbeat (every 3 s of
  play-time) persists `last_p/last_w` for unclean stops.
- **Ghost timeline** — per LSAX downtime window, forked at the last known head; hosts unobserved saves.

### 4.2 Ledger maintenance (while LSAX runs)

- Poll save-file metadata every 2 s wall and immediately before every transaction apply (≤ 16 files; bounded).
- A changed file observed while running → `OBSERVED(timeline=active, p_lo=P−2500, p_hi=P, W=current)` —
  only if a save-event signal was seen within the correlation window (R-SL-4; until P-SL-01 proves the flag
  semantics, the rule is logged but not enforced, and the FOREIGN path is manual).
- A file whose metadata changed while LSAX was down → at next start `INFERRED(timeline=ghost,
  p_lo=stop_p, p_hi=stop_p + (file_mtime − stop_wall) + 2000, W=unknown, pending_txn=unresolved txn or NULL)`
  (play-time cannot outrun wall time).

### 4.3 Anchoring algorithm (normative; mirrors `phase0-probes/sim/journal_timeline_ref.py::anchor`)

```
ANCHOR(at every LSAX session start; also on in-session discontinuity: P decreases, or W changes without an
       LSAX/observed cause while P jumps):
  read F=(P,W) in the first tick; base = stop marker if clean else heartbeat; down = wall_now - base.wall
  pending = transactions in state PREPARED (≤ 1 by construction)
  if save files changed since last observation: create ghost timeline(parent=head, fork_p=base.p);
      attach them as INFERRED (window per 4.2, pending_txn = pending.id)
  candidates = {}
  for each ledger entry whose file is unchanged since observation and p_lo ≤ P ≤ p_hi
                                 and (INFERRED or entry.W == W):
      k = KEY_AT(entry.timeline, P, W)
      if entry.pending_txn: resolve with wallet evidence: W == after ≠ before → k += txn (APPLIED);
                            W == before → NOT_APPLIED; else → TAINTED
      candidates += k
  continuation = same GTA process ∧ base.p ≤ P ≤ base.p + down + 2000
                 ∧ (down > 10 s ∨ W == base.W ∨ W == pending.after)
  if continuation: candidates += FULL_PATH(active) (+ pending txn by the same wallet evidence)
  if TAINTED                → RECONCILE_REQUIRED(TAINTED)
  if candidates = ∅         → RECONCILE_REQUIRED(NO_MATCH)       -- new game, pre-LSAX or foreign save
  if |distinct states| ≠ 1  → RECONCILE_REQUIRED(AMBIGUOUS)
  resolve pending (TRANSACTION-STATE-MACHINE §7); an APPLIED pending commit is stamped p_prepare and
      hosted on the ghost (or a RECOVERY timeline)
  ALWAYS fork a new active timeline at the anchored state (parent = last txn of the state, fork_p = P)
  if exactly one non-ghost slot explained the world: pin it (INFERRED → OBSERVED with exact P, W)

KEY_AT(t, P, W): commits on Path(t) with p < P, plus the unique prefix of commits with p == P (same
  granule) whose expected wallet equals W; if not exactly one prefix fits → ambiguous.
```

### 4.4 What is timeline-coupled

| Timeline-coupled (rewinds with the save) | Global (never rewinds) |
|---|---|
| vehicle identity registrations, ownership, provenance, odometer/condition checkpoints, modification snapshots, history events, listings, offers, negotiations, market inventory & indices, Heat, mail messages, LSAX-held balances (none planned), market RNG counters | configuration, catalogue, localisation, logs, the journal itself (all branches kept for audit), anti-exploit audit trail, save-slot ledger, schema/migration state |

Rationale: everything the player could exploit by reloading is coupled to the same save the money comes from;
deterministic seeding (NPC generation, market events) is keyed on timeline position, so reloading does not
re-roll outcomes (LSAX-NPC-GENERATION-MODEL.md §2).

### 4.5 Odometer and other high-frequency state

Odometer/condition are integrated in memory and checkpointed as journal events at bounded cadence (every
≥ 1 km or ≥ 60 s of driving, and at every lifecycle checkpoint). A rewind restores the last checkpoint at or
before the anchor; maximum loss is one checkpoint interval (≤ 1 km). Documented, not hidden.

### 4.6 RECONCILE_REQUIRED

Entered only by §4.3. Effects: all market/transaction/ownership operations refused with a localised reason;
tracking continues read-only (odometer integrates in memory, is not committed); the projection is untouched
(sim invariant I6); the debug inspector (Stage 1) lists candidate states with their evidence. Exit only by an
explicit player action: choose a listed candidate, or start a **new LSAX campaign** for this world.
Auto-selection is forbidden (mandatory invariant 4).

### 4.7 Why "new campaign" is safe for NO_MATCH

A new campaign has an empty LSAX state. Vehicles present in the world are then unregistered (UNKNOWN
provenance, LSAX-DOMAIN-MODEL.md §5), which can reduce value (they need title verification) but can never
duplicate it. Money is untouched: LSAX never credits cash on anchoring.

### 4.8 Retention

All timelines are kept (audit). Orphaned branches older than 30 MT days and not referenced by any current
ledger entry are compacted into a summary row (count, value moved) after 1 000 orphaned commits; compaction is
itself a journaled maintenance operation. Bounds in LSAX-PERFORMANCE-BUDGET.md.

## 5. Verification status

| Claim | Status | Evidence |
|---|---|---|
| Model D logic keeps LSAX state = effects present in the loaded world, or refuses | VERIFIED (sim) | E8-5: 800 episodes, 3 566 crashes (C0–C3), 9 815 successful anchorings, 422 roll-forwards, 1 190 evidence aborts, **0 safety-invariant failures** |
| RECONCILE frequency acceptable | OPEN (R-SL-3) | sim 2.0–3.0 % (realistic mix, still ~4 crashes/episode), 3.8–4.3 % adversarial |
| Load detection, cash restore, play-time stat, file observability | **BLOCKER B-01** | §6 |
| Model sensitive to stat granularity | characterised | RECONCILE 3.8 % (1 ms) vs 4.3 % (1 s), adversarial |

The simulation passed only after five sim-driven corrections (decisions D-SL-2, D-SL-8…D-SL-11, D-TX-1) and one
detected vacuous pass. They are listed so the auditor can judge whether other corner cases remain.

## 6. Exact experiment required before Stage 1 persistence work

Run **P-SL-01** (`phase0-probes/shvdn/LsaxPhase0Probe`, passive, no game-state writes) on the target PC with the
full modpack and a minimal setup, following `phase0-probes/README-PROBES.md` steps T1–T13. **B-01 closes when
PC-1…PC-5 all pass 10/10.** Also run **P-DB-01** (SQLite load/reload, R-DB-1/2). P-SL-02 and P-ID-01 are optional.

## 7. Decision table if P-SL-01 fails

| Failure | Consequence | Pre-agreed fallback |
|---|---|---|
| PC-1 (no domain reload on load) | loads not signalled by SHVDN | poll F every 1 s; a decrease of P or a W change not explained by LSAX/observed saves triggers ANCHOR in-session. Requires PC-2. |
| PC-2 (no persisted monotonic play-time stat) | no primary coordinate | **F1**: P-SL-02 watermark stat (LSAX writes last commit seq into a proven-safe SP stat; anchor = exact seq). If no safe stat: **F2**: coordinate = (W, GTA clock date-time, player model), expect higher RECONCILE; re-run sim with that coordinate before Stage 1. |
| PC-3 (cash not restored) | money is not save-coupled | re-evaluate: money-coupled state becomes global (model C for money), ownership stays timeline-coupled → new sim required. |
| PC-4 (save files not observable) | no ledger | configurable profile path; if still impossible → F2 with "every load = RECONCILE unless W+clock match exactly one known observation" (strict mode). |
| PC-5 (cannot tell console reload from load) | continuation mis-detected | stop marker already distinguishes (wallet + P window); if insufficient, disable continuation (every restart anchors via ledger only). |

## 8. Decision record (ADR-SL-001)

- **Context:** §1–§2. No slot identity signal exists (S11).
- **Decision:** Model D "Anchored Timeline" with passive fingerprint (play-time stat + wallet vector), save-slot
  ledger, stop markers, ghost timelines, always-fork, evidence-only transaction recovery, RECONCILE_REQUIRED on
  zero/multiple candidates. Decisions D-SL-1…D-SL-12, D-TX-1…D-TX-3.
- **Alternatives rejected:** A (no slot id), C alone (money exploit), B alone (needs the same anchor; storage).
- **Consequences:** Stage 1 must implement the journal as the source of truth and the projection as derived
  state; the transaction core runs PREPARE/APPLY/COMMIT in one tick (2 fsync'd commits); players may meet
  RECONCILE_REQUIRED after unusual crash/load sequences and need a resolution UI.
- **Status:** PROPOSED — conditional on B-01. Owner of the experiment: project owner (target PC).
- **Revisit if:** any PC fails (→ §7), or P-SL-01 shows the play-time stat has granularity > 1 s (re-run sim with
  the measured granularity).

## 9. Assumptions referenced

| ID | Assumption | Closed by |
|---|---|---|
| A-SL-1 | SP save load (pause menu, mission retry, `SHUTDOWN_AND_LOAD_MOST_RECENT_SAVE`) restarts SHVDN's domain | P-SL-01 PC-1 (or polling fallback) |
| A-SL-3 | `Aborted` sees post-load game state | P-SL-01 PC-6 (informative; design already safe) |
| A-SL-4 | a save snapshot never interleaves an LSAX tick | source E1-8; not directly probed |
| A-SL-5 | `SPx_TOTAL_CASH` restored from the save | P-SL-01 PC-3 |
| A-SL-6 | persisted monotonic play-time stat exists | P-SL-01 PC-2 |
| A-SL-7 | save-file writes observable while running | P-SL-01 PC-4 |
| A-ENV-1 | user's SHVDN 3.7.x lifecycle code equals pinned source | P-SL-01 logs version |
