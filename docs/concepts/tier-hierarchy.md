# The tier hierarchy — T0 through T7

The framework's classifier emits a **tier label** for every problem it
inspects. The tier tells you which exact-evaluation member (if any) can
solve the problem in polynomial time, and what to expect about its cost.

This is the operational form of the [Cai-Lu dichotomy](holant-and-matchgates.md):
T0–T4 are *in-family* (matchgate-Holant tractable, poly-time exact); T5–T6
are *pending* (in-family in principle, awaiting native `holant-tools`
support); T7 is *out-of-family* (the honest-stop tier).

## The hierarchy at a glance

| tier | what's in it | member | cost shape | example |
|---|---|---|---|---|
| **T0** | GF(2)-affine constraints: `A x = b (mod 2)` | `ch-form` | `O(n·k)` | linear codes, parity-check problems |
| **T1** | GF(2)-quadratic constraints: linear + `x^T Q x = c (mod 2)` | `ch-form` + post-selecting Z | `O(n·k)` × (small) | quadratic constraint sets, XOR-linearised SAT |
| **T2** | Planar binary Holant (arity-2 signatures, planar graph) | `free-fermion` (FKT Pfaffian) | `O(n^3)` | planar 2-SAT, planar perfect-matching count, build-DAG audit |
| **T3** | Higher-arity symmetric signatures (arity ≥ 3) | `free-fermion` + basis-aware rank ≤ 2 parity-split | `O(n^3)` (with small constants) | cardinality constraints, EXACTLY-K, MAJORITY |
| **T4** | Bounded-genus Holant (genus > 0, finite) | `free-fermion` + genus-g Kasteleyn | `O(4^g · n^3)` | tournament scheduling, non-planar dependency graphs |
| **T5** | Cardinality / threshold / modular-counting (advised, pending) | *advised* | n/a | "exactly k of n" with non-standard structure |
| **T6** | Weighted optimisation / tropical Holant | `tropical-pfaffian` (planar) or *advised* (non-planar) | `O(n^3)` planar; advised otherwise | max-weight matching, assignment problem |
| **T7** | Out-of-family: mod-p (p ≠ 2), real-valued, unbounded matchgate-rank, permanent-class | *advised: external solver* | +∞ in framework | full SAT, MILP, continuous optimisation, mod-p ≠ 2 arithmetic |

## What each tier means in practice

### T0 — GF(2)-affine

Problems of the shape "find / count assignments `x ∈ {0, 1}^n` satisfying
`A x = b (mod 2)` for some matrix `A` and vector `b`." Solvable via the
CH-form (stabilizer-circuit) representation in `O(n·k)` time where `k` is
the dimension of the affine variety.

**Examples:** linear error-correcting codes (count codewords, find one
witness, compute minimum Hamming distance), simple parity check problems,
GF(2)-linear feasibility.

**Demo:** `pipeline-router/parity_codes/codes.py` — Hamming (7,4) and
3-repetition codes audited end-to-end.

### T1 — GF(2)-quadratic

T0 plus quadratic constraints `x^T Q x = c (mod 2)`. The CH-form
representation extends with a quadratic phase + post-selecting Z
measurements; still poly-time.

**Examples:** quadratic constraint sets in cryptography (Walsh-coefficient
analysis), boolean-circuit-equivalence checks, certain XOR-quadratic SAT
encodings.

**Demo:** `pipeline-router/circuit_topology_audit/quadratic.py`.

### T2 — Planar binary Holant

The classical FKT regime. Any graph with arity-2 signatures, planar
embedding. The framework dispatches to `kasteleyn_orient` +
`exact_planar_pfaffian` for the Pfaffian.

**Examples:** counting perfect matchings on planar graphs, planar 2-SAT,
weighted Ising / Gibbs partition function on planar graphical models,
build-DAG analysis on planar dependency graphs.

**Demo:** `pipeline-router/build_dag_audit/audit.py` (K_4 instance),
`pipeline-router/planar_3sat_relaxation/planar_sat.py`.

### T3 — Higher-arity symmetric signatures

Vertices of degree ≥ 3 with symmetric signatures (value depends only on
Hamming weight). The publicly-original **basis-aware matchgate rank ≤ 2**
result (see [`../originality.md`](../originality.md)) guarantees every
symmetric signature is tractable via a parity-split construction.

**Examples:** cardinality constraints (`EXACTLY-K`, `AT-LEAST-K`,
`AT-MOST-K`), `MAJORITY` signatures, threshold functions.

**Demo:** `pipeline-router/cardinality_constraints/cardinality.py` — 11
classical symmetric signatures, every basis-aware rank in {0, 1, 2}.

### T4 — Bounded-genus Holant

The graph isn't planar but has bounded genus. The framework dispatches to
`kasteleyn_orient_genus_g` + `holant_genus_g`, with the Galluccio-Loebl
`4^g` cost factor.

**Examples:** K_{3,3} (genus 1, all degree-3), tournament schedules on
non-planar compatibility graphs, surface-code QEC analysis.

**Demo:** `pipeline-router/tournament_scheduling/tournament.py` — K_{3,3}
classified T4 via the dart-chain intersection matrix.

### T5 — Cardinality / threshold (advised, pending)

The Stembridge / Wenzl degree-3+ Plücker relations — a research direction
for `holant-tools`' future. Until they ship, cardinality / threshold
constraints in non-symmetric form route to advised mode. For symmetric
cardinality constraints, use T3 instead.

### T6 — Weighted optimisation / tropical Holant

Max-weight or min-weight optimisation over a Holant structure. Planar
instances run via `planar_tropical_pfaffian` exactly. Non-planar instances
honest-stop with `advised:tropical-klein` (the native tropical Klein
extension is a `holant-tools` roadmap item).

**Examples:** max-weight perfect matching, min-cost assignment problem,
shortest path on a structured graph.

**Demo:** `pipeline-router/tropical_max_weight/max_weight.py` — planar
instances solved exactly; non-planar K_{3,3} honest-stops.

### T7 — Out-of-family (advised forever)

Problems whose structural shape places them outside the matchgate-Holant
family for fundamental reasons:

- **mod-p arithmetic with p ≠ 2.** Different algebraic territory (the
  Cai-Lu SRP solver applies; lives in admissibility-geometry, the private
  research repo).
- **Continuous / real-valued variables.** No discrete combinatorial
  structure to exploit.
- **Unbounded matchgate rank.** Non-symmetric signatures with high rank.
- **Permanent-class counting** beyond matchgate-realisable.
- **Genuine non-planar with high genus.** `4^g` cost makes it intractable
  for large g.

The framework's behaviour: report T7 with a clear reasoning, suggest an
external solver (CP-SAT for SAT-like; Gurobi/CPLEX for MILP-like;
`scipy.optimize` for continuous; etc.). No false answer.

## Routing across the hierarchy

A pipeline can route different stages to different tiers. The classic
example is `pipeline-router/trotter_dynamics_1000/`:

- Stages 1–333: H(t) dominated by `H_FF` → routes to T2 free-fermion.
- Stages 334–666: H(t) dominated by `H_Cliff` → routes to T0 ch-form.
- Stages 667–1000: H(t) dominated by `H_dense` → routes to T7 advised.

The pipeline's `RichTrace` records the regime changes exactly. **Standard
algorithms can't do this** — they're fixed to one solver. The framework
adapts per-stage.

## Cost models

Each in-family tier has an explicit cost model used by `route_constraint`:

```
T0, T1     cost = 2 log2(n + 1)                            (CH-form O(n·k))
T2         cost = 2 log2(2·n_vertices)                     (planar Pfaffian)
T3         cost = 2 log2(2·arity)                          (parity-split)
T4         cost = genus · log2(4) + 2 log2(2·n_vertices)   (4^g overhead)
T5, T6     cost = +∞  unless planar tropical               (honest stop)
T7         cost = +∞                                       (honest stop)
```

These are the same `2 log2 n` poly surrogate that `hybrid-dispatcher`'s
`route_block` uses for circuit routing.

## Where the hierarchy comes from

The dichotomy boundary between T0–T4 and T7 is exactly the **Cai-Lu
dichotomy boundary** (see [`holant-and-matchgates.md`](holant-and-matchgates.md)).
The intermediate T5 / T6 tiers are *in-principle in-family*
(matchgate-realisable in the right basis with the right primitives) but
not yet implemented in `holant-tools` — they sit in advised mode
pending native support.

The tier labels are the framework's contract with the user: **T0–T4
means exact answer in poly-time; T5–T6 means advised pending; T7 means
honest stop, no false answer ever.**

## See also

- [`holant-and-matchgates.md`](holant-and-matchgates.md) — the
  mathematical primitive underneath the hierarchy.
- [`the-four-coordinates.md`](the-four-coordinates.md) — finer-grained
  classification beyond tier.
- [`the-paradigm.md`](the-paradigm.md) — the abstract claim the hierarchy
  serves.
- [`../reference/pipeline-router.md`](../reference/pipeline-router.md) —
  the API for inspecting and routing on the hierarchy.
