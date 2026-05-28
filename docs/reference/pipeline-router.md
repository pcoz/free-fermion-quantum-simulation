# `pipeline-router` framework — API reference

The six primitives that make up the framework underneath
[`StructuralComputer`](structural-computer.md). Use these directly when you
want to compose custom pipelines, write domain-specific routing
classifiers, or extend the framework with new tiers.

If you're new, start with [`StructuralComputer`](structural-computer.md) —
it hides everything in this page.

---

## `pipeline_router.py` — the driver

### `Stage(name, kind, data, route_fn, runner_fn)`

One unit of a pipeline. A dataclass with:

- `name: str` — human-readable label (appears in the trace)
- `kind: str` — coarse category ("constraint", "graph", "circuit", ...)
- `data: Any` — the stage's input payload
- `route_fn: Callable[[data, prev], Route]` — inspects the data plus
  upstream output and emits a `Route`
- `runner_fn: Callable[[data, prev, route], Any]` — runs the chosen
  member and returns the output threaded forward

### `Route(member, cost, meters, tier)`

The router's per-stage decision. Dataclass:

- `member: str` — which evaluator was chosen ("ch-form", "free-fermion",
  "advised:external-solver", ...)
- `cost: float` — expected log₂(ops); `+inf` for advised
- `meters: Dict[str, Any]` — structural meters that justified the choice
- `tier: Optional[str]` — `"T0"` through `"T7"`

### `run_pipeline(stages, seed=None, trace=None, output_summary_fn=None) -> (final, trace)`

Walk an iterable of `Stage`s in order. Threads each stage's output into
the next stage's `prev` argument. Returns `(final_output, trace)`.

```python
from pipeline_router import Stage, run_pipeline
stages = [...]  # build list of Stage
final, trace = run_pipeline(stages, seed=initial_state)
```

`stages` can be a list, a generator, or any iterable. Generator-driven
mode lets you stream 1000+ stage pipelines without materialising them.

### `run_pipeline_streaming(stages, seed=None, trace=None, output_summary_fn=None)`

Generator-driven variant. Yields `(stage, route, output)` per completed
stage so the caller can react step by step.

### `Trace`

The minimal trace returned by `run_pipeline`. Methods:

- `records: List[StageRecord]` — one record per completed stage
- `stages: int` — convenience property
- `member_histogram() -> Dict[str, int]` — which members ran how often
- `tier_histogram() -> Dict[str, int]`
- `total_log_budget() -> float` — sum of per-stage `log2`-costs
- `total_ops_cost() -> float` — `log2(sum of 2^cost)` numerically stable
- `regime_changes() -> List[int]` — indices where the member changed
  from the previous stage

For richer aggregation see `RichTrace` in `trace.py`.

---

## `classify.py` — the classifier

### `classify_constraint_set(A, b, Q=None, c=None, modulus=2) -> Classification`

Classify a constraint problem:

- Linear: `A x = b (mod modulus)`
- Optional quadratic: `x^T Q_i x = c_i (mod 2)`

Returns a `Classification` with tier T0 (linear only, mod 2), T1
(quadratic, mod 2), or T7 (other moduli).

### `classify_graph(rotation, weights=None) -> Classification`

Classify a graph problem given as a rotation system (cellular embedding).
Computes genus; uses the dart-chain passage-arc formula for the
homology intersection matrix at degree-3 vertices.

Returns a `Classification` with tier T2 (genus 0) or T4 (genus ≥ 1).

### `classify_signature(values) -> Classification`

Classify a single symmetric signature given as a Hamming-weight-indexed
value sequence `[v_0, v_1, ..., v_n]`. Computes basis-aware matchgate
rank (always in `{0, 1, 2}` for symmetric signatures).

Returns T2 (arity ≤ 2) or T3 (arity ≥ 3).

### `classify(problem) -> Classification`

Dispatcher on `problem["kind"]`:
- `"constraint_set"` → `classify_constraint_set(**problem["data"])`
- `"graph"` → `classify_graph(**problem["data"])`
- `"signature"` → `classify_signature(**problem["data"])`
- anything else → T7 advised

### `Classification` dataclass

- `tier: str` — `"T0"` ... `"T7"`
- `meters: Dict[str, Any]` — structural meters
- `in_family: bool` — `True` for T0-T4 (and runnable T6); `False` for T5/T6
  pending and T7
- `reasoning: str` — human-readable why

---

## `route_constraint.py` — tier → member + cost

### `route(classification) -> Route`

Map a `Classification` to a `Route`. Cost models follow
`hybrid-dispatcher.route_block`'s `2 log2 n` polynomial surrogate; T4
includes the `4^g` genus overhead.

```python
from classify import classify_graph
from route_constraint import route

cls = classify_graph(my_rotation_system)
r = route(cls)
print(r.member, r.cost, r.tier)
```

In-family tiers (T0-T4) return finite costs and runnable members. T5/T6
pending and T7 return `+inf` cost with `advised:...` members.

---

## `trace.py` — aggregated trace

### `RichTrace`

Extends `Trace` with:

- `cost_by_member() -> Dict[str, float]` — log-budget per bucket
- `ops_by_member() -> Dict[str, float]` — log of total ops per bucket
  (numerically stable)
- `cost_by_tier()`, `ops_by_tier()` — same, keyed on tier
- `regime_changes_detailed() -> List[RegimeChange]` — prev_member,
  new_member, delta_cost per detected regime change
- `window(start, end) -> RichTrace` — sub-trace
- `summary() -> str` — multiline tabular report suitable for printing

```python
from trace import RichTrace
rt = RichTrace()
run_pipeline(stages, trace=rt)
print(rt.summary())
```

---

## `replay.py` — memoisation

### `ReplayCache`

Unbounded dict-backed cache. Statistics: `hits`, `misses`, `hit_rate()`,
`size`.

```python
from replay import ReplayCache, cached_runner
cache = ReplayCache()
```

### `cached_runner(runner_fn, cache, key_fn=default_key) -> Callable`

Wrap a Stage's `runner_fn` so identical `(data, prev)` calls return the
cached output. Pass `key_fn` to override the default JSON-SHA-1 keying
(useful when `data` has noise fields you want to ignore).

```python
def my_runner(data, prev, route):
    ...

cached = cached_runner(my_runner, cache)
stage = Stage("...", "...", my_data, my_route_fn, cached)
```

---

## `verifier.py` — small-n brute-force verification

### `brute_force_count_matchings(vertices, edges) -> int`

Exact perfect-matching count via exhaustive enumeration. Delegates to
`holant_tools.perfect_matching_count_brute_force`. Use as a reference
at small `n`.

### `enumerate_satisfying_assignments(A, b) -> List[int]`

All `n`-bit integers `x` with `A x = b (mod 2)`. Exhaustive `2^n`
enumeration; small `n` only.

### `satisfies_gf2_affine(x, A, b) -> bool`

Predicate: does the bitstring satisfy `A x = b (mod 2)`?

### `gibbs_expectation_brute(states, weight_fn, observable_fn) -> float`

Exact `<observable>` over enumerated `states` with weights from
`weight_fn` and values from `observable_fn`.

### `verify_pipeline(stages, reference_outputs, seed=None, atol=1e-10) -> (ok, report)`

Run a pipeline and compare each stage's output to a precomputed
reference (from a brute-force / textbook source). Returns `(all_ok,
multiline_report)`.

Used by every flagship/companion example to verify the routed run
matches brute force at small `n`.

---

## A complete custom pipeline (mini example)

```python
from pipeline_router import Stage, Route, run_pipeline
from classify import classify_graph
from route_constraint import route as route_cls
from trace import RichTrace
from replay import ReplayCache, cached_runner

def make_inspect_stage():
    def route_fn(data, prev):
        cls = classify_graph(prev["rotation"])
        r = route_cls(cls)
        r.meters["_cls"] = cls
        return r
    def runner_fn(data, prev, route):
        return {**prev, "tier": route.tier, "in_family": route.meters["_cls"].in_family}
    return Stage("inspect", "graph", None, route_fn, runner_fn)

def make_count_stage():
    def route_fn(data, prev):
        return prev["_classified_route"]   # carried forward from inspect
    def runner_fn(data, prev, route):
        # ... call holant-tools to do the actual count ...
        return {**prev, "matching_count": 42}
    return Stage("count", "graph", None, route_fn, runner_fn)

# Wire them up:
graph_rotation = {...}
stages = [make_inspect_stage(), make_count_stage()]
trace = RichTrace()
final, _ = run_pipeline(stages, seed={"rotation": graph_rotation}, trace=trace)
print(trace.summary())
```

## See also

- [`structural-computer.md`](structural-computer.md) — the friendly
  wrapper class.
- [`../concepts/holant-and-matchgates.md`](../concepts/holant-and-matchgates.md) —
  what the framework is implementing.
- [`../concepts/tier-hierarchy.md`](../concepts/tier-hierarchy.md) — the
  tiers `classify` emits.
- [`../cookbook/`](../cookbook/) — recipes that use these primitives.
