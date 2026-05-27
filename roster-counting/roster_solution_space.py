r"""Count and CERTIFY a roster's whole solution space -- exactly, fast.

The questions people assume are out of reach (so they never ask):
  * "Exactly HOW MANY valid rosters are there?"          -> the solution-space size
  * "Is the roster FORCED (only one), or flexible?"      -> uniqueness / rigidity
  * "How many rosters put this worker on that shift?"    -> a conditional count
  * "If this availability disappears, do we still have a roster?"  -> robustness
  * "Which single assignment is a hidden single-point-of-failure?" -> criticality

A solver gives you ONE roster. Here we count and interrogate the ENTIRE space.

The model (a spatial-coverage roster)
-------------------------------------
Workers and shift-slots sit on a planar layout (here: a grid). Each worker covers
exactly one ADJACENT slot, and each slot is covered by exactly one worker -- so a
"valid full roster" is a PERFECT MATCHING of the worker/slot adjacency graph.
Counting valid rosters = counting perfect matchings.

Why it's fast (and the honest limit)
-------------------------------------
For a PLANAR layout, the FKT theorem turns this count into a single Pfaffian
(`holant_tools`: kasteleyn_orient -> holant_planar), so it is POLYNOMIAL-TIME and
exact -- even when the number of rosters is astronomically large. Every query
below is just the same count on a slightly modified graph, so each is equally
fast. Honest caveat: this works because the structure is planar + exact-cover
(perfect matching). General dense rostering (a worker covering many shifts, dense
availability) is the permanent -- #P-hard -- and needs MILP/CP solvers instead.

Run:  python roster_solution_space.py
"""
from holant_tools import kasteleyn_orient, holant_planar


# ---------------------------------------------------------------------------
# Build a planar worker/slot layout: an R x C grid.
#   - cells (r, c) are the positions;
#   - a cell with (r + c) even is a WORKER, (r + c) odd is a SHIFT-SLOT
#     (so every adjacency joins a worker to a slot -- a bipartite roster);
#   - an edge = "this worker can cover this adjacent slot" (availability).
# A perfect matching = a valid full roster.
# ---------------------------------------------------------------------------
def grid_layout(R, C):
    verts = [(r, c) for r in range(R) for c in range(C)]
    vset = set(verts)
    edges = []
    for (r, c) in verts:
        if c + 1 < C:
            edges.append(((r, c), (r, c + 1)))   # horizontal adjacency
        if r + 1 < R:
            edges.append(((r, c), (r + 1, c)))   # vertical adjacency
    # Rotation system = a planar embedding: each cell's neighbours in CCW order
    # (right, up, left, down), using screen coords x=c, y=-r.
    rotation = {}
    for (r, c) in verts:
        cand = [(r, c + 1), (r - 1, c), (r, c - 1), (r + 1, c)]
        rotation[(r, c)] = [v for v in cand if v in vset]
    return verts, edges, rotation


def is_worker(cell):
    return (cell[0] + cell[1]) % 2 == 0


def label(cell):
    return ("W" if is_worker(cell) else "S") + str(cell)


# ---------------------------------------------------------------------------
# Counting valid rosters two ways.
# ---------------------------------------------------------------------------
def count_rosters_fkt(verts, edges, rotation):
    """EXACT count via FKT: |Pf(Kasteleyn-oriented adjacency)| = #perfect
    matchings = #valid rosters. Polynomial time, even for huge counts."""
    if len(verts) % 2 == 1:
        return 0                                 # odd #cells -> no full roster
    M = kasteleyn_orient(verts, edges, rotation)
    return abs(int(holant_planar(M)))


def count_rosters_bruteforce(verts, edges):
    """Reference count: enumerate every perfect matching. Exponential -- only for
    verifying the fast method on small layouts."""
    adj = {v: [] for v in verts}
    for (u, v) in edges:
        adj[u].append(v)
        adj[v].append(u)

    def rec(unmatched):
        if not unmatched:
            return 1
        u = unmatched[0]
        rest = unmatched[1:]
        total = 0
        for w in adj[u]:
            if w in rest:
                total += rec([x for x in rest if x != w])
        return total

    return rec(list(verts))


# ---------------------------------------------------------------------------
# Editing the graph for the "what-if" queries. Removing edges/vertices from a
# planar embedding keeps it planar, so each reduced count is still FKT-fast.
# ---------------------------------------------------------------------------
def reduce_layout(verts, edges, rotation, drop_verts=(), drop_edges=()):
    """Return a copy of the layout with some vertices and/or edges removed
    (and the rotation system updated to match)."""
    dv = set(drop_verts)
    # normalise dropped edges to an unordered-pair set
    de = {frozenset(e) for e in drop_edges}
    new_verts = [v for v in verts if v not in dv]
    new_edges = [e for e in edges
                 if e[0] not in dv and e[1] not in dv and frozenset(e) not in de]
    keep = set(new_verts)
    allowed = {frozenset(e) for e in new_edges}
    new_rot = {}
    for v in new_verts:
        new_rot[v] = [w for w in rotation[v]
                      if w in keep and frozenset((v, w)) in allowed]
    return new_verts, new_edges, new_rot


def main():
    print(__doc__)
    R, C = 4, 4                                  # 16 cells: 8 workers, 8 slots
    verts, edges, rot = grid_layout(R, C)
    workers = [v for v in verts if is_worker(v)]
    slots = [v for v in verts if not is_worker(v)]

    # --- Q0: how big is the solution space? (and is the fast count correct?) ---
    print("=" * 70)
    print(f"Roster layout: {R}x{C} grid -> {len(workers)} workers, {len(slots)} slots")
    print("=" * 70)
    total_fkt = count_rosters_fkt(verts, edges, rot)
    total_bf = count_rosters_bruteforce(verts, edges)
    assert total_fkt == total_bf, (total_fkt, total_bf)
    print(f"  EXACTLY HOW MANY valid rosters?  {total_fkt}")
    print(f"    (FKT/Pfaffian = {total_fkt}, brute force = {total_bf} -- agree)")
    print(f"  Is the roster forced/unique?      {'YES (rigid)' if total_fkt == 1 else 'no -- flexible'}")

    # --- Q1: conditional count -- how many rosters use a given assignment? ---
    w, s = (0, 0), (0, 1)                          # worker W(0,0) covering slot S(0,1)
    # rosters with w->s = rosters of the layout with w and s (and their edges) gone
    rv, re, rr = reduce_layout(verts, edges, rot, drop_verts=[w, s])
    with_ws = count_rosters_fkt(rv, re, rr)
    assert with_ws == count_rosters_bruteforce(rv, re)
    print(f"\n  How many rosters assign {label(w)} -> {label(s)}?  {with_ws}"
          f"   ({with_ws}/{total_fkt} = {with_ws / total_fkt:.0%} of all rosters)")

    # --- Q2: robustness -- an availability disappears; do rosters survive? ---
    w2, s2 = (1, 1), (1, 2)
    rv, re, rr = reduce_layout(verts, edges, rot, drop_edges=[(w2, s2)])
    after = count_rosters_fkt(rv, re, rr)
    print(f"\n  If {label(w2)} can no longer cover {label(s2)}:")
    print(f"    rosters remaining = {after}   "
          f"({'STILL feasible' if after > 0 else 'NO roster left -- this availability was essential'})"
          f"  [lost {total_fkt - after} of {total_fkt}]")

    # --- Q3: criticality -- find the hidden single-points-of-failure ---
    # An assignment that appears in EVERY roster is forced: lose it and you lose
    # every roster. An assignment in NO roster is dead availability.
    print("\n  Criticality of each availability (share of rosters that use it):")
    forced, dead, normal = [], [], 0
    for (u, v) in edges:
        rv, re, rr = reduce_layout(verts, edges, rot, drop_verts=[u, v])
        uses = count_rosters_fkt(rv, re, rr)          # rosters that use edge (u,v)
        frac = uses / total_fkt
        if uses == total_fkt:
            forced.append((u, v))
        elif uses == 0:
            dead.append((u, v))
        else:
            normal += 1
    print(f"    forced assignments (in 100% of rosters -> single point of failure): "
          f"{len(forced)}")
    for (u, v) in forced[:4]:
        print(f"        {label(u)} -> {label(v)}")
    print(f"    dead availabilities (used by NO roster): {len(dead)}")
    print(f"    normal (flexible) availabilities: {normal}")
    if not forced:
        print("    -> healthy: no single assignment is a point of failure here.")

    # --- Contrast: a RIGID roster has exactly ONE solution ---
    # A 1x6 "coverage chain": cells pair along a line. A path has a single
    # perfect matching, so the roster is forced -- every assignment mandatory.
    cv, ce, crot = grid_layout(1, 6)
    chain_total = count_rosters_fkt(cv, ce, crot)
    assert chain_total == count_rosters_bruteforce(cv, ce)
    chain_forced = sum(
        1 for (u, v) in ce
        if chain_total and count_rosters_fkt(*reduce_layout(cv, ce, crot, drop_verts=[u, v])) == chain_total
    )
    print("\n  Contrast -- a 1x6 coverage chain (a deliberately rigid layout):")
    print(f"    valid rosters = {chain_total}  -> {'UNIQUE / forced' if chain_total == 1 else 'flexible'}")
    print(f"    forced assignments: {chain_forced} of {len(ce)} availabilities are mandatory")
    print("    a rigid roster has zero slack: lose any forced assignment and it breaks.")

    # --- Scale: the same exact count where brute force is hopeless ---
    print("\n" + "=" * 70)
    print("Fast at scale: exact roster counts FKT computes instantly")
    print("=" * 70)
    print(f"  {'layout':>9} | {'workers+slots':>13} | {'valid rosters (exact)':>34}")
    print("  " + "-" * 64)
    import time
    for (r, c) in [(4, 4), (8, 8), (12, 12), (16, 16), (20, 20)]:
        v, e, rt = grid_layout(r, c)
        t0 = time.perf_counter()
        n = count_rosters_fkt(v, e, rt)
        dt = time.perf_counter() - t0
        digits = len(str(n))
        shown = str(n) if digits <= 20 else f"{str(n)[:8]}...({digits} digits)"
        print(f"  {f'{r}x{c}':>9} | {r * c:>13} | {shown:>34}   [{dt:.3f}s]")
    print("\n  A 20x20 layout has a ~50-digit number of valid rosters, counted")
    print("  exactly in a fraction of a second. Brute-force enumeration of that")
    print("  many rosters could never finish on any computer.")
    print("  This is the whole point: for STRUCTURED rosters, 'how many?', 'is it")
    print("  unique?', 'how robust?' and 'what's critical?' are exact, cheap")
    print("  questions -- not the intractable ones everyone assumes they are.")


if __name__ == "__main__":
    main()
