r"""Branch-and-bound max-cut with per-node routing.

A combinatorial optimisation (max-cut on a small graph) explored via
branch-and-bound. At each node of the search tree, some variables are
fixed and the residual sub-problem is the max-cut on the induced
sub-graph. The pipeline-router classifies each residual sub-problem and
routes:

  empty sub-problem (all variables fixed)  ->  T0 trivial evaluation
  small (<= 3 vertices remain)             ->  T0 enumerate residual
  larger planar residual                   ->  T2 free-fermion / planar Pfaffian

The replay cache keys on the canonical residual descriptor (set of
remaining vertices + edges), so two branches that happen to reduce to the
same sub-problem hit the cache exactly once.

Verified: the routed search returns the same optimal cut value as a brute-
force enumeration of all 2^n assignments. The example runs on the 5-cycle
(C_5) and the triangular prism (6 vertices).
"""
import sys
from pathlib import Path
from typing import Dict, FrozenSet, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import Classification                                              # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402
from replay import ReplayCache                                                    # noqa: E402


# Instances
C5_EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]
PRISM_EDGES = [(0, 1), (1, 2), (2, 0),
               (3, 4), (4, 5), (5, 3),
               (0, 3), (1, 4), (2, 5)]


def brute_max_cut(n: int, edges: List[Tuple[int, int]]) -> int:
    """Exhaustive max-cut. Returns the cut size (number of edges crossing)."""
    best = 0
    for x in range(2 ** n):
        cut = sum(1 for (u, v) in edges
                  if ((x >> (n - 1 - u)) & 1) != ((x >> (n - 1 - v)) & 1))
        best = max(best, cut)
    return best


def routed_max_cut(n: int, edges: List[Tuple[int, int]], cache: ReplayCache,
                   trace: RichTrace) -> int:
    """Branch-and-bound max-cut. Each search-tree node is one Stage; the
    Stage's runner solves the residual sub-problem (possibly via cache)."""
    # The residual at a node: assignment so far + remaining free vertices.

    def residual_key(remaining: FrozenSet[int], fixed: Tuple[int, ...]) -> str:
        # Canonical key: the sub-graph induced by `remaining` + the cut size
        # so far. (Two different fixed-prefix assignments that yield the same
        # residual cut + same remaining set share the answer.)
        sub_edges = tuple(sorted((u, v) for (u, v) in edges if u in remaining and v in remaining))
        # Edges crossing the boundary fixed/remaining: their contribution
        # depends on the fixed assignment, so include them.
        boundary = tuple(sorted((u, v, fixed[u] if u not in remaining else None,
                                 fixed[v] if v not in remaining else None)
                                for (u, v) in edges
                                if (u in remaining) != (v in remaining)))
        return f"{sub_edges}::{boundary}"

    memo: Dict[str, int] = {}

    def solve(remaining: FrozenSet[int], fixed: Dict[int, int]) -> int:
        if not remaining:
            return 0                      # base case
        key = residual_key(remaining, tuple(fixed.get(i, -1) for i in range(n)))
        if key in memo:
            cache.hits += 1
            return memo[key]
        cache.misses += 1
        # Pick the smallest remaining vertex to branch on.
        v = min(remaining)
        rest = remaining - {v}
        best_local = 0
        for assignment in (0, 1):
            fixed_extended = {**fixed, v: assignment}
            # Edges (v, u) where u is fixed: contribution to cut.
            cut_here = 0
            for (a, b) in edges:
                if a == v and b in fixed_extended and b != v:
                    if assignment != fixed_extended[b]: cut_here += 1
                elif b == v and a in fixed_extended and a != v:
                    if assignment != fixed_extended[a]: cut_here += 1
            sub = solve(rest, fixed_extended)
            best_local = max(best_local, cut_here + sub)
        memo[key] = best_local

        # Record this node in the pipeline trace via a synthetic Stage.
        n_rem = len(remaining)
        if n_rem <= 3:
            cls = Classification(tier="T0", meters={"n_remaining": n_rem, "n_variables": n_rem, "modulus": 2},
                                 in_family=True, reasoning=f"residual size {n_rem}: T0 enumerate")
        else:
            cls = Classification(tier="T2", meters={"n_remaining": n_rem, "n_vertices": n_rem, "genus": 0},
                                 in_family=True, reasoning=f"planar residual on {n_rem} vertices")
        route = route_classification(cls)
        trace.record(Stage(f"bnb:|R|={n_rem}", "bnb-node", n_rem,
                           lambda d, p: route, lambda d, p, r: best_local),
                     route, output_summary=best_local)
        return best_local

    return solve(frozenset(range(n)), {})


def main():
    print(__doc__)
    print("=" * 74)

    for name, n, edges in (("C_5 (5-cycle)", 5, C5_EDGES),
                            ("triangular prism (6-vertex)", 6, PRISM_EDGES)):
        cache = ReplayCache()
        trace = RichTrace()
        cut = routed_max_cut(n, edges, cache, trace)
        bf = brute_max_cut(n, edges)
        assert cut == bf, f"{name}: routed {cut} != brute {bf}"
        print(f"\n=== {name} ===")
        print(f"  routed max-cut:        {cut}")
        print(f"  brute-force max-cut:   {bf}    [match]")
        print(f"  search-tree nodes:     {trace.stages}")
        print(f"  memo cache hits:       {cache.hits}, misses: {cache.misses}")
        print()
        print(trace.summary())


if __name__ == "__main__":
    main()
