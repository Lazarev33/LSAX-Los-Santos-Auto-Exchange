# LSAX — Heat Model & Underground Market

Document: LSAX-HEAT-AND-UNDERGROUND-MODEL.md · Spec: LSAX MASTER SPEC v1.0 DRAFT2 · Status: DRAFT for independent re-audit

Normative reference implementation: `phase0-probes/sim/heat_ref.py` (VERIFIED (sim), E8-4). Constants are
**INITIAL / TUNABLE** except where marked.

## 1. Boundary: Heat is not policing

Heat is an **LSAX market quantity**: how risky a vehicle or a seller looks to underground buyers. LSAX **never**
sets or clears wanted level, never spawns or dispatches police, never alters RDE/SixStar escalation (mandatory
invariant 9). The wanted level is **read-only input** via `GET_PLAYER_WANTED_LEVEL` (verified to exist). All Heat
effects are market effects: prices, buyer availability, deal failure, access, cooldowns.

## 2. Scales

| Scale | Subject | Range | Stored |
|---|---|---|---|
| Vehicle Heat `VH` | one vehicle (title STOLEN or UNDERGROUND) | integer 0…1000 | `heat_state(scope='VEHICLE')`, timeline-coupled |
| Player Heat `PH` | one protagonist (SP0/SP1/SP2) | integer 0…1000 | `heat_state(scope='PROTAGONIST')`, timeline-coupled |
| Effective Heat `E` | a deal | `E = max(VH, PH / 2)` | derived |

Tiers (apply to VH, PH and E): **COLD 0–199 · WARM 200–449 · HOT 450–749 · BURNING 750–1000**.

## 3. Sources (observed events → deltas; each delta clamped to ±500, result clamped to 0…1000)

| Event (detection) | Scale | Delta |
|---|---|---|
| `THEFT_PARKED`: player drives ≥ 50 m in a world vehicle with population type `RandomParked` that LSAX does not record as owned by the acting protagonist | VH | +250 |
| `THEFT_CARJACK`: driver seat held by a non-player ped (`GET_PED_IN_VEHICLE_SEAT`/`GET_LAST_PED_IN_VEHICLE_SEAT`, `IS_PED_JACKING`) within 5 s before the player took it; population type `RandomAmbient`/`RandomScenario`/`RandomPermanent` | VH | +400 |
| `WANTED_AT_THEFT`: wanted level observed within 60 s after the theft | VH | +100 per star, ≤ +300 |
| `PURSUIT_IN_VEHICLE`: wanted level ≥ 1 observed while driving this stolen vehicle (≤ once per MT hour) | VH | +60 |
| `PLATE_SWAP` on a stolen vehicle (≤ once per 7 MT days) | VH / PH | −150 / +20 |
| `RESPRAY` on a stolen vehicle (≤ once per 7 MT days) | VH | −100 |
| `SALE_FENCE` | PH | +40 + VH/10 + velocity (§5) |
| `SALE_EXPORT` | PH | +25 + VH/20 + velocity |
| `SALE_CHOP` | PH | +15 + velocity |
| `BUY_UNDERGROUND` | PH | +10 |
| `WANTED_DURING_UG_DEAL` (wanted level ≥ 1 observed during an underground meeting) | PH | +50 |

Exclusions (no theft classification, no Heat): mission/script-owned vehicles, population type `Mission`,
`Permanent` (until P-ID-01 clarifies story personal vehicles, R-ID-4), vehicles owned by the acting protagonist in
LSAX, SHVDN `VehicleClass` `Emergency`/`Military`/`Service`/`Trains`/`Boats`/`Planes`/`Helicopters`/`Cycles`
(also **not tradeable** in LSAX markets). Enum names verified in SHVDN source (`EntityPopulationType`,
`VehicleClass`).

## 4. Decay (normative arithmetic)

Hourly steps in **MT** (LSAX-TIME-MODEL.md), using **floor** division (the one exception to `rdiv`, D-HEAT-3):

`VH ← floor(VH × 9911 / 10000)` (half-life 72 MT h) · `PH ← floor(PH × 9949 / 10000)` (half-life 121 MT h).

Floor guarantees strict decrease for any value ≥ 1 (with `rdiv`, 52 × 0.9904 = 51.5 → 52 is a fixed point — found by
the simulation). Catch-up after a gap applies at most 720 steps; any heat is already 0 after 450 steps.

**Offline:** MT does not advance while GTA is closed → **no decay offline** (S7 below). **Sleep:** credited MT
(≤ 12 h per event) decays normally. **Save/load:** Heat rewinds with the timeline.

| Scale | 1000 → below HOT | → below WARM | → COLD | → 0 | measured half-life |
|---|---:|---:|---:|---:|---:|
| Vehicle heat | 31 MT h | 83 | 160 | 315 | 72 |
| Player heat | 51 | 138 | 253 | 450 | 121 |

(1 MT hour = 2 real minutes of active play; a 72 MT h half-life ≈ 2.4 h of play.)

## 5. Tier effects

| Effect | COLD | WARM | HOT | BURNING |
|---|---|---|---|---|
| Fence haircut (bp of FMV basis) | 5500 | 6200 | 7200 | fence refuses |
| Velocity surcharge on fence haircut | +400 per underground sale beyond 2 within 48 MT h, ≤ +2000; total haircut ≤ 9000 (D-HEAT-6) | | | |
| Exporter | yes | yes | no | no |
| Collector | yes | yes | yes | no |
| Chop shop | yes | yes | yes | yes |
| Underground buyer availability (offers per MT day multiplier) | 1.0 | 0.8 | 0.5 | 0.2 |
| Deal failure at meeting (buyer no-show/walk-away) | 3 % | 6 % | 12 % | 25 % |
| Player access (PH) | normal | normal | new UG listings delayed 6 MT h | **lay-low**: enter at PH ≥ 750, exit at PH < 600 (hysteresis): no new UG listings, fence/export refuse |

Legal market: Heat never changes legal prices; STOLEN/UNDERGROUND titles are simply ineligible (AX-5).

## 6. Underground access lifecycle

`LOCKED → UNLOCKED` when the protagonist completes the introduction (Stage 9 content: an LSAX contact; at least one
observed theft) → `LAYLOW` (PH ≥ 750) → `UNLOCKED` (PH < 600). Access is per protagonist and timeline-coupled.

## 7. Anti-farm stack (steal → sell loops)

1. Velocity surcharge and PH growth per sale (§3, §5).
2. Daily caps: ≤ 3 vehicles per fence and ≤ 6 underground sales in total per protagonist per MT day.
3. Identity: a VehicleId can be sold to the underground once; chopped/exported vehicles become RETIRED;
   respawns of sold vehicles are blocked (AX-7).
4. Saturation: repeated sales of the same model raise that segment's supply index for the underground
   (lower basis FMV) for 7 MT days.
5. Deterministic market seeds: reloading cannot re-roll buyers or no-shows (LSAX-NPC-GENERATION-MODEL.md §2).
6. No offline cooling.

## 8. Heat examples (reference run; FMV basis $20 000)

| Scenario | VH at sale | PH before | E | Tier | Fence payout | PH after |
|---|---:|---:|---:|---|---:|---:|
| S1 parked theft, sell after 2 MT h | 244 | 0 | 244 | WARM | 7 600 | 64 |
| S2 carjack + 2 stars, sell after 1 MT h | 594 | 0 | 594 | HOT | 5 600 | 99 |
| S3 as S2, lay low 72 MT h | 291 | 0 | 291 | WARM | 7 600 | 69 |
| S6 as S2 + plate swap + respray, 24 MT h | 274 | 0 | 274 | WARM | 7 600 | 67 |
| S7 as S2, GTA closed 3 real days (MT +0) | 594 | 0 | 594 | HOT | 5 600 | 99 |

Farming loop (parked theft + fence sale every 2 MT h, alternating two fences): payouts 7 600, 7 600, 6 800, 6 000,
5 200, 4 400; cars 7–12 refused (daily cap). First-MT-day income $37 600 for 6 cars. **OPEN RISK R-ECO-2:** whether
this ceiling is right is a balance question for Stage 9 (target: underground income per active hour within
0.6–1.2× the legal flipping income for comparable effort — to be measured by the Stage 9 economy simulation).

## 9. Tests

T-HEAT-1 half-lives 72 ± 1 / 121 ± 1 MT h; T-HEAT-2 decay terminates ≤ 720 steps and never leaves [0, h];
T-HEAT-3 offline gap → no change; T-HEAT-4 cooling (lay low / plate swap / respray) raises payout; T-HEAT-5 farming
loop: payout of the 6th sale ≤ 75 % of the 1st and the 7th is refused; T-HEAT-6 LSAX never calls wanted-level or
dispatch setters (static check: forbidden-native list in LSAX-COMPATIBILITY-CONTRACT.md §4).
