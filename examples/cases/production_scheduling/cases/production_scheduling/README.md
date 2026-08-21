# Production Scheduling

`production_scheduling` 展示 `nsgablack` 在受约束生产排程问题上的优化搜索语义。这是运筹优化 Case，不是 ML 训练 Case。

## 这个 Case 验证什么

- 在机器、物料、库存流约束下搜索 schedule candidate
- 在 output、utilization、switching、stability 之间做多目标 tradeoff
- 使用 case-local adapters 对比 greedy、ACO、local/random、multi-agent 策略
- 使用 export / audit plugins 写出 schedule sidecar
- 通过 `build_solver.py` 走标准 scaffold assembly

## 架构边界

| 层 | 责任 |
| --- | --- |
| `problem/` | objectives、constraints、bounds、生产数据语义 |
| `pipeline/` | schedule 初始化、变异、repair、smoothing |
| `adapter/` | 搜索策略与 propose/update 行为 |
| `bias/` | 软生产偏好和先验信号 |
| `plugins/` | progress、export、Pareto batch、audit/report wiring |
| `solver/` | 薄 runner helper |
| `build_solver.py` | 标准 Case 组装入口 |
| `run_solver.py` | Case-level CLI/debug entry |

`working_integrated_optimizer.py` 是 legacy compatibility wrapper，不再作为当前 assembly 参考。

## 运行

从仓库根目录执行：

```powershell
python examples\cases\production_scheduling\run_project.py --check
python examples\cases\production_scheduling\run_project.py
```

Baseline 对比：

```powershell
python examples\cases\production_scheduling\solver\run_case.py --solver baseline-greedy --single-objective
python examples\cases\production_scheduling\solver\run_case.py --solver baseline-aco --single-objective --aco-ants 48
```

较大的 multi-agent run：

```powershell
python examples\cases\production_scheduling\solver\run_case.py --solver multi-agent --pop-size 160 --generations 36 `
  --moead-pop-size 80 --vns-batch-size 64 `
  --parallel --parallel-backend process --parallel-workers 8 `
  --pareto-export 12 --sanity-check-export
```

## 预期产物

被选中的 schedule 会写出 summary 和 audit sidecar：

- `*.summary.json`：schedule 摘要
- `*.audit.json`：feasibility、stock-flow、utilization、switching、stability 报告

具体 scenario 见 `SCENARIO_MATRIX.md`。
