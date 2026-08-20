# DECOUPLING_ADAPTER: 为什么 Adapter 要这样设计

Adapter 是“搜索策略内核”。它只负责 **propose/update**，不负责问题细节、约束细节或工程能力。

> 一句话定位：**Adapter 决定“怎么搜”，但不决定“搜什么、如何评估、如何修复”。**

这不是形式主义，而是为了让实验 **可复现、可比较、可演化**。

---

## 1) 为什么必须把 Adapter “缩小到策略内核”

### 传统痛点
- 算法里混入问题逻辑 → 换问题就得重写算法。
- 算法里混入约束/偏好 → 对比实验变成“比谁写得更乱”。
- 算法里混入日志/并行 → 工程改动导致算法不可复现。

### 解法
把 Adapter 收缩成“纯策略”，其余职责由其他组件承担：

- **硬约束**：Pipeline 负责
- **软约束/偏好**：Bias 负责
- **评估口径**：Problem/Plugin 负责
- **工程能力**：Plugin 负责

这样做的直接好处：
- **策略可替换**：同一问题可快速切换策略
- **实验可比较**：只变 Adapter 时，其他变量不变
- **可演化**：策略升级不污染问题/工程层

---

## 2) 如果不这样做，会发生什么（反例）

### 反例 A：把约束写进 Adapter
后果：
- 约束逻辑分散、不可复用
- 其他算法无法共享同一约束
- 复现实验时“算法里藏约束”，难以审计

### 反例 B：把偏好写进 Adapter
后果：
- 偏好无法开关、无法比较
- 实验结论混淆“策略好”还是“偏好强”

### 反例 C：把评估/日志写进 Adapter
后果：
- 工程改动会影响算法行为
- 并行/缓存导致状态不一致

---

## 3) Adapter 的职责边界（清楚、可执行）

Adapter **只做**：

- 生成候选解（propose）
- 根据评估结果更新内部状态（update）
- 维护策略相关的内部参数（如温度、权重、邻域选择）

Adapter **不做**：

- 不直接访问业务约束（约束在 Pipeline）
- 不编码领域偏好（偏好在 Bias）
- 不决定评估口径（评估在 Problem/Plugin）
- 不做日志/并行/复现（工程能力在 Plugin）

---

## 4) 这样拆解的“好处”是什么

- **可复现**：策略变了就是 Adapter 变了，其他不动
- **可比较**：不同策略在同一问题/管线/偏置下公平对比
- **可组合**：多个 Adapter 可协同编排（Multi-Strategy）
- **可维护**：策略升级不影响工程和问题定义

---

## 5) 什么时候应该“新增 Adapter”

当你的改进满足以下条件之一：

- 搜索策略发生了根本变化（全局 → 局部、单策略 → 多策略协同）
- 你希望这个策略可替换、可复用、可对比
- 你希望把策略逻辑从偏置/管线中剥离

否则优先考虑：

- **Bias**：只是改变“偏好方向”
- **Pipeline**：只是改变“可行性/修复方式”
- **Plugin**：只是增加“评估/记录/并行能力”

---

## 6) 最小接口心智模型

```
propose() -> candidates
update(evaluations) -> state
```

只要满足这一点，Adapter 就可以被：

- `ComposableSolver` 统一编排
- `MultiStrategyController` 协同调度
- `Wiring` 权威装配

---

## 7) 典型 Adapter 拆解示例（思路）

### 丰富反馈不是新的算法边界

Solver 现在向 Adapter 交付 `OptimizationFeedbackBatch`。它同时保留两种视图：

- 优化视图：`objectives` 与权威 `violations`，供 NSGA、DE、SA 等通用策略使用；
- 语义视图：逐候选的 `blackbase.types.Feedback`，可携带 `gradients`、`loss`、
  `metrics`、`residuals` 和 provider 信号。

旧 Adapter 无需迁移，二元解包仍然成立：

```python
def update(self, control, candidates, feedback, context):
    objectives, violations = feedback
```

需要梯度或训练信号的 Adapter 可以显式读取语义项：

```python
def update(self, control, candidates, feedback, context):
    objectives, violations = feedback
    gradients = [item.gradients for item in feedback.items]
```

这条边界只负责**携带证据**，不在 Solver 中解释 ML 语义。梯度如何产生、模型处于
训练态还是推理态、GPU tensor 如何管理，仍由对应 provider/扩展层负责。复合 Adapter
必须使用批反馈的 `subset()` 切分，以便在多策略、Role 和事件路由中保留完整语义项。

一阶优化也遵守同一拆分。`GradientOptimizerAdapter` 只实现 SGD/Adam/AdamW 的更新
机制，梯度由任意解析梯度或 Autograd provider 产生：

```python
from nsgablack.adapters import GradientOptimizerAdapter, GradientOptimizerConfig

adapter = GradientOptimizerAdapter(
    GradientOptimizerConfig.from_method("gradient.adam", learning_rate=1e-3)
)
```

如果反馈没有 `gradients`，该 Adapter 会明确失败，不会悄悄切换成另一种算法。需要
数值差分时，应显式使用原有的 `GradientDescentAdapter`。这使“机制选择”成为可审计
装配，而不是隐藏 fallback。

Provider 也可以在 `Feedback.gradient_ref` 与 `evaluation_state_ref` 中发布进程内
`StateRef`。此时 Adapter 仍只选择稳定方法和参数，实际设备 kernel 通过 BlackBase
`StateTransitionRequest` 执行；更新后的参数必须经 `StateMaterializationRequest`
导出后才能进入 checkpoint。旧进程的活引用不会跨恢复继续使用。

### 模拟退火（SA）
- **Adapter**：温度调度 + 接受准则
- **Pipeline**：邻域生成与修复
- **Bias**：探索/收敛倾向

### VNS
- **Adapter**：邻域阶段控制
- **Pipeline**：多邻域算子 + 修复

### 多策略协同
- **Adapter**：协调器（预算分配、共享状态）
- **Plugin**：档案、记录、并行评估

---

## 8) 常见误区清单（快速自查）

- [ ] 我是不是把约束逻辑写进了 Adapter？
- [ ] 我是不是把偏好硬编码进 Adapter？
- [ ] 我是不是在 Adapter 里做日志/统计？
- [ ] 我是不是因为“方便”把策略和评估耦合在一起？

只要有一个“是”，就应该拆出来。

---

## 9) 相关入口

- `adapters/`：Adapter 实现
- `utils/wiring/`：权威组合装配
- `docs/guides/DECOUPLING_REPRESENTATION.md`
- `docs/guides/DECOUPLING_BIAS.md`
- `docs/guides/DECOUPLING_CAPABILITIES.md`

---

## 10) 关于权威 incumbent 的标量化契约

`ComposableSolver` 会维护一次 run 内的权威 incumbent。默认先按可行性比较，
在同一可行性层级内再使用稳定标量：

- `score = sum(objective_row)`

约束违反量由 feasibility-first 比较器单独处理，不再通过固定惩罚系数混入目标。
Pareto front 仍保留完整多目标语义，incumbent 是显式策略选出的权威单点。

因此框架提供一个**可选的 scalarizer**（你可以不改任何代码，只有在需要更稳摘要时才用）：

```python
from nsgablack.core.composable_solver import ComposableSolver

def weighted_sum(objective_row, violation, context):
    # pointwise：只能读取当前候选和固定 context，不能读取整个 batch
    del violation
    weights = context["weights"]
    return sum(float(w) * float(v) for w, v in zip(weights, objective_row))

solver = ComposableSolver(problem=problem, adapter=adapter)
solver.set_incumbent_scalarizer(
    weighted_sum,
    policy_id="weighted_sum/v1",
    context={"weights": [0.7, 0.3]},
    failure_policy="raise",
)
```

**建议**：
- scalarizer 异常默认终止 incumbent 选择，不能静默换一套排序规则。
- 如确需容错，显式使用 `failure_policy="fallback_sum"`；结果会记录降级次数。
- 依赖整个 population 的相对排序属于 Adapter 代内选择，不能定义跨代 incumbent。

checkpoint 使用 `nsgablack.checkpoint.v4` 保存完整 incumbent、scalarizer policy/context、token 对齐的 CandidateBatch population、
failure policy、fallback 次数、质量退化状态、run sequence，以及 Solver 声明的
Adapter / Representation / Provider / DataSchedule 等 stateful components。恢复时 builder
必须先重建同一 scalarizer 和组件身份，policy、固定 context 或组件类型不一致会拒绝继续；历史 v1/v2 只能通过显式迁移读取，
其缺失的 scalarizer 审计会标记为 unknown，而不是伪装成“从未降级”。

ContextStore 只允许在配置的序列化尺寸阈值内内联 `best_x`。超过阈值后，候选写入
SnapshotStore，Context 只保存规范 `best_candidate_ref`；目标摘要仍可保持轻量内联。
warm-start 候选在进入候选批次时获得稳定 token，该 token 随 repair 和 evaluate 的行级
sidecar 传播，因此相同数值的普通提案不会被误认成 warm-start。

Adapter 的代内局部最佳与 Solver 的跨代权威 incumbent 是两套不同语义。Adapter runtime
projection 必须使用 `adapter_best_x`、`adapter_best_objectives`、`adapter_best_score`，不得
发布 `best_x`、`best_candidate_ref`、`best_objective`，也不得覆盖 Solver 的 `generation` 或
`evaluation_count`。正式投影接口固定为 `get_runtime_context_projection(self, solver)`，每次
采集最多调用一次；内部 `TypeError` 按真实运行错误报告，不能被当成签名兼容信号重试。

正式消费者统一通过受控 runtime projection 网关读取 Adapter 遥测。网关同时执行
保留字段检查、单字段尺寸预算和整体尺寸预算；超限字段被省略并进入
`runtime_projection_audit`。网关不会在监控轮询中自动写 Snapshot，也不会为未知对象
制造不可解析的引用。大对象如确需交付，必须由拥有 codec 和生命周期的 Plugin/Adapter
先发布真实 `*_ref`。

普通 Adapter 投影的外层审计使用 `ok / unavailable / error / invalid_result` 四态；正式组合
投影额外允许 `degraded`，因此完整外层状态机是五态。没有 Adapter 或正式投影器属于健康的
`unavailable`；组合子单元部分失败使用 `degraded`；执行异常、组合全部失败与非法非 Mapping
返回都必须标记为不健康，且 `degraded / error / invalid_result` 均不得声明 `current=True`。
组合信封自身只使用 `ok / degraded / error`，并由 blackbase 校验状态与组件分类计数一致。
嵌套组合发生降级或失败时，父级问题证据通过固定 64 位 `cause_digest` 吸收子信封的
`audit_digest`；父级不展开子级样本，但不同的深层原因仍会形成不同的父级摘要和去重事件。
子投影的调用、验证、状态计数、因果摘要与 first-writer 字段合并统一由 blackbase
`aggregate_runtime_projections()` 完成。nsgablack 组合器只声明活动拓扑：Composite 使用全部
子 Adapter，Async 使用当前启用策略（事件 Case 模式仅当前活动 Case），Role 包装器使用
`inner`，RoleRouter 使用全部 role，SerialChain 仅使用当前活动阶段，MultiStrategy 使用启用 unit。
事件 Case 尚未选出活动 Case 时，活动子拓扑必须为空；Context 投影是观测操作，不得为了生成
审计而提前选择或启动 Case。字段 writer 随 blackbase 信封递归传播，Solver 外层审计只保留
有界叶子写入者样本、完整计数和独立 `field_source_digest`，不得把直接父包装器伪装成实际写入者。
任何新增复合 Adapter 都必须接入同一聚合器，不能以空字典或仅自身字段掩盖子组件健康。
审计仅保存固定数量且类型化的冲突/省略/组件问题样本、完整计数、原因计数和稳定摘要；字段名、
错误消息、组件审计及完整外层审计均有硬字节上限。每次 fresh run 都会清除上一运行的审计与
去重 signature，审计隔离失败也必须以最小 `error` 信封原子替换旧证据。

