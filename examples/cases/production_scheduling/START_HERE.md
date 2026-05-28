# START_HERE

## 1) 这个 case 验证什么

`production_scheduling` 验证 nsgablack 在真实生产排程约束下的搜索能力。

- nsgablack 搜索 schedule candidates 和 Pareto tradeoffs。
- case-local adapters 提供 greedy、ACO、local/random 和 multi-agent 策略。
- Export plugins 会为选中 schedule 写 summary/audit sidecars。
- 当前 runtime path 不使用 mlblack。

更多指标、结构、baseline 和能力信号见 `README.md`。

## 2) 验证 assembly

```powershell
python -m nsgablack project doctor --path . --build
python build_solver.py
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

## 3) 快速运行

```powershell
python solver/run_case.py --parallel --parallel-backend thread --parallel-workers 8
```

## 4) Baseline 对比

```powershell
python solver/run_case.py --solver baseline-greedy --single-objective
python solver/run_case.py --solver baseline-aco --single-objective --aco-ants 48
```

## 5) Serious run

```powershell
python solver/run_case.py --solver multi-agent --pop-size 160 --generations 36 `
  --moead-pop-size 80 --vns-batch-size 64 `
  --parallel --parallel-backend process --parallel-workers 8 `
  --pareto-export 12 --sanity-check-export
```

## 6) 关键指标

| 指标 | 含义 |
|---|---|
| `total_output` | 主要产量信号。 |
| feasibility / stock-flow audit | 确认导出的 schedule 满足物料和库存约束。 |
| utilization | 机器/资源利用率。 |
| switching / stability | 排程平滑性和产品切换压力。 |

## 7) 预期信号

有效运行应该导出可行的 Pareto schedules，并相对 greedy/ACO baselines 展示 output-vs-stability 的权衡。
