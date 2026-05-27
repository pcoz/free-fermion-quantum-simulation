# Free Fermion Quantum Simulation

Runnable, self-contained examples showing that **some computations that look
hopelessly expensive are actually exact and fast — when the problem has the right
hidden structure.** Plain Python (`numpy`, `sympy`, and
[`holant-tools`](https://github.com/pcoz/holant-tools), which supplies the core
algorithms) — no quantum hardware, no GPU, no cluster.

---

### The idea: hidden structure makes hard problems exact

Many important calculations *look* intractable because the obvious way to do them
blows up exponentially:

- simulating a quantum system of *n* particles seems to need **2ⁿ** numbers;
- counting how many valid schedules exist seems to need checking them one at a time;
- getting an exact probability over a huge space of possibilities seems to need
  summing over all of them.

For *n* in the dozens, "exponential" already means *more operations than there are
atoms in the universe* — so people give up and **estimate** (sampling,
Monte-Carlo), **approximate**, or just **find one answer** instead of the whole
picture.

But a subset of these problems have a **regular structure** in how their parts
connect — and when they do, an algorithm *matched to that structure* returns the
**exact** answer in **polynomial** time. (For example: a *non-interacting* quantum
system needs only an *n × n* table instead of 2ⁿ amplitudes; counting valid
configurations on a *planar* layout is a single matrix computation instead of an
enumeration.)

This repository contains worked examples that show this in action: each takes a
problem that looks impossible, exploits its structure, and produces an **exact**
answer on an ordinary laptop in milliseconds to seconds — at sizes brute force
could never reach.

---

### Unlocking things you can't do with standard algorithmic approaches

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

---

### Limitations

This is **not** a general speedup for all computation. The trick works *only* when
the structure is present, and most problems don't have it. Every example states
plainly where the structure runs out and what to reach for instead (a general
solver, a quantum computer, a sampling method). The skill is recognising the
structured slice — inside it, "intractable" becomes "milliseconds."

## What's inside

Seven worked examples, in four folders — [`free-fermion/`](free-fermion/) (the
namesake), [`ising-phase-transition/`](ising-phase-transition/),
[`network-reliability/`](network-reliability/), and
[`roster-counting/`](roster-counting/):

| example | what it shows (and why it matters) | the "impossible" done on silicon |
|---|---|---|
| [`ff_analog_twin.py`](free-fermion/ff_analog_twin.py) | **Simulate a quantum system** (a chain of magnetic spins) on an ordinary computer. Quantum systems are famously hard to simulate because the bookkeeping **doubles with every particle added** — this special **free-fermion** family sidesteps that. | a **2048-qubit** simulation in seconds — a state vector would need more numbers than there are atoms in the universe |
| [`entanglement_entropy.py`](free-fermion/entanglement_entropy.py) | **Measure how entangled a quantum system is.** Entanglement is the **resource behind quantum computing** and the fingerprint of exotic phases of matter — and it normally needs the **full exponential state** to compute. | the entropy of a **512-qubit** chain in ~1 s, where brute force needs ~10¹⁵⁴ numbers |
| [`lieb_robinson_lightcone.py`](free-fermion/lieb_robinson_lightcone.py) | **Watch how fast information spreads** through a quantum material. There's an emergent **"speed of light"** (the Lieb–Robinson bound) that caps how quickly a disturbance can travel — it **limits how fast quantum computers and quantum communication can ever be**. | exact to **256 qubits**, resolving signals **~10 orders of magnitude below** any sampling floor |
| [`quantum_device_benchmark.py`](free-fermion/quantum_device_benchmark.py) | **Check whether a real quantum computer actually did what it claimed**, by comparing its output to an exact answer computed classically. Validating quantum hardware needs a **trusted reference** — which normally **doesn't exist at large sizes**. | certifying a **128-qubit** processor against a zero-error reference — no 2¹²⁸ state vector exists |
| [`ising_phase_transition.py`](ising-phase-transition/ising_phase_transition.py) | **Compute exactly when a magnet abruptly loses its magnetism** as it's heated — a **phase transition**, like water boiling. The 2D Ising model is the textbook case, and it's exactly solvable *because it is secretly a **free-fermion system***. | the exact **critical temperature** and critical exponent (1/8), which simulation can only estimate with error bars |
| [`network_reliability.py`](network-reliability/network_reliability.py) | **Compute the exact risk of a large simultaneous outage** in a planar utility/telecom grid when failures are **correlated** (a storm takes out neighbouring lines together). Assuming failures are independent **badly underestimates that risk**; sampling never sees the rare, costly tail. | the **exact** probability of a major outage, where Monte-Carlo reports **zero** |
| [`roster_solution_space.py`](roster-counting/roster_solution_space.py) | **Count and audit *all* valid staff rosters at once** — how many exist, is the schedule forced, which assignment is a **single point of failure** — instead of just finding one. Schedulers return one answer; **the whole solution space is assumed too big to explore**. | the **exact** count of valid rosters — a ~**50-digit** number — in ~0.5 s, where enumeration could never finish |

## Quick start

```bash
pip install holant-tools numpy sympy   # the only dependencies

cd free-fermion                  # quantum simulation (the free-fermion examples)
python ff_analog_twin.py
python entanglement_entropy.py
python lieb_robinson_lightcone.py
python quantum_device_benchmark.py

cd ../ising-phase-transition     # the 2D Ising phase transition
python ising_phase_transition.py

cd ../network-reliability        # exact correlated-outage risk
python network_reliability.py

cd ../roster-counting            # count + certify a roster's whole solution space
python roster_solution_space.py
```

Each subfolder has its own README explaining the maths in plain terms, the
honest scope, and a short glossary.

## Where this repository sits among other quantum simulation systems

Simulating a quantum system on an ordinary (classical) computer is hard for one
basic reason: a system of *n* quantum particles is described by **2ⁿ** numbers, so
the memory needed doubles with every particle you add. By a few dozen particles
that already exceeds the number of atoms in the universe, and storing the state
outright — the "state vector" approach — becomes impossible. This is the wall that
motivated building quantum computers in the first place.

But that wall is not uniform. Over the decades, physicists have found that *many*
quantum systems of practical interest carry some special **structure** — and that
structure can be exploited to simulate them on a classical computer after all,
without ever writing down all 2ⁿ numbers. The catch is that there is **no single
method**: each known technique exploits a *different* kind of structure, works
brilliantly when that structure is present, and fails when it isn't.

Classical quantum simulation is therefore best understood as a **toolbox**, and
choosing the tool whose assumption matches your problem is what determines whether
the simulation is feasible at all:

| method | structure it exploits | exact? | where it wins / where it stops |
|---|---|---|---|
| **State vector** (brute force) | none — stores all 2ⁿ amplitudes | exact | any system, but only to ~30–50 qubits (memory is 2ⁿ) |
| **Tensor networks** (MPS / DMRG / PEPS) | *low entanglement* (area law) | approximate (truncation) | excellent for ground states and short-time dynamics of weakly-entangled systems; degrades as entanglement grows (long-time quenches, volume-law states) |
| **Stabilizer / Clifford+T** | *low "magic"* (few non-Clifford gates) | exact for Clifford; cost grows with the number of T-gates | error-correction-style and near-Clifford circuits |
| **Quantum Monte Carlo** | *sign-free* (positive path-integral weights) | stochastic (statistical error bars) | many bosonic / unfrustrated spin systems; the "sign problem" defeats frustrated and fermionic ones |
| **Free fermion / matchgate** *(this repo)* | *non-interacting* (Gaussian / quadratic) | **exact** | matchgate circuits and free-fermion Hamiltonians, to **thousands** of qubits — *at any entanglement* — but breaks the moment an interacting gate is added |

**Where this repo sits — the exact, non-interacting corner.** Two things make it
distinctive among the above:

- **It is exact** — no truncation, no sampling error, no variational gap. That is
  exactly what the examples here lean on (counting *all* solutions, resolving
  signals below the noise floor, certifying hardware against a zero-error
  reference) — workflows the approximate or stochastic methods cannot support.
- **It is indifferent to entanglement.** A free-fermion state can be *highly*
  entangled and still fit in the same small covariance matrix — precisely the
  regime where tensor networks blow up. The method doesn't care how entangled the
  state is, only that the dynamics is non-interacting.

**The unifying picture.** Each method has one "easy axis": low entanglement
(tensor networks), low magic (stabilizer), sign-free (QMC), non-interacting (free
fermions, here). They are complementary — a real study may use several. **Genuine
quantum advantage lives where *no* axis applies:** a circuit that is at once
highly entangled, magic-rich, interacting, and sign-problematic offers no
structure for any classical method to exploit — and that is exactly the regime a
quantum computer is for. This repo takes one of those axes, the free-fermion one,
to its exact, large-scale conclusion, and shows where it ends.

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
