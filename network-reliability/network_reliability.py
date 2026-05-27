r"""Exact correlated-failure risk for a planar utility / telecom grid -- where the
standard approaches fail exactly where it costs the most: the rare big-outage tail.

The problem
-----------
Components in a grid (power lines, fibre links) fail occasionally. The dangerous
case is *correlated* failure -- a storm knocks out neighbouring components
together -- because that's how a handful of failures becomes a blackout. Two
standard approaches both mislead here:

  * "Assume failures are independent" -- analytically convenient, but it badly
    UNDERESTIMATES the chance of a big simultaneous outage (it ignores the
    correlation that bunches failures together).
  * "Monte-Carlo simulate it" -- but a large outage is rare, so a finite sample
    sees it zero times and reports probability 0 -- worst precisely in the tail
    you care about.

What we compute (exactly)
-------------------------
We model correlated failures as a planar Ising / Gibbs field (neighbours coupled,
so a failure makes neighbouring failures more likely) and compute the EXACT
outage statistics: each component's failure probability, the expected number of
simultaneous failures, and the full outage-size distribution -- in particular the
exact probability of a large simultaneous outage. The exact tail is the number a
risk model, an insurer, or a regulator actually needs.

Honest scope
------------
Connectivity reliability ("is the grid still one connected piece?") is #P-hard
*even on planar graphs* (Provan 1986) -- planarity alone does not make it easy.
What IS planar-tractable is the correlated-failure *statistics* above (a planar
Ising partition function), which is exactly the regime where the independent
assumption and Monte-Carlo both fail. At the small grid here the exact statistics
are by enumeration (the verifiable ground truth); at scale, that planar partition
function is computed by the same FKT/Pfaffian machinery used in the Ising example
(`../ising-phase-transition/`).

Run:  python network_reliability.py
"""
import math

import numpy as np


def grid_bonds(R, C):
    """Nearest-neighbour bonds of an R x C grid of components (index r*C + c)."""
    bonds = []
    for r in range(R):
        for c in range(C):
            i = r * C + c
            if c + 1 < C:
                bonds.append((i, i + 1))
            if r + 1 < R:
                bonds.append((i, i + C))
    return bonds


def exact_failure_statistics(R, C, J, h):
    """Enumerate all 2^(R*C) up/down configurations of the grid (s = +1 up,
    -1 down/failed), weighted by the correlated-failure Gibbs model
        P(s) ~ exp( J * sum_<ij> s_i s_j  +  h * sum_i s_i ),
    with J > 0 coupling neighbours (correlation) and h > 0 biasing toward "up"
    (a low base failure rate). Returns the exact per-component failure
    probability and the outage-size distribution P(#failed = k)."""
    n = R * C
    bonds = grid_bonds(R, C)
    bits = ((np.arange(2 ** n)[:, None] >> np.arange(n)) & 1)   # 1 = failed (down)
    s = 1 - 2 * bits                                            # +1 up, -1 down
    E = np.zeros(2 ** n)
    for (i, j) in bonds:
        E += J * s[:, i] * s[:, j]
    E += h * s.sum(1)
    w = np.exp(E)
    p = w / w.sum()                                             # exact probabilities
    n_failed = bits.sum(1)
    per_component = np.array([w[bits[:, i] == 1].sum() / w.sum() for i in range(n)])
    outage_dist = np.bincount(n_failed, weights=p, minlength=n + 1)  # P(#failed = k)
    return per_component, outage_dist, p, n_failed


def main():
    print(__doc__)
    R, C, J, h = 4, 4, 0.5, 0.85
    n = R * C
    per_comp, outage, p, n_failed = exact_failure_statistics(R, C, J, h)
    pbar = float(per_comp.mean())
    expected = float((np.arange(n + 1) * outage).sum())

    print("=" * 70)
    print(f"Planar grid: {R}x{C} = {n} components | correlated-failure model (J={J}, h={h})")
    print("=" * 70)
    print(f"  per-component failure probability: {pbar:.3%} (mean)")
    print(f"  expected simultaneous failures   : {expected:.3f}")

    # --- correlated (exact) vs the "independent" assumption, matched on rate ---
    from math import comb
    indep = np.array([comb(n, k) * pbar ** k * (1 - pbar) ** (n - k) for k in range(n + 1)])
    print("\n  Probability of >= k simultaneous failures: exact vs 'assume independent'")
    print(f"  {'k':>3} | {'exact (correlated)':>19} | {'independent':>13} | underestimate")
    print("  " + "-" * 60)
    for k in range(2, n + 1, 2):
        ex, iid = outage[k:].sum(), indep[k:].sum()
        if ex < 1e-13:
            continue
        factor = ex / iid if iid > 1e-300 else float("inf")
        print(f"  {k:>3} | {ex:>19.3e} | {iid:>13.3e} | {factor:>10.0f}x")
    print("  -> ignoring correlation underestimates big-outage risk by orders of")
    print("     magnitude -- and the gap grows for the largest, costliest outages.")

    # --- Monte-Carlo vs exact in the tail (the number you actually need) ---
    k_major = max(2, n // 2)
    truth = float(outage[k_major:].sum())
    print(f"\n  A 'major outage' (>= {k_major} of {n} failed): exact probability = {truth:.3e}")
    rng = np.random.default_rng(0)
    for N in (10_000, 100_000):
        zero_runs = 0
        for _ in range(20):
            samp = rng.choice(2 ** n, size=N, p=p)
            if (n_failed[samp] >= k_major).mean() == 0.0:
                zero_runs += 1
        print(f"    Monte-Carlo, {N:>7,} samples: reported probability 0 in "
              f"{zero_runs}/20 runs -> it simply never sees the event")
    print("    The exact method returns the real, nonzero risk; sampling cannot.")

    print("\n" + "=" * 70)
    print("Why exactness matters here")
    print("=" * 70)
    print("  Risk pricing, regulatory compliance, and safety cases need the exact")
    print("  tail probability of a correlated outage. The independent assumption")
    print("  is off by orders of magnitude, and Monte-Carlo returns 0 for the rare")
    print("  events that dominate the risk. Exact, structure-exploiting computation")
    print("  is what makes the right number available at all.")


if __name__ == "__main__":
    main()
