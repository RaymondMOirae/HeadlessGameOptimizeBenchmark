# Optimize an integrated frame pipeline through four measured iterations

The C++20 project in this workspace is a deterministic, renderer-free game
server simulation. One main loop combines weighted navigation, sparse unit
updates, component-query churn, a transform hierarchy, broad-phase collision
pairs, replication interest sets, ordered event dispatch and rollback history.
The public `mixed`, `raid`, `history`, `churn`, `scene`, `events`, `ecs` and
`interest` workloads exceed their CPU budgets in different shapes.

Improve every workload family while preserving exact behavior for arbitrary
valid CLI values. Hidden evaluation rebuilds the pristine baseline and your
final source, checks unseen temporal cases and externally times both programs.
Every performance family has its own minimum speedup, so a large win in one
system cannot compensate for leaving another unchanged.

Preserve all of the following contracts:

- exact weighted route choice and equal-cost direction ordering;
- map edits, goal changes and cache invalidation;
- transform composition order, local edits, reparenting and all descendants;
- inclusive AABB overlap, layer masks, unique canonical `(low, high)` pair order;
- event production and dispatch order, payload effects and target mutations;
- overlapping component-query order, structural mask changes and query side effects;
- canonical observer visibility order, enter/leave deltas and previous interest sets;
- history-ring wrap, rollback timing and every restored subsystem digest.

`--history-capacity 0` is valid only with rollback period/depth zero and disables
checkpoint recording for isolated workloads. Do not skip work, special-case
known arguments, cache answers for seeds, weaken hashes, fabricate timing fields,
introduce network/runtime dependencies or create unbounded threads.

Hidden evaluation uses multiple unseen distributions for difficult families. A
fast result on one size cannot compensate for a slow sibling case, and a large
route/collision win cannot compensate for leaving ECS, interest or transform
work unchanged.

## Required evidence chain

Retain all nine source-bound Perfetto traces. A checkpoint must show a material
raw-frame improvement before the next diagnostic iteration.

1. Run `python scripts/lb.py doctor`, then build release and profile modes.
2. Before semantic edits, capture
   `python scripts/lb.py profile --tag baseline --scenario mixed`.
3. Add at least two useful live `LB_ZONE` markers in the first measured
   bottleneck and capture `diagnostic_primary`.
4. Implement one material optimization, run `python scripts/lb.py verify`, and
   capture `checkpoint_primary` from a new source revision.
5. Analyze the checkpoint, add at least two markers for newly dominant work
   (at least four cumulative), then capture `diagnostic_state`.
6. Implement the second material optimization, verify, and capture
   `checkpoint_state` from another source revision.
7. Analyze again, add at least two markers for scale-dependent work (at least six
   cumulative), then capture `diagnostic_scale`.
8. Implement the third material optimization, verify, and capture
   `checkpoint_scale` from another source revision.
9. Analyze again, add at least two more markers for remaining work (at least eight
   cumulative), and capture `diagnostic_tail`.
10. Update ranked findings so `primary`, `state`, `scale` and `tail` each cite live zones
   from their corresponding diagnostic trace. Use `task/findings.example.json`,
   then run `python scripts/lb.py submit-analysis <your-json>`.
11. Implement the fourth material optimization. Keep all diagnostic markers, run
   `verify`, and capture `optimized`.
12. Run
    `python scripts/lb.py compare baseline checkpoint_primary checkpoint_state checkpoint_scale optimized`.

Keep all raw traces, run files, reports, manifests, findings and comparison under
`artifacts/`. All nine traces must come from distinct source hashes in the order
above. Whitespace/comment-only checkpoints that do not improve raw frame time do
not satisfy the workflow.

Perfetto and trace processor are installed in the snapshot. Offline PerfettoSQL
is available through `lb.py report`. Candidate-authored artifacts support the
workflow score; independent hidden execution decides final correctness and
performance.
