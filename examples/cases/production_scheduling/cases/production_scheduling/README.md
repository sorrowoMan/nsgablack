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

默认 Project 运行的是 4 机种、10 物料槽位、1 代的接线检查，不是完整数据求解。
完整数据有 156 个物料 ID，最大 ID 为 157，必须保留 157 个槽位；生产候选为 22×31。
正式 builder 遇到数据缺失或解析失败会报错，不会改用随机数据。

完整原数据的先导与 Greedy 对照（保存正式 Project 收据、CSV 与复核报告）：

```powershell
python examples/cases/production_scheduling/run_quality_benchmark.py --groups pilot greedy --seeds 42 --run-id my_acceptance
```

先查看更大的配置，确认预算后再去掉 `--plan` 执行：

```powershell
python examples/cases/production_scheduling/run_quality_benchmark.py --groups directional --seeds 42 --run-id my_directional --plan
```

## 预期产物

被选中的 schedule 会写出 summary 和 audit sidecar：

- `*.summary.json`：schedule 摘要
- `*.audit.json`：feasibility、stock-flow、utilization、switching、stability 报告

具体 scenario 见 `SCENARIO_MATRIX.md`。

`results/quality/<run-id>/comparison.csv` 比较各组的原始四目标；`recommendations/`
分别给产量、稳定和折中方案。Greedy 自身搜索单目标，报告在同一四目标 Problem 下重评，
不是等预算的算法优劣证明。`*.audit.json` 审计实际交付的整数 CSV。

需要单独调试 Case 时使用本目录的 `run_solver.py --check`。正式并行评估目前使用
`--parallel-backend thread`；旧 process 示例不代表该评估链受支持。
更改问题看 `problem/`，更改领域变化看 `pipeline/neighborhood_search.py`，
更改探索/精修/返回顺序看 `adapter/directional.py`，更改资源与运行组看 Project 的 `project_config.py`。

保存检查点可在原命令追加 `--checkpoint-dir DIR --checkpoint-every 10`；
沿用同一配置并追加 `--checkpoint-dir DIR --resume` 可恢复最新文件，或以 `--resume PATH` 指定。
签名密钥由首次运行在目录内创建，恢复时必须保留，检查模式不创建文件。
更简单的完整 Project 续算与预算原因说明见
[checkpoint 用法](../../../../../docs/user_guide/PRODUCTION_CHECKPOINT_AND_LARGE_RUN_CN.md)。
