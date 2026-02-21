# Traditional GA -> Framework Mapping / 传统 GA 到框架映射

This file maps the baseline implementation (`00_baseline.py`) to the framework-native implementation (`02_framework_final.py`).
本文将传统实现（`00_baseline.py`）映射到框架实现（`02_framework_final.py`）。

## Mapping Table / 映射表

| Baseline responsibility / 传统职责 | Baseline location / 传统位置 | Framework replacement / 框架替代 | Why this helps / 价值 |
|---|---|---|---|
| Objective definition / 目标定义 | `objective()` | `ShiftedSphereProblem.evaluate()` | Keeps objective in Problem layer and reusable. / 目标函数放在 Problem 层，可复用。 |
| Bounds metadata / 边界信息 | `BaselineGAConfig` + clip in mutate | `BlackBoxProblem.bounds` + `ClipRepair` | Constraints become explicit and inspectable. / 边界和约束显式化，可审计。 |
| Initial sampling / 初始采样 | `initialize_population()` | `UniformInitializer` | Sampling policy is swappable. / 初始化策略可替换。 |
| Mutation operator / 变异算子 | `mutate()` | `GaussianMutation` | Operator becomes modular. / 算子模块化。 |
| Crossover + selection + survivor / 交叉选择生存 | baseline evolve loop | `NSGA2Adapter.propose()/update()` | Process loop is encapsulated in adapter. / 过程逻辑被封装为 adapter。 |
| Main optimization loop / 主循环 | `run_baseline()` | `ComposableSolver.run()` | Unified lifecycle and plugin/context hooks. / 统一生命周期、插件钩子、context 观测。 |
| Reproducibility seed / 随机种子 | local `rng` | `solver.set_random_seed()` | Framework-level reproducibility entry. / 框架级可复现入口。 |

## Minimal Migration Checklist / 最小迁移清单

1. Move objective/constraints into `BlackBoxProblem`. / 把目标与约束迁入 `BlackBoxProblem`。
2. Move init/mutate/repair into `RepresentationPipeline`. / 把初始化、变异、修复迁入 `RepresentationPipeline`。
3. Choose one adapter for process logic. / 选一个 adapter 负责过程逻辑。
4. Assemble with `ComposableSolver(problem, adapter, pipeline)`. / 用 `ComposableSolver` 组装。
5. Run with `solver.set_max_steps(...)` + `solver.run()`. / 用 `set_max_steps` + `run` 执行。

## Notes / 备注

- This case intentionally keeps bias/plugin empty to focus on GA migration. / 本案例先不接入 bias/plugin，聚焦 GA 迁移。
- Next step: add one bias and one plugin without changing adapter code. / 下一步可以在不改 adapter 的前提下接入 1 个 bias + 1 个 plugin。
