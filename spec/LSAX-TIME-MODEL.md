# LSAX — Canonical Time Model

Document: LSAX-TIME-MODEL.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

LSAX has **no universal clock**. It has seven time domains with fixed owners and uses. Gameplay rules may only
use the domain assigned to them in §3. All values are integers.

## 1. Domains

| ID | Name | Source | Unit / type | Persisted | Monotonic | Label |
|---|---|---|---|---|---|---|
| WALL | Real UTC time | `DateTime.UtcNow` (.NET BCL) | ms, int64 | yes (logs, ledger, stop markers) | no (system clock can change) | VERIFIED (BCL) |
| GT | GTA game timer | `GET_GAME_TIMER` = `Game.GameTime` (E5-1) | ms, int32 | **never** | within a session only; behaviour across load not assumed | VERIFIED (API) |
| AT | Active session time | LSAX: Σ clamped GT deltas while active (§2.1) | ms, int64 | no (per session) | yes | DESIGN DECISION |
| PT | Persisted play-time stat | SP stat read via `STAT_GET_INT` (name TBD by P-SL-01) | ms (granularity G) | inside the GTA save | assumed | **ASSUMPTION A-SL-6** |
| MT | Market Time | LSAX canonical gameplay clock (§2.2) | MT minutes, int64 | yes, timeline-coupled | yes along a timeline path | DESIGN DECISION |
| GC | GTA in-game clock | `GET_CLOCK_*` (E4-1), `GameClock` (E5-4) | date + h:m:s | inside the GTA save | no (sleep, trainers, load) | VERIFIED (API) |
| OD | Odometer distance | LSAX integration (LSAX-MASTER-SPEC §07) | metres, int64 | yes, timeline-coupled | yes per vehicle | DESIGN DECISION |

## 2. Definitions

### 2.1 AT — Active Session Time

Each LSAX tick: `Δ = GT_now − GT_prev`.

- If `Δ < 0` or `Δ > 1 000` ms → counted 0 (stall, debugger, alt-tab, load) and logged at DEBUG.
- Else counted `Δ` only if the game is **active**: not `IS_PAUSE_MENU_ACTIVE`, not
  `GET_IS_LOADING_SCREEN_ACTIVE`, not `IS_SCREEN_FADED_OUT` for more than 5 000 ms consecutively
  (short fades from mods/teleports still count), player control not suspended by a player switch
  (`IS_PLAYER_SWITCH_IN_PROGRESS`).
- Low FPS does not distort AT (Δ grows, still ≤ 1 000 ms). AT resets at session start.

### 2.2 MT — Market Time

- Unit: MT minute. **Base rate: 1 MT minute per 2 000 ms of AT** (an LSAX constant, equal to GTA's default
  ms-per-game-minute but independent of `GET_MILLISECONDS_PER_GAME_MINUTE`, so time-scale mods do not
  accelerate the LSAX economy). 1 MT day = 1 440 MT min = 48 min of active play.
- **Time-skip credit** (sleeping, safehouse time skips): when GC advances by `Δgc` game minutes in a window where
  base MT advanced `Δbase`, `skip = Δgc − Δbase`. If `skip ≥ 30`: credit `min(skip, 720)` MT min (≤ 12 MT h per
  event), subject to a rolling cap of total credits ≤ base MT accrued over the last 1 440 base MT min (at most
  doubles the rate). Negative GC jumps (trainer set-back, load) are ignored. Label: DESIGN DECISION + OPEN RISK
  R-TIME-1 (heuristic).
- **Persistence:** MT is timeline-coupled. Every commit stores `mt`; an `mt_checkpoint(p, mt)` journal event is
  written every 60 s of AT. After anchoring at play-time P:
  `MT(P) = mt_cp + rdiv(P − p_cp, 2000)` using the last checkpoint on the anchored path with `p_cp ≤ P`.
  Error ≤ skip credits granted inside one 60 s checkpoint interval.
- **Offline (GTA closed):** MT does **not** advance. DESIGN DECISION. Reasons: (1) the save being loaded cannot
  know how much real time passed, so offline progression would decouple LSAX from the save; (2) system-clock
  manipulation would become an exploit; (3) determinism of replay.
- **Character switch:** MT is per timeline, shared by all protagonists (the market is one world).
- **Save/load:** MT rewinds with the timeline (anchoring). Reloading cannot "fast-forward" the market.
- **Display:** player-facing UI shows MT **durations** ("listed 2 days ago", "expires in 5 h"), never an
  absolute LSAX date. Mail items additionally show the GC date/time at receipt as flavour.

### 2.3 PT — play-time stat

Used **only** for save/load anchoring and commit stamping (LSAX-SAVELOAD-FEASIBILITY.md). Never used to time
gameplay (it is not proven to exist; fallback anchoring must not change gameplay timing).

### 2.4 GC — GTA clock

Presentation and time-skip detection only. Month from `GET_CLOCK_MONTH` is 0-based (SHVDN `GameClock.Month0`,
verified in source). GC is never authoritative for expiry, decay or age.

## 3. Subsystem → clock assignment (normative)

| Subsystem / quantity | Clock | Why |
|---|---|---|
| Market simulation steps (NPC inventory, demand/supply drift) | MT (step every 60 MT min) | save-coupled, deterministic, pause-safe |
| Listing age, listing expiry | MT | fair to paused/away players; rewinds with save |
| Asynchronous negotiation (offer response delay, offer expiry) | MT | as above |
| Live in-scene negotiation (buyer standing in front of player) | AT | must not expire while paused; bounded per scene |
| Physical handover / inspection scenes, world-task timeouts, retry back-off | AT | real-time bounded execution; pause must not fail a scene |
| Heat decay | MT (hourly steps) | tied to save; no offline cooling |
| Accident age (history) | MT stamp + OD stamp | "12 days / 340 km ago" survives rewinds |
| Vehicle age | MT (`age = MT_now − birth_mt`; NPC vehicles get negative `birth_mt` at generation) | slow ageing consistent with MT day = 48 min |
| Odometer | OD (distance) | distance, not time |
| Offline absence | none | MT frozen |
| Sleep / time skip | MT credit (capped) | world "moves on" a bounded amount |
| Save/load rollback | MT via anchoring | coupling |
| Logs, diagnostics, ledger, stop markers | WALL | forensic |
| Anchoring window bounds | PT + WALL (play time ≤ wall time) | LSAX-SAVELOAD-FEASIBILITY.md §4.2 |
| Tick cadence, cache TTL, notification on-screen duration | GT/AT | session-local |
| Anti-farm windows (e.g. underground sales per 48 MT h) | MT | save-coupled; cannot be reset by waiting offline |

## 4. Conversions and constants (tunable except where marked)

| Constant | Value | Tunable |
|---|---|---|
| MT base rate | 2 000 ms AT per MT minute | no (changing it rescales every MT-denominated constant) |
| Skip credit threshold / per-event cap / rolling cap | 30 / 720 / 1 440 MT min | yes |
| AT stall threshold | 1 000 ms | yes |
| Fade-out exclusion after | 5 000 ms | yes |
| MT checkpoint interval | 60 s AT | yes (trades DB writes vs rewind precision) |
| MT month (for age tables) | 30 MT days = 43 200 MT min | no |

## 5. Tests (see LSAX-TEST-STRATEGY.md T-TIME-*)

- Pure: AT accumulation with synthetic GT streams (negative Δ, 5 s stall, 10 FPS, pause toggles) → exact
  expected AT; MT from AT at base rate; skip credit caps (single 12 h sleep → 720; three sleeps in one MT day
  → capped at 1 440 total credit); negative GC jump → 0 credit; offline gap → 0 MT.
- Anchoring: MT(P) reconstruction from checkpoints equals the value recorded at save within one checkpoint
  interval (simulation extension of `journal_timeline_ref.py`, Stage 1).
- Runtime: 30 min active play → MT advance 900 ± 1 MT min (± 0.1 %), with the pause menu open 10 min in between
  → +0 during pause.
