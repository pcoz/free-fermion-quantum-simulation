# Free Fermion Quantum Simulation

**Exact, polynomial-time answers to questions sampling-based tools cannot
answer at all** — when the problem has the right hidden structure. Plain
Python (`numpy`, `sympy`, [`holant-tools`](https://github.com/pcoz/holant-tools)).
No quantum hardware, no GPU, no cluster.

```python
from pipeline_router.easy import StructuralComputer

sc = StructuralComputer()
config_a = [(0, 1), (1, 2), (2, 3), (3, 0)]      # a 4-cycle network
config_b = [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]  # a fully-connected K_4

report = sc.compare(config_a, config_b, p_fail=0.05)
print(report.explain())
# -> "Configuration B is 90.2% more reliable (9.5e-3 vs 9.3e-4).
#     This distinction is provably real (exact computation), not a sampling artefact."
```

That comparison — sub-statistical-noise-floor, regulator-defensible, exact —
**no off-the-shelf reliability tool can produce**, because their internal
data models are structurally Monte-Carlo. This repo demonstrates the
underlying capability across catastrophe modelling, network reliability,
workflow audit, quantum simulation, and combinatorial counting.

---

## Read these in order if you're new

| | doc | reader intent |
|---|---|---|
| 1 | **[`docs/getting-started.md`](docs/getting-started.md)** | *"teach me — 10 minutes, hands on"* |
| 2 | **[`docs/originality.md`](docs/originality.md)** | *"what's genuinely new here?"* |
| 3 | **[`docs/concepts/`](docs/concepts/)** | *"why does it work? what are the underlying ideas?"* |
| 4 | **[`docs/cookbook/`](docs/cookbook/)** | *"how do I do task X?"* |
| 5 | **[`docs/reference/`](docs/reference/)** | *"what's the API for component Y?"* |

Plus: **[`docs/glossary.md`](docs/glossary.md)** for vocabulary,
**[`docs/faq.md`](docs/faq.md)** for common questions.

---

## What this repo does, in one sentence

It provides **runnable, brute-force-verified worked examples** of exact
polynomial-time computation on combinatorial systems that the standard
toolkit assumes intractable: the free-fermion / matchgate-Holant family.
The simulators are exact (no truncation, no sampling, no statistical
error). Each example states its honest scope and what to reach for when
the structure runs out.

## What's inside, at a glance

| folder | what's in it | start with |
|---|---|---|
| [`pipeline-router/`](pipeline-router/) | the workflow-level routing framework + 13 worked examples + a friendly wrapper class | [`pipeline-router/easy.py`](pipeline-router/easy.py) |
| [`hybrid-dispatcher/`](hybrid-dispatcher/) | cut a quantum circuit, route each piece to a different exact simulator | [`hybrid-dispatcher/hybrid_dispatcher.py`](hybrid-dispatcher/hybrid_dispatcher.py) |
| [`simulator-router/`](simulator-router/) | given one circuit, name the cheapest classical simulator (or flag "genuinely quantum") | [`simulator-router/simulator_router.py`](simulator-router/simulator_router.py) |
| [`free-fermion/`](free-fermion/) | the namesake: 2048-qubit free-fermion simulation, entanglement entropy, Lieb-Robinson lightcone, quantum-device benchmark | [`free-fermion/ff_analog_twin.py`](free-fermion/ff_analog_twin.py) |
| [`ising-phase-transition/`](ising-phase-transition/) | exact 2D Ising phase transition via the Onsager free-fermion solution | [`ising-phase-transition/ising_phase_transition.py`](ising-phase-transition/ising_phase_transition.py) |
| [`network-reliability/`](network-reliability/) | exact correlated-outage probability on a planar utility/telecom grid | [`network-reliability/network_reliability.py`](network-reliability/network_reliability.py) |
| [`roster-counting/`](roster-counting/) | exact count + certification of the whole roster solution space | [`roster-counting/roster_solution_space.py`](roster-counting/roster_solution_space.py) |

Each folder has its own README (a reference card pointing into [`docs/`](docs/)).

## Honest scope

This is **not** a general computational speedup. The framework's exact
polynomial-time answers apply to combinatorial problems with the right
structural shape: planar / bounded-genus / matchgate-family / GF(2)-affine.
**Most problems don't have this shape.** Every example states plainly
where the structure runs out and what to reach for instead (a general
solver, a quantum computer, a sampling method). See
[`docs/faq.md`](docs/faq.md) for what this *isn't* applicable to.

## Built on holant-tools

The mathematical engine is
[`holant-tools`](https://github.com/pcoz/holant-tools) — Python primitives
for matchgate-Holant tractability (Pfaffian / FKT, free-fermion simulator,
exact counting, basis-aware matchgate rank, the dart-chain passage-arc
formula, polynomial-time decision procedures). This repo is the
worked-examples-and-applications companion.

## License

See [`LICENSE`](LICENSE) — modelled on the MIT License with an attribution
clause. Free to use; visible attribution to **Edward Chalk
(sapientronic.ai)** is required for publications, presentations,
derivative works, and products.
