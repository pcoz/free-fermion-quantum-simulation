r"""The 2D Ising phase transition, computed EXACTLY -- the birthplace of the
free-fermion method.

Why this belongs here
---------------------
The 2D Ising model (a lattice of spins that prefer to align with their
neighbours) is the most famous exactly-solvable model in physics: Onsager solved
it in 1944, and the reason it *can* be solved exactly is that it is **secretly a
free-fermion system** -- the same structure that powers every other example in
this repo. So this is the historical root of "the impossible made exact": a
genuine thermodynamic phase transition, with its critical temperature and
critical exponents pinned down to the digit.

What we compute (all exact)
---------------------------
- the exact **critical temperature** T_c, where the magnet abruptly orders;
- the exact **free energy** per spin f(T) (Onsager's integral);
- the exact **spontaneous magnetisation** m(T) (Yang 1952) -- the order parameter
  that switches on below T_c with the famous critical exponent **1/8**;
- the **specific heat**, which *diverges* at T_c (the signature of the transition).

Why EXACTNESS matters here (the workflow it enables)
----------------------------------------------------
Locating a phase transition by simulation (Monte-Carlo) is hard precisely at the
transition: correlations diverge, sampling slows critically, and finite samples
*round off* the sharp features -- you need careful finite-size scaling and still
get error bars on T_c and the exponents. The exact solution gives T_c and the
1/8 exponent with no statistical error and no finite-size rounding. That is the
difference between "the transition is somewhere around here" and "the transition
is exactly here, with this exponent."

Also included: a genuine `holant-tools` FKT/Pfaffian computation on the *sister*
exactly-solvable lattice model (dimers), since both the Ising and the dimer model
are solved by the same free-fermion / Pfaffian machinery.

Run:  python ising_phase_transition.py
"""
import math

import numpy as np


def onsager_lnZ_per_spin(T, n_grid=400):
    """Exact (Onsager) ln Z / N for the isotropic 2D square-lattice Ising model
    at temperature T (coupling J = 1, Boltzmann constant = 1), evaluated by
    numerical integration of Onsager's double integral:

        ln Z / N = ln 2
                 + 1/(2 (2pi)^2) * int_0^2pi int_0^2pi
                       ln[ cosh^2(2K) - sinh(2K)(cos a + cos b) ] da db,

    with K = 1/T. (At K=0 the integral vanishes and this returns ln 2 = ln Z/N
    for free spins -- a sanity check built into the formula.)
    """
    K = 1.0 / T
    c2 = math.cosh(2 * K)
    s2 = math.sinh(2 * K)
    a = np.linspace(0, 2 * np.pi, n_grid, endpoint=False)
    ca = np.cos(a)
    # integrand on the a x b grid; arg is >= 0 (min (sinh2K - 1)^2 at a=b=0)
    arg = c2 ** 2 - s2 * (ca[:, None] + ca[None, :])
    arg = np.clip(arg, 1e-300, None)
    integral = np.log(arg).mean() * (2 * np.pi) ** 2     # mean * area
    return math.log(2) + integral / (2 * (2 * np.pi) ** 2)


def spontaneous_magnetisation(T):
    """Exact spontaneous magnetisation (Yang 1952): m = (1 - sinh^{-4}(2K))^{1/8}
    for T < T_c, and 0 for T >= T_c.  K = 1/T."""
    K = 1.0 / T
    s = math.sinh(2 * K)
    if s <= 1.0:                       # T >= T_c: disordered, no net magnetisation
        return 0.0
    return (1.0 - s ** (-4)) ** 0.125  # the 1/8 critical exponent lives here


def main():
    print(__doc__)
    Tc = 2.0 / math.log(1.0 + math.sqrt(2.0))     # exact: sinh(2/T_c) = 1
    print("=" * 70)
    print(f"Exact critical temperature  T_c = 2 / ln(1+sqrt 2) = {Tc:.6f}  (J=1)")
    print("=" * 70)

    # --- the order parameter switching on at T_c (the phase transition) ---
    print("\n  Spontaneous magnetisation m(T) -- the order parameter:")
    print(f"  {'T':>6} | {'m(T)':>10} | phase")
    print("  " + "-" * 34)
    for T in [1.5, 2.0, 2.20, 2.25, Tc, 2.30, 2.40, 3.0]:
        m = spontaneous_magnetisation(T)
        phase = "ordered (magnetised)" if m > 0 else "disordered"
        tag = "  <- T_c" if abs(T - Tc) < 1e-6 else ""
        print(f"  {T:>6.3f} | {m:>10.6f} | {phase}{tag}")

    # --- free energy + specific heat; the heat capacity diverges at T_c ---
    Ts = np.linspace(1.6, 3.2, 321)
    g = np.array([onsager_lnZ_per_spin(T) for T in Ts])   # ln Z / N
    U = Ts ** 2 * np.gradient(g, Ts)                      # internal energy per spin
    C = np.gradient(U, Ts)                                # specific heat per spin
    T_peak = Ts[np.argmax(C)]
    print(f"\n  Free energy is smooth, but the specific heat C(T) peaks (diverges)")
    print(f"  at the transition: numerical peak at T = {T_peak:.3f} vs exact T_c = {Tc:.3f}.")

    # --- verification against the exact, known answers ---
    assert spontaneous_magnetisation(Tc + 0.05) == 0.0          # disordered above T_c
    assert spontaneous_magnetisation(Tc - 0.05) > 0.0           # ordered below T_c
    assert abs(onsager_lnZ_per_spin(1e6) - math.log(2)) < 1e-6  # free spins at T->inf
    assert abs(T_peak - Tc) < 0.05                              # C peak sits at T_c
    print("  [verified: m=0 above T_c, m>0 below; ln Z/N -> ln2 as T->inf;")
    print("   specific-heat peak coincides with the exact T_c]")

    # --- what exactness unlocks ---
    print("\n" + "=" * 70)
    print("What exactness unlocks")
    print("=" * 70)
    print("  The transition is located EXACTLY (T_c to machine precision) and the")
    print("  order parameter carries the exact critical exponent 1/8 -- e.g.")
    near = [(Tc - d) for d in (0.20, 0.10, 0.05, 0.02)]
    print(f"  {'T_c - T':>8} | {'m':>9} | {'m^8 / (1 - T/T_c)':>18}  (should approach a constant)")
    for T in near:
        m = spontaneous_magnetisation(T)
        ratio = m ** 8 / (1 - T / Tc)
        print(f"  {Tc - T:>8.3f} | {m:>9.5f} | {ratio:>18.4f}")
    print("  A Monte-Carlo study would *round off* this singular behaviour and")
    print("  return T_c and the exponent only with error bars and finite-size")
    print("  extrapolation. Exactness removes both -- the workflow it enables is")
    print("  pinning critical points and exponents with certainty, not estimates.")

    # --- holant-tools tie-in: the sister exactly-solvable model (dimers) ---
    dimer_fkt_sidebar()


def dimer_fkt_sidebar():
    """The dimer model is the Ising's sister exactly-solvable lattice model, and
    holant-tools solves it directly by the same FKT/Pfaffian machinery. Compute
    the exact dimer free energy per site and watch it approach Kasteleyn's
    constant (Catalan / pi ~ 0.29156)."""
    try:
        from holant_tools import kasteleyn_orient, holant_planar
    except Exception:
        print("\n  (holant-tools not installed; skipping the dimer FKT sidebar.)")
        return

    def grid(R, C):
        verts = [(r, c) for r in range(R) for c in range(C)]
        vset = set(verts)
        edges = []
        for (r, c) in verts:
            if c + 1 < C:
                edges.append(((r, c), (r, c + 1)))
            if r + 1 < R:
                edges.append(((r, c), (r + 1, c)))
        rot = {}
        for (r, c) in verts:
            cand = [(r, c + 1), (r - 1, c), (r, c - 1), (r + 1, c)]
            rot[(r, c)] = [v for v in cand if v in vset]
        return verts, edges, rot

    print("\n" + "=" * 70)
    print("Sister model via holant-tools (FKT/Pfaffian): dimer free energy")
    print("=" * 70)
    catalan_over_pi = 0.915965594177219 / math.pi
    print(f"  exact target (Kasteleyn's constant, Catalan/pi) = {catalan_over_pi:.5f}")
    print("  (ln(Z)/N rises toward it as the lattice grows; the gap is the finite")
    print("   boundary correction.)")
    last = None
    for (R, C) in [(8, 8), (12, 12), (16, 16), (20, 20)]:
        v, e, rot = grid(R, C)
        z = abs(int(holant_planar(kasteleyn_orient(v, e, rot))))   # exact #dimer coverings
        f_per_site = math.log(z) / (R * C)
        assert last is None or f_per_site > last      # must increase toward the constant
        last = f_per_site
        shown = str(z) if len(str(z)) <= 18 else str(z)[:8] + f"...({len(str(z))} digits)"
        print(f"  {R}x{C}: exact dimer coverings = {shown}  ->  ln(Z)/N = {f_per_site:.5f}")
    print("  Same free-fermion / Pfaffian machinery that makes the Ising solvable,")
    print("  computed exactly by holant-tools.")


if __name__ == "__main__":
    main()
