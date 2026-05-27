# Exact correlated-outage risk for a planar grid

Components in a utility or telecom grid (power lines, fibre links) fail
occasionally. The dangerous case is **correlated** failure — a storm takes out
neighbouring lines *together*, and a handful of failures cascades into a
blackout. The number a risk model, an insurer, or a regulator actually needs is
the probability of a **large simultaneous outage** — and the two standard ways of
getting it both mislead exactly there:

- **"Assume failures are independent."** Analytically convenient, but it ignores
  the correlation that bunches failures together, so it **badly underestimates**
  the big-outage tail.
- **"Monte-Carlo simulate it."** A large outage is rare, so a finite sample sees
  it **zero times** and reports probability 0 — failing worst precisely in the
  tail you care about.

## The scenario: the tail your Monte-Carlo can't see

A reliability engineer at a power or telecom utility needs the probability of a
**major simultaneous outage** — for a risk model, an insurer, or a regulator. They
write a Monte-Carlo simulation of correlated failures and run 100,000 samples. The
big-outage event shows up **zero times**, so the report says **probability 0**.

But the event isn't impossible — it's *rare*. On the small grid in this example the
exact probability is about **5.7 × 10⁻⁷**: tiny, nonzero, and legally material.
Reporting 0 isn't conservative, it's wrong. And the convenient *"assume failures are
independent"* shortcut is no better — it **underestimates that tail by orders of
magnitude**, because it throws away the very correlation (a storm hitting neighbouring
lines together) that turns a few failures into a blackout.

For a **planar** grid model, this example computes that exact tail *directly* — the
same Pfaffian / partition-function machinery as the
[Ising example](../ising-phase-transition/), **not a simulation at all**. The run
prints the exact tail beside the independent-failure estimate (off by orders of
magnitude) and beside Monte-Carlo (which reports 0 right where the risk lives).

```bash
pip install numpy
python network_reliability.py
```

## What it computes (exactly)

We model correlated failures as a planar **Ising / Gibbs field** (neighbours
coupled, so one failure makes neighbouring failures more likely) and compute the
exact outage statistics: each component's failure probability, the expected
number of simultaneous failures, and the full **outage-size distribution** — in
particular the exact probability of a major outage. The example prints the exact
tail next to the "independent" estimate (off by orders of magnitude) and next to
Monte-Carlo (which reports 0 for the rare events that dominate the risk).

## Why exactness matters here

Risk pricing, regulatory compliance, and safety cases need the *exact* tail
probability of a correlated outage. An approximate method gives you a number you
can't trust precisely where it's most expensive to be wrong. Exact,
structure-exploiting computation is what makes the right number available at all.

## Honest scope

Connectivity reliability — "is the grid still one connected piece?" — is
**#P-hard even on planar graphs** (Provan 1986); planarity alone does not make it
easy. What *is* planar-tractable is the correlated-failure **statistics** above (a
planar Ising partition function), which is exactly the regime where the
independent assumption and Monte-Carlo both fail. At the small grid here the exact
statistics come from direct enumeration (the verifiable ground truth); at scale,
that planar partition function is computed by the same FKT/Pfaffian machinery used
in the [Ising example](../ising-phase-transition/).
