"""LSAX Phase 0 — valuation reference model (REFERENCE MODEL, NOT PRODUCTION CODE).

Implements LSAX-VALUATION-MODEL.md exactly, using only lsax_ref_math integer arithmetic.
Outputs: worked vectors (markdown), golden-range checks, property tests. Exit code != 0 on any failure.
All constants are INITIAL TUNABLE VALUES (see LSAX-VALUATION-MODEL.md §9 for the tuning procedure).
"""
import json
import sys
from dataclasses import dataclass, field
from typing import List, Optional

from lsax_ref_math import BP, clamp, interp, mul_bp, rdiv, round_money

# ---------------------------------------------------------------- tunable tables (bp unless noted)
AGE_CURVES = {  # age in MT months -> retention bp
    "MAINSTREAM": [(0, 9000), (12, 7800), (24, 6800), (36, 6000), (60, 4700), (96, 3300), (144, 2200), (240, 1500), (360, 1200)],
    "LUXURY": [(0, 8800), (12, 7200), (24, 6000), (36, 5000), (60, 3600), (96, 2400), (144, 1600), (240, 1200), (360, 1000)],
    "SPORTS": [(0, 9000), (12, 8000), (24, 7100), (36, 6400), (60, 5200), (96, 4000), (144, 3000), (240, 2400), (360, 2400)],
    "SUPER": [(0, 9200), (12, 8200), (24, 7400), (36, 6800), (60, 5800), (96, 5000), (144, 4500), (240, 4500), (360, 4500)],
    "COMMERCIAL": [(0, 8800), (12, 7400), (24, 6300), (36, 5400), (60, 4000), (96, 2700), (144, 1800), (240, 1200), (360, 1000)],
    "CLASSIC": [(0, 9000), (12, 7800), (24, 6800), (36, 6000), (60, 4700), (96, 3300), (144, 2500), (240, 2600), (300, 3500), (420, 5000), (600, 5500)],
    "COLLECTIBLE": [(0, 9200), (24, 8000), (60, 7000), (120, 6800), (240, 7500), (360, 9000), (480, 10500), (600, 11000)],
}
ANNUAL_KM = {"MAINSTREAM": 15000, "LUXURY": 14000, "SPORTS": 9000, "SUPER": 4000, "COMMERCIAL": 30000, "CLASSIC": 5000, "COLLECTIBLE": 3000}
MILEAGE_RATIO = [(0, 10600), (5000, 10300), (10000, 10000), (15000, 9300), (20000, 8700), (30000, 8000), (50000, 7500)]  # x = odo/expected in bp
MILEAGE_ABS = [(0, 10000), (150000, 10000), (250000, 9200), (400000, 8500)]  # x = km
F_MILEAGE_BOUNDS = (6400, 10600)
CONDITION = [(0, 2000), (100, 3000), (300, 5200), (500, 7200), (700, 8800), (850, 9600), (1000, 10000)]  # x = C (0..1000)
NOT_DRIVEABLE_COND_CAP = 3000
ACC_EACH = {"MINOR": -200, "MODERATE": -500, "SEVERE": -1000, "STRUCTURAL": -1500}
ACC_CAP = {"MINOR": -600, "MODERATE": -1200, "SEVERE": -2000, "STRUCTURAL": -2500}
ACC_TOTAL_CAP = -2500
SERVICE = [(0, -600), (600, 0), (1000, 300)]
OWNERS = {1: 200, 2: 0, 3: -200, 4: -350}
OWNERS_5PLUS = -500
MOD_RECOVERY = {"PERFORMANCE": 3500, "ARMOR": 4000, "WHEELS": 3000, "VISUAL": 1500, "LIVERY": 1000, "LIGHTING": 500}
MOD_CAP_OF_CAV = 1000
ORIGINALITY_COLLECTIBLE = [(0, -800), (700, 0), (1000, 500)]
ORIGINALITY_OTHER = [(0, -400), (500, 0), (1000, 0)]
RARITY = {"COMMON": 0, "UNCOMMON": 200, "RARE": 500, "VERY_RARE": 800, "UNIQUE": 1200}
RECOVERED_STIGMA = -300
ADJ_BOUNDS = (-3500, 1500)
MARKET_BOUNDS = (8500, 11500)
GLOBAL_FACTOR_BOUNDS = (1500, 13500)  # FMV_raw / BUV
FLOOR_MSRP_BP, FLOOR_MIN = 500, 500
CEILING_BP = {"default": 12500, "CLASSIC": 20000, "COLLECTIBLE": 20000}
SALVAGE_REGIME = 7000
DEALER_SPREAD_BY_LIQ = [(0, 3000), (10000, 1800)]  # x = liquidity bp
DEALER_POOR_COND_EXTRA = 500  # if C < 400
DEALER_RETAIL_MARKUP = 1000
HEAT_TIERS = [(0, "COLD"), (200, "WARM"), (450, "HOT"), (750, "BURNING")]
FENCE_HAIRCUT = {"COLD": 5500, "WARM": 6200, "HOT": 7200}  # BURNING: fence refuses
CHOP_OF_BUV = 2000
EXPORT_OF_FMV = 4000
EXPORT_CLASSES = {"SPORTS", "SUPER", "LUXURY"}


@dataclass
class Vehicle:
    label: str
    model: str
    klass: str
    msrp: int
    age_months: int
    odo_km: int
    mech: int  # 0..1000
    body: int  # 0..1000
    driveable: bool = True
    accidents: List[str] = field(default_factory=list)
    service: Optional[int] = None  # None = no service due yet
    owners: int = 1
    mods: List[tuple] = field(default_factory=list)  # (category, cost $)
    originality: int = 1000
    rarity: str = "COMMON"
    provenance: str = "CLEAN_TITLE"
    demand_bp: int = 10000
    supply_bp: int = 10000
    liquidity_bp: int = 6000
    vehicle_heat: int = 0
    player_heat: int = 0


def heat_tier(h: int) -> str:
    t = "COLD"
    for lo, name in HEAT_TIERS:
        if h >= lo:
            t = name
    return t


def value(v: Vehicle):
    lines = []
    f_age = interp(AGE_CURVES[v.klass], v.age_months)
    expected_km = rdiv(ANNUAL_KM[v.klass] * max(v.age_months, 3), 12)
    ratio_bp = rdiv(v.odo_km * BP, max(expected_km, 1))
    f_mil = clamp(mul_bp(interp(MILEAGE_RATIO, ratio_bp), interp(MILEAGE_ABS, v.odo_km)), *F_MILEAGE_BOUNDS)
    buv = mul_bp(mul_bp(v.msrp, f_age), f_mil)
    lines.append(("F_age", f_age, f"age={v.age_months}mo class={v.klass}"))
    lines.append(("F_mileage", f_mil, f"odo={v.odo_km}km expected={expected_km}km ratio={ratio_bp}bp"))
    lines.append(("BUV", buv, "MSRP*F_age*F_mileage"))

    c = rdiv(6 * v.mech + 4 * v.body, 10)
    f_cond = interp(CONDITION, c)
    if not v.driveable:
        f_cond = min(f_cond, NOT_DRIVEABLE_COND_CAP)
    cav = mul_bp(buv, f_cond)
    lines.append(("F_condition", f_cond, f"C={c} (0.6*M{v.mech}+0.4*B{v.body}) driveable={v.driveable}"))
    lines.append(("CAV", cav, "BUV*F_condition"))

    adj = []
    for sev in ACC_EACH:
        n = sum(1 for a in v.accidents if a == sev)
        if n:
            adj.append((f"acc_{sev.lower()}", max(ACC_EACH[sev] * n, ACC_CAP[sev])))
    acc_total = sum(a for k, a in adj if k.startswith("acc_"))
    if acc_total < ACC_TOTAL_CAP:
        adj = [(k, a) for k, a in adj if not k.startswith("acc_")] + [("acc_total_capped", ACC_TOTAL_CAP)]
    adj.append(("service", 0 if v.service is None else interp(SERVICE, v.service)))
    adj.append(("owners", OWNERS.get(v.owners, OWNERS_5PLUS)))
    collectible = v.klass in ("CLASSIC", "COLLECTIBLE")
    adj.append(("originality", interp(ORIGINALITY_COLLECTIBLE if collectible else ORIGINALITY_OTHER, v.originality)))
    adj.append(("rarity", RARITY[v.rarity]))
    if v.provenance == "RECOVERED":
        adj.append(("recovered_stigma", RECOVERED_STIGMA))
    a_raw = sum(a for _, a in adj)
    a = clamp(a_raw, *ADJ_BOUNDS)
    for k, x in adj:
        lines.append((f"adj.{k}", x, "bp"))
    lines.append(("A", a, f"sum={a_raw}bp clamped to {ADJ_BOUNDS}"))

    mod_raw = sum(rdiv(cost * MOD_RECOVERY[cat], BP) for cat, cost in v.mods)
    mod_val = min(mod_raw, mul_bp(cav, MOD_CAP_OF_CAV))
    av = mul_bp(cav, BP + a) + mod_val
    lines.append(("ModValue", mod_val, f"raw={mod_raw} cap={mul_bp(cav, MOD_CAP_OF_CAV)}"))
    lines.append(("AV", av, "CAV*(1+A)+ModValue"))

    f_mkt = clamp(BP + rdiv(4 * (v.demand_bp - BP), 10) - rdiv(3 * (v.supply_bp - BP), 10), *MARKET_BOUNDS)
    fmv_raw = mul_bp(av, f_mkt)
    lines.append(("F_market", f_mkt, f"D={v.demand_bp} S={v.supply_bp}"))
    if v.provenance == "SALVAGE_TITLE":
        fmv_raw = mul_bp(fmv_raw, SALVAGE_REGIME)
        lines.append(("salvage_regime", SALVAGE_REGIME, "bp"))
    lo_g, hi_g = mul_bp(buv, GLOBAL_FACTOR_BOUNDS[0]), mul_bp(buv, GLOBAL_FACTOR_BOUNDS[1])
    fmv_g = clamp(fmv_raw, lo_g, hi_g)
    floor = max(FLOOR_MIN, mul_bp(v.msrp, FLOOR_MSRP_BP))
    ceiling = mul_bp(v.msrp, CEILING_BP.get(v.klass, CEILING_BP["default"]))
    fmv = round_money(clamp(fmv_g, floor, ceiling))
    lines.append(("FMV", fmv, f"raw={fmv_raw} globalBand=[{lo_g},{hi_g}] floor={floor} ceiling={ceiling} rounded"))

    liq_spread = interp(DEALER_SPREAD_BY_LIQ, v.liquidity_bp) + (DEALER_POOR_COND_EXTRA if c < 400 else 0)
    legal = v.provenance in ("CLEAN_TITLE", "SALVAGE_TITLE", "RECOVERED")          # no LEGACY title (D-PROV-1); UNKNOWN never legal
    out = {"label": v.label, "model": v.model, "msrp": v.msrp, "BUV": buv, "CAV": cav, "AV": av, "FMV": fmv, "C": c,
           "legal_eligible": legal,
           "dealer_acquisition": round_money(mul_bp(fmv, BP - liq_spread)) if legal else None,
           "dealer_retail": round_money(mul_bp(fmv, BP + DEALER_RETAIL_MARKUP)) if legal else None,
           "lines": lines}
    eff_heat = max(v.vehicle_heat, rdiv(v.player_heat, 2))
    tier = heat_tier(eff_heat)
    out["heat_tier"] = tier
    out["fence"] = round_money(mul_bp(fmv, BP - FENCE_HAIRCUT[tier])) if tier in FENCE_HAIRCUT else None
    out["chop"] = round_money(mul_bp(mul_bp(buv, CHOP_OF_BUV), max(f_cond, 3000)))
    out["export"] = round_money(mul_bp(fmv, EXPORT_OF_FMV)) if v.klass in EXPORT_CLASSES and tier in ("COLD", "WARM") else None
    return out


VECTORS = [
    Vehicle("V1 commuter sedan, typical", "Karin Asterope", "MAINSTREAM", 26000, 36, 45000, 800, 780, service=900),
    Vehicle("V2 same model, high mileage", "Karin Asterope", "MAINSTREAM", 26000, 36, 140000, 620, 600, accidents=["MINOR"], service=700, owners=2),
    Vehicle("V3 ex-fleet sedan", "Vapid Stanier", "MAINSTREAM", 32000, 96, 420000, 380, 420, accidents=["MODERATE", "MODERATE"], service=950, owners=3),
    Vehicle("V4 modified sports, hot demand", "Bravado Buffalo", "SPORTS", 35000, 12, 12000, 950, 930, service=1000, mods=[("PERFORMANCE", 18000)], demand_bp=11500, supply_bp=9000),
    Vehicle("V5 supercar, near new", "Pegassi Zentorno", "SUPER", 725000, 24, 6000, 980, 970, service=1000, rarity="RARE", liquidity_bp=2500),
    Vehicle("V6 neglected beater", "Albany Emperor", "MAINSTREAM", 18000, 264, 310000, 300, 250, accidents=["MINOR", "MINOR", "MINOR", "SEVERE"], service=150, owners=6),
    Vehicle("V7 classic muscle", "Declasse Sabre Turbo", "CLASSIC", 45000, 408, 90000, 750, 800, service=800, owners=4, originality=950, rarity="UNCOMMON", liquidity_bp=3500),
    Vehicle("V8 luxury, severe repaired accident", "Benefactor Schafter", "LUXURY", 65000, 60, 80000, 720, 650, accidents=["SEVERE"], service=500, owners=2, mods=[("VISUAL", 6000)]),
    Vehicle("V9 work van, supply glut", "Vapid Speedo", "COMMERCIAL", 30000, 72, 260000, 550, 480, service=850, owners=2, supply_bp=12500, liquidity_bp=7000),
    Vehicle("V10 collectible, pristine", "Grotti Stinger", "COLLECTIBLE", 850000, 540, 40000, 900, 920, service=900, owners=3, originality=1000, rarity="VERY_RARE", liquidity_bp=1500),
    Vehicle("V11 stolen sports compact (hot)", "Karin Sultan", "SPORTS", 12000, 48, 60000, 700, 690, service=600, owners=2, provenance="STOLEN", vehicle_heat=520),
    Vehicle("V12 non-driveable wreck", "Karin Asterope", "MAINSTREAM", 26000, 120, 200000, 150, 100, driveable=False, accidents=["STRUCTURAL"], service=300, owners=4),
]

# Golden ranges: design-intent plausibility as FMV/MSRP (bp). The canonical implementation must ALSO match the
# exact reference FMV (regression). Ranges are the tuning acceptance criteria (LSAX-VALUATION-MODEL.md §9).
GOLDEN_RANGES_BP = {
    "V1": (5000, 6500), "V2": (2800, 4500), "V3": (500, 1500), "V4": (8500, 11000), "V5": (7000, 8500),
    "V6": (500, 1000), "V7": (3000, 5000), "V8": (2400, 3800), "V9": (1000, 2200),
    # V10 revised in Phase 0 after first run (was 7500..11000): appreciation above MSRP is intended for
    # COLLECTIBLE (ceiling 200%); see decisions.md D-VAL-9.
    "V10": (9000, 14000),
    "V11": (4000, 6500), "V12": (500, 700),
}


def property_tests():
    failures = []
    base = VECTORS[0]
    prev = None
    for odo in range(0, 600001, 5000):
        r = value(Vehicle(**{**base.__dict__, "odo_km": odo}))["FMV"]
        if prev is not None and r > prev:
            failures.append(f"P1 mileage monotonic violated at {odo}: {r}>{prev}")
        prev = r
    for m in range(0, 1001, 25):
        prev = None
        for b in range(0, 1001, 25):
            r = value(Vehicle(**{**base.__dict__, "mech": m, "body": b}))["FMV"]
            if prev is not None and r < prev:
                failures.append(f"P2 condition monotonic violated M={m} B={b}")
            prev = r
    prev = None
    for n in range(0, 6):
        r = value(Vehicle(**{**base.__dict__, "accidents": ["MODERATE"] * n}))["FMV"]
        if prev is not None and r > prev:
            failures.append(f"P3 accident monotonic violated n={n}")
        prev = r
    grid = 0
    for klass in AGE_CURVES:
        for age in (0, 6, 24, 60, 120, 240, 480):
            for odo in (0, 20000, 150000, 500000):
                for c in (0, 300, 700, 1000):
                    for acc in ([], ["SEVERE", "SEVERE", "STRUCTURAL"]):
                        for dem, sup in ((7000, 13000), (13000, 7000), (10000, 10000)):
                            v = Vehicle("grid", "g", klass, 50000, age, odo, c, c, accidents=acc, service=0, owners=7,
                                        demand_bp=dem, supply_bp=sup, liquidity_bp=0, mods=[("ARMOR", 10**6)])
                            o = value(v)
                            grid += 1
                            floor = max(FLOOR_MIN, mul_bp(v.msrp, FLOOR_MSRP_BP))
                            ceiling = mul_bp(v.msrp, CEILING_BP.get(klass, CEILING_BP["default"]))
                            if not (round_money(floor) <= o["FMV"] <= round_money(ceiling)):
                                failures.append(f"P4 bounds {klass} {age} {odo} {c}: {o['FMV']}")
                            if o["dealer_acquisition"] > mul_bp(o["FMV"], 8200) + 100:
                                failures.append(f"P6 dealer spread too small {klass}")
                            if o["fence"] is not None and o["fence"] >= o["dealer_acquisition"]:
                                failures.append(f"P7 fence >= dealer {klass}")
    a, b = value(VECTORS[4]), value(VECTORS[4])
    if json.dumps(a) != json.dumps(b):
        failures.append("P5 determinism")
    return failures, grid


def main():
    results = [value(v) for v in VECTORS]
    fails = []
    print("| # | Vehicle | MSRP | Age mo | Odo km | M/B | BUV | CAV | A (bp) | FMV | FMV/MSRP | Dealer buys | Fence | Chop | Export |")
    print("|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for v, r in zip(VECTORS, results):
        a_bp = next(x for k, x, _ in r["lines"] if k == "A")
        ratio = rdiv(r["FMV"] * BP, v.msrp)
        key = v.label.split()[0]
        lo, hi = GOLDEN_RANGES_BP[key]
        ok = lo <= ratio <= hi
        if not ok:
            fails.append(f"golden {key}: {ratio}bp not in [{lo},{hi}]")
        fmt = lambda x: "—" if x is None else f"{x:,}"
        print(f"| {key} | {v.model} ({v.label.split(' ', 1)[1]}) | {v.msrp:,} | {v.age_months} | {v.odo_km:,} | {v.mech}/{v.body} | "
              f"{r['BUV']:,} | {r['CAV']:,} | {a_bp:+d} | **{r['FMV']:,}** | {ratio/100:.1f}% {'✓' if ok else '✗'} | "
              f"{fmt(r['dealer_acquisition'])} | {fmt(r['fence'])} ({r['heat_tier']}) | {fmt(r['chop'])} | {fmt(r['export'])} |")
    print()
    for v, r in zip(VECTORS, results):
        print(f"#### {v.label.split()[0]} breakdown — {v.model}")
        for k, x, note in r["lines"]:
            print(f"- `{k}` = {x:,} — {note}")
        print()
    pf, n = property_tests()
    fails += pf
    json.dump([{k: r[k] for k in r if k != "lines"} for r in results], open("valuation_vectors.json", "w"), indent=1)
    print(f"PROPERTY TESTS: grid={n} failures={len(pf)}")
    print("RESULT:", "PASS" if not fails else "FAIL")
    for f in fails[:20]:
        print("  -", f)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
