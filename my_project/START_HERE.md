# START_HERE

新项目 6 步上手（中文 + English）。

## Step 1 - 先做体检 / Health check first
```powershell
python -m nsgablack project doctor --path . --build
```
- 若要新增可复用组件，先读 `COMPONENT_REGISTRATION.md`。
- If you will add reusable components, read `COMPONENT_REGISTRATION.md` first.

## Step 2 - 实现问题层 / Implement problem
- File: `problem/example_problem.py`
- 必需 / Required:
  - `evaluate(x)` returns objective vector (`numpy.ndarray`)
  - `evaluate_constraints(x)` returns violation vector (empty if no constraints)

## Step 3 - 实现管线层 / Implement pipeline
- File: `pipeline/example_pipeline.py`
- 硬可行性优先放在此层 / Keep hard feasibility in this layer.

## Step 4 - 按需加偏置 / Add bias if needed
- File: `bias/example_bias.py`
- 偏置表达偏好，不替代硬约束 / Bias encodes preference, not hard constraints.

## Step 5 - 只做装配 / Assemble only
- File: `build_solver.py`
- 保持 wiring，不重写框架内核 / Keep it as wiring; avoid re-implementing internals.

## Step 6 - 运行与检查 / Run and inspect
```powershell
python build_solver.py
python -m nsgablack project catalog list --path .
```

## 可选 / Optional
- Run Inspector: `python -m nsgablack run_inspector --entry build_solver.py:build_solver`
- 搜索时合并全局目录 / Include global catalog in search:
  `python -m nsgablack project catalog search vns --path . --global`

## Catalog registration priority / 注册路径优先级
- Preferred: `catalog/entries.toml`
- Optional fallback: `project_registry.py`

Rule:
- Static searchable metadata -> `entries.toml`
- Dynamic registration code -> `project_registry.py`
