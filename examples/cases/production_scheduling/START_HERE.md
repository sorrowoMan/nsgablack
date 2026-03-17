# START_HERE

本案例的标准入口已经切换到“脚手架 + 组装分层”：

1. 体检：`python -m nsgablack project doctor --path . --build`
2. 标准入口运行：`python build_solver.py`
3. 可视化：`python -m nsgablack run_inspector --entry build_solver.py:build_solver`
4. CLI 入口：`python solver/run_case.py --parallel --parallel-backend thread --parallel-workers 8`

基线对照（单目标）：
- `python solver/run_case.py --solver baseline-greedy --single-objective`
- `python solver/run_case.py --solver baseline-aco --single-objective --aco-ants 48`

结构说明：

- `build_solver.py`：项目脚手架标准入口 + 求解器装配与插件注册区
- `solver/assembly.py`：兼容模块（历史导入不破）
- `solver/run_case.py`：命令行入口
- `working_integrated_optimizer.py`：兼容转发脚本（不再承载主装配逻辑）
