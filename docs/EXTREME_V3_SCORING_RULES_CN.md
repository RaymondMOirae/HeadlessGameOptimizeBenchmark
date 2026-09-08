# Extreme V3：Code Grade 评分规则

> 出题方内部文档。本文包含隐藏性能门槛，不应随候选 workspace 发放。

## 1. 评分目标

评分器同时判断三件事：

1. 优化后是否保持完全相同的游戏语义；
2. 每个主要系统是否获得足够且可复现的性能提升；
3. 被测 Agent 是否真实完成了“打点、分析、修改、复测”的多轮工作流。

最终结果包含：

```json
{
  "resolved": false,
  "score": 0.79,
  "reason": "详细评分原因"
}
```

`resolved` 是是否通过的唯一硬判定；`score` 用于描述完成程度和排序，不能替代
硬门槛。

## 2. 独立评测过程

评分器不使用候选生成的性能结论作为最终真值，而是：

1. 校验并解压出题方保存的原始基线源码；
2. 分别以 CMake Release、Perfetto OFF 构建基线和候选；
3. 执行 13 个隐藏语义用例；
4. 执行 13 个隐藏性能用例并再次校验输出；
5. 每个性能用例交替运行基线和候选三轮；
6. 用两者外部 wall-clock 中位数计算加速比；
7. 独立解析九份 Perfetto trace、manifest、findings 和 comparison；
8. 计算原始分、硬门槛、gate coverage 和最终上报分。

单次用例超时为 45 秒，stdout 上限为 64 KiB。构建失败、附件异常、输出非法或
评分器异常都 fail-safe 为 `resolved=false`。

## 3. 100 分构成

| 部分 | 分值 | 主要内容 |
|---|---:|---|
| Hidden semantics | 25 | 13 个隐藏用例的精确结果比较 |
| Hidden performance | 45 | 9 个性能家族、13 个负载的相对加速 |
| Nine-trace workflow | 25 | 九份 trace、四轮诊断/优化、findings 和 provenance |
| Hygiene | 5 | 源码确实变化且全部隐藏输出正确 |

语义分：

```text
semantic_points = 25 × semantic_passes / 13
```

只要任一隐藏语义或 timed correctness 错误，performance 整段为 0，hygiene 也
为 0。性能提升不能补偿游戏结果错误。

## 4. 正确性字段

基线和候选必须精确匹配以下 19 个字段：

- `checksum`；
- `route_digest`、`rollback_digest`；
- `transform_digest`、`collision_digest`、`event_digest`；
- `query_digest`、`interest_digest`；
- `collision_pair_count`、`query_match_count`、`interest_visible_count`；
- `units`、`navigators`、`frames`；
- `transforms`、`colliders`；
- `events_per_frame`、`component_queries`、`interest_observers`。

候选报告的 `measured_ns` 和帧分位数只用于自查，不作为隐藏性能真值。

## 5. 性能采样与聚合

单用例加速比：

```text
case_ratio = median(baseline_wall_time[3])
             / median(candidate_wall_time[3])
```

同一性能家族包含多个用例时：

```text
family_ratio = geometric_mean(case_ratios)
```

总体加速比：

```text
speed_geo = geometric_mean(nine_family_ratios)
```

隐藏性能门槛如下：

| 性能家族 | Family aggregate floor | Case guard（90%） |
|---|---:|---:|
| route | 3.00x | 2.700x |
| history | 1.25x | 1.125x |
| transform | 2.00x | 1.800x |
| collision | 2.50x | 2.250x |
| events | 1.50x | 1.350x |
| invalidation | 2.00x | 1.800x |
| mixed | 2.50x | 2.250x |
| query | 1.80x | 1.620x |
| interest | 2.00x | 1.800x |

每个家族必须同时满足：

```text
family_ratio >= family_floor
min(case_ratios) >= family_floor × 0.90
```

`case_guard:pass` 只表示某个 case 达到 90% 保护线，不表示完整的
`family_gate` 已通过。对于只有一个 case 的 family，两处使用相同 ratio，但门槛
仍不同。

## 6. Performance 45 分公式

Family 部分共 21 分，九个家族均分：

```text
single_family_points =
    (21 / 9) × clamp((family_ratio - 1) / (floor - 1), 0, 1)
```

总体 geo 部分共 24 分，在下列节点间按 `log(speed_geo)` 线性插值：

| speed_geo | Geo points |
|---:|---:|
| 1.0x | 0 |
| 1.5x | 6 |
| 2.1x | 13 |
| 4.0x | 20 |
| 8.0x | 24 |

超过 8x 仍为 24 分，performance 总分封顶 45。

## 7. Workflow 25 分

| 证据 | 分值 | 判定 |
|---|---:|---|
| baseline | 2 | 原始源码 hash、合法 trace、四个 coarse zone |
| 四个 diagnostic | 8 | 各 2 分；2/4/6/8 个 marker，每轮至少两个新名称 |
| 三个中间 checkpoint | 6 | 各 2 分；结果一致、源码独立、原始 Frame 至少 1.04x |
| findings | 3 | 覆盖 primary/state/scale/tail，数值与对应 trace 一致 |
| optimized | 2 | 最终源码 hash、八 marker、结果一致、第四段至少 1.04x |
| provenance/comparison | 4 | 九个源码/trace hash 唯一、有序且 comparison 合法 |

九个 trace tag 的固定顺序是：

```text
baseline
diagnostic_primary
checkpoint_primary
diagnostic_state
checkpoint_state
diagnostic_scale
checkpoint_scale
diagnostic_tail
optimized
```

阶段 1.04x 增益由评分器直接查询 Perfetto `Frame` slice 总时长。不能通过修改
`run.json` 或 `comparison.json` 伪造。

Findings 必须有 4–8 条，按 rank 排列，覆盖四个阶段，引用真实 live zone、真实
源码文件和 symbol。`calls` 容差为 0.1；时间指标容差为
`max(0.25 ms, |actual| × 15%)`。

## 8. `resolved=true` 硬门槛

只有以下条件全部成立才通过：

```text
13/13 hidden semantics
AND 所有 timed output 正确
AND 9 个 family aggregate 全部达到各自 floor
AND 每个 case 达到其 90% guard
AND speed_geo >= 2.30x
AND workflow >= 23/25
```

这是 AND gate。某个家族获得数百倍提升，不能抵消 history、events 或其他家族
未达标。

## 9. Raw score、gate coverage 与 0.79 封顶

`raw_score` 为四部分直接相加的 0–100 分。

`gate_coverage` 取下列归一化覆盖度的最小值，并限制在 0–1：

- 每个 family ratio / family floor；
- 每个 worst case / case guard；
- speed geo / 2.30；
- workflow / 23；
- semantic pass fraction；
- timed correctness。

未通过时：

```text
multiplier = 0.65 + 0.35 × gate_coverage
pre_cap = raw_score × multiplier
reported_score = min(pre_cap, 79分)
```

通过时：

```text
reported_score = raw_score
```

因此高原始分但缺一个硬门槛的提交会显示：

```text
resolved=false
raw=99.8/100
pre-cap=99.7/100
reported=79.0/100
failed gates: history_aggregate ...
```

这既保留诊断信息，也避免 `resolved=false` 与接近满分同时出现。

## 10. 数值精度说明

门槛判断使用未舍入浮点数，而当前 reason 中 ratio 只显示两位小数，因此可能
出现：

```text
history=family_gate:FAIL,1.25x<1.25x
```

实际含义可能是 `1.2487 < 1.2500`。这属于展示精度，不是判定错误。不可使用
`round(ratio, 2)` 放宽判定；推荐后续把 ratio、coverage、时间和门槛统一显示
至少四位小数，并显示相对门槛 gap。

## 11. 结果解读顺序

建议按以下顺序分析失败：

1. 是否构建失败或超时；
2. 是否 13/13 semantics；
3. timed correctness 是否全对；
4. workflow 是否达到 23/25；
5. 哪个 case guard 或 family gate 未达标；
6. speed geo 是否达到 2.30x；
7. 最后再比较 raw score 和各家族余量。

模型比较优先使用 resolved rate，再报告语义通过率、workflow 通过率、各家族
speedup 分布和 raw score。不能仅按 reported score 排序。

