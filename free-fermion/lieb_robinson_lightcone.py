r"""The speed limit on information: a Lieb-Robinson "light cone" in a quantum
chain, computed exactly for hundreds of qubits on a laptop.

Why this matters
----------------
Relativity says nothing travels faster than light. Quantum many-body systems have
their OWN emergent speed limit (the Lieb-Robinson bound): after you disturb one
spot, correlations cannot appear arbitrarily far away instantly -- they spread at
a finite velocity, carving out a "light cone" in space-time. This underpins how
fast quantum information / entanglement can propagate, and it's a live concern in
designing quantum simulators and understanding thermalisation in materials.

We measure it with the connected two-point correlation between site 0 and site r,
    C(0, r, t) = <Z_0 Z_r> - <Z_0><Z_r>,
as the chain evolves. Starting from a product state (no correlations anywhere),
C(0, r, t) stays ~0 until time ~ r / v, then switches on -- the edge of the cone.

Why it's normally impossible, and why it's easy here
----------------------------------------------------
<Z_0 Z_r> normally needs the full 2^n quantum state. But our chain is a
free-fermion system, so every correlation is read off the 2n x 2n covariance
matrix by Wick's theorem -- no 2^n anywhere. We reuse this repo's engine
(`ff_analog_twin.tfim_covariance_numpy`) and reach n = 256 in seconds.

Run:  python lieb_robinson_lightcone.py
"""
import numpy as np

from ff_analog_twin import tfim_covariance_numpy, tfim_state_vector


def connected_zz(M, i, j):
    """Connected correlation C(i,j) = <Z_i Z_j> - <Z_i><Z_j>, read off the
    free-fermion covariance matrix M via Wick's theorem.

    With Majorana indices 2k, 2k+1 for qubit k (and <Z_k> = M[2k, 2k+1]), Wick's
    theorem gives the connected part purely from the cross-blocks of M:
        C(i,j) = M[2i, 2j+1] * M[2i+1, 2j]  -  M[2i, 2j] * M[2i+1, 2j+1].
    """
    a, b, c, d = 2 * i, 2 * i + 1, 2 * j, 2 * j + 1
    return float(M[a, d] * M[b, c] - M[a, c] * M[b, d])


def connected_zz_statevector(psi, n, i, j):
    """The same correlation the brute-force way, from the full 2^n state vector
    (only used to check the fast method at small n)."""
    k = np.arange(2 ** n)
    # qubit q's Z eigenvalue on basis state k (+1 if bit q is 0, else -1);
    # qubit 0 is the most-significant bit (matches the state-vector layout).
    zi = 1 - 2 * ((k >> (n - 1 - i)) & 1)
    zj = 1 - 2 * ((k >> (n - 1 - j)) & 1)
    p = np.abs(psi) ** 2
    ezi, ezj = float(p @ zi), float(p @ zj)
    ezizj = float(p @ (zi * zj))
    return ezizj - ezi * ezj


def main():
    print(__doc__)
    J, h = 1.0, 0.6

    # --- Part 1: the fast (covariance) correlation matches brute force ---
    print("=" * 70)
    print("Part 1 -- correctness: covariance correlation == state-vector")
    print("=" * 70)
    n, T, steps = 8, 1.5, 30
    M = tfim_covariance_numpy(n, J, h, T, steps)
    psi = tfim_state_vector(n, J, h, T, steps)
    worst = 0.0
    for (i, j) in [(0, 1), (0, 2), (0, 3), (1, 4)]:
        c_ff = connected_zz(M, i, j)
        c_sv = connected_zz_statevector(psi, n, i, j)
        worst = max(worst, abs(c_ff - c_sv))
        print(f"  C(Z_{i},Z_{j}):  covariance={c_ff:+.6e}   state-vector={c_sv:+.6e}")
    print(f"  max difference: {worst:.1e}")
    assert worst < 1e-9

    # --- Part 2: draw the light cone (space x time) ---
    print("\n" + "=" * 70)
    print("Part 2 -- the light cone: |C(0, r, t)| over distance r and time t")
    print("=" * 70)
    n, steps = 48, 60
    times = np.linspace(0.0, 8.0, 17)[1:]        # 16 snapshots
    thresh = 1e-3                                  # "correlation has switched on"
    print("  rows = time (increasing downward); columns = distance r from site 0;")
    print(f"  '#' = |C(0,r,t)| > {thresh:g} (correlated); '.' = still ~0.\n")
    print("        r = " + "".join(str(r % 10) for r in range(n)))
    for t in times:
        M = tfim_covariance_numpy(n, J, h, t, max(2, int(steps * t / 8.0)))
        row = "".join("#" if abs(connected_zz(M, 0, r)) > thresh else "." for r in range(n))
        print(f"  t={t:4.1f} : {row}")
    print("\n  The boundary between '#' and '.' is the light cone: correlations")
    print("  reach distance r only after a time proportional to r. Its slope is")
    print("  the Lieb-Robinson velocity -- the system's emergent 'speed of light'.")

    # --- Part 3: what EXACTNESS unlocks (a workflow sampling cannot do) ---
    print("\n" + "=" * 70)
    print("Part 3 -- what exactness unlocks: structure ~10 orders below the noise")
    print("=" * 70)
    n3, t3, steps3 = 48, 3.0, 40
    M = tfim_covariance_numpy(n3, J, h, t3, steps3)
    print(f"  Exact |C(0, r, t={t3})| around the cone edge. A quantum device or a")
    print("  Monte-Carlo estimate of <Z_0 Z_r> has shot noise ~ 1/sqrt(shots);")
    print("  even 1,000,000 shots cannot resolve a correlation below ~1e-3.\n")
    print(f"  {'r':>4} | {'exact |C|':>11} | visible to a 1e6-shot estimate?")
    print("  " + "-" * 52)
    for r in range(7, 21):
        c = abs(connected_zz(M, 0, r))
        verdict = "yes" if c > 1e-3 else "NO  (buried in sampling noise)"
        print(f"  {r:>4} | {c:>11.2e} | {verdict}")
    print("\n  Exactness reaches ~10 orders of magnitude below the sampling floor,")
    print("  exposing the smooth exponential 'precursor' tail beyond the cone that")
    print("  any sampled or noisy method sees as flat zero. NEW WORKFLOW: measure")
    print("  the propagation front AND its weak precursors precisely -- and use the")
    print("  exact values as a certified reference to validate a real quantum")
    print("  simulator (see quantum_device_benchmark.py).")

    # --- Part 4: a scale a brute-force simulator could never reach ---
    print("\n" + "=" * 70)
    print("Part 4 -- the same physics at n = 256 (brute force: 2^256 amplitudes)")
    print("=" * 70)
    import time as _time
    n, T, steps = 256, 4.0, 80
    t0 = _time.perf_counter()
    M = tfim_covariance_numpy(n, J, h, T, steps)
    edge = max((r for r in range(n) if abs(connected_zz(M, 0, r)) > 1e-3), default=0)
    dt = _time.perf_counter() - t0
    print(f"  evolved {n} qubits to t={T}; correlations have reached distance "
          f"r = {edge}   [{dt:.2f}s]")
    print(f"  a brute-force state vector would need 2^{n} ~ 10^{round(0.30103*n)} numbers.")

    print("\n" + "=" * 70)
    print("Honest scope")
    print("=" * 70)
    print("  Exact and fast because the chain is FREE-FERMION (correlations come")
    print("  from a 2n x 2n covariance matrix via Wick's theorem). Add an")
    print("  interacting (non-matchgate) term and you lose this -- correlations no")
    print("  longer close on the covariance matrix, and you're back to 2^n.")


if __name__ == "__main__":
    main()
