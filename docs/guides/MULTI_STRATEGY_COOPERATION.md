# Multi-Strategy Cooperation

多策略/多 agent 协作不是新的 solver 模式，也不是 `nsgablack` 独占的顶层编排能力。

当前分层：

- 同一个 Case 内的多搜索策略：Adapter / RoleAdapter / StrategyRouterAdapter。
- 多 solver、多 trainer、多混合 case：Project / Case / L0 substrate。
- 跨 Case 资源、顺序、fanout：Project L0 与 `run_project.py`。

## Case 内协作

适合放在 Adapter 层：

- explore -> exploit -> refine 阶段策略
- 多 adapter group 候选提案
- role adapter 包装同类搜索单元
- 通过 context 轻量事实共享，如 archive、telemetry、seed

不要在 solver base 中新增特殊 multi-agent loop。

## Project 级协作

适合放在 Project 层：

- 多 solver profile 并行比较
- 多 trainer 并行训练
- solver 调 inner trainer / numeric Case
- 多 inner Case ensemble
- 跨 case 资源预算与结果汇总

## 推荐入口

- `docs/standard_scaffold_tutorial/03_orchestration_language.md`
- `docs/standard_scaffold_tutorial/07_nested_orchestration_standard.md`
- `docs/architecture/SOLVER_ORCHESTRATION.md`
