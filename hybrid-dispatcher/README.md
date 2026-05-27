# The hybrid dispatcher — cut a problem, then route each piece

The [`simulator-router/`](../simulator-router/) example answers *"which single
simulator is cheapest for this whole circuit?"* This is the sequel, and it closes
the loop: instead of choosing one method, **cut the circuit into pieces and route
each piece to its own cheapest simulator**, paying an exponential price only in the
small "hard part" that connects the pieces.

```bash
python hybrid_dispatcher.py     # needs numpy
```

## Two ideas, combined

**1. Circuit cutting** (also called circuit knitting / the Schrödinger–Feynman
method — what Google used to verify Sycamore on classical computers). Split the
qubits into two halves, **A** and **B**. Most gates act inside one half; only a few
*cross* between them. Every crossing two-qubit gate can be rewritten as a short sum
of products of one-qubit operators (its *operator Schmidt decomposition* — ≤ 4 terms,
just 2 for a CNOT). Expanding, the whole circuit becomes a sum over **branches**, and
in every branch the gates split cleanly into an A-only and a B-only circuit:

```
|whole circuit>  =  Σ over branches   |result on A>  ⊗  |result on B>
```

This is an **exact identity**, and you pay only in the cut (branches = product of the
crossing gates' Schmidt ranks), never in the bulk.

**2. Per-block routing.** Once cut, each half is its own circuit — so run the router
on it and send it to its cheapest member. The punchline:

> A circuit can have **no single cheap method as a whole**, yet split into halves
> that are each easy along a **different axis.**

## What the script shows

The demo circuit is exactly that two-natured case — a **Clifford half welded to a
free-fermion half**, plus two crossing gates — on 20 qubits:

```
Route the WHOLE circuit:  -> STABILIZER   (t=21, k=27; best single method, cost ~ 2^13.4)
  No single method is polynomial on the whole: a stabilizer simulator must pay
  for all the non-Clifford rotations, a free-fermion simulator for all the H/CX gates.

Cut into two halves and route EACH:
  block A (qubits 0..9):   -> STABILIZER    (t=0, k=25;  cost ~ 2^6.6)   ← polynomial
  block B (qubits 10..19): -> FREE FERMION  (t=21, k=0;  cost ~ 2^8.6)   ← polynomial
  + 2 crossing gates  ->  4 branches

Exact match with brute force: True

  brute force ............. 2^20 = 1,048,576
  route the whole circuit . ~ 11,115
  cut + route each half ... 4 x (2^6.6 + 2^8.6) = 2,000   (524x less than brute force)
```

The recombined state is **verified equal to brute force to machine precision**.
Cutting *exposed* structure that was invisible in the whole circuit: each half is
polynomial under a different member, and you pay only for the cut.

## Why this matters

This is the dispatcher's whole reason for existing, made concrete and *exact*: a
problem with no single cheap method is split into pieces that are each cheap, each
routed to its own member. Because it is exact (not sampled or truncated), it supports
the workflows the rest of this repo is about — certified ground truth, exact
probabilities, no error bars.

## Honest scope

Circuit cutting is exact and general, but its cost is **multiplicative in the number
of crossing gates** (branches = product of their Schmidt ranks, up to 4ᵐ for *m*
crossing gates), so it wins only when the cut is narrow — exactly the regime the
router's entanglement meter `w` detects. The per-block **routing decision and its
cost are real and computed per block**; for the exact numerical check each half is
executed on the universal state-vector reference engine, which is phase-exact so the
cut and recombination can be verified against brute force. Substituting each member's
**native polynomial engine** — with the correct global phase across the cut — is the
final piece of engineering.
