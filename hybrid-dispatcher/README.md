# The hybrid dispatcher — cut a problem, then route each piece

The [`simulator-router/`](../simulator-router/) example answers *"which single
simulator is cheapest for this whole circuit?"* This is the sequel, and it closes
the loop: instead of choosing one method, **cut the circuit into pieces and route
each piece to its own cheapest simulator** — and *both* halves are now run on real
structured engines (a stabilizer engine and a free-fermion engine) — paying an
exponential price only in the small "hard part" that connects the pieces.

```bash
python hybrid_dispatcher.py     # needs numpy
```

## Two ideas, combined

**1. Circuit cutting** (circuit knitting / the Schrödinger–Feynman method — what
Google used to verify Sycamore on classical computers). Split the qubits into halves
**A** and **B**; only a few gates *cross* between them. We expand each crossing gate
in the **Pauli basis**, `G = Σ c_{PQ} P ⊗ Q`. Expanding, the whole circuit becomes a
sum over **branches**, and in every branch the gates split cleanly into an A-only and
a B-only circuit:

```
|whole circuit>  =  Σ over branches   coeff · |result on A>  ⊗  |result on B>
```

This is an **exact identity**. We cut with **CZ** gates on purpose: their Pauli
decomposition injects only `I` or `Z` (a *diagonal* factor) into each block — so
block A stays **Clifford** and block B stays a **free-fermion (matchgate)** circuit,
each piece remaining inside its member's gate set, and each block state factorises as
a fixed base state times a cheap sign mask. You pay only in the cut.

**2. Per-block routing — with real per-block engines.** Once cut, each half is its
own circuit, routed to its cheapest member and **run there**:

> A circuit can have **no single cheap method as a whole**, yet split into halves
> that are each easy along a **different axis** — a Clifford half and a free-fermion
> half.

## The two engines (and why they must be phase-aware)

The recombination sums `|A> ⊗ |B>` over branches, so each block state must carry its
correct **global phase**, or the branches interfere wrongly. A bare stabilizer
tableau (or a bare covariance matrix) is poly-time but fixes the state only up to a
global phase — exactly the information the cut needs. So both engines track it:

- **Stabilizer (block A)** — the explicit stabilizer-superposition representation:
  the state as its sparse amplitudes over the affine support. Phase-exact, and
  compresses to `2^(support)` (block A spreads over `2^3`, not `2^10`).
- **Free fermion (block B)** — the fermionic Gaussian representation: the `m × m`
  pairing matrix `A` with `|ψ> ∝ exp(½ Σ A_ij a†_i a†_j)|0>`. Matchgates update `A` in
  closed form (number-conserving gates by congruence `A → W A Wᵀ`; an initial
  disjoint pairing layer sets `A` directly), the vacuum amplitude `<0|ψ>` is tracked
  to fix the global phase, and amplitudes are **Pfaffians**: `<x|ψ> = <0|ψ>·Pf(A[occupied modes of x])`.

Both engines are validated by a **self-test against the universal backend on random
circuits** (150 Clifford + 150 matchgate), exactly, global phase included — before
the dispatcher runs.

## What the script shows

The demo circuit is a **Clifford half welded to a free-fermion half**, plus two CZ
crossing gates, on 20 qubits:

```
[stabilizer engine: phase-exact on 150 random Clifford circuits]
[free-fermion engine: phase-exact on 150 random matchgate circuits]

Route the WHOLE circuit:  -> STABILIZER   (t=25, k=19; best single method, cost ~ 2^14.4)
  No single method is polynomial on the whole.

Cut into two halves and route EACH:
  block A (0..9):   -> STABILIZER    (t=0)  -- RUN on the stabilizer engine, support 2^3 = 8 (not 2^10)
  block B (10..19): -> FREE FERMION  (k=0)  -- RUN on the free-fermion engine (pairing matrix + Pfaffians)
  + 2 crossing CZ gates, Pauli-decomposed  ->  16 branches

Exact match with brute force: True

  brute force ............. 2^20 = 1,048,576
  route the whole circuit . ~ 20,938
  cut + route each half ... 16 x (2^3 + 2^8.6) = 6,528   (161x less than brute force)
```

The recombined state is **verified equal to brute force to machine precision**, with
each half genuinely run on its own structured, phase-exact engine. Cutting *exposed*
structure invisible in the whole circuit: each half is cheap under a different member.

## Honest scope

Circuit cutting is exact and general, but its cost is **multiplicative in the number
of crossing gates** (branches grow with each crossing gate's Pauli rank), so it wins
when the cut is narrow — the regime the router's entanglement meter `w` detects. Both
engines are phase-exact, and their *compact* objects are poly (the stabilizer support
and the `m × m` pairing matrix).

**A poly-time-always stabilizer engine is in [`ch_form.py`](ch_form.py).** The block-A
engine above is phase-exact but its cost scales with the stabilizer support (`2^k`),
so it is only cheap for low-Hadamard blocks. `ch_form.py` carries the *same* phase-exact
state in the affine-quadratic (CH) form — an `O(n·k)` matrix, never the `2^k` support —
and updates it in polynomial time for `X, Z, S, CX, CZ` and **`H` anywhere** (including
on an already-entangled qubit, the delicate core of the CH-form, handled by evaluating
the new amplitude function and re-fitting the form — both polynomial). A self-test
checks it against a state-vector backend on **1500 random Clifford circuits** (H in any
position), exactly, global phase included. So a stabilizer block costs `O(n·k)`
regardless of how many Hadamards it has.

**Amplitude-level recombination (the asymptotic win) is implemented.** Beyond building
the full state, the script also exposes `build_amplitude_oracle`, which returns a
function `amp(x)` giving any single output amplitude `<x|U|0>` with **no 2ⁿ vector
ever built**: it factorises as `α_A(x_A)·α_B(x_B)·Σ_branches(coeff·signs)`, where
`α_A` is one stabilizer-amplitude lookup, `α_B` is **one Pfaffian** over the occupied
modes of `x_B`, and the branch sum is over the few crossing branches — all polynomial
per amplitude. A run checks a sample of these against brute force exactly. So you can
compute just the outcomes you care about (e.g. the most likely ones), where brute
force must first build all 2ⁿ amplitudes.
