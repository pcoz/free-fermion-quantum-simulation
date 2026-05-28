r"""Tropical max-weight perfect matching -- tier T6 of the Holant hierarchy.

Weighted optimisation under the tropical (min, +) semiring. For planar
in-family instances, the framework routes to `tropical-pfaffian` (the
exact poly-time route via holant-tools' `min_weight_perfect_matching`,
which is the tropical Pfaffian via the Mucha-Sankowski / Karp-Tardos
construction). For non-planar or otherwise out-of-family instances, the
framework routes to `advised:tropical-klein` -- a HONEST STOP. Native
tropical Klein integration is pending in holant-tools' roadmap.

This file's pipeline solves max-weight matching on small planar weighted
graphs and brute-force-verifies the answer. Max-weight is computed by
negating weights and running min-weight under the standard (min, +)
algorithm: the framework's T6-planar route handles this exactly.

Demonstrated on:
  * a 4-cycle with four edge weights (small enough to verify by hand);
  * a 6-vertex planar-prism graph (a triangular prism); verified by
    exhaustive enumeration of perfect matchings.

For the non-planar honest-stop case, the same pipeline is run on a
small non-planar weighted instance; the classifier emits T6 advised,
the runner reports the advised member, no false computation is done.
"""
import math
import sys
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import holant_tools                                                              # noqa: E402

from pipeline_router import Stage, Route, run_pipeline                           # noqa: E402
from classify import Classification                                               # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402


def planar_4_cycle():
    """C_4 with edge weights. 2 perfect matchings: {(0,1),(2,3)} cost 3+4=7,
    and {(0,3),(1,2)} cost 1+2=3.  Max-weight is 7."""
    return {
        "name": "planar 4-cycle",
        "weights": np.array([
            [math.inf, 3.0, math.inf, 1.0],
            [3.0, math.inf, 2.0, math.inf],
            [math.inf, 2.0, math.inf, 4.0],
            [1.0, math.inf, 4.0, math.inf],
        ]),
        "n": 4,
        "planar": True,
    }


def planar_prism_6():
    """The 6-vertex triangular prism graph. Two triangles (0,1,2) and (3,4,5)
    connected by vertical edges (0,3), (1,4), (2,5). Planar. 4 perfect
    matchings; weighted, find the max."""
    INF = math.inf
    W = np.full((6, 6), INF)
    # Triangle top: 0-1-2-0
    W[0, 1] = W[1, 0] = 1.0
    W[1, 2] = W[2, 1] = 5.0
    W[0, 2] = W[2, 0] = 2.0
    # Triangle bottom: 3-4-5-3
    W[3, 4] = W[4, 3] = 3.0
    W[4, 5] = W[5, 4] = 1.0
    W[3, 5] = W[5, 3] = 6.0
    # Vertical edges
    W[0, 3] = W[3, 0] = 4.0
    W[1, 4] = W[4, 1] = 2.0
    W[2, 5] = W[5, 2] = 1.0
    return {"name": "triangular prism", "weights": W, "n": 6, "planar": True}


def k_3_3_weighted():
    """K_{3,3} -- non-planar (genus 1). Pipeline must report 'advised'."""
    INF = math.inf
    W = np.full((6, 6), INF)
    for u in (0, 1, 2):
        for v in (3, 4, 5):
            W[u, v] = W[v, u] = float(u + v)
    return {"name": "K_{3,3} (non-planar)", "weights": W, "n": 6, "planar": False}


def make_pipeline():
    def route_fn(data, prev):
        meters = {"n_vertices": prev["n"], "planar": prev["planar"], "weighted": True}
        in_family = prev["planar"]
        cls = Classification(tier="T6", meters=meters, in_family=in_family,
                             reasoning=("planar weighted optimisation"
                                        if in_family else
                                        "non-planar weighted optimisation; out of family pending tropical Klein"))
        return route_classification(cls)

    def runner_fn(data, prev, route):
        if not prev["planar"]:
            return {**prev, "max_weight": None, "matching": None,
                    "verdict": "advised: external solver (CP-SAT / MILP)"}
        W = prev["weights"]
        W_neg = np.where(np.isfinite(W), -W, math.inf)
        cost, matching = holant_tools.min_weight_perfect_matching(W_neg.tolist())
        max_w = -cost if cost != math.inf else None
        return {**prev, "max_weight": max_w, "matching": matching, "verdict": "ok"}

    return [Stage("MAX-WEIGHT", "tropical-pfaffian", None, route_fn, runner_fn)]


def brute_max_weight(prob):
    """Brute-force max-weight perfect matching by enumerating all matchings."""
    n = prob["n"]; W = prob["weights"]
    def all_matchings(remaining):
        if not remaining:
            return [[]]
        first = remaining[0]
        out = []
        for j in remaining[1:]:
            if not math.isinf(W[first][j]):
                rest = [x for x in remaining[1:] if x != j]
                for sub in all_matchings(rest):
                    out.append([(first, j)] + sub)
        return out
    best = -math.inf
    for m in all_matchings(list(range(n))):
        w = sum(W[i][j] for (i, j) in m)
        if w > best:
            best = w
    return best if best > -math.inf else None


def main():
    print(__doc__)
    print("=" * 74)
    pipeline = make_pipeline()
    for prob in (planar_4_cycle(), planar_prism_6(), k_3_3_weighted()):
        trace = RichTrace()
        final, _ = run_pipeline(pipeline, seed=prob, trace=trace)
        print(f"\n=== {prob['name']} ===")
        print(f"  vertices:        {prob['n']}    planar: {prob['planar']}")
        if final["verdict"] == "ok":
            bf = brute_max_weight(prob)
            assert abs(final["max_weight"] - bf) < 1e-9, \
                f"{prob['name']}: pipeline {final['max_weight']} vs brute {bf}"
            print(f"  pipeline result: max-weight matching {final['matching']}")
            print(f"                   total weight = {final['max_weight']:.1f}")
            print(f"  brute-force max-weight:           {bf:.1f}    [pipeline matches]")
        else:
            print(f"  pipeline result: {final['verdict']}")
            print(f"  (the classifier honestly stops at the family boundary; no false answer)")


if __name__ == "__main__":
    main()
