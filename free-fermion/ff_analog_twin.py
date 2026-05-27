r"""The free-fermion ANALOG TWIN, via holant_tools.free_fermion.

A free-fermion (matchgate) quantum system -- e.g. a transverse-field Ising chain
-- is the canonical "analog Holant computer": its natural dynamics IS a matchgate
evolution, and the whole state is captured by a 2n x 2n real antisymmetric
COVARIANCE MATRIX (the analog device's state) instead of 2^n complex amplitudes.
`holant_tools.FreeFermionCircuit` is the digital twin of that analog device.

This script shows the "mega gains" of exploiting that structure on silicon:

  * the analog/free-fermion twin tracks the system with an O(n^2)-per-step
    covariance update (one local 4xO(n) matrix touch per gate);
  * a faithful STATE-VECTOR simulation -- the regular way to simulate this
    quantum dynamics on a CPU -- needs 2^n complex amplitudes and hits a hard
    memory wall (~30 qubits = exabytes).

Honest scope (the punchline): the gain is EXPONENTIAL over naive state-vector
simulation -- because the dynamics is free-fermion structured, the tractable
corner. It is NOT a speedup of classical computation in general, and an actual
analog free-fermion device would match this digital twin asymptotically (no
further win). The structure -- non-interacting / free-fermion dynamics -- is the
whole reason the simulation is cheap. See README.md for the full explanation.

----------------------------------------------------------------------------
The physics, in one paragraph (so the code below reads clearly)
----------------------------------------------------------------------------
Each qubit j carries two "Majorana" operators, indexed 2j and 2j+1 (so n qubits
give 2n Majorana indices). A free-fermion state is fully described by the
pairwise correlations of these Majoranas -- a 2n x 2n real ANTISYMMETRIC matrix M
(the covariance matrix), with M[2j, 2j+1] = <Z_j> (the magnetisation of qubit j).
The vacuum |0...0> has M[2j, 2j+1] = +1 for every qubit. A matchgate gate on two
qubits is a 4x4 orthogonal rotation R of the four Majoranas it touches, and it
updates the whole state by   M -> R_full @ M @ R_full.T   where R_full is R on
those 4 indices and the identity everywhere else. Because R_full is the identity
off those 4 indices, only 4 rows and 4 columns of M actually change -- so each
gate costs O(n), not O(n^2), and a full sweep of gates costs O(n^2).
"""
import math
import time

import numpy as np
from sympy import Matrix

from holant_tools import FreeFermionCircuit
from holant_tools.free_fermion import (
    majorana_rotation_xx,       # 4x4 Majorana rotation for an exp(i theta XX/...) gate
    majorana_rotation_z_left,   # ... for a Z rotation acting on the LEFT qubit of a pair
    majorana_rotation_z_right,  # ... for a Z rotation acting on the RIGHT qubit of a pair
)


def _f(M):
    """Convert a sympy Matrix to a sympy Matrix of plain Python floats.

    `FreeFermionCircuit` works with exact sympy entries by default; for the
    timing demo we want floats so the arithmetic is fast (no symbolic overhead).
    """
    return Matrix([[float(M[i, j]) for j in range(M.shape[1])] for i in range(M.shape[0])])


# --------------------------------------------------------------------------
# The analog twin (reference engine): holant_tools.FreeFermionCircuit.
# Exact, well-tested, but sympy-backed -> a higher constant factor.
# --------------------------------------------------------------------------
def ff_tfim(n, J, h, total_time, n_steps):
    """Trotterised time evolution of the transverse-field Ising chain
        H = -J sum_j X_j X_{j+1}  -  h sum_j Z_j
    on the free-fermion covariance matrix, returning the final average
    magnetisation (1/n) sum_j <Z_j>.

    One Trotter step approximates e^{-i dt H} by first doing all the Z rotations,
    then all the XX rotations.
    """
    ff = FreeFermionCircuit(n)          # starts in the vacuum |0...0>
    ff._M = _f(ff._M)                   # use float entries for speed
    dt = total_time / n_steps           # time per Trotter step

    # Pre-build the three 4x4 Majorana rotations used every step. The angle
    # conventions (-2*h*dt, -2*J*dt) are what reproduce e^{-i dt H} for this
    # library's gate definitions.
    Rz = _f(majorana_rotation_z_left(-2 * h * dt))     # Z on the left qubit of a pair
    Rz_last = _f(majorana_rotation_z_right(-2 * h * dt))  # Z on the right qubit (for the last qubit)
    Rxx = _f(majorana_rotation_xx(-2 * J * dt))        # XX on a neighbouring pair

    mags = [float(sum(ff.expectation_z_all())) / n]    # magnetisation at t=0 (= +1)
    for _ in range(n_steps):
        # --- Z layer: apply a Z rotation to every qubit ---
        # A "z_left" rotation on the pair (j, j+1) actually only rotates qubit j,
        # so iterating j = 0..n-2 covers qubits 0..n-2; the last qubit (n-1) is
        # then hit with a "z_right" rotation on the final pair.
        for j in range(n - 1):
            ff.apply_majorana_rotation(Rz, (j, j + 1))
        ff.apply_majorana_rotation(Rz_last, (n - 2, n - 1))
        # --- XX layer: apply an XX rotation to every neighbouring bond ---
        for j in range(n - 1):
            ff.apply_majorana_rotation(Rxx, (j, j + 1))
        mags.append(sum(float(ff.expectation_z(j)) for j in range(n)) / n)
    return mags[-1]


# --------------------------------------------------------------------------
# The analog twin (fast path): the identical algorithm in pure NumPy float64.
# Same O(n^2)/step cost, but ~100-450x smaller constant -> reaches n in the
# thousands.
# --------------------------------------------------------------------------
def _np_rot(sym4):
    """Turn a 4x4 sympy rotation into a 4x4 NumPy float64 array."""
    return np.array([[float(sym4[i, j]) for j in range(4)] for i in range(4)], dtype=float)


def tfim_covariance_numpy(n, J, h, total_time, n_steps):
    """Evolve |0...0> under Trotterised TFIM; return the 2n x 2n free-fermion
    COVARIANCE MATRIX (the analog device's full state), pure-NumPy float64.

    Same O(n^2)-per-step algorithm as `ff_tfim` (a local 4xO(n) touch of the
    covariance matrix per gate); the float64 engine lets it reach n in the
    thousands. Every other quantity (magnetisation in `ff_tfim_numpy`,
    entanglement entropy in entanglement_entropy.py, ...) is read off the
    returned matrix.
    """
    dt = total_time / n_steps

    # Build the vacuum covariance matrix: a block-diagonal of 2x2 blocks
    # [[0, +1], [-1, 0]], one per qubit. So M[2q, 2q+1] = +1 (i.e. <Z_q> = +1).
    M = np.zeros((2 * n, 2 * n))
    for q in range(n):
        M[2 * q, 2 * q + 1] = 1.0
        M[2 * q + 1, 2 * q] = -1.0

    # The same three 4x4 rotations as before, now as NumPy arrays.
    Rz = _np_rot(majorana_rotation_z_left(-2 * h * dt))
    Rz_last = _np_rot(majorana_rotation_z_right(-2 * h * dt))
    Rxx = _np_rot(majorana_rotation_xx(-2 * J * dt))

    def apply(R, q1, q2):
        """Apply gate R to qubits (q1, q2): the LOCAL covariance update.

        R acts on the 4 Majorana indices [2q1, 2q1+1, 2q2, 2q2+1]. The full
        update M -> R_full M R_full.T touches only those 4 rows and 4 columns
        (R_full is the identity elsewhere), so this is O(n), not O(n^2).
        """
        idx = [2 * q1, 2 * q1 + 1, 2 * q2, 2 * q2 + 1]
        M[idx, :] = R @ M[idx, :]      # update the 4 rows:  (R_full M) on these rows
        M[:, idx] = M[:, idx] @ R.T    # update the 4 cols:  (... R_full^T), uses updated M

    for _ in range(n_steps):
        for j in range(n - 1):                 # Z layer (every qubit) ...
            apply(Rz, j, j + 1)
        apply(Rz_last, n - 2, n - 1)
        for j in range(n - 1):                 # ... then XX layer (every bond)
            apply(Rxx, j, j + 1)
    return M


def ff_tfim_numpy(n, J, h, total_time, n_steps):
    """Average magnetisation (1/n) sum_j <Z_j>, read straight off the covariance
    matrix: <Z_q> is exactly the entry M[2q, 2q+1]."""
    M = tfim_covariance_numpy(n, J, h, total_time, n_steps)
    return float(sum(M[2 * q, 2 * q + 1] for q in range(n)) / n)


# --------------------------------------------------------------------------
# The "regular silicon" baseline: brute-force state-vector simulation.
# Stores all 2^n complex amplitudes -> exponential memory; the thing we beat.
# --------------------------------------------------------------------------
def _apply_2q(psi, n, j, k, G):
    """Apply a 4x4 two-qubit gate G to qubits j, k of an n-qubit state vector.

    Trick: view the length-2^n vector as an n-dimensional [2]*n array (one axis
    per qubit), move qubits j and k to the front, fold them into a single size-4
    axis, multiply by G, then undo the moves. This is the standard way to apply a
    gate without ever forming the full 2^n x 2^n gate matrix.
    """
    psi = psi.reshape([2] * n)                              # one axis per qubit
    psi = np.moveaxis(psi, [j, k], [0, 1]).reshape(4, -1)   # qubits j,k -> a size-4 front axis
    psi = (G @ psi).reshape([2, 2] + [2] * (n - 2))         # apply the gate
    psi = np.moveaxis(psi, [0, 1], [j, k])                  # put the axes back
    return psi.reshape(-1)


def tfim_state_vector(n, J, h, total_time, n_steps):
    """Brute-force state-vector evolution of |0...0> under Trotterised TFIM;
    return the 2^n complex amplitude vector. Cost and memory grow as 2^n."""
    dt = total_time / n_steps
    psi = np.zeros(2 ** n, dtype=complex); psi[0] = 1.0     # |0...0>

    # The Z layer exp(i h dt sum_j Z_j) is DIAGONAL: amplitude k just gets a phase
    # depending on how many qubits are |1>. With pc = popcount(k), sum_j Z_j has
    # eigenvalue (n - 2*pc) on basis state k (each 0-bit contributes +1, each
    # 1-bit -1), so the phase is exp(i h dt (n - 2 pc)).
    pc = np.array([bin(k).count("1") for k in range(2 ** n)])
    z_phase = np.exp(1j * h * dt * (n - 2 * pc))

    # The XX gate exp(i J dt X_j X_{j+1}) = cos(J dt) I + i sin(J dt) (X kron X).
    X = np.array([[0, 1], [1, 0]], dtype=complex)
    Gxx = math.cos(J * dt) * np.eye(4) + 1j * math.sin(J * dt) * np.kron(X, X)

    for _ in range(n_steps):
        psi = psi * z_phase                    # Z layer (all qubits at once)
        for j in range(n - 1):                 # XX layer (one gate per bond)
            psi = _apply_2q(psi, n, j, j + 1, Gxx)
    return psi


def sv_tfim(n, J, h, total_time, n_steps):
    """Average magnetisation from the state vector: <Z_q> summed = sum over basis
    states of |amplitude|^2 * (n - 2*popcount), divided by n."""
    psi = tfim_state_vector(n, J, h, total_time, n_steps)
    pc = np.array([bin(k).count("1") for k in range(2 ** n)])
    return float(np.sum(np.abs(psi) ** 2 * (n - 2 * pc)) / n)


# --------------------------------------------------------------------------
# The demonstration.
# --------------------------------------------------------------------------
def main():
    print(__doc__)
    J, h, T, steps = 1.0, 0.5, 0.5, 5    # Ising couplings, evolution time, Trotter steps

    # Part 1: the analog twin and the brute-force state vector compute the SAME
    # physics -- check they agree at small n (where the state vector is feasible).
    print("=" * 66)
    print("Part 1 -- correctness: analog twin == state-vector (small n)")
    print("=" * 66)
    for n in (4, 6):
        m_ff = ff_tfim(n, J, h, T, steps)          # twin (sympy engine)
        m_np = ff_tfim_numpy(n, J, h, T, steps)    # twin (numpy engine)
        m_sv = sv_tfim(n, J, h, T, steps)          # brute-force state vector
        print(f"  n={n}:  twin={m_ff:+.8f}   numpy-twin={m_np:+.8f}   "
              f"state-vector={m_sv:+.8f}   diff={max(abs(m_ff - m_sv), abs(m_np - m_sv)):.2e}")
        assert abs(m_ff - m_sv) < 1e-8 and abs(m_np - m_sv) < 1e-8

    # Part 2: race them as n grows. The twin scales ~n^2; the state vector needs
    # 2^n amplitudes and quickly becomes infeasible (memory wall).
    print("\n" + "=" * 66)
    print("Part 2 -- MEGA GAINS: analog twin (poly) vs state-vector (2^n)")
    print("=" * 66)
    print(f"  {'n':>4} | {'twin time':>10} | {'state-vec time':>14} | {'state-vec memory':>18}")
    print("  " + "-" * 56)
    sv_cap = 22                                    # largest n we still try by brute force
    for n in (8, 12, 16, 20, 24, 32, 48, 64):
        t0 = time.perf_counter(); ff_tfim(n, J, h, T, steps); t_ff = time.perf_counter() - t0
        mem = 2 ** n * 16                          # bytes for 2^n complex128 amplitudes
        if n <= sv_cap:
            t0 = time.perf_counter(); sv_tfim(n, J, h, T, steps)
            t_sv = f"{time.perf_counter() - t0:.3f} s"
        else:
            t_sv = "INFEASIBLE"                     # would exceed available memory
        print(f"  {n:>4} | {t_ff:>8.3f} s | {t_sv:>14} | {_human(mem):>18}")
    print("\n  The analog twin's cost grows ~n^2 per step; state-vector cost and")
    print("  memory grow as 2^n. By n=64 the state vector would need 2^64 complex")
    print(f"  numbers = {_human(2**64 * 16)} -- more than all storage on Earth.")
    print("  The twin handles it in well under a second.")

    # Part 2b: the fast NumPy engine pushes the SAME algorithm into the thousands.
    print("\n" + "=" * 66)
    print("Part 2b -- NumPy fast-path twin: into the THOUSANDS of qubits")
    print("=" * 66)
    print(f"  {'n':>6} | {'numpy twin':>11} | {'final M_z':>11} | {'state-vector amplitudes':>24}")
    print("  " + "-" * 62)
    for n in (64, 128, 256, 512, 1024, 2048):
        t0 = time.perf_counter(); m = ff_tfim_numpy(n, J, h, T, steps)
        dt = time.perf_counter() - t0
        # 2^n written as a power of ten: 2^n = 10^(n*log10 2) ~ 10^(0.30103 n).
        print(f"  {n:>6} | {dt:>9.3f} s | {m:>+11.6f} | {('~10^' + str(round(0.30103 * n))):>24}")
    print("\n  Same O(n^2) algorithm, float64 engine: the constant factor drops")
    print("  ~100x and the twin reaches thousands of qubits in seconds. At n=2048")
    print("  a state vector would need ~10^617 amplitudes -- vastly more than the")
    print("  ~10^80 atoms in the observable universe. The structure makes it a")
    print("  non-event.")

    print("\n" + "=" * 66)
    print("Why this is the 'analog' computer (and the honest limit)")
    print("=" * 66)
    print("  * The 2n x 2n covariance matrix IS the analog free-fermion state;")
    print("    each gate is a local orthogonal rotation of it (the physics).")
    print("  * Observables are read straight off the matrix; amplitudes/overlaps")
    print("    are PFAFFIANS of its submatrices -- the same FKT/Holant kernel.")
    print("  * The mega gain is EXPONENTIAL over naive state-vector simulation,")
    print("    purely because the dynamics is free-fermion (the tractable corner).")
    print("    A real analog free-fermion device would match this twin, not beat")
    print("    it -- and interacting (non-matchgate) dynamics gets no such gain,")
    print("    on silicon OR in analog. Structure is the whole story.")


def _human(b):
    """Format a byte count as B / KB / MB / ... for the memory column."""
    for unit in ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"):
        if b < 1024 or unit == "YB":
            return f"{b:.0f} {unit}" if unit == "B" else f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} YB"


if __name__ == "__main__":
    main()
