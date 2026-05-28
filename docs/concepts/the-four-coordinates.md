# The four coordinates — quantifying distance from tractability

The [tier hierarchy](tier-hierarchy.md) gives discrete classifications:
T0, T1, T2, ..., T7. But within and around those, the framework
quantifies *how far* a problem sits from the easiest tractable point.
Four coordinates do this.

This is the **diagnostic-layer thesis** in its quantitative form: instead
of "tractable or not," ask *"how tractable, and along what axis?"*

## The four coordinates, named

| coordinate | what it measures | tractable when... | what increases it |
|---|---|---|---|
| **Matchgate rank** | how many parity-split components the signature needs | rank ≤ 2 (always true for symmetric) | non-symmetric signatures, larger arities |
| **Genus** | the surface the graph has to embed on | genus = 0 (planar) | non-planar edges, "twisted" rotation systems |
| **Sub-signature coverage** | how much of the problem can be tiled with in-family signatures | full coverage (every vertex's signature is in-family) | "out-of-family" signatures scattered through the graph |
| **Field-extension distance** | how far the signature values are from the underlying field | values in the base field (Q, F_2) | values in higher-degree algebraic extensions |

Each is a real-valued or integer-valued meter the classifier can emit.
Together they form a 4-dimensional coordinate space inside which any
Holant problem sits at one point.

## Coordinate 1 — matchgate rank

For a signature, **matchgate rank** measures the smallest number of
matchgate-realisable pieces needed to express it via parity-splitting.

The publicly-original result (see [`../originality.md`](../originality.md))
says: **every symmetric signature has basis-aware matchgate rank in
{0, 1, 2}** via a common-basis parity-split construction.

- **Rank 0** — the all-zero signature (rare in practice).
- **Rank 1** — directly matchgate-realisable in the natural basis.
- **Rank 2** — needs the parity-split construction.
- **Rank ≥ 3** — non-symmetric only; not yet characterised cleanly.

The framework computes this via
`holant_tools.basis_aware_matchgate_rank(signature, max_rank=2)`. The
result is in the route's meters whenever a signature-based stage is
classified.

**What it tells you:** the cost of evaluating the Holant per vertex.
Rank-1 vertices are direct Pfaffian contributions; rank-2 vertices add
a small constant factor; higher rank crosses into non-symmetric / Stembridge
territory.

**Concrete check:**
```python
sc = StructuralComputer()
cls = sc.classify_signature_via([1, 1, 1, 0])    # arity-3 symmetric
print(cls.meters["basis_aware_rank"])              # always in {0, 1, 2}
```

## Coordinate 2 — genus

The **genus** of a graph (with a chosen cellular embedding) tells you
which topological surface it embeds on:

- **Genus 0** — sphere; this is the planar case; FKT applies directly;
  cost is `O(n^3)`.
- **Genus g > 0** — surface with g holes; Galluccio-Loebl formula
  applies; cost is `O(4^g · n^3)`.

The framework computes genus via
`holant_tools.genus_from_rotation_system(rotation).genus`. For a graph
with vertices, edges, and a rotation system, the Euler characteristic
`χ = V - E + F` and `g = (2 - χ) / 2`.

**What it tells you:** the Pfaffian-cost overhead. Each unit of genus
multiplies cost by 4. So genus 1 = `4× planar`, genus 2 = `16× planar`,
genus 3 = `64×`, etc.

**Why the framework cares specifically:** the genus-g intersection
matrix on the homology basis needs to be computed correctly. The
*publicly-original* dart-chain passage-arc formula (see
[`../originality.md`](../originality.md)) is the corrected primitive
for this computation, replacing Cimasoni 2012's walks formula which has
a systematic blindspot at degree-3 vertices.

**Concrete check:**
```python
from holant_tools import genus_from_rotation_system
result = genus_from_rotation_system(my_rotation_system)
print(result.genus, "with overhead", 4 ** result.genus)
```

## Coordinate 3 — sub-signature coverage

For a Holant problem with `n` vertices, **coverage** is the fraction of
vertices whose signatures are in-family (matchgate-realisable). Coverage
= 1.0 means every vertex's signature is tractable; the whole problem is
in-family. Coverage < 1.0 means some vertices have non-matchgate-realisable
signatures, and the framework must either:

- (a) decompose the problem into in-family parts + brute-force the rest,
  paying `2^(non-coverage gap)` cost overhead;
- (b) route the whole thing to advised mode.

**What it tells you:** whether to expect a hybrid decomposition (most of
the problem fast, a small piece expensive) or a full honest-stop.

**Concrete check:** `holant_tools.signature_coverage(signature_list)`
returns the fraction of signatures that are matchgate-realisable in some
basis.

## Coordinate 4 — field-extension distance

For signatures whose values live in an algebraic extension field (e.g.,
the values involve `sqrt(2)` or roots of unity), **field-extension
distance** measures the degree of the extension over the underlying
field.

- **Distance 0** — values in the base field (rationals, or `F_2` for
  parity problems).
- **Distance d > 0** — values in a degree-`d` algebraic extension.

**What it tells you:** the size of intermediate symbolic expressions
during exact computation. Distance 0 = arithmetic in `Q` or `F_2`,
fast. Distance d = arithmetic in a degree-d extension, factor-d slower.

**Concrete check:** `holant_tools.field_extension_distance(signature)`.

## The diagnostic-layer thesis

Together, the four coordinates define a 4-dimensional **viewing frame**
for Holant problems. Every problem sits at a point in this space:

```
(matchgate rank, genus, coverage, field-extension distance)
```

The framework's classifier doesn't just emit a tier label — it emits the
problem's coordinates in this space. From them, the router computes the
expected cost (in `log2` ops) and the choice of member.

**Why this matters as a thesis.** Standard complexity theory says "P or
not-P." The Cai-Lu dichotomy says "tractable or hard." The diagnostic
layer says "**here's how far you are from tractable along each of four
independent axes, and here's what each step in each direction costs.**"

That graceful degradation is what makes the framework useful for *real*
problems (which are rarely perfectly in-family) rather than just the
canonical pretty cases.

## Worked example

Consider the K_{3,3} tournament from `tournament_scheduling/`:

- **Matchgate rank:** the signature at each vertex is "exactly one
  incident edge active" (the perfect-matching signature) → rank 1.
- **Genus:** the K_{3,3} embedding has genus 1 (computed via Euler χ);
  cost overhead is `4× planar`.
- **Coverage:** every vertex has the in-family matching signature →
  coverage 1.0.
- **Field-extension distance:** signature values are in {0, 1, -1} (the
  Kasteleyn signs) → distance 0.

Coordinate vector: `(1, 1, 1.0, 0)`. The framework dispatches to T4
free-fermion with cost `1 · log2(4) + 2 log2(12) ≈ 9.17`. Matches the
actual trace output.

## Connection to the originality pieces

Two of the framework's publicly-original results sharpen specific
coordinates:

1. **Basis-aware matchgate rank ≤ 2** sharpens the matchgate-rank
   coordinate for symmetric signatures: it's *always* in {0, 1, 2},
   never higher.

2. **The dart-chain passage-arc formula** corrects the genus-coordinate
   computation at degree-3 vertices (where the standard literature
   primitive returns degenerate intersection matrices, and so the
   downstream genus-cost overhead is mis-estimated).

Both results live in `holant-tools` and are exercised by the framework's
`classify` primitive on every execution.

## See also

- [`holant-and-matchgates.md`](holant-and-matchgates.md) — the mathematics
  the coordinates are coordinates *in*.
- [`tier-hierarchy.md`](tier-hierarchy.md) — the discrete classification
  derived from the coordinates.
- [`the-paradigm.md`](the-paradigm.md) — the paradigm-level claim under
  which the coordinates are the natural cost model.
- [`../originality.md`](../originality.md) — the publicly-original
  refinements to the matchgate-rank and genus coordinates.
