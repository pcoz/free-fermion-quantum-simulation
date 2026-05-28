r"""Linear error-correcting codes -- tier T0 (GF(2)-affine) of the Holant
hierarchy in a different application domain.

A linear code defined by parity-check matrix H (m x n binary) has codewords

    C = { x in F_2^n  :  H x = 0  (mod 2) },

so the codewords are exactly the affine variety satisfying the framework's
T0 constraint shape A x = b (mod 2). The pipeline:

  CLASSIFY  -> T0 GF(2)-affine, dim(C) = n - rank(H)
  COUNT     -> |C| = 2^(n - rank H)
  WITNESS   -> one non-zero codeword
  MIN-DIST  -> the code's minimum Hamming distance (the error-correction radius)

Demonstrated on:

  * a 3-repetition code (n=3, k=1, d=3) -- the smallest non-trivial code;
  * the classical (7,4) Hamming code  -- n=7, k=4, d=3, single-error correcting.

Every count and the minimum distance are verified against exhaustive
enumeration of {0, 1}^n. The pipeline's CLASSIFY stage routes to the
framework's T0/ch-form member; the rest of the stages reuse that route.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline_router import Stage, run_pipeline                                  # noqa: E402
from classify import classify_constraint_set                                     # noqa: E402
from route_constraint import route as route_classification                       # noqa: E402
from trace import RichTrace                                                       # noqa: E402
from verifier import satisfies_gf2_affine, enumerate_satisfying_assignments      # noqa: E402


def hamming_7_4():
    """(7,4) Hamming code. The classic single-error-correcting code."""
    H = np.array([
        [1, 0, 1, 0, 1, 0, 1],
        [0, 1, 1, 0, 0, 1, 1],
        [0, 0, 0, 1, 1, 1, 1],
    ], dtype=int)
    b = np.zeros(3, dtype=int)
    return {"name": "(7,4) Hamming code", "H": H, "b": b, "n": 7}


def repetition_3():
    """3-repetition code: x_0 = x_1 = x_2."""
    H = np.array([[1, 1, 0], [0, 1, 1]], dtype=int)
    b = np.zeros(2, dtype=int)
    return {"name": "3-repetition code", "H": H, "b": b, "n": 3}


def _gf2_rank(M):
    rows = [list(map(int, row)) for row in M]
    n_rows = len(rows)
    n_cols = len(rows[0]) if rows else 0
    rank = 0
    for col in range(n_cols):
        pv = next((r for r in range(rank, n_rows) if rows[r][col] == 1), None)
        if pv is None: continue
        rows[rank], rows[pv] = rows[pv], rows[rank]
        for r in range(n_rows):
            if r != rank and rows[r][col] == 1:
                rows[r] = [a ^ b for a, b in zip(rows[r], rows[rank])]
        rank += 1
    return rank


def make_pipeline():
    def classify_route(data, prev):
        cls = classify_constraint_set(A=prev["H"], b=prev["b"], modulus=2)
        r = route_classification(cls)
        r.meters["_cls"] = cls
        return r

    def reuse_route(data, prev):
        return route_classification(prev["classification"])

    return [
        Stage("CLASSIFY", "code-structure", None,
              classify_route,
              lambda d, p, r: {**p, "classification": r.meters["_cls"]}),
        Stage("COUNT", "codeword-count", None, reuse_route,
              lambda d, p, r: {**p, "rank": _gf2_rank(p["H"]),
                               "count": 2 ** (p["n"] - _gf2_rank(p["H"]))}),
        Stage("WITNESS", "find-codeword", None, reuse_route,
              lambda d, p, r: dict(p,
                  all_codewords=enumerate_satisfying_assignments(p["H"], p["b"]),
                  witness=next((c for c in enumerate_satisfying_assignments(p["H"], p["b"]) if c), None))),
        Stage("MIN-DIST", "min-hamming-weight", None, reuse_route,
              lambda d, p, r: dict(p,
                  min_distance=(min((bin(c).count("1") for c in p["all_codewords"] if c),
                                    default=None)))),
    ]


def verify(code, final):
    n = code["n"]
    bf = sum(1 for x in range(2 ** n) if satisfies_gf2_affine(x, code["H"], code["b"]))
    assert final["count"] == bf, f"{code['name']}: count {final['count']} != brute {bf}"
    bf_min = min((bin(x).count("1") for x in range(1, 2 ** n)
                  if satisfies_gf2_affine(x, code["H"], code["b"])), default=None)
    assert final["min_distance"] == bf_min, \
        f"{code['name']}: min-distance {final['min_distance']} != brute {bf_min}"


def main():
    print(__doc__)
    print("=" * 74)
    pipeline = make_pipeline()
    for code in (repetition_3(), hamming_7_4()):
        trace = RichTrace()
        final, _ = run_pipeline(pipeline, seed=code, trace=trace)
        verify(code, final)
        n = code["n"]
        wit = final["witness"]
        wit_str = f"0b{wit:0{n}b}  (weight {bin(wit).count('1')})" if wit is not None else "(none)"
        print(f"\n=== {code['name']} ===")
        print(f"  parity-check matrix H:        {code['H'].shape[0]} x {code['H'].shape[1]}")
        print(f"  rank(H) over GF(2):           {final['rank']}")
        print(f"  dim of code (n - rank H):     {n - final['rank']}")
        print(f"  codeword count = 2^dim:       {final['count']}")
        print(f"  example codeword:             {wit_str}")
        print(f"  minimum Hamming distance:     {final['min_distance']}  (corrects up to {(final['min_distance']-1)//2 if final['min_distance'] else 0} bit errors)")
        print()
        print(trace.summary())


if __name__ == "__main__":
    main()
