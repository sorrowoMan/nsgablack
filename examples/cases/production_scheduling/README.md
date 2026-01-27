# 生产调度案例（可运行）

这是一个“真实业务味道”的权威案例，用来证明框架在复杂约束 + 管线修复 + 偏置模块 + 并行评估下依然能跑通、可复现、可审计。

## 目录结构（自包含）

- `working_integrated_optimizer.py`: 主入口（推荐直接跑这个）
- `refactor_problem.py`: Problem / objectives / constraints
- `refactor_pipeline.py`: RepresentationPipeline（初始化/变异/修复/平滑）
- `refactor_bias.py`: BiasModule（软偏好/工程启发）
- `refactor_data.py`: 数据加载（找不到 Excel 时会自动 fallback 生成数据）

## 依赖

- 基础：`numpy`
- 如果你要读取/导出 Excel：`pandas` + `openpyxl`
- 如果你要用分布式评估：`ray`（可选）

## 运行（推荐在仓库上一级目录）

```bash
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py
```

常用参数：

```bash
# 更小规模/更快验证
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py --machines 8 --materials 40 --days 10 --pop-size 60 --generations 10

# 关闭导出（不生成 Excel/CSV；也避免依赖 pandas）
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py --no-export

# 进程并行（默认）
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py --parallel --parallel-backend process --parallel-workers 12

# Ray（可选）
python nsgablack/examples/cases/production_scheduling/working_integrated_optimizer.py --parallel --parallel-backend ray --parallel-workers 16
```

## 输入数据（可选）

把文件放在本目录下即可自动发现：

- BOM：`BOM.xlsx` 或 `BOM.csv`
- 供应：`SUPPLY.xlsx`

如果不放文件，脚本会 fallback 生成一份可跑通的数据（用于 CI/冒烟测试/演示）。

## 输出与“证据链”

默认会：

- 输出 Excel：最佳两个解 + 可选 Pareto 批量导出（`--pareto-export`）
- 自动写入 `runs/production_schedule/`：
  - `*.csv` / `*.summary.json`（BenchmarkHarness：收敛曲线、用时、评估吞吐）
  - `*.modules.json` / `*.bias.json` / `*.bias.md`（ModuleReport：模块/偏置是否启用、参数快照）
  - `*.profile.json`（Profiler：每代 wall time、eval/s 分位数）

