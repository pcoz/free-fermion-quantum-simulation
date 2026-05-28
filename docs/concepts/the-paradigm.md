# The paradigm — declarative structural computation

The other concept docs explain the *mathematics* this repo implements
([`holant-and-matchgates.md`](holant-and-matchgates.md)), the *operational
classification* the framework uses ([`tier-hierarchy.md`](tier-hierarchy.md)),
and the *quantitative coordinates* it emits
([`the-four-coordinates.md`](the-four-coordinates.md)). This page explains
what those amount to **at the paradigm level** — the abstract claim
about computation that the whole framework instantiates.

## The one-line version

**Declarative structural computation with exact-counting semantics,
semiring-generic, auto-routed to the cheapest correct evaluator.**

That's the paradigm. The framework is a working instance of it. The
hypothesis is that this is the right computing-paradigm shape for a
specific class of problems — structural counting, exact rare-tail
probabilities, audit-grade workflow analysis — that classical
imperative computing currently handles via 100k-line Monte-Carlo /
graph-traversal / scheduling codebases.

## The precedent: prior paradigm shifts

The shape of the claim has happened before, in different domains. Every
time, the precondition was the same: *find a domain where the imperative
"how" can be separated from the declarative "what," then ship an engine
that owns the "how."*

| paradigm | replaced | domain |
|---|---|---|
| **SQL** | nested loops over rows | relational data |
| **Regex** | hand-rolled state machines | string matching |
| **JAX / PyTorch autodiff** | hand-coded gradients | differentiable computation |
| **Prolog** | hand-coded search engines | rule-based inference |
| **Probabilistic programming** | hand-coded MCMC | Bayesian inference |

Each one collapsed roughly 100k lines of imperative ancestor code into
~10 lines of declarative replacement. Each one took 10–15 years from
"someone proves the underlying algebra works" to "the 100k → 10 collapse
is real and the old codebases atrophy."

This paradigm does the same for **structural-graph computation under any
semiring with exact-counting semantics**.

## The SQL analogy in detail

| | imperative ancestor | declarative replacement |
|---|---|---|
| **data shape** | nested loops over rows | `SELECT … FROM … WHERE …` |
| **what it does** | tells the CPU step-by-step how to traverse | declares what you want from the data |
| **what disappears** | iteration order, join algorithms, index selection, parallelisation | all of it — the optimiser owns it |
| **what stays** | the actual question | the actual question |

For structural computation:

| | imperative ancestor (the 100k lines) | declarative replacement (the 10 lines) |
|---|---|---|
| **data shape** | graph traversal + Monte-Carlo sampling + scheduling heuristics | `sc.tail_probability(graph, p_fail)` |
| **what it does** | hand-rolled exploration of the combinatorial space | declares the structural question |
| **what disappears** | the MC machine, importance sampling, the sampling-noise infrastructure, the seed reproducibility tracking, the parallel-MC scaffold | all of it — the framework's classifier + router owns it |
| **what stays** | the structural question | the structural question |

## Three concrete 100k-to-10 collapses

Each of these is a real codebase that exists today, and what it would
look like in this paradigm.

### Catastrophe / network reliability engines

**Today.** RMS / AIR / EQECAT internal engines have **millions of lines
of C++** for hazard simulation, event-set generation, exposure
aggregation, sampling-driven loss aggregation, importance sampling,
confidence-interval computation, parallel execution, and a sub-system
for managing Monte-Carlo seeds reproducibly. The same architecture
appears in power-grid reliability tools (PSS/E, PowerWorld) and telecom
outage models.

**In this paradigm (~10 lines):**

```python
hazard = pipeline.load_hazard_graph("california_seismic.geojson")
portfolio = pipeline.load_exposure("treaty_2024.parquet")
loss_dist = pipeline.exact_loss_distribution(
    hazard, portfolio, quantiles=[0.99, 0.995, 0.999]
)
print(loss_dist.tail_summary())
```

Everything inside the Monte-Carlo machinery vanishes. The 10 lines
don't shrink because the codebase is dense; they shrink because **the
Monte-Carlo machine isn't needed at all.**

### Build-system incremental-rebuild logic

**Today.** Bazel, Buck, Pants, Make, Ninja, Gradle, sbt — tens of
thousands of lines for dependency analysis, change-impact propagation,
rebuild strategy selection, cache invalidation, parallel execution.
Imperative graph traversal interleaved with hand-coded scheduling
heuristics.

**In this paradigm:**

```python
graph = pipeline.parse_build_graph("BUILD.bazel")
for edit in dev_session:
    result = pipeline.process_edit(graph, edit)
```

The `adaptive_rebuild/` example in `pipeline-router/` already does this
at small scale.

### Workflow-engine analysis layer

**Today.** Temporal's static analysis, Camunda's process-definition
validator, ServiceNow's workflow simulator — tens of thousands of lines
of imperative analysis for reachability, dead-state detection,
guard-conflict detection, stress-testing, what-if simulation.

**In this paradigm:**

```python
workflow = pipeline.parse_workflow("claims_processing.bpmn")
report = pipeline.audit(workflow,
                        questions=["reachable_terminals", "rare_failure_modes",
                                   "single_points_of_failure", "guard_conflicts"])
```

The 100k lines of analysis machinery vanish; the structured questions remain.

## The honest meta-claim

The framework as built today does **not** yet deliver the 100k → 10
collapse on any real codebase. The `build_dag_audit/` example is 312
lines, not 10. **What's been demonstrated is that the underlying
primitives exist, the routing works, the exactness holds at small n, and
the cost scaling is right.** The compression itself is the next-phase
deliverable: a thin domain DSL on top of the framework that turns the
questions into one-liners.

But this is exactly the trajectory every prior declarative paradigm
followed:

1. **Year 0:** someone proves the underlying algebra works (relational
   algebra; reverse-mode AD; the matchgate-Holant family + the Cai-Lu
   dichotomy).
2. **Year 5:** someone ships a library that implements it (early System
   R; Theano; this framework + `holant-tools`).
3. **Year 10:** someone ships the DSL that hides the library (SQL;
   PyTorch's `nn.Module`; the domain-facing DSL on top of
   `StructuralComputer`).
4. **Year 15:** the 100k → 10 collapse is real and the old codebases
   atrophy.

**The framework today is somewhere between Year 0 and Year 5.** The
`StructuralComputer` wrapper is a first taste of the Year-5 form. The
domain DSL — where the catastrophe-loss query is *literally* 10 lines,
the workflow audit is *literally* 10 lines — is the Year-10 deliverable.

## Where the analogy breaks down

The SQL analogy isn't perfect. Three honest caveats:

1. **The applicable domain is narrower than relational data.** SQL works
   on anything you can put in tables. Structural-graph exact-counting
   works on anything you can put in a Holant instance — which is a much
   narrower data model. Many real codebases don't fit this shape and
   won't shrink.

2. **The exact-counting semantics are a hard constraint.** SQL works
   approximately well enough for most queries that need approximation.
   Here, if your problem is intrinsically continuous or non-combinatorial,
   the framework doesn't help. Trying to force-fit continuous problems
   gives you the "advised: external" honest stop, not the 10-line
   version.

3. **The optimiser is younger than SQL's.** SQL query optimisers have
   had 50 years of tuning. The classifier here makes routing decisions
   on four coordinates — that's a tiny query optimiser by SQL standards.
   Mature versions of this paradigm will need much richer cost models,
   particularly for the cross-tier hybrid routing decisions.

## What the paradigm would replace

The 100k lines that go away are specifically:

- **Monte-Carlo machinery** built to estimate quantities that are exactly
  computable in a structural setting.
- **Imperative graph-traversal code** built to answer questions a Pfaffian
  could answer in one call.
- **Sampling-based analysis** built because the exact answer was assumed
  intractable.
- **Hand-rolled scheduling / dispatch** built to choose between solvers,
  replaced by the classifier.
- **Idempotency / memoisation infrastructure** built to avoid recomputation,
  replaced by replay.

What stays:

- **Data parsing** (loading the hazard model, the build graph, the
  workflow definition).
- **The actual structural question** (what's the failure probability,
  what's the rebuild order, what's the tail of the loss distribution).
- **Domain-specific result formatting** (turning the framework's output
  into a regulator-ready report, a build invalidation, a workflow audit
  trail).

The compression is real where the codebase was **mostly** Monte-Carlo
machinery and traversal heuristics, **mostly** sampling-based, **mostly**
imperative scheduling. It's not real where the codebase was actually
about parsing, formatting, distribution, or genuinely continuous
mathematics.

## The pitch in one paragraph

Today there are millions of lines of imperative C++ that simulate, sample,
and traverse structured combinatorial systems Monte-Carlo-style —
**because exact computation was assumed intractable**. The framework's
underlying claim is that for the structured-graph subset of those systems
(which is a large fraction of catastrophe modelling, network reliability,
workflow analysis, build systems, scheduling, and some scientific
computing), **exact computation is polynomial-time and the imperative
machinery isn't needed at all**. The 100k → 10 collapse is what happens
when you delete the Monte-Carlo machine and keep only the question.
**That's the paradigm.** The cookbook is just where you teach people to
write the questions.

## Strategic significance, honestly

If the rest of the framework's directions land — the
[workflow-systems integration](https://github.com/pcoz/admissibility-geometry/blob/main/proposals/workflow_systems_integration.md),
the [industry-change applications](https://github.com/pcoz/admissibility-geometry/blob/main/proposals/industry_change_applications.md),
the technical foundations in `holant-tools` — then **this** is what they
collectively are. Not just "another library." Not just "a clever way to
do reliability analysis." **A new computing paradigm**, in the sense the
field has used the word maybe a dozen times in 70 years.

The honest probability of full delivery is low — most declared "new
paradigms" don't make it past Year 5. But the underlying algebra is
right, the runnable primitives exist, and the demonstrations
([`build_dag_audit/`](../../pipeline-router/build_dag_audit/),
[`adaptive_rebuild/`](../../pipeline-router/adaptive_rebuild/),
[`easy.py`](../../pipeline-router/easy.py),
the dart-chain artefact, the MC comparison) all check out at small n.
The Year-0 to Year-5 distance is closing. The Year-5 to Year-10 distance —
which is where the domain DSL lives — is the next decade of work.

## See also

- [`holant-and-matchgates.md`](holant-and-matchgates.md) — the
  mathematical content underneath.
- [`tier-hierarchy.md`](tier-hierarchy.md) — the operational classification.
- [`the-four-coordinates.md`](the-four-coordinates.md) — the cost
  coordinates underneath the classifier.
- [`../originality.md`](../originality.md) — the publicly-original
  pieces that make the paradigm claim non-trivial.
