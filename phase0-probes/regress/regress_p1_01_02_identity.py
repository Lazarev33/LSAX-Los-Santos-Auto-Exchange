"""P1-01 / P1-02 regression — handle reuse can never inherit a VehicleId; the candidate bound can never create false
uniqueness (decisions D-ID-6, D-ID-7, D-ID-8; model phase0-probes/sim/identity_ref.py).

Each directed case runs the DRAFT1 rule (to show the defect is reproduced by the case) and the DRAFT2 rule.
Pass = DRAFT2 never binds the wrong record automatically, legitimate re-observations still bind, and every
>32-candidate case gives the same verdict as the unbounded reference (or AMBIGUOUS_OVERFLOW, never BIND/NO_MATCH).
"""
import sys

from regress_common import Suite
from identity_ref import (AMBIGUOUS, BIND, NO_MATCH, OVERFLOW, BinderDraft1, BinderDraft2, Index, Obs, Rec,
                          decide_draft1, decide_draft2, decide_reference, lemma_check, property_run, score)

STOCK = tuple([0] * 10)
COS = (0, 0, 0)


def rec(vid, plate="LSAX0001", colours=(1, 1, 1, 1), pos=(0, 0), model=500, mods=STOCK):
    return Rec(vid, model, plate, 0, colours, mods, COS, pos)


def obs(handle, r=None, gt=0, **kw):
    base = dict(model=500, plate="LSAX0001", style=0, colours=(1, 1, 1, 1), mods=STOCK, cos=COS, pos=(0, 0))
    if r is not None:
        base.update(model=r.model, plate=r.plate, style=r.style, colours=r.colours, mods=r.mods, cos=r.cos, pos=r.last_pos)
    base.update(kw)
    return Obs(handle, gt=gt, **base)


def run():
    s = Suite("P1-01/P1-02 identity")
    s.check("lemma L1/L2 (only same-plate records can BIND or break uniqueness; >=60 needs colours+context)", lemma_check())

    # ---------------------------------------------------------------- P1-01 handle reuse
    mine = rec("MINE", plate="LSAX0001", colours=(3, 3, 0, 0), pos=(100, 100))
    idx = Index([mine])

    # H1 same handle + same model + nearby, DIFFERENT vehicle (traffic car, other plate, other colours)
    for name, B in (("DRAFT1", BinderDraft1), ("DRAFT2", BinderDraft2)):
        b = B(idx)
        b.observe(obs(7, mine, gt=0))
        v, vid = b.observe(obs(7, gt=1500, plate="X9TRAF1C", colours=(5, 5, 0, 0), pos=(110, 100)))
        if name == "DRAFT1":
            s.check("H1 DRAFT1 reproduces the defect (reused handle inherits MINE)", (v, vid) == (BIND, "MINE"), (v, vid))
        else:
            s.check("H1 DRAFT2: reused handle does not inherit", vid is None and v in (NO_MATCH, AMBIGUOUS), (v, vid))

    # H2 same handle + same model + nearly identical appearance (only the plate differs)
    for name, B in (("DRAFT1", BinderDraft1), ("DRAFT2", BinderDraft2)):
        b = B(idx)
        b.observe(obs(7, mine, gt=0))
        o = obs(7, mine, gt=900, plate="ZZ000001")
        v, vid = b.observe(o)
        if name == "DRAFT1":
            s.check("H2 DRAFT1 reproduces the defect (lookalike inherits MINE)", (v, vid) == (BIND, "MINE"), (v, vid))
        else:
            s.check("H2 DRAFT2: lookalike -> AMBIGUOUS, not bound", (v, vid) == (AMBIGUOUS, None), (v, vid))
            s.check("H2 DRAFT2: explicit confirmation refused (plate differs, no occupied continuity)",
                    not b.may_confirm(o, "MINE"))

    # H3 handle reuse after despawn: original despawned, new same-model entity gets the handle later elsewhere
    b = BinderDraft2(idx)
    b.observe(obs(7, mine, gt=0))
    v, vid = b.observe(obs(7, gt=60_000, plate="AB12CD34", colours=(3, 3, 0, 0), pos=(2500, 2500)))
    s.check("H3 DRAFT2: handle reused after despawn is not bound", vid is None, (v, vid))
    v, vid = b.observe(obs(9, mine, gt=61_000))
    s.check("H3 DRAFT2: the real vehicle (new handle) binds again", (v, vid) == (BIND, "MINE"), (v, vid))

    # H4 two legitimate similar vehicles, handles swapped between observations
    a = rec("CAR_A", plate="LSAX000A", colours=(2, 2, 2, 2), pos=(0, 0))
    c = rec("CAR_B", plate="LSAX000B", colours=(2, 2, 2, 2), pos=(10, 0))
    idx2 = Index([a, c])
    b = BinderDraft2(idx2)
    s.check("H4 CAR_A binds", b.observe(obs(1, a)) == (BIND, "CAR_A"))
    s.check("H4 CAR_B binds", b.observe(obs(2, c)) == (BIND, "CAR_B"))
    s.check("H4 handles swapped: handle 1 now shows CAR_B -> CAR_B", b.observe(obs(1, c, gt=500)) == (BIND, "CAR_B"))
    s.check("H4 handles swapped: handle 2 now shows CAR_A -> CAR_A", b.observe(obs(2, a, gt=500)) == (BIND, "CAR_A"))
    b1 = BinderDraft1(idx2)
    b1.observe(obs(1, a)); b1.observe(obs(2, c))
    s.check("H4 DRAFT1 reproduces the defect (swapped handle keeps the old id)",
            b1.observe(obs(1, c, gt=500)) == (BIND, "CAR_A"))

    # H5 stale cache across streaming: vehicle streamed out; a same-model car streams in with the cached handle
    b = BinderDraft2(idx)
    b.observe(obs(7, mine, gt=0))
    v, vid = b.observe(obs(7, gt=1200, plate="STREAM01", colours=(3, 3, 0, 0), pos=(140, 100)))
    s.check("H5 DRAFT2: stale cache entry does not bind the streamed-in car", vid is None, (v, vid))
    s.check("H5 DRAFT2: cache entry dropped", 7 not in b.bound)

    # H6 decorator collision / stale hint: entity carries a token that maps to MINE, but it is another vehicle
    other = rec("OTHER", plate="LSAX0777", colours=(3, 3, 0, 0), pos=(100, 120))
    idx3 = Index([mine, other])
    for name, B in (("DRAFT1", BinderDraft1), ("DRAFT2", BinderDraft2)):
        b = B(idx3)
        o = obs(7, mine)
        b.observe(o)
        b.tag(o, 0x1234)
        o2 = obs(8, other, decorator=0x1234)              # stale / colliding token on a different entity
        v, vid = b.observe(o2)
        if name == "DRAFT2":
            s.check("H6 DRAFT2: stale/colliding decorator does not force MINE; OTHER binds on its own evidence",
                    (v, vid) == (BIND, "OTHER"), (v, vid))
        o3 = obs(8, gt=100, plate="LSAX0001", colours=(9, 9, 9, 9), mods=tuple([1] * 10), pos=(900, 900), decorator=0x1234)
        v, vid = b.observe(o3)                            # same plate text, nothing else matches
        if name == "DRAFT1":
            s.check("H6 DRAFT1 reproduces the defect (decorator + model + plate fast path binds)", (v, vid) == (BIND, "MINE"), (v, vid))
        else:
            s.check("H6 DRAFT2: decorator + plate alone is not identity", vid is None, (v, vid))

    # H7 liveness: same vehicle, respray (primary+secondary) while observed -> still BIND (score 91, unique)
    b = BinderDraft2(idx)
    b.observe(obs(7, mine))
    v, vid = b.observe(obs(7, mine, gt=500, colours=(8, 8, 0, 0)))
    s.check("H7 respray of the same vehicle keeps BIND", (v, vid) == (BIND, "MINE"), (v, vid))

    # H8 in-place plate change at a mod shop with the player inside: AMBIGUOUS, confirmable (occupied continuity)
    b = BinderDraft2(idx)
    b.observe(obs(7, mine, occupied=True))
    o = obs(7, mine, gt=500, plate="NEWPLATE", occupied=True)
    v, vid = b.observe(o)
    s.check("H8 plate change while occupied -> AMBIGUOUS (no automatic reuse)", (v, vid) == (AMBIGUOUS, None), (v, vid))
    s.check("H8 explicit confirmation allowed (occupied continuity since BIND)", b.may_confirm(o, "MINE"))
    b = BinderDraft2(idx)
    b.observe(obs(7, mine, occupied=True))
    b.observe(obs(7, mine, gt=300, occupied=False))       # player left the car
    o = obs(7, mine, gt=600, plate="NEWPLATE", occupied=True)
    b.observe(o)
    s.check("H8b continuity broken (player left) -> confirmation refused", not b.may_confirm(o, "MINE"))

    # ---------------------------------------------------------------- P1-02 candidate cap
    # C1 >32 same-model records; two share the observed legacy plate; the plate-twin is the farthest
    recs = [rec(f"N{i:02d}", plate=f"OTH{i:05d}", colours=(1, 1, 1, 1), pos=(i * 10, 0)) for i in range(40)]
    twin_near = rec("TWIN_NEAR", plate="46EEK572", colours=(1, 1, 1, 1), pos=(5, 0))
    twin_far = rec("TWIN_FAR", plate="46EEK572", colours=(1, 1, 1, 1), pos=(3000, 0))
    idx4 = Index(recs + [twin_near, twin_far])
    o = obs(1, twin_near)
    s.check("C1 DRAFT1 reproduces false uniqueness (BIND with the twin truncated away)",
            decide_draft1(o, idx4)[0] == BIND, decide_draft1(o, idx4))
    s.check("C1 reference: not unique", decide_reference(o, idx4)[0] == AMBIGUOUS, decide_reference(o, idx4))
    s.check("C1 DRAFT2 equals reference (AMBIGUOUS)", decide_draft2(o, idx4)[:2] == decide_reference(o, idx4),
            decide_draft2(o, idx4))

    # C2 >32 candidates at an impound spawn point; only a far record has the exact colour signature -> AMBIGUOUS
    recs = [rec(f"M{i:02d}", plate=f"OTH{i:05d}", colours=(4, 4, 4, 4), pos=(i, 0)) for i in range(50)]
    far = rec("FAR_SAME_COLOUR", plate="OLDPLATE", colours=(1, 1, 1, 1), pos=(3900, 3900))
    idx5 = Index(recs + [far])
    o = obs(1, far, plate="UNKNOWN1", pos=(0, 0), at_spawn_point=True)
    s.check("C2 DRAFT1 reproduces false NO MATCH (would allow duplicate registration)",
            decide_draft1(o, idx5)[0] == NO_MATCH, decide_draft1(o, idx5))
    s.check("C2 DRAFT2 equals reference (AMBIGUOUS)", decide_draft2(o, idx5)[:2] == decide_reference(o, idx5) == (AMBIGUOUS, None))

    # C3 100 same-plate same-model records (legacy default plate): time-sliced, identical verdict
    recs = [rec(f"P{i:03d}", plate="DEFAULT1", colours=(i % 7, 0, 0, 0), pos=(i * 3, 0)) for i in range(100)]
    idx6 = Index(recs)
    o = obs(1, recs[42])
    v, vid, ticks = decide_draft2(o, idx6)
    s.check("C3 K1=100: DEFER over 4 ticks, verdict equals reference", ticks == 4 and (v, vid) == decide_reference(o, idx6),
            (v, vid, ticks, decide_reference(o, idx6)))

    # C4 300 same-plate records: overflow -> AMBIGUOUS, never BIND or NO MATCH
    recs = [rec(f"Q{i:03d}", plate="DEFAULT1", colours=(9, 9, 9, 9), mods=tuple([1] * 10), pos=(2000 + i * 3, 2000))
            for i in range(300)]
    recs[0] = rec("Q000", plate="DEFAULT1", colours=(1, 1, 1, 1), pos=(0, 0))
    idx7 = Index(recs)
    o = obs(1, recs[0])
    s.check("C4 reference would BIND (unique best)", decide_reference(o, idx7)[0] == BIND)
    s.check("C4 DRAFT2 K1=300 -> AMBIGUOUS_OVERFLOW (conservative, never BIND/NO MATCH)", decide_draft2(o, idx7)[0] == OVERFLOW)

    # C5 K2 overflow: 80 records at a spawn point with the exact colour signature, none with the plate
    recs = [rec(f"R{i:02d}", plate=f"X{i:07d}", colours=(1, 1, 1, 1), mods=tuple([1] * 10), pos=(i * 50, 0)) for i in range(80)]
    idx8 = Index(recs)
    o = obs(1, plate="NOPE0000", colours=(1, 1, 1, 1), mods=STOCK, at_spawn_point=True)
    s.check("C5 K2=80 > 64 -> AMBIGUOUS_OVERFLOW (never NO MATCH)", decide_draft2(o, idx8)[0] == OVERFLOW)

    # C6 randomized dense populations (up to 400 records, heavy collisions): DRAFT2 == reference, DRAFT1 unsafe
    st = property_run(trials=1500, seed=0x5EED)
    s.check("C6 DRAFT2 never differs from the unbounded reference (except conservative overflow)", st["draft2_unsafe"] == 0, st)
    s.check("C6 >32 candidates actually exercised", st["max_k1"] > 32, st)
    s.check("C6 DRAFT1 unsafe divergences reproduced (false BIND / false NO MATCH)",
            st["draft1_false_bind"] > 0 and st["draft1_false_nomatch"] > 0, st)
    print("C6 property statistics:", st)
    return s


def main():
    return run().report()


if __name__ == "__main__":
    sys.exit(main())
