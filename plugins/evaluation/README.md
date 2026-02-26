# plugins/evaluation

## 目录职责 / Responsibility
- 中文：放“评估阶段”的增强能力，强调评估加速、稳健性、数值求解，不负责跨层编排。
- English: Holds evaluation-stage enhancements (acceleration, robustness, numerical solve), not cross-layer orchestration.

## 触发时机 / Trigger Timing
- 中文：通常在 `evaluate_individual`、代末统计、求解完成后触发。
- English: Usually triggered at `evaluate_individual`, end-of-generation hooks, or end-of-run hooks.

## 输入输出 / I/O Contract
- **输入 Input**
  - `problem`, `population`, `objectives`, `constraint_violations`（按插件需要）。
  - Optional model/state fields in context.
- **输出 Output**
  - 评估结果、metrics、报告字段（写入 context 或模块报告）。
  - Numerical solver plugins may short-circuit objective/violation evaluation.

## 失败策略 / Failure Policy
- 中文：增强路径失败时优先降级到基础评估路径（base evaluate）。
- English: Degrade gracefully to base evaluation when enhanced path fails.

## 主要模块 / Key Modules
- `monte_carlo_evaluation.py`
- `multi_fidelity_evaluation.py`
- `surrogate_evaluation.py`
- `newton_solver_plugin.py`
 - `gpu_evaluation_template.py`
  - `NewtonSolverPlugin`: Newton-like nonlinear root solve (`scipy.optimize.root`).
  - `BroydenSolverPlugin`: quasi-Newton style root solve (`scipy.optimize.broyden1`).
  - `NumericalSolverPlugin`: base class for implicit-equation solve in evaluation.
  - `GpuEvaluationTemplatePlugin`: minimal short-circuit template for GPU batch evaluation.

## 边界说明 / Boundary
- 中文：涉及“内外层任务编排、跨层字段桥接、预算门控”请放到 `plugins/solver_backends/`。
- English: Put nested orchestration, cross-layer bridge, and budget guard into `plugins/solver_backends/`.

