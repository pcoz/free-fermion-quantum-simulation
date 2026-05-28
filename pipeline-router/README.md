# pipeline-router — workflow-level routing for structural problems

The third step in the routing arc:

```
  simulator-router/     answer "which simulator is cheapest for this WHOLE CIRCUIT?"
  hybrid-dispatcher/    answer "how do I CUT this circuit and route each piece?"
  pipeline-router/      answer "how do I route a SEQUENCE of typed problems?" (this folder)
```

Where the dispatcher cuts a single circuit in two and runs each half on a
different engine, the **pipeline-router routes a chained workflow** — a
sequence of typed problems where the output of one stage threads into the
next. Each stage is independently classified, routed to its tier's
cheapest evaluator, and run; the whole pipeline can be 1, 5, 1000, or
10000 stages long without re-architecting.

```bash
python easy.py                                     # the friendly 10-line entry point
python build_dag_audit/audit.py                    # the flagship 5-stage example
python build_dag_audit/monte_carlo.py              # rare-tail miss demo
python build_dag_audit/dartchain_stress.py         # dart-chain originality demo
python adaptive_rebuild/incremental.py             # 1000-pass companion
```

---

## What's in this folder

### The friendly entry point (start here)

| file | what it is |
|---|---|
| [`easy.py`](easy.py) | **`StructuralComputer`** — the wrapper class. `sc.count_matchings(graph)`, `sc.witness(graph)`, `sc.tail_probability(graph, p_fail)`, `sc.compare(a, b, p_fail)`, `sc.audit(graph)`, `sc.explain(graph)`. No tier / Holant / matchgate vocabulary required from the caller. A full structural audit fits in ~10 lines of user-facing code. |

### The framework (six primitives, each self-tested)

| file | role |
|---|---|
| [`pipeline_router.py`](pipeline_router.py) | the driver — `Stage`, `Route`, `run_pipeline` (eager and generator-streamed); minimal `Trace` with member/tier histograms, total cost, regime-change indices |
| [`classify.py`](classify.py) | constraint / structure inspector — emits a `Classification` (tier, meters, in-family flag). **The dart-chain originality demo runs in this file's self-test on every execution** (the 4×4 torus disagree-case) |
| [`route_constraint.py`](route_constraint.py) | tier → member + cost map; mirrors hybrid-dispatcher's `2 log2 n` poly-cost convention and the genus `4^g` scaling |
| [`trace.py`](trace.py) | `RichTrace` — cost-by-member / cost-by-tier breakdowns; detailed regime changes with prev/new member + delta_cost; window slicing; structured `summary()` text |
| [`replay.py`](replay.py) | `ReplayCache` + `cached_runner` — memoisation keyed on the problem descriptor (not on activity ID), load-bearing for long-running adaptive pipelines |
| [`verifier.py`](verifier.py) | small-n brute-force harness — `brute_force_count_matchings`, `enumerate_satisfying_assignments`, `gibbs_expectation_brute`, `verify_pipeline` |

Run `python <file>.py` on any of these to see its self-test.

### Worked examples — categorised by what they demonstrate

**The flagship (5-stage audit, both originality demos live here):**

| folder | demonstrates |
|---|---|
| [`build_dag_audit/`](build_dag_audit/) | The full 5-stage pipeline (CLASSIFY → COUNT → WITNESS → STRESS → ITERATE) on two instances (K_4 tetrahedron T2 and 4×4 toroidal grid T4). Brute-force-verified at every stage. **Plus `monte_carlo.py`** (rare-tail miss demo: exact 2.06e-4 vs MC 1.9e-4 at 10⁶ samples) **and `dartchain_stress.py`** (4×4 torus disagree-case + random K_5 / K_{3,3} stress test where the standard walks formula fails 60/60 on K_{3,3}'s all-degree-3 vertices and dart-chain succeeds 60/60). |

**The 1000-pass companion (replay-cache at scale):**

| folder | demonstrates |
|---|---|
| [`adaptive_rebuild/`](adaptive_rebuild/) | An 8-hour dev session with 1000 file edits. Each edit's structural impact is classified and routed independently. 1000 edits collapse to 14 unique edit-descriptors via the replay cache (98.6% hit rate). Routed total is 2.2× cheaper in real operations than the best fixed-strategy baseline. |

**Constraint hierarchy (one folder per tier of the Holant hierarchy):**

| folder | tier | demonstrates |
|---|---|---|
| [`parity_codes/`](parity_codes/) | **T0** | Linear error-correcting codes (Hamming (7,4), 3-repetition). Codeword count, witness, minimum distance — all via the T0 / GF(2)-affine path, brute-force verified |
| [`circuit_topology_audit/`](circuit_topology_audit/) | **T1** | GF(2)-quadratic constraint sets: linear + quadratic constraint mixes, satisfying-assignment count brute-force verified |
| [`planar_3sat_relaxation/`](planar_3sat_relaxation/) | **T2** | Planar 2-SAT instances as binary Holant. Demonstrated on a triangle, 4-cycle, and bowtie; brute-force verified |
| [`cardinality_constraints/`](cardinality_constraints/) | **T3** | 11 classical symmetric signatures (OR, AND, XOR, EXACTLY-K, MAJORITY, AT-LEAST-K, AT-MOST-K, ALL-OR-NOTHING). Every one has basis-aware matchgate rank in {0, 1, 2} — exercises the publicly-original rank-≤2 insight |
| [`tournament_scheduling/`](tournament_scheduling/) | **T4** | K_{3,3} as a tournament-pairing problem; classifier emits T4 (genus 1+) via the dart-chain intersection matrix |
| [`tropical_max_weight/`](tropical_max_weight/) | **T6** | Max-weight matching via the tropical Pfaffian on planar instances; honest-stop on non-planar — demonstrates the family-boundary honest stop pin in action |

**Iterative / adaptive patterns (each demonstrates a distinct adaptive routing shape):**

| folder | demonstrates |
|---|---|
| [`trotter_dynamics_1000/`](trotter_dynamics_1000/) | 1000 Trotter steps under H(t) with Gaussian-weighted FF / Cliff / dense terms. Routing tier shifts FF → CH-form → advised at the expected time-thresholds; exactly 2 regime changes detected. **Time-dependent regime shift.** |
| [`ising_mcmc_10k/`](ising_mcmc_10k/) | 10000 Metropolis steps on a 4-spin planar Ising; replay cache hits 9936/10000 (99.4%); empirical distribution converges to exact Boltzmann within TV distance 0.02. **Replay caching at scale.** |
| [`vqe_ground_state/`](vqe_ground_state/) | 20-iteration synthetic VQE with growing ansatz; routing escalates T0 → T2 → T7 at depth thresholds 5 and 15. **Growing-problem escalation.** |
| [`branch_and_bound/`](branch_and_bound/) | Max-cut via branch-and-bound on C_5 + triangular prism; per-node tier classification with memo cache; optimal cut verified vs brute force. **Search-tree per-node routing.** |
| [`mbqc_pattern/`](mbqc_pattern/) | 20-step measurement-based QC pattern with adaptive routing based on accumulated outcome history; tier shifts as the residual pattern's structural complexity grows. **Outcome-driven adaptation.** |

---

## Why this exists

Most workflows that look "intractably combinatorial" — Monte-Carlo-rare-tail
risk reporting, build-system incremental analysis, workflow-engine audits,
1000-pass adaptive simulations — are actually exact and polynomial-time when
you spot their **structural** nature. The pipeline-router lets you route
sequenced problems through whichever exact-evaluation engine is cheapest
per stage, with a single primitive (`classify` → `route` → `run`).

Three artefacts make the originality story concrete and runnable:

1. **`classify.py`'s self-test** prints the dart-chain vs walks-formula
   disagreement on the 4×4 torus on every execution — a public
   demonstration of the corrected passage-arc formula (`holant-tools`
   v0.4.0a5).
2. **`build_dag_audit/monte_carlo.py`** demonstrates the rare-tail miss
   that Monte-Carlo produces on the same instance the pipeline yields
   exactly in milliseconds.
3. **`build_dag_audit/dartchain_stress.py`** runs the dart-chain
   correction stress test on K_5 and K_{3,3} (where K_{3,3}'s all-
   degree-3 vertices make the walks formula fail 60/60 times).

---

## Honest scope

The pipeline-router routes problems through the framework's tier
hierarchy:

- **T0 / T1** — GF(2)-affine / quadratic constraints → CH-form
- **T2 / T3 / T4** — planar / higher-arity / bounded-genus Holant → free-fermion
- **T5 / T6** — cardinality / tropical-optimisation → advised (pending native holant-tools support)
- **T7** — out-of-family (mod-p ≠ 2, continuous, unbounded-rank, permanent-class) → advised: use an external solver

The honest scope is: in-family problems get exact answers in poly-time;
out-of-family problems get a verbal advisor pointing at the right
external tool. The pipeline-router does **not** approximate, sample, or
truncate. If it can't compute exactly, it stops and says so.

---

## Quick start

```bash
pip install holant-tools numpy sympy

# the friendly entry point -- start here
python easy.py

# the framework primitives (each is self-testable)
python pipeline_router.py
python classify.py                    # the dart-chain originality demo prints here
python route_constraint.py
python trace.py
python replay.py
python verifier.py

# the flagship 5-stage audit, both originality demos
python build_dag_audit/audit.py
python build_dag_audit/monte_carlo.py
python build_dag_audit/dartchain_stress.py

# the 1000-pass companion
python adaptive_rebuild/incremental.py

# constraint-hierarchy examples (one per tier)
python parity_codes/codes.py
python circuit_topology_audit/quadratic.py
python planar_3sat_relaxation/planar_sat.py
python cardinality_constraints/cardinality.py
python tournament_scheduling/tournament.py
python tropical_max_weight/max_weight.py

# iterative / adaptive patterns
python trotter_dynamics_1000/trotter.py
python ising_mcmc_10k/mcmc.py
python vqe_ground_state/vqe.py
python branch_and_bound/bnb.py
python mbqc_pattern/mbqc.py
```

---

## Connection to the rest of the repo

The pipeline-router sits on top of `holant-tools`' primitives (FKT,
Kasteleyn, dart-chain, basis-aware matchgate rank, CH-form). It generalises
the `simulator-router/` (single-circuit routing) and `hybrid-dispatcher/`
(cut-circuit routing) up to workflow-level routing. The flagship example's
verification harness shares the `holant-tools`
`perfect_matching_count_brute_force` reference that the other examples in
this repo use for their small-n verification.

If you've already explored `simulator-router/` and `hybrid-dispatcher/`,
the pipeline-router is the natural sequel. If you haven't, start with
`easy.py` here — it's the one entry point that doesn't assume any prior
knowledge of the framework.
