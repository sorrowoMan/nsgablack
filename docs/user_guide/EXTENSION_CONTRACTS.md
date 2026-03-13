# 扩展点契约（可执行护栏）

框架不限制你如何拆解算法（同一算法可同时偏置化/管线化/适配器化/插件化），但为了避免“自由发挥把系统拆坏”，在关键边界提供最小的可执行契约。

## 1) Solver ↔ RepresentationPipeline（表示管线）

- `init()/mutate()/repair()` 输出必须是“候选解”（可 `np.asarray` 且非 object dtype），并且长度等于 `problem.dimension`。
- 表示可以是 float/int/permutation 等，框架不会强制转 float（避免破坏离散/排列表示）。

## 2) Solver ↔ Bias（偏置）

- `compute_bias(...)` 的输出必须是有限 `float`（非 NaN/Inf）。
- 偏置建议只影响“评分/选择压力/软约束倾向”，不要直接替代表示修复（硬约束更适合放在 repair/约束算子里）。
- 若偏置依赖外部统计信号（信号驱动偏置），必须声明 `requires_metrics` 并提供 `recommended_plugins` 或 `utils/wiring/*` 权威组合入口；缺信号时必须安全退化（返回 0.0）。

## 3) Solver ↔ Adapter（搜索策略模块）

- `AlgorithmAdapter.propose()` 返回候选解序列；每个候选解必须满足候选解契约（长度=dimension）。
- `update(...)` 只消费反馈；不要假设 `objectives/violations` 的 shape 以外的隐式约定。

## 4) Solver ↔ Plugin（胶水/观察/编排）

- 默认事件（例如 `on_generation_start` 等）返回值应为 `None`；非 `None` 会触发 `RuntimeWarning`（并被忽略）。
- 如需“短路返回”，请使用 `PluginManager(short_circuit=True, short_circuit_events=[...])` 并在对应事件中返回非 `None`。

## 5) 解构算法的工程清单（强烈建议遵守）

- 当你要把传统算法拆成 Bias/Representation/Adapter/Plugin/Wiring 时，建议按工程清单执行，避免“组件找不到 / 忘配套导致静默退化”。
- 参考：`docs/development/DECOMPOSITION_CHECKLIST.md`

## 工程实现

- 可执行校验集中在 `utils/extension_contracts.py`，并在 `core/blank_solver.py` / `core/composable_solver.py` 的关键边界处启用。
