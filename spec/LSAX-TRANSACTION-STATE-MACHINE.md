# LSAX — Transaction Core: State Machine, Journal, Idempotency, Recovery

Document: LSAX-TRANSACTION-STATE-MACHINE.md · Spec: LSAX MASTER SPEC v1.0 DRAFT2 · Status: DRAFT for independent re-audit

Designed **before** any marketplace (invariant 11). The logical commit covers **money + ownership + vehicle
state + market state** (invariant 12). Physical handover is a later world adapter over this core. The protocol
and its recovery rules are VERIFIED (sim) by `phase0-probes/sim/journal_timeline_ref.py` and the deterministic
regressions `phase0-probes/regress/regress_p0_02_txn_recovery.py` / `regress_audit_repro.py` under the runtime
assumptions of B-01. DRAFT2 (audit P0-02): recovery uses only LSAX's own evidence; wallet values are never causal
proof (D-TX-4, D-TX-5).

## 1. Invariants

| ID | Invariant | Enforced by |
|---|---|---|
| TX-I1 | All LSAX-side effects of a transaction commit in one SQLite transaction; all money-coupled game-side effects are applied in the same game tick as that commit | §4 single-tick core |
| TX-I2 | An idempotency key commits at most once on the active timeline path; a replay returns the stored outcome with no effect | `idem_key` check at PREPARE and COMMIT (§5) |
| TX-I3 | No double sale: a vehicle has ≤ 1 live reservation; COMMIT requires the reservation to be held by this txn and the seller to still own the vehicle | reservation table PK(vehicle_id) |
| TX-I4 | No double payment: the wallet is re-read and must equal `cash_before` immediately before apply; after a crash a PREPARED transaction is rolled forward **only** on LSAX's own flushed `APPLIED` status within a token-proven same session — never on wallet values | §4 step 4, §7 |
| TX-I5 | No ownership transfer without economic commit, and no money movement without ownership commit | both in one COMMIT (TX-I1) |
| TX-I6 | No stale acceptance: offer version, listing version and vehicle state hash checked at PREPARE; expiry checked in MT | §6 |
| TX-I7 | Crash/reload never duplicates or fabricates: recovery only by positive evidence (§7); otherwise RECONCILE_REQUIRED | anchor + recovery |
| TX-I8 | While RECONCILE_REQUIRED, every new transaction is refused | gate at PREPARE |
| TX-I9 | Every external world action is bounded by timeout + retry budget + fallback + abort/rollback (invariant 10) | §9 |

## 2. Identifiers

- **TransactionId** — 128-bit random, text form `tx_<26 base32>`. Unique across campaigns.
- **IdempotencyKey** — deterministic from intent: `KIND|actor|subject ids|version` — e.g.
  `LEGAL_BUY|SP1|listing:LS-9F2…|v7`, `ACCEPT_OFFER|SP0|offer:…|v3`, `DEALER_SELL|SP2|veh:…|state:<hash16>`,
  `LISTING_FEE|SP0|listing:…`. The same user intent always yields the same key; a changed version is a new intent.
- **Reservation** — `(vehicle_id | listing_id | offer_id) → txn_id`, unique per subject.

## 3. Transaction kinds (initial set)

| Kind | Money (acting protagonist) | Ownership | Vehicle state | Market state |
|---|---|---|---|---|
| `LEGAL_BUY` | − price − transfer tax | NPC/Dealer → protagonist | registration, LSAX plate, title CLEAN/SALVAGE | listing SOLD, competing offers VOID |
| `ACCEPT_OFFER` (player sells to NPC) | + price − commission | protagonist → NPC | released from binding; lifecycle per delivery | listing SOLD, other offers VOID |
| `DEALER_SELL` (instant) | + dealer acquisition value | protagonist → Dealer | — | any listing WITHDRAWN |
| `LISTING_CREATE` | − listing fee | — | — | listing ACTIVE |
| `LISTING_WITHDRAW` | refund only if system-cancelled | — | — | listing WITHDRAWN |
| `UG_SELL` (fence/chop/export/collector) | + underground value | protagonist → Underground party | lifecycle RETIRED (chop/export) or stays | — ; Heat events |
| `UG_BUY` | − price | Underground → protagonist | title UNDERGROUND | — ; Heat events |
| `TITLE_VERIFY` | − fee | — | title UNKNOWN → CLEAN or STOLEN | — |
| `SERVICE_PAY` (LSAX service/rebuild) | − cost | — | condition/history | — |
| `REFUND` (compensation) | + amount of a named committed txn | reverse of named txn | reverse where defined | reverse where defined |
| `REGISTER_VEHICLE`, `OFFER_CREATE`, `OFFER_COUNTER`, `OFFER_EXPIRE` | none | none / — | registration | offer rows |

Money-neutral kinds cannot use the wallet as recovery evidence; they carry **no game-side effect** by design, so
they are pure DB transactions (crash → either committed or not, no ambiguity).

## 4. Single-tick atomic core (normative, D-TX-1)

All steps run in **one LSAX tick** on the script thread:

1. **Gate:** not RECONCILE_REQUIRED; acting party has a defined wallet (protagonist model); no pending PREPARED txn.
2. **Precommit validation** (§6) against the current projection; idempotency check. Failure → `REJECTED`
   (audit log only, nothing durable in the journal).
3. **PREPARE** (synchronous SQLite commit): txn row `state=PREPARED`, **`apply_status=APPLYING`** (durable
   pessimistic default: "LSAX may be inside the apply"), `idem_key`, `kind`, parties, subjects, `wallet_slot`,
   `wallet_before`, `wallet_after`, fees, `p_prepare` (play-time stat), `mt`, `prev_txn` (head of active path),
   planned domain events; reservation rows. In memory: `apply_status = NOT_STARTED`.
4. **Poll saves, verify & apply game side:** poll the save slots (a save observed here predates the apply,
   SAVELOAD §4.2); re-read the acting wallet (`STAT_GET_INT SPx_TOTAL_CASH`); if ≠ `wallet_before` → ABORT (another
   script changed cash in between; R-ECO-1). Else in memory `apply_status = APPLYING`, write `wallet_after`
   (`STAT_SET_INT`), read back; mismatch → write `wallet_before` back, read back, ABORT. Apply other in-tick
   game-side effects (e.g. set plate on an already-bound vehicle). In memory `apply_status = APPLIED`; restart the
   save-poll wallet bracket (D-SL-17).
5. **COMMIT** (synchronous SQLite commit): commit row on the active timeline (`seq`, `p_ms = p_prepare`, `mt`),
   projection updates (ownership, title, vehicle state, listing/offer state, fees ledger, Heat events), txn
   `state=COMMITTED`, `apply_status=APPLIED`, reservation rows deleted. Emit mail/notification requests (after
   commit only).
6. **COMMIT failure after a successful apply (D-TX-5):** compensate in the same tick — write `wallet_before` back,
   undo the other in-tick effects, read back — then durably ABORT. If compensation or the ABORT write fails, LSAX
   enters **FAULT**: it stops observing saves (no ledger rows can be written while the world holds an unrecorded
   apply), refuses every operation, and keeps the durable `APPLYING` status so the next start resolves it as
   unknown. Hence every TRUSTED save predates any unrecorded apply.
7. **In `Aborted`** (clean stop): flush the in-memory `apply_status` of the PREPARED transaction (NOT_STARTED /
   APPLYING / APPLIED) — LSAX's own knowledge, no game-state read (D-SL-7).

Cost: 2 fsync'd SQLite commits per transaction tick; budget ≤ 25 ms p95 (R-DB-2; P-DB-01 measures). Transactions
are rare events (player actions, market resolutions), never per frame.

```mermaid
stateDiagram-v2
  [*] --> CREATED: intent (UI/debug/market/system)
  CREATED --> REJECTED: gate or validation fails
  CREATED --> PREPARED: durable PREPARE (apply_status=APPLYING)
  PREPARED --> ABORTED: wallet mismatch / apply failed and restored / COMMIT failed and compensated
  PREPARED --> APPLIED: game effects written & verified (in memory, same tick)
  APPLIED --> COMMITTED: durable COMMIT (same tick)
  APPLIED --> FAULT: COMMIT and compensation failed
  PREPARED --> COMMITTED: recovery: token-proven session + own flushed APPLIED (roll forward, stamped p_prepare)
  PREPARED --> ABORTED: recovery: own NOT_STARTED, or world anchored to a save that predates the apply
  PREPARED --> RECONCILE_REQUIRED: recovery: APPLYING / unflushed / unproven session
  RECONCILE_REQUIRED --> COMMITTED: explicit player choice "completed"
  RECONCILE_REQUIRED --> ABORTED: explicit player choice "not completed" / other state / new campaign
  COMMITTED --> [*]
  ABORTED --> [*]
  REJECTED --> [*]
```

## 5. Idempotency and replay

- PREPARE and COMMIT both reject if a commit with the same `idem_key` exists on the **active path**; the stored
  outcome (txn id, amounts) is returned as `DUPLICATE`.
- A key orphaned by a rewind (its commit lies on an abandoned branch) is **not** on the active path and may commit
  again — the loaded world never saw it (D-TX-3).
- UI double-clicks, repeated key events, message re-delivery and retries after a crash all map to the same key.

## 6. Precommit validation (per kind, all must pass)

Common: acting party wallet defined; `wallet ≥ total debit`; subject rows exist on the active projection; no
reservation held by another txn; identity of any involved world vehicle currently **Bound** with confidence ≥ 85
(never Ambiguous); vehicle lifecycle ∈ {ACTIVE, DORMANT, VIRTUAL} as required; not a mission/script-owned vehicle;
not `GAME_RESPAWN_OF_SOLD` / `CLONE_SUSPECT`.
Legal market: title ∈ {CLEAN, SALVAGE, RECOVERED, LEGACY}; listing `ACTIVE`, `listing.version` = expected;
offer `ACTIVE`, `offer.version` = expected, `offer.expires_mt > MT_now`; buyer budget ≥ price.
Seller side: seller owns the vehicle; vehicle state hash (odometer bucket, condition bucket, mods hash) equals the
hash the offer was made against, else the offer is `STALE` (buyer must re-evaluate).
Underground: access unlocked; Heat rules allow the counterparty (LSAX-HEAT-AND-UNDERGROUND-MODEL.md); daily caps.

## 7. Recovery (at every anchoring)

Resolution of a PREPARED transaction during the anchoring of LSAX-SAVELOAD-FEASIBILITY.md §4.3 (D-TX-4). The inputs
are only LSAX's own durable `apply_status` (flushed in `Aborted`; `APPLYING` if no flush happened) and how the
session was established. **Wallet values are never an input.**

**Table A — continuation (session token on the player ped equals the stored token: same live session proven):**

| Own `apply_status` | Verdict |
|---|---|
| `NOT_STARTED` (crash after PREPARE, before the apply began; clean stop) | **ABORT**, release reservations |
| `APPLIED` ∧ `prev_txn` = active head (crash after the apply was verified, before COMMIT; clean stop) | **ROLL FORWARD**: COMMIT with `p_ms = p_prepare` |
| `APPLYING` (crash inside the apply, or any unclean stop — no flush) | **RECONCILE_REQUIRED(PENDING_UNKNOWN)**; candidates "completed" / "not completed" |

**Table B — no session token (load, new game, new process, or token lost):**

| Outcome of hypothesis exclusion (SAVELOAD §4.3) | Verdict |
|---|---|
| accepted state from a content-identified save file (LIVE excluded, or LIVE agrees with pending `NOT_STARTED`) | **ABORT**: every TRUSTED save predates any unrecorded apply (single-tick core + D-TX-5 FAULT rule), so the loaded world does not contain it |
| LIVE hypothesis remains with pending `APPLIED`/`APPLYING` | **RECONCILE_REQUIRED** (AMBIGUOUS / SESSION_UNPROVEN / PENDING_UNKNOWN) |
| any other refusal | **RECONCILE_REQUIRED**; the pending transaction stays PREPARED until the player resolves |

Resolution of RECONCILE_REQUIRED is an explicit player choice among the listed candidates (`R:txn` commits the
pending transaction stamped `p_prepare`; `H:head` or new campaign aborts it). Retry after ABORT uses the same
idempotency key (the intent never committed); replay after COMMIT returns `DUPLICATE` (§5).

Stale cleanup: reservations exist only inside one tick for the core; a reservation found at startup always belongs
to a PREPARED txn and is resolved by the tables above. Multi-tick **deal holds** (§8) carry `expires_mt` and
`expires_at_session`; they are released by the market step (every 60 MT min) or at session start.

## 8. Deals: multi-tick orchestration around the core

Physical interactions (meet, inspect, hand over, deliver) are a **Deal** state machine that calls the atomic core
exactly once.

```mermaid
stateDiagram-v2
  [*] --> NEGOTIATED
  NEGOTIATED --> SCHEDULED: meeting agreed (hold on listing + vehicle, expires_mt)
  SCHEDULED --> MEETING: player arrives (world scene starts)
  MEETING --> INSPECTION
  INSPECTION --> COMMITTING: both sides accept
  COMMITTING --> DELIVERY: atomic core COMMITTED
  COMMITTING --> CANCELLED: atomic core REJECTED/ABORTED
  DELIVERY --> CLOSED: delivery done or fallback storage
  MEETING --> INTERRUPTED: timeout / player left / wanted level observed / ped died
  INSPECTION --> INTERRUPTED
  INTERRUPTED --> SCHEDULED: retry budget left
  INTERRUPTED --> CANCELLED: budget exhausted (no money moved)
  SCHEDULED --> EXPIRED: expires_mt passed
  DELIVERY --> DELIVERY_PENDING: session ended / scene failed
  DELIVERY_PENDING --> DELIVERY: retry
  DELIVERY_PENDING --> CLOSED: fallback (vehicle to LSAX storage pickup)
```

Pre-commit states can always be cancelled without money movement ("rolled back" = never committed). Post-commit
failures never un-commit; they complete through fallback or a `REFUND` compensation transaction with key
`REFUND|<txn_id>` (idempotent).

## 9. External world actions — bounds (normative; AT = active session time)

| Action | Timeout | Retry budget | Fallback | Abort / rollback |
|---|---|---|---|---|
| Model request (`REQUEST_MODEL`/`HAS_MODEL_LOADED`) | 5 s | 3 | — | pre-commit: cancel deal; post-commit: deliver to storage |
| Spawn delivered vehicle | 10 s | 2 | LSAX storage pickup (virtual) | n/a (post-commit) |
| NPC buyer/seller arrival | 180 s | 1 (respawn closer, off-screen) | "no-show" message | cancel deal, release hold |
| Walk-up / greeting task | 30 s | 1 | teleport ped off-screen to mark (not in view) | cancel deal |
| Handover synchronised scene | 30 s | 1 | skip animation, fade | if player > 150 m away or wanted level > 0 observed → cancel (pre-commit) |
| Inspection walkaround | 60 s | 0 | static inspection report | none (informative) |
| Buyer drives away with sold car | 120 s | 0 | despawn when > 200 m and not visible, or at timeout | none (post-commit, entity LSAX-owned) |
| Any LSAX-spawned entity | lifetime ≤ deal lifetime | — | `SET_ENTITY_AS_NO_LONGER_NEEDED` | registry cleanup |

LSAX-spawned entities live in a bounded registry (≤ 16 concurrent peds + vehicles + props). **LSAX never deletes
entities by handle inside `Aborted`** (the handle may belong to the new session, E1-4; the reference mod SellCars does
this, R9). Instead, at the next start, a bounded sweep deletes only entities carrying the current-session ownership
decorator that are not occupied by the player; everything else is released with `SET_ENTITY_AS_NO_LONGER_NEEDED`.
DESIGN DECISION D-WORLD-2.

## 10. Interruption / recovery matrix (appendix, normative)

Crash points: C0 inside the PREPARE commit; C1 after PREPARE (`NOT_STARTED`); CA after `APPLYING`, before the
native write; CB after the native write, before `APPLIED` is recorded; C2 after `APPLIED`, before COMMIT; C3 after
COMMIT. "Clean" = `Aborted` flush ran; "unclean" = it did not. External cash writes by other mods may land on any
value, including exactly `wallet_before` or `wallet_after` — they change no verdict below.

| Interruption | C0 | C1 | CA / CB | C2 | C3 |
|---|---|---|---|---|---|
| Script exception / console reload, same session, clean | nothing durable; intent lost | token → **ABORT** | token → **RECONCILE(PENDING_UNKNOWN)** | token → **ROLL FORWARD** | consistent |
| Same session, unclean (no flush) | nothing | token → RECONCILE(PENDING_UNKNOWN) | RECONCILE(PENDING_UNKNOWN) | RECONCILE(PENDING_UNKNOWN) | consistent |
| LSAX down in the session, trainer/other-mod cash writes, console reload (token intact) | nothing | ABORT | RECONCILE(PENDING_UNKNOWN) | ROLL FORWARD | consistent |
| LSAX down, character switched (token lost), console reload | nothing | RECONCILE(SESSION_UNPROVEN) | RECONCILE(SESSION_UNPROVEN) | RECONCILE(SESSION_UNPROVEN) | RECONCILE(SESSION_UNPROVEN) |
| Game crash, then load of a TRUSTED save made before the tick | nothing | **ABORT** | **ABORT** | **ABORT** | rewind: commit orphaned (world lacks it) — consistent |
| In-session load of an older TRUSTED save | nothing | ABORT | ABORT | ABORT | rewind; orphaned commit; key may be re-used |
| Load of a save written while LSAX was down (after the apply) | — | RECONCILE(UNTRUSTED_PRESENT) | RECONCILE(UNTRUSTED_PRESENT) | RECONCILE(UNTRUSTED_PRESENT) | — |
| Save written between PREPARE and apply | impossible (same tick, A-SL-4) | impossible | impossible | impossible | — |
| COMMIT write fails after apply | — | — | — | compensate + ABORT, else FAULT (step 6) | — |
| Deal interrupted before COMMITTING | no money moved; deal → INTERRUPTED/CANCELLED | | | | |
| Deal interrupted in DELIVERY | money committed; DELIVERY_PENDING → retry → storage fallback | | | | |

Every row is exercised by `regress_p0_02_txn_recovery.py` (exhaustive over direction × wallet × crash point × stop
mode × external-cash value) and by the random crash injection of `journal_timeline_ref.py`; no row produced a
safety-invariant failure.
