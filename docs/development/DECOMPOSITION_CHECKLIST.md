# 算法解构工程清单（必读）

这份清单用于约束“如何把一个传统算法拆成 NSGABlack 的 Bias/Representation/Adapter/Plugin/Suite”，核心目标是：

- 框架不限制你怎么拆，但**拆出来的组件必须可发现、可组合、且不会静默退化**；
- 当组合需要“成套配合”时，必须提供权威组合入口（suite）或至少给出明确伙伴提示。

---

## 0. 先做分类（避免一上来就拆错层）

拆解前先回答：算法的“特色”主要落在哪？

- **倾向/压力/软约束/接受概率**（策略思想，可注入任意底座）→ `Bias`
- **有明确循环过程/阶段/子过程**（流程算法，如 VNS/TS/SA 的完整版本）→ `Adapter` 或 `Plugin`
- **编码/变异/交叉/修复/可行性**（表示与算子）→ `RepresentationPipeline`
- **编排/记录/并行/缓存/代理/评估调度**（能力层，绝不污染底座）→ `Plugin`
- **必须成套才有意义**（否则无效或语义错误）→ `utils/suites/*`

经验法则：

- “能跨算法复用的思想”优先偏置化；
- “必须维持自身状态与循环”的算法优先适配器化；
- “融合”多数是阶段编排（Plugin/Suite），不是把所有东西揉成一个偏置。

---

## 1. 伙伴元数据（每个新组件都要写）

目的：解决可发现性问题（用户不会再“找不到 TS/忘记配 VNS 的管线算子”）。

### 1.1 Bias

- `requires_metrics: set[str]`（信号驱动必填；缺信号必须退化）
- `recommended_plugins: list[str]`（或指向 suite）

例：`RobustnessBias.requires_metrics = {"mc_std"}`

### 1.2 Plugin

- `provides_metrics: set[str]`（如果它往 `context["metrics"]` 注入信号/统计）
- `short_circuit` 事件必须在 README/docstring 写清楚（接管了哪些事件）

例：`MonteCarloEvaluationPlugin.provides_metrics = {"mc_std", ...}`

### 1.3 Adapter

- `requires_context_keys: set[str]`（它会往 context 写什么，也希望算子消费什么）
- `recommended_mutators: list[str]` / `recommended_plugins: list[str]`

例：`VNSAdapter.recommended_mutators = ["ContextGaussianMutation", "ContextSwitchMutator"]`

---

## 2. 运行期护栏（必须有，避免静默退化）

规则：

- 如果缺配套会导致“功能退化但不报错”（最危险），必须在 `setup()` 或首次运行时 **warn-once**。
- 如果缺配套会导致“语义错误/结果不可用”，提供 `strict=True` 或配置项，开启后直接抛错。

示例：

- `VNSAdapter` 在 `setup()` 检查 `representation_pipeline.mutator` 是否可能消费 context，不满足则 warning。
- 信号驱动偏置（如 robustness）缺 `mc_std` 时返回 0，并 warning 一次。

---

## 3. context 协议（跨层通信的唯一推荐方式）

你不应该让 Adapter 直接理解“排列/整数/图”的细节；应该让 Adapter 写抽象信号，让管线算子读取。

建议最小协议：

- `vns_k`: 邻域编号/尺度级别（离散表示也能用）
- `mutation_sigma`: 连续扰动的 sigma（连续表示专用）
- `metrics`: 能力层写入的统计信号（给 Bias/日志/控制策略使用）

配套算子：

- 连续：`ContextGaussianMutation(sigma_key="mutation_sigma")`
- 多邻域切换：`ContextSwitchMutator(k_key="vns_k")`

---

## 4. Suite（权威组合入口）

只有在“必须成套才有意义”时才做 suite。规则：

- suite 不引入新状态：只负责装配（挂 plugin/bias/adapter/pipeline 默认值）
- suite 提供一个最小可运行的基准组合，后续任何功能回归都应对齐它

例：

- `utils/suites/monte_carlo_robustness.py`：MC 插件提供 `mc_std`，RobustnessBias 消费它

---

## 5. 最小验证（每次拆解都要加）

- 1 个最小 demo（放 `examples/`，能直接运行）
- 1 个测试（放 `tests/`，验证关键护栏/契约）

建议测试重点：

- 缺配套时会 warning/报错（护栏有效）
- 组合后能稳定运行并产生预期行为
