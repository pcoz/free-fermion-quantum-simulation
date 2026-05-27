r"""Benchmark a quantum processor against an EXACT reference -- at a scale where
no other classical reference exists.

The workflow exactness unlocks
------------------------------
To trust a quantum computer you must compare its output to a known-correct
answer. For a generic circuit the only classical reference is the full 2^n state
vector -- impossible past ~30 qubits -- so large-scale hardware validation has no
ground truth to check against. But MATCHGATE (free-fermion) circuits are
classically EXACT at any size, and this repo computes their observables exactly.
That hands quantum-hardware QA a certified reference for the standard
free-fermion benchmarking class, to hundreds of qubits.

Why EXACTNESS is the whole point here
-------------------------------------
You can only certify a device to the accuracy of your reference. A sampled or
truncated (e.g. tensor-network) classical reference carries its OWN error, which
you cannot separate from the device's error -- so you can't set a real tolerance.
An EXACT reference has zero error, so every observed deviation IS hardware error.
Combined with "no 2^n reference exists at this scale", that makes acceptance
testing of free-fermion circuits on a 128-qubit processor a workflow you simply
cannot run today by any other means.

(Here we *simulate* a noisy device reading as exact + shot noise + a small
hardware drift, so the script is self-contained. In practice the device value
comes from the real processor; the reference -- the part that matters -- is exact.)

Run:  python quantum_device_benchmark.py
"""
import numpy as np

from ff_analog_twin import tfim_covariance_numpy


def exact_magnetisations(n, J, h, T, steps):
    """The certified ground truth: exact <Z_q>(T) for every qubit, read off the
    free-fermion covariance matrix (<Z_q> = M[2q, 2q+1])."""
    M = tfim_covariance_numpy(n, J, h, T, steps)
    return np.array([M[2 * q, 2 * q + 1] for q in range(n)])


def simulated_device_run(exact, rng, shots, gate_error):
    """Stand-in for a real quantum processor's measured <Z_q>: the true value
    plus (a) shot noise ~ 1/sqrt(shots) and (b) a small per-qubit hardware drift.
    In a real run this whole function is replaced by the device's output."""
    shot_noise = rng.normal(0.0, 1.0 / np.sqrt(shots), size=exact.shape)
    drift = gate_error * rng.standard_normal(exact.shape)
    return np.clip(exact + shot_noise + drift, -1.0, 1.0)


def main():
    print(__doc__)
    n, J, h, T, steps = 128, 1.0, 0.6, 2.0, 40
    tol = 0.03                                   # acceptance tolerance per qubit

    # 1. the exact reference (classically certified, any scale for this class)
    exact = exact_magnetisations(n, J, h, T, steps)

    # 2. a (simulated) run of the same circuit on a quantum processor
    rng = np.random.default_rng(0)
    device = simulated_device_run(exact, rng, shots=10_000, gate_error=0.012)

    # 3. the acceptance test -- only meaningful because the reference is EXACT
    err = np.abs(device - exact)
    failing = np.where(err > tol)[0]
    print("=" * 70)
    print(f"Acceptance test: {n}-qubit free-fermion circuit, tolerance {tol} per qubit")
    print("=" * 70)
    print(f"  max per-qubit error  : {err.max():.4f}")
    print(f"  mean per-qubit error : {err.mean():.4f}")
    print(f"  qubits over tolerance: {len(failing)} of {n}"
          + (f"  -> {[int(x) for x in failing[:8]]}{' ...' if len(failing) > 8 else ''}" if len(failing) else ""))
    print(f"  VERDICT: {'PASS' if len(failing) == 0 else 'FAIL (device out of spec on those qubits)'}")

    # 4. why exactness is load-bearing
    print("\n" + "=" * 70)
    print("Why exactness enables this (and what's impossible without it)")
    print("=" * 70)
    print(f"  * No brute-force reference exists: the state vector would need")
    print(f"    2^{n} ~ 10^{round(0.30103 * n)} amplitudes.")
    print("  * Because the reference is EXACT, every deviation above is genuine")
    print("    hardware error -- so the tolerance is meaningful. With an")
    print("    approximate reference of error e_ref, you could not certify the")
    print("    device below e_ref, and at this depth a tensor-network reference")
    print("    carries uncontrolled truncation error.")
    # demonstrate the point: a noisy reference would mis-certify
    noisy_ref = exact + rng.normal(0.0, tol, size=exact.shape)   # a 'reference' as bad as the tol
    misjudged = np.sum((np.abs(device - noisy_ref) > tol) != (err > tol))
    print(f"  * Demonstration: a reference with error ~{tol} would mis-classify")
    print(f"    {misjudged} of {n} qubits (pass<->fail) versus the exact reference")
    print("    -- you literally cannot run the QA without an exact ground truth.")

    print("\n  Scope: this is the free-fermion / matchgate benchmarking class, where")
    print("  the exact reference is classically tractable. Interacting circuits get")
    print("  no such reference -- which is exactly why they are candidates for")
    print("  genuine quantum advantage.")


if __name__ == "__main__":
    main()
