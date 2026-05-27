# Free Fermion Quantum Simulation

**Worked examples and practical applications of classical "structure-exploiting"
computation** — built on the [`holant-tools`](https://github.com/pcoz/holant-tools)
library. Each example takes a problem that *looks* impossible or intractable and
shows it collapsing to something a laptop does in milliseconds — *because the
problem has structure a matched algorithm can exploit* — and is honest about
where that stops working.

Everything here is plain Python (`numpy`, `sympy`, `holant-tools`). No quantum
hardware, no GPU, no cluster.

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

## The one idea behind all of it

> Find the structure, and the "impossible" collapses to polynomial.

- A **free-fermion** quantum system is *non-interacting*, so its whole state fits
  in a small covariance matrix instead of 2ⁿ amplitudes — exponential → quadratic.
- A **planar** roster's valid-assignment count is a single Pfaffian (the FKT
  theorem) instead of an enumeration — #P-hard-looking → polynomial.

Both are instances of the same move, and both come with the same honest caveat:
**the speed is a property of the structure, not magic.** Remove the structure
(an interacting quantum gate; dense, capacity-bearing rostering) and you're back
to genuinely hard, where you reach for the right specialised tool instead. Each
example says exactly where that line is.

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
