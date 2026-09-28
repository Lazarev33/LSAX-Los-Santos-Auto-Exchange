"""LSAX Phase 0 — correlated NPC vehicle generation reference model (REFERENCE MODEL, NOT PRODUCTION CODE).

Causal chain (LSAX-NPC-GENERATION-MODEL.md §3):
  segment -> Age -> UsageArchetype | age band -> AnnualKm | archetype -> Odometer -> Condition(M,B) | age, odo, archetype
          -> ServiceHistory | archetype, condition -> Accidents | odo, age, archetype -> OwnerCount | age, archetype
Integer-only, SplitMix64-seeded, bounded rejection sampling with deterministic fallback.
"""
import hashlib
import json
import sys
from collections import defaultdict

from lsax_ref_math import BP, MASK64, SplitMix64, clamp, derive_seed, interp, mix64, mul_bp, rdiv, unmix64

ARCH = ["LOW_USE", "COMMUTER", "FLEET", "NEGLECTED", "ENTHUSIAST"]
AGE_Q = {  # quantile tables: p_bp -> age months
    "MAINSTREAM": [(0, 6), (2000, 24), (5000, 72), (8000, 132), (9500, 204), (10000, 300)],
    "COMMERCIAL": [(0, 6), (2000, 30), (5000, 84), (8000, 144), (9500, 216), (10000, 300)],
    "SPORTS": [(0, 3), (2000, 18), (5000, 54), (8000, 108), (9500, 180), (10000, 264)],
    "LUXURY": [(0, 3), (2000, 18), (5000, 48), (8000, 96), (9500, 156), (10000, 240)],
    "SUPER": [(0, 1), (2000, 8), (5000, 24), (8000, 48), (9500, 84), (10000, 144)],
    "CLASSIC": [(0, 300), (3000, 360), (7000, 456), (10000, 600)],
}
ARCH_W = {  # per segment, per age band (A0 <36, A1 <120, A2 <240, A3 >=240): weights in ARCH order; 0 = ineligible
    "MAINSTREAM": [(15, 55, 20, 5, 5), (15, 55, 12, 13, 5), (15, 45, 5, 30, 5), (25, 30, 0, 40, 5)],
    "COMMERCIAL": [(5, 35, 55, 5, 0), (5, 35, 45, 15, 0), (5, 35, 25, 35, 0), (10, 30, 10, 50, 0)],
    "SPORTS": [(20, 35, 0, 5, 40), (15, 40, 0, 15, 30), (15, 35, 0, 25, 25), (25, 20, 0, 25, 30)],
    "LUXURY": [(25, 45, 20, 0, 10), (20, 45, 15, 10, 10), (20, 40, 5, 25, 10), (30, 25, 0, 30, 15)],
    "SUPER": [(55, 10, 0, 0, 35), (55, 10, 0, 5, 30), (50, 10, 0, 10, 30), (50, 5, 0, 10, 35)],
    "CLASSIC": [(45, 10, 0, 20, 25)] * 4,
}
KM_Q = {  # annual km quantile tables by archetype
    "LOW_USE": [(0, 1000), (1000, 2000), (5000, 4000), (9000, 7000), (10000, 9000)],
    "COMMUTER": [(0, 6000), (1000, 10000), (5000, 15000), (9000, 20000), (10000, 28000)],
    "FLEET": [(0, 15000), (1000, 25000), (5000, 35000), (9000, 50000), (10000, 70000)],
    "NEGLECTED": [(0, 3000), (1000, 6000), (5000, 12000), (9000, 22000), (10000, 30000)],
    "ENTHUSIAST": [(0, 1500), (1000, 3000), (5000, 6000), (9000, 10000), (10000, 14000)],
}
SEG_KM_SCALE = {"MAINSTREAM": 10000, "COMMERCIAL": 13000, "SPORTS": 7500, "LUXURY": 9500, "SUPER": 3500, "CLASSIC": 5000}
M_OFF = {"LOW_USE": 30, "COMMUTER": 0, "FLEET": 20, "NEGLECTED": -150, "ENTHUSIAST": 80}
B_OFF = {"LOW_USE": 40, "COMMUTER": 0, "FLEET": -30, "NEGLECTED": -120, "ENTHUSIAST": 60}
SERVICE_P = {"LOW_USE": 8500, "COMMUTER": 7000, "FLEET": 9000, "NEGLECTED": 2500, "ENTHUSIAST": 9500}
ACC_RATE_PER_100K = {"LOW_USE": 4000, "COMMUTER": 6000, "FLEET": 8000, "NEGLECTED": 10000, "ENTHUSIAST": 5000}  # bp of 1 accident
ACC_AGE_BP_PER_MONTH = 17
SEVERITY_W = [("MINOR", 60), ("MODERATE", 28), ("SEVERE", 10), ("STRUCTURAL", 2)]
REPAIR_P = {"LOW_USE": 9500, "COMMUTER": 9000, "FLEET": 9000, "NEGLECTED": 5000, "ENTHUSIAST": 9800}
B_HIT_UNREPAIRED = {"MINOR": 40, "MODERATE": 120, "SEVERE": 250, "STRUCTURAL": 400}
B_HIT_REPAIRED = {"MINOR": 0, "MODERATE": 20, "SEVERE": 60, "STRUCTURAL": 100}
OWNER_P_PER_YEAR = {"LOW_USE": 1100, "COMMUTER": 2000, "FLEET": 3300, "NEGLECTED": 2800, "ENTHUSIAST": 1600}
MAX_RETRIES = 8
AGE_WEAR_CAP_MONTHS = 180  # D-GEN-4: age wear saturates at 15 years; beyond that care (archetype) dominates


def band(age):
    return 0 if age < 36 else 1 if age < 120 else 2 if age < 240 else 3


def generate_once(rng: SplitMix64, seg: str):
    age = rng.quantile(AGE_Q[seg])
    w = ARCH_W[seg][band(age)]
    arch = rng.pick_weighted(list(zip(ARCH, w)))
    annual = mul_bp(rng.quantile(KM_Q[arch]), SEG_KM_SCALE[seg])
    odo = rdiv(annual * max(age, 1), 12)
    odo = max(20, mul_bp(odo, 9000 + rng.below(2001)))
    mech = 1000 - rdiv(odo * 12, 10000) - min(age, AGE_WEAR_CAP_MONTHS) + M_OFF[arch] + rng.range_incl(-40, 40)
    mech = clamp(mech, 150, 1000)
    body = 1000 - rdiv(min(age, AGE_WEAR_CAP_MONTHS) * 10, 12) - rdiv(odo * 4, 10000) + B_OFF[arch] + rng.range_incl(-50, 50)
    body = clamp(body, 100, 1000)
    # service | archetype, condition
    p = SERVICE_P[arch] + (-1500 if mech < 400 else 500 if mech > 800 else 0)
    p = clamp(p, 500, 9900)
    due = min(max(rdiv(odo, 15000), age // 12), 40)
    service = None
    if due > 0:
        done = sum(1 for _ in range(due) if rng.chance_bp(p))
        service = rdiv(done * 1000, due)
        mech = clamp(mech + rdiv(60 * (service - 500), 500), 150, 1000)
    # accidents | odo, age, archetype  (binomial(20, lambda/20) approximation, integer only)
    lam = rdiv(odo * ACC_RATE_PER_100K[arch], 100000) + age * ACC_AGE_BP_PER_MONTH
    p_acc = min(rdiv(lam, 20), 5000)
    n_acc = min(sum(1 for _ in range(20) if rng.chance_bp(p_acc)), 4)
    accidents, title = [], "CLEAN_TITLE"
    for _ in range(n_acc):
        sev = rng.pick_weighted(SEVERITY_W)
        repaired = rng.chance_bp(REPAIR_P[arch])
        body -= (B_HIT_REPAIRED if repaired else B_HIT_UNREPAIRED)[sev]
        if sev == "STRUCTURAL" and repaired and rng.chance_bp(5000):
            title = "SALVAGE_TITLE"
        accidents.append((sev, repaired))
    body = clamp(body, 100, 1000)
    # owners | age, archetype
    if age < 12:
        owners = 1 + (1 if rng.chance_bp(300) else 0)
    else:
        owners = min(1 + sum(1 for _ in range(age // 12) if rng.chance_bp(OWNER_P_PER_YEAR[arch])), 8)
    return dict(segment=seg, age_months=age, archetype=arch, annual_km=annual, odo_km=odo, mech=mech, body=body,
                service=service, accidents=accidents, title=title, owners=owners)


def violations(v):
    out = []
    years_x10 = max(v["age_months"], 1)
    max_annual = 90000 if v["archetype"] == "FLEET" else 60000
    if v["odo_km"] < 20 or rdiv(v["odo_km"] * 12, years_x10) > max_annual:
        out.append("C1")
    if v["age_months"] < 12 and (v["owners"] > 2 or len(v["accidents"]) > 1 or (v["service"] is not None and v["service"] < 800)):
        out.append("C2")
    if v["archetype"] == "NEGLECTED" and v["odo_km"] > 200000 and v["mech"] >= 850:
        out.append("C3")
    if v["archetype"] == "LOW_USE" and rdiv(v["odo_km"] * 12, years_x10) > mul_bp(9000, SEG_KM_SCALE[v["segment"]]) + 1000:
        out.append("C4")
    if abs(v["body"] - v["mech"]) > 600:
        out.append("C5")
    if v["service"] is not None and v["service"] >= 800 and v["mech"] < 400:
        out.append("C6")
    if any(s == "STRUCTURAL" for s, _ in v["accidents"]) and v["title"] != "SALVAGE_TITLE" and v["body"] > 700:
        out.append("C7")
    if v["owners"] > 2 + v["age_months"] // 36:
        out.append("C9")  # D-GEN-5: owner count plausibility (e.g. no 4 owners at 50 months)
    return out


def fallback(seg, rng):
    """Deterministic median profile (used only when MAX_RETRIES are exhausted)."""
    age = interp(AGE_Q[seg], 5000)
    arch = ARCH[max(range(5), key=lambda i: ARCH_W[seg][band(age)][i])]
    annual = mul_bp(interp(KM_Q[arch], 5000), SEG_KM_SCALE[seg])
    odo = rdiv(annual * max(age, 1), 12)
    mech = clamp(1000 - rdiv(odo * 12, 10000) - min(age, AGE_WEAR_CAP_MONTHS) + M_OFF[arch], 150, 1000)
    body = clamp(1000 - rdiv(min(age, AGE_WEAR_CAP_MONTHS) * 10, 12) - rdiv(odo * 4, 10000) + B_OFF[arch], 100, 1000)
    due = min(max(rdiv(odo, 15000), age // 12), 40)
    return dict(segment=seg, age_months=age, archetype=arch, annual_km=annual, odo_km=odo, mech=mech, body=body,
                service=(700 if due else None), accidents=[], title="CLEAN_TITLE", owners=min(1 + age // 60, 2 + age // 36), fallback=True)


# ---------------------------------------------------------------- generation identity (DRAFT2, D-GEN-6, audit P1-05)
STEP_BITS, SEG_BITS, ORD_BITS = 40, 4, 20            # 40 + 4 + 20 = 64
SEGMENT_CODE = {seg: code for code, seg in enumerate(AGE_Q)}  # stable order of the segment tables (<= 16 segments)
assert len(SEGMENT_CODE) <= (1 << SEG_BITS)
GENERATED_NS = 1 << 63                               # top bit of high64: generated namespace (registered ids clear it)


def pack_identity(step_index, seg, ordinal):
    """Injective packing of the generation identity (market_step_index, segment, generation_ordinal).
    Out-of-range components are refused (never wrapped)."""
    code = SEGMENT_CODE[seg]
    if not (0 <= step_index < (1 << STEP_BITS) and 0 <= ordinal < (1 << ORD_BITS) and 0 <= code < (1 << SEG_BITS)):
        raise ValueError("generation identity out of range")
    return (step_index << (SEG_BITS + ORD_BITS)) | (code << ORD_BITS) | ordinal


def unpack_identity(v):
    code = (v >> ORD_BITS) & ((1 << SEG_BITS) - 1)
    seg = next(k for k, c in SEGMENT_CODE.items() if c == code)
    return v >> (SEG_BITS + ORD_BITS), seg, v & ((1 << ORD_BITS) - 1)


def vehicle_id(campaign_salt, step_index, seg, ordinal):
    """128-bit VehicleId = high64 (campaign salt, generated namespace bit set) | low64 = mix64(packed identity).
    Injective within a campaign by construction (packing injective, mix64 bijective)."""
    high = (campaign_salt | GENERATED_NS) & MASK64
    return (high << 64) | mix64(pack_identity(step_index, seg, ordinal))


def identity_of(vid):
    return unpack_identity(unmix64(vid & MASK64))


def draft1_vehicle_id(campaign_seed, market_day, seg, slot):
    """DRAFT1 DOMAIN §4.1: derive_seed("vehicle", campaign_seed, market_day, segment, slot) (audit P1-05 defect)."""
    return derive_seed("vehicle", campaign_seed, market_day, seg, slot)


def generate(campaign_seed, market_step_index, seg, generation_ordinal):
    """Vehicle attributes for generation identity (campaign_seed, market_step_index, segment, generation_ordinal).
    Deterministic: the same identity always yields the same vehicle (re-roll protection)."""
    rng = SplitMix64(derive_seed("npcgen", campaign_seed, market_step_index, seg, generation_ordinal))
    for attempt in range(MAX_RETRIES):
        v = generate_once(rng, seg)
        if not violations(v):
            v["attempts"] = attempt + 1
            return v
    v = fallback(seg, rng)
    v["attempts"] = MAX_RETRIES
    return v


def spearman(xs, ys):
    def ranks(a):
        order = sorted(range(len(a)), key=lambda i: a[i])
        r = [0] * len(a)
        for rank, i in enumerate(order):
            r[i] = rank
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1 - 6 * d2 / (n * (n * n - 1))  # analysis only (float allowed in tests, never in gameplay)


def main():
    N = 20000
    fails = []
    stats = {}
    for seg in AGE_Q:
        vs = [generate(1234567, 42, seg, i) for i in range(N)]
        viol = sum(1 for v in vs if violations(v))
        fb = sum(1 for v in vs if v.get("fallback"))
        by_arch = defaultdict(list)
        for v in vs:
            by_arch[v["archetype"]].append(v)
        med_annual = {}
        for a, lst in by_arch.items():
            rates = sorted(rdiv(v["odo_km"] * 12, max(v["age_months"], 1)) for v in lst)
            med_annual[a] = rates[len(rates) // 2]
            target = mul_bp(interp(KM_Q[a], 5000), SEG_KM_SCALE[seg])
            if len(lst) >= 200 and abs(med_annual[a] - target) * 100 > 15 * target:
                fails.append(f"{seg}/{a}: median annual {med_annual[a]} vs target {target} (>15%)")
        rho = spearman([v["age_months"] for v in vs], [v["odo_km"] for v in vs])
        if seg in ("MAINSTREAM", "COMMERCIAL", "LUXURY", "SPORTS") and rho < 0.6:
            fails.append(f"{seg}: spearman(age,odo)={rho:.2f} < 0.6")
        mean_m = {a: sum(v["mech"] for v in lst) // len(lst) for a, lst in by_arch.items() if lst}
        if "ENTHUSIAST" in mean_m and "NEGLECTED" in mean_m and not mean_m["ENTHUSIAST"] > mean_m["NEGLECTED"]:
            fails.append(f"{seg}: mean mech ENTHUSIAST <= NEGLECTED")
        if viol:
            fails.append(f"{seg}: {viol} constraint violations after generation")
        if "ENTHUSIAST" in mean_m and mean_m["ENTHUSIAST"] < 750:
            fails.append(f"{seg}: mean mech ENTHUSIAST {mean_m['ENTHUSIAST']} < 750 (care must dominate age)")
        if "COMMUTER" in mean_m and "NEGLECTED" in mean_m and mean_m["COMMUTER"] - mean_m["NEGLECTED"] < 150:
            fails.append(f"{seg}: COMMUTER-NEGLECTED mech gap < 150")
        if fb * 1000 > 5 * N:
            fails.append(f"{seg}: fallback rate {fb}/{N} > 0.5%")
        stats[seg] = dict(n=N, violations=viol, fallbacks=fb, spearman_age_odo=round(rho, 3),
                          archetype_share={a: len(l) for a, l in sorted(by_arch.items())},
                          median_annual_km=med_annual, mean_mech=mean_m,
                          mean_accidents=round(sum(len(v["accidents"]) for v in vs) / N, 3),
                          mean_owners=round(sum(v["owners"] for v in vs) / N, 2),
                          salvage_share=sum(1 for v in vs if v["title"] == "SALVAGE_TITLE"))
    # determinism: identical digest for two independent runs of the same seeds
    d1 = hashlib.sha256(json.dumps([generate(7, 3, "MAINSTREAM", i) for i in range(1000)], sort_keys=True).encode()).hexdigest()
    d2 = hashlib.sha256(json.dumps([generate(7, 3, "MAINSTREAM", i) for i in range(1000)], sort_keys=True).encode()).hexdigest()
    if d1 != d2:
        fails.append("determinism digest mismatch")

    print("### Distribution summary (N=20,000 per segment, campaign_seed=1234567, market_step_index=42)\n")
    print("| Segment | Violations | Fallbacks | Spearman(age,odo) | Archetype counts | Median annual km by archetype | Mean M by archetype | Mean accidents | Mean owners | Salvage |")
    print("|---|---:|---:|---:|---|---|---|---:|---:|---:|")
    for seg, s in stats.items():
        print(f"| {seg} | {s['violations']} | {s['fallbacks']} | {s['spearman_age_odo']} | {s['archetype_share']} | "
              f"{s['median_annual_km']} | {s['mean_mech']} | {s['mean_accidents']} | {s['mean_owners']} | {s['salvage_share']} |")
    print("\n### Example generated vehicles (campaign seed 1234567, market step 42, MAINSTREAM ordinals 0..5, SPORTS 0..1, COMMERCIAL 0..1, CLASSIC 0)\n")
    print("| Ordinal | Seg | Age mo | Archetype | Odo km | km/yr | M | B | Service | Accidents (sev, repaired) | Title | Owners | Attempts |")
    print("|---|---|---:|---|---:|---:|---:|---:|---:|---|---|---:|---:|")
    for seg, slots in (("MAINSTREAM", range(6)), ("SPORTS", range(2)), ("COMMERCIAL", range(2)), ("CLASSIC", range(1))):
        for i in slots:
            v = generate(1234567, 42, seg, i)
            print(f"| {i} | {seg} | {v['age_months']} | {v['archetype']} | {v['odo_km']:,} | {rdiv(v['odo_km']*12, max(v['age_months'],1)):,} | "
                  f"{v['mech']} | {v['body']} | {v['service'] if v['service'] is not None else 'n/due'} | {v['accidents'] or '—'} | {v['title']} | {v['owners']} | {v['attempts']} |")
    print(f"\nDeterminism digest (campaign seed 7, market step 3, MAINSTREAM ordinals 0..999): `{d1}`")
    print("RESULT:", "PASS" if not fails else "FAIL")
    for f in fails:
        print("  -", f)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
