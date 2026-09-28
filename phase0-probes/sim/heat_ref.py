"""LSAX Phase 0 — Heat reference model (REFERENCE MODEL, NOT PRODUCTION CODE).

LSAX-HEAT-AND-UNDERGROUND-MODEL.md. Heat is an LSAX *market* quantity. LSAX never sets wanted level, never
spawns police and never dispatches anything (RDE/SixStar owns that); wanted level is only OBSERVED as an input.
Time base: LSAX Market Time (MT) hours. No decay while GTA is closed (MT does not advance).
"""
import sys

from lsax_ref_math import BP, clamp, mul_bp, rdiv, round_money

HMAX = 1000
TIERS = [(0, "COLD"), (200, "WARM"), (450, "HOT"), (750, "BURNING")]
VH_RETAIN_BP_PER_H = 9911  # half-life 72 MT hours under floor rounding (D-HEAT-3)
PH_RETAIN_BP_PER_H = 9949  # half-life 121 MT hours under floor rounding (D-HEAT-3)
MAX_DECAY_STEPS = 720      # 30 MT days; beyond this any heat <= 1000 is already 0 (asserted in tests)
EVENT_DELTA_CAP = 500
VH_EVENTS = {"THEFT_PARKED": 250, "THEFT_CARJACK": 400, "PURSUIT_IN_VEHICLE": 60, "PLATE_SWAP": -150, "RESPRAY": -100}
WANTED_AT_THEFT_PER_STAR, WANTED_AT_THEFT_CAP = 100, 300
PH_SALE = {"FENCE": (40, 10), "EXPORT": (25, 20), "CHOP": (15, 0)}  # base, divisor of VH (0 = none)
PH_BUY_UG, PH_PLATE_SWAP, PH_WANTED_DURING_UG_DELIVERY = 10, 20, 50
VELOCITY_WINDOW_H, VELOCITY_FREE, VELOCITY_STEP = 48, 2, 30
FENCE_HAIRCUT = {"COLD": 5500, "WARM": 6200, "HOT": 7200}
VELOCITY_HAIRCUT_STEP, VELOCITY_HAIRCUT_CAP, HAIRCUT_MAX = 400, 2000, 9000  # D-HEAT-6 (sim-driven fix)
LAYLOW_ENTER, LAYLOW_EXIT = 750, 600
UG_DAILY_CAP_PER_FENCE, UG_DAILY_CAP_TOTAL = 3, 6
BUYER_AVAIL_BP = {"COLD": 10000, "WARM": 8000, "HOT": 5000, "BURNING": 2000}
DEAL_FAIL_BP = {"COLD": 300, "WARM": 600, "HOT": 1200, "BURNING": 2500}


def tier(h):
    t = "COLD"
    for lo, name in TIERS:
        if h >= lo:
            t = name
    return t


def apply_delta(h, d):
    return clamp(h + clamp(d, -EVENT_DELTA_CAP, EVENT_DELTA_CAP), 0, HMAX)


def decay(h, hours, retain_bp):
    for _ in range(min(hours, MAX_DECAY_STEPS)):
        if h == 0:
            break
        # D-HEAT-3 (sim-driven): FLOOR, not rdiv. rdiv has a fixed point at h=52 (52*0.9904=51.5 -> 52) and heat
        # would never reach 0. floor(h*r) <= h-1 for every h>=1, so decay is strictly decreasing and terminates.
        # Operands are non-negative, so C# integer division (truncation) is identical.
        h = (h * retain_bp) // BP
    return 0 if hours > MAX_DECAY_STEPS else h


class Player:
    def __init__(self):
        self.ph = 0
        self.laylow = False
        self.ug_sales = []  # MT hour of each underground sale (bounded: only last window kept)

    def advance(self, hours):
        self.ph = decay(self.ph, hours, PH_RETAIN_BP_PER_H)
        if self.laylow and self.ph < LAYLOW_EXIT:
            self.laylow = False


def sell_to_fence(p: Player, vh: int, fmv: int, now_h: int, fence_counts: dict, fence="F1"):
    p.ug_sales = [t for t in p.ug_sales if now_h - t < VELOCITY_WINDOW_H]
    day = now_h // 24
    per_fence = fence_counts.get((fence, day), 0)
    total = sum(v for (f, d), v in fence_counts.items() if d == day)
    eff = max(vh, rdiv(p.ph, 2))
    t = tier(eff)
    if p.laylow:
        return None, "REFUSED_LAYLOW", eff
    if t == "BURNING":
        return None, "REFUSED_BURNING", eff
    if per_fence >= UG_DAILY_CAP_PER_FENCE or total >= UG_DAILY_CAP_TOTAL:
        return None, "REFUSED_DAILY_CAP", eff
    excess = max(0, len(p.ug_sales) + 1 - VELOCITY_FREE)
    haircut = min(FENCE_HAIRCUT[t] + min(VELOCITY_HAIRCUT_STEP * excess, VELOCITY_HAIRCUT_CAP), HAIRCUT_MAX)
    payout = round_money(mul_bp(fmv, BP - haircut))
    base, div = PH_SALE["FENCE"]
    velocity = VELOCITY_STEP * excess
    p.ph = apply_delta(p.ph, base + (rdiv(vh, div) if div else 0) + velocity)
    if p.ph >= LAYLOW_ENTER:
        p.laylow = True
    p.ug_sales.append(now_h)
    fence_counts[(fence, day)] = per_fence + 1
    return payout, t, eff


def main():
    fails = []
    out = []
    # S5: decay curves
    out.append("### S5 — decay from 1000 (MT hours to leave each tier)\n")
    out.append("| Scale | ->HOT (<750) | ->WARM (<450) | ->COLD (<200) | ->0 | measured half-life (h) |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for name, rb, target in (("Vehicle heat", VH_RETAIN_BP_PER_H, 72), ("Player heat", PH_RETAIN_BP_PER_H, 120)):
        h, hrs, marks, half = 1000, 0, {}, None
        while h > 0 and hrs < 2000:
            h = decay(h, 1, rb)
            hrs += 1
            for thr in (750, 450, 200):
                if h < thr and thr not in marks:
                    marks[thr] = hrs
            if half is None and h <= 500:
                half = hrs
        out.append(f"| {name} | {marks[750]} | {marks[450]} | {marks[200]} | {hrs} | {half} |")
        if abs(half - target) * 100 > 10 * target:
            fails.append(f"{name}: half-life {half}h not within 10% of {target}h (floor rounding)")
        if hrs > MAX_DECAY_STEPS:
            fails.append(f"{name}: reaches 0 after {hrs}h > MAX_DECAY_STEPS")

    # S1..S3, S6
    out.append("\n### Single-vehicle scenarios (FMV $20,000 legal basis)\n")
    out.append("| Scenario | Vehicle heat at sale | Player heat before | Effective | Tier | Fence payout | Player heat after |")
    out.append("|---|---:|---:|---:|---|---:|---:|")

    def scenario(label, vh, wait_h, pre_ph=0, extra=()):
        p = Player()
        p.ph = pre_ph
        for ev in extra:
            vh = apply_delta(vh, VH_EVENTS[ev])
            if ev == "PLATE_SWAP":
                p.ph = apply_delta(p.ph, PH_PLATE_SWAP)
        vh = decay(vh, wait_h, VH_RETAIN_BP_PER_H)
        p.advance(wait_h)
        before = p.ph
        pay, t, eff = sell_to_fence(p, vh, 20000, 1000 + wait_h, {})
        out.append(f"| {label} | {vh} | {before} | {eff} | {t} | {pay if pay is not None else '—'} | {p.ph} |")
        return pay

    s1 = scenario("S1 parked theft, sell after 2 h", VH_EVENTS["THEFT_PARKED"], 2)
    s2 = scenario("S2 carjack + 2 stars, sell after 1 h", apply_delta(VH_EVENTS["THEFT_CARJACK"], min(2 * WANTED_AT_THEFT_PER_STAR, WANTED_AT_THEFT_CAP)), 1)
    s3 = scenario("S3 as S2, lay low 72 h", apply_delta(VH_EVENTS["THEFT_CARJACK"], 200), 72)
    s6 = scenario("S6 as S2 + plate swap + respray, 24 h", apply_delta(VH_EVENTS["THEFT_CARJACK"], 200), 24, extra=("PLATE_SWAP", "RESPRAY"))
    s7 = scenario("S7 as S2, GTA closed 3 real days (MT +0 h)", apply_delta(VH_EVENTS["THEFT_CARJACK"], 200), 1)
    if not (s3 > s2 and s6 > s2):
        fails.append("laying low / cooling must raise payout")
    if s7 != s2:
        fails.append("offline time must not change heat (MT does not advance)")

    # S4: farming loop — steal (parked) and sell every 2 MT hours
    out.append("\n### S4 — farming loop: parked theft + fence sale every 2 MT hours (FMV $20,000 each)\n")
    out.append("| Car | MT hour | Player heat before | Vehicle heat | Effective | Result | Payout |")
    out.append("|---:|---:|---:|---:|---:|---|---:|")
    p, counts, now, pays = Player(), {}, 0, []
    for car in range(1, 13):
        before = p.ph
        vh = decay(VH_EVENTS["THEFT_PARKED"], 2, VH_RETAIN_BP_PER_H)
        pay, t, eff = sell_to_fence(p, vh, 20000, now, counts, fence="F1" if car % 2 else "F2")
        pays.append(pay)
        out.append(f"| {car} | {now} | {before} | {vh} | {eff} | {t} | {pay if pay is not None else '—'} |")
        now += 2
        p.advance(2)
    paid = [x for x in pays if x]
    if len(paid) > UG_DAILY_CAP_TOTAL:
        fails.append("daily cap not enforced")
    if paid and paid[-1] * 100 > 75 * paid[0]:
        fails.append("velocity/heat did not reduce payout of last paid car below 75% of first")
    if not any(x is None for x in pays):
        fails.append("farming loop never refused")
    out.append(f"\nFarming loop income in first MT day: ${sum(paid):,} for {len(paid)} cars "
               f"(honest pacing, 1 car/day at COLD: ${round_money(mul_bp(20000, BP - FENCE_HAIRCUT['COLD'])):,} per car).")

    for h in range(0, 1001, 50):
        for hours in (0, 1, 5, 100, 719, 720, 721, 10**6):
            for rb in (VH_RETAIN_BP_PER_H, PH_RETAIN_BP_PER_H):
                d = decay(h, hours, rb)
                if not 0 <= d <= h:
                    fails.append(f"decay bound violated {h} {hours}")
    if decay(1000, MAX_DECAY_STEPS, VH_RETAIN_BP_PER_H) != 0 or decay(1000, MAX_DECAY_STEPS, PH_RETAIN_BP_PER_H) != 0:
        fails.append("MAX_DECAY_STEPS too small: heat not zero after cap")
    print("\n".join(out))
    print("\nRESULT:", "PASS" if not fails else "FAIL")
    for f in fails:
        print("  -", f)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
