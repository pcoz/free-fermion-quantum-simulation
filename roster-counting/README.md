# Exact roster counting — count and certify a whole solution space

A small, runnable worked example: instead of finding *one* valid roster (what a
solver gives you), **count and interrogate the *entire* space of valid rosters —
exactly, and fast** — using [`holant-tools`](https://pypi.org/project/holant-tools/).

It answers the questions people usually assume are intractable, so never ask:

- **"Exactly how many valid rosters are there?"** — the size of your solution space.
- **"Is the roster forced, or flexible?"** — uniqueness / rigidity.
- **"How many rosters put this worker on that shift?"** — a conditional count.
- **"If this availability disappears, do we still have a roster?"** — robustness.
- **"Which single assignment is a hidden single-point-of-failure?"** — criticality.

```bash
pip install holant-tools
python roster_solution_space.py
```

## What you'll see

- a 4×4 layout has **36** valid rosters (verified two independent ways); a given
  assignment appears in 50% of them; removing one availability leaves 30; and no
  single assignment is a point of failure ("healthy");
- a contrasting 1×6 "chain" layout has exactly **one** roster — fully rigid, every
  assignment mandatory;
- the exact count scales to a **~50-digit** number of valid rosters for a 20×20
  layout, computed in about half a second — where brute force could never finish.

## How it works (and why it's fast)

The roster is modelled as a **spatial-coverage** problem: workers and shift-slots
sit on a planar layout (a grid), each worker covers one *adjacent* slot, and each
slot is covered once. A valid full roster is then a **perfect matching** of the
worker/slot adjacency graph, and *counting valid rosters = counting perfect
matchings*.

For a **planar** layout, the **FKT theorem** turns that count into a single
**Pfaffian** (a classical matrix quantity) — so it is *polynomial-time and exact*,
even when the answer is astronomically large. `holant-tools` provides the engine
(`kasteleyn_orient` builds the matrix, `holant_planar` takes the Pfaffian). Every
"what-if" query above is just the same count on a slightly modified graph, so
each is equally fast.

| term | plain meaning |
|---|---|
| perfect matching | a way to pair every worker with one adjacent slot, with none left over — i.e. one valid full roster |
| FKT / Pfaffian | the classical method that counts perfect matchings of a *planar* graph in polynomial time, without enumerating them |

## Honest scope

This is fast and exact **because the structure is planar + exact-cover** (each
position filled exactly once). That's the genuine win, and the queries above are
real, useful, and cheap there.

It is **not** a general rostering counter. As soon as availability is dense, or a
worker can cover many shifts, or capacities exceed one, counting valid rosters
becomes computing a **permanent** — #P-hard — and you should reach for a MILP / CP
solver (OR-Tools, Gurobi) instead. `holant-tools` even ships a "four-question
test" (`examples/06-...`) to tell you up front which side of that line your
problem is on.

## Files

- `roster_solution_space.py` — the worked example (well commented).
- `README.md` — this file.

## Requirements

Python ≥ 3.10 and `holant-tools` (`pip install holant-tools`). No other deps.
