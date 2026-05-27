r"""A practical computation that is IMPOSSIBLE by brute force, on a laptop:
the entanglement entropy of a 512-qubit quantum chain.

This is a worked example built on THIS repo's own free-fermion engine
(`ff_analog_twin.tfim_covariance_numpy`) -- the impossible running on silicon.

What is entanglement entropy, and why care?
-------------------------------------------
Split a quantum system into two halves, A and B. The "entanglement entropy" S_A
is a single number measuring how quantum-correlated the two halves are -- 0 if
they're independent, large if they're deeply entangled. It is one of the most
important quantities in modern physics and quantum information: it tells you how
hard a state is to compress, whether a material is in an exotic phase, and how
fast quantum information spreads.

Why it's normally impossible
-----------------------------
Computing S_A normally needs the full quantum state -- 2^n complex numbers for n
qubits. At n=256 that already exceeds the number of atoms in the universe, so for
a few hundred qubits it simply cannot be done by brute force on any computer.

Why we can do it here
---------------------
Our system (a transverse-field Ising chain) is a FREE-FERMION system, so its
entire state lives in a small 2n x 2n covariance matrix. The entanglement entropy
of a region is then read straight off that matrix: take the sub-block for the
region, find its eigenvalues, and plug them into a one-line formula
(Vidal-Latorre-Rico-Kitaev / Peschel). Cost: O(n^3) for the eigenvalues -- a
non-event up to thousands of qubits.

Run:  python entanglement_entropy.py
"""
import math
import time

import numpy as np

# Re-use THIS repo's own free-fermion engine: the covariance-matrix evolution
# (fast path) and the brute-force state vector (for the correctness check).
from ff_analog_twin import tfim_covariance_numpy, tfim_state_vector


def _binary_entropy(p):
    """The binary (Shannon/von Neumann) entropy function H(p), in nats:
        H(p) = -p ln p - (1-p) ln(1-p).
    We clip p away from 0 and 1 so the logs never blow up (the limits are 0)."""
    p = np.clip(p, 1e-15, 1.0 - 1e-15)
    return -p * np.log(p) - (1.0 - p) * np.log(1.0 - p)


def entanglement_entropy_covariance(M, n_A):
    """Entanglement entropy (in nats) of region A = qubits 0..n_A-1, read off the
    free-fermion covariance matrix M.

    The recipe (Vidal-Latorre-Rico-Kitaev 2003 / Peschel 2003):
      1. Region A occupies Majorana indices 0, 1, ..., 2*n_A - 1, so its
         covariance is the top-left 2n_A x 2n_A sub-block of M.
      2. That real antisymmetric sub-block has eigenvalues +-i*nu_k, where the
         n_A "occupation-like" numbers nu_k lie in [0, 1].
      3. Each mode contributes H((1 + nu_k)/2) to the entropy.

    Implementation note: numpy returns all 2*n_A eigenvalues, and they come in
    +-pairs of equal magnitude, so each nu_k shows up twice. We therefore sum the
    contribution over all 2*n_A of them and multiply by 1/2.
    """
    k = 2 * n_A
    sub = M[:k, :k]                                  # covariance of region A
    nu = np.clip(np.abs(np.linalg.eigvals(sub)), 0.0, 1.0)   # the |+-i nu_k| values
    return 0.5 * float(np.sum(_binary_entropy((1.0 + nu) / 2.0)))


def entanglement_entropy_state_vector(psi, n, n_A):
    """Entanglement entropy (in nats) of the first n_A qubits, the BRUTE-FORCE
    way: from the full 2^n amplitude vector via the Schmidt decomposition.

    Reshape the state into a (2^n_A) x (2^(n-n_A)) matrix (rows = region A's basis
    states, columns = the rest), take its singular values s; the squared singular
    values p = s^2 are the Schmidt probabilities, and S = -sum p ln p.
    This is only feasible for small n -- it's exactly the wall we're beating.
    """
    mat = psi.reshape(2 ** n_A, 2 ** (n - n_A))
    s = np.linalg.svd(mat, compute_uv=False)         # singular values only
    p = s ** 2
    p = p[p > 1e-15]                                 # drop ~zero probabilities
    return float(-np.sum(p * np.log(p)))


def _amp_str(n):
    """How many amplitudes a brute-force state vector would need, as a power of
    ten: 2^n = 10^(n * log10 2) ~ 10^(0.30103 n)."""
    return "~10^" + str(round(0.30103 * n))


def main():
    print(__doc__)
    # Transverse-field Ising chain parameters: coupling J, field h, evolve to
    # time T in `steps` Trotter steps. Starting state is the product |0...0>.
    J, h, T, steps = 1.0, 0.6, 2.0, 20

    # ---- Part 1: prove the fast method computes the right number ----
    # At small n the brute-force state vector is feasible, so we can check the
    # covariance-matrix entropy against the exact Schmidt entropy.
    print("=" * 68)
    print("Part 1 -- correctness: free-fermion entropy == brute-force entropy")
    print("=" * 68)
    for n in (6, 8):
        nA = n // 2                                          # cut the chain in half
        M = tfim_covariance_numpy(n, J, h, T, steps)         # fast: covariance matrix
        psi = tfim_state_vector(n, J, h, T, steps)           # slow: full 2^n state
        s_ff = entanglement_entropy_covariance(M, nA)
        s_sv = entanglement_entropy_state_vector(psi, n, nA)
        print(f"  n={n}, half={nA}:  free-fermion S={s_ff:.10f}   "
              f"state-vector S={s_sv:.10f}   diff={abs(s_ff - s_sv):.1e}")
        assert abs(s_ff - s_sv) < 1e-9                       # they must agree

    # ---- Part 2: the same computation at sizes brute force can never reach ----
    print("\n" + "=" * 68)
    print("Part 2 -- THE IMPOSSIBLE: half-chain entanglement entropy at scale")
    print("=" * 68)
    print(f"  {'qubits':>7} | {'compute time':>12} | {'entropy S (nats)':>16} | "
          f"{'brute-force state':>18}")
    print("  " + "-" * 62)
    for n in (16, 32, 64, 128, 256, 512):
        nA = n // 2
        t0 = time.perf_counter()
        M = tfim_covariance_numpy(n, J, h, T, steps)         # evolve (fast path)
        s = entanglement_entropy_covariance(M, nA)           # read entropy off M
        dt = time.perf_counter() - t0
        print(f"  {n:>7} | {dt:>10.3f} s | {s:>16.6f} | {_amp_str(n) + ' numbers':>18}")
    print("\n  At 256 qubits the brute-force state already needs ~10^77 numbers --")
    print("  about the number of atoms in the observable universe. We computed the")
    print("  512-qubit entanglement entropy on a laptop, in well under a second.")
    print("  (The entropy is ~constant across n: after a fixed evolution time the")
    print("   entanglement only reaches a finite distance from the cut, so once the")
    print("   chain is long enough the half-chain value no longer depends on n.)")

    # ---- Part 3: the actual physics -- entanglement spreads after a quench ----
    print("\n" + "=" * 68)
    print("Part 3 -- the physics: entanglement growth after a quench (n=128)")
    print("=" * 68)
    print(f"  {'time t':>7} | {'entropy S (nats)':>16}")
    print("  " + "-" * 28)
    n, nA = 128, 64
    for t in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0):
        st = max(1, int(steps * t / T)) if t > 0 else 1     # keep the step size ~constant
        M = tfim_covariance_numpy(n, J, h, max(t, 1e-9), st)
        s = entanglement_entropy_covariance(M, nA)
        print(f"  {t:>7.2f} | {s:>16.6f}")
    print("\n  Starting from a product state (S=0), entanglement spreads across the")
    print("  chain as it evolves -- the hallmark of quantum dynamics, computed here")
    print("  at a system size no brute-force simulator could ever reach.")


if __name__ == "__main__":
    main()
