r"""GF(2)-quadratic constraints -- tier T1 of the Holant hierarchy.

A T1 constraint set has a linear part `A x = b (mod 2)` and a quadratic
part `x^T Q_i x = c_i (mod 2)`. The framework's `classify_constraint_set`
detects the quadratic part and emits tier T1, routing to the CH-form
member with post-selecting Z measurements -- the natural way to encode
a quadratic phase against an affine variety in the CH stabilizer formalism.

Cover story (loosely): "circuit topology audit" -- given a boolean circuit
whose inputs satisfy a parity test (linear) AND an additional invariant on
input pairs (quadratic), count the inputs that satisfy both. A small
combinatorial-circuit-design check; toy in scale but T1 in structure.

This file demonstrates two T1 instances:
  * a 4-bit constraint set with one linear + one quadratic constraint;
  * a 5-bit constraint set with two linear + two quadratic constraints.
Both are brute-force enumerated (2^n inputs) and the count compared.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import classify_constraint_set                                     # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402
from verifier import satisfies_gf2_affine                                         # noqa: E402


def instance_4bit():
    """4-bit: x_0 + x_1 + x_2 + x_3 = 0 (mod 2)  AND  x_0 x_1 + x_2 x_3 = 0 (mod 2)."""
    A = np.array([[1, 1, 1, 1]], dtype=int)
    b = np.array([0], dtype=int)
    Q = [np.array([
        [0, 1, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 0, 0],
    ], dtype=int)]
    c = np.array([0], dtype=int)
    return {"name": "4-bit: parity + (x0 x1 + x2 x3) = 0 mod 2",
            "A": A, "b": b, "Q": Q, "c": c, "n": 4}


def instance_5bit():
    """5-bit: x_0 + x_2 + x_4 = 1, x_1 + x_3 = 0;  x_0 x_2 = 1, x_1 x_4 = 0."""
    A = np.array([
        [1, 0, 1, 0, 1],
        [0, 1, 0, 1, 0],
    ], dtype=int)
    b = np.array([1, 0], dtype=int)
    Q = [
        np.array([[0,0,1,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]], dtype=int),
        np.array([[0,0,0,0,0],[0,0,0,0,1],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]], dtype=int),
    ]
    c = np.array([1, 0], dtype=int)
    return {"name": "5-bit: 2 linear + 2 quadratic", "A": A, "b": b, "Q": Q, "c": c, "n": 5}


def _satisfies(x, inst):
    n = inst["n"]
    bits = np.array([(x >> (n - 1 - i)) & 1 for i in range(n)], dtype=int)
    if not np.array_equal((inst["A"] @ bits) % 2, inst["b"] % 2):
        return False
    for Q, ci in zip(inst["Q"], inst["c"]):
        if (bits @ Q @ bits) % 2 != ci % 2:
            return False
    return True


def make_pipeline():
    def classify_route(data, prev):
        cls = classify_constraint_set(A=prev["A"], b=prev["b"], Q=prev["Q"], c=prev["c"])
        r = route_classification(cls)
        r.meters["_cls"] = cls
        return r
    def reuse_route(data, prev):
        return route_classification(prev["classification"])
    return [
        Stage("CLASSIFY", "constraint-tier", None, classify_route,
              lambda d, p, r: {**p, "classification": r.meters["_cls"]}),
        Stage("COUNT", "satisfying-count", None, reuse_route,
              lambda d, p, r: {**p,
                  "satisfying": [x for x in range(2 ** p["n"]) if _satisfies(x, p)]}),
    ]


def main():
    print(__doc__)
    print("=" * 74)
    pipeline = make_pipeline()
    for inst in (instance_4bit(), instance_5bit()):
        trace = RichTrace()
        final, _ = run_pipeline(pipeline, seed=inst, trace=trace)
        cls = final["classification"]
        bf_count = sum(1 for x in range(2 ** inst["n"]) if _satisfies(x, inst))
        assert len(final["satisfying"]) == bf_count
        print(f"\n=== {inst['name']} ===")
        print(f"  tier:            {cls.tier}")
        print(f"  reasoning:       {cls.reasoning}")
        print(f"  satisfying inputs ({len(final['satisfying'])}):  "
              f"{[bin(s)[2:].rjust(inst['n'], '0') for s in final['satisfying']]}")
        print(f"  brute-force count matches:    {bf_count}")
        print()
        print(trace.summary())


if __name__ == "__main__":
    main()
