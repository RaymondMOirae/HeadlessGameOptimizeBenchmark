# Extreme V3：一帧执行内容详解

## 1. 总览

该程序没有渲染器。一帧代表游戏服务器把确定性世界向前推进一次。每个 warmup
帧和 measured 帧执行相同流程：

```text
Input
  → Navigation
  → Population Update
  → Component Queries
  → Transform Propagation
  → Collision Detection
  → Interest Management
  → Ordered Events
  → Finalize Digest
  → Record Snapshot
  → Optional Rollback
  → Tick/Perfetto Counters
```

顺序是语义的一部分。组件变化会影响 query 和队伍，Transform 会影响 collision，
collision/query/interest 的计数又会参与 event 生成，所有状态最终进入 snapshot 和
checksum。

## 2. 世界如何生成

### 2.1 初始化随机序列

世界初始化由 seed 驱动的 SplitMix64 风格序列生成：

```text
random_state = seed XOR 0x4f1bbcdc6765d2a9

每次取值：
  random_state += 0x9e3779b97f4a7c15
  value = 多轮 XOR、右移和 64 位乘法混合(random_state)
```

它不是密码学随机数，而是确定性数据生成器。相同 seed 和参数会产生完全相同的
世界。

### 2.2 网格

地图有 `width × height` 个 cell。每格生成：

```text
terrain = 1 + random % 4
blocked = random % 100 < 9
```

因此地形代价为 1–4，约 9% cell 初始不可通行。

### 2.3 目标

每个 goal 先用 `random % cell_count` 选择。如果与已有 goal 重复，就按 cell
编号向后查找。所有 goal 强制设为可通行，后续地图编辑也不会修改 goal cell。

### 2.4 单位

单位 ID 与 vector index 相同。每个单位初始化：

```text
cell             = random % cell_count
goal_slot        = random % goal_count
flags            = random 的低 8 位
component_mask   = 1 OR random 的低 8 位
health           = 80..120
energy           = 900..1200
cooldown         = 0..16
inventory_digest = random 64 位值
behavior_state   = random 64 位值
```

前 `navigator_count` 个单位负责寻路，它们的出生 cell 会被修正为可通行。其余
单位不做这一限制。component mask 的低两位同时表示 interest team：

```text
team = component_mask & 3
```

### 2.5 Transform

Transform 按 ID 顺序生成。除根节点外：

```text
parent = random % current_id
```

所以父 ID 总小于子 ID，不会形成环。ID 0 以及每 4096 个节点是根。local
matrix 使用 1024 代表 1.0 的定点数，local position 位于 -1000..1000。

### 2.6 Collider

Collider 通过固定公式绑定 Transform：

```text
transform = collider_id × 2654435761 % transform_count
half_x/half_y = 6..40
layer = 1、2、4、8 之一
mask = 1..15
```

## 3. 每帧“随机”变化如何生成

运行期不用连续推进的全局随机状态，而使用键控函数：

```text
R(seed, tick, salt)
```

其输入是世界 seed、当前 tick 和操作专属 salt，经相同的 64 位混合函数得到结果。
因此同一帧同一操作永远得到相同值，某系统增加临时计算不会消耗其他系统的随机
序列。

主要 salt 命名空间：

| 范围 | 用途 |
|---|---|
| `0x1000` | 地图编辑 |
| `0x2000` | navigator 目标切换 |
| `0x3000/0x4000` | population update |
| `0x5000` | Transform local 修改 |
| `0x7100/0x7900` | query 描述和副作用 |
| `0x8100` | component structural change |
| `0x8900` | interest position churn |
| `0xe000` | event 生成 |

## 4. Input 阶段

### 4.1 地图编辑

当 `edit_period != 0` 且 `tick % edit_period == 0` 时，每次编辑计算：

```text
cell = R(seed, tick, 0x1000 + edit_index) % cell_count
```

若命中 goal，就向后寻找非 goal cell，然后切换 `blocked[cell]` 并递增
`grid.revision`。这会要求导航缓存正确失效。

### 4.2 目标切换

当 `tick % 13 == 5` 时，改变最多七个 navigator：

```text
index = R(seed, tick, 0x2000 + change) % navigator_count
goal_slot = (goal_slot + 1 + change) % goal_count
```

### 4.3 Transform local 修改与 reparent

每帧从后半部分 Transform 中选择节点，local X/Y 各增加 -4..4。每 11 次修改
还会让 local A/D 各变化 -1..1。

到达 `tick % reparent_period == reparent_period - 1` 时，选择一个非根节点并设置：

```text
new_parent = random_high_32_bits % node_index
```

新父级仍位于节点之前，但该节点整棵子树的 world transform 都可能失效。

### 4.4 Component structural change

每次结构变化选择：

```text
unit = R(seed, tick, 0x8100 + change × 47) % unit_count
bit  = 1 << ((value >> 21) & 7)
component_mask ^= bit
```

mask 若变为 0，则设回 1。同一单位可能在一帧内被选择多次。低两位变化还会改变
interest team。

### 4.5 普通单位位置 churn

只选择非 navigator unit：

```text
delta = ((value >> 29) % 9) - 4
cell = (cell + delta + cell_count) % cell_count
```

这是用于制造空间索引变化的合成移动，按线性 cell 编号环绕，不模拟真实物理。

## 5. Navigation

只有前 `navigator_count` 个单位寻路。每个单位取得 start 和当前 goal。如果两者
相同就原地不动，否则基线从 goal 反向执行一次 Dijkstra。

四邻居的固定顺序是：

```text
上 → 左 → 右 → 下
```

从当前已知 cell 向 predecessor 松弛时：

```text
candidate = distance[cell] + terrain[cell]
```

blocked predecessor 被跳过。距离场完成后，从 start 的四个邻居中按固定方向顺序
选择：

```text
terrain[neighbor] + distance[neighbor]
```

最小者。比较使用严格 `<`，所以相同成本时保留较早方向；无可达邻居则不移动。

移动后：

```text
energy -= terrain[next]
if energy < -2000: energy = 1200
```

无论移动与否，`(unit.id << 32) XOR unit.cell` 都按 navigator 顺序混入 route
digest。基线瓶颈是每个 navigator 单独重做完整 Dijkstra。

## 6. Population Update

每帧最多修改 `mutations_per_frame` 个单位：

```text
index = R(seed, tick, 0x3000 + mutation × 17) % unit_count
value = R(seed XOR unit.id, tick, 0x4000 + mutation)
```

副作用：

```text
health += value % 7 - 3
越出 [-50, 180] 后重置为 100
cooldown = (cooldown + 1 + (value & 3)) % 31
inventory_digest = mix(inventory_digest, value)
behavior_state ^= value + tick
```

同一单位可以在一帧内多次命中，所以执行顺序可观察。

## 7. Component Queries

每个 query 需要三个 bit、排除一个不同 bit，并选择 energy、cooldown、behavior
三种 operation 之一。query 描述每三帧更新一次：

```text
query_epoch = tick / 3
```

匹配条件：

```text
(mask & required) == required
AND (mask & excluded) == 0
```

基线对每个 query 扫描全部 unit，按 unit ID 收集 match vector，再按 query
sequence 和 ID 顺序执行副作用。每个 query 和 match 都进入 query digest。

优化可以使用 bitset/archetype/index，但必须处理结构变化、稳定枚举和 rollback
后的索引重建或失效。

## 8. Transform Propagation

根节点把 local 直接复制为 world；子节点按父子顺序执行 2×2 矩阵与位移组合。
例如：

```text
world_x = parent.world_x
        + (parent.world_a × local_x + parent.world_c × local_y) / 1024
```

其余矩阵分量使用相同定点规则。整数乘加和除法位置是语义的一部分，改成浮点或
改变运算顺序可能导致摘要不同。

基线每帧重算所有节点。优化需要把 local mutation、祖先变化和 reparent 精确
传播到全部后代。每帧固定抽样最多 32 个节点写入 transform digest。

## 9. Collision Detection

每个 collider 根据 world position 生成 AABB：

```text
min = world - half_extent
max = world + half_extent
```

双方 mask/layer 必须互相允许，且四个轴向比较都使用 `<=`，所以边缘接触也算
碰撞。基线枚举全部 `left < right` 组合。

碰撞对编码为 `(left << 32) | right`，按 collider ID 的规范顺序进入摘要。任何
broad-phase 优化都必须去重、无遗漏，并恢复相同全局 pair order。

## 10. Interest Management

每个 observer slot 在每帧选择：

```text
observer_index =
  (slot × 2654435761 + tick × 17) % unit_count
```

候选可见条件：

```text
candidate != observer
AND candidate.team == observer.team
AND ManhattanDistance <= interest_radius
```

`team = component_mask & 3`。基线为每个 observer 扫描全部 unit，按 ID 生成
visible vector，再与该 slot 的 `previous_interest` 有序合并，产生 leave、enter、
stay。delta 修改 observer behavior，当前 visible 成为下一帧 previous state。

注意 previous state 属于 observer slot，而非永久绑定某个 unit。空间索引必须
处理队伍变化、位置 churn、稳定 ID 顺序和 rollback。

## 11. Ordered Events

事件数：

```text
min(events_per_frame, unit_count × 8)
```

事件随机输入同时包含：

```text
seed XOR collision_pair_count
     XOR query_match_count
     XOR (interest_visible_count << 1)
```

第 `sequence` 个事件使用 salt `0xe000 + sequence × 29`，并计算：

```text
target = value % unit_count
kind = (value >> 17) % 3
payload_size = 16 + value % 48
```

三类事件分别修改：

- kind 0：health；
- kind 1：cooldown 和 energy；
- kind 2：flags 和 inventory digest。

事件严格按生产顺序派发，payload 也进入摘要。基线为每个事件分配多态堆对象和
独立 payload，是 allocation/dispatch 热点。

## 12. Finalize Digest

帧末把以下信息混入 simulation digest：

- tick 和 grid revision；
- route/transform/collision/event/query/interest digest；
- collision/query/interest 三类计数；
- 按 `(tick × 977) % units` 选取单位的 inventory 和 cell。

它把整帧中间过程压缩为可比较状态。少处理一个单位、重排事件或使用过期 cache
都会传播到最终 checksum。

## 13. Snapshot 与 Rollback

Finalize 后将快照写入：

```text
slot = source_tick % history_capacity
```

快照复制 units、transforms、blocked grid、grid revision、previous-interest、七个
可回退系统 digest 和三类计数。

满足以下条件时回滚：

```text
rollback_period != 0
AND tick >= rollback_depth
AND tick % rollback_period == rollback_period - 1
```

恢复目标：

```text
target_tick = tick - rollback_depth
```

当前帧先完整执行并保存，再恢复旧动态状态。逻辑 tick 仍推进到 `tick + 1`，所以下
一帧是“新帧号配旧世界状态”。恢复状态的 hash、target tick 和当前 tick 被混入
独立 rollback digest；rollback digest 本身不会随普通快照回退。

实现级 route field、component index、spatial index 或 dirty flags 不属于基准语义
状态，但必须在 rollback 后自行重建、版本化或正确失效。

## 14. 帧结束与性能数据

最后设置：

```text
world.tick = tick + 1
```

并写入 Perfetto counter：Units、GridRevision、HistoryBytes、Transforms、
CollisionPairs、Events、QueryMatches、InterestVisible。

`run.json.measured_ns` 只覆盖 measured frame 循环；Profile trace 的 Frame slice
还包含 warmup。隐藏性能评分使用基线和候选整个子进程的外部 wall-clock 中位数，
因此候选不能靠修改自身时间字段得分。

## 15. 一帧为什么难优化

难点不在单个 O(N²) 循环，而在状态依赖：

- 地图编辑要求 route cache 失效；
- component mask 同时影响 query 和 team；
- reparent 影响 Transform 子树，再影响 collision；
- collision/query/interest 计数影响 event 随机序列；
- event 修改 unit，后续 snapshot 必须保存；
- rollback 会把 mask、Transform、位置和 previous-interest 一起恢复；
- 所有可观察集合与副作用都要求规范顺序。

因此正确优化通常需要多种结构共同工作：共享路由场、dirty propagation、碰撞
broad phase、component bitset、team/cell 空间索引、packed event 和稀疏/全量
自适应历史，同时为 rollback 和 invalidation 建立明确策略。
