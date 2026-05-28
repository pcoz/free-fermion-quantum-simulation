# FAQ

The common questions, with honest answers.

## What does this repo actually do?

It provides runnable, brute-force-verified worked examples of **exact
polynomial-time computation** on combinatorial systems that the standard
toolkit assumes intractable. Specifically: anything expressible as a
matchgate-Holant problem with planar / bounded-genus / GF(2)-affine
structure. For those problems, you get bit-identical reproducible answers
in milliseconds-to-seconds, no Monte-Carlo, no truncation.

For everything else, the framework **stops honestly** and tells you to
use an external solver.

## Is this faster than Monte-Carlo?

When applicable, yes — usually by 1000× to 10⁶× — and the framework's
answer is **exact** where Monte-Carlo's is necessarily noisy. See
`pipeline-router/build_dag_audit/monte_carlo.py` for a runnable demo: a
rare-tail probability the framework computes in 1.7 ms; Monte-Carlo at
10⁶ samples is still ~9% off after 3700 ms.

But "faster" isn't the right framing. The framework produces a
*different kind of answer* (exact, bit-reproducible, regulator-defensible)
than Monte-Carlo can produce at any sample budget. See
[`originality.md`](originality.md) §3.

## What problems can the framework actually solve exactly?

The structural family: matchgate-Holant problems on planar or bounded-
genus graphs with signatures admitting basis-aware matchgate rank ≤ 2.
Concrete examples:

- counting perfect matchings on a planar graph,
- computing exact rare-tail probabilities under independent edge failure,
- finding one specific matching (the "witness" question),
- identifying structural single points of failure,
- counting satisfying assignments of GF(2)-affine constraints,
- computing tropical Pfaffians for max-weight matching on planar instances,
- simulating free-fermion / matchgate quantum circuits to thousands of qubits,
- computing exact partition functions for planar Ising models.

For each, the framework dispatches to the right exact-evaluation kernel
automatically. See [`concepts/tier-hierarchy.md`](concepts/tier-hierarchy.md).

## What problems doesn't the framework natively solve exactly (and what's being done about it)?

A problem that doesn't *look* matchgate-Holant at first glance is often
**reducible to** one that does, or **composable from** multiple in-family
ones. The framework's reduction-and-composition layer is the active
development direction. Currently-native shapes:

**In-family today (T0-T4) — exact, poly-time:**
- GF(2)-affine and GF(2)-quadratic constraints.
- Planar binary Holant.
- Higher-arity symmetric signatures (basis-aware rank ≤ 2).
- Bounded-genus Holant.

**Reducible to in-family (active work):**
- **Near-planar graphs** (a few crossings): crossing-elimination gadgets
  replace each crossing with a small planar sub-graph → reduces to T2.
- **High-degree vertices**: split into planar trees of degree-3 vertices →
  classifier-friendly.
- **Non-symmetric signatures**: basis-change machinery (the basis-aware
  rank-2 result already handles symmetric; degree-3+ Plücker is pending
  in holant-tools).
- **Cardinality / threshold constraints**: parity-split decomposition.
- **Real-valued weights**: rationalise + work in F_p, or discretise with
  provable error bounds.

**Composable from in-family (active work):**
- **Linear combinations** of in-family signatures → many non-matchgate
  signatures fall out.
- **Projections of joint distributions** from two in-family Holants →
  some permanent-class quantities.
- **Holographic basis pairs** (Valiant 2004): two matchgates with
  coordinated bases compute things neither could alone.
- **Branch-sum recombinations**: already in `hybrid-dispatcher/` for
  circuit cutting; generalises.

**Recursively decomposable into in-family (active work):**
- **Tree-decomposition / treewidth-bounded dynamic programming**: a
  graph with bounded treewidth solved exactly by recursing on its
  tree-decomposition, with each bag as an in-family Holant.
- **Planar-separator divide-and-conquer**: split a planar graph at its
  separator, solve each half recursively, combine via the boundary.
- **Tensor-network contraction order**: contract in the right order so
  every intermediate is in-family.
- **Shannon expansion**: branch on a variable, recurse on each branch;
  base case is an in-family fragment.
- **Circuit cutting with per-block recursive routing**: the hybrid-
  dispatcher's pattern lifted to N-way splits and recursive sub-cuts.

**Genuinely beyond reach (honest stop, advisor recommendation):**
- **Truly continuous-variable problems** with no discretisation: real-
  valued optimisation, PDEs, control theory.
- **mod-p arithmetic for p ≠ 2** with no reduction: different
  complexity-theoretic territory (the Cai-Lu SRP solver applies, in the
  private research repo).
- **Permanent-class counting** with no known decomposition or
  composition.

If a problem is in-family today, the classifier emits T0-T4 and you get an
exact answer. If it's currently outside-family, the classifier emits T7
and the framework advises an external solver — **without producing a
false answer**. As the reduction/composition layer matures, more T7
problems will become "T2 via reduction X" or "T2-composed via
construction Y".

## How does this compare to a quantum computer?

Quantum computing is for problems with *no* classical easy axis —
genuinely entangled, magic-rich, interacting, sign-problematic
simultaneously. Most problems aren't like that. For problems with one
clear easy axis (low entanglement → tensor networks; few non-Clifford
gates → stabilizer; non-interacting → free-fermion / this repo; sign-free
→ QMC), classical methods exist and are often faster than quantum
hardware will be for years.

The framework is for the **structural** easy-axis problems specifically.
Not a quantum replacement; a tool for problems quantum computing isn't
the right hammer for.

## Why exact answers vs sampled ones?

Three reasons:

1. **Reproducibility.** Bit-identical across runs. A regulator can audit
   the calculation. A reviewer can rerun it.
2. **Sub-statistical-noise comparisons.** Two configurations whose exact
   tail probabilities differ by less than the MC noise floor are
   structurally indistinguishable to sampling. The framework distinguishes
   them.
3. **Rare-tail accuracy.** Sampling fundamentally underestimates rare
   events at any practical sample budget. Exact computation has no rare-
   tail penalty.

See [`originality.md`](originality.md) §3 for the architectural reason
no off-the-shelf sampling tool *can* produce these properties.

## What's the dart-chain thing?

The `holant-tools` library shipped a corrected version of an
intersection-number primitive in v0.4.0a5 — fixing a systematic blindspot
in Cimasoni 2012's published formula at vertices of degree 3. This repo
uses the corrected primitive in `classify.py`. The fix matters for
QEC surface-code analysis (where degree-3 vertices are pervasive), knot
classification, and topological-materials computations.

Run `python pipeline-router/classify.py` to see the corrected vs broken
primitive disagree on the canonical 4×4 toroidal grid. Run
`python pipeline-router/build_dag_audit/dartchain_stress.py` for the
empirical stress test on K_5 and K_{3,3}. The literature primitive **fails
60/60** times on random K_{3,3} embeddings (all-degree-3 vertices); the
corrected formula **succeeds 60/60**. See [`originality.md`](originality.md) §1.

## Does this require knowing about Holant / matchgates / etc.?

No. The `StructuralComputer` wrapper in `pipeline-router/easy.py` lets
you call `sc.count_matchings(graph)`, `sc.tail_probability(graph,
p_fail)`, `sc.compare(a, b, p_fail)`, etc., with no exposure to the
underlying theory. See [`getting-started.md`](getting-started.md) for
the 10-minute tutorial.

The framework primitives (`classify`, `route`, `pipeline_router.run_pipeline`)
are there if you want to compose custom pipelines or implement new
domain DSLs on top.

## How do I use this in production?

Today: not yet. The framework is mid-development. Several pieces are
research-grade rather than production-grade:

- The tropical Klein extension (T6 tier) is **advised mode** pending
  `holant-tools` native implementation.
- The Stembridge / Wenzl degree-3+ Plücker relations (T5 tier) are
  similarly pending.
- The genus-g Kasteleyn pipeline is finicky on some random rotation
  systems (works on canonical embeddings).

For real applications, treat the framework as a **research tool**: use
the small-n verification harness everywhere, brute-force-check every
result, and be ready to flag bugs.

For the **future production roadmap**, see the speculative-roadmap
proposals in the private `admissibility-geometry` research repo:
`workflow_systems_integration.md`, `industry_change_applications.md`,
and `declarative_structural_computation.md`.

## What's the relationship to `holant-tools`?

`holant-tools` is the mathematical engine: Pfaffian / FKT evaluation,
Kasteleyn orientations, the free-fermion simulator, the dart-chain
passage-arc primitive, basis-aware matchgate rank, CH-form, the
classifier internals. Published separately on PyPI as `holant-tools`.

This repo is the **worked-examples-and-applications companion**: it
demonstrates `holant-tools`' capabilities on concrete instances with
brute-force verification, and provides the routing/dispatch layer
(`pipeline-router/`) that sits on top of the primitives.

You can use either independently:
- `holant-tools` if you want the raw primitives.
- This repo if you want runnable demonstrations, the `StructuralComputer`
  wrapper, or the pipeline-router framework.

## Where do I file bugs / contribute?

Bugs against the worked examples or the pipeline-router framework: this
repo's GitHub issues.

Bugs against the underlying mathematical primitives (Pfaffian, FKT,
dart-chain, etc.): `holant-tools` issues.

The verification harness is the contract. If `python <example>.py`
produces a failing `assert` (not a syntax error, an actual assertion
violation), that's a real bug.

## License

MIT-with-attribution. Free to use; visible attribution to **Edward Chalk
(sapientronic.ai)** required for publications, presentations, derivative
works, and products. See [`LICENSE`](../LICENSE).
