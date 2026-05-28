# Adaptive incremental rebuild — the 1000-pass companion

The pipeline-router's companion to the [`build_dag_audit/`](../build_dag_audit/)
flagship. Where the flagship is a single 5-stage pipeline on one dependency
graph, **this example runs a 1000-stage pipeline** — one stage per file
edit in an 8-hour developer session — and routes each edit's structural
analysis independently.

```bash
python incremental.py     # verified small-n run + 1000-edit scaling demonstration
```

## The cover story

A developer is working in a project for 8 hours and makes ~1000 file edits.
Each edit triggers an incremental-build *analysis* — not the build itself,
but the structural question *"what does this edit affect, and how expensive
is analysing that?"*

The pipeline-router decides **per edit** which member handles it:

| edit shape | tier | member | cost |
|---|---|---|---|
| leaf file, no downstream | **T0** | trivial-traverse | O(1) |
| in a planar downstream subgraph | **T2** | planar-cone-traverse | O(\|cone\|) |
| cross-module (higher arity) | **T2/T3** | (same) | (same) |
| circular dep introduced | **T7** | advised: honest stop | +∞ |

The carry-forward state is the **dirty set** — files that need rebuilding
given the edits seen so far. Each edit updates it.

## What no off-the-shelf build system does

| capability | Bazel / Buck / Pants / Make / Ninja | this example |
|---|---|---|
| per-edit structural routing | one strategy chosen globally at config time | classifier picks per edit |
| replay-cached structural analysis | idempotency keyed by activity ID + input hash | keyed by problem descriptor — two structurally identical edits hit the same cache entry |
| audit-grade routing trace | rebuild log (which targets ran) | structured RichTrace: per-member / per-tier histograms, regime-change indices, total log-ops |

## What the run shows

### Verified small-n run (5 files, 50 edits)

A 5-file project with the dependency graph

```
A → B → C
 ↘ D
   E   (no deps)
```

A 50-edit session: every edit's downstream cone is **brute-force
verified**. The trace shows:

- 26 regime changes (T0 ↔ T2 transitions as edits flip between leaf and
  non-leaf files);
- 76% cache hit rate (12 unique edit-descriptors out of 50).

### 1000-edit scaling demonstration (10 files)

A larger planar project (two parallel chains, shared root and tail) under
a 1000-edit session, biased to a hot subset of files:

- **14 unique edit-descriptors out of 1000** — the rest are repeated;
- **98.6% cache hit rate** — the replay cache reduces 1000 calls to 14;
- **104 regime changes** detected (the routing shifts dozens of times
  between T0 and T2 as the developer cycles through hot and cold files);
- routed total log-ops **17.44**, fixed-strategy baseline log-ops
  **18.61** — routed is **2.2× cheaper** in real ops.

This is the load-bearing demonstration the planning doc called for: at
1000 passes, the replay cache and per-pass routing pay off concretely.

## How the trace reads

```
Pipeline trace -- 1000 stages, 104 regime changes
  total log-budget   = 6867.73    (sum of per-stage log2-costs)
  total log-ops      =   17.44    (log2 of total operations)

  by member                              stages   log_ops    log_budget
  ------------------------------------   ------   --------   ----------
  planar-cone-traverse                      947     17.44      6814.73
  trivial-traverse                           53      6.73        53.00

  by tier   stages   log_ops    log_budget
  -------   ------   --------   ----------
  T0            53      6.73        53.00
  T2           947     17.44      6814.73

  regime changes (showing 6 of 104):
    stage 26: planar-cone-traverse -> trivial-traverse  (delta_cost = -7.64)
    stage 27: trivial-traverse -> planar-cone-traverse  (delta_cost = +6.17)
    ...
```

Every line of that summary comes from the `RichTrace` accumulated during
the routed run — no separate logging pass.

## Verification

`verify_session` asserts, for every stage in the verified run, that the
reported downstream cone size matches a brute-force traversal of the
dependency graph. A failed assertion stops the run; the printed numbers
are what passed.

## Why this matters

The flagship example (`build_dag_audit/`) proves the **5-stage**
pipeline-router does exact analysis no off-the-shelf tool produces. This
example proves the same router scales to **1000+ stages** with the replay
cache making it practical. Together: the framework is fit for both
single-shot structural audits and long-running adaptive workflows — the
two ends of the "diagnostic-layer at the workflow level" thesis the
pipeline-router embodies.

The same pattern lifts to **pure workflow systems** (Temporal, Camunda,
Airflow, Prefect, n8n, ServiceNow, Pega): a workflow definition is a
labelled directed graph of activities, exactly the shape the framework's
classifier inspects. Per-activity routing, replay-cached subworkflow
invocation, and an audit-grade execution trace are the natural integration
points — application direction, not built here.
