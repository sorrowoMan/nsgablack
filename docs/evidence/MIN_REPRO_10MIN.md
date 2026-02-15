# 10 分钟最小可复现实验包

目标：让第一次接触项目的人，在 10 分钟内完成“创建项目 -> 体检 -> 运行 -> 可发现性检查”。

## 前置条件

- Python 3.10+（建议）
- 已在本机拿到 `nsgablack` 源码
- 在仓库根目录执行命令

## 复现步骤（按顺序）

```powershell
python -m pip install -e .
python -m nsgablack project init demo_repro_10min
cd demo_repro_10min
python -m nsgablack project doctor --path . --build
python build_solver.py
python -m nsgablack project catalog list --path .
```

可选（UI 审查）：

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

## 通过标准（验收）

- `project doctor` 输出中 `errors=0`。
- `build_solver.py` 可跑完，且输出示例指标（如 `best_objective_0=...`）。
- `project catalog list --path .` 能看到 `project.*` 条目。
- （可选）Run Inspector 的 `Catalog` 页可用 `Scope=project` 看到本地组件。

## 产物清单（最小）

- 项目骨架目录：`demo_repro_10min/`
- 体检输出：终端日志（含 doctor summary）
- 运行输出：终端日志（含示例目标值）
- Catalog 输出：本地条目列表

## 常见失败与修复

- 报 `No module named nsgablack`：回仓库根目录重新执行 `python -m pip install -e .`
- `doctor` 找不到项目：确认当前目录有 `project_registry.py`
- UI 无法显示项目组件：确认 `--entry` 指向项目内 `build_solver.py:build_solver`

