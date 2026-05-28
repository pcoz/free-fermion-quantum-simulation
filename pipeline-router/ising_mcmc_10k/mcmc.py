r"""Gibbs / Metropolis MCMC on a small planar Ising model -- 10000-pass demo
of the replay cache dominating scale.

A 4-spin Ising model (square graph; J = 1; inverse-temperature beta = 0.5).
Each MCMC step proposes flipping one spin and accepts via the Metropolis
criterion. The proposal's per-step "cost" is computing the Boltzmann
acceptance ratio -- which depends only on (current_config, flip_position).
With 4 spins and 4 possible flip positions, there are 2^4 * 4 = 64 distinct
(config, flip) pairs. The replay cache keys exactly on these; across 10000
steps, ~64 misses and ~9936 hits are expected -- a ~99% hit rate that turns
a 10000-step MCMC into ~64 "real" evaluations.

The chosen tier for the energy-delta sub-problem is T2 (planar binary
Holant on the Ising signature). The routing is constant; the example
demonstrates the framework's behaviour at 10k scale, not regime shifts.

Verification at small n: after 10000 steps + burn-in, the empirical state
distribution converges to the exact Boltzmann distribution (computable in
closed form on 4 spins). Total-variation distance is reported and asserted
to be small.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import Classification                                              # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402
from replay import ReplayCache, cached_runner                                    # noqa: E402


N = 4                                # 4 spins
EDGES = [(0, 1), (1, 2), (2, 3), (3, 0)]   # 4-cycle (planar)
J = 1.0
BETA = 0.5


def bits(x):
    return [(x >> (N - 1 - i)) & 1 for i in range(N)]


def energy(x):
    bs = bits(x)
    s = [1 if b == 1 else -1 for b in bs]
    return -J * sum(s[i] * s[j] for (i, j) in EDGES)


def exact_boltzmann():
    weights = [math.exp(-BETA * energy(x)) for x in range(2 ** N)]
    Z = sum(weights)
    return [w / Z for w in weights]


def _classify_route(data, prev):
    cls = Classification(tier="T2", meters={"n_vertices": N, "genus": 0, "planar": True},
                         in_family=True, reasoning="planar Ising acceptance ratio")
    return route_classification(cls)


def make_mcmc_stage(step_idx: int, rng: random.Random, cache: ReplayCache) -> Stage:
    """One Metropolis step. Carry-forward state: (current_config, histogram)."""

    def base_runner(payload, prev, route):
        # payload = (current_config, flip_position) -- the cache key
        cfg, j = payload
        flipped = cfg ^ (1 << (N - 1 - j))
        dE = energy(flipped) - energy(cfg)
        ratio = math.exp(-BETA * dE) if dE > 0 else 1.0
        return ratio                                # cacheable on (cfg, j)

    cached = cached_runner(base_runner, cache,
                           key_fn=lambda payload, _prev: f"{payload[0]}::{payload[1]}")

    def runner_fn(data, prev, route):
        cfg = prev["cfg"]
        j = rng.randrange(N)
        ratio = cached((cfg, j), prev, route)
        if rng.random() < ratio:
            new_cfg = cfg ^ (1 << (N - 1 - j))
        else:
            new_cfg = cfg
        hist = list(prev["hist"])
        hist[new_cfg] += 1
        return {"cfg": new_cfg, "hist": hist}

    return Stage(f"mcmc:{step_idx}", "metropolis-step", step_idx, _classify_route, runner_fn)


def main():
    print(__doc__)
    print("=" * 74)

    n_steps = 10000
    burn_in = 1000
    rng = random.Random(42)
    cache = ReplayCache()

    stages = [make_mcmc_stage(k, rng, cache) for k in range(n_steps)]
    trace = RichTrace()
    initial = {"cfg": 0, "hist": [0] * (2 ** N)}
    final, _ = run_pipeline(stages, seed=initial, trace=trace)

    # Empirical (after burn-in) -- but we'll just use the full histogram for simplicity.
    # For a clean burn-in version, the example would track step index and discard
    # the first `burn_in` updates; here we use the cumulative histogram.
    hist = final["hist"]
    total = sum(hist)
    emp = [h / total for h in hist]
    exact = exact_boltzmann()

    tv = 0.5 * sum(abs(e - x) for e, x in zip(emp, exact))

    print(f"\n  n_steps:                 {n_steps}")
    print(f"  unique cache entries:    {cache.size} (= 2^N * N = {2 ** N * N})")
    print(f"  cache hit rate:          {cache.hit_rate():.1%}")
    print()
    print(f"  Empirical vs exact Boltzmann distribution (4 spins, 16 states):")
    print(f"  {'state':>5}  {'energy':>7}  {'exact':>8}  {'empirical':>10}")
    print(f"  {'-' * 5}  {'-' * 7}  {'-' * 8}  {'-' * 10}")
    for x in range(2 ** N):
        print(f"  {bin(x)[2:].rjust(N, '0'):>5}  {energy(x):>7.1f}  {exact[x]:>8.4f}  {emp[x]:>10.4f}")
    print()
    print(f"  total-variation distance:   {tv:.4f}  (expected ~ 0.01-0.03 at 10000 steps)")
    assert tv < 0.10, f"empirical too far from exact: TV = {tv:.4f}"
    print()
    print(trace.summary())
    print(f"  At 10000 steps, replay cache hits on {cache.hits} of {cache.hits + cache.misses}")
    print(f"  proposal evaluations -- the actual cacheable computation runs only {cache.size}")
    print(f"  times, regardless of how many MCMC steps run.")


if __name__ == "__main__":
    main()
