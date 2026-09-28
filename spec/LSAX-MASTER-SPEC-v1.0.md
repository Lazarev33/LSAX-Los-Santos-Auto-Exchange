# LSAX — Los Santos Auto Exchange · MASTER SPEC v1.0 DRAFT 1

Status: **DRAFT 1 for independent READ-ONLY audit. Not SPEC_APPROVED** (the author does not grant approval; see
Appendix L — one gate item is FAIL: BLOCKER B-01).
Runtime target: GTA V Legacy 1.0.3725.0 · ScriptHookVDotNet 3.7.x · C# / .NET Framework 4.8.
Date: 2026-09-28. Evidence base: `feasibility.md` (E0–E8), `decisions.md`, `risks.md`, `evidence/`, `phase0-probes/`.

Evidence labels used throughout: **VERIFIED FEASIBILITY** (qualified as *source*, *compile*, *sim* or *runtime* —
nothing in Phase 0 is *runtime*), **DESIGN DECISION**, **ASSUMPTION**, **OPEN RISK**, **BLOCKER**.

---

## 00 Overview & Scope

LSAX is a new GTA V Legacy mod, written from scratch, simulating a persistent used-vehicle ownership and trading
world with two markets: a **legal white market** (Avito/Auto.ru/mobile.de-like) and an **underground market** for
stolen/illicit vehicles with separate buyers, valuation, Heat and risk. It simulates *specific* vehicles: identity,
mileage, condition/wear, accident/service/owner/modification history, legal provenance, valuation, NPC market,
listings/offers/counter-offers, mail/notifications, and later physical inspection/handover.

**Architecture (DESIGN DECISION D-ARCH-1):**

```
LSAX.Core (netstandard2.0, pure: domain, valuation, Heat, generation, transaction rules, MessageRef)
   ▲ ports: IWorldPort, IWalletPort, IClockPort, ISaveLedgerPort, IPersistencePort, ILocalizer, IUiRenderer
LSAX.Persistence (SQLite journal/projection/migrations)   LSAX.Localization (JSON, ICU subset)
LSAX.Adapters.Shvdn (net48: natives, entity scans, wallet, clock, save-file ledger)
LSAX.Ui.<Renderer> (chosen by UI-S1; Core never references it)   LSAX.Diagnostics (log, inspector)
```

**Phase 0 result summary**

| Area | Result |
|---|---|
| Save/load synchronisation | Model D "Anchored Timeline" selected; logic VERIFIED (sim) with 0 safety failures in 800 crash/load episodes; runtime assumptions unproven → **BLOCKER B-01** with an exact, compile-verified probe (P-SL-01) |
| GTA/SHVDN capabilities | lifecycle, money API, decorators, assembly loading VERIFIED (source) at SHVDN@56ba3bf; 100+ natives verified to exist; absence of any save-slot-id native VERIFIED |
| Maths | valuation, NPC generation, Heat: integer-deterministic reference models VERIFIED (sim) |
| Transaction core | single-tick PREPARE/APPLY/COMMIT with evidence-only recovery, VERIFIED (sim) |

Reading guide: this file is normative for cross-cutting rules and indexes the companion documents, which are
normative for their domains.

## 01 Glossary

| Term | Definition |
|---|---|
| Anchoring | Matching the loaded GTA world to one LSAX journal state at session start (SAVELOAD §4.3) |
| AT | Active Session Time: clamped, pause-excluded ms of this session (TIME §2.1) |
| AV / BUV / CAV / FMV | Adjusted / Base Used / Condition-Adjusted / Fair Market Value (VALUATION §1) |
| Binding | In-memory link handle → VehicleId with continuity checks; never persisted as identity |
| bp | basis point, 10 000 bp = 1.0 |
| Campaign | One GTA story playthrough as seen by LSAX; root of a timeline tree |
| Commit | A committed LSAX logical transaction recorded on a timeline with its domain events |
| Continuation | Anchoring outcome "the world went on from LSAX's last known state" (no load) |
| Deal | Multi-tick orchestration (meeting, inspection, delivery) around exactly one atomic transaction |
| Decorator hint | Per-session int token on an entity for fast re-identification; never identity |
| Effective Heat E | `max(VH, PH/2)` for a deal |
| Fingerprint | Multifactor, native-readable description of a vehicle (model gate, plate, colours, mods, cosmetics, context) |
| GC / GT / PT / MT / OD / WALL | GTA clock / game timer / persisted play-time stat / Market Time / odometer distance / real UTC (TIME §1) |
| Ghost timeline | Branch holding saves written while LSAX was not running (D-SL-10) |
| Idempotency key | Deterministic key of a user/system intent; commits at most once on the active path |
| Journal | Authoritative append-only record of commits and events; projection is derived |
| Ledger (save-slot) | LSAX's record of each GTA save file's current content fingerprint (D-SL-3) |
| LsaxVin | 17-character display code derived from VehicleId |
| PREPARED | Durable pre-apply transaction state; resolved only by evidence |
| Projection | Rebuildable current state of the active timeline path |
| Protagonist wallet | `SP0/1/2_TOTAL_CASH` of Michael/Franklin/Trevor (E2-1) |
| RECONCILE_REQUIRED | Safe-refusal state: trading paused until explicit player resolution |
| Reservation | Exclusive claim of a vehicle/listing/offer by one transaction |
| Stop marker | Last-tick values flushed in `Aborted` (never read from game state there) |
| Timeline | Branch of LSAX history; forks at every anchoring |
| Title | Legal standing: CLEAN, SALVAGE, STOLEN, RECOVERED, UNDERGROUND, UNKNOWN, LEGACY |
| VehicleId | 128-bit LSAX identity of a specific vehicle |
| VH / PH | Vehicle Heat / Player (protagonist) Heat, 0…1000 |

## 02 Domain Model → `LSAX-DOMAIN-MODEL.md` §2–§6

Four orthogonal dimensions per vehicle: **ownership**, **title/provenance**, **market state**, **physical lifecycle**.
Parties: three protagonists (separate wallets and garages), NPC parties with virtual budgets. All gameplay state is
timeline-coupled (SAVELOAD §4.4).

## 03 Ownership & Provenance → `LSAX-DOMAIN-MODEL.md` §5

Owned/Purchased/Stolen/Recovered/ForSale/Sold/Unknown are mapped precisely (§5.2). Destroyed, Retired and Missing
are **lifecycle**, not ownership (D-DOM-3). Records retained after destruction are listed in §5.4. LSAX owns only
LSAX transactions (invariant 7); external ownership changes are recorded as events, reconciled only when reliably
detectable (invariant 8) — none are in scope for v1.

## 04 Vehicle Identity / Runtime Binding / Fingerprint → `LSAX-DOMAIN-MODEL.md` §4

Invariants 1–4 hold by construction: handles are runtime only; decorators are session hints (and SHVDN's
`DecoratorInterface.Remove` bug is avoided, E3-2); identity = VehicleId + fingerprint score (BIND ≥ 85 unique,
AMBIGUOUS 60–84 or gap < 20, NO MATCH < 60) + continuity rule (handle-reuse protection) + 20-row collision matrix;
ambiguous → never auto-merge, safe refusal.

## 05 Save/Load Persistence Feasibility → `LSAX-SAVELOAD-FEASIBILITY.md`

Models A/B/C/D compared; **D selected conditionally**; decision record ADR-SL-001 (§8); exact experiment (§6) and
fallback decision table (§7). **BLOCKER B-01** open.

## 06 Canonical Time Model → `LSAX-TIME-MODEL.md`

Seven domains; every subsystem bound to one (§3). MT: 1 MT min per 2 000 ms AT; no offline progression; capped
sleep credit; rewinds with the save.

## 07 Odometer / Condition / Modifications (normative here)

**Odometer (OD, metres, int64, per vehicle, timeline-coupled):**
- Integrates only while the vehicle is **Bound**, has an occupied driver seat, is not attached
  (`IS_ENTITY_ATTACHED`, verified), and the game is active (AT rules).
- Per tick: `Δd = |pos_now − pos_prev|`; accepted iff `Δd ≤ max(v × Δt × 1.5 + 2 m, 5 m)` with
  `v = max(speed_now, speed_prev)` (`GET_ENTITY_SPEED`) and Δt from GT (clamped as AT). Otherwise the step is a
  **teleport/reposition** → 0 m, `TELEPORT_REJECTED` logged (rate-limited). Low FPS scales the bound with Δt
  (displacement-based, chord error < 3 % at 15 FPS — T-ODO-3).
- Pause/loading/fade: no integration; `pos_prev` refreshed on resume. Stream gaps / continuity breaks: `pos_prev`
  reset, nothing added (unobserved distance is not invented). Handle reuse cannot transfer distance (binding rule).
- Checkpoints to the journal every ≥ 1 km or ≥ 60 s of driving and at lifecycle checkpoints; rewind loses ≤ 1 km.
- Corruption/clamping: monotonic within a timeline; values outside 0…10 000 000 km fail DB CHECKs; repair tool logs
  `DATA_REPAIR`. No external mod or trainer can write LSAX odometer (LSAX-owned).

**Condition (durable simulated wear, 0…1000 per component):** ENGINE, TRANSMISSION, SUSPENSION, BRAKES, TYRES,
BODY, INTERIOR. `M = 35 % ENGINE + 20 % TRANSMISSION + 15 % SUSPENSION + 15 % BRAKES + 15 % TYRES`;
`B = 80 % BODY + 20 % INTERIOR` (integer, rdiv).
- Wear per 1 000 km (initial): ENGINE 1.0, TRANSMISSION 0.8, SUSPENSION 1.2, BRAKES 3.0, TYRES 5.0 points; ×1.5 above
  160 km/h segments; multiplier bounded [1.0, 2.0].
- Damage from native signals (signals only): drops of `GET_VEHICLE_BODY_HEALTH` → BODY; `GET_VEHICLE_ENGINE_HEALTH`
  → ENGINE collision damage; `IS_VEHICLE_TYRE_BURST` → TYRES. Native health is never the value basis.
- **Repair semantics:** a native repair (body/engine health jumps up without an LSAX cause) restores BODY to
  `max(BODY, 900)` and ENGINE collision damage; **km-based wear is restored only by LSAX service** (`SERVICE_PAY`);
  undocumented repairs (trainer/unknown) are recorded `REPAIR(documented=false)`. A trainer "fix" can never reset
  mechanical wear or odometer (AX-6).

**Modifications:** `BaselineMods` (generated spec for NPC vehicles; snapshot at registration for world vehicles,
flagged "observed baseline"), `CurrentMods` (latest snapshot), `ModificationHistory` (diffs with MT/OD stamps).
Snapshots at registration, ownership acquisition, garage store, listing, inspection, transaction, and a bounded
periodic check (mod hash every 5 s while Bound; full snapshot ≤ 1 per 60 s when the hash changed). LS Customs /
Benny's entry/exit is an **optional** signal, enabled only if a Stage 2 probe shows ≥ 95 % reliable detection; it is
never the sole provenance mechanism.

## 08 Accident / Service / Owner History (normative here)

- **Accident detection** (Bound, driven vehicles): within a 500 ms window, native body-health drop ΔH and speed drop
  Δv: MINOR (ΔH 10–100 or Δv 15–35 km/h), MODERATE (100–300 or 35–60), SEVERE (> 300 or > 60), STRUCTURAL (not
  driveable after the event, engine health < 0, or ΔH > 600). **Dedupe:** one event per collision sequence (3 s
  window, max severity). Unrepaired damage lives in condition; repaired accidents remain as history stigma
  (VALUATION §4.4). Initial thresholds, tuned in Stage 3 (≥ 90 % agreement on scripted crashes).
- **Service history:** documented services = committed `SERVICE_PAY`; generated service history for NPC vehicles
  (NPC-GEN §4.5). Score S = 1000·done/due.
- **Owner history:** chain of committed ownership changes + generated prior owner count (NPC-GEN §4.7).
- **Disclosure:** remote listing shows title, owner count, accident count by severity, service band; generated history
  is labelled `GENERATED`; physical inspection (Stage 10) shows component condition.

## 09 Valuation Engine → `LSAX-VALUATION-MODEL.md`

Hybrid, integer, bounded: structural multiplicative (age, mileage, condition) + bounded additive adjustments
(A ∈ [−35 %, +15 %]) + capped mod recovery + bounded market factor (±15 %) + global band (0.15–1.35 × BUV) + floor
(5 % MSRP, ≥ $500) + ceiling (125 %, collectibles 200 %). 12 golden vectors, explainable breakdown, tuning sims.

## 10 NPC Vehicle Generation → `LSAX-NPC-GENERATION-MODEL.md`

Correlated causal chain, constraints C1–C9, deterministic seeds keyed to MT day (reload cannot re-roll).

## 11 Demand / Supply / Rarity / Liquidity (normative here)

Per segment (valuation class), updated at each market step (every 60 MT min), integer bp:
- **Supply** `S = clamp(10 000 × live_listings_seg / target_listings_seg, 7 000, 13 000)`, smoothed:
  `S ← S + rdiv(2·(S_raw − S), 10)` (α = 0.2).
- **Demand** `D`: bounded mean-reverting walk — each MT day `D ← D + rdiv(3·(10 000 − D), 10) + U[−200, +200]`
  (seeded by `derive_seed("demand", campaign, seg, mt_day)`), plus event impulses (e.g. a segment's recent player
  sales lower D by 50 bp per sale over 7 MT days), clamped [7 000, 13 000].
- **Liquidity** `L = clamp(10 000 × λ_seg(D,S) / λ_max, 0, 10 000)` with `λ_seg = base_λ_seg × D / S` expected buyer
  contacts per listing per MT day; rarity ≥ VERY_RARE halves λ.
- **Rarity** is a static catalogue attribute (valuation adjustment + buyer-pool size).
- **Saturation:** player listings count toward `live_listings_seg`; mass-listing one segment raises S → lower FMV
  (F_market) and longer time-to-sale.
- Bounds: ≤ 30 generated vehicles per step, ≤ 600 live NPC listings (PERF §4). Targets (initial): live listings per
  segment MAINSTREAM 180, COMMERCIAL 60, SPORTS 80, LUXURY 60, SUPER 20, CLASSIC 30 (+ underground pool 40).

## 12 Legal Market (normative summary; backend Stage 7)

- Listings: DRAFT → ACTIVE (listing fee charged by `LISTING_CREATE`) → RESERVED/SOLD/EXPIRED (MT, default 7 MT days)/
  WITHDRAWN/INVALIDATED; one ACTIVE listing per vehicle; `version` increments on every change; `state_hash` binds
  offers to the vehicle state.
- Eligibility: title ∈ {CLEAN, SALVAGE (disclosed), RECOVERED (disclosed), LEGACY}; UNKNOWN requires title verification.
- Search/filter backend: by segment, make/model, price, age, mileage, condition band, title, owners, accidents, distance;
  deterministic sort; paged (≤ 50 per page); purely Core (UI-independent).
- Offers/counter-offers per VALUATION §6.1 and §15; offer expiry in MT; stale offers invalidated on state-hash change.
- Remote inspection/disclosure per §08; exercised through the debug/test adapter before any polished UI.

## 13 Underground Market → `LSAX-HEAT-AND-UNDERGROUND-MODEL.md`

Access lifecycle, stolen eligibility, fences/chop shops/exporters/collectors, separate valuation and haircut, anti-farm;
no LSAX police engine.

## 14 Heat Model → `LSAX-HEAT-AND-UNDERGROUND-MODEL.md`

VH and PH 0…1000, observed-only sources, floor-rounded MT-hourly decay (half-lives 72/121 MT h), tiers
COLD/WARM/HOT/BURNING, tier effects on price/buyers/deal failure/access, no offline decay, anti-farm stack.

## 15 NPC Buyers / Sellers / Behaviour (normative here; constants initial)

| Buyer profile | Share | Offer discount d (bp) | Reservation d_res | Budget (× FMV) | Traits |
|---|---:|---|---|---|---|
| BARGAIN_HUNTER | 30 % | 1500–3000 | ≥ 1000 | 0.8–1.0 | ignores mods, many counters |
| PRACTICAL | 35 % | 500–1500 | ≥ 300 | 0.9–1.1 | values service history (+200 bp if S ≥ 800) |
| ENTHUSIAST | 15 % | 0–1000 | ≥ 0 | 1.0–1.3 | values tasteful mods (+ up to 50 % of mod cost recovery), sports/muscle/classic only |
| COLLECTOR | 5 % | −200–800 | ≥ −200 | 1.1–1.6 | rarity ≥ RARE or CLASSIC/COLLECTIBLE; originality premium |
| FLEET_BUYER | 10 % | 1000–2000 | ≥ 800 | 0.9–1.0 | COMMERCIAL/MAINSTREAM; mileage-sensitive |
| DEALER | 5 % | 1800–3000 | = dealer spread | 1.0 | always available (liquidity of last resort) |

Seller profiles: EAGER (m 0–300 bp), NORMAL (300–800), GREEDY (800–1 200), DEALER (retail +10 %). Response delays
30–240 MT min; ≤ 3 counter rounds; walk-away after a rejected final counter; all draws seeded
(`derive_seed("buyer", campaign, listing, version, round)`). Buyer arrival rate per listing per MT day =
`λ_seg × attractiveness(ask/FMV)` with attractiveness 1.3 at ask ≤ 0.95 FMV, 1.0 at FMV, 0.5 at 1.15 FMV, 0.1 at
≥ 1.35 FMV (piecewise-linear).

## 16 Transaction State Machine & Recovery → `LSAX-TRANSACTION-STATE-MACHINE.md`

Invariants TX-I1…TX-I9; single-tick atomic core covering money + ownership + vehicle state + market state; idempotency
on the active path; reservations; evidence-only recovery; deals around the core; bounded world actions; interruption
matrix (§10).

## 17 Persistence / SQLite Schema / Migrations → `LSAX-DB-SCHEMA-DRAFT.md`

Journal (authoritative) + projection (derived) + snapshots; schema_version; forward-only checksummed migrations with
backup; startup integrity and rebuild; growth bounds; native SQLite preload (R-DB-1).

## 18 Economy / GTA Money / Fees / Sinks (normative here; amounts initial)

- **Money:** GTA protagonist wallets only (no LSAX currency, no LSAX-held balances). Wallet access exclusively through
  the transaction core's wallet port: read → verify → absolute write → read-back (E2-2), one tick. Characters without a
  wallet are refused (D-ECO-2). Invariant: Σ wallet deltas caused by LSAX = Σ committed money lines (T-RT-TX-1).
- **Purchase validation:** wallet ≥ price + transfer tax at PREPARE and re-verified at apply.
- **Seller payment:** credited in the same tick as the ownership transfer.
- **Fees (sinks):** listing fee = clamp(0.5 % × ask, $100, $2 500), non-refundable unless LSAX cancels (system
  INVALIDATED → `REFUND`); sale commission (player sells legally) = clamp(3 % × TP, $200, $25 000); transfer tax (player
  buys legally) = clamp(1 % × TP, $50, $10 000); title verification = $500 + 1 % FMV, ≤ $5 000.
- **Cancellation/refund:** pre-commit cancellation moves no money; commits are final; the only refund is the `REFUND`
  compensation of a failed LSAX delivery or a system cancellation (idempotent key `REFUND|txn`).
- **Dealer spread:** 18–30 % (+5 % if C < 400), VALUATION §6.1. **Underground:** haircut + velocity surcharge (Heat §5).
- **NPC liquidity/budgets:** virtual; budget per buyer seeded from profile (§15); no global money supply.
- **Anti-farm:** round-trip arbitrage negative by construction (T-VAL-SIM-2: dealer round-trip loss ≥ 15 %; list-at-FMV
  net ≤ ask); underground caps (Heat §7); deterministic seeds.
- **Modification value recovery:** capped at 10 % of CAV in FMV (VALUATION §4.4); enthusiast buyers may pay more (§15).
- **Not built:** a macroeconomic simulator. LSAX is a bounded, tunable automotive economy.

## 19 Localization Contract & Enforcement → `LSAX-LOCALIZATION-CONTRACT.md`

ru-RU primary/default, en-US parity; `MessageRef` from Core; JSON + ICU subset; CLDR plurals; fallback and diagnostics;
analyzer LSAX001 and parity tests.

## 20 Debug Inspector / UI Abstraction / Feasibility (normative here)

- **Debug Inspector API (Stage 1, renderer-independent):**
  `InspectVehicle(EntityRef) → InspectionReport{ identity(VehicleId, LsaxVin, confidence, binding state, candidates),
  mileage, condition(components), ownership & title, history (last N), valuation breakdown (VALUATION §5),
  market state, heat }`, all text as `MessageRef`. Also `InspectSession()` (timeline, anchor source, ledger, reconcile
  state), `InspectCaps()` (bounded-collection counters), `InspectL10n()` (missing keys).
- **Minimal debug renderer:** SHVDN built-in `GTA.UI.TextElement`/`ContainerElement` (present in the 3.6.0 assembly
  and 3.7 source — VERIFIED (compile surface)); zero third-party dependency; toggled by a configurable key.
- **UI abstraction:** `IUiRenderer` consumes view models (lists, panels, forms, prompts); Core has no reference to any
  renderer (T-ARCH-1).
- **Renderer choice (OD-1) is not justified yet** (no runtime evidence). Candidates: LemonUI (SHVDN3 build),
  NativeUI, custom Scaleform (e.g. an in-game web-browser style), in-house text overlay.
- **Feasibility spike UI-S1 — pass/fail:** (1) renders ru-RU strings containing ё/Ё/ъ and 60+ characters and en-US
  strings without missing glyphs; (2) documents NBSP/typographic glyph support (R-L10N-1); (3) ≤ 0.5 ms/frame for a
  20-row list (LSAX stopwatch); (4) keyboard and gamepad navigation; (5) input isolation when another mod's menu is
  open (no double actions in 20 trials); (6) survives SHVDN `Reload` 20× without exceptions or leaked handlers;
  (7) 1080p, 1440p and 21:9 layouts legible; (8) 30 min open/close cycling with 0 exceptions. A renderer failing any
  item is rejected.

## 21 Mail / Notifications Contract (normative here)

- **Mail:** persistent, timeline-coupled rows (template key + params, MT + GC display stamp), per protagonist inbox,
  read/archived flags, retention 500 per protagonist (older archived then compacted). Created **only after commit**
  (never for rolled-back work). Triggers: offer received/countered/expired, sale/purchase completed, listing expired,
  delivery status, reconcile required, underground contact, title verification result.
- **Notifications:** transient, in-memory queue ≤ 32, ≤ 1 shown per 3 s, never block input, never persisted; carry a
  `MessageRef`; a notification may reference a mail item.
- Both go through `ILocalizer`; switching locale re-renders mail.

## 22 Performance Budget → `LSAX-PERFORMANCE-BUDGET.md`

≤ 1.0 ms average / 2.0 ms p99 per tick (excluding transaction ticks ≤ 25 ms p95), bounded scans (≤ 64 entities, 120 m,
1 Hz), worker threads for Core and DB, bounded collections table, long-session growth bounds.

## 23 Compatibility Contract → `LSAX-COMPATIBILITY-CONTRACT.md`

Ownership matrix for GTA/RAGE, SHVDN, RDE/SixStarResponse, RealParamedics, Persist Corpses, Crime Scene Aftermath,
Lively World, Unified Shadow Logger, Crime Jobs, LSAX; entity-conflict rules; forbidden-native IL scan.

## 24 Anti-Exploit Invariants (normative here)

| ID | Exploit | Invariant / mechanism |
|---|---|---|
| AX-1 | duplicate VIN / clones | VehicleId/LsaxVin unique; clones never inherit a title (C8/C9); CLONE_SUSPECT |
| AX-2 | replayed commit | idempotency on the active path (TX-I2) |
| AX-3 | double payment / double sale | reservations + wallet verify-before-apply (TX-I3/I4) |
| AX-4 | save/load/reload/crash mid-deal | anchoring + evidence-only recovery; RECONCILE otherwise (TX-I7) |
| AX-5 | stolen → legal bypass | no title path from STOLEN/UNDERGROUND to CLEAN; plate swap/respray never change title; title verification fails on STOLEN match |
| AX-6 | trainer mutation | odometer/wear LSAX-owned; native repair doesn't reset wear; mutations while Dormant lower identity confidence (refusal) |
| AX-7 | sold-vehicle respawn | `GAME_RESPAWN_OF_SOLD` → not registrable/sellable |
| AX-8 | destroyed-vehicle sale | lifecycle DESTROYED/RETIRED not listable/sellable; listings INVALIDATED |
| AX-9 | re-roll by reload | seeds keyed to campaign + MT day/listing version |
| AX-10 | market farming / arbitrage | negative round trip (fees + spreads); underground caps + velocity + Heat |
| AX-11 | stale listing / accepted offer | versions + state hash + MT expiry checked at PREPARE (TX-I6) |
| AX-12 | wallet ambiguity (non-protagonist model) | money operations refused (D-ECO-2) |
| AX-13 | buy → load earlier save → keep car | money-coupled state rewinds with the save (Model D) |

These are designed now and verified adversarially in Stage 11 — not postponed.

## 25 Logging / Diagnostics Contract (normative here)

- `LSAX.log` format per COMPAT §3; levels ERROR/WARN/INFO/DEBUG; categories `core, tx, sl (save/load), id, odo, mkt,
  heat, db, l10n, ui, perf, compat`; stable event codes (`TX_COMMITTED`, `SL_ANCHORED`, `SL_RECONCILE`, `ID_AMBIGUOUS`,
  `ODO_TELEPORT_REJECTED`, `PERF_DEFER`, …); per-code rate limit (≤ 10/min, then summary).
- **Circuit breaker:** every subsystem tick is wrapped; an exception is logged with context and the subsystem is
  disabled after 3 failures in 60 s (others continue). LSAX never lets an exception escape a tick (SHVDN would abort the
  whole script, E1-7).
- DB `audit_log` records every transaction resolution, reconcile decision, data repair and security-relevant refusal.
- Debug inspector exposes counters (caps, queue depths, tick-time histogram, missing keys).
- No personal data (user names, paths) in logs beyond the GTA scripts-relative paths.

## 26 Testing Strategy → `LSAX-TEST-STRATEGY.md`

L1 pure (CI), L2 harness with fake ports + real SQLite (CI), L3 runtime on the target PC; Python reference models as
oracles; evidence requirements.

## 27 Non-Goals (v1)

No LSAX police/wanted/dispatch engine · no global macroeconomic simulator · no LSAX currency/bank · no parsing or
editing of GTA save files · no replacement of GTA garages, impound or story vehicle systems · no mission integration
unless explicitly configured · no multiplayer/FiveM/GTA Online · no GTA V Enhanced support (Legacy 1.0.3725.0 only) · no
offline (GTA-closed) progression · no vehicle handling/physics changes · no traffic/population control · no insurance
system · no mandatory dependency on other mods' data files (reference SellVehicle depends on PDM INI files, R4).

## 28 Stage Acceptance Criteria → `LSAX-STAGE-ACCEPTANCE.md`

Measurable per stage; Stage 1 split into S1a (independent of B-01) and S1b (requires B-01 closed).

## 29 Risk Register / Open Decisions → `LSAX-RISK-REGISTER.md`

1 BLOCKER (B-01), 12 P1 risks, 13 P2 risks/constraints, 6 open decisions.

## 30 Roadmap Mapping

| Roadmap Phase 0 item | Where |
|---|---|
| 1 Glossary | §01 |
| 2 Domain model | DOMAIN-MODEL |
| 3 Ownership/provenance | DOMAIN-MODEL §5 |
| 4 Persistent identity | DOMAIN-MODEL §4 |
| 5 Save/load feasibility spike | SAVELOAD, phase0-probes (P-SL-01/02), sim E8-5 |
| 6 Canonical time | TIME-MODEL |
| 7 SQLite/persistence, schema_version, migrations, recovery | DB-SCHEMA-DRAFT |
| 8 Valuation contract, golden vehicles | VALUATION-MODEL |
| 9 Correlated NPC generation | NPC-GENERATION-MODEL |
| 10 Heat | HEAT-AND-UNDERGROUND-MODEL |
| 11 Economy (GTA money) | §18 |
| 12 Transaction invariants, journal, idempotency | TRANSACTION-STATE-MACHINE |
| 13 Localization | LOCALIZATION-CONTRACT |
| 14 Logging | §25, COMPAT §3 |
| 15 Testing strategy | TEST-STRATEGY |
| 16 UI abstraction + feasibility spike | §20 (UI-S1) |
| 17 Compatibility/performance budgets | COMPATIBILITY-CONTRACT, PERFORMANCE-BUDGET |
| 18 Non-goals | §27 |
| 19 Measurable acceptance criteria | STAGE-ACCEPTANCE |
| 20 Independent read-only audit | not self-granted; Appendix L |

| Stage | Spec sections |
|---|---|
| 1 Foundation, Identity & Persistence | §04, §05 (S1b gated), §06, §17, §19, §20 (inspector), §25 |
| 2 Odometer, Condition & Mods | §07 |
| 3 Ownership, Provenance & History | §03, §08 |
| 4 Valuation & Economy | §09, §18 |
| 5 Transaction Core | §16 |
| 6 NPC Market Simulation | §10, §11, §15 |
| 7 Legal Market Backend | §12 |
| 8 Player UI, Mail & Notifications | §20, §21 |
| 9 Underground & Heat | §13, §14 |
| 10 Physical Inspection & Handover | §16 (deals), TSM §9 |
| 11 Anti-Exploit | §24 |
| 12 Compatibility & Performance | §22, §23 |
| 13 Release Candidate | STAGE-ACCEPTANCE |

---

## Appendices

| Appendix | Content | Location |
|---|---|---|
| A | Domain / state diagrams (entities, binding, title, lifecycle, transaction, deal) | DOMAIN-MODEL §2, §4.2, §5.2, §5.4; TSM §4, §8 |
| B | DB schema draft | DB-SCHEMA-DRAFT §3 |
| C | Valuation formula + 12 worked vectors | VALUATION-MODEL §4, §8; `evidence/sim/valuation_ref.out.md` (all breakdowns) |
| D | Heat model examples | HEAT §4, §8; `evidence/sim/heat_ref.out.md` |
| E | Initial mileage / generation examples | NPC-GENERATION §6, §7; `evidence/sim/npcgen_ref.out.md` |
| F | Identity collision matrix | DOMAIN-MODEL §4.7 |
| G | Save/load decision record | SAVELOAD §8 (ADR-SL-001) |
| H | Transaction interruption / recovery matrix | TSM §10 |
| I | Localization key examples | LOCALIZATION §8 |
| J | Performance budget table | PERFORMANCE §2 |
| K | Compatibility ownership matrix | COMPATIBILITY §1 |
| L | SPEC_APPROVED checklist | below |

### Appendix L — SPEC_APPROVED checklist (author's self-assessment; approval is NOT granted by the author)

| Gate item | Self-assessment | Evidence / reason |
|---|---|---|
| glossary complete | PASS | §01 |
| ownership/provenance boundaries complete | PASS | DOMAIN §5 |
| vehicle identity model complete | PASS (design) — runtime hit-rates pending P-ID-01; R-ID-4 (P1, Stage 3) | DOMAIN §4 |
| **save/load persistence model proven feasible** | **FAIL — BLOCKER B-01** | logic VERIFIED (sim, E8-5); runtime assumptions A-SL-1/5/6/7 unproven; exact experiment SAVELOAD §6 |
| canonical time model complete | PASS (PT depends on A-SL-6, used only for anchoring) | TIME |
| persistence/schema/migration/recovery complete | PASS (design) — native load R-DB-1 (P1) pending P-DB-01 | DB-SCHEMA |
| valuation mathematical contract complete | PASS — constants tunable with simulation criteria | VALUATION, E8-2 |
| NPC generation contract complete | PASS | NPC-GEN, E8-3 |
| Heat model complete | PASS | HEAT, E8-4 |
| economy contract complete | PASS — balance band OD-2 open (P2) | §18 |
| transaction invariants/failure states complete | PASS | TSM, E8-5 |
| localization contract/enforcement complete | PASS | LOCALIZATION |
| testing strategy complete | PASS | TEST-STRATEGY |
| measurable stage acceptance criteria complete | PASS | STAGE-ACCEPTANCE |
| compatibility/performance contracts complete | PASS (design) — third-party behaviour ASSUMPTION (R-COMP-1), budgets unmeasured | COMPAT, PERF |

**Author's recommendation to the auditor:** do **not** grant SPEC_APPROVED until B-01 is closed by P-SL-01 on the target
PC. If the auditor finds no other P0/P1 defects, the owner may authorise **Stage 1a only** (persistence-sync independent
work, STAGE-ACCEPTANCE §S1a) while P-SL-01 is run; S1b and everything depending on save/load coupling stay blocked.
