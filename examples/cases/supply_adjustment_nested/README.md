# Supply Adjustment Nested (Usable Case)

目标：直接优化 `production_scheduling/SUPPLY.xlsx` 的供应事件时序。

外层决策（L1）：
- 对每个 `day>0` 且数量>0 的供应事件，决定提前多少天

约束规则（硬规则）：
- 第0天不可调整
- 只能提前，不能延后
- 整块移动，不可拆分

目标函数：
- 生产指标更好（最大化总产出，等价最小化 `-total_output`）
- 总移动事件数最少
- 总移动天数最少

内层评估（L2）：
- 默认 `hybrid`：先残差分解筛选，再对高潜候选做精细内层复核
- `integrated`：仅残差分解评估（`P=B+A`）
- `fast`：轻量代理评估（调试用）

## Run

```powershell
cd nsgablack/examples/cases/supply_adjustment_nested
python working_nested_optimizer.py --parallel --parallel-backend thread --parallel-workers 8
```

可显式指定输入表：

```powershell
python working_nested_optimizer.py `
  --bom "../production_scheduling/machine_material_mapping.csv" `
  --supply "../production_scheduling/SUPPLY.xlsx"

# 显式指定基线计划（不指定时自动取最新 integrated_result_production_*.xlsx）
python working_nested_optimizer.py `
  --baseline-plan "../integrated_result_production_20260225_022256.xlsx"

# 调低内层预算（更快）
python working_nested_optimizer.py --inner-trials 3

# 混合评估策略参数（残差筛选 + 精细复核）
python working_nested_optimizer.py `
  --inner-eval-mode hybrid `
  --hybrid-top-quantile 0.85 `
  --hybrid-random-refine-ratio 0.10 `
  --hybrid-explore-prob 0.05 `
  --hybrid-warmup 20 `
  --hybrid-refine-pop-size 24 `
  --hybrid-refine-generations 3

说明：
- 每个候选会记录 `hybrid_residual` 或 `hybrid_refined` 决策，可在 decision trace 中审计。
```

## Output

运行结束会自动导出：
- `runs/supply_adjustment_nested/adjusted_supply_<run_id>.xlsx`
- `runs/supply_adjustment_nested/adjusted_supply_moves_<run_id>.csv`
