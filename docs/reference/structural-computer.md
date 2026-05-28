# `StructuralComputer` — API reference

The friendly wrapper class in [`pipeline-router/easy.py`](../../pipeline-router/easy.py).
Import:

```python
from easy import StructuralComputer
```

Construct one and call its methods. No knowledge of tiers, Holant
problems, matchgate rank, or Pfaffians is required.

```python
sc = StructuralComputer()
```

## Methods

### `count_matchings(graph) -> int`

How many perfect matchings does the graph admit. Exact integer.

```python
sc.count_matchings([(0,1),(1,2),(2,3),(3,0)])     # 2  (the 4-cycle)
sc.count_matchings([(0,1),(0,2),(0,3),
                    (1,2),(1,3),(2,3)])           # 3  (K_4)
```

Raises `NotInFamily` if the problem is out-of-family. The exception
carries the `Classification` so you can inspect why.

### `witness(graph) -> List[Tuple[Any, Any]]`

Find one specific perfect matching, if any exists. Returns the list of
matched edges. Empty list if no matching exists.

```python
sc.witness([(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)])
# -> [(0, 1), (2, 3)]
```

Uses `holant_tools.min_weight_perfect_matching` with uniform weights
under the hood.

### `tail_probability(graph, p_fail: float) -> float`

The exact probability that **no perfect matching survives** when each
edge fails independently with probability `p_fail`. Returns a real
number in `[0, 1]`.

```python
sc.tail_probability([(0,1),(1,2),(2,3),(3,0)], p_fail=0.05)
# -> 0.009506...   (exact, ~1.7 ms)
```

**Honest scope (current implementation):** uses exact enumeration of
edge subsets, so requires `|E| <= 24`. Larger instances will need the
matching-polynomial form (Year-6 deliverable) and raise `ValueError`
today. Practical: works for any graph with up to 24 edges, which covers
small but useful examples.

### `single_points_of_failure(graph) -> List[Tuple[Any, Any]]`

Edges whose removal eliminates all perfect matchings (structural single
points of failure). Returns the list.

```python
sc.single_points_of_failure(some_graph)
# -> [(2, 5), (3, 7)]   # these edges are critical
```

For each edge, the function removes it and brute-force-counts the
remaining matchings. SPOFs are the edges that drop the count to 0.

### `compare(graph_a, graph_b, p_fail: float, metric="tail_probability") -> CompareReport`

Compare two configurations on a reliability metric. Returns a
`CompareReport` with the absolute and relative difference and a verdict
on which is more reliable.

```python
report = sc.compare(config_a, config_b, p_fail=0.05)
print(report.explain())
# "Configuration B is 90.2% more reliable (9.5063e-03 vs 9.2686e-04).
#  This distinction is provably real (exact computation),
#  not a sampling artefact."
```

`CompareReport` has fields:
- `quantity_a, quantity_b: float` — the metric values
- `absolute_difference: float` — `B - A`
- `relative_difference: float` — `(B - A) / A`
- `more_reliable: str` — `"A"`, `"B"`, or `"equal"`
- `.explain() -> str` — human-readable verdict, regulator-style

The verdict is provably exact (not statistical). Two configurations
whose tail probabilities differ by less than the MC noise floor are still
distinguishable by `compare`.

### `classify(graph) -> Classification`

What kind of structural problem is this? Returns the underlying
`Classification` object from `classify_graph` with tier, in-family flag,
and structural meters.

```python
cls = sc.classify(my_graph)
print(cls.tier)             # "T2" / "T4" / "T7" / ...
print(cls.in_family)        # True / False
print(cls.meters)           # {"genus": 0, "n_vertices": 4, ...}
```

For advanced users who want to inspect routing decisions directly.

### `explain(graph) -> str`

Human-readable summary of what the framework will do with this graph.
No math jargon.

```python
print(sc.explain([(0,1),(1,2),(2,3),(3,0)]))
# "This graph is classified as T2 (planar (genus 0) on 4 vertices).
#  The framework will route the analysis to: free-fermion.
#  Exact analyses are available: count_matchings, tail_probability,
#  witness, single_points_of_failure, audit."
```

If the graph is out-of-family, the output is an honest "WARNING:
... the framework will honestly stop and advise an external solver."

### `audit(graph, p_fail: float = 0.01) -> Dict[str, Any]`

Everything in one call. Returns a dict with tier, classification
reasoning, matching count, witness, single points of failure, and tail
probability at the given `p_fail`.

```python
audit = sc.audit(graph, p_fail=0.05)
for k, v in audit.items():
    print(f"{k}: {v}")
```

Output dict structure:
- `classification: Classification` — the raw classification
- `tier: str` — convenience copy of `classification.tier`
- `in_family: bool` — convenience copy
- `reasoning: str` — convenience copy
- (if in-family:)
  - `matching_count: int`
  - `witness: List[Tuple]`
  - `single_points_of_failure: List[Tuple]`
  - `tail_probability: float | None`
  - `p_fail_assumed: float`
- (if out-of-family:)
  - `verdict: str` — "out of family; no exact analysis available"

## Input formats

Methods accept graphs in three formats. The wrapper normalises internally:

### Edge list

```python
graph = [(0, 1), (1, 2), (2, 3), (3, 0)]
```

The simplest format. The wrapper synthesises a rotation system
(neighbour order is deterministic via `sorted(...)`); this may not
correspond to a planar embedding even on planar graphs, so the genus
inferred from the synthesised rotation system can be > 0 on graphs that
*are* planar in some other embedding. For exact planarity-dependent
computations, use a rotation system explicitly.

### Adjacency dict (set values)

```python
graph = {0: {1, 3}, 1: {0, 2}, 2: {1, 3}, 3: {0, 2}}
```

Same caveat: rotation is synthesised.

### Rotation system (dict of vertex -> ordered neighbour list)

```python
graph = {0: [1, 2, 3], 1: [0, 3, 2], 2: [0, 1, 3], 3: [0, 2, 1]}  # K_4 tetrahedron
```

The canonical format. The framework uses the rotation system directly
for cellular-embedding analysis. **Use this when planarity / genus
matters** (it does for T2 vs T4 routing).

## Exception types

### `NotInFamily(Classification)`

Raised when a method requires an exact computation on a problem the
framework classifies as out-of-family. The exception carries the
`Classification` so you can inspect tier, meters, and reasoning.

```python
try:
    sc.count_matchings(some_pathological_graph)
except NotInFamily as e:
    print(e.classification.tier)         # "T7"
    print(e.classification.reasoning)    # human-readable why
```

### `ValueError`

For inputs that are malformed or beyond the current implementation's
honest scope (e.g. `tail_probability` on graphs with `|E| > 24`).

## Performance notes

- `count_matchings`: dominated by the FKT Pfaffian for planar graphs
  (cubic in `|V|`); brute-force-based at small `n` for genus ≥ 1.
- `witness`: `holant-tools`' min-weight matching, polynomial.
- `tail_probability`: 2^|E| exact enumeration in this wrapper (capped at
  |E| ≤ 24); the matching-polynomial form is the planned next iteration.
- `single_points_of_failure`: `|E|` Pfaffian computations.
- `audit`: roughly the sum of the above; a few milliseconds for small
  graphs.

## Related

- [`pipeline-router.md`](pipeline-router.md) — the framework primitives
  underneath the wrapper, for users who need to compose custom pipelines.
- [`../getting-started.md`](../getting-started.md) — the 10-minute
  tutorial.
- [`../cookbook/reliability.md`](../cookbook/reliability.md) — how-to
  recipes that use `StructuralComputer`.
- [`../glossary.md`](../glossary.md) — vocabulary.
