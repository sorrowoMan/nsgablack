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

内层求解（L2）：
- 标准嵌套：内层用完整生产调度 solver 求解（`full_nested`）
- 可选保留：`production_inner_eval` 的快速评估模式（非标准嵌套）

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

# 显式指定基线计划（不指定时自动取最新 integrated_result_production_*.xlsx，
# 会优先扫描 `../runs/production_schedule/exports/`）
python working_nested_optimizer.py `
  --baseline-plan "../runs/production_schedule/exports/integrated_result_production_20260225_022256.xlsx"

# 调低内层预算（更快）
python working_nested_optimizer.py --inner-trials 3

# 标准嵌套内层预算（inner solver）
python working_nested_optimizer.py `
  --hybrid-refine-pop-size 24 `
  --hybrid-refine-generations 3
```

## Output

运行结束会自动导出：
- `runs/supply_adjustment_nested/adjusted_supply_<run_id>.xlsx`
- `runs/supply_adjustment_nested/adjusted_supply_moves_<run_id>.csv`
