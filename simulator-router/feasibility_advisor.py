r"""For developers: "Can I simulate this quantum circuit on my machine, and how?"

You do NOT need to know any quantum physics to use this. Say you're building an app
that calls a quantum subroutine, or you've been handed a circuit and asked "can we
just run it on a laptop instead of paying for a quantum device?" Before you spin up
an expensive simulation (or expensive hardware), run this advisor on the circuit.

It is a thin, plain-English front-end to the tractability router in
`simulator_router.py`. It reads the circuit's *structure* (you don't have to
understand the structure) and prints:

  * which off-the-shelf simulator to reach for,
  * a rough estimate of how long it would take and whether it fits in memory,
  * a one-line, jargon-free reason, and
  * a clear verdict: laptop job / workstation job / cluster job / not feasible
    classically (i.e. genuinely needs a quantum computer).

Run:  python feasibility_advisor.py
      python feasibility_advisor.py examples/clifford_t.qasm   # advise on your own circuit
"""
import math
import os
import sys

# Reuse the router itself -- the advisor is just a human-friendly layer on top.
from simulator_router import (estimate_costs, load_circuit, tfim_trotter,
                              clifford_circuit, shallow_generic, dense_random)

OPS_PER_SECOND = 1e9          # a rough "ops per second" for a single modern core

# What each method means in practical, tooling terms (no physics required).
RECOMMENDED_TOOL = {
    "state vector":   "a standard state-vector simulator (e.g. Qiskit Aer)",
    "stabilizer":     "a stabilizer simulator (e.g. Stim, or Qiskit StabilizerState)",
    "free fermion":   "a free-fermion / matchgate simulator (covariance-matrix based)",
    "tensor network": "a tensor-network simulator (e.g. quimb or ITensor)",
}


def human_time(n_ops):
    """Turn an operation count into a human-readable duration estimate."""
    seconds = n_ops / OPS_PER_SECOND
    if seconds < 1e-3:
        return "under a millisecond"
    if seconds < 1:
        return f"about {seconds * 1e3:.0f} ms"
    if seconds < 90:
        return f"about {seconds:.0f} seconds"
    if seconds < 90 * 60:
        return f"about {seconds / 60:.0f} minutes"
    if seconds < 48 * 3600:
        return f"about {seconds / 3600:.0f} hours"
    if seconds < 3 * 365 * 24 * 3600:
        return f"about {seconds / (24 * 3600):.0f} days"
    return "longer than the age of the universe"


def human_memory(n_qubits):
    """Memory a *state-vector* simulator needs: 16 bytes per amplitude, 2^n of them."""
    n_bytes = 16 * (2.0 ** n_qubits)
    for unit in ("bytes", "KB", "MB", "GB", "TB", "PB"):
        if n_bytes < 1024 or unit == "PB":
            return f"{n_bytes:.0f} {unit}" if unit == "bytes" else f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.0f} PB"


def plain_reason(method, meters):
    """One jargon-free sentence on why this method is the cheap one for this circuit."""
    t, k, w = meters["t"], meters["k"], meters["w"]
    if method == "stabilizer":
        return (f"only {t} of your gates are the 'hard' kind for this simulator, so it "
                f"stays cheap even for thousands of qubits.")
    if method == "free fermion":
        return (f"your gates are all the 'non-interacting' kind ({k} are not), which this "
                f"simulator handles exactly for thousands of qubits, however tangled the state.")
    if method == "tensor network":
        return (f"your circuit barely mixes its two halves (a 'width' of just {w}), which "
                f"keeps this simulator cheap; it gets dear as that width grows.")
    return ("your circuit has no special structure the cheaper simulators can exploit, so "
            "it falls back to brute force (fine up to ~30 qubits, then memory runs out).")


def advise(name, circuit, n_qubits):
    """Print plain-English guidance for one circuit."""
    costs, meters = estimate_costs(circuit, n_qubits)
    method, (log2_ops, _) = min(costs.items(), key=lambda kv: kv[1][0])
    n_ops = 2.0 ** log2_ops

    # Verdict tiers, by the (log2 of the) operation count the cheapest method needs.
    if log2_ops <= 20:
        verdict = "LAPTOP JOB -- runs almost instantly."
    elif log2_ops <= 33:
        verdict = "LAPTOP JOB -- runs in seconds."
    elif log2_ops <= 40:
        verdict = "WORKSTATION JOB -- minutes to hours; mind the RAM."
    elif log2_ops <= 50:
        verdict = "CLUSTER / CLOUD JOB -- hours to days, and a lot of memory."
    else:
        verdict = "NOT FEASIBLE CLASSICALLY -- this is what real quantum hardware is for."

    print(f"  circuit: {name}  ({n_qubits} qubits, {len(circuit)} gates)")
    print(f"    -> verdict     : {verdict}")
    print(f"    -> best tool   : {RECOMMENDED_TOOL[method]}")
    print(f"    -> rough cost  : ~2^{log2_ops:.0f} operations ({human_time(n_ops)})")
    if method == "state vector":
        print(f"    -> memory note : a state vector needs {human_memory(n_qubits)} of RAM")
    print(f"    -> why         : {plain_reason(method, meters)}")
    print()


def main():
    print(__doc__)

    # A developer was handed a path to a circuit file: advise on just that one.
    if len(sys.argv) > 1:
        circuit, n = load_circuit(sys.argv[1])
        print("=" * 74)
        advise(os.path.basename(sys.argv[1]), circuit, n)
        return

    print("=" * 74)
    print("Pre-flight check on a batch of circuits (no quantum expertise required)")
    print("=" * 74)
    # A realistic mix a developer might face -- note the sizes are large on purpose,
    # to show the advisor sorting the feasible from the hopeless.
    advise("error-correction-style circuit (Clifford)", clifford_circuit(500, 40), 500)
    advise("physics dynamics circuit (free-fermion)", tfim_trotter(800, 60), 800)
    advise("shallow data-encoding circuit", shallow_generic(120, 2), 120)
    advise("deep, dense, general-purpose circuit", dense_random(60, 60), 60)
    if os.path.exists("examples/clifford_t.qasm"):
        circ, n = load_circuit("examples/clifford_t.qasm")
        advise("examples/clifford_t.qasm (your own file)", circ, n)

    print("=" * 74)
    print("Takeaway")
    print("=" * 74)
    print("  Same question for every circuit -- 'how do I run this?' -- and the advisor")
    print("  answers without you knowing a thing about the physics. It reads the")
    print("  structure, names the right off-the-shelf tool, and tells you up front when a")
    print("  circuit is simply out of reach for any classical machine. Point it at your")
    print("  own circuit:  python feasibility_advisor.py path/to/circuit.qasm")


if __name__ == "__main__":
    main()
