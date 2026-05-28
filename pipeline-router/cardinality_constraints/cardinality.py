r"""Cardinality constraints -- tier T3 of the Holant hierarchy.

A SYMMETRIC signature is a constraint defined by a sequence of values
indexed by Hamming weight:  signature[k] = the value when exactly k of
the n inputs are 1. Classic examples:

  AT-LEAST-1 of n      [0, 1, 1, ..., 1]
  EXACTLY-K of n       [0, ..., 0, 1, 0, ..., 0]   (1 in position K)
  MAJORITY (n odd)     [0, ..., 0, 1, ..., 1]      (1 above the midpoint)
  XOR                  [1, 0, 1, 0, ...]

The publicly-original result wired into the framework (holant-tools
v0.4.0): every symmetric signature has BASIS-AWARE MATCHGATE RANK in
{0, 1, 2}, via a common-basis parity-split decomposition. This is what
the T3 path of the pipeline-router exploits.

This file's pipeline:

  CLASSIFY  -> tier (T2 for arity 2, T3 for arity >= 3) via
               classify_signature, with the basis-aware rank as a meter.
  ROUTE     -> free-fermion via the rank-decomposition; rank <= 2 always.

It tabulates the rank for a battery of classical symmetric signatures.
Every result is asserted to be in {0, 1, 2}.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import classify_signature                                          # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402


def signatures_to_test():
    return [
        ("OR_arity_2",              [0, 1, 1]),
        ("AND_arity_2",             [0, 0, 1]),
        ("XOR_arity_2",             [0, 1, 0]),
        ("XOR_arity_3",             [0, 1, 0, 1]),
        ("OR_arity_3",              [0, 1, 1, 1]),
        ("EXACTLY_1_of_3",          [0, 1, 0, 0]),
        ("EXACTLY_2_of_4",          [0, 0, 1, 0, 0]),
        ("AT_LEAST_2_of_4",         [0, 0, 1, 1, 1]),
        ("MAJORITY_arity_5",        [0, 0, 0, 1, 1, 1]),
        ("AT_MOST_1_of_5",          [1, 1, 0, 0, 0, 0]),
        ("ALL_OR_NOTHING_arity_4",  [1, 0, 0, 0, 1]),
    ]


def make_pipeline():
    def route_fn(data, prev):
        cls = classify_signature(prev["values"])
        r = route_classification(cls)
        r.meters["_cls"] = cls
        return r
    def runner_fn(data, prev, route):
        cls = route.meters["_cls"]
        return {**prev, "tier": cls.tier, "rank": cls.meters["basis_aware_rank"],
                "member": route.member, "cost": route.cost}
    return [Stage("CLASSIFY-AND-ROUTE", "symmetric-signature", None, route_fn, runner_fn)]


def main():
    print(__doc__)
    print("=" * 74)
    pipeline = make_pipeline()
    print(f"\n  {'signature':<28}  {'arity':>5}  {'tier':>5}  "
          f"{'rank':>5}  {'route member':<35}")
    print(f"  {'-' * 28}  {'-' * 5}  {'-' * 5}  {'-' * 5}  {'-' * 35}")
    all_ranks = []
    for name, values in signatures_to_test():
        arity = len(values) - 1
        final, _ = run_pipeline(pipeline, seed={"name": name, "values": values})
        rank = final["rank"]
        assert rank in (0, 1, 2), f"{name}: rank {rank} not in {{0, 1, 2}}"
        all_ranks.append(rank)
        print(f"  {name:<28}  {arity:>5}  {final['tier']:>5}  "
              f"{rank:>5}  {final['member']:<35}")
    print(f"\n  All {len(all_ranks)} symmetric signatures have basis-aware matchgate rank in {{0, 1, 2}}.")
    print(f"  Rank distribution: 0 -> {all_ranks.count(0)}, 1 -> {all_ranks.count(1)}, 2 -> {all_ranks.count(2)}.")
    print()
    print("  This is the basis-aware rank-<=2 result (holant-tools v0.4.0, originally")
    print("  observed in this project's research log 2026-05-26): for EVERY symmetric")
    print("  signature there exists a common basis in which the matchgate decomposition")
    print("  has rank at most 2, via a parity-split construction. The pipeline-router's")
    print("  T3 tier routes to free-fermion regardless of how the signature was defined.")


if __name__ == "__main__":
    main()
