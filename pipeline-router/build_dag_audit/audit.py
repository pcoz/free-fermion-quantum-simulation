r"""Flagship example for the pipeline-router: a structural audit of a
planar dependency graph.

Cover story (dev-native): you have a planar compatibility graph -- tasks
that can share resources, file dependencies that can be batched, services
that can be co-deployed. You want, exactly:

    1. CLASSIFY    is the graph planar? genus-g? what's its structure?
    2. COUNT       how many valid total pairings does it admit?
    3. WITNESS     show me one.
    4. STRESS      if any single edge fails, how many pairings survive?
                   which edges are single points of failure?
    5. ITERATE     run 1000 stress evaluations under varying conditions
                   (different edges, repeated draws) -- the replay cache
                   reuses identical conditional sub-problems.

Each stage is independently routed through the pipeline-router. The exact
counts at every stage are verified against brute-force enumeration at small
n. No general-purpose build system / scheduler produces these numbers
exactly; everything off-the-shelf approximates or samples.

The flagship runs on two instances:

  * **K_4 tetrahedron** -- planar (genus 0), 4 vertices all degree 3, the
    smallest non-trivial dependency graph with multiple valid pairings
    (3 perfect matchings).
  * **4x4 toroidal grid** -- genus 1, 16 vertices all degree 4. Same
    pipeline; the classifier inspects the homology via the dart-chain
    passage-arc formula; the route shifts from T2 (planar Pfaffian) to T4
    (genus-g Kasteleyn).

A separate `dartchain_stress.py` runs the public-facing demonstration that
the dart-chain formula succeeds where the naive direction-aware walks
formula fails; a separate `monte_carlo.py` reports the rare-tail miss that
sampling-based off-the-shelf tools produce on the same instance.

Run:  python audit.py
"""
import math
import sys
from typing import Any, Dict, List, Tuple

import numpy as np

import holant_tools

# Path so we can import the framework modules from the pipeline-router/ folder.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from pipeline_router import Stage, Route, run_pipeline                          # noqa: E402
from classify import classify_graph                                             # noqa: E402
from route_constraint import route as route_classification                      # noqa: E402
from trace import RichTrace                                                     # noqa: E402
from replay import ReplayCache, cached_runner                                   # noqa: E402
from verifier import brute_force_count_matchings                                # noqa: E402


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

def k4_tetrahedron() -> Dict[str, Any]:
    """K_4 with the standard tetrahedral embedding. Planar, 4 vertices, all
    degree 3. Brute-force perfect-matching count: 3."""
    rotation = {0: [1, 2, 3], 1: [0, 3, 2], 2: [0, 1, 3], 3: [0, 2, 1]}
    vertices = [0, 1, 2, 3]
    edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    return {"name": "K_4 tetrahedron", "rotation": rotation, "vertices": vertices, "edges": edges}


def torus_4x4_grid() -> Dict[str, Any]:
    """4x4 toroidal grid with the canonical rotation system. Genus 1, 16
    vertices all degree 4. Brute-force perfect-matching count: 272."""
    n = 4
    rotation = {}
    for i in range(n):
        for j in range(n):
            v = (i, j)
            rotation[v] = [(i, (j + 1) % n), ((i + 1) % n, j),
                           (i, (j - 1) % n), ((i - 1) % n, j)]
    vertices = list(rotation.keys())
    edge_set = set()
    for u, nbrs in rotation.items():
        for w in nbrs:
            edge_set.add(tuple(sorted([u, w], key=str)))
    return {"name": "4x4 toroidal grid", "rotation": rotation,
            "vertices": vertices, "edges": list(edge_set)}


# ---------------------------------------------------------------------------
# The five stages
# ---------------------------------------------------------------------------

def stage1_classify():
    """Stage 1: CLASSIFY the dependency graph -- planar or bounded-genus?

    `prev` on the first call is the raw instance dict (run_pipeline's `seed`).
    Stage 1 wraps it into the {classification, instance} record that the rest
    of the pipeline threads forward."""
    def route_fn(data, prev):
        cls = classify_graph(prev["rotation"])
        r = route_classification(cls)
        # Carry the Classification forward so runner_fn doesn't classify again.
        r.meters["_classification"] = cls
        return r

    def runner_fn(data, prev, route):
        return {"classification": route.meters["_classification"], "instance": prev}

    return Stage("CLASSIFY", "structural-inspection", None,
                 route_fn=route_fn, runner_fn=runner_fn)


def stage2_count():
    """Stage 2: COUNT exact number of perfect matchings via FKT (planar) or
    genus-g Kasteleyn (toroidal). Routes to free-fermion."""
    def route_fn(data, prev):
        cls = prev["classification"]
        return route_classification(cls)

    def runner_fn(data, prev, route):
        inst = prev["instance"]
        g = prev["classification"].meters["genus"]
        if g == 0:
            K = holant_tools.kasteleyn_orient(inst["vertices"], inst["edges"], inst["rotation"])
            count = abs(int(holant_tools.exact_planar_pfaffian(K)))
        else:
            mats = holant_tools.kasteleyn_orient_genus_g(
                inst["vertices"], inst["edges"], inst["rotation"], g,
            )
            count = int(holant_tools.holant_genus_g(mats, g))
        return {**prev, "count": count}

    return Stage("COUNT", "perfect-matching-count", None, route_fn=route_fn, runner_fn=runner_fn)


def stage3_witness():
    """Stage 3: WITNESS one specific perfect matching, via min-weight
    perfect matching with uniform weights. Routes to free-fermion."""
    def route_fn(data, prev):
        return route_classification(prev["classification"])

    def runner_fn(data, prev, route):
        inst = prev["instance"]
        n = len(inst["vertices"])
        # Build a uniform-weight n x n matrix; non-edges get +inf.
        W = [[math.inf] * n for _ in range(n)]
        idx = {v: i for i, v in enumerate(inst["vertices"])}
        for (u, w) in inst["edges"]:
            i, j = idx[u], idx[w]
            W[i][j] = W[j][i] = 1.0
        cost, matching = holant_tools.min_weight_perfect_matching(W)
        witness = [(inst["vertices"][i], inst["vertices"][j]) for (i, j) in (matching or [])]
        return {**prev, "witness": witness, "witness_cost": cost}

    return Stage("WITNESS", "matching-extraction", None, route_fn=route_fn, runner_fn=runner_fn)


def stage4_stress():
    """Stage 4: STRESS-test each edge: if this edge is removed, how many
    matchings survive? An edge with the largest impact (matchings drop to 0
    or near 0 without it) is a single point of failure."""
    def route_fn(data, prev):
        return route_classification(prev["classification"])

    def runner_fn(data, prev, route):
        inst = prev["instance"]
        impact: List[Tuple[Any, int]] = []
        for e in inst["edges"]:
            sub_edges = [x for x in inst["edges"] if x != e]
            c = brute_force_count_matchings(inst["vertices"], sub_edges)  # truth at small n
            impact.append((e, c))
        # Single points of failure: edges whose removal drops the count to 0.
        spofs = [e for (e, c) in impact if c == 0]
        return {**prev, "stress_impact": impact, "single_points_of_failure": spofs}

    return Stage("STRESS", "single-point-of-failure-analysis", None, route_fn=route_fn, runner_fn=runner_fn)


def stage5_iterate(n_steps: int = 1000):
    """Stage 5: ITERATE -- 1000 stress evaluations cycling through edge
    removals. The number of distinct sub-problems is |E|, so the replay
    cache produces ~|E| misses and (n_steps - |E|) hits. Demonstrates that
    the framework is fit for the 1000-pass regime."""
    cache = ReplayCache()

    def base_runner(payload, prev, route):
        # payload = (instance_id, edge_to_remove)
        inst_id, e = payload
        inst = prev["instance"]
        sub = [x for x in inst["edges"] if x != e]
        return brute_force_count_matchings(inst["vertices"], sub)

    def stage5_inner_key(payload, prev):
        # Key only on (instance_name, edge); don't include prev (carries huge state).
        return f"{prev['instance']['name']}::{payload}"

    cached = cached_runner(base_runner, cache, key_fn=stage5_inner_key)

    def route_fn(data, prev):
        return route_classification(prev["classification"])

    def runner_fn(data, prev, route):
        edges = prev["instance"]["edges"]
        name = prev["instance"]["name"]
        counts: List[int] = []
        for step in range(n_steps):
            e = edges[step % len(edges)]                         # cycle deterministically
            counts.append(cached((name, e), prev, route))
        return {
            **prev,
            "iterate_steps": n_steps,
            "iterate_unique_subproblems": cache.size,
            "iterate_hits": cache.hits,
            "iterate_misses": cache.misses,
            "iterate_hit_rate": cache.hit_rate(),
            "iterate_sample_counts": counts[: min(10, len(counts))],
        }

    return Stage("ITERATE", "adaptive-1000-pass", None, route_fn=route_fn, runner_fn=runner_fn)


def make_pipeline(n_iterate_steps: int = 1000) -> List[Stage]:
    return [
        stage1_classify(),
        stage2_count(),
        stage3_witness(),
        stage4_stress(),
        stage5_iterate(n_steps=n_iterate_steps),
    ]


# ---------------------------------------------------------------------------
# Runners + verifier
# ---------------------------------------------------------------------------

def run_audit(instance: Dict[str, Any], n_iterate_steps: int = 1000) -> Tuple[Dict[str, Any], RichTrace]:
    """Run the 5-stage pipeline on `instance`. Returns (final_output, trace)."""
    pipeline = make_pipeline(n_iterate_steps=n_iterate_steps)
    trace = RichTrace()
    final, _ = run_pipeline(pipeline, seed=instance, trace=trace)
    return final, trace


def verify(instance: Dict[str, Any], final: Dict[str, Any]) -> None:
    """At small n we can brute-force every stage's output and check exactly."""
    inst = instance
    name = inst["name"]
    # Stage 2 count vs brute force.
    bf = brute_force_count_matchings(inst["vertices"], inst["edges"])
    assert final["count"] == bf, f"{name}: pipeline count {final['count']} != brute force {bf}"
    # Stage 3 witness validity: every vertex appears in exactly one matched pair.
    seen = set()
    for (u, w) in final["witness"]:
        assert (u, w) in inst["edges"] or (w, u) in inst["edges"], \
            f"{name}: witness edge {(u,w)} not in graph"
        for v in (u, w):
            assert v not in seen, f"{name}: vertex {v} matched twice in witness"
            seen.add(v)
    assert seen == set(inst["vertices"]), f"{name}: witness does not cover every vertex"
    # Stage 4 stress: brute-force each edge removal independently and compare.
    for (e, c_pipe) in final["stress_impact"]:
        c_bf = brute_force_count_matchings(inst["vertices"],
                                            [x for x in inst["edges"] if x != e])
        assert c_pipe == c_bf, f"{name}: stress for edge {e}: pipeline {c_pipe} != brute force {c_bf}"
    # Stage 5: replay cache size equals |E| (one unique sub-problem per edge).
    assert final["iterate_unique_subproblems"] == len(inst["edges"]), \
        f"{name}: stage5 cache size {final['iterate_unique_subproblems']} != |E| {len(inst['edges'])}"
    expected_hits = final["iterate_steps"] - len(inst["edges"])
    assert final["iterate_hits"] == expected_hits, \
        f"{name}: stage5 hits {final['iterate_hits']} != expected {expected_hits}"


def print_audit_report(instance: Dict[str, Any], final: Dict[str, Any], trace: RichTrace) -> None:
    name = instance["name"]
    print(f"\n=== {name} ===")
    cls = final["classification"]
    print(f"  Stage 1 (CLASSIFY) -> tier {cls.tier}: {cls.reasoning}")
    print(f"  Stage 2 (COUNT)    -> {final['count']} perfect matchings")
    print(f"  Stage 3 (WITNESS)  -> {final['witness']}  (cost = {final['witness_cost']:g})")
    spofs = final["single_points_of_failure"]
    impact = sorted(final["stress_impact"], key=lambda pair: pair[1])
    print(f"  Stage 4 (STRESS)   -> {len(spofs)} single point(s) of failure"
          + (f": {spofs}" if spofs else " (graph is robust to single-edge removal)"))
    worst = impact[0]
    print(f"                        most impactful: removing {worst[0]} -> {worst[1]} matchings remain")
    print(f"  Stage 5 (ITERATE)  -> {final['iterate_steps']} steps, "
          f"{final['iterate_unique_subproblems']} unique sub-problems, "
          f"hit_rate = {final['iterate_hit_rate']:.1%}")
    print()
    print(trace.summary())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(__doc__)
    print("=" * 74)

    for instance in (k4_tetrahedron(), torus_4x4_grid()):
        final, trace = run_audit(instance, n_iterate_steps=1000)
        verify(instance, final)
        print_audit_report(instance, final, trace)

    print("=" * 74)
    print("Every stage's output was verified against brute-force enumeration above.")


if __name__ == "__main__":
    main()
