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
python simulator_router.py      # pure Python, no dependencies
```

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
