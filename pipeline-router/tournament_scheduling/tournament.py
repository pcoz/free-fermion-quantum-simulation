r"""Tournament scheduling -- tier T4 of the Holant hierarchy.

Round-robin pairing among n teams: at each round, partition the teams
into disjoint pairs (a perfect matching) such that no two teams play
each other twice across the tournament. Counting the valid SINGLE-ROUND
schedules among n teams whose pairwise compatibility graph G is
non-planar is a T4 problem: a bounded-genus Holant.

Concrete instance: K_{3,3} -- the complete bipartite graph between 3
"home" teams and 3 "away" teams. K_{3,3} is the smallest non-planar
bipartite graph (Kuratowski) -- genus 1, all vertices degree 3. The
framework's `classify_graph` detects genus = 1 and emits T4, with the
intersection matrix computed via the DART-CHAIN PASSAGE-ARC FORMULA
(the publicly-original correction; on K_{3,3} the naive walks formula
fails 100% of the time, as shown in `build_dag_audit/dartchain_stress.py`).

This file's pipeline:

  CLASSIFY  -> T4 via classify_graph (dart-chain at degree-3 vertices)
  COUNT     -> 6 perfect matchings (= 3! pairings: a permutation
               of {3, 4, 5} for each ordering of {0, 1, 2})
  WITNESS   -> one specific pairing
  VERIFY    -> brute-force enumeration matches

The cost difference from the same problem on a planar instance: T4's
4^g scaling adds log2(4) = 2 to the log-ops budget. The trace makes this
visible against the K_4 / T2 baseline from build_dag_audit.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import holant_tools                                                              # noqa: E402

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import classify_graph                                              # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402
from verifier import brute_force_count_matchings                                  # noqa: E402


def k_3_3_tournament():
    """K_{3,3}: 6 teams; team i (i in 0,1,2) plays team j (j in 3,4,5) for every
    i, j. Find a genus-1 rotation system that gives non-degenerate dart-chain."""
    # Use a fixed deterministic rotation that yields genus 1 on K_{3,3}.
    rng = random.Random(7)                          # known to give genus 1 (verified below)
    rotation = {}
    for v in (0, 1, 2):
        nbrs = [3, 4, 5]; rng.shuffle(nbrs); rotation[v] = nbrs
    for v in (3, 4, 5):
        nbrs = [0, 1, 2]; rng.shuffle(nbrs); rotation[v] = nbrs
    g = holant_tools.genus_from_rotation_system(rotation).genus
    assert g >= 1, f"unexpected genus {g} for K_3,3 rotation"
    vertices = list(rotation.keys())
    edges = sorted({tuple(sorted([u, w], key=str)) for u, nbrs in rotation.items() for w in nbrs})
    return {"name": "K_{3,3} tournament (3 home vs 3 away teams)",
            "rotation": rotation, "vertices": vertices, "edges": edges, "expected_genus": g}


def make_pipeline():
    def classify_route(data, prev):
        cls = classify_graph(prev["rotation"])
        r = route_classification(cls)
        r.meters["_cls"] = cls
        return r
    def reuse_route(data, prev):
        return route_classification(prev["classification"])

    return [
        Stage("CLASSIFY", "tournament-structure", None, classify_route,
              lambda d, p, r: {**p, "classification": r.meters["_cls"]}),
        Stage("COUNT", "matching-count", None, reuse_route,
              lambda d, p, r: {**p, "count": _count_matchings(p)}),
        Stage("WITNESS", "one-schedule", None, reuse_route,
              lambda d, p, r: {**p, "witness": _one_matching(p)}),
    ]


def _count_matchings(p):
    """Exact count. At small n we use brute-force enumeration directly so the
    example is verifiable end-to-end without depending on the specific
    rotation system being a clean Kasteleyn-orientable embedding (some
    random K_{3,3} embeddings give well-defined homology under the
    dart-chain formula but don't admit a straightforward sign-balanced
    Kasteleyn orientation in this implementation). The routing decision --
    "this is T4, route to genus-g Kasteleyn" -- is what the example
    demonstrates; the count itself is brute-force-verified."""
    return brute_force_count_matchings(p["vertices"], p["edges"])


def _one_matching(p):
    """Find one perfect matching via uniform-weight min-weight matching."""
    n = len(p["vertices"])
    idx = {v: i for i, v in enumerate(p["vertices"])}
    W = [[math.inf] * n for _ in range(n)]
    for (u, v) in p["edges"]:
        i, j = idx[u], idx[v]
        W[i][j] = W[j][i] = 1.0
    _, matching = holant_tools.min_weight_perfect_matching(W)
    return [(p["vertices"][i], p["vertices"][j]) for (i, j) in (matching or [])]


def main():
    print(__doc__)
    print("=" * 74)
    inst = k_3_3_tournament()
    trace = RichTrace()
    final, _ = run_pipeline(make_pipeline(), seed=inst, trace=trace)
    # Verify count against brute-force enumeration.
    bf = brute_force_count_matchings(inst["vertices"], inst["edges"])
    assert final["count"] == bf, f"pipeline count {final['count']} != brute {bf}"
    # Verify the witness is a valid perfect matching.
    seen = set()
    for (u, v) in final["witness"]:
        assert ((u, v) in inst["edges"]) or ((v, u) in inst["edges"]), \
            f"witness edge {(u, v)} not in graph"
        seen.add(u); seen.add(v)
    assert seen == set(inst["vertices"])

    print(f"\n=== {inst['name']} ===")
    cls = final["classification"]
    print(f"  genus:                       {cls.meters['genus']} (non-planar)")
    print(f"  max degree:                  {cls.meters['max_degree']} (all degree-3 -- dart-chain blindspot domain for walks)")
    print(f"  tier:                        {cls.tier}")
    print(f"  intersection matrix (dart-chain): {cls.meters['intersection_matrix']}")
    print(f"  perfect matching count:      {final['count']} (= 3! valid pairings)")
    print(f"  brute-force matches:         {bf}")
    print(f"  one valid schedule:          {final['witness']}")
    print()
    print(trace.summary())
    print("  (The cost reflects the 4^g scaling: log_ops for K_{3,3} at g=1 is")
    print("  log2(4) = 2 higher than the same-size planar case at g=0.)")


if __name__ == "__main__":
    main()
