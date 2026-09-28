"""LSAX Phase 0 — canonical deterministic arithmetic kernel (REFERENCE MODEL, NOT PRODUCTION CODE).

Normative rules (LSAX-VALUATION-MODEL.md §2, LSAX-NPC-GENERATION-MODEL.md §2, LSAX-HEAT-AND-UNDERGROUND-MODEL.md §3):
  * Money is an integer number of whole GTA dollars (int64). No floating point anywhere in gameplay maths.
  * Factors are integers in basis points (bp): 10_000 bp = 1.0.
  * Every division uses rdiv(): round half away from zero. C# must implement the identical rule
    (C# `/` truncates toward zero; Python `//` floors; neither is used directly on signed values).
  * Curves are piecewise-linear tables of integer points; no exp/log/pow (libm results differ by platform).
  * Randomness is SplitMix64 with explicitly derived seeds; integer sampling uses rejection (no modulo bias).
"""

MASK64 = (1 << 64) - 1
BP = 10_000


def rdiv(a: int, b: int) -> int:
    """Integer division rounding half away from zero. b must be > 0."""
    if b <= 0:
        raise ValueError("rdiv divisor must be positive")
    if a >= 0:
        return (a + b // 2) // b
    return -((-a + b // 2) // b)


def clamp(x: int, lo: int, hi: int) -> int:
    if lo > hi:
        raise ValueError("clamp bounds inverted")
    return lo if x < lo else hi if x > hi else x


def mul_bp(value: int, factor_bp: int) -> int:
    """value * factor (factor in bp), rounded half away from zero."""
    return rdiv(value * factor_bp, BP)


def interp(table, x: int) -> int:
    """Piecewise-linear interpolation over integer points [(x0,y0),(x1,y1),...], x strictly increasing.
    Outside the table the end value is held (flat extrapolation)."""
    if not table:
        raise ValueError("empty table")
    for i in range(1, len(table)):
        if table[i][0] <= table[i - 1][0]:
            raise ValueError("table x must be strictly increasing")
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    for i in range(1, len(table)):
        x0, y0 = table[i - 1]
        x1, y1 = table[i]
        if x <= x1:
            return y0 + rdiv((y1 - y0) * (x - x0), (x1 - x0))
    raise AssertionError("unreachable")


def round_money(v: int) -> int:
    """Display/settlement rounding: $50 below $100k, $100 below $1M, $1000 above (half away from zero)."""
    step = 50 if v < 100_000 else 100 if v < 1_000_000 else 1_000
    return rdiv(v, step) * step


class SplitMix64:
    """SplitMix64 (Steele, Lea, Flood 2014). Deterministic, trivially portable to C# (ulong arithmetic)."""

    def __init__(self, seed: int):
        self.state = seed & MASK64

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def below(self, n: int) -> int:
        """Uniform integer in [0, n) by rejection sampling (no modulo bias)."""
        if n <= 0:
            raise ValueError("n must be positive")
        limit = (MASK64 + 1) - ((MASK64 + 1) % n)
        while True:
            r = self.next_u64()
            if r < limit:
                return r % n

    def range_incl(self, lo: int, hi: int) -> int:
        return lo + self.below(hi - lo + 1)

    def chance_bp(self, p_bp: int) -> bool:
        return self.below(BP) < p_bp

    def pick_weighted(self, weighted):
        """weighted: list of (item, integer_weight>=0). Deterministic order = list order."""
        total = sum(w for _, w in weighted)
        if total <= 0:
            raise ValueError("no positive weight")
        r = self.below(total)
        acc = 0
        for item, w in weighted:
            acc += w
            if r < acc:
                return item
        raise AssertionError("unreachable")

    def quantile(self, qtable) -> int:
        """Inverse-CDF sampling from a piecewise-linear quantile table [(p_bp, value), ...] with p from 0 to 10000."""
        return interp(qtable, self.below(BP + 1))


def fnv1a64(text: str) -> int:
    """Stable 64-bit seed derivation from a UTF-8 string (FNV-1a)."""
    h = 0xCBF29CE484222325
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * 0x100000001B3) & MASK64
    return h


def mix64(x: int) -> int:
    """SplitMix64 finaliser: a bijection on 64-bit integers (xor-shifts and odd multipliers are invertible)."""
    z = x & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return z ^ (z >> 31)


def _unxorshift(z: int, k: int) -> int:
    x = z
    for _ in range(64 // k + 1):
        x = z ^ (x >> k)
    return x & MASK64


def unmix64(z: int) -> int:
    """Inverse of mix64 (proves bijectivity; used only by tests)."""
    x = _unxorshift(z & MASK64, 31)
    x = (x * pow(0x94D049BB133111EB, -1, 1 << 64)) & MASK64
    x = _unxorshift(x, 27)
    x = (x * pow(0xBF58476D1CE4E5B9, -1, 1 << 64)) & MASK64
    return _unxorshift(x, 30)


def derive_seed(*parts) -> int:
    """Seed = FNV-1a64 of the '|'-joined decimal/str parts. Parts must be ints or ASCII identifiers."""
    return fnv1a64("|".join(str(p) for p in parts))


if __name__ == "__main__":
    # Self-checks (also executed by run_all.py)
    assert rdiv(5, 2) == 3 and rdiv(-5, 2) == -3 and rdiv(4, 2) == 2 and rdiv(-4, 2) == -2 and rdiv(1, 3) == 0
    assert mul_bp(10_000, 9_000) == 9_000
    t = [(0, 10_000), (100, 5_000)]
    assert interp(t, -5) == 10_000 and interp(t, 50) == 7_500 and interp(t, 500) == 5_000
    r1, r2 = SplitMix64(42), SplitMix64(42)
    assert [r1.next_u64() for _ in range(5)] == [r2.next_u64() for _ in range(5)]
    # Published SplitMix64 reference: seed 0 -> first output 0xE220A8397B1DCDAF
    assert SplitMix64(0).next_u64() == 0xE220A8397B1DCDAF
    assert round_money(12_345) == 12_350 and round_money(123_449) == 123_400 and round_money(1_234_500) == 1_235_000
    print("lsax_ref_math self-check OK")
