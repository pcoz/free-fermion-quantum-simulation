# Which classical simulator should you use? — a tractability router

This repo's main README has a table of the different ways to simulate a quantum
circuit on an ordinary computer. The whole point of that table is that **each
method is cheap only when the circuit has a particular kind of structure** — so
the practical question is always: *for this circuit, which method is the cheap
one?*

This example answers that **automatically**. Give it a circuit and it measures how
far the circuit sits from each kind of "easy structure", estimates what each
method would cost, and names the winner.

```bash
python simulator_router.py                       # route six built-in circuits
python simulator_router.py examples/clifford_t.qasm   # route YOUR own circuit
```

Pure Python, no dependencies.

## For developers (no quantum physics required)

If you just want to know *"can I run this circuit on my machine, and how?"*, use the
plain-English front-end [`feasibility_advisor.py`](feasibility_advisor.py). It wraps
the router and, for any circuit, tells you which off-the-shelf simulator to reach
for, roughly how long it would take, whether it fits in memory, and a one-line
jargon-free reason — plus a clear verdict: laptop job / workstation job / cluster job
/ not feasible classically (i.e. genuinely needs a quantum computer).

```bash
python feasibility_advisor.py                        # advise on a batch of circuits
python feasibility_advisor.py examples/clifford_t.qasm   # advise on YOUR own circuit
```

Sample output:

```
circuit: error-correction-style circuit (Clifford)  (500 qubits, ...)
  -> verdict     : LAPTOP JOB -- runs almost instantly.
  -> best tool   : a stabilizer simulator (e.g. Stim, or Qiskit StabilizerState)
  -> why         : only 0 of your gates are the 'hard' kind for this simulator ...

circuit: deep, dense, general-purpose circuit  (60 qubits, ...)
  -> verdict     : NOT FEASIBLE CLASSICALLY -- this is what real quantum hardware is for.
  -> rough cost  : ~2^60 operations (longer than the age of the universe)
  -> memory note : a state vector needs 16384.0 PB of RAM
```

You don't need to understand free fermions, stabilizers, or matchgates — the advisor
reads the structure for you and names the right tool.

## How it routes

It computes three honest structural meters and compares four cost estimates:

| method | the meter it pays in | cheap when |
|---|---|---|
| **State vector** (brute force) | nothing — always 2ⁿ | never cheap; the fallback |
| **Stabilizer / Clifford+T** | **T-count** `t` (non-Clifford gates) | `t` is small (cost ~ 2^0.23ᵗ) |
| **Free fermion / matchgate** | **interacting-gate count** `k` (non-matchgate gates) | `k = 0` → polynomial; degrades gently as `k` grows |
| **Tensor network** (MPS/PEPS) | **entanglement width** `w` across a cut | `w` is small (shallow / low-entanglement) |

## What it shows

Running it routes six circuits to **six different answers**:

- a free-fermion (Ising-dynamics) circuit → **free fermion** (`k = 0`, polynomial — even though it has thousands of non-Clifford gates and volume-law entanglement);
- the same circuit with one interacting gate added → still **free fermion**, now `k = 1` (graceful degradation);
- a deep Clifford circuit → **stabilizer** (`t = 0`, even though it is hopeless for the matchgate method);
- Clifford + a few T-gates → still **stabilizer**;
- a shallow generic circuit → **tensor network** (low entanglement);
- a deep, dense, random circuit → **none of them win**: the router flags the **genuinely-quantum regime**, where no classical structure applies and a real quantum computer is what you would actually want.

The headline lesson: **there is no single best classical simulator.** The axes are
*independent* — being easy for one method tells you nothing about the others — and
the router is what matches a problem to the right tool. The free-fermion axis (the
one this repository is built on) is the exact, entanglement-indifferent corner: it
wins precisely when a circuit is non-interacting, no matter how non-Clifford or
entangled it is.

## Route your own circuit

Pass a circuit file and the router analyses just that circuit. Two simple text
formats are accepted (auto-detected) — gate *parameters are ignored*, since routing
only depends on the circuit's structure, not its numbers:

**Plain** — one gate per line, `NAME qubit [qubit ...]`; `#` starts a comment and an
optional `qubits N` line sets the size (otherwise it is inferred):

```
qubits 4
rz 0
xx_yy 0 1      # a matchgate on neighbours
cx 0 2         # an interacting gate -> bumps k
```

**QASM-lite** — a subset of OpenQASM 2.0 (`qreg q[N];` plus gate lines):

```
OPENQASM 2.0;
qreg q[4];
h q[0];
cx q[0],q[1];
t q[2];
rz(0.5) q[1];
```

Two ready-to-run examples live in [`examples/`](examples/):

```bash
python simulator_router.py examples/clifford_t.qasm    # -> stabilizer (only 2 T-gates)
python simulator_router.py examples/free_fermion.txt   # -> free fermion (k = 0)
```

Recognised gate names: Clifford `h s sdg x y z cx/cnot cz swap`; non-Clifford
`t tdg rz rx ry`; matchgates `rz z xy xx_yy givens fswap`; multi-qubit `ccx`. Any
**unrecognised** name is treated as a generic gate — neither Clifford nor matchgate
— which is the safe, conservative choice (it counts against *both* `t` and `k`).

## Honest scope

The structural meters (T-count, non-matchgate count, cut entanglement) are real and
computed honestly; the cost *constants* are illustrative — chosen so the **ordering**
of methods is right, not as certified complexity bounds. (The 0.23 stabilizer-rank
exponent is Bravyi–Gosset 2016; the per-gate free-fermion base and polynomial
overheads are representative.) Quantum Monte Carlo is omitted on purpose: it targets
a different problem class (thermal/ground states of sign-free Hamiltonians), not
arbitrary gate circuits. When the router answers "free fermion", the actual
simulation is exactly what [`../free-fermion/ff_analog_twin.py`](../free-fermion/)
does.
