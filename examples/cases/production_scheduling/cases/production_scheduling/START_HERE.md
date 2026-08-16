# START_HERE

`production_scheduling` 是一个标准 `nsgablack` Case，用于受约束生产排程。

## 快速检查

从仓库根目录执行：

```powershell
python examples\cases\production_scheduling\run_project.py --check
```

## 快速运行

```powershell
python examples\cases\production_scheduling\run_project.py
```

## Baselines

```powershell
python examples\cases\production_scheduling\solver\run_case.py --solver baseline-greedy --single-objective
python examples\cases\production_scheduling\solver\run_case.py --solver baseline-aco --single-objective --aco-ants 48
```

## 继续阅读

- `README.md`：组件边界和运行命令
- `SCENARIO_MATRIX.md`：scenario 对比协议
- `build_solver.py`：canonical assembly entry

旧 single-file wrapper 只作为 compatibility material。
