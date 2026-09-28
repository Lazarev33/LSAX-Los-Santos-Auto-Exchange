"""P1-05 regression — NPC VehicleId uniqueness across market steps, replenishment, sold/expired listings, rewinds and
branches (decision D-GEN-6; model phase0-probes/sim/npcgen_ref.py identity functions).

Generation identity = (campaign, market_step_index, segment, generation_ordinal); VehicleId low 64 bits =
mix64(pack(step, segment, ordinal)) — injective by construction (packing injective, mix64 bijective); high 64 bits =
campaign salt with the generated-namespace bit. A path never repeats a step index (SYS_MARKET_STEP key, P1-04), and
ordinals are allocated sequentially within (step, segment) and never reused.
"""
import sys

from regress_common import Suite
from lsax_ref_math import SplitMix64, mix64, unmix64
from npcgen_ref import (SEGMENT_CODE, draft1_vehicle_id, generate, identity_of, pack_identity, unpack_identity,
                        vehicle_id)

SALT = 0x5A17_C0DE_0000_0042
SEGS = list(SEGMENT_CODE)


class Market:
    """Minimal deterministic market over a timeline path: each step generates `need` vehicles per segment
    (replenishment = number of listings that ended — sold or expired — in the previous step, min 1)."""

    def __init__(self, campaign_seed=42):
        self.seed, self.step, self.active, self.ended = campaign_seed, -1, {}, []
        self.generated = []                              # (vid, identity, attributes digest) in path order

    def clone(self):
        m = Market(self.seed)
        m.step, m.active, m.ended, m.generated = self.step, dict(self.active), list(self.ended), list(self.generated)
        return m

    def run_step(self, player_buys=()):
        self.step += 1
        k = self.step
        for vid in player_buys:                          # player purchases end listings (branch-dependent)
            if vid in self.active:
                self.ended.append(self.active.pop(vid))
        for vid, (born, _) in list(self.active.items()):  # expiry after 7 steps
            if k - born >= 7:
                self.ended.append(self.active.pop(vid))
        for seg in SEGS:
            need = 1 + sum(1 for _ in self.ended) % 3
            for ordinal in range(need):
                vid = vehicle_id(SALT, k, seg, ordinal)
                attrs = generate(self.seed, k, seg, ordinal)
                self.active[vid] = (k, seg)
                self.generated.append((vid, (k, seg, ordinal), repr(sorted(attrs.items()))))
        self.ended = []
        return k


def run():
    s = Suite("P1-05 NPC VehicleId uniqueness")

    # 1 DRAFT1 reproduction: two market steps of the same MT day with step-local slots 0..2
    d1a = [draft1_vehicle_id(42, 42, "MAINSTREAM", slot) for slot in range(3)]
    d1b = [draft1_vehicle_id(42, 42, "MAINSTREAM", slot) for slot in range(3)]
    s.check("DRAFT1 reproduces the defect: two steps of MT day 42 -> 3/3 identical VehicleIds", d1a == d1b)
    step_a, step_b = 42 * 24 + 5, 42 * 24 + 6            # two steps inside MT day 42
    n1 = [vehicle_id(SALT, step_a, "MAINSTREAM", o) for o in range(3)]
    n2 = [vehicle_id(SALT, step_b, "MAINSTREAM", o) for o in range(3)]
    s.check("DRAFT2: two steps of the same MT day -> 6 distinct VehicleIds", len(set(n1 + n2)) == 6)

    # 2 injectivity: pack/unpack round trip, mix64 inverse, identity recoverable from the id
    rng = SplitMix64(0xABC)
    ok = True
    for _ in range(20_000):
        st, seg, o = rng.below(1 << 40), SEGS[rng.below(len(SEGS))], rng.below(1 << 20)
        ok &= unpack_identity(pack_identity(st, seg, o)) == (st, seg, o) and identity_of(vehicle_id(SALT, st, seg, o)) == (st, seg, o)
    s.check("injective: identity recovered exactly from VehicleId (20 000 random identities)", ok)
    ok = all(unmix64(mix64(x)) == x for x in (rng.next_u64() for _ in range(20_000)))
    s.check("mix64 is a bijection (inverse verified on 20 000 values)", ok)
    try:
        pack_identity(1 << 40, "MAINSTREAM", 0)
        s.check("out-of-range identity refused (never wraps)", False)
    except ValueError:
        s.check("out-of-range identity refused (never wraps)", True)

    # 3 exhaustive uniqueness: 90 MT days x 24 steps x 8 segments x 30 ordinals
    ids = {vehicle_id(SALT, st, seg, o) for st in range(90 * 24) for seg in SEGS for o in range(30)}
    s.check(f"90 MT days x 24 steps x {len(SEGS)} segments x 30 ordinals -> all {90 * 24 * len(SEGS) * 30} VehicleIds distinct", len(ids) == 90 * 24 * len(SEGS) * 30, len(ids))

    # 4 replenishment + sold + expired listings over 200 steps on one path: no id ever repeats
    m = Market()
    for k in range(200):
        buys = [v for v in list(m.active)[:2]] if k % 5 == 0 else []
        m.run_step(buys)
    vids = [g[0] for g in m.generated]
    s.check("200 steps with replenishment, sales and expiry: no VehicleId repeats on the path", len(vids) == len(set(vids)), len(vids))

    # 5 rewind/replay: anchor back to step 120, re-run 121..199 -> identical ids and attributes
    m1 = Market()
    snap = None
    for k in range(200):
        if k == 121:
            snap = m1.clone()
        m1.run_step([v for v in list(m1.active)[:2]] if k % 5 == 0 else [])
    m2 = snap
    for k in range(121, 200):
        m2.run_step([v for v in list(m2.active)[:2]] if k % 5 == 0 else [])
    s.check("rewind to step 120 and replay -> identical VehicleIds and attributes (no re-roll)", m2.generated == m1.generated)
    s.check("replayed path has no duplicate VehicleId", len({g[0] for g in m2.generated}) == len(m2.generated))

    # 6 branch replay: two branches from step 120 with different player purchases
    a, b = snap.clone(), snap.clone()
    for k in range(121, 160):
        a.run_step([v for v in list(a.active)[:3]] if k % 4 == 0 else [])
        b.run_step([])
    ga, gb = {g[0]: g for g in a.generated}, {g[0]: g for g in b.generated}
    s.check("branch A: no duplicate VehicleId", len(ga) == len(a.generated))
    s.check("branch B: no duplicate VehicleId", len(gb) == len(b.generated))
    common = set(ga) & set(gb)
    s.check("same VehicleId on two branches <=> same generation identity and identical attributes",
            all(ga[v][1:] == gb[v][1:] for v in common) and len(common) > 0, len(common))
    s.check("branches differ only by extra ordinals (state-dependent replenishment), never by reuse",
            all(ga[v][1] not in {gb[w][1] for w in gb} for v in set(ga) - common))

    # 7 deterministic regeneration
    s.check("deterministic regeneration of attributes", generate(7, 3, "MAINSTREAM", 5) == generate(7, 3, "MAINSTREAM", 5))

    # 8 campaign namespaces: same identity in two campaigns -> different ids; generated namespace bit set
    v1, v2 = vehicle_id(SALT, 10, "SPORTS", 0), vehicle_id(SALT ^ 1, 10, "SPORTS", 0)
    s.check("different campaigns never share a VehicleId for the same identity", v1 != v2)
    s.check("generated ids carry the generated-namespace bit (disjoint from random player registrations)", (v1 >> 127) == 1)

    # 9 avalanche: consecutive ordinals differ in ~32 of 64 bits (DRAFT1 raw FNV-1a differed in few)
    def diff_bits(x, y):
        return bin(x ^ y).count("1")
    new_avg = sum(diff_bits(vehicle_id(SALT, 5, "MAINSTREAM", o) & ((1 << 64) - 1),
                            vehicle_id(SALT, 5, "MAINSTREAM", o + 1) & ((1 << 64) - 1)) for o in range(1000)) / 1000
    old_avg = sum(diff_bits(draft1_vehicle_id(42, 5, "MAINSTREAM", o), draft1_vehicle_id(42, 5, "MAINSTREAM", o + 1)) for o in range(1000)) / 1000
    print(f"avalanche: DRAFT2 mean differing bits {new_avg:.1f}/64, DRAFT1 raw FNV-1a {old_avg:.1f}/64")
    s.check("DRAFT2 ids are well mixed (mean differing bits between neighbours >= 28)", new_avg >= 28, new_avg)
    return s


def main():
    return run().report()


if __name__ == "__main__":
    sys.exit(main())
