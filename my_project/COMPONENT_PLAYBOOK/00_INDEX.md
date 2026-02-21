# 组件逐行批注手册索引

这个目录是给“第一次上手框架的人”准备的：
- 每个组件一份独立文档
- 代码块每一行都带中文注释
- 先照抄跑通，再改成你的业务逻辑

## 推荐阅读顺序
1. `01_PROBLEM_逐行批注.md`
2. `02_PIPELINE_逐行批注.md`
3. `03_BIAS_逐行批注.md`
4. `04_PLUGIN_逐行批注.md`
5. `05_ADAPTER_逐行批注.md`

## 难题案例（多份）
1. `CASE_A_Production_Scheduling_LineByLine.md`
2. `CASE_B_TSP_LineByLine.md`
3. `CASE_C_Robust_Optimization_LineByLine.md`

## 难题案例（再拆分：每个案例 5 份）
- 目录：`SPLIT_CASES/`
- Case A（真实排产）
  - `CASE_A_prod_problem.md`
  - `CASE_A_prod_pipeline.md`
  - `CASE_A_prod_bias.md`
  - `CASE_A_prod_plugin.md`
  - `CASE_A_prod_adapter.md`
- Case B（TSP）
  - `CASE_B_tsp_problem.md`
  - `CASE_B_tsp_pipeline.md`
  - `CASE_B_tsp_bias.md`
  - `CASE_B_tsp_plugin.md`
  - `CASE_B_tsp_adapter.md`
- Case C（稳健优化）
  - `CASE_C_robust_problem.md`
  - `CASE_C_robust_pipeline.md`
  - `CASE_C_robust_bias.md`
  - `CASE_C_robust_plugin.md`
  - `CASE_C_robust_adapter.md`

## 真实源码整文件逐行批注（超详细）
- 目录：`REAL_CODE/`
- `working_integrated_optimizer_line_by_line.md`
- `refactor_pipeline_line_by_line.md`

## 每次开发固定流程
1. 在 `problem/pipeline/bias/plugins/adapter` 里复制对应模板
2. 跑通：`python build_solver.py`
3. 审计：`python -m nsgablack project doctor --path . --build`
4. 联动检查：`python -m nsgablack run_inspector --entry build_solver.py:build_solver`

## 硬规则
- 统一用 `context_keys.py` 常量，不手写字符串 key
- 新组件必须写 `context_requires/provides/mutates/cache/notes`
- 依赖指标时再写 `requires_metrics/metrics_fallback`
- `adapter` 负责完整算法过程，`bias` 只做偏好评分
