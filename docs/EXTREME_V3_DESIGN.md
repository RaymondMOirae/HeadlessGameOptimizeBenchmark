# Extreme V3: multi-distribution integrated frame pipeline

Extreme V3 supersedes the archived V2 task. It remains a C++20, renderer-free,
single-process simulation, but adds two stateful game-server systems and a fourth
measured optimization iteration. The design goal is an empirical pass rate below
50%, with a pilot target band of 10–30%, without relying on a heavyweight engine.

## Frame dependency chain

Each frame executes deterministic input/structural changes, weighted navigation,
unit updates, component queries, transform propagation, broad-phase collision,
replication interest management, ordered events, finalization and snapshot/
rollback. Later systems consume state changed by earlier systems. Rollback restores
all semantic state while implementation-only indexes must be repaired safely.

## New hard systems

### ECS component-query churn

Units carry an eight-bit component mask. Query specifications change every three
frames, overlap, and execute in canonical unit-ID order. Matches mutate unit
energy, cooldown or behavior, so query reordering is observable. Structural
changes toggle masks before queries, while rollback can restore older masks.

The baseline scans all units and allocates a match vector for every query. A
competitive solution generally needs a mask/archetype or bitset index, cheap
structural maintenance, canonical enumeration and an explicit rollback rebuild or
versioning strategy.

### Replication interest management

Observers compute same-team Manhattan-radius visibility, canonical visible-ID
order and ordered enter/leave/stay deltas against a previous-frame set. Observers
and ordinary units move, structural changes can change team bits, and previous
interest sets are rollback state.

The baseline scans the complete population per observer. A competitive solution
needs spatial indexing while preserving stable global ordering and temporal delta
semantics.

## Anti-specialization evaluation

The hidden grader contains 13 semantic cases and 13 timed cases across nine
families. Transform, query, interest and mixed families use multiple parameter
distributions. The family value is the geometric mean of its cases, and its worst
case must also reach 90% of the family floor. This blocks optimization for a
single known scale or sparsity pattern.

## Four measured iterations

The workflow contains nine source-bound Perfetto traces: baseline, diagnostic and
checkpoint pairs for primary/state/scale, diagnostic tail, and optimized. The
four diagnostics require 2/4/6/8 cumulative live zones. Every checkpoint must
preserve the public result and improve raw Perfetto Frame time by at least 1.04x.
All nine source hashes and trace hashes must be distinct.

## Pass-rate policy

The task is released only after a mixed-model pilot. The desired band is 10–30%
resolved with a hard acceptance ceiling below 50%. Thresholds may be changed only
from pilot evidence; semantic contracts, hidden seeds and evidence validation are
not relaxed to hit a target rate.
