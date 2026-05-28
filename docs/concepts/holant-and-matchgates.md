# Holant problems and matchgates — the foundational primitive

The framework's exact-computation kernel sits on top of two ideas: the
**matching sum** (introduced in the [glossary](../glossary.md)) and the
**Holant problem** that generalises it. This page walks through what they
are, how they fit together, and why this is the central computational
primitive of structured combinatorial reasoning.

## Start with the matching sum

A graph with edge weights `w_e`. A *perfect matching* is a set of edges
covering every vertex exactly once. The matching sum is:

```
matching_sum(G, w)  =  sum over perfect matchings M of  product over e in M of w_e
```

That's the central object. It encodes:

- **Counts** (set all `w_e = 1`),
- **Probabilities** (set `w_e` to per-edge success probability),
- **Expectations** (ratio of two matching sums with different weights),
- **Partition functions** (set `w_e` to Boltzmann factors),
- **Reliability tails** (set `w_e` to intactness indicators),
- ... and more (see [`glossary.md`](../glossary.md)).

For planar graphs, **Kasteleyn (1961)** showed the matching sum equals the
Pfaffian of a specific skew-symmetric matrix derived from the graph (the
"Kasteleyn-orientated adjacency matrix"). Pfaffians are computable in
`O(n^3)` time. So the matching sum on a planar graph is poly-time exact.

This is the **FKT theorem** (Fisher-Kasteleyn-Temperley). It is the single
mathematical fact that makes everything in this framework possible.

## The Holant generalisation

Matching sums are great but restrictive: every vertex's "rule" is *"exactly
one of my incident edges must be in the matching."* What if you want
*other* rules?

- "exactly K of my incident edges" (cardinality constraints)
- "all-or-nothing" (parity constraints)
- "the XOR of my incident edges equals 1" (linear constraints)
- "OR / AND" (boolean constraints)

The **Holant problem** lets each vertex have an arbitrary rule, called a
**signature**. A signature at a vertex of degree `n` is just a function
`{0, 1}^n → ℝ` (or any semiring): for each possible pattern of edges-on
or edges-off incident to that vertex, the signature says how much that
pattern contributes.

The Holant value of a graph is:

```
Holant(G, sigs)  =  sum over edge-assignments  (e_1, ..., e_m) in {0,1}^m  of
                    product over v in V  of  sig_v(e_incident_to_v)
```

A few examples of useful signatures (on arity 2 — vertices of degree 2):

```
"PERFECT MATCHING"  sig(00) = 0  sig(01) = 1  sig(10) = 1  sig(11) = 0
                    (exactly one edge incident is on)

"OR"                sig(00) = 0  sig(01) = 1  sig(10) = 1  sig(11) = 1

"XOR"               sig(00) = 0  sig(01) = 1  sig(10) = 1  sig(11) = 0
                    (same as PERFECT MATCHING in arity 2!)

"EQUAL"             sig(00) = 1  sig(01) = 0  sig(10) = 0  sig(11) = 1
                    (both edges must agree)
```

**Symmetric signatures** are signatures whose value depends only on the
*Hamming weight* of the inputs (how many edges are on, not which ones).
A symmetric arity-n signature is just a sequence `[v_0, v_1, ..., v_n]`
of n+1 numbers. The framework's `classify_signature` handles these
specifically and reports their basis-aware matchgate rank in the meters.

## Why this is one primitive, not several

Once you can compute Holant values exactly, every combinatorial counting
question on graphs becomes "**choose the right signatures** and compute
the Holant." The matching sum is a Holant problem. The number of
satisfying assignments to a 2-SAT instance is a Holant problem (with `OR`
signatures at clause vertices). The partition function of any planar
graphical model is a Holant problem. Counting independent sets, counting
perfect colourings, counting Eulerian circuits — all Holant problems
with different signature choices.

So the framework's primitive isn't "count perfect matchings"; it's
"**evaluate any Holant problem on a structured graph**." Everything else
is a wrapper.

## The Cai-Lu dichotomy (high level)

A natural question: which Holant problems are poly-time exact? The
**Cai-Lu dichotomy theorem** (Cai, Lu, Xia, 2009-2014) classifies all
Holant problems into two camps:

- **Either** the problem is poly-time computable via the matchgate /
  free-fermion / FKT family — call this **tractable**.
- **Or** the problem is #P-hard (in the standard complexity-theoretic
  sense) — call this **hard**.

There's no middle ground. The dichotomy is sharp.

The tractable side has a clean structural characterisation: signatures
that are **matchgate-realisable** in some basis. The framework's tier
hierarchy (T0 through T7) is the operational form of this dichotomy:
T0–T4 are in-family (matchgate-realisable, poly-time), T5–T7 are out of
family.

## Matchgates as building blocks

A **matchgate** is a small graph gadget whose signature, viewed as the
matching-sum pattern at its dangling edges, equals some target signature
you want to use. By composing matchgate gadgets, you can build up large
Holant problems whose total matching sum is exactly the answer to your
question.

This is the practical mechanism of the FKT / matchgate-Holant family:
**every tractable Holant problem can be wired as matching sums on a
larger planar graph**, then evaluated via a single Pfaffian. No
enumeration. No sampling. Polynomial time.

The framework hides this wiring from the user — `classify` + `route` +
the appropriate evaluator do it automatically based on the problem's
classification. But conceptually, every exact answer the framework
produces is "the Pfaffian of a Kasteleyn matrix of a specific gadget
graph built up from your problem's signatures."

## What's beyond the matchgate family

The Cai-Lu dichotomy is binary: either matchgate-realisable in some basis
(tractable) or #P-hard. But the framework has finer structure than that:

- **Genus.** Planar Holant is poly-time via FKT. Bounded-genus Holant
  costs an additional `4^g` factor via the Galluccio-Loebl formula. So
  genus is a "near-tractable" coordinate: small genus is still
  poly-time, with a known cost overhead.
- **Basis-aware matchgate rank.** Symmetric signatures are always in
  {0, 1, 2} (the publicly-original result; see [`originality.md`](../originality.md)).
  Higher rank for non-symmetric signatures may exist; this is open
  research.
- **Coverage / field-extension distance.** Further coordinates in the
  diagnostic-layer thesis (see [`the-four-coordinates.md`](the-four-coordinates.md))
  that quantify how far an "outside-family" problem is from being
  in-family.

The Cai-Lu dichotomy says nothing about graceful degradation — it just
says "tractable or hard." The framework's coordinates let you quantify
the degradation: "this problem is genus 2, so it's exactly solvable at
`16× planar cost`; this signature has basis-aware rank 2, so it's
solvable via the parity-split construction."

## In one paragraph

The matching sum is the central primitive. The Holant problem generalises
it with arbitrary vertex signatures. The Cai-Lu dichotomy classifies
Holant problems into poly-time-tractable (the matchgate-realisable family)
and #P-hard. The framework's tier hierarchy is the operational
classification: T0–T4 are tractable members (different signature shapes /
genus), T5–T7 are advised. Every exact answer the framework produces is a
Holant evaluation in disguise; every Holant evaluation reduces to a
Pfaffian on a matchgate-gadget graph via FKT.

That's the chain. Once you see it, the framework is just "exact Holant
evaluation, automatically classified and routed."

## See also

- [`tier-hierarchy.md`](tier-hierarchy.md) — how the framework operationalises
  the Cai-Lu dichotomy.
- [`the-four-coordinates.md`](the-four-coordinates.md) — finer-grained
  classification beyond tier.
- [`the-paradigm.md`](the-paradigm.md) — what this all looks like at the
  paradigm-level, abstracted up.
- [`../glossary.md`](../glossary.md) — for vocabulary.
- [`../originality.md`](../originality.md) — for the novel pieces in
  this specific tradition.
