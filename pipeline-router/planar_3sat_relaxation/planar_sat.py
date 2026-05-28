r"""Planar 2-SAT / binary Holant -- tier T2 of the Holant hierarchy in a
different application domain (constraint satisfaction).

A 2-SAT clause `(x_i OR x_j)` corresponds exactly to the symmetric
arity-2 OR signature [0, 1, 1] (value 0 when both inputs are 0;
value 1 otherwise). A 2-SAT INSTANCE is then a graph: variables are
vertices, each clause is an edge labelled with the OR signature, and the
"counting" question -- how many variable assignments satisfy every
clause -- is a planar binary Holant on that graph (when the graph is
planar).

This is the same tier the flagship build_dag_audit's K_4 routes to, but
applied to constraint satisfaction rather than dependency-graph analysis.
The pipeline:

  CLASSIFY  -> T2 via classify_graph (planar binary Holant)
  COUNT     -> exact number of satisfying assignments by enumeration
               for verification at small n; in the field-strength runner
               this would be the planar Pfaffian via holant-tools.

Demonstrated on:
  * a triangle (3 variables, 3 OR-clauses);
  * a 4-cycle (4 variables, 4 OR-clauses);
  * a "bowtie" (two triangles sharing a vertex; planar).

Each case has its 2^n possible assignments enumerated; the pipeline's
count is verified against brute force.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import classify_graph                                              # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402


def triangle_or():
    """3 variables, clauses (x0 v x1), (x1 v x2), (x2 v x0). All-OR."""
    return {
        "name": "triangle: 3 OR-clauses",
        "vars": [0, 1, 2],
        "clauses": [(0, 1), (1, 2), (2, 0)],
        "rotation": {0: [1, 2], 1: [2, 0], 2: [0, 1]},
    }


def four_cycle_or():
    """4 variables, 4 OR-clauses around the cycle."""
    return {
        "name": "4-cycle: 4 OR-clauses",
        "vars": [0, 1, 2, 3],
        "clauses": [(0, 1), (1, 2), (2, 3), (3, 0)],
        "rotation": {0: [1, 3], 1: [2, 0], 2: [3, 1], 3: [0, 2]},
    }


def bowtie_or():
    """5 vertices, two triangles sharing vertex 0."""
    return {
        "name": "bowtie: 2 triangles sharing a vertex",
        "vars": [0, 1, 2, 3, 4],
        "clauses": [(0, 1), (1, 2), (2, 0), (0, 3), (3, 4), (4, 0)],
        "rotation": {0: [1, 2, 3, 4],
                     1: [2, 0], 2: [0, 1],
                     3: [4, 0], 4: [0, 3]},
    }


def _is_satisfying(x, n, clauses):
    """Each clause (i, j) is x_i OR x_j; i.e., NOT (x_i = 0 AND x_j = 0)."""
    bits = [(x >> (n - 1 - k)) & 1 for k in range(n)]
    return all(bits[i] == 1 or bits[j] == 1 for (i, j) in clauses)


def make_pipeline():
    def classify_route(data, prev):
        cls = classify_graph(prev["rotation"])
        r = route_classification(cls)
        r.meters["_cls"] = cls
        return r
    def reuse_route(data, prev):
        return route_classification(prev["classification"])
    return [
        Stage("CLASSIFY", "planar-sat", None, classify_route,
              lambda d, p, r: {**p, "classification": r.meters["_cls"]}),
        Stage("COUNT", "satisfying-assignments", None, reuse_route,
              lambda d, p, r: {**p, "satisfying":
                  [x for x in range(2 ** len(p["vars"]))
                   if _is_satisfying(x, len(p["vars"]), p["clauses"])]}),
    ]


def main():
    print(__doc__)
    print("=" * 74)
    pipeline = make_pipeline()
    for inst in (triangle_or(), four_cycle_or(), bowtie_or()):
        trace = RichTrace()
        final, _ = run_pipeline(pipeline, seed=inst, trace=trace)
        cls = final["classification"]
        n = len(inst["vars"])
        bf = sum(1 for x in range(2 ** n) if _is_satisfying(x, n, inst["clauses"]))
        assert len(final["satisfying"]) == bf
        print(f"\n=== {inst['name']} ===")
        print(f"  variables: {n}    clauses: {len(inst['clauses'])}")
        print(f"  tier: {cls.tier}    reasoning: {cls.reasoning}")
        print(f"  satisfying assignments: {len(final['satisfying'])} of {2 ** n}")
        examples = [bin(s)[2:].rjust(n, '0') for s in final["satisfying"][:6]]
        more = "..." if len(final["satisfying"]) > 6 else ""
        print(f"  first few:  {examples} {more}")
        print(f"  brute-force count matches: {bf}")
        print()
        print(trace.summary())


if __name__ == "__main__":
    main()
