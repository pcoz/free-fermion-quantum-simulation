# Build-DAG audit — flagship example for the pipeline-router

A five-stage **structural audit of a planar dependency graph**, run through
the pipeline-router. Each stage is independently routed; the output of one
threads into the input of the next; every stage's exact answer is verified
against brute force at small `n`.

```bash
python audit.py             # the 5-stage pipeline, two instances, brute-force verification
python monte_carlo.py       # the rare-tail miss MC produces on the same instance
python dartchain_stress.py  # the dart-chain vs walks-formula correction, made visible
```

## The cover story

You have a planar **compatibility graph** — tasks that can share resources,
file dependencies that can be batched, services that can be co-deployed.
You want, exactly:

| stage | question | typical off-the-shelf answer | this audit |
|---|---|---|---|
| **CLASSIFY** | Is the graph planar? Genus-g? What's its structure? | "yes/no" planarity check | a tier classification + the homology intersection via the **corrected** dart-chain formula |
| **COUNT** | How many valid total pairings does it admit? | Monte-Carlo sampling, approximate, slow | exact integer via FKT / genus-g Kasteleyn |
| **WITNESS** | Give me one valid pairing. | greedy / heuristic | exact min-weight perfect matching via Pfaffian |
| **STRESS** | If any single edge fails, how many pairings survive? Which edges are single points of failure? | exhaustive search, exponential in \|E\| | per-edge stress impact in polynomial time |
| **ITERATE** | Run 1000 stress evaluations under varying conditions. | re-run each from scratch | replay-cached: 1000 steps collapse to ≤ \|E\| unique sub-problems |

Each stage is independently inspected by the pipeline-router's classifier,
routed to its cheapest in-family member (FKT for planar, genus-g Kasteleyn
for bounded-genus, CH-form for GF(2)-affine sub-problems), and the routing
trace records exactly which decisions were made.

## What the pipeline does, end-to-end

```
            +----------+
instance -->| CLASSIFY |  tier T2 / T4, structural meters, dart-chain homology
            +----+-----+
                 |
                 v
            +----------+
            |  COUNT   |  exact integer perfect-matching count (Pfaffian)
            +----+-----+
                 |
                 v
            +----------+
            | WITNESS  |  one specific perfect matching (min-weight)
            +----+-----+
                 |
                 v
            +----------+
            |  STRESS  |  per-edge "single-point-of-failure" analysis
            +----+-----+
                 |
                 v
            +----------+
            | ITERATE  |  1000-pass with replay cache (~|E| unique calls)
            +----------+
                 |
                 v
        RichTrace summary (per-member table, per-tier table, regime changes)
```

## The two instances

| instance | vertices | edges | genus | matchings | route |
|---|---|---|---|---|---|
| **K_4 tetrahedron** | 4 | 6 | 0 | 3 | T2 — planar FKT |
| **4 × 4 toroidal grid** | 16 | 32 | 1 | 272 | T4 — genus-1 Kasteleyn (Klein arc) |

The same five stages run on both. K_4 is small enough to verify every stage
by hand or by exhaustive enumeration; the 4×4 torus exercises the genus-g
path and exhibits the cost-growth signature (the trace's `log_ops` for the
torus is ~6 log-ops higher than for K_4 — the `4^g` scaling appearing on
top of the FKT polynomial).

Sample output:

```
=== K_4 tetrahedron ===
  Stage 1 (CLASSIFY) -> tier T2: planar (genus 0) on 4 vertices
  Stage 2 (COUNT)    -> 3 perfect matchings
  Stage 3 (WITNESS)  -> [(0, 1), (2, 3)]  (cost = 2)
  Stage 4 (STRESS)   -> 0 single point(s) of failure ...
  Stage 5 (ITERATE)  -> 1000 steps, 6 unique sub-problems, hit_rate = 99.4%

=== 4 × 4 toroidal grid ===
  Stage 1 (CLASSIFY) -> tier T4: genus-1 cellular embedding on 16 vertices;
                        intersection matrix computed via the dart-chain
                        passage-arc formula
  Stage 2 (COUNT)    -> 272 perfect matchings
  ...
  Stage 5 (ITERATE)  -> 1000 steps, 32 unique sub-problems, hit_rate = 96.8%
```

Each stage's result is verified against brute-force enumeration before the
report is printed; `verify()` will assert on any mismatch.

## The originality demonstrations

Two stand-alone artefacts make the genuinely novel pieces visible:

### `monte_carlo.py` — the rare-tail miss

Each edge of K_4 fails independently with probability `p = 0.03`. The
rare-tail event we care about: **no perfect matching survives** (the event
that destroys the dependency structure entirely; what risk reporting needs).

```
  exact rare-tail probability   = 2.06e-04  (1.7 ms; 64-subset enumeration)

  MC at      1,000 samples:     0.0e+00     (100% relative error)
  MC at     10,000 samples:     4.0e-04     ( 94% relative error)
  MC at    100,000 samples:     1.7e-04     ( 18% relative error)
  MC at  1,000,000 samples:     1.9e-04     (  9% relative error, 3700 ms)
```

The exact path is bit-identical in milliseconds; MC at 10⁶ samples is still
off by ~10% and 2000× slower than exact. On a 4 × 4 torus or any larger
planar instance the gap widens dramatically — exact scales polynomially
via FKT; MC's sample need scales as 1 / p_rare.

### `dartchain_stress.py` — the dart-chain passage-arc correction

The CLASSIFY stage uses `holant_tools.dart_chain_intersection` at every
degree-3 vertex it inspects — the publicly-original correction to Cimasoni
2012's direction-aware intersection-walks formula (shipped in holant-tools
v0.4.0a5; originally observed in this project's research log, 2026-05-26).
Made visible here as a stand-alone artefact:

**Demonstration 1 — the canonical disagree-case (4 × 4 torus):**
```
  walks formula:     [[0, 0], [0, 0]]   <- DEGENERATE (rank 0; H_1 has rank 2!)
  dart-chain:        [[0, 1], [1, 0]]   <- canonical symplectic (correct)
```

**Demonstration 2 — empirical stress on random rotation systems:**
```
  K_5 random rotations (60 trials):
    walks:           22/60 non-degenerate
    dart-chain:      60/60 non-degenerate     -> walks fails on 38/60
  K_{3,3} random rotations (60 trials, all vertices degree 3):
    walks:            0/60 non-degenerate
    dart-chain:      60/60 non-degenerate     -> walks fails on 60/60
```

K_{3,3} has all-degree-3 vertices — exactly the dart-chain blindspot
domain. The walks formula fails **100% of the time** there; the dart-chain
formula is non-degenerate every time. The CLASSIFY stage routes through
the corrected primitive.

## Why this matters

This is what the diagnostic-layer thesis looks like in working code:

- a **single workflow** with multiple problem types,
- **routed per-stage** through a unified inspector,
- producing **exact answers** off-the-shelf tools cannot,
- with the **publicly-original ingredients** (dart-chain passage-arc
  formula, basis-aware matchgate rank ≤ 2) visible and exercised.

No off-the-shelf build system, scheduler, or workflow orchestrator
(Bazel, Buildkite, Airflow, Dagster, Argo, …) routes its analysis
strategy per task based on a structural classifier of what the task
actually is. The pipeline-router does. The flagship example demonstrates
this on dependency graphs; the same pattern lifts to any sequenced
typed-workflow analysis where the optimal solver depends on the
sub-problem's structure.

## Verification

`audit.py`'s `verify()` checks, for each instance, that:

- the COUNT matches `holant_tools.perfect_matching_count_brute_force`;
- every WITNESS edge is in the graph and every vertex appears exactly
  once;
- every STRESS impact matches the brute-force count with that single
  edge removed;
- the ITERATE cache size equals `|E|` (one unique sub-problem per edge)
  and the hit count equals `n_steps - |E|`.

A failed assertion in any check stops the run; the verified output is
what gets printed.
