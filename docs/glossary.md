# Glossary

The vocabulary used throughout this repo. Terms link to their primary
[`concepts/`](concepts/) explanation where one exists.

## Core terms

**Perfect matching.** A pairing of the vertices of a graph in which
**every vertex is paired with exactly one other vertex via an edge** —
no vertex is left out, no vertex is paired twice. (Think: assigning every
person at a dance to a partner; everyone has exactly one, only adjacent
people can pair.) For K_4 (4 vertices, all connected) there are exactly
3 perfect matchings: `{A-B, C-D}`, `{A-C, B-D}`, `{A-D, B-C}`.

**Weight of a matching.** If every edge of the graph has a weight (a
number), the *weight of a perfect matching* is the **product** of the
weights of the edges that make up that matching. If `A-B` weighs 3 and
`C-D` weighs 5, the matching `{A-B, C-D}` has weight `3 × 5 = 15`.

**Sum of weights of perfect matchings (the matching sum).** Add up the
weight of *every* perfect matching of the graph. For K_4 with edge
weights `w(A-B), w(A-C), w(A-D), w(B-C), w(B-D), w(C-D)`:

```
matching sum = w(A-B)·w(C-D)  +  w(A-C)·w(B-D)  +  w(A-D)·w(B-C)
```

**This single number encodes the answer to a huge family of practical
questions.** Different choices of edge weights make the matching sum
compute different things:

- *weights = 1 everywhere* → **count** of perfect matchings (how many
  task-resource assignments? how many schedules? how many crystal
  structures?);
- *weights = success probabilities* → **joint probability** of valid
  pairings under independent edge events;
- *weights = Boltzmann factors* → **partition function** of a physical
  system (this is how Kasteleyn 1961 made the 2D Ising model exactly
  solvable);
- *weights = intactness indicators* → **reliability quantities** (rare-tail
  probability of total failure under correlated outage);
- *ratios of two matching sums* → **expected values** under any of the
  above.

The matching sum is the **central computational primitive** the framework
is built around — every exact answer produced by `count_matchings`,
`tail_probability`, `compare`, `audit` ultimately reduces to a matching
sum on a derived graph. The FKT theorem (1961) is what makes computing
it polynomial-time: a single `n × n` Pfaffian instead of enumerating all
`(n-1)!!` matchings.

**Matchgate.** A computational object that participates in matching-sum
calculations. Specifically: a small graph (or "gadget") whose
matching-sum contribution, when wired into a larger graph, computes a
chosen mathematical function of its external inputs. By composing
matchgates you build up large combinatorial calculations whose total
matching sum is the answer you want. The matchgate-Holant family
generalises this to a wide class of structured combinatorial problems.
**The crucial property:** matching sums on planar (and bounded-genus)
graphs of matchgates can be computed in polynomial time via Pfaffians
(the FKT theorem), so wiring problems as matchgates makes them
poly-time exact. See [`concepts/holant-and-matchgates.md`](concepts/holant-and-matchgates.md).

**Holant problem.** A graph with a *signature* (constraint function) at
each vertex; the problem's "value" is the sum, over all edge-assignments
(each edge gets a truth value), of the product of signature evaluations
at each vertex. A direct generalisation of the matching sum: the
matching sum is a Holant problem where each vertex's signature is "I
must have exactly one of my incident edges chosen." Other signatures
encode other combinatorial constraints (XOR, OR, AT-MOST-K, EXACTLY-K,
arbitrary cardinality, ...). Counting problems on graphs are expressible
as Holant problems by choosing the right signatures. See
[`concepts/holant-and-matchgates.md`](concepts/holant-and-matchgates.md).

**Signature.** A constraint function. An *arity-n* signature has n
boolean inputs and produces a value (boolean, integer, real, or in
some other semiring). Examples: `OR` (arity 2, returns 1 unless both
inputs are 0), `EXACTLY-K` (arity n, returns 1 iff exactly k inputs
are 1).

**Symmetric signature.** A signature whose value depends only on the
*Hamming weight* of its inputs, not on which specific inputs are 1. The
arity-n symmetric signatures are exactly the sequences `[v_0, v_1, ...,
v_n]` of n+1 values indexed by Hamming weight.

**Pfaffian.** A polynomial in the entries of a skew-symmetric matrix
whose square equals the determinant. For a Kasteleyn-orientated planar
graph, the absolute value of the Pfaffian counts the perfect matchings
of the graph exactly. This is the computational kernel underneath most
of the framework's exact answers.

**Kasteleyn orientation.** A specific edge orientation of a planar graph
that makes the absolute value of the Pfaffian equal to the perfect-
matching count. The FKT theorem (Fisher, Kasteleyn, Temperley, 1961)
proves Kasteleyn orientations exist on planar graphs and gives a
polynomial-time algorithm to construct one.

**FKT theorem.** The Fisher-Kasteleyn-Temperley theorem: for any planar
graph, the perfect-matching count can be computed in polynomial time via
the Pfaffian of a Kasteleyn-orientated adjacency matrix.

**Genus.** A topological invariant of a closed surface. Genus 0 is the
sphere (planar graphs embed here). Genus 1 is the torus (one "hole").
Genus g is g holes. Bounded-genus graphs have Holant computable in
polynomial time with a factor of `4^g` cost overhead via the Galluccio-
Loebl formula.

**Cellular embedding.** A drawing of a graph on a surface where every
face is a topological disk. A planar graph has cellular embeddings on
the sphere; a non-planar graph has cellular embeddings on higher-genus
surfaces. Specified by a *rotation system*.

**Rotation system.** A combinatorial specification of a cellular
embedding: for each vertex, the cyclic order in which its neighbours
appear around it. Two different rotation systems on the same graph give
genuinely different embeddings (potentially on different-genus surfaces).

## The framework's vocabulary

**Tier.** The framework's classification of a problem's structural type.
Tiers T0 through T7 correspond to: GF(2)-affine, GF(2)-quadratic, planar
binary Holant, higher-arity symmetric, bounded-genus, cardinality
(advised), tropical optimisation (advised), out-of-family. See
[`concepts/tier-hierarchy.md`](concepts/tier-hierarchy.md).

**Member.** A concrete in-family evaluator the framework can dispatch to.
Examples: `ch-form` (CH-form Clifford simulator), `free-fermion`
(Pfaffian-based matchgate evaluator), `tropical-pfaffian` (planar tropical
Pfaffian), `advised:external-solver` (the framework's honest-stop label).

**Pipeline-router.** The framework's workflow-level routing layer. A
pipeline is a sequence of typed problems (`Stage`s); the router classifies
each, picks the cheapest in-family member, runs it, and threads the output
into the next stage. See [`reference/pipeline-router.md`](reference/pipeline-router.md).

**Stage.** One unit of a pipeline-router pipeline. Each Stage has a
`data` payload, a `route_fn` (which returns a `Route` after inspecting the
data), and a `runner_fn` (which produces the stage's output by running
the chosen member on the data).

**Route.** The router's per-stage decision: which member to use, what the
expected cost is (in log₂ ops), what structural meters justified the
choice, and the tier label.

**RichTrace.** The framework's aggregated routing trace. Records each
stage's route, gives cost-by-member / cost-by-tier breakdowns, detects
regime changes (where the dominant member shifted mid-pipeline), supports
window slicing for diagnosis at scale.

**ReplayCache.** The framework's memoisation layer. Keyed by the problem
descriptor (not by activity ID), so structurally-identical sub-problems
in different parts of a pipeline share a cache entry. Load-bearing for
1000+ stage adaptive pipelines.

**Classification.** What the classifier emits: a tier label, structural
meters (genus, vertex count, basis-aware rank, etc.), an `in_family` flag,
and a human-readable reasoning string.

**Basis-aware matchgate rank.** A refined notion of matchgate-rank that
considers all possible bases (not just the standard basis). For symmetric
signatures, basis-aware rank is always in {0, 1, 2} — see
[`originality.md`](originality.md).

**Dart-chain passage-arc formula.** The corrected primitive for computing
intersection numbers on the homology basis of a cellular embedding.
Replaces Cimasoni 2012's direction-aware-intersection-walks formula,
which has a systematic blindspot at degree-3 vertices. See
[`originality.md`](originality.md).

**Direction-aware intersection walks.** The standard literature primitive
for computing intersection numbers (Cimasoni 2012). Has the
degree-3-vertex blindspot the dart-chain formula corrects.

**CH-form.** The affine-quadratic representation of stabilizer (Clifford-
circuit) states. An `O(n·k)` data structure (where `k` is the number of
free bits) that admits polynomial-time evaluation of all Clifford gates,
including `H` on already-entangled qubits. See `hybrid-dispatcher/ch_form.py`
for the working implementation.

## Probability / sampling terms (for the rare-tail demos)

**Rare-tail probability.** The probability of an event in the
low-probability tail of a distribution. For reliability analyses: the
probability that a system fails catastrophically. Sampling-based tools
struggle here because the relevant events are by definition under-sampled.

**Total-variation distance.** A way to measure how different two
probability distributions are. The MCMC convergence test in
`pipeline-router/ising_mcmc_10k/` reports TV distance to the exact
Boltzmann distribution.

**Monte-Carlo (MC).** Sampling-based estimation. Standard for problems
deemed intractable to compute exactly. Has structural noise floors that
the framework's exact methods do not.

## Semantics

**Semiring.** A mathematical structure with addition and multiplication
(roughly: integers with +,× ; reals with +,× ; tropical with min,+).
Holant problems can be defined over any semiring; the framework supports
standard (counting), tropical (optimisation), and modular (for some
applications).

**Tropical semiring.** The (min, +) algebra: instead of summing
contributions, take the minimum; instead of multiplying weights, add
them. The tropical Pfaffian computes the *minimum-weight* perfect
matching in polynomial time on planar graphs.

## Things you'll see in code but might not recognise

**`(graph, edges, rotation)` triple.** The framework's canonical graph
representation: a vertex list, an edge list, and a rotation system
(cellular embedding). Functions like `classify_graph` accept any of
these formats.

**Kasteleyn matrix.** The matrix produced by `kasteleyn_orient` — a
skew-symmetric matrix whose Pfaffian counts perfect matchings exactly.

**Pipeline trace.** The accumulated record of routing decisions across
all stages of a pipeline run. Inspected via `RichTrace.summary()`,
`.regime_changes_detailed()`, `.cost_by_member()`, etc.
