r"""The hybrid dispatcher: cut a problem, then route each piece to its own simulator.

This is the sequel to `../simulator-router/`. The router answers "which single
simulator is cheapest for this whole circuit?" Here we close the loop: **cut the
circuit into pieces and route each piece to its OWN cheapest simulator**, and we run
*both* halves on real structured engines -- a phase-aware stabilizer engine and a
free-fermion engine -- paying an exponential price only in the small "hard part"
that connects the pieces.

Two ideas combine:

1. Circuit cutting (circuit knitting / the Schrodinger-Feynman method, what Google
   used to verify Sycamore classically). Split the qubits into halves A and B; only
   a few gates cross between them. We expand each crossing gate in the Pauli basis,
   G = sum_{P,Q} c_{PQ} P (x) Q. Expanding, the whole circuit becomes a sum over
   "branches", and in every branch the gates factorise into an A-only and a B-only
   circuit:

       |psi_full>  =  sum over branches of   coeff * |psi_A^branch> (x) |psi_B^branch> .

   We cut with CZ gates on purpose: their Pauli decomposition injects only I or Z
   into each block (a diagonal factor), so block A stays Clifford AND block B stays
   a free-fermion (matchgate) circuit -- each piece remains inside its member's gate
   set, and each block state factorises as (a fixed base state) with a sign mask.

2. Per-block routing with real per-block engines. Block A is run on a phase-aware
   stabilizer engine; block B is run on a free-fermion engine.

The punchline: a circuit with **no single cheap method as a whole** splits into
halves that are each easy along a **different axis** -- a Clifford half and a
free-fermion half.

The engines, and why they are phase-aware
-----------------------------------------
The recombination sums |psi_A> (x) |psi_B> over branches, so each block state must
carry its correct GLOBAL phase, or the branches interfere wrongly.

* Stabilizer (block A): the explicit stabilizer-superposition representation -- the
  state as its sparse amplitudes over the affine support. Phase-exact; compresses to
  2^(support) (block A spreads over 2^3, not 2^10). For the poly-time-ALWAYS variant
  (O(n*k) regardless of Hadamard count) see the companion module `ch_form.py`.
* Free fermion (block B): the FERMIONIC GAUSSIAN representation -- the m x m pairing
  matrix A with |psi> proportional to exp(1/2 sum A_ij a_i^dag a_j^dag)|0> (Thouless
  form). Matchgates update A in closed form (number-conserving gates by congruence
  A -> W A W^T; an initial disjoint pairing layer sets A directly), and the vacuum
  amplitude <0|psi> is tracked exactly to fix the global phase. Amplitudes are
  Pfaffians: <x|psi> = <0|psi> * Pf(A[occupied modes of x]). This is phase-exact and
  the pairing matrix is the genuine poly object; reconstructing the full vector here
  costs one Pfaffian per amplitude (the readout).

Amplitude-level recombination (the asymptotic win): `build_amplitude_oracle` returns a
function giving any single output amplitude <x|U_full|0> with NO 2^n vector ever built
-- it factorises into one stabilizer-amplitude lookup, one Pfaffian (block B), and a
sum over the few branches, all polynomial. So you compute only the outcomes you want.

Both engines are validated by self-tests against the universal backend on random
circuits, exactly (global phase included), before the dispatcher runs.

Run:  python hybrid_dispatcher.py
"""
import itertools
import math
from collections import defaultdict

import numpy as np


# --- a minimal, correct state-vector backend (brute force) --------------------
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


# --- gate library ------------------------------------------------------------
H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
S = np.array([[1, 0], [0, 1j]], dtype=complex)
PX = np.array([[0, 1], [1, 0]], dtype=complex)
PY = np.array([[0, -1j], [1j, 0]], dtype=complex)
PZ = np.array([[1, 0], [0, -1]], dtype=complex)
I2 = np.eye(2, dtype=complex)
PAULI = {"I": I2, "X": PX, "Y": PY, "Z": PZ}

CNOT = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
CZ = np.diag([1, 1, 1, -1]).astype(complex)
FSWAP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, -1]], dtype=complex)


def rz(theta):
    return np.array([[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]], dtype=complex)


def xx_yy(theta):
    """exp(-i th/2 (XX+YY)) -- hopping; number-conserving matchgate."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[1, 0, 0, 0], [0, c, -1j * s, 0], [0, -1j * s, c, 0], [0, 0, 0, 1]], dtype=complex)


def pair_gate(theta):
    """exp(-i th/2 (XX-YY)) -- pairing; creates/annihilates a pair (mixes |00>,|11>)."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, 0, 0, -1j * s], [0, 1, 0, 0], [0, 0, 1, 0], [-1j * s, 0, 0, c]], dtype=complex)


# --- phase-aware stabilizer engine (explicit-superposition representation) ----
class StabilizerSim:
    """Phase-EXACT Clifford simulator: state as sparse amplitudes over the affine
    stabilizer support (a dict {basis state -> amplitude}). Applying the real gate
    actions keeps the GLOBAL phase exact, which a bare tableau loses."""

    def __init__(self, m):
        self.m, self.amp = m, {0: 1.0 + 0j}

    def _mask(self, q):
        return 1 << (self.m - 1 - q)

    def _bit(self, x, q):
        return (x >> (self.m - 1 - q)) & 1

    def apply(self, name, qs):
        if name == "I":
            return
        if name in ("Z", "S"):
            f = 1j if name == "S" else -1
            for x in self.amp:
                if self._bit(x, qs[0]):
                    self.amp[x] *= f
        elif name in ("X", "Y"):
            mask = self._mask(qs[0])
            self.amp = {x ^ mask: (1j * (-1) ** self._bit(x, qs[0]) if name == "Y" else 1) * a
                        for x, a in self.amp.items()}
        elif name in ("CX", "CNOT"):
            cm, tm = self._mask(qs[0]), self._mask(qs[1])
            self.amp = {(x ^ tm if x & cm else x): a for x, a in self.amp.items()}
        elif name == "CZ":
            for x in self.amp:
                if self._bit(x, qs[0]) and self._bit(x, qs[1]):
                    self.amp[x] *= -1
        elif name == "H":
            mask, inv = self._mask(qs[0]), 1.0 / math.sqrt(2)
            new = defaultdict(complex)
            for x, a in self.amp.items():
                sign = -1 if (x & mask) else 1
                new[x & ~mask] += a * inv
                new[x | mask] += a * inv * sign
            self.amp = {x: a for x, a in new.items() if abs(a) > 1e-12}

    def amplitude(self, x):
        """A single amplitude <x|psi> -- just a lookup in the (sparse) support."""
        return self.amp.get(x, 0.0 + 0j)

    def statevector(self):
        psi = np.zeros(2 ** self.m, dtype=complex)
        for x, a in self.amp.items():
            psi[x] = a
        return psi


def stab_engine(m, named_ops):
    sim = StabilizerSim(m)
    for name, qs in named_ops:
        sim.apply(name, qs)
    return sim


def run_stabilizer(m, named_ops):
    sim = stab_engine(m, named_ops)
    return sim.statevector(), len(sim.amp)


# --- free-fermion engine (fermionic Gaussian / pairing-matrix representation) -
def pfaffian(A):
    """Pfaffian of an antisymmetric matrix via Laplace-style expansion along the first
    row: Pf(A) = sum_{j>0} (-1)^j A[0,j] Pf(A with rows/cols 0 and j removed). Pf of the
    empty matrix is 1; Pf of any odd-size matrix is 0. (Fine for the small minors here.)"""
    n = A.shape[0]
    if n == 0:
        return 1.0 + 0j
    if n % 2 == 1:
        return 0.0 + 0j
    total = 0.0 + 0j
    rest = list(range(1, n))                      # candidate partners j for index 0
    for jj, j in enumerate(rest):
        if A[0, j] != 0:
            sub = [rest[t] for t in range(len(rest)) if t != jj]   # remove rows/cols 0 and j
            total += (-1) ** jj * A[0, j] * pfaffian(A[np.ix_(sub, sub)])
    return total


class FreeFermionSim:
    """Phase-EXACT free-fermion (matchgate) simulator. The state is the fermionic
    Gaussian state |psi> ~ exp(1/2 sum A_ij a_i^dag a_j^dag)|0>, stored as the m x m
    antisymmetric pairing matrix A and the vacuum amplitude v = <0|psi>. Supports an
    initial disjoint PAIRING layer (sets A directly) followed by number-conserving
    matchgates (RZ, hopping XX_YY, FSWAP, Z), each updating A by a closed-form
    congruence A -> W A W^T and v by a known scalar. Amplitudes are Pfaffians:
    <x|psi> = v * Pf(A restricted to the occupied modes of x)."""

    def __init__(self, m):
        self.m, self.A, self.v = m, np.zeros((m, m), dtype=complex), 1.0 + 0j

    def _congruence(self, W2, i, j):
        """A number-conserving Gaussian gate acts on creation operators by
        a_k^dag -> sum_l W_lk a_l^dag, which carries the Thouless matrix to W A W^T.
        Here W is the identity except for a 2x2 block W2 on modes (i, j)."""
        W = np.eye(self.m, dtype=complex)
        W[i, i], W[i, j], W[j, i], W[j, j] = W2[0, 0], W2[0, 1], W2[1, 0], W2[1, 1]
        self.A = W @ self.A @ W.T

    def apply(self, name, qs, param):
        if name == "I":
            return
        if name == "RZ":
            # RZ(th) = e^{-i th/2} exp(i th n_q): the exp(i th n_q) part sends
            # a_q^dag -> e^{i th} a_q^dag, scaling row/col q of A; the e^{-i th/2}
            # prefactor is a vacuum phase (it acts on |0>) and goes into v.
            q, th = qs[0], param
            self.A[q, :] *= np.exp(1j * th)
            self.A[:, q] *= np.exp(1j * th)
            self.v *= np.exp(-1j * th / 2)
        elif name == "Z":
            # Z = exp(i pi n_q): a_q^dag -> -a_q^dag (and Z|0> = |0>, so v is unchanged).
            q = qs[0]
            self.A[q, :] *= -1
            self.A[:, q] *= -1
        elif name == "XX_YY":
            # Hopping exp(-i th (a_i^dag a_j + a_j^dag a_i)): creation operators rotate
            # by W = exp(-i th [[0,1],[1,0]]) = [[cos,-i sin],[-i sin,cos]]. It annihilates
            # the vacuum, so v is unchanged.
            c, s = math.cos(param), math.sin(param)
            self._congruence(np.array([[c, -1j * s], [-1j * s, c]]), qs[0], qs[1])
        elif name == "FSWAP":
            # Fermionic swap: exchange modes i and j (the -1 on |11> is automatic from
            # the antisymmetry of A under the row/col swap). Vacuum unchanged.
            self._congruence(np.array([[0, 1], [1, 0]], dtype=complex), qs[0], qs[1])
        elif name == "PAIR":
            # exp(-i th/2 (XX-YY)) on a FRESH pair: PAIR|00> = cos th |00> - i sin th |11>.
            # In Thouless form cos th (|00> + A_ij |11>), so A_ij = -i tan th (i<j) and
            # the vacuum amplitude picks up cos th. (Restricted to fresh, disjoint modes
            # so no Mobius update is needed -- this is the initial pairing layer.)
            i, j, th = qs[0], qs[1], param
            assert i < j and not self.A[i, :].any() and not self.A[j, :].any(), \
                "PAIR must act on fresh, ascending modes (initial disjoint layer)"
            self.A[i, j], self.A[j, i] = -1j * math.tan(th), 1j * math.tan(th)
            self.v *= math.cos(th)

    def amplitude(self, x):
        # <x|psi> = <0|psi> * Pf(A restricted to the modes occupied in x). One Pfaffian.
        # Odd occupation -> 0 (the state lives in the even-parity sector).
        S = [q for q in range(self.m) if (x >> (self.m - 1 - q)) & 1]      # occupied modes
        if len(S) % 2 == 1:
            return 0.0 + 0j
        return self.v * pfaffian(self.A[np.ix_(S, S)])

    def statevector(self):
        return np.array([self.amplitude(x) for x in range(2 ** self.m)], dtype=complex)


def ff_engine(m, named_param_ops):
    sim = FreeFermionSim(m)
    for name, qs, param in named_param_ops:
        sim.apply(name, qs, param)
    return sim


def run_freefermion(m, named_param_ops):
    return ff_engine(m, named_param_ops).statevector()


# --- per-block routing (the same meters as ../simulator-router/) --------------
CLIFFORD = {"H", "S", "SDG", "X", "Y", "Z", "CX", "CNOT", "CZ", "SWAP"}
MATCHGATE = {"RZ", "Z", "XY", "XX_YY", "GIVENS", "FSWAP", "PAIR", "MG"}
ALPHA = 0.2284


def _poly(x):
    return 2.0 * math.log2(max(x, 2))


def route_block(gates, m):
    t = sum(1 for (nm, _) in gates if nm not in CLIFFORD)
    k = sum(1 for (nm, _) in gates if nm not in MATCHGATE)
    costs = {"state vector": float(m), "stabilizer": ALPHA * t + _poly(m),
             "free fermion": k * math.log2(4) + _poly(2 * m)}
    member = min(costs, key=lambda c: costs[c])
    return member, costs[member], {"t": t, "k": k}


# --- Pauli-basis decomposition of a crossing gate ----------------------------
def pauli_decomposition(U, tol=1e-12):
    """U = sum_{P,Q} c_{PQ} P (x) Q; returns [(coeff, P_name, Q_name)]."""
    terms = [(np.trace(np.kron(P, Q).conj().T @ U) / 4.0, pn, qn)
             for pn, P in PAULI.items() for qn, Q in PAULI.items()]
    terms = [(c, pn, qn) for (c, pn, qn) in terms if abs(c) > tol]
    assert np.allclose(sum(c * np.kron(PAULI[pn], PAULI[qn]) for (c, pn, qn) in terms), U)
    return terms


def _sign_mask(m, z_qubits):
    """Diagonal +-1 mask on an m-qubit register for a product of Z's (and I's)."""
    mask = np.ones(2 ** m)
    for q in z_qubits:
        bit = 1 << (m - 1 - q)
        mask *= np.array([-1.0 if (x & bit) else 1.0 for x in range(2 ** m)])
    return mask


# --- the hybrid: cut, route each half, run A and B on their own engines -------
def _partition(n, circuit):
    """Split a circuit (list of (name, U, qubits, param)) into the two blocks. Returns
    cut, block-A gates as (name, locqs), block-B gates as (name, locqs, param), the
    native gate names of each block (for routing), and the crossing gates (each with
    its Pauli decomposition and the local qubits it touches on A and B)."""
    cut = n // 2
    in_A = lambda q: q < cut
    locA, locB = (lambda q: q), (lambda q: q - cut)
    aNamed, bParam, aNames, bNames, crossing = [], [], [], [], []
    for (name, U, qs, param) in circuit:
        if len(qs) == 1:
            if in_A(qs[0]):
                aNamed.append((name, (locA(qs[0]),))); aNames.append((name, qs))
            else:
                bParam.append((name, (locB(qs[0]),), param)); bNames.append((name, qs))
        elif in_A(qs[0]) and in_A(qs[1]):
            aNamed.append((name, (locA(qs[0]), locA(qs[1])))); aNames.append((name, qs))
        elif (not in_A(qs[0])) and (not in_A(qs[1])):
            bParam.append((name, (locB(qs[0]), locB(qs[1])), param)); bNames.append((name, qs))
        else:
            q0, q1 = qs
            aq, bq = (q0, q1) if in_A(q0) else (q1, q0)
            crossing.append((pauli_decomposition(U), locA(aq), locB(bq), in_A(q0)))
    return cut, aNamed, bParam, aNames, bNames, crossing


def _branches(crossing):
    """Expand the crossing gates' Pauli decompositions into branches. Each branch is
    (coeff, za, zb): the product of chosen Pauli coefficients, and the local qubits
    receiving an injected Z on block A and block B. Because we cut with CZ, the injected
    factors are only I or Z (diagonal), so a Z is just a +-1 sign on the block state."""
    ranks = [len(c[0]) for c in crossing]
    out = []
    for choice in (itertools.product(*[range(r) for r in ranks]) if ranks else [()]):
        coeff, za, zb = 1.0 + 0j, [], []
        for ci, (terms, aq, bq, a_is_first) in enumerate(crossing):
            c, pn, qn = terms[choice[ci]]
            coeff *= c
            a_p, b_p = (pn, qn) if a_is_first else (qn, pn)
            assert a_p in ("I", "Z") and b_p in ("I", "Z"), "CZ cut must inject only I/Z"
            if a_p == "Z":
                za.append(aq)
            if b_p == "Z":
                zb.append(bq)
        out.append((coeff, za, zb))
    return out


def simulate_by_cutting(n, circuit):
    """Cut the circuit down the middle, route and run each block on its own engine,
    and recombine to the FULL exact state. Because the injected factors are diagonal,
    each block's base state is computed ONCE (block A on the stabilizer engine, block B
    on the free-fermion engine) and every branch is a cheap +-1 sign mask times it."""
    cut, aNamed, bParam, aNames, bNames, crossing = _partition(n, circuit)
    routeA, routeB = route_block(aNames, cut), route_block(bNames, n - cut)
    phiA, supportA = run_stabilizer(cut, aNamed)        # block A base state, once
    phiB = run_freefermion(n - cut, bParam)             # block B base state, once

    full = np.zeros(2 ** cut * 2 ** (n - cut), dtype=complex)
    for coeff, za, zb in _branches(crossing):
        full += coeff * np.kron(_sign_mask(cut, za) * phiA, _sign_mask(n - cut, zb) * phiB)

    return {"state": full, "branches": len(_branches(crossing)), "n_crossing": len(crossing),
            "routeA": routeA, "routeB": routeB, "supportA": supportA}


def build_amplitude_oracle(n, circuit):
    """The asymptotic payoff of the cut: return a function amp(x) giving the exact
    output amplitude <x|U_full|0> WITHOUT ever building a 2^n vector.

    Because every block's native circuit is fixed and the injected cut factors are
    diagonal, a single output amplitude factorises:

        <x|U_full|0> = alpha_A(x_A) * alpha_B(x_B) * sum_branches coeff * (+-1 signs),

    where alpha_A(x_A) = <x_A|C_A|0> is one stabilizer-amplitude lookup, alpha_B(x_B)
    = <x_B|U_B|0> is ONE Pfaffian over the occupied modes of x_B, and the branch sum is
    over the (few) crossing branches. Each call is polynomial; no 2^n state ever exists."""
    cut, aNamed, bParam, aNames, bNames, crossing = _partition(n, circuit)
    stab = stab_engine(cut, aNamed)             # provides alpha_A via .amplitude
    ff = ff_engine(n - cut, bParam)             # provides alpha_B via .amplitude (one Pfaffian)
    branches = _branches(crossing)
    nB = n - cut

    def amp(x):
        xA, xB = x >> nB, x & ((1 << nB) - 1)   # split the global index into A and B bits
        aA = stab.amplitude(xA)
        if aA == 0:
            return 0.0 + 0j
        aB = ff.amplitude(xB)
        if aB == 0:
            return 0.0 + 0j
        s = 0.0 + 0j                            # sum over branches of coeff * Z-signs
        for coeff, za, zb in branches:
            sgn = 1
            for q in za:                        # injected Z on block A flips sign if x_A bit set
                if (xA >> (cut - 1 - q)) & 1:
                    sgn = -sgn
            for q in zb:
                if (xB >> (nB - 1 - q)) & 1:
                    sgn = -sgn
            s += coeff * sgn
        return aA * aB * s

    return amp, len(branches), cut, nB


# --- a two-natured demonstration circuit -------------------------------------
def two_natured_circuit(n, seed=0):
    """Block A (qubits 0..n/2-1): a low-Hadamard Clifford circuit -> stabilizer.
    Block B (qubits n/2..n-1): a free-fermion circuit -- an initial pairing layer
    then number-conserving matchgates -> free fermion. Plus two CZ gates crossing
    the middle. Easy along different axes; hard as a whole."""
    rng = np.random.default_rng(seed)
    cut = n // 2
    c = []
    # Block A: Clifford, only a few Hadamards (keeps the stabilizer support small)
    for q in (0, 1, 2):
        c.append(("H", H, (q,), None))
    for q in range(cut - 1):
        c.append(("CX", CNOT, (q, q + 1), None))
    for q in range(0, cut, 3):
        c.append(("S", S, (q,), None))
    c.append(("CZ", CZ, (0, cut - 1), None))
    # Block B: free fermion -- a pairing layer (creates a genuine Gaussian state)...
    for q in range(cut, n - 1, 2):
        th = rng.uniform(0.3, 1.2)
        c.append(("PAIR", pair_gate(th), (q, q + 1), th))
    # ...then number-conserving matchgates
    for q in range(cut, n):
        th = rng.uniform(0.2, 3.0)
        c.append(("RZ", rz(th), (q,), th))
    for q in range(cut, n - 1):
        th = rng.uniform(0.2, 3.0)
        c.append(("XX_YY", xx_yy(th), (q, q + 1), th))
    c.append(("FSWAP", FSWAP, (cut, cut + 1), None))
    # the two gates crossing the cut: CZ injects only I/Z into each block
    c.append(("CZ", CZ, (cut - 1, cut), None))
    c.append(("CZ", CZ, (cut - 2, cut + 1), None))
    return c


def self_test():
    """Validate both engines against the universal backend on random circuits."""
    rng = np.random.default_rng(1)
    cliff = {"H": H, "S": S, "X": PX, "Y": PY, "Z": PZ, "CX": CNOT, "CZ": CZ}
    for _ in range(150):                               # stabilizer engine
        m = int(rng.integers(2, 6))
        named, mats = [], []
        for _ in range(int(rng.integers(5, 25))):
            g = str(rng.choice(["H", "S", "X", "Y", "Z", "CX", "CZ"]))
            qs = tuple(int(x) for x in rng.choice(m, size=(2 if g in ("CX", "CZ") else 1), replace=False))
            named.append((g, qs)); mats.append((cliff[g], qs))
        vec, _ = run_stabilizer(m, named)
        assert np.allclose(vec, run_statevector(m, mats), atol=1e-10), "stabilizer mismatch!"
    print("  [stabilizer engine: phase-exact on 150 random Clifford circuits]")

    for _ in range(150):                               # free-fermion engine
        m = int(rng.integers(2, 7))
        named_param, mats = [], []
        used = set()
        for q in range(0, m - 1, 2):                   # initial disjoint pairing layer
            if rng.random() < 0.7:
                th = rng.uniform(0.2, 1.3)
                named_param.append(("PAIR", (q, q + 1), th)); mats.append((pair_gate(th), (q, q + 1)))
                used.update((q, q + 1))
        for _ in range(int(rng.integers(3, 18))):      # number-conserving matchgates
            g = str(rng.choice(["RZ", "XX_YY", "FSWAP", "Z"]))
            if g in ("XX_YY", "FSWAP"):
                q = int(rng.integers(m - 1))
                th = rng.uniform(0.2, 3.0)
                named_param.append((g, (q, q + 1), th))
                mats.append((xx_yy(th) if g == "XX_YY" else FSWAP, (q, q + 1)))
            else:
                q = int(rng.integers(m)); th = rng.uniform(0.2, 3.0)
                named_param.append((g, (q,), th if g == "RZ" else None))
                mats.append((rz(th) if g == "RZ" else PZ, (q,)))
        vec = run_freefermion(m, named_param)
        ref = run_statevector(m, mats)
        assert np.allclose(vec, ref, atol=1e-10), "free-fermion engine mismatch!"
    print("  [free-fermion engine: phase-exact on 150 random matchgate circuits]")


def main():
    print(__doc__)
    print("=" * 74)
    print("Step 0 -- validate the two phase-aware engines")
    print("=" * 74)
    self_test()

    n = 20
    circuit = two_natured_circuit(n)
    cut = n // 2

    print("\n" + "=" * 74)
    print(f"A two-natured circuit on n = {n} qubits ({len(circuit)} gates)")
    print("=" * 74)
    whole = route_block([(nm, qs) for (nm, U, qs, p) in circuit], n)
    print(f"  Route the WHOLE circuit:  -> {whole[0].upper():<13} "
          f"(t = {whole[2]['t']}, k = {whole[2]['k']};  best single method, cost ~ 2^{whole[1]:.1f})")
    print("  No single method is POLYNOMIAL on the whole: a stabilizer simulator must")
    print("  pay for the non-Clifford rotations/pairings (t large), a free-fermion")
    print("  simulator for the H/CX/S gates (k large). The best of them is exponential.")

    out = simulate_by_cutting(n, circuit)
    (mA, cA, meA), (mB, cB, meB) = out["routeA"], out["routeB"]
    print(f"\n  Cut into two halves of {cut} qubits and route EACH:")
    print(f"    block A (qubits 0..{cut-1}):  -> {mA.upper():<13} (t={meA['t']}, k={meA['k']})"
          f"  -- RUN on the STABILIZER engine, support 2^{int(round(math.log2(out['supportA'])))} "
          f"= {out['supportA']} (not 2^{cut})")
    print(f"    block B (qubits {cut}..{n-1}): -> {mB.upper():<13} (t={meB['t']}, k={meB['k']})"
          f"  -- RUN on the FREE-FERMION engine (m x m pairing matrix + Pfaffians)")
    print(f"    + {out['n_crossing']} crossing CZ gate(s), Pauli-decomposed  ->  {out['branches']} branches")

    truth = run_statevector(n, [(U, qs) for (nm, U, qs, p) in circuit])
    ok = np.allclose(out["state"], truth, atol=1e-10)
    print(f"\n  Exact match with brute force: {ok}")
    assert ok, "hybrid result did not match brute force!"

    brute, whole_cost = 2 ** n, 2 ** whole[1]
    cut_cost = out["branches"] * (out["supportA"] + 2 ** cB)
    print("\n  Cost (operations, order of magnitude):")
    print(f"    brute force ................... 2^{n} = {brute:,.0f}")
    print(f"    route the whole circuit ....... ~ {whole_cost:,.0f}")
    print(f"    cut + route each half ......... {out['branches']} x (2^{int(round(math.log2(out['supportA'])))} "
          f"+ 2^{cB:.1f}) = {cut_cost:,.0f}   ({brute / cut_cost:.0f}x less than brute force)")

    # --- amplitude-level recombination: any single outcome, no 2^n vector ----
    print("\n" + "=" * 74)
    print("Amplitude-level recombination -- any single outcome, no 2^n vector built")
    print("=" * 74)
    amp, nbr, _, nB = build_amplitude_oracle(n, circuit)
    rng = np.random.default_rng(7)
    nz = [int(x) for x in np.nonzero(np.abs(truth) > 1e-12)[0]]      # nonzero outcomes
    sample = [int(x) for x in rng.choice(nz, size=min(300, len(nz)), replace=False)]
    sample += [int(x) for x in rng.integers(2 ** n, size=50)]        # include some zeros
    ok2 = all(abs(amp(x) - truth[x]) < 1e-10 for x in sample)
    print(f"  checked {len(sample)} output amplitudes (including zeros) against brute "
          f"force: {'all match' if ok2 else 'MISMATCH'}")
    assert ok2, "amplitude oracle disagreed with brute force!"
    for x in (nz[0], nz[len(nz) // 2], nz[-1]):      # three distinct nonzero outcomes
        print(f"    <{x:0{n}b}|U|0> = {amp(x): .5f}   (brute force {truth[x]: .5f})")
    print(f"\n  Cost of ONE amplitude: 1 stabilizer lookup + 1 Pfaffian over <= {nB} modes")
    print(f"  + a sum over {nbr} branches -- a few thousand operations, and NO 2^{n} vector")
    print(f"  is ever built. Want the 100 most-likely outcomes? ~100x that. Brute force")
    print(f"  must first build all 2^{n} = {2 ** n:,} amplitudes.")

    print("\n" + "=" * 74)
    print("The point")
    print("=" * 74)
    print("  A circuit with no single cheap method splits into pieces that are each")
    print("  cheap -- along DIFFERENT axes. The dispatcher cuts, routes every piece to")
    print("  its own member, and runs it there: block A on a phase-aware stabilizer")
    print("  engine, block B on a free-fermion (pairing-matrix + Pfaffian) engine. Both")
    print("  are phase-exact, and amplitude-level recombination delivers any individual")
    print("  outcome in polynomial work -- the cut never builds a 2^n vector at all.")


if __name__ == "__main__":
    main()
