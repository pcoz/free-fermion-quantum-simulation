# Free-fermion analog twin

A small, runnable demonstration that **one special family of quantum systems can
be simulated on an ordinary computer astonishingly fast** — thousands of qubits
in seconds, where the naive method would need more memory than there are atoms in
the universe — together with an honest explanation of *why*, and of what this
does (and doesn't) say about quantum computers.

It uses the free-fermion simulator from [`holant-tools`](https://pypi.org/project/holant-tools/)
as its engine.

## The 30-second version

- Simulating a quantum system on a normal computer is *usually* impossible: a
  system of *n* quantum bits ("qubits") needs **2ⁿ** numbers to write down — at
  100 qubits that already exceeds all the storage on Earth.
- But a special, **non-interacting** family of quantum systems — physicists call
  them **free fermions**, and the equivalent quantum gates are called
  **matchgates** — can be described by a small **table of size ~2n × 2n** instead
  of 2ⁿ numbers. The cost then grows like **n²**, not **2ⁿ**.
- This demo simulates such a system *both* ways and races them. The compact
  method does **2048 qubits in ~7.5 seconds**; the brute-force method is hopeless
  past ~24 qubits.
- **The honest twist:** this is *not* "beating quantum computers." Free-fermion
  systems are exactly the **easy corner** of quantum computing — the part with no
  quantum advantage. The last section explains where the real quantum/classical
  gap actually lives.

## Run it

```bash
pip install holant-tools numpy sympy
python ff_analog_twin.py        # the benchmark: free-fermion vs brute force
python entanglement_entropy.py  # worked example: a normally-impossible computation
```

`ff_analog_twin.py` shows three things: (1) the fast method agrees with the
brute-force method to ~15 decimal places; (2) a timing table where brute force
hits a memory wall while the fast method sails; (3) the fast method pushed into
the thousands of qubits. `entanglement_entropy.py` is the worked example below.

## What's actually going on

**The system.** We evolve a *transverse-field Ising chain* — a standard,
much-studied physics model of *n* spins in a row, each coupled to its neighbours
and tilted by an external field — and track its average magnetisation over time.

**Why brute force is hopeless.** The honest, general way to simulate a quantum
system is to store its *state vector*: 2ⁿ complex numbers. Every qubit you add
**doubles** the memory. At n=64 that is ~10¹⁹ numbers; at n=2048, ~10⁶¹⁷ — numbers
with hundreds of digits, vastly more than the ~10⁸⁰ atoms in the universe.

**Why this system is special.** The Ising chain is a **free-fermion** system:
after a standard change of variables (the *Jordan–Wigner transformation*), its
dynamics becomes *non-interacting*. A non-interacting quantum state is completely
captured by its pairwise correlations — a single **2n × 2n table called the
covariance matrix**. Each step of the evolution is a small, *local* update of
that table, so the whole simulation costs about **n² per step instead of 2ⁿ**.

**The "analog twin" framing.** A real physical free-fermion device would compute
the answer simply by *being* that physics — an analog computer. This code is its
**digital twin**: it runs the exact same math (`holant_tools.FreeFermionCircuit`)
on a normal CPU. Reading an answer off the covariance matrix amounts to
evaluating a **Pfaffian** (a classical matrix quantity), the same mathematical
kernel that makes a whole family of counting problems tractable.

## Jargon, briefly

| term | plain meaning |
|---|---|
| **qubit** | a quantum bit; *n* of them need 2ⁿ numbers to describe in general |
| **state vector** | that full list of 2ⁿ numbers — the brute-force representation |
| **free fermion / matchgate** | the special *non-interacting* family this trick applies to; the classically-easy corner of quantum computing |
| **covariance matrix** | the compact 2n × 2n table that fully describes a free-fermion state |
| **Jordan–Wigner transformation** | the change of variables that turns the spin chain into free fermions |
| **Pfaffian / FKT** | the classical matrix computation used to read answers off the covariance matrix (FKT = the Fisher–Kasteleyn–Temperley method) |
| **BQP** | the class of problems a full quantum computer can solve efficiently |

## What the demo measures

- **Correctness** — at small sizes (n = 4, 6) the fast covariance method matches a
  full state-vector simulation to ~1e-15. They are computing the same thing.
- **The gain (`FreeFermionCircuit` engine)** — the covariance method's cost grows
  ~n² per step; the state vector grows 2ⁿ and walls out around n = 24 on a laptop
  (n = 64 would need 256 EB of memory). The twin handles n = 64 in seconds.
- **The gain at scale (NumPy fast-path)** — the same algorithm in a float64 engine
  drops the constant factor ~100–450× and reaches **n = 1024 in ~0.9 s** and
  **n = 2048 in ~7.5 s**, where a state vector would need ~10⁶¹⁷ amplitudes.

## Worked example: entanglement entropy of a 512-qubit chain

`entanglement_entropy.py` uses this repo's own engine to compute a quantity that
is *normally impossible* — the **entanglement entropy** of a large quantum chain
(a central measure of how quantum-correlated two halves of a system are). It:

- checks the free-fermion result against the brute-force answer at small sizes
  (they agree to ~15 decimal places);
- computes the **half-chain entanglement entropy of a 512-qubit chain in ~1 s**,
  where the brute-force method would need ~10¹⁵⁴ numbers (already at 256 qubits
  it exceeds the number of atoms in the universe);
- watches **entanglement grow after a quench** — the hallmark of quantum dynamics
  — at a system size no exact simulator could reach.

It works because the entanglement entropy of a free-fermion state is read off the
covariance matrix's eigenvalues (Vidal–Latorre–Rico–Kitaev / Peschel) — cost
O(n³), not 2ⁿ. This is "the impossible running on silicon," demonstrated with the
repo itself.

## Honest scope — what the gains do and don't mean

- The speedup is **exponential over naive state-vector simulation**, *purely
  because the dynamics is free-fermion structured* (the matchgate-tractable
  corner). It is **not** a speedup of classical computation in general.
- A real **analog** free-fermion device would *match* this digital twin
  asymptotically, not beat it. Interacting (non-matchgate) dynamics gets no such
  gain — on silicon *or* in analog.
- The fast-path twin's constant factor is just engineering; the asymptotics
  (n² vs 2ⁿ) are the real point.

## Are we reducing the gap between silicon and quantum?

Two honest senses, and they point opposite ways.

**Complexity-theoretically: no — we're *mapping* the gap, not closing it.**
Free-fermion/matchgate circuits are exactly the classically-easy corner of
quantum computing. Simulating them efficiently on silicon doesn't catch up to
quantum — it proves this slice was *never on the hard side*. The genuine quantum
advantage lives in the *interacting* (non-matchgate) regime, and here's the
striking part: matchgates sit right at the edge. Valiant / Jozsa–Miyake showed
that matchgate circuits plus *one* non-matchgate gate (e.g. a SWAP) become
universal quantum computation (BQP-complete). So:

> Our analog twin simulates everything up to the boundary of quantum advantage —
> and one gate past the boundary, silicon is exponentially lost again.

We're not shrinking the gap; we're standing exactly on its edge and drawing the
map. The free-fermion corner is the largest natural class where silicon keeps
pace, and it's precisely the class with no quantum advantage to give.

**Practically/empirically: a little yes — and this is real science.** Every
classical structure-exploitation trick — free-fermion, tensor networks (low
entanglement), stabilizer-rank (low "magic") — raises the classical frontier,
which repeatedly forces quantum-advantage demonstrations into harder regimes.
(The Sycamore "supremacy" claim got chased down for years by improving classical
simulations.) So better classical methods shrink the *practical* set of
"quantum-only" computations — even though the conjectured asymptotic separation
(BQP ⊄ P) stays put.

### The unifying way to see it

The gap *is* structure. The question "classical or quantum-hard?" is really
"how much non-free / interacting / entangling / magic structure does your
computation carry?"

- Free-fermion → zero of it → classical, exactly what this demo simulates to 2048 qubits.
- The frontier of classical simulation = the frontier of exploitable structure.
- Quantum advantage = whatever structure remains unexploitable.

The principle is the same at every scale: find the structure, and the
"impossible" collapses to polynomial. Free fermions are the quantum instance of
it — and they mark the exact line where the structure runs out and genuine
quantum hardness begins. We didn't reduce the gap; we found its edge and built a
fast twin that lives right on it.

## Files

- `ff_analog_twin.py` — the benchmark: correctness check, the `FreeFermionCircuit`
  vs state-vector timing race, and the NumPy fast-path twin to 2048 qubits.
- `entanglement_entropy.py` — the worked example: entanglement entropy of a
  512-qubit chain (verified at small sizes, then run where brute force can't).
- `README.md` — this file.

## Requirements

Python ≥ 3.10, `numpy`, `sympy`, and `holant-tools` (`pip install holant-tools`).
No quantum hardware required — that's the whole point.
