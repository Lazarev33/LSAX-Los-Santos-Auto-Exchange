"""LSAX Phase 0 — vehicle identity reference model, DRAFT2 (NOT PRODUCTION CODE).

Normative mirror of LSAX-DOMAIN-MODEL.md §4.2–§4.4 as corrected for audit findings P1-01 (handle reuse) and
P1-02 (candidate cap). Decisions D-ID-6 (handle/decorator/cache only schedule and order, never decide),
D-ID-7 (lossless bounded candidate search), D-ID-8 (explicit confirmation limits).

Scoring is unchanged from DRAFT1 (weights plate 40, colours 20, mods 25, cosmetics 10, context 15; score =
rdiv(sum*100, 110); BIND >= 85 and unique with gap >= 20; AMBIGUOUS 60..84 or not unique; NO MATCH < 60).

Lossless-bound lemma (proved in LSAX-DOMAIN-MODEL.md §4.4, checked exhaustively by `lemma_check`):
  (L1) a record whose normalised plate differs scores <= rdiv(70*100,110) = 64 < 85, and 64 <= 85-20, so it can
       neither BIND nor break the uniqueness of a BIND. Hence BIND/uniqueness depend only on
       K1 = records with (model, normalised plate) equal to the observation.
  (L2) a record outside K1 reaches >= 60 only with all four colour components equal AND context 15. Hence the
       AMBIGUOUS-vs-NO-MATCH decision additionally depends only on
       K2 = records with (model, exact colour signature) that are context-15-eligible.
Evaluation: K1 <= 32 in one tick; 32 < K1 <= 256 time-sliced (DEFER, no verdict until complete); K1 > 256 ->
AMBIGUOUS(OVERFLOW). K2 needed only when best(K1) < 60; K2 > 64 -> AMBIGUOUS(OVERFLOW). Truncation never yields
BIND or NO MATCH.
"""
import sys
from dataclasses import dataclass, field

from lsax_ref_math import SplitMix64, rdiv

W_PLATE, W_COL, W_MODS, W_COS, W_CTX = 40, 20, 25, 10, 15
TOTAL = W_PLATE + W_COL + W_MODS + W_COS + W_CTX
BIND_MIN, GAP, AMB_MIN = 85, 20, 60
K1_PER_TICK, K1_MAX, K2_MAX = 32, 256, 64
DRAFT1_CAP = 32
BIND, AMBIGUOUS, OVERFLOW, NO_MATCH = "BIND", "AMBIGUOUS", "AMBIGUOUS_OVERFLOW", "NO_MATCH"


@dataclass(frozen=True)
class Rec:
    vid: str
    model: int
    plate: str
    style: int
    colours: tuple      # (primary, secondary, pearl, wheel)
    mods: tuple
    cos: tuple
    last_pos: tuple     # (x, y) metres


@dataclass
class Obs:
    handle: int
    model: int
    plate: str
    style: int
    colours: tuple
    mods: tuple
    cos: tuple
    pos: tuple
    at_spawn_point: bool = False
    occupied: bool = False
    decorator: int = 0
    gt: int = 0


def norm_plate(p):
    return p.strip().upper()


def dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def ctx_points(rec, obs):
    if dist2(rec.last_pos, obs.pos) <= 50 * 50 or obs.at_spawn_point:
        return 15
    if (rec.last_pos[0] // 1000, rec.last_pos[1] // 1000) == (obs.pos[0] // 1000, obs.pos[1] // 1000):
        return 5
    return 0


def score(rec, obs):
    if rec.model != obs.model:
        return 0
    s = W_PLATE if (norm_plate(rec.plate) == norm_plate(obs.plate) and rec.style == obs.style) else 0
    s += 5 * sum(a == b for a, b in zip(rec.colours, obs.colours))
    s += rdiv(W_MODS * sum(a == b for a, b in zip(rec.mods, obs.mods)), max(len(rec.mods), 1))
    s += rdiv(W_COS * sum(a == b for a, b in zip(rec.cos, obs.cos)), max(len(rec.cos), 1))
    s += ctx_points(rec, obs)
    return rdiv(s * 100, TOTAL)


def verdict_from(scored):
    """scored: list of (score, vid). Returns (verdict, vid|None)."""
    if not scored:
        return NO_MATCH, None
    scored = sorted(scored, key=lambda t: (-t[0], t[1]))
    best, vid = scored[0]
    second = scored[1][0] if len(scored) > 1 else -1
    if best >= BIND_MIN and second <= best - GAP:
        return BIND, vid
    if best >= AMB_MIN:
        return AMBIGUOUS, None
    return NO_MATCH, None


class Index:
    """Complete indexes (persistent DB indexes in production): K1 by (model, plate_norm), K2 by (model, colours)."""

    def __init__(self, records):
        self.records = list(records)
        self.k1, self.k2 = {}, {}
        for r in self.records:
            self.k1.setdefault((r.model, norm_plate(r.plate)), []).append(r)
            self.k2.setdefault((r.model, r.colours), []).append(r)


def decide_reference(obs, index):
    """Unbounded ground truth: score every record."""
    return verdict_from([(score(r, obs), r.vid) for r in index.records])


def decide_draft1(obs, index):
    """DRAFT1 §4.4: same model, nearest last-seen first, truncated to 32 before the uniqueness test (P1-02 defect)."""
    cands = sorted((r for r in index.records if r.model == obs.model), key=lambda r: (dist2(r.last_pos, obs.pos), r.vid))
    return verdict_from([(score(r, obs), r.vid) for r in cands[:DRAFT1_CAP]])


def decide_draft2(obs, index, hint_vid=None):
    """DRAFT2 D-ID-7. Returns (verdict, vid, ticks). hint_vid (handle cache / decorator) only orders evaluation."""
    k1 = list(index.k1.get((obs.model, norm_plate(obs.plate)), []))
    if hint_vid is not None:
        k1.sort(key=lambda r: (r.vid != hint_vid, r.vid))
    if len(k1) > K1_MAX:
        return OVERFLOW, None, 1
    ticks = max(1, -(-len(k1) // K1_PER_TICK))          # time-sliced: no verdict before the last slice
    scored = [(score(r, obs), r.vid) for r in k1]
    v, vid = verdict_from(scored)
    if v == BIND:
        return BIND, vid, ticks
    if v == AMBIGUOUS:
        return AMBIGUOUS, None, ticks
    k2 = [r for r in index.k2.get((obs.model, obs.colours), []) if ctx_points(r, obs) == 15]
    if len(k2) > K2_MAX:
        return OVERFLOW, None, ticks
    if any(score(r, obs) >= AMB_MIN for r in k2):
        return AMBIGUOUS, None, ticks
    return NO_MATCH, None, ticks


# ------------------------------------------------------------------------------ runtime binding (P1-01)
class BinderDraft1:
    """DRAFT1 §4.2/§4.3: continuity rule (same handle + model + <=2 s + plausible position) keeps the binding and
    records fingerprint changes as mutations; decorator fast path verifies only model + plate."""

    def __init__(self, index):
        self.index, self.bound, self.last, self.tokens = index, {}, {}, {}

    def observe(self, obs):
        h = obs.handle
        if h in self.bound:
            prev = self.last[h]
            dt = obs.gt - prev.gt
            if obs.model == prev.model and 0 <= dt <= 2000 and dist2(obs.pos, prev.pos) <= (150 * dt // 1000 + 50) ** 2:
                self.last[h] = obs
                return BIND, self.bound[h]                   # continuity -> same VehicleId (mutations recorded)
        if obs.decorator and obs.decorator in self.tokens:
            vid = self.tokens[obs.decorator]
            rec = next(r for r in self.index.records if r.vid == vid)
            if rec.model == obs.model and norm_plate(rec.plate) == norm_plate(obs.plate):
                self.bound[h], self.last[h] = vid, obs
                return BIND, vid
        v, vid = decide_draft1(obs, self.index)
        if v == BIND:
            self.bound[h], self.last[h] = vid, obs
        else:
            self.bound.pop(h, None)
        return v, vid

    def tag(self, obs, token):
        self.tokens[token] = self.bound[obs.handle]


class BinderDraft2:
    """DRAFT2 D-ID-6: every observation is a full multifactor evaluation over the lossless candidate set.
    The handle cache and decorator token only produce a hint that orders evaluation; they never decide."""

    def __init__(self, index):
        self.index, self.bound, self.tokens = index, {}, {}
        self.occupied_since_bind = {}                      # handle -> vid while the player never left it (D-ID-8)

    def observe(self, obs):
        h = obs.handle
        hint = self.bound.get(h) or self.tokens.get(obs.decorator)
        v, vid, _ = decide_draft2(obs, self.index, hint_vid=hint)
        if v == BIND:
            self.bound[h] = vid
            if obs.occupied:
                self.occupied_since_bind[h] = vid
            else:
                self.occupied_since_bind.pop(h, None)
        else:
            if not (obs.occupied and self.occupied_since_bind.get(h) == self.bound.get(h)):
                self.occupied_since_bind.pop(h, None)
            self.bound.pop(h, None)
        return v, vid

    def tag(self, obs, token):
        self.tokens[token] = self.bound[obs.handle]

    def may_confirm(self, obs, vid):
        """D-ID-8: explicit player confirmation (AMBIGUOUS -> Bound) needs exactly one candidate >= 60 for this
        entity, and either an equal plate or occupied continuity since the last BIND of this handle to vid."""
        cands = [r for r in self.index.records if score(r, obs) >= AMB_MIN]
        if len(cands) != 1 or cands[0].vid != vid:
            return False
        rec = cands[0]
        plate_ok = norm_plate(rec.plate) == norm_plate(obs.plate) and rec.style == obs.style
        return plate_ok or self.occupied_since_bind.get(obs.handle) == vid


def lemma_check():
    """Exhaustive check of L1/L2 over every combination of per-field points."""
    mods_pts = sorted({rdiv(W_MODS * k, n) for n in range(1, 60) for k in range(n + 1)})
    cos_pts = sorted({rdiv(W_COS * k, n) for n in range(1, 20) for k in range(n + 1)})
    ok = True
    for plate in (0, W_PLATE):
        for col in (0, 5, 10, 15, 20):
            for m in mods_pts:
                for c in cos_pts:
                    for ctx in (0, 5, 15):
                        sc = rdiv((plate + col + m + c + ctx) * 100, TOTAL)
                        if plate == 0:
                            ok &= sc <= 64 and sc < BIND_MIN and sc <= BIND_MIN - GAP
                            if sc >= AMB_MIN:
                                ok &= col == 20 and ctx == 15
    return ok


def random_population(rng, n, models=3, plates=6, colours=3, spread=4000):
    recs = []
    for i in range(n):
        m = 100 + rng.below(models)
        recs.append(Rec(f"V{i:04d}", m, f"PL{rng.below(plates)}", 0,
                        tuple(rng.below(colours) for _ in range(4)), tuple(rng.below(2) for _ in range(10)),
                        tuple(rng.below(2) for _ in range(3)), (rng.below(spread), rng.below(spread))))
    return recs


def random_obs(rng, recs, models=3, plates=6, colours=3, spread=4000):
    if recs and rng.chance_bp(6000):                       # perturbed copy of a real record
        r = recs[rng.below(len(recs))]
        col = tuple(c if rng.chance_bp(8500) else rng.below(colours) for c in r.colours)
        mods = tuple(x if rng.chance_bp(9000) else 1 - x for x in r.mods)
        plate = r.plate if rng.chance_bp(8000) else f"PL{rng.below(plates)}"
        pos = r.last_pos if rng.chance_bp(5000) else (rng.below(spread), rng.below(spread))
        return Obs(1, r.model, plate, 0, col, mods, r.cos, pos, at_spawn_point=rng.chance_bp(1500))
    return Obs(1, 100 + rng.below(models), f"PL{rng.below(plates)}", 0, tuple(rng.below(colours) for _ in range(4)),
               tuple(rng.below(2) for _ in range(10)), tuple(rng.below(2) for _ in range(3)),
               (rng.below(spread), rng.below(spread)), at_spawn_point=rng.chance_bp(1500))


def property_run(trials=3000, seed=0x1D2):
    """DRAFT2 vs unbounded reference on dense, collision-heavy populations (up to 400 same-model records)."""
    rng = SplitMix64(seed)
    st = dict(trials=0, equal=0, overflow=0, draft2_unsafe=0, draft1_false_bind=0, draft1_false_nomatch=0,
              draft1_wrong=0, max_k1=0, deferred=0)
    for _ in range(trials):
        recs = random_population(rng, rng.range_incl(1, 400))
        idx = Index(recs)
        obs = random_obs(rng, recs)
        ref = decide_reference(obs, idx)
        new_v, new_vid, ticks = decide_draft2(obs, idx)
        old = decide_draft1(obs, idx)
        st["trials"] += 1
        st["max_k1"] = max(st["max_k1"], len(idx.k1.get((obs.model, norm_plate(obs.plate)), [])))
        st["deferred"] += ticks > 1
        if new_v == OVERFLOW:
            st["overflow"] += 1
        elif (new_v, new_vid) == ref:
            st["equal"] += 1
        else:
            st["draft2_unsafe"] += 1
        if old != ref:
            st["draft1_wrong"] += 1
            st["draft1_false_bind"] += old[0] == BIND and ref != old
            st["draft1_false_nomatch"] += old[0] == NO_MATCH and ref[0] != NO_MATCH
    return st


def main():
    ok = lemma_check()
    print(f"lemma L1/L2 exhaustive check: {'OK' if ok else 'FAIL'}")
    st = property_run()
    print("property run (DRAFT2 vs unbounded reference):", st)
    ok &= st["draft2_unsafe"] == 0 and st["draft1_false_bind"] + st["draft1_false_nomatch"] > 0 and st["max_k1"] > 32
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
