# Extreme V3 Code Grade specification

## Score composition

| Section | Points | Evaluation |
|---|---:|---|
| hidden semantics | 25 | 13 exact baseline/candidate comparisons |
| hidden performance | 45 | nine family aggregates, per-case floors and geo curve |
| nine-trace workflow | 25 | raw traces, measured findings, four stage gains, provenance |
| hygiene | 5 | changed logic, successful build and exact behavior |

The candidate output must match checksum; route, rollback, transform, collision,
event, component-query and interest digests; collision/query/visibility counts;
and all reported workload dimensions.

## Performance aggregation

Timed baseline/candidate executions alternate order and use the median of three
rounds. Families with multiple cases use
`family_ratio = geometric_mean(case_ratios)`. Every case must additionally meet
`case_ratio >= 0.90 * family_floor`.

| Family | Aggregate floor |
|---|---:|
| route | 3.0x |
| history | 1.25x |
| transform | 2.0x |
| collision | 2.5x |
| events | 1.5x |
| invalidation | 2.0x |
| mixed | 2.5x |
| component query | 1.8x |
| interest management | 2.0x |

The family portion is 21 points divided equally across nine families. The other
24 points use the log-interpolated geometric-mean curve: 1.0x→0, 1.5x→6,
2.1x→13, 4.0x→20 and 8.0x→24. Any wrong timed output makes the performance
section zero.

## Workflow — 25 points

| Evidence | Points |
|---|---:|
| pristine baseline trace | 2 |
| four distinct diagnostics with 2/4/6/8 live markers | 8 |
| three intermediate checkpoints with exact output and ≥1.04x stage gain | 6 |
| four-phase findings validated against raw Perfetto metrics | 3 |
| final exact optimized trace with fourth ≥1.04x gain | 2 |
| nine unique ordered source/trace hashes and V3 comparison | 4 |

## Resolved gate

`resolved=true` requires 13/13 semantics, correct timed outputs, every aggregate
and worst-case floor, family geometric mean at least 2.3x, and workflow at least
23/25.

The grader reports each timed case's `case_guard` separately from each family's
aggregate `family_gate`, then lists every failed hard gate. The case guard is
90% of the family floor; it prevents a weak case from being hidden by a strong
case in the same family, but passing it does not imply that the full aggregate
family gate passed. For a single-case family, both values are shown explicitly
even though the family aggregate equals that case's ratio.

Unresolved scores first receive a weakest-gate multiplier:

`reported_score = raw_score * (0.65 + 0.35 * gate_coverage)`

`gate_coverage` is the minimum normalized coverage across semantics, timed
correctness, family aggregates, case guards, geometric mean and workflow. The
result is then capped at `0.79` whenever `resolved=false`:

`reported_score = min(reported_score, 0.79) if unresolved`

This keeps `raw_score` useful for diagnosis while ensuring a failed hard gate
cannot appear as a near-perfect platform score. Fully resolved submissions
retain the uncapped raw score. When the cap applies, the reason string reports
both the calculated `pre-cap` score and the `unresolved cap`.

## Author calibration

The unchanged baseline resolved false at approximately `0.1661`: semantics and
timed outputs were correct, but all speed families and the workflow gate failed.

The composed private reference preserved all 26 semantic/timed outputs and
resolved at `0.9807` with workflow `25/25` and family geometric mean `5.73x`.
Family aggregates were approximately route `29.41x`, history `1.58x`, transform
`2.55x`, collision `32.34x`, events `3.18x`, invalidation `9.91x`, mixed `7.01x`,
component query `1.91x` and interest `4.12x`. The four public raw-Frame stage
gains were `1.95x`, `1.53x`, `1.64x` and `1.21x`, for `5.92x` end to end.

The same optimized source without workflow evidence scored `0.4750` and remained
unresolved, confirming that aggregate speed alone cannot replace the autonomous
profiling chain.
