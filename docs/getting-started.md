# Getting started — your first structural audit in 10 minutes

This is the tutorial. Run the code blocks in order. By the end you'll have
computed an exact rare-tail probability that Monte-Carlo can't reliably
estimate at any sample budget, and you'll have produced a regulator-style
"Configuration B is more reliable" verdict that no off-the-shelf tool can.

Time: ~10 minutes. Prerequisites: Python 3.10+, ability to run `pip install`.

## Step 0 — Install (1 minute)

```bash
pip install holant-tools numpy sympy
git clone https://github.com/pcoz/free-fermion-quantum-simulation
cd free-fermion-quantum-simulation/pipeline-router
```

You're now in the folder where the wrapper lives.

## Step 1 — The 10-line audit (2 minutes)

Open a Python REPL or save this as `tutorial.py`:

```python
from easy import StructuralComputer

sc = StructuralComputer()

# Two network configurations as edge lists.
# Each represents a small dependency network -- think microservice topology,
# task-resource compatibility graph, or build-DAG critical path.
config_a = [(0, 1), (1, 2), (2, 3), (3, 0)]                      # a 4-cycle
config_b = [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]                  # fully-connected K_4

# Question 1: how many "valid configurations" (perfect matchings) does each admit?
print("A:", sc.count_matchings(config_a))    # -> 2
print("B:", sc.count_matchings(config_b))    # -> 3

# Question 2: give me one specific valid configuration for B.
print("B witness:", sc.witness(config_b))    # -> [(0, 1), (2, 3)]
```

Run it. You'll see the matching counts and one witness pairing. These
are **exact integers**, not estimates.

## Step 2 — Ask the question off-the-shelf tools can't answer (3 minutes)

Add this:

```python
# Question 3: if each edge fails independently with probability 0.05,
#             what is the exact probability that NO valid configuration survives?
p_a = sc.tail_probability(config_a, p_fail=0.05)
p_b = sc.tail_probability(config_b, p_fail=0.05)
print(f"A tail probability: {p_a:.4e}")        # -> ~9.51e-03
print(f"B tail probability: {p_b:.4e}")        # -> ~9.27e-04

# Question 4: which configuration is more reliable? By how much?
report = sc.compare(config_a, config_b, p_fail=0.05)
print(report.explain())
```

Output:

> *Configuration B is 90.2% more reliable (9.5063e-03 vs 9.2686e-04). This
> distinction is provably real (exact computation), not a sampling artefact.*

**That last sentence matters.** Monte-Carlo can produce comparable numbers
with 10⁶–10⁷ samples — but with sampling noise that makes the verdict
contingent on the random seed. The framework's verdict is bit-identical
reproducible across runs.

## Step 3 — Find the structural single points of failure (1 minute)

```python
# Question 5: are there edges whose removal eliminates ALL valid configurations?
print("A SPOFs:", sc.single_points_of_failure(config_a))    # -> [] (robust)
print("B SPOFs:", sc.single_points_of_failure(config_b))    # -> [] (robust)
```

Neither configuration here has structural SPOFs (any single edge can be
removed and configurations still exist). On a different topology you'd
get a list of the critical edges.

## Step 4 — The full audit in one call (1 minute)

```python
# Question 6: just give me everything at once.
audit = sc.audit(config_b, p_fail=0.05)
for k, v in audit.items():
    if k == "classification":
        continue                             # the framework's internal classification object
    print(f"  {k}: {v}")
```

Output:

```
  tier: T4
  in_family: True
  reasoning: genus-1 cellular embedding on 4 vertices; intersection matrix computed via the dart-chain passage-arc formula
  matching_count: 3
  witness: [(0, 1), (2, 3)]
  single_points_of_failure: []
  tail_probability: 0.0009268593750000002
  p_fail_assumed: 0.05
```

That `intersection matrix computed via the dart-chain passage-arc formula`
line is one of the originality artefacts — the framework uses a **corrected**
intersection-number primitive that fixes the standard formula's
systematic blindspot at degree-3 vertices. See
[`originality.md`](originality.md).

## Step 5 — Run the originality demos (3 minutes)

The three artefacts that demonstrate what makes this framework genuinely
new:

```bash
# The dart-chain primitive at work. Prints the disagree-case with the
# standard literature formula on every execution.
python classify.py

# The Monte-Carlo rare-tail miss on a small instance you can reproduce.
python build_dag_audit/monte_carlo.py

# The dart-chain vs walks-formula stress test on K_5 and K_{3,3}.
python build_dag_audit/dartchain_stress.py
```

The first prints `dart-chain = [[0, 1], [1, 0]]` (correct, canonical
symplectic) next to `walks formula = [[0, 0], [0, 0]]` (degenerate, the
standard literature primitive's wrong answer).

The second shows that 10⁶ Monte-Carlo samples give ~9% relative error
on a probability the framework computes exactly in 1.7 ms.

The third runs 60 random rotation systems on K_{3,3} (the smallest non-
planar bipartite graph, all-degree-3 vertices) and reports 0/60 success
for the standard walks formula vs 60/60 for the dart-chain corrected
formula. **100% failure** of the standard primitive on that domain.

---

## What now?

You've used the framework's friendliest entry point and seen the three
originality artefacts. From here:

- **"I want to learn what's structurally novel here."** Read [`originality.md`](originality.md).
- **"I want to understand the underlying maths."** Read [`concepts/`](concepts/).
- **"I have a specific question — count, optimise, audit."** Look in [`cookbook/`](cookbook/).
- **"I want to use the API directly, not the wrapper."** Read [`reference/`](reference/).

## A sanity check before you build on this

Every example in this repo is **brute-force verified at small `n`**. The
flagship `build_dag_audit/audit.py`'s `verify()` runs after every audit
and asserts that the exact answers match brute-force enumeration. If you
fork the framework and your verification still passes, you can trust your
results at larger `n`.

If a check fails: **that's a real bug.** File it. Don't paper over.
