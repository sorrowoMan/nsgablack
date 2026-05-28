# mlblack_symbolic_consensus_scaffold（符号共识嵌套 scaffold）

`mlblack_symbolic_consensus_scaffold` 验证 nsgablack 对多次 mlblack symbolic-learning runs 的外层编排能力。

这是正式的跨框架 scaffold：nsgablack 负责 outer search 和 resource budget；mlblack 负责 inner symbolic orthogonal-basis training 与 consensus workflow。

## 这个 case 验证什么

- nsgablack 搜索 symbolic consensus 和 budget knobs，作为 outer decision vector。
- nsgablack 负责 multi-strategy search、timeout control、bias 和 bridge-back metrics。
- mlblack 执行多次 symbolic orthogonal-basis training，然后做 consensus 与 locked-core refinement。
- inner truth-recovery、RMSE 和 core-basis summaries 会投影回 outer run。

## 是否使用 mlblack

使用。inner runtime 通过 `mlblack.workflow.run_semantic_train_flow(...)` 执行 mlblack symbolic training。

## nsgablack 侧能力

- Outer solver 和 multi-strategy candidate search。
- 围绕 inner runs 的 timeout / budget control。
- symbolic structure choices 的 bias/constraint surfaces。
- 通过 `TaskInnerRuntimeEvaluator` 和 `EvaluationModelProviderPlugin(scope="inner")` 做 runtime bridge。

## mlblack 侧能力

- Symbolic orthogonal-basis train flows。
- Multi-run consensus。
- Locked-core refinement。
- Experiment summaries 和 tracker artifacts。

## Contract path

1. `TaskInnerRuntimeEvaluator`
2. `EvaluationModelProviderPlugin(scope="inner")`
3. `MlblackSymbolicConsensusBackend.solve(request)`
4. `mlblack.workflow.run_semantic_train_flow(...)`

## 指标和目标（Metrics / Objectives）

| 指标 | 含义 |
|---|---|
| truth-recovery summary | symbolic basis 是否恢复预期结构。 |
| RMSE summary | 内层 mlblack 的预测/回归误差信号。 |
| core-basis summary | 多次运行中选中 symbolic basis terms 的稳定性。 |
| outer timeout/budget metrics | 选中 consensus recipe 的成本和可靠性。 |
| bridge-back metrics | mlblack inner results 投影到 nsgablack candidate scores 的信号。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `case_scaffold/problem/` | Outer decision-vector decoding、objectives、constraints 和 inner-task contract。 |
| `case_scaffold/pipeline/` | Outer genome 的 representation pipeline。 |
| `case_scaffold/config/` | CLI/config surface。 |
| `case_scaffold/orchestration/` | Solver assembly 和 adapter strategy selection。 |
| `case_scaffold/bias/` | Symbolic structure/domain bias assembly。 |
| `case_scaffold/plugins/` | Runtime provider、bridge、timeout、tracking、observability wiring。 |
| `case_scaffold/reporting/` | Inner mlblack runs 到 outer result 的投影。 |
| `build_solver.py` | Thin compatibility/entry wrapper。 |
| `run_benchmark_suite.py` | Formal scaffold entrypoint 的 suite runner。 |

`case_scaffold/` 是有意设置的 namespace boundary，避免 `config`、`plugins`、`pipeline` 等通用名字遮蔽 mlblack 使用的 top-level imports。

## 运行

```powershell
python examples\cases\mlblack_symbolic_consensus_scaffold\build_solver.py `
  --benchmark-key ohm_like `
  --outer-adapter complex `
  --generations 3 `
  --pop-size 6 `
  --vanilla-runs 3 `
  --locked-runs 2
```

`--outer-adapter complex` 是默认值，使用包含 NSGA-II、SPEA2、differential evolution、VNS、non-smooth trust region、pattern search roles 的 `StrategyRouterAdapter`。`--outer-adapter vns` 仅用于 legacy single-adapter comparison。

## 输出（Output）

- Outer run logs：`examples/cases/mlblack_symbolic_consensus_scaffold/runs/...`
- Inner mlblack summaries：`inner_mlblack/<benchmark>/<signature>/summary.json`
- mlblack experiment tracker DB：`mlblack_experiment_tracker.sqlite3`

## 预期信号（Expected signal）

有效运行应该说明 outer search 能选择更好的 consensus/refinement settings，在预算内提升 symbolic recovery stability 或降低 RMSE。
