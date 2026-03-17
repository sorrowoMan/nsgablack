# `nsgablack` Bias 面试复习文档

> 面向面试复习 / 偏置体系理解 / 业务引导落地。
>
> 本文基于仓库源码整理，重点参考：
>
> - `bias/bias_module.py`
> - `bias/core/base.py`
> - `bias/core/manager.py`
> - `core/solver_helpers/bias_helpers.py`

---

## 1. 先记住：Bias 在这个框架里是什么

Bias 是**软引导层**，不是硬约束求解器。

它做的是：

1. 用算法偏置影响搜索方向
2. 用领域偏置注入业务知识
3. 在不破坏主流程的前提下提升收敛效率与可行性命中

一句话：**Bias 负责“往哪里更值得搜”，不负责“保证一定可行”。**

---

## 2. Bias 核心组件分工

### `BiasModule`（`bias/bias_module.py`）

- Solver 侧统一入口
- 封装缓存与上下文适配
- 聚合算法偏置与领域偏置

### `OptimizationContext`（`bias/core/base.py`）

- 偏置计算上下文对象
- 提供代数、个体、指标、历史、问题数据

### `UniversalBiasManager`（`bias/core/manager.py`）

- 内部分离 `algorithmic_manager` 与 `domain_manager`
- 管理偏置注册、组合计算、统计信息

---

## 3. Bias 如何接到 Solver（真实链路）

关键在 `core/solver_helpers/bias_helpers.py::apply_bias_module(...)`：

1. 从 solver 拿到 `bias_module`
2. 绑定 `context_store` 与 `snapshot_store`
3. 调 `compute_bias(...)` 计算偏置后的目标值
4. 做输出归一化并回写评估流程

面试要点：

- Bias 是评估阶段的“修正项”
- 不改 `propose/update` 主算法契约

---

## 4. Bias 的上下文合同（contract）

Bias 体系支持：

- `context_requires`
- `context_provides`
- `context_mutates`
- `context_cache`
- `context_notes`

意义：

- 让偏置依赖显式化
- 降低“隐式字段耦合”
- 便于 catalog/doctor 做治理校验

---

## 5. 缓存与快照：为什么 Bias 也要接 Store

### 为什么

- 某些偏置计算昂贵、重复高
- context 里只应放轻量信息

### 怎么做

- `BiasModule.set_context_store(...)`
- `BiasModule.set_snapshot_store(...)`
- 结合 `cache_backend/cache_ttl_seconds/cache_context_keys`

一句话：

> Bias 用 store 是为了可复用、可追溯、可控成本，而不是把业务逻辑塞进缓存。  

---

## 6. 设计边界（高频追问）

### Bias 该做

- 软偏好引导
- 领域经验注入
- 指标驱动的轻量自适应

### Bias 不该做

- 替代 `repair` 做硬约束兜底
- 篡改 solver 生命周期
- 直接覆盖算法状态机

---

## 7. `ignore_constraint_violation_when_bias` 怎么答

可答：

- 这是工程开关，不是默认安全策略
- 只在约束已由 `repair`/业务逻辑充分处理时考虑
- 需要明确风险并配合监控与回归验证

---

## 8. Bias 常见组合模式

### 模式 A：领域约束引导 + 进化算法

- `NSGA2/NSGA3/SPEA2` + 领域偏置
- 目标：提高可行解密度

### 模式 B：代理模型 + 偏置协同

- `MAS/Surrogate` + Bias
- 目标：低成本探索 + 业务方向引导

### 模式 C：控制器策略 + 偏置反馈

- `MultiStrategy` + Bias
- 目标：按阶段调整偏置强度

---

## 9. Bias 逐项介绍（按导出清单一项项过）

以下名称来自 `bias/__init__.py::__all__`。

### 9.1 算法偏置（Algorithmic Bias）

| Bias | 作用一句话 | 适用场景 | 使用注意 |
| --- | --- | --- | --- |
| `DiversityBias` | 鼓励解分散，避免早熟 | 多峰、多目标前期 | 后期不降权会拖慢收敛 |
| `AdaptiveDiversityBias` | 按状态自动调多样性强度 | 搜索阶段切换明显 | 依赖状态指标质量 |
| `NicheDiversityBias` | 在局部 niche 内维持差异 | many-objective / niching | niche 划分策略要稳定 |
| `CrowdingDistanceBias` | 偏好拥挤距离大的个体 | NSGA 系流程 | 与 selection 语义要一致 |
| `SharingFunctionBias` | 用共享函数抑制密集区 | 多峰优化 | 共享半径参数敏感 |
| `ConvergenceBias` | 强化朝最优方向的推进 | 中后期精修 | 过早增强会塌缩多样性 |
| `AdaptiveConvergenceBias` | 自适应收敛强度 | 阶段性优化 | 触发阈值需调参 |
| `PrecisionBias` | 偏好高精度局部改进 | 收敛尾段 | 易陷局部，需要配探索 |
| `LateStageConvergenceBias` | 后期专用收敛推动 | 明确分阶段策略 | 前期启用会丢覆盖 |
| `MultiStageConvergenceBias` | 分阶段切换收敛策略 | 长周期优化 | 需有清晰 phase 计划 |
| `ParticleSwarmBias` | 引入粒子群式方向信息 | 连续空间全局探索 | 与 DE/GA 混用要限权 |
| `AdaptivePSOBias` | 自适应 PSO 偏置强度 | 动态景观问题 | 状态噪声会误触发 |
| `CMAESBias` | 引入协方差导向搜索 | 高维连续优化 | 计算开销较高 |
| `AdaptiveCMAESBias` | 自调协方差偏置力度 | 复杂高维地形 | 建议配预算控制 |
| `TabuSearchBias` | 惩罚回访、增强跳出局部 | 离散/组合优化 | tabu 列表过大影响效率 |
| `LevyFlightBias` | 通过长跳步增强探索 | 多峰远距探索 | 需防止步长过激 |
| `RobustnessBias` | 偏好对扰动更稳的解 | 噪声/不确定问题 | 需定义鲁棒性指标 |
| `UncertaintyExplorationBias` | 优先探索不确定区域 | 代理模型/主动学习 | 必须配真值回注 |

### 9.2 领域偏置（Domain Bias）

| Bias | 作用一句话 | 适用场景 | 使用注意 |
| --- | --- | --- | --- |
| `ConstraintBias` | 约束违反惩罚 | 通用约束优化 | 不替代 repair |
| `FeasibilityBias` | 优先可行区域 | 强约束问题 | 惩罚尺度要与目标同量纲 |
| `PreferenceBias` | 体现业务偏好 | 多目标偏好引导 | 需明确偏好来源 |
| `RuleBasedBias` | 规则函数注入业务知识 | 规则明确场景 | 规则冲突需治理 |
| `CallableBias` | 快速函数式偏置封装 | 快速实验 | 生产环境建议规范化 |
| `DynamicPenaltyBias` | 动态调整惩罚强度 | 约束逐步收紧 | 调整过快会震荡 |
| `StructurePriorBias` | 注入结构先验 | 图/序列/矩阵结构 | 先验错误会误导 |
| `RiskBias` | 风险暴露惩罚 | 风险敏感业务 | 风险模型需可解释 |

### 9.3 管理器与门面逐项介绍

| 组件 | 作用 | 你该怎么讲 |
| --- | --- | --- |
| `BiasModule` | Solver 侧统一入口 | 负责接入 store、缓存、聚合计算，不改主循环语义 |
| `UniversalBiasManager` | 总管理器 | 组合 algorithmic/domain 两路偏置并统一统计 |
| `AlgorithmicBiasManager` | 算法偏置管理 | 管探索-收敛类偏置，可做自适应权重 |
| `DomainBiasManager` | 领域偏置管理 | 管业务规则与约束倾向，强调稳定与可解释 |
| `BiasRegistry` | 注册发现机制 | 让 bias 可发现、可扩展、可治理（呼应 catalog） |

---

## 10. 面试追问模板（Bias）

### Q1：为什么不把 Bias 写进 Adapter？

A：因为 Bias 是横切能力，和算法策略正交。放在独立层更容易复用、切换与治理。

### Q2：Bias 会不会破坏收敛？

A：会有风险，所以它是软引导，并通过权重、缓存、监控、回放进行约束，不替代主优化逻辑。

### Q3：你怎么保证 Bias 可解释？

A：通过 context contract、trace/report 插件、以及偏置统计（usage_count/历史值）保留证据链。

---

## 11. 30 秒口述模板（Bias）

> `nsgablack` 的 Bias 是软引导层，目标是把算法偏好和领域知识解耦到独立体系。它通过 `BiasModule + UniversalBiasManager` 组合算法偏置和领域偏置，利用 context/snapshot 做可控缓存和可追溯计算，不替代硬约束 repair，也不改 solver 运行语义。这样我们能在不破坏主框架稳定性的前提下，逐步提升问题特化能力。

---

## 12. 一页速记（只背这些）

- Bias = 软引导，不是硬约束
- 入口在 `apply_bias_module(...)`
- `BiasModule` 封装，`Manager` 组合
- 算法偏置 18 项、领域偏置 8 项，面试可按“作用-场景-注意”三句法展开
- 支持 context contract 与缓存
- 风险开关要配监控与边界声明
- 目标是增强，不是替代算法主干
