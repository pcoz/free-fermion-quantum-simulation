# The hybrid dispatcher — cut a problem, then route each piece

The [`simulator-router/`](../simulator-router/) example answers *"which single
simulator is cheapest for this whole circuit?"* This is the sequel, and it closes
the loop: instead of choosing one method, **cut the circuit into pieces and route
each piece to its own cheapest simulator** — and one piece is actually run on a real
stabilizer engine — paying an exponential price only in the small "hard part" that
connects the pieces.

```bash
python hybrid_dispatcher.py     # needs numpy
```

## Two ideas, combined

**1. Circuit cutting** (circuit knitting / the Schrödinger–Feynman method — what
Google used to verify Sycamore on classical computers). Split the qubits into halves
**A** and **B**; only a few gates *cross* between them. We expand each crossing
two-qubit gate in the **Pauli basis**, `G = Σ c_{PQ} P ⊗ Q`. Expanding, the whole
circuit becomes a sum over **branches**, and in every branch the gates split cleanly
into an A-only and a B-only circuit:

```
|whole circuit>  =  Σ over branches   coeff · |result on A>  ⊗  |result on B>
```

This is an **exact identity**. The Pauli basis is chosen deliberately: the factor
injected into each block is a *Pauli*, so block A stays a **Clifford** circuit (a
stabilizer simulator can run it) and block B stays a matchgate-plus-Pauli circuit.
You pay only in the cut; the price of the Pauli basis is a few more branches (4 per
CNOT instead of 2).

**2. Per-block routing — with a real per-block engine.** Once cut, each half is its
own circuit, so we route it to its cheapest member. Here block A is **actually
executed by a phase-aware stabilizer engine**, not the universal one. The punchline:

> A circuit can have **no single cheap method as a whole**, yet split into halves
> that are each easy along a **different axis.**

## Why the stabilizer engine must be phase-aware

The recombination sums `|A> ⊗ |B>` over branches, so each block state must carry its
correct **global phase** — otherwise the branches interfere wrongly. A bare
stabilizer *tableau* is poly-time but fixes the state only up to a global phase,
which is exactly the information the cut needs. So block A is run with a stabilizer
engine in the **explicit-superposition representation**: it keeps the state as its
sparse amplitudes over the affine stabilizer support — phase-exact, and compressed to
`2^(support)` entries (a genuine saving for low-Hadamard Clifford blocks). A
self-test checks it against the universal engine on 200 random Clifford circuits,
exactly, global phase included. (Poly-time *and* phase-exact is the CH-form; this is
the phase-exact, easy-to-verify version.)

## What the script shows

The demo circuit is a **Clifford half welded to a free-fermion half**, plus two
crossing gates, on 20 qubits:

```
[self-test passed: stabilizer engine is phase-exact on 200 random Clifford circuits]

Route the WHOLE circuit:  -> STABILIZER   (t=21, k=19; best single method, cost ~ 2^13.4)
  No single method is polynomial on the whole.

Cut into two halves and route EACH:
  block A (0..9):   -> STABILIZER    (t=0)  -- RUN on the stabilizer engine, support 2^3 = 8 (not 2^10)
  block B (10..19): -> FREE FERMION  (k=0)  -- universal engine (native free-fermion engine: future)
  + 2 crossing gates, Pauli-decomposed  ->  16 branches

Exact match with brute force: True

  brute force ............. 2^20 = 1,048,576
  route the whole circuit . ~ 11,115
  cut + route each half ... 16 x (2^3 + 2^8.6) = 6,528   (161x less than brute force)
```

The recombined state is **verified equal to brute force to machine precision**, with
block A genuinely run in the stabilizer formalism (support 8, not 1024). Cutting
*exposed* structure invisible in the whole circuit: each half is cheap under a
different member, and you pay only for the cut.

## Honest scope

Circuit cutting is exact and general, but its cost is **multiplicative in the number
of crossing gates** (branches grow with each crossing gate's Pauli rank), so it wins
when the cut is narrow — the regime the router's entanglement meter `w` detects.
Block A is now run by a real phase-aware stabilizer engine; **running block B on its
native polynomial free-fermion engine** (phase-correct across the cut) is the one
remaining drop-in. The stabilizer engine's explicit-superposition representation is
phase-exact but its cost scales with the stabilizer support (`2^k`), which is small
for low-Hadamard blocks and grows toward the full vector for Hadamard-heavy ones; the
CH-form is the poly-time-always refinement.
