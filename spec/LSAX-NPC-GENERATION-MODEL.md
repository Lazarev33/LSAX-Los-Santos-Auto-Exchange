# LSAX — Correlated NPC Vehicle Generation Model

Document: LSAX-NPC-GENERATION-MODEL.md · Spec: LSAX MASTER SPEC v1.0 DRAFT1 · Status: DRAFT for independent audit

Normative reference implementation: `phase0-probes/sim/npcgen_ref.py`. Structure, causal order, constraints,
determinism and acceptance tests are normative; distribution tables are **INITIAL / TUNABLE**.

## 1. Goal

Generate NPC market vehicles whose attributes are **causally correlated**, not independent random fields, so that
mileage, condition, service, accidents and owners tell one plausible story.

## 2. Determinism and seeding

- PRNG: SplitMix64 (`lsax_ref_math.py`), integer sampling by rejection, inverse-CDF sampling from integer quantile
  tables. No floating point in generation.
- Seed per generated vehicle: `derive_seed("npcgen", campaign_seed, market_day, segment, slot)` (FNV-1a 64 over
  the `|`-joined parts). `market_day = MT_day` of the market step that creates the listing.
- Consequence: after a save/load rewind to an earlier MT day, the market step regenerates **the same** vehicles —
  reloading cannot re-roll offers or inventory (anti-exploit AX-9). Player-caused state differences still change
  outcomes through state, not through re-rolled randomness.
- Test: SHA-256 digest of the first 1 000 MAINSTREAM vehicles for seed (7, day 3) is fixed
  (`d63a888c…6afcb`, evidence/sim/npcgen_ref.out.md); C# must reproduce it (T-GEN-1).

## 3. Causal chain

```
segment ──► Age ──► UsageArchetype | age band, segment eligibility
                        │
                        ▼
                 AnnualKm | archetype × segment scale ──► Odometer | age, jitter ±10 %
                        │                                       │
                        ▼                                       ▼
             Condition (M, B) | odometer, age (saturating 180 mo), archetype care, noise
                        │
                        ▼
             ServiceHistory | archetype, condition band ──► (service feeds back into M: ±60)
                        │
                        ▼
             Accidents | odometer, age, archetype ──► severity, repaired? ──► body hits, salvage title
                        │
                        ▼
             OwnerCount | age, archetype
                        │
                        ▼
             plausibility constraints C1…C9 (reject & resample ≤ 8, else deterministic median fallback)
```

Then (outside the physical-history chain): model choice within segment (catalogue popularity weights), colours
(catalogue colour palette weights), baseline mods (stock except ENTHUSIAST: 60 % chance of 1–4 tasteful mods),
seller profile, asking markup (LSAX-VALUATION-MODEL.md §6.1).

## 4. Tables (initial values)

### 4.1 Age quantiles (months; p in bp)

| Segment | p0 | p2000 | p5000 | p8000 | p9500 | p10000 |
|---|---:|---:|---:|---:|---:|---:|
| MAINSTREAM | 6 | 24 | 72 | 132 | 204 | 300 |
| COMMERCIAL | 6 | 30 | 84 | 144 | 216 | 300 |
| SPORTS | 3 | 18 | 54 | 108 | 180 | 264 |
| LUXURY | 3 | 18 | 48 | 96 | 156 | 240 |
| SUPER | 1 | 8 | 24 | 48 | 84 | 144 |
| CLASSIC | 300 (p0) | 360 (p3000) | 456 (p7000) | 600 (p10000) | | |

### 4.2 Usage archetype weights by age band (LOW_USE, COMMUTER, FLEET, NEGLECTED, ENTHUSIAST); 0 = ineligible

| Segment | < 36 mo | 36–119 | 120–239 | ≥ 240 |
|---|---|---|---|---|
| MAINSTREAM | 15,55,20,5,5 | 15,55,12,13,5 | 15,45,5,30,5 | 25,30,0,40,5 |
| COMMERCIAL | 5,35,55,5,0 | 5,35,45,15,0 | 5,35,25,35,0 | 10,30,10,50,0 |
| SPORTS | 20,35,0,5,40 | 15,40,0,15,30 | 15,35,0,25,25 | 25,20,0,25,30 |
| LUXURY | 25,45,20,0,10 | 20,45,15,10,10 | 20,40,5,25,10 | 30,25,0,30,15 |
| SUPER | 55,10,0,0,35 | 55,10,0,5,30 | 50,10,0,10,30 | 50,5,0,10,35 |
| CLASSIC | 45,10,0,20,25 (all bands) | | | |

### 4.3 Annual km quantiles by archetype (km/yr; p0 / p1000 / p5000 / p9000 / p10000) and segment scale

LOW_USE 1 000 / 2 000 / 4 000 / 7 000 / 9 000 · COMMUTER 6 000 / 10 000 / 15 000 / 20 000 / 28 000 ·
FLEET 15 000 / 25 000 / 35 000 / 50 000 / 70 000 · NEGLECTED 3 000 / 6 000 / 12 000 / 22 000 / 30 000 ·
ENTHUSIAST 1 500 / 3 000 / 6 000 / 10 000 / 14 000.
Segment scale (bp): MAINSTREAM 10 000, COMMERCIAL 13 000, SPORTS 7 500, LUXURY 9 500, SUPER 3 500, CLASSIC 5 000.
`odo = max(20, (annual × max(age,1) / 12) × U[0.90, 1.10])`.

### 4.4 Condition

`M = clamp(1000 − 1.2·odo/1000 − min(age,180) + M_off[arch] + U[−40,40], 150, 1000)`
`B = clamp(1000 − 10·min(age,180)/12 − 0.4·odo/1000 + B_off[arch] + U[−50,50], 100, 1000)`
M_off: LOW_USE +30, COMMUTER 0, FLEET +20, NEGLECTED −150, ENTHUSIAST +80.
B_off: LOW_USE +40, COMMUTER 0, FLEET −30, NEGLECTED −120, ENTHUSIAST +60.
Age wear saturates at 180 months (D-GEN-4, sim-driven: without it maintained classics averaged M = 592).

### 4.5 Service history | archetype, condition

Base compliance p (bp): LOW_USE 8500, COMMUTER 7000, FLEET 9000, NEGLECTED 2500, ENTHUSIAST 9500; −1500 if M < 400,
+500 if M > 800; clamp [500, 9900]. `due = min(max(odo/15 000, age/12), 40)`; `done ~ Binomial(due, p)` (sequential
Bernoulli draws); `S = 1000·done/due` (none due → "not yet due"). Feedback: `M += 60·(S − 500)/500`.

### 4.6 Accidents | odometer, age, archetype

`λ (bp of one accident) = odo × rate[arch] / 100 000 + 17 × age_months`; rate: LOW_USE 4000, COMMUTER 6000,
FLEET 8000, NEGLECTED 10000, ENTHUSIAST 5000. Count = Binomial(20, λ/20) capped at 4 (integer-only Poisson
approximation). Severity weights MINOR 60, MODERATE 28, SEVERE 10, STRUCTURAL 2. Repaired probability: LOW_USE 95 %,
COMMUTER 90 %, FLEET 90 %, NEGLECTED 50 %, ENTHUSIAST 98 %. Body hits unrepaired/repaired: MINOR 40/0, MODERATE
120/20, SEVERE 250/60, STRUCTURAL 400/100. Repaired STRUCTURAL → SALVAGE title with 50 %.

### 4.7 Owners | age, archetype

`age < 12` → 1 (+1 with 3 %); else `1 + Σ_{years} Bernoulli(p_own)`, p_own/yr: LOW_USE 11 %, COMMUTER 20 %,
FLEET 33 %, NEGLECTED 28 %, ENTHUSIAST 16 %; cap 8.

## 5. Plausibility constraints (reject and resample; ≤ 8 attempts; then deterministic median fallback)

| ID | Constraint |
|---|---|
| C1 | `odo ≥ 20 km` and annual rate ≤ 60 000 km/yr (FLEET ≤ 90 000) |
| C2 | age < 12 mo ⇒ owners ≤ 2 ∧ accidents ≤ 1 ∧ (S ≥ 800 or not due) |
| C3 | NEGLECTED ∧ odo > 200 000 ⇒ M < 850 |
| C4 | LOW_USE ⇒ annual rate ≤ 9 000 × segment scale + 1 000 |
| C5 | abs(B − M) ≤ 600 |
| C6 | S ≥ 800 ⇒ M ≥ 400 |
| C7 | STRUCTURAL accident ⇒ SALVAGE title ∨ B ≤ 700 |
| C8 | archetype eligible for the segment (weight > 0, by construction) |
| C9 | owners ≤ 2 + age_months / 36 (D-GEN-5, sim-driven) |

## 6. Verification (reference run, E8-3)

N = 20 000 per segment, seed 1234567, day 42: **0 constraint violations, 0 fallbacks** in every segment.

| Segment | Spearman(age, odo) | Median annual km (archetype: km) | Mean M (archetype: M) | Mean accidents | Mean owners |
|---|---:|---|---|---:|---:|
| MAINSTREAM | 0.744 | COMMUTER 14 966 · LOW_USE 4 037 · FLEET 35 434 · NEGLECTED 12 007 · ENTHUSIAST 6 087 | 827 · 935 · 816 · 541 · 960 | 0.81 | 2.28 |
| COMMERCIAL | 0.707 | FLEET 45 053 · NEGLECTED 15 502 · COMMUTER 19 347 · LOW_USE 5 206 | 708 · 474 · 746 · 910 | 1.46 | 2.65 |
| SPORTS | 0.827 | ENTHUSIAST 4 581 · LOW_USE 3 038 · COMMUTER 11 164 · NEGLECTED 8 871 | 983 · 964 · 876 · 635 | 0.40 | 1.93 |
| LUXURY | 0.731 | COMMUTER 14 181 · LOW_USE 3 791 · FLEET 32 959 · ENTHUSIAST 5 793 · NEGLECTED 11 594 | 875 · 966 · 858 · 978 · 578 | 0.57 | 1.87 |
| SUPER | 0.843 | COMMUTER 5 140 · LOW_USE 1 394 · ENTHUSIAST 2 085 · NEGLECTED 4 544 | 963 · 992 · 999 · 725 | 0.09 | 1.30 |
| CLASSIC | 0.263 | COMMUTER 7 354 · ENTHUSIAST 3 033 · LOW_USE 2 041 · NEGLECTED 6 051 | 522 · 819 · 801 · 361 | 1.52 | 5.86 |

(CLASSIC correlation is weak by design: all are old; usage, not age, drives mileage.)

## 7. Initial mileage / generation examples (seed 1234567, market day 42)

| Slot | Segment | Age mo | Archetype | Odo km | km/yr | M | B | Service | Accidents (severity, repaired) | Title | Owners |
|---|---|---:|---|---:|---:|---:|---:|---:|---|---|---:|
| 0 | MAINSTREAM | 80 | COMMUTER | 41,250 | 6,188 | 890 | 824 | 833 | SEVERE ✓, MODERATE ✓ | CLEAN | 1 |
| 1 | MAINSTREAM | 159 | LOW_USE | 77,874 | 5,877 | 853 | 892 | 846 | — | CLEAN | 3 |
| 2 | MAINSTREAM | 103 | COMMUTER | 94,638 | 11,026 | 815 | 832 | 625 | — | CLEAN | 1 |
| 3 | MAINSTREAM | 116 | COMMUTER | 126,605 | 13,097 | 774 | 897 | 556 | MINOR ✓, MINOR ✓ | CLEAN | 3 |
| 4 | MAINSTREAM | 36 | COMMUTER | 28,655 | 9,552 | 1000 | 938 | 1000 | MINOR ✓ | CLEAN | 1 |
| 5 | MAINSTREAM | 28 | COMMUTER | 33,201 | 14,229 | 951 | 925 | 500 | — | CLEAN | 1 |
| 0 | SPORTS | 70 | ENTHUSIAST | 18,603 | 3,189 | 1000 | 1000 | 1000 | — | CLEAN | 3 |
| 1 | SPORTS | 16 | LOW_USE | 3,457 | 2,593 | 1000 | 1000 | 1000 | — | CLEAN | 1 |
| 0 | COMMERCIAL | 36 | FLEET | 133,704 | 44,568 | 891 | 800 | 1000 | MINOR ✗ | CLEAN | 1 |
| 1 | COMMERCIAL | 191 | NEGLECTED | 139,348 | 8,755 | 446 | 540 | 333 | MODERATE ✓, MINOR ✓, MODERATE ✗ | CLEAN | 1 |
| 0 | CLASSIC | 524 | COMMUTER | 293,226 | 6,715 | 484 | 657 | 750 | MODERATE ✓, SEVERE ✓, MINOR ✓ | CLEAN | 8 |

## 8. Acceptance tests (normative; Stage 6)

T-GEN-1 determinism digest; T-GEN-2 0 violations of C1–C9 in 20 000 per segment; T-GEN-3 fallback rate < 0.5 %;
T-GEN-4 per-archetype median annual km within 15 % of `P50 × scale` (n ≥ 200); T-GEN-5 Spearman(age, odo) ≥ 0.6 for
MAINSTREAM/COMMERCIAL/SPORTS/LUXURY; T-GEN-6 mean M: ENTHUSIAST ≥ 750 and > NEGLECTED; COMMUTER − NEGLECTED ≥ 150;
T-GEN-7 generated FMV distribution meets T-VAL-SIM-1.
