# 案例：生产调度优化（权威可运行）

这是一份“真实约束 + 可交付输出”的案例，用来展示 NSGABlack 在工程场景下的典型组合方式：

- `Problem` 只负责稳定定义目标与约束（口径可审计）
- `RepresentationPipeline` 承担“可行性修复/平滑/初始化”等工程逻辑（把脏活从 evaluate 里拿出来）
- `BiasModule` 表达软偏好与启发式（可控、可开关、可做消融）
- `ParallelEvaluator` 支持多进程/线程/joblib/Ray（评估慢的问题用工程化解决）
- `Plugin` 输出“证据链”（benchmark + 模块报告 + profiler）

## 入口

- 案例目录：`examples/cases/production_scheduling/`
- 主脚本：`examples/cases/production_scheduling/working_integrated_optimizer.py`

推荐从仓库上一级目录运行（或先 `pip install -e .`）：

```bash
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py
```

## 输入数据（可选）

将以下文件放在 `examples/cases/production_scheduling/` 下即可自动发现：

- BOM：`BOM.xlsx` 或 `BOM.csv`
- 供应：`SUPPLY.xlsx`

没有文件也可以跑：脚本会自动生成 fallback 数据，用于演示/冒烟测试/快速验证。

## 并行与分布式

```bash
# 多进程（默认推荐）
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py --parallel --parallel-backend process --parallel-workers 12

# Ray（可选，需要安装）
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py --parallel --parallel-backend ray --parallel-workers 16
```

## 输出（证据链）

- 交付结果：默认导出最佳解与 Pareto 批量导出（Excel/CSV）
- 运行证据：默认写入 `runs/production_schedule/`：
  - `*.csv` + `*.summary.json`：BenchmarkHarness（收敛、耗时、吞吐）
  - `*.modules.json` + `*.bias.json` (+ `*.bias.md`)：ModuleReport（模块启用/参数快照/偏置配置）
  - `*.profile.json`：Profiler（每代 wall time / eval/s 分位数）

如果你只想跑通，不想导出文件（也避免依赖 `pandas`），可以加 `--no-export`。

