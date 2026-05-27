r"""Which classical simulator should you use? -- a tractability router.

The companion to this repo's landscape table ("Where this repository sits among
other quantum simulation systems"). That table lists several ways to simulate a
quantum circuit on an ordinary computer, and the key point is that *each one
exploits a different kind of structure* and is cheap only when that structure is
present. So the practical question for any given circuit is: **which method is the
cheap one here?**

This script answers that automatically. It takes a circuit and measures how far
the circuit sits from each kind of "easy structure" -- i.e. how much of the
expensive stuff each method would have to pay for:

  * State vector  (brute force) ........ no structure used; always costs 2^n.
  * Stabilizer / Clifford+T ............ pays for NON-CLIFFORD gates (the
                                         "T-count" t); cost ~ 2^(0.23 t).
  * Free fermion / matchgate ........... pays for INTERACTING (non-matchgate)
                                         gates (the count k); cost ~ base^k,
                                         and free (polynomial) when k = 0.
  * Tensor network (MPS/PEPS) .......... pays for ENTANGLEMENT across a cut (the
                                         width w); cost ~ 2^(2w).

It then prints the estimated cost of each method and names the winner -- and, when
*no* method beats brute force, it flags the circuit as living in the
genuinely-quantum regime (the regime a real quantum computer is actually for).

Crucial teaching point that falls straight out of this: the axes are INDEPENDENT.
A circuit of Z- and XY-rotations is free-fermion-trivial (k = 0) yet has a huge
T-count; a circuit of H and CNOT is stabilizer-trivial (t = 0) yet is hopeless for
the matchgate method. Neither is "simpler" than the other -- they are simple along
*different* axes, and the router is what tells them apart.

Honest scope
------------
These are deliberately simple, ORDER-OF-MAGNITUDE cost estimates meant to make the
routing logic transparent and correct in its *ordering*, not certified complexity
bounds. The structural meters (T-count, non-matchgate count, cut entanglement) are
real and computed honestly; the cost constants are illustrative (the 0.23
stabilizer-rank exponent is Bravyi-Gosset 2016; the per-gate free-fermion base and
the polynomial overheads are representative). Quantum Monte Carlo is deliberately
omitted: it targets a different problem class (thermal / ground states of sign-free
Hamiltonians), not arbitrary gate circuits. When the router answers "free fermion",
the actual simulation is exactly what `../free-fermion/ff_analog_twin.py` does.

Run:  python simulator_router.py
"""
import math
from collections import namedtuple

# A gate is just its NAME and the qubits it acts on -- routing only needs the
# circuit's structure (which gate types, on which wires), never the numbers.
Gate = namedtuple("Gate", ["name", "qubits"])


# --- gate vocabularies -------------------------------------------------------
# The Clifford generators: the "free" gates for the stabilizer simulator
# (Gottesman-Knill -- any circuit of these alone is classically poly-time).
CLIFFORD = {"H", "S", "Sdg", "X", "Y", "Z", "CX", "CNOT", "CZ", "SWAP"}

# Non-Clifford gates are what the stabilizer simulator must pay for. The canonical
# unit is the T-gate (weight 1). A Toffoli (CCX) is non-Clifford and decomposes
# into ~7 T-gates, so it carries weight 7. An arbitrary-angle rotation formally
# needs ~log(1/eps) T-gates to synthesise; we charge it a representative 1.
NON_CLIFFORD_WEIGHT = {"CCX": 7, "TOFFOLI": 7}   # everything else not in CLIFFORD: weight 1

# Matchgate (free-fermion / Gaussian) gates: nearest-neighbour Gaussian operations.
# Single-mode Z-rotations and two-mode "Givens" / XY rotations and the FERMIONIC
# swap are matchgates. Note what is NOT here: H, CNOT, CZ, and the ordinary SWAP
# are not fermion-Gaussian (SWAP in particular makes matchgates universal).
MATCHGATE = {"RZ", "Z", "XY", "XX_YY", "GIVENS", "FSWAP", "MG"}


# --- the three structural meters ---------------------------------------------
def t_count(circuit):
    """How many non-Clifford gates -- the meter the stabilizer simulator pays in."""
    t = 0
    for g in circuit:
        if g.name in CLIFFORD:
            continue
        t += NON_CLIFFORD_WEIGHT.get(g.name, 1)
    return t


def non_matchgate_count(circuit):
    """How many gates are NOT free-fermion -- the meter the matchgate simulator
    pays in. A gate counts as a matchgate only if it is in the matchgate set AND
    (for two-qubit gates) acts on ADJACENT modes; a long-range "matchgate" breaks
    the free-fermion locality and must be paid for."""
    k = 0
    for g in circuit:
        is_mg = g.name in MATCHGATE
        if is_mg and len(g.qubits) == 2 and abs(g.qubits[0] - g.qubits[1]) != 1:
            is_mg = False
        if not is_mg:
            k += 1
    return k


def central_cut_entanglement(circuit, n):
    """An UPPER bound (in qubits) on the entanglement a tensor network must carry
    across the central bipartition [0, n/2) | [n/2, n). Each two-qubit gate that
    straddles the cut can at most double the Schmidt rank -- i.e. add 1 to its
    log2 -- capped by the number of qubits on the smaller side. This is exactly
    how one bounds the bond dimension an MPS needs, and it correctly captures that
    entanglement GROWS WITH DEPTH: a deep entangling circuit saturates at n/2
    (tensor networks then cost as much as brute force), while a shallow one stays
    small (tensor networks win)."""
    cut = n // 2
    cap = min(cut, n - cut)
    w = 0
    for g in circuit:
        if len(g.qubits) == 2:
            a, b = g.qubits
            if (a < cut) != (b < cut):        # one endpoint each side of the cut
                w = min(w + 1, cap)
    return w


# --- cost model (log2 of the operation/memory count; illustrative) -----------
ALPHA = 0.2284          # Bravyi-Gosset stabilizer-rank exponent: chi ~ 2^(ALPHA * t)
BASE_FF = 4.0           # illustrative: each non-matchgate gate multiplies the
                        # free-fermion ("Gaussian rank") cost by ~ this constant


def _poly(m):
    """A representative polynomial overhead (~ m^2), expressed in log2."""
    return 2.0 * math.log2(max(m, 2))


def estimate_costs(circuit, n):
    """Return {method: (log2_cost, reason)} plus the raw structural meters."""
    t = t_count(circuit)
    k = non_matchgate_count(circuit)
    w = central_cut_entanglement(circuit, n)
    genus = 0   # all example circuits below are nearest-neighbour on a line => planar

    costs = {
        # brute force: store all 2^n amplitudes, no structure exploited.
        "state vector":   (float(n),
                           "stores all 2^n amplitudes (no structure used)"),
        # Gottesman-Knill + stabilizer rank: poly when t = 0, else ~ 2^(0.23 t).
        "stabilizer":     (ALPHA * t + _poly(n),
                           f"t = {t} non-Clifford gates"),
        # FKT / Pfaffian: poly when k = 0 (and planar); a genus-g surface adds 4^g.
        "free fermion":   (k * math.log2(BASE_FF) + _poly(2 * n) + 2 * genus,
                           f"k = {k} interacting (non-matchgate) gates, genus {genus}"),
        # MPS/PEPS: bond dimension 2^w, contraction/memory ~ (2^w)^2 = 2^(2w).
        "tensor network": (2.0 * w + _poly(n),
                           f"entanglement width <= {w} across the central cut"),
    }
    return costs, dict(t=t, k=k, w=w, genus=genus)


def route(name, circuit, n):
    """Print the per-method cost analysis for one circuit and return the winner."""
    costs, meters = estimate_costs(circuit, n)
    winner = min(costs, key=lambda m: costs[m][0])

    print("-" * 74)
    print(f"  {name}   (n = {n} qubits, {len(circuit)} gates)")
    print(f"  meters:  T-count t = {meters['t']:<5} "
          f"non-matchgate k = {meters['k']:<5} "
          f"cut-entanglement w = {meters['w']}")
    print("  " + "-" * 70)
    for method, (log2cost, reason) in sorted(costs.items(), key=lambda kv: kv[1][0]):
        mark = "  <== cheapest" if method == winner else ""
        print(f"    {method:<16} cost ~ 2^{log2cost:6.1f}   ({reason}){mark}")

    # If even the best structured method cannot beat brute force, there is no
    # structure to exploit -- this is the regime a quantum computer is actually for.
    best_structured = min(c for m, (c, _) in costs.items() if m != "state vector")
    if best_structured >= costs["state vector"][0] - 1e-9:
        print("  >> no exploitable structure: every method costs ~ 2^n. This is the")
        print("     genuinely-quantum regime -- brute force only because n is small;")
        print("     at scale this is what you would want a quantum computer for.")
    else:
        print(f"  >> route to: {winner.upper()}")
    return winner


# --- example circuits (nearest-neighbour on a line of n qubits) --------------
def _brickwork_pairs(n, layer):
    """Alternating nearest-neighbour pairs (0,1),(2,3),... then (1,2),(3,4),..."""
    start = layer % 2
    return [(i, i + 1) for i in range(start, n - 1, 2)]


def tfim_trotter(n, depth):
    """Transverse-field Ising Trotter dynamics: single-qubit Z-rotations + two-qubit
    XY/XX-YY rotations on neighbours. EVERY gate is a matchgate -> k = 0 (free
    fermion is exact and polynomial), yet it is highly non-Clifford and builds
    volume-law entanglement."""
    c = []
    for layer in range(depth):
        for q in range(n):
            c.append(Gate("RZ", (q,)))
        for (a, b) in _brickwork_pairs(n, layer):
            c.append(Gate("XX_YY", (a, b)))
    return c


def tfim_trotter_plus_one_toffoli(n, depth):
    """The same free-fermion circuit with a SINGLE interacting (Toffoli) gate
    dropped in -- shows the graceful k = 1 degradation of the matchgate method."""
    c = tfim_trotter(n, depth)
    c.append(Gate("CCX", (n // 2 - 1, n // 2, n // 2 + 1)))
    return c


def clifford_circuit(n, depth):
    """Deeply entangling but purely Clifford (H + CNOT + CZ): t = 0, so the
    stabilizer simulator is polynomial -- even though it is hopeless for the
    matchgate method (H and CNOT are not free-fermion)."""
    c = []
    for layer in range(depth):
        for q in range(n):
            c.append(Gate("H", (q,)))
        for (a, b) in _brickwork_pairs(n, layer):
            c.append(Gate("CNOT", (a, b)))
    return c


def clifford_plus_t(n, depth, num_t):
    """A Clifford circuit with a HANDFUL of T-gates -- still cheap for the
    stabilizer simulator, since its cost grows only as 2^(0.23 t)."""
    c = clifford_circuit(n, depth)
    for j in range(num_t):
        c.append(Gate("T", (j % n,)))
    return c


def shallow_generic(n, depth=2):
    """A SHALLOW circuit of generic two-qubit gates: not matchgates, not Clifford,
    so both t and k are large -- but it is too shallow to build much entanglement,
    so the tensor network wins."""
    c = []
    for layer in range(depth):
        for (a, b) in _brickwork_pairs(n, layer):
            c.append(Gate("U2", (a, b)))
    return c


def dense_random(n, depth):
    """A DEEP circuit of generic gates on far-apart pairs (effectively all-to-all):
    high T-count, high non-matchgate count, AND volume-law entanglement. No axis
    applies -- the genuinely-quantum regime."""
    import random
    rng = random.Random(0)
    c = []
    for _ in range(depth):
        qs = list(range(n))
        rng.shuffle(qs)
        for i in range(0, n - 1, 2):
            c.append(Gate("U2", (qs[i], qs[i + 1])))
    return c


def main():
    print(__doc__)
    print("=" * 74)
    print("Routing six circuits to their cheapest classical simulator")
    print("=" * 74)

    results = []
    results.append(("free-fermion dynamics (TFIM Trotter)",
                    route("free-fermion dynamics (TFIM Trotter)", tfim_trotter(40, 40), 40)))
    results.append(("free-fermion + 1 interacting gate",
                    route("free-fermion + 1 interacting gate",
                          tfim_trotter_plus_one_toffoli(40, 40), 40)))
    results.append(("Clifford circuit (no T-gates)",
                    route("Clifford circuit (no T-gates)", clifford_circuit(40, 40), 40)))
    results.append(("Clifford + 5 T-gates",
                    route("Clifford + 5 T-gates", clifford_plus_t(40, 40, 5), 40)))
    results.append(("shallow generic circuit",
                    route("shallow generic circuit", shallow_generic(40, 2), 40)))
    results.append(("deep dense random circuit",
                    route("deep dense random circuit", dense_random(26, 26), 26)))

    print("=" * 74)
    print("Summary -- same question, six different answers:")
    print("=" * 74)
    for name, winner in results:
        print(f"  {name:<40} -> {winner}")
    print("\n  The point: there is no single best classical simulator. Each circuit")
    print("  is 'easy' along a DIFFERENT axis, and matching the method to the axis")
    print("  is the whole game. The free-fermion axis -- the one this repo builds")
    print("  on -- is exact, indifferent to entanglement, and wins precisely when a")
    print("  circuit is non-interacting (k = 0), however non-Clifford or entangled.")


if __name__ == "__main__":
    main()
