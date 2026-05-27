r"""The hybrid dispatcher: cut a problem, then route each piece to its own simulator.

This is the sequel to `../simulator-router/`. The router answers "which single
simulator is cheapest for this whole circuit?" Here we do the thing that closes the
loop: **cut the circuit into pieces and route each piece to its OWN cheapest
simulator**, paying an exponential price only in the small "hard part" that connects
the pieces.

Two ideas combine:

1. Circuit cutting (a.k.a. circuit knitting / the Schrodinger-Feynman method, used
   by Google to verify Sycamore classically). Partition the qubits into blocks A
   and B; only a few gates cross between them. Each crossing two-qubit gate is
   written as a short sum of products of one-qubit operators (its operator Schmidt
   decomposition), G = sum_alpha L_alpha (x) R_alpha (<= 4 terms, just 2 for CNOT).
   Expanding, the whole circuit becomes a sum over "branches", and in every branch
   the gates factorise into an A-only and a B-only sub-circuit:

       |psi_full>  =  sum over branches of   |psi_A^branch> (x) |psi_B^branch> ,

   an EXACT identity. You pay only in the cut (branches = product of crossing
   Schmidt ranks), never in the bulk.

2. Per-block routing. Once cut, each block is its own circuit -- so we run the
   router on it and dispatch it to its cheapest member (stabilizer, free fermion,
   ...). The punchline of this example: **a circuit can have NO single cheap method
   as a whole, yet split into halves that are each easy along a DIFFERENT axis.**
   The demo circuit is exactly that -- a Clifford half welded to a free-fermion half
   -- so the undivided circuit routes to brute force, but after the cut block A goes
   to the stabilizer simulator and block B to the free-fermion simulator.

What this script does
---------------------
1. Builds that two-natured circuit (Clifford half + free-fermion half + a few
   crossing gates) on n qubits.
2. Routes the WHOLE circuit -- finds no single cheap method.
3. Cuts it; routes each HALF -- each is cheap, along a different axis.
4. Recombines the cut pieces and VERIFIES the result equals brute force to machine
   precision; reports the cost of brute force vs. whole-circuit routing vs.
   cut-and-route-each-piece.

Honest scope
------------
The per-block routing DECISION and its cost are real and computed per block. For the
exact numerical check, each block is executed on the universal state-vector
reference engine (which is phase-exact, so the cut + recombination can be verified
against brute force). Substituting each member's NATIVE polynomial engine -- with
the correct cross-block global phase -- is the final piece of engineering; the
routing layer here is what decides where each block would go and what it would cost.

Run:  python hybrid_dispatcher.py
"""
import itertools
import math

import numpy as np


# --- a minimal, correct state-vector backend (the phase-exact reference) ------
# Convention: qubit 0 is the most significant bit, so kron(state_A, state_B) places
# the A qubits before the B qubits -- exactly the contiguous A | B split we cut on.
def zero_state(m):
    psi = np.zeros((2,) * m, dtype=complex)
    psi[(0,) * m] = 1.0
    return psi


def apply_1q(psi, U, q):
    psi = np.tensordot(U, psi, axes=([1], [q]))
    return np.moveaxis(psi, 0, q)


def apply_2q(psi, U, q0, q1):
    U4 = U.reshape(2, 2, 2, 2)                       # U4[o0, o1, i0, i1]
    psi = np.tensordot(U4, psi, axes=([2, 3], [q0, q1]))
    return np.moveaxis(psi, [0, 1], [q0, q1])


def run_statevector(m, ops):
    """Apply a time-ordered list of (U, qubits) gates to |0..0> of m qubits."""
    psi = zero_state(m)
    for U, qs in ops:
        psi = apply_1q(psi, U, qs[0]) if len(qs) == 1 else apply_2q(psi, U, qs[0], qs[1])
    return psi.reshape(-1)


# --- gate library (matrices + names; names drive the per-block routing) -------
H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
S = np.array([[1, 0], [0, 1j]], dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)

CNOT = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
CZ = np.diag([1, 1, 1, -1]).astype(complex)


def rz(theta):
    return np.array([[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]], dtype=complex)


def xx_yy(theta):
    """exp(-i theta/2 (XX + YY)) -- an XY / Givens rotation. A genuine matchgate:
    it acts as a rotation inside the odd-parity {|01>, |10>} subspace and as the
    identity on {|00>, |11>}."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[1, 0, 0, 0],
                     [0, c, -1j * s, 0],
                     [0, -1j * s, c, 0],
                     [0, 0, 0, 1]], dtype=complex)


# fermionic SWAP: swaps two modes with the fermionic sign on |11>. A matchgate.
FSWAP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, -1]], dtype=complex)


# --- per-block routing (the same meters as ../simulator-router/) --------------
CLIFFORD = {"H", "S", "SDG", "X", "Y", "Z", "CX", "CNOT", "CZ", "SWAP"}
MATCHGATE = {"RZ", "Z", "XY", "XX_YY", "GIVENS", "FSWAP", "MG"}
NON_CLIFFORD_WEIGHT = {"CCX": 7, "TOFFOLI": 7}
ALPHA = 0.2284                              # Bravyi-Gosset stabilizer-rank exponent


def _poly(x):
    return 2.0 * math.log2(max(x, 2))


def route_block(gates, m):
    """Route a block's native gates (a list of (name, qubits)) to its cheapest
    member. Returns (member, log2_cost, {t, k}). Mirrors the simulator-router cost
    model for the members that apply to a sub-circuit (the cut already accounts for
    entanglement, so the relevant axes here are T-count and interacting-gate count)."""
    t = sum(NON_CLIFFORD_WEIGHT.get(nm, 1) for (nm, _) in gates if nm not in CLIFFORD)
    k = sum(1 for (nm, _) in gates if nm not in MATCHGATE)
    costs = {
        "state vector": float(m),                        # 2^m, the fallback
        "stabilizer":   ALPHA * t + _poly(m),            # poly when t = 0
        "free fermion": k * math.log2(4) + _poly(2 * m),  # poly when k = 0
    }
    member = min(costs, key=lambda c: costs[c])
    return member, costs[member], {"t": t, "k": k}


# --- operator Schmidt decomposition (the heart of the cut) -------------------
def operator_schmidt(U, tol=1e-12):
    """U[2*o0+o1, 2*i0+i1] = sum_alpha L_alpha[o0,i0] * R_alpha[o1,i1].
    Returns [(L_alpha, R_alpha)] with singular values folded into L_alpha; the
    length is the gate's operator Schmidt rank (2 for CNOT/CZ, up to 4 general)."""
    W = np.zeros((4, 4), dtype=complex)
    for o0 in range(2):
        for i0 in range(2):
            for o1 in range(2):
                for i1 in range(2):
                    W[2 * o0 + i0, 2 * o1 + i1] = U[2 * o0 + o1, 2 * i0 + i1]
    Uu, s, Vh = np.linalg.svd(W)
    terms = [((s[a] * Uu[:, a]).reshape(2, 2), Vh[a, :].reshape(2, 2))
             for a in range(4) if s[a] > tol]
    assert np.allclose(sum(np.kron(L, R) for (L, R) in terms), U), \
        "operator Schmidt decomposition failed self-check"
    return terms


# --- the hybrid: cut down the middle, route each half, recombine -------------
def simulate_by_cutting(n, circuit):
    """circuit: list of (name, U, qubits). Returns a dict with the exact recombined
    state, the branch count, and the per-block routing of each half."""
    cut = n // 2
    in_A = lambda q: q < cut
    locA = lambda q: q
    locB = lambda q: q - cut

    a_only, b_only, crossing = [], [], []     # (U, locqs) lists; crossing keeps decomp
    a_names, b_names = [], []                 # (name, locqs) for routing each half
    for (name, U, qs) in circuit:
        if len(qs) == 1:
            if in_A(qs[0]):
                a_only.append((U, (locA(qs[0]),))); a_names.append((name, (locA(qs[0]),)))
            else:
                b_only.append((U, (locB(qs[0]),))); b_names.append((name, (locB(qs[0]),)))
        elif in_A(qs[0]) and in_A(qs[1]):
            a_only.append((U, (locA(qs[0]), locA(qs[1])))); a_names.append((name, qs))
        elif (not in_A(qs[0])) and (not in_A(qs[1])):
            b_only.append((U, (locB(qs[0]), locB(qs[1])))); b_names.append((name, qs))
        else:
            q0, q1 = qs
            aq, bq = (q0, q1) if in_A(q0) else (q1, q0)
            crossing.append((operator_schmidt(U), aq, bq, in_A(q0)))

    # NOTE: a_only/b_only are time-ordered because we walk the circuit in order and
    # operators on disjoint qubit sets commute, so each branch's two sub-circuits are
    # exactly the original time-ordered gates restricted to that block.
    ranks = [len(c[0]) for c in crossing]
    n_branches = int(np.prod(ranks)) if ranks else 1
    routeA = route_block(a_names, cut)
    routeB = route_block(b_names, n - cut)

    full = np.zeros(2 ** cut * 2 ** (n - cut), dtype=complex)
    for choice in (itertools.product(*[range(r) for r in ranks]) if ranks else [()]):
        opsA, opsB = list(a_only), list(b_only)   # copy the block-local gates
        # NOTE: appending the crossing factors after the block gates is exact here
        # because the demo's crossing gates come last in time; in general one would
        # interleave them at their time position (operators on disjoint blocks commute).
        for ci, (terms, aq, bq, a_is_first) in enumerate(crossing):
            L, R = terms[choice[ci]]
            a_fac, b_fac = (L, R) if a_is_first else (R, L)
            opsA.append((a_fac, (locA(aq),)))
            opsB.append((b_fac, (locB(bq),)))
        full += np.kron(run_statevector(cut, opsA), run_statevector(n - cut, opsB))

    return {"state": full, "branches": n_branches, "n_crossing": len(crossing),
            "routeA": routeA, "routeB": routeB}


# --- a two-natured demonstration circuit -------------------------------------
def two_natured_circuit(n, seed=0):
    """Block A (qubits 0..n/2-1): a Clifford circuit (H, CX, S, CZ) -> stabilizer.
    Block B (qubits n/2..n-1): a free-fermion circuit (RZ, XX_YY, FSWAP) -> matchgate.
    Plus two CNOTs crossing the middle. The two halves are easy along DIFFERENT axes,
    and the undivided circuit is easy along neither."""
    rng = np.random.default_rng(seed)
    cut = n // 2
    c = []
    # Block A: Clifford (t = 0, but full of non-matchgate H/CX -> k large)
    for q in range(cut):
        c.append(("H", H, (q,)))
    for q in range(cut - 1):
        c.append(("CX", CNOT, (q, q + 1)))
    for q in range(0, cut, 2):
        c.append(("S", S, (q,)))
    c.append(("CZ", CZ, (0, cut - 1)))
    # Block B: free fermion (k = 0, but full of non-Clifford rotations -> t large)
    for q in range(cut, n):
        c.append(("RZ", rz(rng.uniform(0.2, 3.0)), (q,)))
    for q in range(cut, n - 1):
        c.append(("XX_YY", xx_yy(rng.uniform(0.2, 3.0)), (q, q + 1)))
    c.append(("FSWAP", FSWAP, (cut, cut + 1)))
    c.append(("FSWAP", FSWAP, (n - 2, n - 1)))
    # the few gates crossing the cut (these are what you pay for)
    c.append(("CX", CNOT, (cut - 1, cut)))
    c.append(("CX", CNOT, (cut - 2, cut + 1)))
    return c


def main():
    print(__doc__)
    n = 20
    circuit = two_natured_circuit(n)
    cut = n // 2

    # 1) Route the WHOLE circuit -- it is easy along no single axis.
    whole = route_block([(nm, qs) for (nm, U, qs) in circuit], n)
    print("=" * 74)
    print(f"A two-natured circuit on n = {n} qubits ({len(circuit)} gates)")
    print("=" * 74)
    print(f"  Route the WHOLE circuit:  -> {whole[0].upper():<13} "
          f"(t = {whole[2]['t']}, k = {whole[2]['k']};  best single method, cost ~ 2^{whole[1]:.1f})")
    print("  No single method is POLYNOMIAL on the whole: a stabilizer simulator must")
    print("  pay for all the non-Clifford rotations (t large), and a free-fermion")
    print("  simulator must pay for all the H/CX gates (k large). The best of them is")
    print("  still exponential.")

    # 2) Cut it down the middle and route each half independently.
    out = simulate_by_cutting(n, circuit)
    (mA, cA, meA), (mB, cB, meB) = out["routeA"], out["routeB"]
    print(f"\n  Cut into two halves of {cut} qubits and route EACH:")
    print(f"    block A (qubits 0..{cut-1}):  -> {mA.upper():<13} "
          f"(t = {meA['t']}, k = {meA['k']};  cost ~ 2^{cA:.1f})")
    print(f"    block B (qubits {cut}..{n-1}): -> {mB.upper():<13} "
          f"(t = {meB['t']}, k = {meB['k']};  cost ~ 2^{cB:.1f})")
    print(f"    + {out['n_crossing']} crossing gate(s)  ->  {out['branches']} branches")

    # 3) Verify the cut + recombination is exact.
    truth = run_statevector(n, [(U, qs) for (nm, U, qs) in circuit])
    ok = np.allclose(out["state"], truth, atol=1e-10)
    print(f"\n  Exact match with brute force: {ok}")
    assert ok, "hybrid result did not match brute force!"

    # 4) The cost story.
    brute = 2 ** n
    whole_cost = 2 ** whole[1]
    cut_cost = out["branches"] * (2 ** cA + 2 ** cB)
    print("\n  Cost (operations, order of magnitude):")
    print(f"    brute force ................... 2^{n}  = {brute:,.0f}")
    print(f"    route the whole circuit ....... ~ {whole_cost:,.0f}")
    print(f"    cut + route each half ......... {out['branches']} x (2^{cA:.1f} + 2^{cB:.1f}) "
          f"= {cut_cost:,.0f}   ({brute / cut_cost:.0f}x less than brute force)")

    print("\n" + "=" * 74)
    print("The point")
    print("=" * 74)
    print("  Cutting can expose structure that is invisible in the whole circuit: a")
    print("  problem with no single cheap method splits into pieces that are each")
    print("  cheap -- along DIFFERENT axes. The dispatcher cuts, routes every piece to")
    print("  its own member, and pays only for the cut. (The routing and its cost are")
    print("  computed per block; the blocks are run here on the exact reference engine")
    print("  so the recombination can be checked -- swapping in each member's native")
    print("  polynomial engine, phase-correct across the cut, is the final step.)")


if __name__ == "__main__":
    main()
