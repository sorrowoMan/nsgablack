# 快速开始：clustering

1. 在 Case 目录执行装配检查：

~~~powershell
python run_solver.py --check
~~~

2. 检查 **build_solver.py** 实际装配的 Problem、Pipeline、Adapter、Plugin 与 README 声明一致。

3. 需要完整运行时，从所属 Project 启动：

~~~powershell
python examples/cases/clustering/run_project.py
~~~

这样可以获得 Project L0 发放的资源、统一运行 lineage、预算、取消和 Artifact 发布边界。
