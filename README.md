# Free Fermion Quantum Simulation

Runnable, self-contained examples showing that **some computations that look
hopelessly expensive are actually exact and fast — when the problem has the right
hidden structure.** Plain Python (`numpy`, `sympy`, and
[`holant-tools`](https://github.com/pcoz/holant-tools), which supplies the core
algorithms) — no quantum hardware, no GPU, no cluster.

### The idea

Many important calculations *look* intractable because the obvious way to do them
blows up exponentially: simulating a quantum system of *n* particles seems to need
**2ⁿ** numbers; counting how many valid schedules exist seems to need checking them
one at a time; getting an exact probability over a huge space of possibilities
seems to need summing over all of them. For *n* in the dozens, "exponential"
already means *more operations than there are atoms in the universe* — so people
give up and **estimate** (sampling, Monte-Carlo), **approximate**, or just **find
one answer** instead of the whole picture.

But a subset of these problems have a **regular structure** in how their parts
connect — and when they do, an algorithm *matched to that structure* returns the
**exact** answer in **polynomial** time. The exponential cost never appears. Each
folder here is a concrete, runnable instance: a problem that looks impossible, made
exact and quick on an ordinary laptop, at sizes brute force could never reach.
(For example: a *non-interacting* quantum system needs only an *n × n* table
instead of 2ⁿ amplitudes; counting valid configurations on a *planar* layout is a
single matrix computation instead of an enumeration.)

### Why this unlocks things you normally can't do

The win is not just speed — it's that the answers are **exact** (not sampled,
estimated, or truncated) at **large scale**, which enables workflows that are
otherwise out of reach:

- **Ask "exactly how many?"** — count *all* valid configurations of a system (e.g.
  every valid staff roster), not just find one, and certify uniqueness and
  robustness.
- **Resolve tiny signals** — exact correlations expose effects ~10 orders of
  magnitude below the noise floor of any sampling method, revealing structure that
  estimates simply cannot see.
- **Get a certified ground truth** — validate a real quantum processor against an
  *exact* classical reference at hundreds of qubits, impossible when your only
  reference is itself an approximation.
- **Compute exact probabilities / risk** where the standard approach can only
  sample and quote error bars.

In every case, *exactness is the enabler*: an approximate answer carries error you
cannot separate from the quantity you are trying to measure or certify.

### The honest boundary

This is **not** a general speedup for all computation. The trick works *only* when
the structure is present, and most problems don't have it. Every example states
plainly where the structure runs out and what to reach for instead (a general
solver, a quantum computer, a sampling method). The skill is recognising the
structured slice — inside it, "intractable" becomes "milliseconds."

## What's inside

| folder | what it shows | the "impossible" it does on silicon |
|---|---|---|
| [`free-fermion/`](free-fermion/) | the repo's namesake: classically simulating a free-fermion (matchgate) quantum system via its covariance matrix — a **2048-qubit** benchmark, **entanglement entropy** of a 512-qubit chain, the **Lieb–Robinson information light cone**, and **exact validation of a quantum processor** | computations a brute-force state vector (2ⁿ amplitudes) could never reach — *and* workflows only **exactness** unlocks: resolving signals ~10 orders below any sampling floor, and certifying hardware against a zero-error reference |
| [`roster-counting/`](roster-counting/) | counting and **certifying the whole solution space** of a scheduling roster (how many, unique?, robust?, what's critical?) | the **exact** number of valid rosters for a layout with a ~50-digit count, in half a second — where enumeration could never finish |

## Quick start

```bash
pip install -r requirements.txt        # holant-tools, numpy, sympy

# the free-fermion simulator + entanglement-entropy worked example
cd free-fermion
python ff_analog_twin.py
python entanglement_entropy.py

# the roster solution-space counter
cd ../roster-counting
python roster_solution_space.py
```

Each subfolder has its own README explaining the maths in plain terms, the
honest scope, and a short glossary.

## Built on holant-tools

The engine is [`holant-tools`](https://github.com/pcoz/holant-tools) — a Python
toolkit for matchgate-Holant tractability (Pfaffian / FKT evaluation, the
free-fermion simulator, exact counting, and a polynomial-time decision procedure
for *whether* a given problem lies in the tractable corner). This repo is the
worked-examples-and-applications companion to it.

## License

See [`LICENSE`](LICENSE) — modeled on the MIT License with an attribution clause.
Free to use; visible attribution to **Edward Chalk (sapientronic.ai)** is required
for publications, presentations, derivative works, and products.
