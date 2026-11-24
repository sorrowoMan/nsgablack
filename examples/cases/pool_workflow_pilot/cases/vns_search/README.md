# VNS 池来源试作

标准 Solver Case。装配入口是 [build_solver.py](build_solver.py)，独立 CLI 是 [run_solver.py](run_solver.py)。

- [pipeline/main.py](pipeline/main.py) 提供随机初始候选与盒约束修复。
- [adapter/workflow.py](adapter/workflow.py) 包含唯一的普通 change 函数与原生 VNS 装配。
- 母池先生成 3 个未评种子；PoolTaskSpec 显式取 1 个，先评估基准，然后开始邻域搜索。
- 默认 10 次逻辑提交、首步 1 次求值，后续每步 3 个邻域提案。
- 不要求函数继承变异基类；不在函数中申请资源、修复、评估或直接写池。
- Plugin 通过本地 [plugins/__init__.py](plugins/__init__.py) 薄导出启动源与只读观察。

在 Project 根目录执行 `python run_project.py` 或 `python run_and_report.py`。在本 Case 内可执行 `python run_solver.py --check` 或 `python run_solver.py`。Project 统一授权资源；本 Case 不创建 L0 allocator。

完整流程与当前池对象接口缺口见 [Project 说明](../../README.md)。
