# Advanced-case pilot protocol

The target pass band is a measured rollout property, not something that should
be declared from source complexity. The archived two-bottleneck revision used
10–30%; Extreme V3 targets 10–30% and must remain below 50%. Use this protocol after uploading the
Linux package and before freezing a benchmark version.

## Sample design

- Run 12–20 independent rollouts per model, with at least two model families.
- Keep the agent framework, prompt snapshot, tool budget and timeout identical.
- Randomize model/run order across the same worker pool and retain failed task
  workspaces, Code Grade JSON and terminal logs.
- Do not tune after looking at a single model pair. Pool capable-model runs for
  the configured target band, but report each model separately for discrimination.
- Freeze a holdout set of semantic seeds and one performance workload family for
  the final confirmation pass.

Aggregate downloaded `code_result.json` files with:

```text
python challenges/nav_rollback/authoring/analyze_pilot.py \
  --group model_a=pilot/model_a --group model_b=pilot/model_b \
  --target-min 0.10 --target-max 0.30
```

The output includes pass-rate Wilson intervals, score quartiles, exact-semantics
rate, workflow-gate rate and per-family speedup quartiles. With only 12–20 runs,
the confidence interval will remain wide; use the band as a tuning signal rather
than a precise estimate.

## Interpret failures in gate order

1. **Build or timeout:** fix environment reliability; do not lower performance
   thresholds to compensate.
2. **Hidden semantics:** inspect which temporal case fails. A task where almost
   every attempt fails correctness may be testing ambiguity rather than skill.
3. **Nine-trace workflow:** distinguish missing raw traces from invalid
   provenance, nonexistent source symbols or findings unsupported by live zones.
4. **Family floors:** identify the isolated family that blocks resolution. A
   large navigation win must not compensate for no history improvement.
5. **Geometric mean:** use only after all isolated families show useful gains.

Tune one gate at a time. If pass rate is above the configured maximum, first raise the floor for the
family most often skipped by partial solutions or add a held-out invalidation
shape. If pass rate is below the configured minimum, lower only a noisy performance floor for
otherwise exact, workflow-complete attempts. Do not weaken temporal or checksum
oracles to hit the target.

## Required author-side ablations

Before a pilot, run four private controls against the independent grader:

| Control | Expected outcome |
|---|---|
| unchanged source | exact semantics, no speed/workflow resolution |
| instrumentation only | workflow partial, no performance resolution |
| primary algorithmic checkpoint only | route/collision improve; other floors fail |
| state checkpoint only | history/transform also improve; event floor still fails |
| private reference solution | all gates pass with margin |

If either one-subsystem control resolves, the family floors are not doing their
job. After tuning, version the config and never alter thresholds for a published
model comparison.
