# The 2D Ising phase transition — exactly

A magnet heated past a critical temperature **abruptly loses its magnetism** — a
*phase transition*, like water boiling. The 2D Ising model (a lattice of spins
that prefer to align with their neighbours) is the textbook example, and Onsager
solved it exactly in 1944. The reason it *can* be solved exactly is that it is
**secretly a free-fermion system** — the same structure behind the rest of this
repository — which is why it belongs here.

```bash
pip install numpy            # (holant-tools too, for the dimer sidebar)
python ising_phase_transition.py
```

## What it computes (all exact)

- the exact **critical temperature** `T_c = 2 / ln(1+√2) ≈ 2.269`;
- the **spontaneous magnetisation** `m(T)` — the order parameter that switches on
  below `T_c` with the famous critical exponent **1/8**;
- the **free energy** (Onsager's integral) and the **specific heat**, which
  *diverges* at `T_c` — the signature of the transition;
- a `holant-tools` FKT/Pfaffian computation on the **sister** exactly-solvable
  model (dimers), since both are solved by the same free-fermion machinery.

## Why exactness matters here

Locating a phase transition by simulation (Monte-Carlo) is hardest *at* the
transition: correlations diverge, sampling slows critically, and finite samples
**round off** the sharp features — so you get `T_c` and the critical exponents
only with error bars and finite-size extrapolation. The exact solution pins them
to the digit, with no statistical error. That is the workflow exactness unlocks:
certainty about critical points and exponents, not estimates.

## Honest scope

This uses the exact free-fermion (Onsager / Yang) solution — the analytic sibling
of the FKT/Pfaffian *counting* the rest of the repo uses. It is specific to the
exactly-solvable case (the 2D Ising with no external field); a 3D Ising model, or
a field, is not free-fermion-solvable and needs Monte-Carlo or other methods.
