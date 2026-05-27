r"""A poly-time, phase-EXACT stabilizer simulator (CH / affine-quadratic form).

The dispatcher's explicit-superposition stabilizer engine is phase-exact but its cost
grows with the stabilizer support (2^k), so it is only cheap for low-Hadamard blocks.
This module is the poly-time-ALWAYS upgrade: it stores a stabilizer state in the
affine-quadratic ("CH") form

    |psi> = omega * 2^(-k/2) * sum_{y in {0,1}^k}  i^(lin . y)  (-1)^(quad(y))  |b XOR G y>,

where
  * G is an n x k binary matrix whose columns span the support directions,
  * b is the n-bit affine offset,
  * lin is a length-k vector mod 4 (the linear phase) and quad is a strictly-upper
    binary matrix (the quadratic phase), so the phase of term y is i^(lin.y) (-1)^(quad),
  * omega is the exact global phase, and k is the number of free bits.

Every Clifford gate updates (G, b, lin, quad, omega, k) in O(n^2)-ish time -- no 2^n
or 2^k object is built. The representation is updated with this file's OWN consistent
conventions (so there is nothing to mismatch against an external standard); every gate
is checked against a brute-force state-vector backend in `self_test()`.

Bit convention (matches the rest of the repo): qubit q is bit (n-1-q) of a basis
index, so |x> sits at index sum_q x_q 2^(n-1-q).

Scope of this build. Fully implemented and self-tested, poly-time and phase-exact:
X, Z, S, CX, CZ, and H on a NOT-yet-superposed qubit. That already covers the common
"Hadamard layer, then entangle" normal form -- including the dispatcher's Clifford
half (`two_natured_circuit` applies its H's first). The one remaining case is H on an
already-superposed qubit, whose phase update under the affine-form variable change is
the intricate core of the full CH-form; it raises NotImplementedError here so the
boundary is explicit rather than silently wrong. The point this module makes is the
one that matters: a phase-exact stabilizer state can be carried in a polynomial
(O(n*k)) object, never the 2^k support the dispatcher's other engine materialises.
"""
import math

import numpy as np


def _phase_i(p):
    """i**p for integer p (mod 4)."""
    return (1.0 + 0j, 1j, -1.0 + 0j, -1j)[p % 4]


class CHForm:
    def __init__(self, n):
        self.n = n
        self.k = 0
        self.G = np.zeros((n, 0), dtype=np.int8)     # n x k, rows r_a
        self.b = np.zeros(n, dtype=np.int8)          # affine offset
        self.lin = np.zeros(0, dtype=np.int8)        # length k, mod 4
        self.quad = np.zeros((0, 0), dtype=np.int8)  # k x k strictly upper, mod 2
        self.omega = 1.0 + 0j

    # -- helpers --------------------------------------------------------------
    def _row(self, a):
        return self.G[a].copy() if self.k else np.zeros(0, dtype=np.int8)

    def _add_free_var(self, col, lin_val):
        """Append a new free variable y_{k}: its support direction is `col` (length n),
        its linear phase is lin_val (mod 4), no quadratic coupling yet."""
        self.G = np.hstack([self.G, col.reshape(self.n, 1).astype(np.int8)])
        self.lin = np.append(self.lin, lin_val % 4).astype(np.int8)
        newq = np.zeros((self.k + 1, self.k + 1), dtype=np.int8)
        if self.k:
            newq[:self.k, :self.k] = self.quad
        self.quad = newq
        self.k += 1

    # -- gates ----------------------------------------------------------------
    def x(self, a):
        # X_a flips qubit a in every basis state: just flip the offset bit.
        self.b[a] ^= 1

    def z(self, a):
        # Z_a multiplies by (-1)^x_a = (-1)^b_a (-1)^(r_a . y). The data-independent
        # sign goes to omega; (-1)^(r_a.y) = i^(2 r_a . y) adds 2 r_a to the linear phase.
        r = self._row(a)
        if self.b[a]:
            self.omega = -self.omega
        if self.k:
            self.lin = (self.lin + 2 * r) % 4

    def s(self, a):
        # S_a multiplies by i^x_a, x_a = b_a XOR (r_a . y). Using the identity
        # i^((sum c_i) mod 2) = i^(sum c_i) (-1)^(sum_{i<j} c_i c_j) with c_i = r_{a,i} y_i:
        #   i^x_a = i^b_a * i^(r_a . y) * (-1)^(b_a (r_a . y))
        # -> omega *= i^b_a;  lin += r_a (1 + 2 b_a);  quad += strict-upper(r_a r_a^T).
        r = self._row(a)
        self.omega *= _phase_i(int(self.b[a]))
        if self.k:
            self.lin = (self.lin + r * (1 + 2 * int(self.b[a]))) % 4
            outer = np.triu(np.outer(r, r), k=1) % 2
            self.quad = (self.quad + outer) % 2

    def h(self, a):
        r = self._row(a)
        if not r.any():
            # Case 1: qubit a is deterministic (x_a = b_a). H_a creates a fresh free
            # bit y_new with x_a = y_new and phase (-1)^(b_a y_new) = i^(2 b_a y_new).
            col = np.zeros(self.n, dtype=np.int8)
            col[a] = 1
            self._add_free_var(col, 2 * int(self.b[a]))
            self.b[a] = 0
        else:
            raise NotImplementedError(
                "H on an already-superposed qubit -- the intricate core of the full "
                "CH-form (phase update under the affine variable change). Out of scope "
                "for this build; circuits with their Hadamards before any entangling "
                "gate (e.g. the dispatcher's block A) stay in the supported fragment.")

    def cx(self, a, b):
        # CX permutes basis states (x_b -> x_a XOR x_b), no phase. As a map on y:
        # offset bit b_b XORs b_a, and support row r_b XORs r_a.
        self.b[b] ^= self.b[a]
        if self.k:
            self.G[b] = (self.G[b] + self.G[a]) % 2

    def cz(self, a, b):
        # CZ multiplies by (-1)^(x_a x_b). With u = r_a.y, v = r_b.y (mod 2):
        #   (-1)^(x_a x_b) = (-1)^(b_a b_b) (-1)^(b_b u) (-1)^(b_a v) (-1)^(uv),
        # and (-1)^(uv) = i^(u mod2) i^(v mod2) i^-((u^v) mod2) folds into lin/quad.
        ra, rb = self._row(a), self._row(b)
        if self.b[a] and self.b[b]:
            self.omega = -self.omega
        if self.k:
            self.lin = (self.lin + 2 * int(self.b[b]) * ra + 2 * int(self.b[a]) * rb
                        + 2 * (ra & rb)) % 4
            outer = np.triu(np.outer(ra, rb) + np.outer(rb, ra), k=1) % 2
            self.quad = (self.quad + outer) % 2

    # -- readout (for testing; O(2^k)) ---------------------------------------
    def statevector(self):
        psi = np.zeros(2 ** self.n, dtype=complex)
        norm = self.omega * 2.0 ** (-self.k / 2)
        for yint in range(2 ** self.k):
            y = np.array([(yint >> i) & 1 for i in range(self.k)], dtype=np.int8)
            x = self.b.copy()
            if self.k:
                x = (x + (self.G @ y)) % 2
            idx = 0
            for q in range(self.n):
                if x[q]:
                    idx |= 1 << (self.n - 1 - q)
            lin_term = int(self.lin @ y) % 4 if self.k else 0
            quad_term = int(y @ self.quad @ y) % 2 if self.k else 0
            psi[idx] += norm * _phase_i(lin_term) * ((-1) ** quad_term)
        return psi


# ---------------------------------------------------------------------------
# Brute-force reference backend (qubit 0 = MSB), for the self-test.
# ---------------------------------------------------------------------------
_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_S = np.array([[1, 0], [0, 1j]], dtype=complex)
_X = np.array([[0, 1], [1, 0]], dtype=complex)
_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_CX = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
_CZ = np.diag([1, 1, 1, -1]).astype(complex)
_MAT1 = {"H": _H, "S": _S, "X": _X, "Z": _Z}
_MAT2 = {"CX": _CX, "CZ": _CZ}


def _apply_1q(psi, U, q, n):
    psi = psi.reshape((2,) * n)
    return np.moveaxis(np.tensordot(U, psi, axes=([1], [q])), 0, q).reshape(-1)


def _apply_2q(psi, U, a, b, n):
    psi = psi.reshape((2,) * n)
    U4 = U.reshape(2, 2, 2, 2)
    return np.moveaxis(np.tensordot(U4, psi, axes=([2, 3], [a, b])), [0, 1], [a, b]).reshape(-1)


def _reference(n, ops):
    psi = np.zeros(2 ** n, dtype=complex)
    psi[0] = 1.0
    for name, qs in ops:
        if name in _MAT1:
            psi = _apply_1q(psi, _MAT1[name], qs, n)
        else:
            psi = _apply_2q(psi, _MAT2[name], qs[0], qs[1], n)
    return psi


def _run_chform(n, ops):
    st = CHForm(n)
    for name, qs in ops:
        if name in _MAT1:
            getattr(st, name.lower())(qs)
        else:
            getattr(st, name.lower())(qs[0], qs[1])
    return st.statevector()


def _random_2q(rng, n):
    a, b = (int(x) for x in rng.choice(n, size=2, replace=False))
    return a, b


def self_test():
    rng = np.random.default_rng(0)
    # Piece 1: X, Z, S, H on a fresh qubit (<=1 H per qubit, no entangling).
    for _ in range(500):
        n = int(rng.integers(1, 6))
        ops, hit = [], set()
        for _ in range(int(rng.integers(1, 16))):
            choices = ["X", "Z", "S"] + (["H"] if len(hit) < n else [])
            name = str(rng.choice(choices))
            if name == "H":
                q = int(rng.choice([q for q in range(n) if q not in hit])); hit.add(q)
            else:
                q = int(rng.integers(n))
            ops.append((name, q))
        assert np.allclose(_run_chform(n, ops), _reference(n, ops), atol=1e-12), ops
    print("  [piece 1 OK: X, Z, S, H(fresh) phase-exact on 500 random circuits]")

    # Piece 2: a layer of H (case 1) THEN X/Z/S/CX/CZ -- exercises CZ/CX on
    # entangled, superposed states while keeping every H in the easy case.
    for _ in range(500):
        n = int(rng.integers(2, 6))
        ops = [("H", q) for q in range(n) if rng.random() < 0.6]
        for _ in range(int(rng.integers(1, 20))):
            name = str(rng.choice(["X", "Z", "S", "CX", "CZ"]))
            ops.append((name, _random_2q(rng, n) if name in _MAT2 else int(rng.integers(n))))
        assert np.allclose(_run_chform(n, ops), _reference(n, ops), atol=1e-12), ops
    print("  [piece 2 OK: + CX, CZ on entangled states, phase-exact on 500 circuits]")

    # The dispatcher's block A shape: a few Hadamards FIRST, then a CX chain, S, CZ.
    # This is exactly the supported fragment; show it is exact and that the carried
    # object stays small (k free bits, an O(n*k) matrix -- never the 2^k support).
    n = 10
    ops = [("H", 0), ("H", 1), ("H", 2)]
    ops += [("CX", (q, q + 1)) for q in range(n - 1)]
    ops += [("S", q) for q in range(0, n, 3)] + [("CZ", (0, n - 1))]
    st = CHForm(n)
    for name, qs in ops:
        getattr(st, name.lower())(*(qs if isinstance(qs, tuple) else (qs,)))
    assert np.allclose(st.statevector(), _reference(n, ops), atol=1e-12)
    print(f"  [block-A shape OK at n={n}: phase-exact, carried in k={st.k} free bits "
          f"(an {n}x{st.k} matrix), not the 2^{st.k} support]")


if __name__ == "__main__":
    self_test()
