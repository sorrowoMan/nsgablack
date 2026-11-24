# 固定供应候选 Case

`build_solver.py` 只转发原 `supply_adjustment_nested` 的 canonical builder，并原样传递
`resource_context` 与 `component_overrides`。问题、管线、Adapter 与发布实现仍由原 Case 拥有。
本 Project 的 `probe` stage 固定 evaluation-only 零移位候选，不启动外层优化。
独立 CLI 使用 `run_solver.py`；本次诊断从 Project 入口装配，不能绕过 Project/L0 运行。
