r"""The hybrid dispatcher: split a problem across simulators, pay only for the cut.

This is the sequel to `../simulator-router/`. The router answers "which single
simulator is cheapest for this whole circuit?" The natural next step -- the one
that README flags as future work -- is to stop choosing one simulator and instead
**split the problem**: cut the circuit into pieces, simulate each piece with
whatever method is cheap for it, and pay an exponential price only in the small
"hard part" that connects the pieces.

This file implements the cleanest, exactly-verifiable version of that idea:
**circuit cutting** (a.k.a. circuit knitting / the Schrodinger-Feynman method,
the technique Google used to verify its Sycamore circuits classically).

The idea in one line
--------------------
Partition the qubits into two blocks A and B. Most gates act inside one block;
only a few gates cross between them. Each crossing two-qubit gate can be written
as a short sum of *products* of one-qubit operators (its operator Schmidt
decomposition), G = sum_alpha L_alpha (x) R_alpha, with at most 4 terms (and only
2 for a CNOT). Substituting those sums and expanding, the whole circuit becomes a
sum over "branches", and in EVERY branch the gates factorise cleanly into an
A-only sub-circuit and a B-only sub-circuit. So

    |psi_full>  =  sum over branches of   |psi_A^branch> (x) |psi_B^branch> ,

an EXACT identity. Each block has only n/2 qubits, so each branch costs
~ 2 * 2^(n/2) instead of 2^n, and the number of branches is the product of the
crossing gates' Schmidt ranks -- i.e. you pay only in the *cut*, never in the
bulk. When the cut is narrow this is a large, exact saving.

What this script does
---------------------
1. Builds a circuit on n qubits that is mostly local to two halves, with a few
   gates crossing the middle.
2. Simulates it the brute-force way (one 2^n state vector) to get the ground truth.
3. Simulates it by cutting: decompose the crossing gates, enumerate branches,
   simulate each n/2-qubit block, and recombine.
4. VERIFIES the recombined state equals the brute-force state to machine precision,
   and reports the cost actually paid (branches x block-cost) versus 2^n -- at the
   verified size and, via the same formula, at a large size where brute force is
   impossible.

Honest scope
------------
Circuit cutting is exact and completely general, but its cost is multiplicative in
the number of crossing gates (branches = product of their Schmidt ranks, up to
4^m for m crossing gates). It wins precisely when the cut is narrow -- exactly the
regime the router's entanglement meter `w` detects. Here each block is simulated
with a plain state vector so the result can be checked exactly; in a full
dispatcher each block would itself be routed to its cheapest member (free fermion,
stabilizer, ...), which is the remaining open piece.

Run:  python hybrid_dispatcher.py
"""
import itertools
import math

import numpy as np


# --- a minimal, correct state-vector backend (used for every block) ----------
# Convention: qubit 0 is the most significant bit, so the amplitude of basis
# state |b_0 b_1 ... b_{m-1}> sits at index sum_i b_i * 2^(m-1-i). With this
# convention, kron(state_A, state_B) places the A qubits before the B qubits --
# exactly the contiguous A | B split we cut along.
def zero_state(m):
    psi = np.zeros((2,) * m, dtype=complex)
    psi[(0,) * m] = 1.0
    return psi


def apply_1q(psi, U, q):
    """Apply a 2x2 gate U to qubit q of an m-qubit state (shape (2,)*m)."""
    psi = np.tensordot(U, psi, axes=([1], [q]))     # new axis 0 = output of q
    return np.moveaxis(psi, 0, q)


def apply_2q(psi, U, q0, q1):
    """Apply a 4x4 gate U to qubits (q0, q1). U acts on the 2-qubit space with
    q0 the first (more significant) factor: U[2*o0+o1, 2*i0+i1]."""
    U4 = U.reshape(2, 2, 2, 2)                       # U4[o0, o1, i0, i1]
    psi = np.tensordot(U4, psi, axes=([2, 3], [q0, q1]))   # new axes 0,1 = o0,o1
    return np.moveaxis(psi, [0, 1], [q0, q1])


def run_statevector(m, ops):
    """Apply a time-ordered list of ops to |0..0> of m qubits. Each op is
    (U, (q,)) for a 1-qubit gate or (U, (q0, q1)) for a 2-qubit gate."""
    psi = zero_state(m)
    for U, qs in ops:
        psi = apply_1q(psi, U, qs[0]) if len(qs) == 1 else apply_2q(psi, U, qs[0], qs[1])
    return psi.reshape(-1)


# --- gate library ------------------------------------------------------------
H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
S = np.array([[1, 0], [0, 1j]], dtype=complex)
T = np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)


def rz(theta):
    return np.array([[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]], dtype=complex)


CNOT = np.array([[1, 0, 0, 0],
                 [0, 1, 0, 0],
                 [0, 0, 0, 1],
                 [0, 0, 1, 0]], dtype=complex)
CZ = np.diag([1, 1, 1, -1]).astype(complex)


# --- operator Schmidt decomposition (the heart of the cut) -------------------
def operator_schmidt(U, tol=1e-12):
    """Decompose a 4x4 two-qubit gate U into a short sum of one-qubit factors:

        U[2*o0+o1, 2*i0+i1] = sum_alpha  L_alpha[o0, i0] * R_alpha[o1, i1].

    Returns a list of (L_alpha, R_alpha) 2x2 matrices (singular values folded
    into L_alpha). The length is the gate's operator Schmidt rank (1 for a product
    gate, 2 for CNOT/CZ, up to 4 in general)."""
    # Reshape U into W[(o0,i0), (o1,i1)] and take its SVD; each singular vector
    # reshapes back into a 2x2 one-qubit operator.
    W = np.zeros((4, 4), dtype=complex)
    for o0 in range(2):
        for i0 in range(2):
            for o1 in range(2):
                for i1 in range(2):
                    W[2 * o0 + i0, 2 * o1 + i1] = U[2 * o0 + o1, 2 * i0 + i1]
    Uu, s, Vh = np.linalg.svd(W)
    terms = []
    for alpha in range(4):
        if s[alpha] <= tol:
            continue
        L = (s[alpha] * Uu[:, alpha]).reshape(2, 2)    # indices (o0, i0)
        R = Vh[alpha, :].reshape(2, 2)                 # indices (o1, i1)
        terms.append((L, R))
    # self-check: the decomposition must rebuild U exactly
    rebuilt = sum(np.kron(L, R) for (L, R) in terms)
    assert np.allclose(rebuilt, U), "operator Schmidt decomposition failed self-check"
    return terms


# --- the hybrid (cutting) simulator ------------------------------------------
def simulate_by_cutting(n, circuit):
    """Simulate `circuit` on n qubits by cutting it down the middle (block A =
    qubits 0..n/2-1, block B = the rest). Returns (full_state, n_branches,
    n_crossing). Exact."""
    cut = n // 2
    in_A = lambda q: q < cut
    locA = lambda q: q             # local index within block A (qubits 0..cut-1)
    locB = lambda q: q - cut       # local index within block B

    # Sort the circuit's gates into A-only, B-only, and crossing (with their
    # operator Schmidt decompositions), keeping the original time order.
    plan = []          # list of ("A", U, locqs) / ("B", ...) / ("X", terms, aq, bq, a_is_first)
    for U, qs in circuit:
        if len(qs) == 1:
            side = "A" if in_A(qs[0]) else "B"
            loc = (locA(qs[0]),) if side == "A" else (locB(qs[0]),)
            plan.append((side, U, loc))
        else:
            q0, q1 = qs
            if in_A(q0) and in_A(q1):
                plan.append(("A", U, (locA(q0), locA(q1))))
            elif (not in_A(q0)) and (not in_A(q1)):
                plan.append(("B", U, (locB(q0), locB(q1))))
            else:
                # crossing gate: L acts on q0, R on q1 (the Schmidt convention).
                terms = operator_schmidt(U)
                aq, bq = (q0, q1) if in_A(q0) else (q1, q0)
                a_is_first = in_A(q0)   # is the L-factor's qubit the one in A?
                plan.append(("X", terms, aq, bq, a_is_first))

    crossing = [p for p in plan if p[0] == "X"]
    ranks = [len(p[1]) for p in crossing]
    n_branches = int(np.prod(ranks)) if ranks else 1

    dimA, dimB = 2 ** cut, 2 ** (n - cut)
    full = np.zeros(dimA * dimB, dtype=complex)

    # Enumerate branches = one Schmidt-term choice per crossing gate.
    for choice in itertools.product(*[range(r) for r in ranks]) if ranks else [()]:
        opsA, opsB = [], []
        ci = 0
        for p in plan:
            if p[0] == "A":
                opsA.append((p[1], p[2]))
            elif p[0] == "B":
                opsB.append((p[1], p[2]))
            else:  # crossing: route the chosen branch's two one-qubit factors
                terms, aq, bq, a_is_first = p[1], p[2], p[3], p[4]
                L, R = terms[choice[ci]]
                a_factor, b_factor = (L, R) if a_is_first else (R, L)
                opsA.append((a_factor, (locA(aq),)))
                opsB.append((b_factor, (locB(bq),)))
                ci += 1
        stateA = run_statevector(cut, opsA)
        stateB = run_statevector(n - cut, opsB)
        full += np.kron(stateA, stateB)
    return full, n_branches, len(crossing)


# --- a demonstration circuit -------------------------------------------------
def demo_circuit(n, crossing_pairs, seed=0):
    """A circuit that is mostly local to the two halves of n qubits, plus a few
    `crossing_pairs` two-qubit gates spanning the middle. Reproducible."""
    rng = np.random.default_rng(seed)
    cut = n // 2
    c = []
    # rich local structure in each block: H/T plus nearest-neighbour CNOTs
    for q in range(n):
        c.append((H, (q,)))
        c.append((rz(rng.uniform(0, 2 * math.pi)), (q,)))
    for q in range(cut - 1):                      # entangle within block A
        c.append((CNOT, (q, q + 1)))
    for q in range(cut, n - 1):                   # entangle within block B
        c.append((CNOT, (q, q + 1)))
    for q in range(n):
        c.append((T, (q,)))
    for (a, b) in crossing_pairs:                 # the few gates across the cut
        c.append((CNOT, (a, b)))
    return c


def report(n, crossing_pairs, seed=0):
    circuit = demo_circuit(n, crossing_pairs, seed)
    truth = run_statevector(n, circuit)                       # brute force, 2^n
    hybrid, n_branches, m = simulate_by_cutting(n, circuit)   # cut down the middle
    ok = np.allclose(hybrid, truth, atol=1e-10)

    cut = n // 2
    brute_cost = 2 ** n
    hybrid_cost = n_branches * (2 ** cut + 2 ** (n - cut))
    print("-" * 74)
    print(f"  n = {n} qubits  |  {m} gate(s) crossing the cut  |  {n_branches} branches")
    print(f"  exact match with brute force: {ok}")
    print(f"  cost paid:  brute force ~ 2^{n} = {brute_cost:,}")
    print(f"              cutting     ~ {n_branches} x 2 x 2^{cut} "
          f"= {hybrid_cost:,}   ({brute_cost / hybrid_cost:.1f}x less)")
    assert ok, "hybrid result did not match brute force!"
    return n_branches


def main():
    print(__doc__)
    print("=" * 74)
    print("Exact verification: cutting reproduces brute force, paying only for the cut")
    print("=" * 74)

    # Same circuit size, increasing the width of the cut: the bulk cost is fixed,
    # and the price grows only with the number of crossing gates.
    report(10, crossing_pairs=[(4, 5)])
    report(10, crossing_pairs=[(4, 5), (3, 6)])
    report(10, crossing_pairs=[(4, 5), (3, 6), (4, 6)])

    print("=" * 74)
    print("What this buys at a scale brute force cannot reach (same cost formula)")
    print("=" * 74)
    for n, m in [(40, 2), (40, 3), (80, 3)]:
        cut = n // 2
        branches = 2 ** m                       # CNOT-like cuts: Schmidt rank 2 each
        hybrid_cost = branches * 2 * 2 ** cut
        print(f"  n = {n}, {m} crossing gates: brute force 2^{n} ~ 10^{n*math.log10(2):.0f}, "
              f"cutting ~ {hybrid_cost:,.0f}  (~10^{math.log10(hybrid_cost):.0f}) -- and EXACT")
    print("\n  The bulk is free; you pay only for the cut. This is the dispatcher")
    print("  'splitting a problem across members' -- here verified exactly. Routing")
    print("  each block to its own cheapest simulator is the remaining open piece.")


if __name__ == "__main__":
    main()
