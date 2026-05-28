# Production Scheduling（生产调度）

`production_scheduling` 验证 nsgablack 在非玩具级生产排程问题上的多目标搜索能力。

## 这个 case 验证什么

- nsgablack 搜索满足物料、机器和库存流约束的 schedule candidates（排程候选）。
- case-local adapters/plugins 提供 greedy、ACO、local/random 和 multi-agent 搜索对比。
- Export plugins 会导出选中的 Pareto schedules，并写出业务审计 sidecar。
- 当前 runtime path 不使用 mlblack；这是运筹优化（operations research）case，不是 ML 训练 case。

## 是否使用 mlblack

不使用。当前路径是纯 nsgablack + case-local scheduling logic。

## nsgablack 能力体现

- 通过 `build_solver.py` 使用标准 scaffold assembly。
- 多目标生产排程优化与 Pareto export。
- case-local strategy adapters 和 baseline solvers。
- thread/process 后端并行评估。
- progress、batch export、sanity check、audit reporting 等 plugin 能力。

## 指标和目标（Metrics / Objectives）

| 指标 | 含义 |
|---|---|
| `total_output` | 核心产量信号；single-objective baselines 直接最大化它。 |
| feasibility / stock-flow audit | 在 `*.audit.json` 中检查物料守恒、负库存和排程有效性。 |
| utilization | 机器/资源利用率信号。 |
| switching / stability | 惩罚过多产品切换导致的不稳定排程。 |
| Pareto export rank | 被选中导出的非支配排程，用于人工比较。 |

## 结构（Structure）

| 路径 | 作用 |
|---|---|
| `build_solver.py` | 标准 scaffold 入口，也是实际 assembly 边界。 |
| `solver/run_case.py` | baseline、single-solver、multi-agent 运行 CLI。 |
| `problem/` | 生产排程语义、目标和约束。 |
| `pipeline/` | schedule 初始化、变异、repair 和 smoothing。 |
| `adapter/` | greedy、ACO、local/random 等 case-local 策略。 |
| `plugins/` | progress、export、Pareto batch、audit plugin wiring。 |
| `reporting/` | 导出 schedule 的业务审计指标。 |
| `config/` | 可复现实验 preset。 |
| `SCENARIO_MATRIX.md` | baseline / multi-agent 对比协议。 |

`working_integrated_optimizer.py` 只是 legacy compatibility wrapper。

## 运行

```powershell
python -m nsgablack project doctor --path . --build
python build_solver.py
python solver/run_case.py --parallel --parallel-backend thread --parallel-workers 8
```

主实验（non-toy run）：

```powershell
python solver/run_case.py --solver multi-agent --pop-size 160 --generations 36 `
  --moead-pop-size 80 --vns-batch-size 64 `
  --parallel --parallel-backend process --parallel-workers 8 `
  --pareto-export 12 --sanity-check-export
```

## Baselines（基线）

```powershell
python solver/run_case.py --solver baseline-greedy --single-objective
python solver/run_case.py --solver baseline-aco --single-objective --aco-ants 48
```

每个被选中导出的结果会写：

- `*.summary.json`：简要排程摘要。
- `*.audit.json`：feasibility、stock-flow、utilization、switching、stability scorecard。

## 预期信号（Expected signal）

有效运行应该能导出可行的 Pareto schedules，在产量上接近或超过 single-objective baselines，同时清楚展示产量、资源利用率和切换稳定性之间的 tradeoff。
