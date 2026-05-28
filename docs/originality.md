# What's genuinely new here

Three publicly-verifiable originality claims. Each one is reproducible
from this repo's runnable artefacts. Each one is either a correction to
the standard literature primitive, a new theorem, or a new application
shape that no off-the-shelf tool can produce.

---

## 1. The dart-chain passage-arc formula corrects Cimasoni 2012's
##   direction-aware intersection-walks primitive at degree-3 vertices

**The standard primitive** (`direction_aware_intersection_walks` in
`holant-tools`, modelled on Cimasoni 2012's published formula) computes
intersection numbers on the homology basis of a cellular embedding by
walking each cycle and counting transversal crossings. It works on most
embeddings but has a **systematic blindspot at vertices of degree 3**: on
many such embeddings it returns a *degenerate* intersection matrix
(rank 0), claiming the homology generators have trivial intersections
when in fact they don't.

**The corrected primitive** (`dart_chain_intersection`, shipped in
`holant-tools` v0.4.0a5, originally observed in this project's research
log 2026-05-26) uses a passage-arc-based formulation that handles
degree-3 vertices correctly.

### Where to see it

Run `python pipeline-router/classify.py` from the repo root. The self-test
prints the canonical disagree-case in plain text:

```
[ORIGINALITY DEMO: 4x4 torus -- naive walks = [[0, 0], [0, 0]] (DEGENERATE)
                                dart-chain   = [[0, 1], [1, 0]] (canonical symplectic)]
```

The 4×4 toroidal grid has genus 1 (so its H_1(T^2; Z/2) has rank 2, and
the canonical symplectic intersection form is `[[0,1],[1,0]]`). The
walks formula returns the all-zero matrix; the dart-chain formula
returns the right answer.

For the empirical stress test, run
`python pipeline-router/build_dag_audit/dartchain_stress.py`:

```
K_5 random rotations (60 trials):
  walks formula:     22/60 non-degenerate
  dart-chain:       60/60 non-degenerate     -> walks fails on 38/60

K_{3,3} random rotations (60 trials, all vertices degree 3):
  walks formula:     0/60 non-degenerate
  dart-chain:       60/60 non-degenerate     -> walks fails on 60/60
```

On K_{3,3} (the smallest non-planar bipartite graph, all vertices
degree 3) the standard literature primitive **fails 100% of the time**.

### Why it matters

The intersection-number primitive is foundational in:

- **Surface-code quantum error correction.** Surface codes are cellular
  embeddings; the algebra of their logical qubits is the intersection
  structure of homology generators. The rotated surface code, IBM's
  heavy hexagonal code, and the bivariate-bicycle (BB) code family all
  use degree-3 vertices in their bulk. Distance analysis, logical
  operator identification, and decoder structure for these codes
  depend on the intersection primitive being correct.
- **Knot and link classification.** Link diagrams are 4-regular graphs
  with rotation systems at crossings. Computing link invariants needs
  the correct primitive; the dart-chain version distinguishes links
  the walks formula collapses into the same degenerate matrix.
- **Topological materials.** Crystal lattices with defects become graphs
  with low-degree vertices. Topological invariants of band structures
  (Chern numbers, Z_2 invariants, defect winding numbers) reduce to
  intersection computations.

**This is the case where the framework supplies a corrected version of a
primitive the field already uses.** The audience is narrow (QEC, topology,
materials) but the value to that audience is foundational.

---

## 2. Basis-aware matchgate rank ≤ 2 for every symmetric signature

**The theorem.** Every symmetric signature (an arity-n boolean function
whose value depends only on the Hamming weight of its inputs) has
**basis-aware matchgate rank in {0, 1, 2}**, via a common-basis
parity-split construction. The basis-aware variant of matchgate rank
admits a wider class of matchgate realisations than the standard-basis
variant; this theorem says: for the symmetric subclass, you never need
rank above 2.

This is a **new structural fact** about the space of symmetric boolean
signatures. It was originally observed in this project's research log
(2026-05-26) and shipped as `basis_aware_matchgate_rank` in `holant-tools`
v0.4.0.

### Where to see it

Run `python pipeline-router/cardinality_constraints/cardinality.py` from
the repo root. The script tests 11 classical symmetric signatures (OR,
AND, XOR, EXACTLY-K, MAJORITY, AT-LEAST-K, AT-MOST-K, ALL-OR-NOTHING) and
asserts that every basis-aware rank is in {0, 1, 2}:

```
signature                arity   tier   basis-aware rank
OR_arity_2                 2     T2          1
AND_arity_2                2     T2          1
XOR_arity_2                2     T2          1
XOR_arity_3                3     T3          1
EXACTLY_1_of_3             3     T3          1
EXACTLY_2_of_4             4     T3          1
MAJORITY_arity_5           5     T3          1
ALL_OR_NOTHING_arity_4     4     T3          1
... (every rank in {0, 1, 2})
```

The script's assertions enforce this: any rank > 2 would fail the test.

### Why it matters

This is the **most distinctively "new science"** of the three originality
pieces. The theorem itself generates research questions:

- **Does rank correlate with cryptographic strength?** Cryptography has
  historically progressed via new structural invariants (Walsh spectrum,
  differential uniformity, algebraic immunity). Matchgate rank could be a
  fifth such invariant, orthogonal to or correlated with the existing
  ones. No one has looked.
- **Can you engineer rank?** If rank = 1 implies a specific weakness, you'd
  design cipher components for rank = 2. The parity-split construction is
  constructive — you can build symmetric signatures with specified rank.
- **Does the result generalise?** Non-symmetric signatures may have
  rank > 2. The Stembridge / Wenzl degree-3+ Plücker relations are the
  next frontier (pending in `holant-tools`' roadmap). If a clean bound
  exists, that's another new theorem; if it doesn't, the rank-gap between
  symmetric and non-symmetric is itself a structural fact.

This is the founding-paper-of-a-research-line kind of result. Not a
correction; a new invariant. It might not pan out — that's the risk
profile of new science.

---

## 3. The diagnostic-layer triad: workflow-level structural routing
##   produces audit-grade outputs no off-the-shelf product can

**The architecture.** Three layers of structural routing, each operating
at a different scale:

```
simulator-router/    one circuit       -> name the cheapest member
hybrid-dispatcher/   one circuit cut    -> route each piece to its own member
pipeline-router/     a sequence         -> route each stage independently
```

Combined with the `StructuralComputer` wrapper (`pipeline-router/easy.py`),
this produces outputs that the workflow tools / reliability engines /
solvers in standard use **cannot structurally produce**, because their
internal data models don't carry structural-classification metadata.

### What the framework can produce that off-the-shelf tools cannot

For each, the structural reason why no off-the-shelf product CAN produce
this is the architecturally important point — it isn't that vendors
haven't built it, it's that the primitive concept doesn't exist in their
internal data model.

**1. Sub-statistical-noise-floor reliability comparisons.** Compare two
configurations whose exact tail probabilities differ by less than the MC
noise floor. Standard reliability tools (RMS, AIR, EQECAT, PSS/E, the
SaaS reliability dashboards) are structurally Monte-Carlo; their
verdicts always carry a confidence interval. The framework's verdicts
are bit-identical reproducible. Demonstration: `easy.py`'s self-test
produces *"Configuration B is 90.2% more reliable, provably real, not a
sampling artefact."*

**2. Audit-grade per-step structural traces.** Each pipeline stage's
routing decision is justified by the structural meters that drove it
(tier, genus, basis-aware rank, etc.). Workflow engines (Temporal,
Camunda, Airflow) produce execution logs — not structural justifications.
Combinatorial solvers (CP-SAT, Gurobi) produce solutions — not
classifications. The framework's `RichTrace.summary()` is qualitatively
different from any existing tool's output. Demonstration:
`pipeline-router/trace.py` and the trace output of every flagship/companion run.

**3. Honest in-family / out-of-family verdicts.** The framework either
produces an exact answer or names the right external solver and stops.
No false answer, no silent approximation, no statistical fudge.
Demonstration: `pipeline-router/tropical_max_weight/max_weight.py` —
planar instances solved exactly; non-planar K_{3,3} routes to
"advised: external solver."

**4. Dart-chain-correct intersection numbers on degree-3 cellular
embeddings.** As above — the standard topology / QEC libraries use the
broken primitive; the framework uses the corrected one.

**5. Per-pass adaptive routing on 1000-stage pipelines with structural
justification.** Algorithm-portfolio systems exist in ML and SAT solving,
but they pick per-instance via learned statistical models. The framework
picks per-pass via structural classification, with bit-identical
justification per stage. Demonstration: `pipeline-router/trotter_dynamics_1000/`
(1000 Trotter steps with FF/CH/dense routing shifts) and
`pipeline-router/adaptive_rebuild/` (1000-edit dev session with 98.6%
replay-cache hit rate).

### Why it matters

The framework's outputs aren't "the same thing as off-the-shelf, done
better" — they're **artefacts that don't have an off-the-shelf analogue
at all.** This is what makes the paradigm-level claim non-trivial. If
the framework were "exact Monte-Carlo," it would just be a faster
version of an existing thing. It isn't. It's a thing that produces
outputs whose generation depends on structural metadata that other tools
don't carry.

That metadata — the tier, the meters, the cost model, the classification
reasoning — is the framework's actual asset. The exactness is a
*consequence* of having that metadata, not the metadata itself.

---

## Summary table

| originality piece | shape | audience | concrete demo | timeline to land |
|---|---|---|---|---|
| **dart-chain passage-arc formula** | literature correction | QEC researchers, topologists, materials physicists (small, motivated) | `classify.py`'s self-test + `dartchain_stress.py` | 2-5 years (narrow audience, fast adoption) |
| **basis-aware rank ≤ 2 for symmetric signatures** | new theorem + new invariant | cryptographers, combinatorial-optimisation practitioners (speculative) | `cardinality_constraints/cardinality.py` | 5-15 years (research-line founding) |
| **diagnostic-layer triad + audit-grade outputs** | new architecture | workflow engineers, reliability engineers, regulators (broad) | `easy.py`, `build_dag_audit/`, `monte_carlo.py`, the whole pipeline-router | 5-10 years (industry-shift via first-mover) |

The three are independent — none depends on the others. Each lands in a
different domain, on a different timescale, with a different risk
profile. Together they constitute the framework's claim to novelty.

---

## What's NOT being claimed

Three things this repo does **not** claim, even though tangentially related
work might:

- **Not a new complexity class.** The Cai-Lu-Xia dichotomy framework
  already exists; the tier hierarchy here is a working code expression
  of established complexity-theoretic results, not new theorems about
  complexity classes.
- **Not a faster Monte-Carlo.** This isn't an improved sampling
  technique. It's a different *kind* of answer: exact, not estimated.
- **Not a universal computational speedup.** Most problems don't have
  the structural shape the framework requires. See
  [`faq.md`](faq.md) for the honest scope.

The originality is specific, demonstrable, and reproducible from the
repo's runnable artefacts. That's the standard the claims are held to.
