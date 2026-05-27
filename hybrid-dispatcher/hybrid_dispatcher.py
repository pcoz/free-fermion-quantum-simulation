r"""The hybrid dispatcher: cut a problem, then route each piece to its own simulator.

This is the sequel to `../simulator-router/`. The router answers "which single
simulator is cheapest for this whole circuit?" Here we close the loop: **cut the
circuit into pieces and route each piece to its OWN cheapest simulator**, paying an
exponential price only in the small "hard part" that connects the pieces -- and we
actually run one half on a real stabilizer engine.

Two ideas combine:

1. Circuit cutting (a.k.a. circuit knitting / the Schrodinger-Feynman method, what
   Google used to verify Sycamore classically). Split the qubits into halves A and
   B; only a few gates cross between them. We expand each crossing two-qubit gate in
   the **Pauli basis**, G = sum_{P,Q} c_{PQ} P (x) Q. Substituting and expanding, the
   whole circuit becomes a sum over "branches", and in every branch the gates split
   cleanly into an A-only and a B-only circuit:

       |psi_full>  =  sum over branches of   coeff * |psi_A^branch> (x) |psi_B^branch> ,

   an EXACT identity. The Pauli basis is chosen on purpose: the factor injected into
   each block is a Pauli, so block A stays a *Clifford* circuit (a stabilizer
   simulator can run it) and block B stays a matchgate-plus-Pauli circuit. You pay
   only in the cut; the price of the Pauli basis is a few more branches (4 per CNOT).

2. Per-block routing + a real per-block engine. Once cut, each half is its own
   circuit, so we route it to its cheapest member -- and here block A is actually
   executed by a phase-aware stabilizer engine, not the universal one.

The punchline: a circuit can have **no single cheap method as a whole**, yet split
into halves that are each easy along a **different axis**. The demo is exactly that
-- a Clifford half welded to a free-fermion half.

Why the stabilizer engine has to be phase-aware
-----------------------------------------------
The recombination sums |psi_A> (x) |psi_B> over branches, so each block state must
carry its correct GLOBAL phase -- otherwise the branches interfere wrongly. A bare
stabilizer tableau is poly-time but fixes the state only up to a global phase, which
is exactly the information the cut needs. So block A is run with a stabilizer engine
in the explicit-superposition representation: it keeps the state as its (sparse)
amplitudes over the affine stabilizer support, which is phase-exact and compresses
to 2^(support) entries -- a genuine saving for low-Hadamard Clifford blocks (the demo
block A spreads over 2^3, not 2^10). Getting poly-always AND phase-exact is the
CH-form; this representation is the phase-exact, easy-to-verify version of it.

Run:  python hybrid_dispatcher.py
"""
import itertools
import math
from collections import defaultdict

import numpy as np


# --- a minimal, correct state-vector backend (brute force + block B) ----------
# Convention: qubit 0 is the most significant bit, so kron(state_A, state_B) places
# the A qubits before the B qubits -- exactly the contiguous A | B split we cut on.
def apply_1q(psi, U, q):
    return np.moveaxis(np.tensordot(U, psi, axes=([1], [q])), 0, q)


def apply_2q(psi, U, q0, q1):
    U4 = U.reshape(2, 2, 2, 2)
    return np.moveaxis(np.tensordot(U4, psi, axes=([2, 3], [q0, q1])), [0, 1], [q0, q1])


def run_statevector(m, ops):
    """Apply a time-ordered list of (U, qubits) gates to |0..0> of m qubits."""
    psi = np.zeros((2,) * m, dtype=complex)
    psi[(0,) * m] = 1.0
    for U, qs in ops:
        psi = apply_1q(psi, U, qs[0]) if len(qs) == 1 else apply_2q(psi, U, qs[0], qs[1])
    return psi.reshape(-1)


# --- gate library (matrices + names; names drive routing and the stabilizer engine)
H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
S = np.array([[1, 0], [0, 1j]], dtype=complex)
I2 = np.eye(2, dtype=complex)
PX = np.array([[0, 1], [1, 0]], dtype=complex)
PY = np.array([[0, -1j], [1j, 0]], dtype=complex)
PZ = np.array([[1, 0], [0, -1]], dtype=complex)
PAULI = {"I": I2, "X": PX, "Y": PY, "Z": PZ}

CNOT = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
CZ = np.diag([1, 1, 1, -1]).astype(complex)


def rz(theta):
    return np.array([[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]], dtype=complex)


def xx_yy(theta):
    """exp(-i theta/2 (XX + YY)) -- an XY / Givens rotation; a genuine matchgate."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[1, 0, 0, 0], [0, c, -1j * s, 0], [0, -1j * s, c, 0], [0, 0, 0, 1]], dtype=complex)


FSWAP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, -1]], dtype=complex)


# --- a phase-aware stabilizer engine (explicit-superposition representation) ---
class StabilizerSim:
    """Phase-EXACT Clifford simulator. The state is held as its sparse amplitudes
    over the affine stabilizer support: a dict {basis state -> amplitude}. For a
    Clifford circuit this support is an affine subspace of size 2^support_dim, with
    all amplitudes of equal magnitude and phases in {+-1, +-i} -- i.e. a genuine
    stabilizer state. Applying the actual gate actions keeps the GLOBAL phase exact
    (which a bare tableau would lose), so the result plugs straight into the cut.

    Bit convention matches the rest of the file: qubit q is bit (m-1-q) of the key."""

    def __init__(self, m):
        self.m = m
        self.amp = {0: 1.0 + 0j}          # |0...0>

    def _mask(self, q):
        return 1 << (self.m - 1 - q)

    def _bit(self, x, q):
        return (x >> (self.m - 1 - q)) & 1

    def z(self, q):
        for x in self.amp:
            if self._bit(x, q):
                self.amp[x] = -self.amp[x]

    def s(self, q):
        for x in self.amp:
            if self._bit(x, q):
                self.amp[x] *= 1j

    def x(self, q):
        mask = self._mask(q)
        self.amp = {x ^ mask: a for x, a in self.amp.items()}

    def y(self, q):
        mask = self._mask(q)
        self.amp = {x ^ mask: (1j * (-1) ** self._bit(x, q)) * a for x, a in self.amp.items()}

    def cx(self, c, t):
        cm, tm = self._mask(c), self._mask(t)
        self.amp = {(x ^ tm if x & cm else x): a for x, a in self.amp.items()}

    def cz(self, a, b):
        for x in self.amp:
            if self._bit(x, a) and self._bit(x, b):
                self.amp[x] = -self.amp[x]

    def h(self, q):
        mask = self._mask(q)
        inv = 1.0 / math.sqrt(2)
        new = defaultdict(complex)
        for x, a in self.amp.items():
            sign = -1 if (x & mask) else 1
            new[x & ~mask] += a * inv             # branch with bit q = 0
            new[x | mask] += a * inv * sign       # branch with bit q = 1 (phase (-1)^x_q)
        self.amp = {x: a for x, a in new.items() if abs(a) > 1e-12}

    def apply(self, name, qs):
        if name == "I":
            return
        {"H": lambda: self.h(qs[0]), "S": lambda: self.s(qs[0]),
         "X": lambda: self.x(qs[0]), "Y": lambda: self.y(qs[0]), "Z": lambda: self.z(qs[0]),
         "CX": lambda: self.cx(qs[0], qs[1]), "CNOT": lambda: self.cx(qs[0], qs[1]),
         "CZ": lambda: self.cz(qs[0], qs[1])}[name]()

    def statevector(self):
        psi = np.zeros(2 ** self.m, dtype=complex)
        for x, a in self.amp.items():
            psi[x] = a
        return psi

    @property
    def support(self):
        return len(self.amp)


def run_stabilizer(m, named_ops):
    """Run a Clifford circuit (list of (name, qubits)) on the stabilizer engine and
    return (statevector, support_size)."""
    sim = StabilizerSim(m)
    for name, qs in named_ops:
        sim.apply(name, qs)
    return sim.statevector(), sim.support


# --- per-block routing (the same meters as ../simulator-router/) --------------
CLIFFORD = {"H", "S", "SDG", "X", "Y", "Z", "CX", "CNOT", "CZ", "SWAP"}
MATCHGATE = {"RZ", "Z", "XY", "XX_YY", "GIVENS", "FSWAP", "MG"}
ALPHA = 0.2284


def _poly(x):
    return 2.0 * math.log2(max(x, 2))


def route_block(gates, m):
    """Route a block's native gates (list of (name, qubits)) to its cheapest member."""
    t = sum(1 for (nm, _) in gates if nm not in CLIFFORD)
    k = sum(1 for (nm, _) in gates if nm not in MATCHGATE)
    costs = {"state vector": float(m),
             "stabilizer": ALPHA * t + _poly(m),
             "free fermion": k * math.log2(4) + _poly(2 * m)}
    member = min(costs, key=lambda c: costs[c])
    return member, costs[member], {"t": t, "k": k}


# --- Pauli-basis decomposition of a crossing gate ----------------------------
def pauli_decomposition(U, tol=1e-12):
    """Write a 4x4 gate as U = sum_{P,Q} c_{PQ} P (x) Q with P, Q Paulis.
    Returns [(coeff, P_name, Q_name)]; P acts on the gate's first qubit, Q the
    second. Keeping the factors Paulis is what lets block A stay Clifford."""
    terms = []
    for pn, P in PAULI.items():
        for qn, Q in PAULI.items():
            c = np.trace(np.kron(P, Q).conj().T @ U) / 4.0
            if abs(c) > tol:
                terms.append((c, pn, qn))
    assert np.allclose(sum(c * np.kron(PAULI[pn], PAULI[qn]) for (c, pn, qn) in terms), U)
    return terms


# --- the hybrid: cut, route each half, run A on the stabilizer engine ---------
def simulate_by_cutting(n, circuit):
    cut = n // 2
    in_A = lambda q: q < cut
    locA, locB = (lambda q: q), (lambda q: q - cut)

    aOps, bOps = [], []          # block A: (name, locqs);  block B: (U, locqs)
    aNames, bNames = [], []      # native gate names for routing each half
    crossing = []                # (terms, aq_local, bq_local, a_is_first)
    for (name, U, qs) in circuit:
        if len(qs) == 1:
            if in_A(qs[0]):
                aOps.append((name, (locA(qs[0]),))); aNames.append((name, qs))
            else:
                bOps.append((U, (locB(qs[0]),))); bNames.append((name, qs))
        elif in_A(qs[0]) and in_A(qs[1]):
            aOps.append((name, (locA(qs[0]), locA(qs[1])))); aNames.append((name, qs))
        elif (not in_A(qs[0])) and (not in_A(qs[1])):
            bOps.append((U, (locB(qs[0]), locB(qs[1])))); bNames.append((name, qs))
        else:
            q0, q1 = qs
            aq, bq = (q0, q1) if in_A(q0) else (q1, q0)
            crossing.append((pauli_decomposition(U), locA(aq), locB(bq), in_A(q0)))

    ranks = [len(c[0]) for c in crossing]
    n_branches = int(np.prod(ranks)) if ranks else 1
    routeA, routeB = route_block(aNames, cut), route_block(bNames, n - cut)

    full = np.zeros(2 ** cut * 2 ** (n - cut), dtype=complex)
    supportA_max = 0
    for choice in (itertools.product(*[range(r) for r in ranks]) if ranks else [()]):
        a_named = list(aOps)
        b_mats = list(bOps)
        coeff = 1.0 + 0j
        for ci, (terms, aq, bq, a_is_first) in enumerate(crossing):
            c, pn, qn = terms[choice[ci]]
            coeff *= c
            a_pauli, b_pauli = (pn, qn) if a_is_first else (qn, pn)
            a_named.append((a_pauli, (aq,)))           # Pauli factor -> block A (Clifford)
            b_mats.append((PAULI[b_pauli], (bq,)))     # Pauli factor -> block B
        stateA, supA = run_stabilizer(cut, a_named)    # block A on the STABILIZER engine
        stateB = run_statevector(n - cut, b_mats)      # block B on the universal engine
        supportA_max = max(supportA_max, supA)
        full += coeff * np.kron(stateA, stateB)

    return {"state": full, "branches": n_branches, "n_crossing": len(crossing),
            "routeA": routeA, "routeB": routeB, "supportA": supportA_max}


# --- a two-natured demonstration circuit -------------------------------------
def two_natured_circuit(n, seed=0):
    """Block A (qubits 0..n/2-1): a low-Hadamard Clifford circuit -> stabilizer.
    Block B (qubits n/2..n-1): a free-fermion circuit (RZ, XX_YY, FSWAP) -> matchgate.
    Plus two CNOTs crossing the middle. Easy along different axes; hard as a whole."""
    rng = np.random.default_rng(seed)
    cut = n // 2
    c = []
    # Block A: Clifford, only a few Hadamards (so the stabilizer support stays small)
    for q in (0, 1, 2):
        c.append(("H", H, (q,)))
    for q in range(cut - 1):
        c.append(("CX", CNOT, (q, q + 1)))
    for q in range(0, cut, 3):
        c.append(("S", S, (q,)))
    c.append(("CZ", CZ, (0, cut - 1)))
    # Block B: free fermion (k = 0, but full of non-Clifford rotations -> t large)
    for q in range(cut, n):
        c.append(("RZ", rz(rng.uniform(0.2, 3.0)), (q,)))
    for q in range(cut, n - 1):
        c.append(("XX_YY", xx_yy(rng.uniform(0.2, 3.0)), (q, q + 1)))
    c.append(("FSWAP", FSWAP, (cut, cut + 1)))
    c.append(("FSWAP", FSWAP, (n - 2, n - 1)))
    # the few gates crossing the cut (what you pay for)
    c.append(("CX", CNOT, (cut - 1, cut)))
    c.append(("CX", CNOT, (cut - 2, cut + 1)))
    return c


def self_test():
    """Independently verify the stabilizer engine: on random Clifford circuits its
    statevector must equal the universal engine's EXACTLY, global phase included."""
    rng = np.random.default_rng(1)
    name_to_mat = {"H": H, "S": S, "X": PX, "Y": PY, "Z": PZ, "CX": CNOT, "CZ": CZ}
    for _ in range(200):
        m = rng.integers(2, 6)
        ops_named, ops_mat = [], []
        for _ in range(rng.integers(5, 25)):
            g = rng.choice(["H", "S", "X", "Y", "Z", "CX", "CZ"])
            if g in ("CX", "CZ"):
                a, b = rng.choice(m, size=2, replace=False)
                ops_named.append((g, (int(a), int(b)))); ops_mat.append((name_to_mat[g], (int(a), int(b))))
            else:
                a = int(rng.integers(m))
                ops_named.append((g, (a,))); ops_mat.append((name_to_mat[g], (a,)))
        vec_stab, _ = run_stabilizer(m, ops_named)
        vec_ref = run_statevector(m, ops_mat)
        assert np.allclose(vec_stab, vec_ref, atol=1e-10), "stabilizer engine mismatch!"
        nz = np.abs(vec_stab[np.abs(vec_stab) > 1e-9])
        assert np.allclose(nz, nz[0]), "not a stabilizer state (unequal magnitudes)!"
    print("  [self-test passed: stabilizer engine is phase-exact on 200 random Clifford circuits]")


def main():
    print(__doc__)
    print("=" * 74)
    print("Step 0 -- validate the phase-aware stabilizer engine")
    print("=" * 74)
    self_test()

    n = 20
    circuit = two_natured_circuit(n)
    cut = n // 2

    print("\n" + "=" * 74)
    print(f"A two-natured circuit on n = {n} qubits ({len(circuit)} gates)")
    print("=" * 74)
    whole = route_block([(nm, qs) for (nm, U, qs) in circuit], n)
    print(f"  Route the WHOLE circuit:  -> {whole[0].upper():<13} "
          f"(t = {whole[2]['t']}, k = {whole[2]['k']};  best single method, cost ~ 2^{whole[1]:.1f})")
    print("  No single method is POLYNOMIAL on the whole: a stabilizer simulator must")
    print("  pay for all the non-Clifford rotations (t large), and a free-fermion")
    print("  simulator for all the H/CX gates (k large). The best of them is exponential.")

    out = simulate_by_cutting(n, circuit)
    (mA, cA, meA), (mB, cB, meB) = out["routeA"], out["routeB"]
    print(f"\n  Cut into two halves of {cut} qubits and route EACH:")
    print(f"    block A (qubits 0..{cut-1}):  -> {mA.upper():<13} (t = {meA['t']}, k = {meA['k']})"
          f"  -- RUN on the stabilizer engine, support 2^{int(math.log2(out['supportA']))} "
          f"= {out['supportA']} (not 2^{cut})")
    print(f"    block B (qubits {cut}..{n-1}): -> {mB.upper():<13} (t = {meB['t']}, k = {meB['k']})"
          f"  -- run on the universal engine (native free-fermion engine: future)")
    print(f"    + {out['n_crossing']} crossing gate(s), Pauli-decomposed  ->  {out['branches']} branches")

    truth = run_statevector(n, [(U, qs) for (nm, U, qs) in circuit])
    ok = np.allclose(out["state"], truth, atol=1e-10)
    print(f"\n  Exact match with brute force: {ok}")
    assert ok, "hybrid result did not match brute force!"

    brute, whole_cost = 2 ** n, 2 ** whole[1]
    cut_cost = out["branches"] * (out["supportA"] + 2 ** cB)
    print("\n  Cost (operations, order of magnitude):")
    print(f"    brute force ................... 2^{n} = {brute:,.0f}")
    print(f"    route the whole circuit ....... ~ {whole_cost:,.0f}")
    print(f"    cut + route each half ......... {out['branches']} x (2^{int(math.log2(out['supportA']))} "
          f"+ 2^{cB:.1f}) = {cut_cost:,.0f}   ({brute / cut_cost:.0f}x less than brute force)")

    print("\n" + "=" * 74)
    print("The point")
    print("=" * 74)
    print("  A circuit with no single cheap method splits into pieces that are each")
    print("  cheap -- along DIFFERENT axes. The dispatcher cuts, routes every piece to")
    print("  its own member, and pays only for the cut. Block A is now genuinely run by")
    print("  the phase-aware stabilizer engine (and its global phase is exact, so the")
    print("  cut recombines to the verified answer). Running block B on its NATIVE")
    print("  free-fermion engine is the one remaining drop-in.")


if __name__ == "__main__":
    main()
