# 本项目的 Case

`hybrid_search/` 是完整的标准求解 Case，装配 NSGA-II、VNS、共享问题管线和观察组件。

在 Project 根目录执行：

```powershell
python run_project.py --check --build-check
python run_and_report.py
```

仅检查 Case 可执行 `python cases/hybrid_search/run_solver.py --check`。
Project 编排和 L0 资源授权仍由根目录的 `project_config.py` 与正式 runner 负责。
