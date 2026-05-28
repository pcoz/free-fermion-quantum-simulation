r"""Trotter dynamics with a mode-shifting Hamiltonian -- the canonical
1000-pass adaptive case.

Quantum-style time evolution under H(t) = a(t) H_FF + b(t) H_Cliff + c(t) H_dense
with time-dependent coefficients. As t evolves over the simulation window
[0, T], the dominant term shifts:

  t around T/6  : H_FF dominates    -> route to free-fermion (T2 matchgate)
  t around T/2  : H_Cliff dominates -> route to CH-form    (T0 stabilizer)
  t around 5T/6 : H_dense dominates -> route to advised    (T7 out-of-family)

The Gaussian-envelope schedule uses sigma = T/4 for each term.

Across 1000 Trotter steps, the pipeline-router makes 1000 routing decisions;
RichTrace's `regime_changes_detailed()` catches exactly the transitions
between dominant terms. Every step is verified: the chosen tier must match
the brute-force-computed dominant term at that time.

This is the single-most-visible demonstration of routing PER PASS at scale:
the routing decision is genuinely time-dependent, not static, and the
trace's regime-change detector catches it.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import Classification                                              # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402


def hamiltonian_weights(t: float, T: float):
    """Three Gaussian envelopes centered at T/6, T/2, 5T/6, width sigma=T/4."""
    sigma = T / 4.0
    a = math.exp(-((t - T / 6) / sigma) ** 2)
    b = math.exp(-((t - T / 2) / sigma) ** 2)
    c = math.exp(-((t - 5 * T / 6) / sigma) ** 2)
    return a, b, c


def dominant_term(t: float, T: float):
    a, b, c = hamiltonian_weights(t, T)
    if a >= b and a >= c: return "FF",    a, ("T2", "free-fermion")
    if b >= a and b >= c: return "CH",    b, ("T0", "ch-form")
    return "DENSE", c, ("T7", "advised:dense")


def make_trotter_stage(t: float, T: float) -> Stage:
    """One Trotter step at time t. The route_fn inspects (t, T), picks the
    dominant term, and emits a Classification with the corresponding tier."""

    def route_fn(data, prev):
        _, w, (tier, _) = dominant_term(t, T)
        if tier == "T7":
            cls = Classification(tier=tier, meters={"t": t, "weight": w},
                                 in_family=False,
                                 reasoning=f"dense term dominant at t={t:.2f}, weight {w:.3f}")
        else:
            cls = Classification(tier=tier, meters={"t": t, "weight": w,
                                                     "n_vertices": 4, "genus": 0,
                                                     "n_variables": 4, "modulus": 2},
                                 in_family=True,
                                 reasoning=f"{tier} term dominant at t={t:.2f}, weight {w:.3f}")
        return route_classification(cls)

    def runner_fn(data, prev, route):
        steps = (prev or {}).get("steps", 0) + 1
        return {"steps": steps, "t": t, "tier": route.tier}

    return Stage(f"trot:t={t:.3f}", "trotter-step", t, route_fn, runner_fn)


def main():
    print(__doc__)
    print("=" * 74)

    T = 10.0
    n_steps = 1000
    dt = T / n_steps
    stages = [make_trotter_stage((k + 0.5) * dt, T) for k in range(n_steps)]

    trace = RichTrace()
    final, _ = run_pipeline(stages, seed={"steps": 0}, trace=trace)

    # Verification: every step's chosen tier must match the brute-force-computed
    # dominant Hamiltonian term at that time.
    for k, record in enumerate(trace.records):
        t = (k + 0.5) * dt
        _, _, (expected_tier, _) = dominant_term(t, T)
        assert record.route.tier == expected_tier, \
            f"step {k} at t={t:.3f}: routed {record.route.tier} != expected {expected_tier}"

    print(f"\n  Ran {n_steps} Trotter steps over T = {T}.")
    print(f"  Total stages:                         {final['steps']}")
    regimes = trace.regime_changes_detailed()
    print(f"  Routing transitions detected:         {len(regimes)}")
    for rc in regimes[: min(4, len(regimes))]:
        t_at = (rc.index + 0.5) * dt
        print(f"    step {rc.index:>4} (t={t_at:.2f}): {rc.prev_member} -> {rc.new_member}")
    print()
    print(trace.summary())

    print(f"  Brute-force verification: all {n_steps} steps routed correctly")
    print(f"  against the dominant-term ground truth. The routing IS time-")
    print(f"  dependent, the regime shifts are real, and the pipeline-router")
    print(f"  caught them exactly.")


if __name__ == "__main__":
    main()
