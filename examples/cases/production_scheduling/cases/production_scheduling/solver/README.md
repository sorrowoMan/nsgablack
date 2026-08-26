# solver

求解控制层（标准结构）：

- 使用框架标准 `ComposableSolver`，不再覆盖 `step()`。
- 物料可行性修复位于 `pipeline/`。
- 评估后的严格可行接纳由 `FeasibleEvaluationAcceptance` 通过
  `BatchDisposition` 投影给 Adapter。
- `assembly.py`
  - 兼容入口（历史导入路径）
  - 实际装配位于项目根 `build_solver.py`
- `run_case.py`
  - CLI 入口
