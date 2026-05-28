# Beating problems into matchgate-Holant shape

The framework's natively-in-family shapes (planar, bounded-genus, GF(2)-affine)
cover a lot, but many "natural" problems sit just outside. This page is
the recipe book for **reductions, compositions, and recursive
decompositions** — the techniques that bring those problems inside.

See the full API at [`../reference/`](../reference/) and the underlying
mathematics at [`../concepts/holant-and-matchgates.md`](../concepts/holant-and-matchgates.md).

---

## Recipe 1 — Exact matching count on a non-planar graph

### Problem

You have a graph that's *almost* planar, but a handful of edges make it
non-planar (a few cross-cluster network links, the "transverse"
dependencies in a workflow, etc.). You need the exact perfect-matching
count.

The framework's native T2 path (FKT planar Pfaffian) doesn't apply.
Brute-force `O(n!)` enumeration is too slow at any reasonable size.

### Solution: HybridDecomposition

Identify the small "extra-edge" set whose removal would make the graph
planar. Branch on those edges (each is either in the matching or not);
each branch is a planar sub-problem solved exactly via FKT.

```python
from structural_computing import StructuralComputer

sc = StructuralComputer()

# K_{3,3} -- the smallest non-planar bipartite graph
K33_edges = [(0, 3), (0, 4), (0, 5),
              (1, 3), (1, 4), (1, 5),
              (2, 3), (2, 4), (2, 5)]

# Branch on 1 extra edge -- K_{3,3} minus any one edge is planar
count = sc.count_matchings_hybrid(K33_edges, extra_edges=[(0, 3)])
print(f"Exact matching count: {count}")   # -> 6  (= 3! pairings)
```

### Discussion

The total cost is `2^|extras| × O(|V|^3)`. For graphs that are "mostly
planar" (a handful of extras), this is polynomial-time exact. For K_{3,3}
with 1 extra edge: 2 sub-problems, each computed in `O(|V|^3)`. Total
work: ~100 operations.

Sometimes you can use more extras to simplify each sub-problem:

```python
# 3 extras: 8 sub-problems (some skipped as invalid), but each
# sub-problem is much smaller after edge removal + vertex contraction.
count = sc.count_matchings_hybrid(K33_edges,
                                    extra_edges=[(0, 3), (1, 4), (2, 5)])
print(count)                              # -> 6  (exact, same answer)
```

### When this works

- Your graph's non-planar character is concentrated in a small edge set
  (typical for workflows, dependency graphs, planar-with-shortcuts).
- You can identify that edge set (by hand, by inspection, or by a
  planarity-test heuristic).

### When this doesn't

- The graph is densely non-planar (treewidth high, many crossings
  everywhere). Use `TreewidthBoundedDP` (v0.2 multi-bag deliverable)
  instead.
- The problem isn't a perfect-matching count. Use the appropriate
  Holant-flavoured leaf evaluator.

---

## Recipe 2 — The orchestrator: just give me an answer

### Problem

You have a graph and a question. You don't want to know about tiers,
classifiers, routers, or which reduction to apply. You just want an
exact answer or a clear honest stop.

### Solution: `Orchestrator.evaluate()`

```python
from structural_computing import Orchestrator, NoKnownReduction

orch = Orchestrator()

# Planar graph: direct dispatch via the leaf-evaluator registry.
K4 = {
    "rotation": {0: [1, 2, 3], 1: [0, 3, 2],
                  2: [0, 1, 3], 3: [0, 2, 1]},
    "vertices": [0, 1, 2, 3],
    "edges": [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)],
}
result = orch.evaluate(K4, question="matching_count")
print(result.answer)                  # -> 3 (exact)
print(result.classification.tier)     # -> "T2"
print(result.sub_evaluations)         # -> 1 (direct dispatch)
```

For a non-planar graph, supply `extra_edges` as a hint and the
orchestrator routes through `HybridDecomposition` automatically:

```python
K33 = {
    "rotation": {0: [3, 4, 5], 1: [3, 4, 5], 2: [3, 4, 5],
                  3: [0, 1, 2], 4: [0, 1, 2], 5: [0, 1, 2]},
    "vertices": [0, 1, 2, 3, 4, 5],
    "edges": [(0, 3), (0, 4), (0, 5), (1, 3), (1, 4), (1, 5),
              (2, 3), (2, 4), (2, 5)],
}
result = orch.evaluate(K33, question="matching_count",
                        hints={"extra_edges": [(0, 3)]})
print(result.answer)                              # -> 6
print(result.reductions_applied)                   # -> ["HybridDecomposition(via hints)"]
print(result.sub_evaluations)                     # -> 2
```

When nothing fits — out-of-family, no leaf evaluator, no applicable
reduction — the orchestrator stops honestly:

```python
try:
    orch.evaluate(K4, question="compute_widget_count")
except NoKnownReduction as e:
    print(e)                          # "no known reduction for T2; attempted: ..."
    print(e.classification.tier)      # "T2"
    print(e.attempted)                # list of what was tried
```

### Discussion

The orchestrator does **three things**:

1. **Classify** the problem (which tier of the Holant hierarchy?).
2. **Dispatch** to the right leaf evaluator if `(tier, question)` is in
   the registry and the problem is in-family.
3. **Reduce** if not — try the supplied or auto-detectable reductions
   to bring the problem in-family.

Provenance is recorded in every `OrchestratorResult`:
`classification`, `reductions_applied`, `sub_evaluations`,
`leaf_evaluator_used`. You can trust the answer because you can audit
how it was computed.

### Plugging in your own leaf evaluator

The default registry covers `(T2, matching_count)` and `(T4,
matching_count)` via brute-force at small `n`. For larger `n` you'd
substitute the planar Pfaffian (FKT) or genus-g Kasteleyn:

```python
def my_pfaffian_leaf(problem, question):
    if question != "matching_count":
        raise ValueError(f"can't answer {question}")
    # ... call holant_tools.exact_planar_pfaffian here ...
    return matching_count

orch.register_leaf_evaluator("T2", "matching_count", my_pfaffian_leaf)
```

### Plugging in your own reduction

```python
from structural_computing import Reduction, ReductionResult, ReductionNotApplicable

class MyCustomReduction:
    name = "MyReduction"
    def applies_to(self, problem):
        return True   # or your check
    def apply(self, problem):
        # transform problem to in-family form
        transformed = ...
        def inverse(answer):
            # lift the in-family answer back to the original problem
            return answer
        return ReductionResult(
            problem=transformed,
            cost_overhead=0.0,
            inverse=inverse,
        )

orch.register_reduction(MyCustomReduction())
```

---

## Recipe 3 — Linear combination of signatures

### Problem

You want to evaluate a Holant problem with a signature `s` that's not
directly matchgate-realisable. But `s = α·s_A + β·s_B` for some
in-family signatures `s_A`, `s_B` and known coefficients.

### Solution: `LinearCombination`

```python
from structural_computing import LinearCombination

def my_evaluator(problem):
    # Evaluate an in-family signature on the framework's graph
    return ...

comp = LinearCombination(
    name="composite signature",
    sub_problems=[
        {"kind": "signature", "data": {"values": [0, 1, 1]}},   # OR
        {"kind": "signature", "data": {"values": [0, 0, 1]}},   # AND
    ],
    coefficients=[0.7, 0.3],
)
result = comp.evaluate(my_evaluator)
```

### Discussion

The composition is exact: each sub-problem is evaluated in-family, and
the linear combination of the values gives the answer. This is the
gateway to expressing many non-matchgate signatures as combinations of
matchgate-realisable ones, and a v0.2 deliverable will auto-detect such
decompositions where they exist.

---

## Recipe 4 — Recursive decomposition via Shannon expansion

### Problem

A boolean function whose direct evaluation isn't matchgate-realisable,
but each *restriction* (substituting one variable) is.

### Solution: `ShannonExpansion`

```python
from structural_computing import ShannonExpansion

# A user-defined problem class with a .restrict(variable, value) method
class MyBooleanProblem:
    def __init__(self, ...): ...
    def restrict(self, variable, value):
        # Return a new MyBooleanProblem with `variable` substituted by `value`.
        ...

exp = ShannonExpansion(variable="x_0")
plan = exp.decompose(my_problem)
# plan is a DecompositionPlan with two children: x_0=0 branch and x_0=1 branch.
# Each child can be evaluated directly or further decomposed.

answer = plan.evaluate(my_in_family_leaf_evaluator)
```

### Discussion

For counting problems, the combiner is `sum`: count of f = count of
f|x=0 + count of f|x=1. For expected values, weighted sum. The
recursion goes down until each leaf is in-family.

---

## What's coming in v0.2

The above recipes use the **v0.1 concrete operations**. The v0.2
deliverables (sketched as `NotImplementedError` in v0.1) include:

- **`CrossingElimination`** — Cai-Lu-Xia 2009 crossover gadget; replaces
  a crossing of two edges with a small planar gadget that preserves
  matching count. Polynomial-size instead of `HybridDecomposition`'s
  exponential `2^|crossings|`.
- **`HighDegreeVertexSplit`** — replace each vertex of degree > 3 with a
  planar tree of degree-3 vertices.
- **`TreewidthBoundedDP` (multi-bag)** — full Bodlaender / Korhonen DP
  on an arbitrary tree decomposition. `O(2^O(w) × n)` for treewidth-w
  instances.
- **`HolographicBasisPair`** — Valiant 2004's basis-change machinery.
  Unlocks a large class of permanent-related quantities.
- **`PlanarSeparator`** — Lipton-Tarjan planar-separator divide-and-conquer.
- **Auto-detection** for `HybridDecomposition` — find the
  minimum-extra-edge set automatically given a non-planar graph.

The full v0.2 roadmap lives in the research repo's
`proposals/reductions_compositions_recursive_decomposition.md`.

---

## See also

- [`reliability.md`](reliability.md) — exact rare-tail probability,
  comparison, single-point-of-failure analysis (the basic recipes for
  in-family graphs).
- [`../reference/structural-computer.md`](../reference/structural-computer.md) — the wrapper API.
- [`../concepts/the-paradigm.md`](../concepts/the-paradigm.md) — why
  declarative structural computation is the right abstraction.
- [`../originality.md`](../originality.md) — the publicly-original
  primitives (dart-chain, basis-aware rank) that the reductions layer
  exploits.
