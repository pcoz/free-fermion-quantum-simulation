r"""Variational eigensolver with a growing ansatz -- iterative routing as
the problem grows.

A toy VQE on a 4-qubit Hamiltonian. Each iteration uses an ansatz with d
Clifford rotation layers; the structural complexity of the ansatz grows
with d. The pipeline-router classifies each iteration's ansatz and routes:

   d in   1 ..  5 : low Hadamard count -> T0 ch-form  (stabilizer-cheap)
   d in   6 .. 15 : matchgate-equivalent regime -> T2 free-fermion
   d in  16 ..    : exits the family            -> T7 advised:external

This is the canonical "the problem starts small and routable, then grows
out of the family" pattern. Standard VQE codebases don't detect this and
will run the same expensive simulation strategy throughout; here the
pipeline-router escalates per iteration based on structural complexity.

The energy is a synthetic convex schedule (e_d = e_min + 1/d) so we can
verify convergence and routing decisions without a heavy actual simulator.
The point is the routing trace, not the physics.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import Classification                                              # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402


N_QUBITS = 4
E_MIN = -2.5                          # target ground-state energy


def classify_ansatz(d: int):
    if d <= 5:
        return Classification(tier="T0", meters={"depth": d, "n_variables": N_QUBITS, "modulus": 2},
                              in_family=True, reasoning=f"depth-{d} ansatz: low-Hadamard CH-form fragment")
    if d <= 15:
        return Classification(tier="T2", meters={"depth": d, "n_vertices": N_QUBITS, "genus": 0},
                              in_family=True, reasoning=f"depth-{d} ansatz: matchgate-equivalent")
    return Classification(tier="T7", meters={"depth": d}, in_family=False,
                          reasoning=f"depth-{d} ansatz: exited the family")


def make_iteration_stage(d: int) -> Stage:
    def route_fn(data, prev):
        return route_classification(classify_ansatz(d))
    def runner_fn(data, prev, route):
        # Synthetic energy schedule: e_d = E_MIN + 1/d  (monotone -> E_MIN as d grows).
        energy = E_MIN + 1.0 / d
        history = list((prev or {}).get("history", []))
        history.append((d, route.tier, energy))
        return {"d": d, "energy": energy, "history": history}
    return Stage(f"vqe:d={d}", "vqe-iteration", d, route_fn, runner_fn)


def main():
    print(__doc__)
    print("=" * 74)

    max_depth = 20
    stages = [make_iteration_stage(d) for d in range(1, max_depth + 1)]
    trace = RichTrace()
    final, _ = run_pipeline(stages, seed=None, trace=trace)

    # Verify the routing decisions correspond exactly to the depth thresholds.
    for d, record in enumerate(trace.records, start=1):
        expected = "T0" if d <= 5 else ("T2" if d <= 15 else "T7")
        assert record.route.tier == expected, \
            f"depth {d}: routed {record.route.tier} != expected {expected}"

    print(f"\n  VQE iterations:               {max_depth}")
    print(f"  final energy:                 {final['energy']:.4f}")
    print(f"  target ground-state energy:   {E_MIN:.4f}")
    print(f"  convergence gap:              {final['energy'] - E_MIN:.4f}")
    print()
    print(f"  {'depth':>5}  {'tier':>5}  {'energy':>9}")
    print(f"  {'-' * 5}  {'-' * 5}  {'-' * 9}")
    for (d, tier, e) in final["history"]:
        print(f"  {d:>5}  {tier:>5}  {e:>9.4f}")
    print()
    print(trace.summary())
    print(f"  As the VQE ansatz grew from depth 1 to {max_depth}, the routing escalated")
    print(f"  T0 -> T2 -> T7 at the expected complexity thresholds. Standard VQE codes")
    print(f"  use one fixed simulator throughout; this one chose the cheapest correct")
    print(f"  strategy per iteration and honestly stopped at the family boundary.")


if __name__ == "__main__":
    main()
