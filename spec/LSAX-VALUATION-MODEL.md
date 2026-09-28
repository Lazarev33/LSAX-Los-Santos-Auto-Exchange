# LSAX — Valuation Engine: Mathematical Contract

Document: LSAX-VALUATION-MODEL.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

Normative reference implementation: `phase0-probes/sim/valuation_ref.py` (+ `lsax_ref_math.py`). The C#
implementation (Stage 4) must reproduce its outputs **exactly** for the golden vectors (§8). Balance constants are
**INITIAL / TUNABLE** (§9); the structure, bounds, arithmetic and properties are normative.

Explicitly rejected: `price = basePrice * health` (the reference mod SellVehicle does a piecewise version of this,
LSAX-REFERENCE-REVIEW.md R1) and long products of minor factors.

## 1. Price concepts

| Concept | Symbol | Definition |
|---|---|---|
| Reference MSRP | `MSRP` | catalogue price of the model new (LSAX catalogue; override table; fallback §3.1) |
| Base Used Value | `BUV` | `MSRP × F_age × F_mileage` — structural, multiplicative |
| Condition-Adjusted Value | `CAV` | `BUV × F_condition` — structural, multiplicative |
| Adjusted Value | `AV` | `CAV × (1 + A) + ModValue` — bounded additive history/attribute adjustments + capped modification recovery |
| Fair Market Value | `FMV` | `AV × F_market` (× salvage regime), clamped by global band, floor, ceiling, rounded |
| Asking Price | `Ask` | seller's listed price (NPC: `FMV × (1+m)`; player: bounded free input) |
| Offer Price | `Offer` | buyer's bid `FMV × (1−d)`, bounded by buyer budget |
| Transaction Price | `TP` | the amount agreed in a committed transaction (fees are separate lines) |
| Dealer acquisition | `DealerBuy` | instant legal sale to LSAX dealer `FMV × (1 − spread)` |
| Dealer retail | `DealerSell` | LSAX dealer stock price `FMV × 1.10` |
| Underground acquisition | `Fence`, `Chop`, `Export`, `Collector` | underground buyer values (§6.3), Heat-dependent |

## 2. Arithmetic (normative)

Integer dollars; factors in basis points (10 000 bp = 1.0); every division via `rdiv` (round half away from zero);
curves are piecewise-linear integer tables with flat extrapolation; no floating point, no `exp/log/pow`. Final
money rounding `round_money`: to $50 below $100 000, $100 below $1 000 000, $1 000 above. (`lsax_ref_math.py`)

## 3. Inputs

| Input | Source | Range |
|---|---|---|
| model, class, MSRP, rarity, annual km norm | catalogue | class ∈ {MAINSTREAM, LUXURY, SPORTS, SUPER, COMMERCIAL, CLASSIC, COLLECTIBLE} |
| age (MT months) | `(MT_now − birth_mt) / 43 200` | ≥ 0 |
| odometer km | OD domain | 0 … 10 000 000 |
| mechanical M, body B | durable simulated condition | 0 … 1000 |
| driveable | `IS_VEHICLE_DRIVEABLE` snapshot or simulated | bool |
| accidents (repaired history) | history events | severities MINOR / MODERATE / SEVERE / STRUCTURAL |
| service score S | history | 0 … 1000 or "not yet due" |
| owner count | ownership chain | ≥ 1 |
| modifications | CurrentMods vs BaselineMods with catalogue part costs | list (category, cost) |
| originality O | share of stock parts, 0 … 1000 | |
| provenance | title status | LSAX-DOMAIN-MODEL.md §5.2 |
| demand D, supply S, liquidity L | market segment state | D, S ∈ [7 000, 13 000] bp; L ∈ [0, 10 000] bp |
| Heat | effective heat (underground only) | 0 … 1000 |

### 3.1 MSRP fallback chain

catalogue override → LSAX shipped catalogue → `GET_VEHICLE_MODEL_VALUE(model)` (handling `nMonetaryValue`,
verified to exist, meaning for add-ons unverified: **ASSUMPTION A-VAL-1**) scaled by class factor → class default.
Every fallback use is logged once per model with the chosen value (debug report "unpriced models").

## 4. Pipeline (normative structure; constants initial)

### 4.1 Age — `F_age = interp(AGE_CURVE[class], age_months)` (bp)

| Class | 0 | 12 | 24 | 36 | 60 | 96 | 120 | 144 | 240 | 300 | 360 | 420 | 480 | 600 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MAINSTREAM | 9000 | 7800 | 6800 | 6000 | 4700 | 3300 | · | 2200 | 1500 | · | 1200 | · | · | · |
| LUXURY | 8800 | 7200 | 6000 | 5000 | 3600 | 2400 | · | 1600 | 1200 | · | 1000 | · | · | · |
| SPORTS | 9000 | 8000 | 7100 | 6400 | 5200 | 4000 | · | 3000 | 2400 | · | 2400 | · | · | · |
| SUPER | 9200 | 8200 | 7400 | 6800 | 5800 | 5000 | · | 4500 | 4500 | · | 4500 | · | · | · |
| COMMERCIAL | 8800 | 7400 | 6300 | 5400 | 4000 | 2700 | · | 1800 | 1200 | · | 1000 | · | · | · |
| CLASSIC | 9000 | 7800 | 6800 | 6000 | 4700 | 3300 | · | 2500 | 2600 | 3500 | · | 5000 | · | 5500 |
| COLLECTIBLE | 9200 | · | 8000 | · | 7000 | · | 6800 | · | 7500 | · | 9000 | · | 10500 | 11000 |

("·" = not a table point; interpolation between neighbours.)

### 4.2 Mileage — `F_mileage = clamp(interp(RATIO, r) × interp(ABS, km), 6400, 10600)`

`expected_km = rdiv(ANNUAL_KM[class] × max(age_months, 3), 12)`, `r = rdiv(km × 10 000, expected_km)` (bp).
ANNUAL_KM: MAINSTREAM 15 000, LUXURY 14 000, SPORTS 9 000, SUPER 4 000, COMMERCIAL 30 000, CLASSIC 5 000,
COLLECTIBLE 3 000.
RATIO table (r bp → bp): 0→10600, 5000→10300, 10000→10000, 15000→9300, 20000→8700, 30000→8000, 50000→7500.
ABS table (km → bp): 0→10000, 150 000→10000, 250 000→9200, 400 000→8500.

`BUV = MSRP × F_age × F_mileage` (two rdiv multiplications).

### 4.3 Condition — `F_condition = interp(COND, C)`, `C = rdiv(6·M + 4·B, 10)`

COND (C → bp): 0→2000, 100→3000, 300→5200, 500→7200, 700→8800, 850→9600, 1000→10000. Not driveable → `min(F, 3000)`.
`CAV = BUV × F_condition`. Mechanical condition is **durable simulated wear**, not native health; native health
only feeds damage events (LSAX-MASTER-SPEC §07).

### 4.4 Bounded adjustments `A` (bp, additive), then clamp `A ∈ [−3500, +1500]`

| Factor | Rule | Per-factor cap |
|---|---|---|
| Accidents (repaired history; unrepaired damage is in condition) | MINOR −200, MODERATE −500, SEVERE −1000, STRUCTURAL −1500 each | per severity: −600 / −1200 / −2000 / −2500; all accidents together ≥ −2500 |
| Service score S | interp: 0→−600, 600→0, 1000→+300; "not yet due" → 0 | [−600, +300] |
| Owners | 1 → +200, 2 → 0, 3 → −200, 4 → −350, ≥5 → −500 | [−500, +200] |
| Originality O | CLASSIC/COLLECTIBLE: 0→−800, 700→0, 1000→+500; others: 0→−400, 500→0, 1000→0 | [−800, +500] |
| Rarity | COMMON 0, UNCOMMON +200, RARE +500, VERY_RARE +800, UNIQUE +1200 | [0, +1200] |
| Recovered stigma | title RECOVERED → −300 | −300 |

`ModValue = min(Σ cost_i × RECOVERY[category_i], 10 % of CAV)`; RECOVERY (bp): PERFORMANCE 3500, ARMOR 4000,
WHEELS 3000, VISUAL 1500, LIVERY 1000, LIGHTING 500. Buyer-profile-specific taste for mods is applied in offers
(LSAX-MASTER-SPEC §15), not in FMV.
`AV = CAV × (10 000 + A) + ModValue`.

### 4.5 Market — `F_market = clamp(10 000 + 0.4·(D − 10 000) − 0.3·(S − 10 000), 8 500, 11 500)`

Liquidity L does not change FMV; it changes spreads (§6) and expected time-to-sale (LSAX-MASTER-SPEC §11).

### 4.6 Regime, band, floor, ceiling, rounding

1. `FMV_raw = AV × F_market`; title SALVAGE → `× 7000 bp`.
2. **Global band:** `FMV_raw` clamped to `[BUV × 0.15, BUV × 1.35]` (no combination of adjustments can move value
   outside this band relative to the structural value).
3. **Floor:** `max($500, MSRP × 5 %)` (scrap value). **Ceiling:** `MSRP × 125 %` (CLASSIC and COLLECTIBLE: 200 %).
4. `FMV = round_money(clamp(band_value, floor, ceiling))`.

## 5. Explainable breakdown

Every valuation returns ordered line items `(code, value, inputs, capped?)`, e.g. `F_age`, `F_mileage`, `BUV`,
`F_condition`, `CAV`, `adj.acc_severe`, `adj.service`, `adj.owners`, `adj.originality`, `adj.rarity`, `A`,
`ModValue`, `AV`, `F_market`, `salvage_regime`, `FMV`. Codes map to localisation keys
`lsax.valuation.line.<code>` (RU/EN). The inspector shows the full breakdown; listings show a disclosed subset.
The breakdown must reconcile: recomputing from its lines gives FMV exactly (T-VAL-5).

## 6. Derived prices

### 6.1 Legal market

| Price | Formula | Bounds |
|---|---|---|
| NPC private asking | `FMV × (1 + m)`, m by seller profile: EAGER 0–300 bp, NORMAL 300–800, GREEDY 800–1200 (seeded) | m ∈ [0, 1200] |
| Dealer retail | `FMV × 1.10` | — |
| Player asking | free input | accepted only in `[FMV × 0.50, FMV × 2.00]` |
| NPC buyer offer | `FMV × (1 − d)`, `d = d_profile + d_liquidity + d_age − d_demand` | d ∈ [−200, 3000] bp; offer ≤ buyer budget |
| Counter-offer | buyer accepts C if `C ≤ reservation = FMV × (1 − d_res)`, else counters `rdiv(offer + C, 2)` capped at reservation; ≤ 3 rounds, then walks away | deterministic per seed |
| Dealer acquisition | `FMV × (1 − spread)`, `spread = interp(L: 0→3000, 10000→1800)` + 500 if C < 400 | spread ∈ [1800, 3500] |

### 6.2 Fees (LSAX-MASTER-SPEC §18) are separate transaction lines, never folded into FMV.

### 6.3 Underground (basis = legal FMV of the vehicle as if titled)

| Buyer | Value | Eligibility |
|---|---|---|
| Fence | `FMV × (1 − haircut)`, haircut COLD 5500, WARM 6200, HOT 7200 bp + velocity surcharge (Heat doc §5), total ≤ 9000 | refuses BURNING and lay-low |
| Chop shop | `BUV × 20 % × max(F_condition, 3000 bp)` | any Heat; daily cap |
| Exporter | `FMV × 40 %` | classes SPORTS/SUPER/LUXURY, Heat ≤ WARM, on current order list |
| Collector | `FMV × 50 %` | rarity ≥ RARE, Heat ≤ HOT |

Property: every underground value < dealer acquisition for the same vehicle (tested over the grid, P7).

## 7. Properties (normative, tested)

P1 non-increasing in odometer; P2 non-decreasing in M and B; P3 non-increasing in accident count; P4 FMV within
[floor, ceiling] and global band; P5 deterministic and breakdown-reconciling; P6 dealer acquisition ≤ 82 % of FMV;
P7 fence < dealer acquisition. Reference run: 4 704-case grid, 0 failures (E8-2).

## 8. Worked vectors = golden test vehicles

Generated by `valuation_ref.py` (evidence/sim/valuation_ref.out.md). Model names are GTA vanilla names; MSRPs are
**LSAX catalogue initial values**, not values read from the game. "FMV/MSRP ✓" = inside the golden range.

| # | Vehicle | MSRP | Age mo | Odo km | M/B | BUV | CAV | A (bp) | FMV | FMV/MSRP | Dealer buys | Fence (tier) | Chop | Export |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V1 | Karin Asterope (commuter sedan, typical) | 26,000 | 36 | 45,000 | 800/780 | 15,600 | 14,494 | +425 | **15,100** | 58.1% ✓ | 11,650 | 6,800 (COLD) | 2,900 | — |
| V2 | Karin Asterope (same model, high mileage) | 26,000 | 36 | 140,000 | 620/600 | 12,436 | 10,068 | −125 | **9,950** | 38.3% ✓ | 7,700 | 4,500 (COLD) | 2,000 | — |
| V3 | Vapid Stanier (ex-fleet sedan) | 32,000 | 96 | 420,000 | 380/420 | 7,069 | 4,355 | −937 | **3,950** | 12.3% ✓ | 2,850 | 1,800 (COLD) | 850 | — |
| V4 | Bravado Buffalo (modified sports, hot demand) | 35,000 | 12 | 12,000 | 950/930 | 26,692 | 26,278 | +500 | **32,950** | 94.1% ✓ | 25,450 | 14,850 (COLD) | 5,250 | 13,200 |
| V5 | Pegassi Zentorno (supercar, near new) | 725,000 | 24 | 6,000 | 980/970 | 544,548 | 541,063 | +1000 | **595,200** | 82.1% ✓ | 434,500 | 267,800 (COLD) | 108,200 | 238,100 |
| V6 | Albany Emperor (neglected beater) | 18,000 | 264 | 310,000 | 300/250 | 2,320 | 1,155 | −2550 | **900** | 5.0% ✓ (floor) | 650 | 400 (COLD) | 250 | — |
| V7 | Declasse Sabre Turbo (classic muscle) | 45,000 | 408 | 90,000 | 750/800 | 22,440 | 20,584 | +417 | **21,450** | 47.7% ✓ | 15,900 | 9,650 (COLD) | 4,100 | — |
| V8 | Benefactor Schafter (luxury, severe repaired accident) | 65,000 | 60 | 80,000 | 720/650 | 22,932 | 20,033 | −1100 | **18,750** | 28.9% ✓ | 14,500 | 8,450 (COLD) | 4,000 | 7,500 |
| V9 | Vapid Speedo (work van, supply glut) | 30,000 | 72 | 260,000 | 550/480 | 9,186 | 6,776 | +188 | **6,400** | 21.3% ✓ | 5,000 | 2,900 (COLD) | 1,350 | — |
| V10 | Grotti Stinger (collectible, pristine) | 850,000 | 540 | 40,000 | 900/920 | 952,310 | 928,978 | +1325 | **1,052,000** | 123.8% ✓ | 755,300 | 473,400 (COLD) | 185,800 | — |
| V11 | Karin Sultan (stolen, vehicle heat 520) | 12,000 | 48 | 60,000 | 700/690 | 6,334 | 5,554 | +0 | **5,550** (basis) | 46.2% ✓ | — (ineligible) | 1,550 (HOT) | 1,100 | — |
| V12 | Karin Asterope (non-driveable wreck, structural) | 26,000 | 120 | 200,000 | 150/100 | 6,544 | 1,963 | −2150 | **1,550** | 6.0% ✓ | 1,100 | 700 (COLD) | 400 | — |

Inputs not shown in the table (service, owners, mods, rarity, market indices) are listed in `valuation_ref.py`
`VECTORS`. Full breakdowns for all 12 are in `evidence/sim/valuation_ref.out.md`. Example (V1):

| Line | Value | Inputs |
|---|---:|---|
| F_age | 6 000 bp | 36 mo, MAINSTREAM |
| F_mileage | 10 000 bp | 45 000 km vs expected 45 000 km (ratio 10 000 bp) |
| BUV | $15 600 | 26 000 × 0.60 × 1.00 |
| F_condition | 9 291 bp | C = 792 (0.6·800 + 0.4·780) |
| CAV | $14 494 | |
| adj.service / adj.owners | +225 / +200 bp | S = 900; 1 owner |
| A | +425 bp | within [−3500, +1500] |
| AV | $15 110 | |
| F_market | 10 000 bp | D = S = 10 000 |
| FMV | **$15 100** | band [2 340, 21 060], floor 1 300, ceiling 32 500, rounded to $50 |

**Golden ranges (FMV/MSRP, bp):** V1 5000–6500, V2 2800–4500, V3 500–1500, V4 8500–11000, V5 7000–8500,
V6 500–1000, V7 3000–5000, V8 2400–3800, V9 1000–2200, V10 9000–14000 (revised, D-VAL-9), V11 4000–6500,
V12 500–700. The C# implementation must match the exact FMVs above while constants are unchanged; after
retuning, the reference model is re-run and the new exact values must stay inside the ranges.

## 9. Tuning procedure (constants are not yet defensible → simulation criteria)

Stage 4 tunes the tables with these simulations (extensions of the Phase 0 reference models):

| ID | Simulation | Acceptance |
|---|---|---|
| T-VAL-SIM-1 | 20 000 NPC-generated vehicles per class (npcgen model) → FMV/MSRP distribution by age band | median per class/band inside target bands (e.g. MAINSTREAM 36–60 mo: 45–60 %; 96–144 mo: 15–30 %; SUPER 0–24 mo: 70–90 %); P10–P90 spread ≥ 15 points (condition/history must matter) |
| T-VAL-SIM-2 | arbitrage: buy at NPC ask, immediately sell to dealer / list at FMV | dealer round-trip loss ≥ 15 % for 100 % of vehicles; list-at-FMV net after fees ≤ ask for 100 % |
| T-VAL-SIM-3 | property grid (P1–P7) | 0 failures |
| T-VAL-SIM-4 | market-step stability: consecutive market steps without vehicle change | |ΔFMV| ≤ 3 % per MT day |
| T-VAL-SIM-5 | golden vectors | all inside ranges |

## 10. Known limitations

- MSRPs for vanilla models are LSAX catalogue data, not read from the game (no such native, E4-3); add-on pricing
  depends on A-VAL-1.
- Repair costs at LS Customs are GTA-owned; LSAX does not price GTA repairs, it only observes them.
