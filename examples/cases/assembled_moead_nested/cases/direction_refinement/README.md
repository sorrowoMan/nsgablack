# direction_refinement

这是 `assembled_moead_nested` Project 内的一个标准 Solver Case。唯一装配入口是 [build_solver.py](build_solver.py)。

数学问题、三个算法实例、两层投影任务、解池交接、真实求值和全部组件源码入口，统一见 [Project 详细说明](../../README.md)。

推荐从 Project 根运行 `python run_and_report.py`，由 Project L0 授权并保存正式结果、轨迹及报告。Case 的 `run_solver.py` 保持标准独立入口；`build_trainer.py` / `run_trainer.py` 只是薄别名，本例没有训练任务。
