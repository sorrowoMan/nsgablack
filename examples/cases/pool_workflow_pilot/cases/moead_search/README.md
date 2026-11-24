# MOEA/D 池来源试作

标准 Solver Case。装配入口是 [build_solver.py](build_solver.py)，独立 CLI 是 [run_solver.py](run_solver.py)。

- [pipeline/main.py](pipeline/main.py) 提供随机初始候选与盒约束修复。
- [adapter/workflow.py](adapter/workflow.py) 包含两个普通辅助函数及方向 change；偶数方向先交叉后变异，奇数方向先分别变异后交叉。
- 母池先生成 8 个未评种子；PoolTaskSpec 显式取 6 个，经正常评估后建立 6 个方向。
- 保留原生权重、邻域、理想点、方向替换和 6 个带来源标记的投影视图；原始目标始终两列。
- ParetoArchivePlugin 提供正式 Pareto 输出；它不负责候选变化或方向比较。
- 默认 10 次逻辑提交，首步评估 6 个起点，后续每步 3 个新提案。

在 Project 根目录执行 `python run_project.py` 或 `python run_and_report.py`。在本 Case 内可执行 `python run_solver.py --check` 或 `python run_solver.py`。Project 统一授权资源；本 Case 不创建 L0 allocator。

完整流程与当前池对象接口缺口见 [Project 说明](../../README.md)。
