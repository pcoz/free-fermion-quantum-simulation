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

Scope. Fully general and self-tested, poly-time and phase-exact: X, Z, S, CX, CZ, and
H ANYWHERE (including on already-entangled qubits). The easy gates update the
affine-quadratic data in closed form. H on an already-superposed qubit -- the delicate
core of the CH-form -- is handled without pushing the phase through the affine variable
change by hand: the result is still a stabilizer state, so we evaluate its new
amplitude function from the old form (one GF(2) solve per amplitude) and re-fit the
affine-quadratic form to it (find the support, then read off the linear and quadratic
phases), both polynomial. Validated against a state-vector backend on 1500 random
Clifford circuits (500 of them with H anywhere), exactly, global phase included.

The point: a phase-exact stabilizer state is carried in a polynomial O(n*k) object,
never the 2^k support the dispatcher's explicit-superposition engine materialises.
"""
import math

import numpy as np


def _phase_i(p):
    """i**p for integer p (mod 4)."""
    return (1.0 + 0j, 1j, -1.0 + 0j, -1j)[p % 4]


def _i_log(c):
    """Inverse of _phase_i: which power of i is c (assumed a 4th root of unity)?"""
    for p in range(4):
        if abs(c - _phase_i(p)) < 1e-6:
            return p
    raise ValueError(f"not a 4th root of unity: {c}")


def _gf2_solve(G, t):
    """Solve G y = t over GF(2) for an n x k matrix G; return one solution y (k,) or
    None if inconsistent. (When G has full column rank the solution is unique.)"""
    n, k = G.shape
    A = [[int(G[i, c]) for c in range(k)] + [int(t[i])] for i in range(n)]
    pivots, row = {}, 0
    for col in range(k):
        sel = next((rr for rr in range(row, n) if A[rr][col]), None)
        if sel is None:
            continue
        A[row], A[sel] = A[sel], A[row]
        for rr in range(n):
            if rr != row and A[rr][col]:
                A[rr] = [A[rr][c] ^ A[row][c] for c in range(k + 1)]
        pivots[col] = row
        row += 1
    for rr in range(n):                              # consistency check
        if A[rr][k] == 1 and not any(A[rr][c] for c in range(k)):
            return None
    y = np.zeros(k, dtype=np.int8)
    for col, rrow in pivots.items():
        y[col] = A[rrow][k]
    return y


def _rref_basis(vecs, n):
    """A GF(2) basis of the span of `vecs` (each an n-bit integer bitmask)."""
    piv = {}                                         # highest set bit -> reduced vector
    for v in vecs:
        cur = v
        while cur:
            hb = cur.bit_length() - 1
            if hb in piv:
                cur ^= piv[hb]
            else:
                piv[hb] = cur
                break
    return list(piv.values())


class CHForm:
    """A stabilizer state held in the affine-quadratic (CH) form described at the top
    of this file: the support directions G (n x k), the offset b, the linear and
    quadratic phases (lin mod 4, quad strictly-upper mod 2), the free-bit count k, and
    the exact global phase omega. Gate methods update these in place."""

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
            self._h_superposed(a)

    # -- amplitude access + the general (case-2) Hadamard ---------------------
    def _xbits(self, z):
        return np.array([(z >> (self.n - 1 - q)) & 1 for q in range(self.n)], dtype=np.int8)

    def _index(self, xb):
        z = 0
        for q in range(self.n):
            if xb[q]:
                z |= 1 << (self.n - 1 - q)
        return z

    def amp(self, z):
        """Exact amplitude <z|psi> in poly time: solve G y = (x XOR b) over GF(2)
        (unique, since G has full column rank), then evaluate the phase."""
        xb = self._xbits(z)
        y = _gf2_solve(self.G, (xb ^ self.b) % 2) if self.k else (np.zeros(0, np.int8)
                                                                  if not (xb ^ self.b).any() else None)
        if y is None:
            return 0.0 + 0j
        lt = int(self.lin @ y) % 4 if self.k else 0
        qt = int(y @ self.quad @ y) % 2 if self.k else 0
        return self.omega * 2.0 ** (-self.k / 2) * _phase_i(lt) * ((-1) ** qt)

    def _h_superposed(self, a):
        """H on an already-superposed qubit. The result is still a stabilizer state,
        so rather than push the phase through the affine variable change by hand (the
        delicate core of the CH-form), we evaluate the NEW amplitude function exactly
        from the old form and re-fit the affine-quadratic form to it -- both poly-time.

            <z|psi'> = 2^(-1/2) ( <z|a=0> + (-1)^z_a <z|a=1> )  (old amplitudes)."""
        amask = 1 << (self.n - 1 - a)
        inv = 1.0 / math.sqrt(2)

        def g(z):                                    # new amplitude at basis state z
            za = (z >> (self.n - 1 - a)) & 1
            return inv * (self.amp(z & ~amask) + (-1) ** za * self.amp(z | amask))

        # 1) Collect support points of the NEW state. Its support lies in the affine
        #    span of the old support and e_a, so old support points with bit a freed
        #    are enough to span it; sample y = 0, each e_i, and a few random y.
        ys = [np.zeros(self.k, np.int8)]
        for i in range(self.k):
            e = np.zeros(self.k, np.int8); e[i] = 1; ys.append(e)
        rng = np.random.default_rng(12345)
        for _ in range(2 * self.k + 4):
            ys.append(rng.integers(0, 2, size=self.k).astype(np.int8))
        support = []
        seen = set()
        for y in ys:
            xb = (self.b ^ ((self.G @ y) % 2)) % 2 if self.k else self.b.copy()
            base = self._index(xb)
            for z in (base & ~amask, base | amask):
                if z not in seen and abs(g(z)) > 1e-9:
                    seen.add(z); support.append(z)

        # 2) b' = a support point; directions = a GF(2) basis of {z XOR b'}.
        bp = support[0]
        basis = _rref_basis([z ^ bp for z in support], self.n)
        kp = len(basis)

        # 3) Read omega, the linear phases (single directions) and quadratic phases
        #    (pairs) straight off the amplitude function.
        g0 = g(bp)
        omega = g0 * 2.0 ** (kp / 2)
        lin = np.zeros(kp, dtype=np.int8)
        for i in range(kp):
            lin[i] = _i_log(g(bp ^ basis[i]) / g0)
        quad = np.zeros((kp, kp), dtype=np.int8)
        for i in range(kp):
            for j in range(i + 1, kp):
                ph = g(bp ^ basis[i] ^ basis[j]) / g0
                quad[i, j] = 0 if abs(ph / _phase_i((lin[i] + lin[j]) % 4) - 1) < 1e-6 else 1

        # 4) Install the refitted form (columns of G' are the basis directions).
        self.b = self._xbits(bp)
        self.G = np.array([self._xbits(d) for d in basis], dtype=np.int8).T.reshape(self.n, kp)
        self.lin, self.quad, self.omega, self.k = lin, quad, omega, kp

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
    """Check every gate against a brute-force state-vector backend, exactly (global
    phase included), on random circuits of three increasing kinds."""
    rng = np.random.default_rng(0)
    # (a) single-qubit gates only: X, Z, S, and a fresh Hadamard (<=1 H per qubit,
    #     no entangling) -- so every H lands on a not-yet-superposed qubit.
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
    print("  [OK: X, Z, S, H(fresh) phase-exact on 500 random circuits]")

    # (b) entangling gates on superposed states: a layer of Hadamards (each still on a
    #     fresh qubit) THEN X/Z/S/CX/CZ -- exercises CX, CZ on entangled, superposed
    #     states while every H stays in the easy case.
    for _ in range(500):
        n = int(rng.integers(2, 6))
        ops = [("H", q) for q in range(n) if rng.random() < 0.6]
        for _ in range(int(rng.integers(1, 20))):
            name = str(rng.choice(["X", "Z", "S", "CX", "CZ"]))
            ops.append((name, _random_2q(rng, n) if name in _MAT2 else int(rng.integers(n))))
        assert np.allclose(_run_chform(n, ops), _reference(n, ops), atol=1e-12), ops
    print("  [OK: + CX, CZ on entangled states, phase-exact on 500 circuits]")

    # (c) fully general circuits: any gate in any order, so H frequently lands on an
    #     already-entangled qubit -- the general case, handled by the amplitude re-fit.
    for _ in range(500):
        n = int(rng.integers(2, 6))
        ops = []
        for _ in range(int(rng.integers(1, 25))):
            name = str(rng.choice(["H", "S", "X", "Z", "CX", "CZ"]))
            ops.append((name, _random_2q(rng, n) if name in _MAT2 else int(rng.integers(n))))
        assert np.allclose(_run_chform(n, ops), _reference(n, ops), atol=1e-12), ops
    print("  [OK: fully general Clifford (H anywhere) phase-exact on 500 circuits]")

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
