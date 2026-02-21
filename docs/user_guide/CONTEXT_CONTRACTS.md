# Context 契约说明（统一语义 + 可审计）

本文档说明 NSGABlack 的 context 契约机制：组件声明自己需要什么、写入什么，并由工具链做一致性检查。

---

## 1) 为什么要有 Context 契约

目标不是“限制算法”，而是保证三件事：

- 组件之间字段可对齐（不靠猜）
- 运行前可审计（Doctor / Inspector 能发现缺口）
- 结果可解释（知道字段由谁提供、谁消费）

---

## 2) 组件声明字段（统一接口）

所有组件都使用同一组契约字段：

- `context_requires`: 读取依赖
- `context_provides`: 新增输出
- `context_mutates`: 原地修改
- `context_cache`: 仅缓存字段
- `context_notes`: 语义说明
- `requires_metrics`: 当组件依赖 `context.metrics` 时，声明具体指标键（字段级）

说明：

- `provides` 表示“创建/首次提供”
- `mutates` 表示“更新已有字段”
- Inspector 的 Providers 视图 = `provides + mutates`
- `requires_metrics` 会被归一为 `metrics.<key>` 参与契约对齐与搜索

---

## 3) Canonical Key 规则（强制）

必须使用 `nsgablack.utils.context.context_keys` 中的标准 key，禁止随意新造同义字段名。

常见标准 key（本轮已统一）：

- 协同调度：`candidate_roles`、`candidate_units`、`unit_tasks`
- 运行状态：`running`、`evaluation_count`
- 参数自适应：`mutation_rate`、`crossover_rate`
- 快照字段：`individual`、`metadata`、`pareto_solutions`、`pareto_objectives`

治理规则：

- 新字段先加到 `context_keys.py`（常量 + `CANONICAL_CONTEXT_KEYS`）
- 同步到 `context_schema.py`（生命周期分类）
- 再在组件契约里引用常量，不写裸字符串

---

## 4) 读写行为与声明关系

声明是“语义契约”，真正写入发生在运行阶段：

- Adapter：通常通过 `get_runtime_context_projection()` 投影运行字段
- Plugin：推荐在 `on_context_build()` 写入可观察字段
- Solver：提供核心基础字段（如 `population/objectives/constraint_violations`）

因此：

- 仅声明不等于自动写值
- 声明 + 运行写入共同构成“可审计证据”

---

## 5) 工具链校验（你会看到什么）

- `project doctor --strict`
  - 检查结构、注册、契约完整性
  - 检查 context 相关守卫（含镜像依赖等）
- `tools/context_field_guard.py`
  - 检查 catalog/契约中的非 canonical key
- Run Inspector / Context 页
  - 显示字段生命周期、声明来源、最后写入者
  - 可按字段联动查看 Providers/Consumers

---

## 6) 新增字段的最小流程

1. 在 `utils/context/context_keys.py` 增加常量并加入 canonical 集合  
2. 在 `utils/context/context_schema.py` 增加字段定义（category/replayable）  
3. 在组件内使用常量更新 `context_requires/provides/mutates/cache`  
4. 运行：
   - `python -m tools.context_field_guard`
   - `python -m nsgablack project doctor --path <project> --strict`

---

## 7) 示例

```python
from nsgablack.plugins.base import Plugin
from nsgablack.utils.context.context_keys import KEY_MUTATION_RATE, KEY_CROSSOVER_RATE


class MyAdaptivePlugin(Plugin):
    context_requires = ()
    context_provides = ()
    context_mutates = (KEY_MUTATION_RATE, KEY_CROSSOVER_RATE)
    context_cache = ()
    context_notes = "Writes adaptive runtime rates for audit."
```

---

## 8) State Governance（状态治理）

Context 契约之上，还有一层更底层的状态治理规则——它约束的是 **population / objectives / constraint_violations 的读写路径**：

- **读取**：统一使用 `resolve_population_snapshot(solver, context)`（3 级 fallback：context → solver → 空）
- **写入**：统一使用 `commit_population_snapshot(solver, context, ...)`（adapter-first：有 adapter 时只写 context，无 adapter 时同步写 solver）
- **禁止**：Plugin / Adapter 不得直接写 `solver.population = ...` 等镜像字段（Doctor `--strict` 会检查 `solver-mirror-write` 和 `plugin-direct-solver-state-access`）

> 参考：`docs/development/DEVELOPER_CONVENTIONS.md` 第 1 节「State Governance」

---

## 9) 一句话原则

先定义语义，再实现逻辑；字段必须可对齐、可追踪、可审计。
