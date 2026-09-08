# Extreme V3 Integrated Frame Pipeline

This is the evolved long-horizon optimization case. The previous
Dynamic-Navigation + Rollback revision has been archived externally; the current
workspace adds Dirty Transform, Broad-phase Collision, ordered Event
Allocation/Dispatch, ECS Component Query Churn and replication Interest
Management to the same simulation.

The public source is functionally correct. The task now requires nine distinct
Perfetto traces across four measured optimization iterations, exact cross-system
rollback behavior and separate hidden floors for route, history, transform,
collision, events, invalidation, component query, interest and mixed workloads.

Author-side build from the repository root can reuse the pinned Perfetto SDK:

```text
cmake -S challenges/nav_rollback -B build-nav-rollback -G Ninja
cmake --build build-nav-rollback
```

When packaged for DSBench, `third_party/perfetto` and the target-platform trace
processor are injected into this challenge workspace.
