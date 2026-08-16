# 创建标准项目骨架（Project -> Case -> Scaffold）

这份文档只回答一件事：如何用统一 Project / Case / Scaffold / L0 substrate 快速起一个可运行项目。

## 1. 一条命令创建

```powershell
python -m nsgablack project new my_project
cd my_project
python -m nsgablack project add-case my_case --type solver
```

`--type solver` 和 `--type trainer` 生成相同目录。差异只在 catalog kind 和语义组件，不在编排资格。

## 2. 会生成什么

```text
my_project/
  project_config.py        # stages/groups/dependencies + Project L0
  run_project.py           # formal entry, grants ResourceContext
  README.md
  START_HERE.md
  cases/
    my_case/
      build_solver.py      # canonical assembly
      build_trainer.py     # alias only
      run_solver.py        # case debug CLI
      run_trainer.py       # alias only
      config.py
      problem/
      pipeline/
      adapter/
      bias/
      plugins/
      evaluation/
      runtime/             # requirement/profile/audit
      solver/
```

## 3. 第一轮检查

```powershell
python -m nsgablack project doctor --path . --build --strict
python run_project.py
```

Doctor 会检查：

- Project / Case / Scaffold 目录和关键入口是否齐全
- case `build_solver()` 是否可实例化
- 组件契约是否清晰（如 `context_requires/provides/mutates`）
- context/snapshot 大对象边界是否符合协议

## 4. Project L0 怎么写

`project_config.py` 中声明可用资源和 case requirement：

```python
L0 = {
    "namespace": "my_project",
    "offer": {"threads": 4, "gpus": 0, "backend": "local"},
    "policy": {"mode": "strict"},
    "default_request": {"threads": 1, "gpus": 0, "backend": "local"},
}

STAGES = [
    {
        "name": "main",
        "cases": ["my_case"],
        "policy": "serial",
        "resource_requests": {
            "my_case": {"threads": 1, "gpus": 0, "backend": "local"},
        },
    },
]
```

规则：case 声明需求，Project L0 发放 `ResourceContext`，组件只消费 grant。

## 5. 本地 Catalog 怎么用

```powershell
python -m nsgablack project catalog list --path .
python -m nsgablack project catalog search pipeline --path .
python -m nsgablack project catalog search vns --path . --global
```

涉及主干能力判断时使用 framework-core：

```powershell
python -m nsgablack catalog list --profile framework-core --kind adapter
```

## 6. 用 Run Inspector 看结构

```powershell
python -m nsgablack run_inspector --entry cases/my_case/build_solver.py:build_solver
```

## 7. 常见问题

- 目标目录非空时报错：换新目录，或显式 `--force` 覆盖模板文件。
- `project doctor` 不可用：先确认当前安装的是最新本地代码（建议在仓库根目录 `python -m pip install -e .`）。
- 导入失败：优先检查是否从项目根运行 `run_project.py`，或 case debug 时是否在 case 目录运行 `run_solver.py --check`。
