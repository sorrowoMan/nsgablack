# QUICKSTART（快速开始）

目标：5~10 分钟跑通一条最小闭环。  
Goal: finish one minimal end-to-end loop in 5-10 minutes.

## 0) 环境前提 / Prerequisites

- Python 3.10+（建议 3.11）
- 可选：Tk（Run Inspector 需要 GUI）
  - Windows/macOS: 通常已自带
  - Linux: 需要系统包（如 `python3-tk`）
- Python 3.10 会自动使用 `tomli` 作为 `tomllib` fallback（已在依赖里声明）

## 1) 安装 / Install

```powershell
python -m pip install -U pip
python -m pip install -e .[dev]
```

## 2) 推荐路径：先建脚手架 / Recommended: scaffold first

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

你会得到：
- 标准结构（`problem/ pipeline/ bias/ adapter/ plugins/`）
- 本地注册入口（`project_registry.py`）
- 可运行装配入口（`build_solver.py`）

## 3) Catalog 搜索 / Catalog search

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show adapter.multi_strategy
python -m nsgablack catalog search context_requires --field context --kind plugin
```

项目范围搜索（本地 + 框架）：

```powershell
python -m nsgablack project catalog search context_mutates --field context --path . --global
```

## 4) 运行前审计（Run Inspector）

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

空启动（先搜后加载）：

```powershell
python -m nsgablack run_inspector --empty --workspace .
```

## 5) 快速质量门禁 / Quick quality gates

```powershell
python -m nsgablack project doctor --path . --strict
python tools/catalog_integrity_checker.py --check-usage --strict-usage --check-context --context-kinds plugin --require-context-notes --strict-context
python tools/context_field_guard.py --strict
```

## 6) pytest 提示（含 refactoring 说明）

- 现在 `tests/test_refactoring.py` 已是标准 pytest，不需要忽略。
- 如果你本地临时加了脚本式测试（非 `test_*` 函数），请不要放进 `tests/`。

## 7) 权威示例（输入/输出契约）

- `examples/end_to_end_workflow_demo.py`
  - 输入：problem + wiring wiring + seed
  - 输出：`runs/` 下 benchmark/module report 工件
- `examples/benchmark_harness_demo.py`
  - 输入：solver + BenchmarkHarnessPlugin 配置
  - 输出：`{run_id}.csv`、`{run_id}.summary.json`
- `examples/cases/production_scheduling/working_integrated_optimizer.py`
  - 输入：排产数据与参数
  - 输出：优化结果文件 + run artifacts

## 8) 5 分钟最小可复现 / 5-minute minimal repro

直接按这份跑：`docs/evidence/MIN_REPRO_10MIN.md`  
建议在 PR 里附这份命令与结果路径。

也可以直接执行：

```powershell
python tools/min_repro_5min.py
```

## 9) Checkpoint HMAC CLI 示例（含不安全兼容）

下面是推荐的 `build_solver.py` 装配方式（签名校验默认开启）：

```python
from nsgablack.utils.wiring import attach_checkpoint_resume

attach_checkpoint_resume(
    solver,
    checkpoint_dir="runs/checkpoints",
    auto_resume=True,
    resume_from="latest",
    hmac_env_var="NSGABLACK_CHECKPOINT_HMAC_KEY",
    unsafe_allow_unsigned=False,  # 推荐：有 key 时禁止无签名 checkpoint
)
```

命令行运行（PowerShell）：

```powershell
$env:NSGABLACK_CHECKPOINT_HMAC_KEY = "replace-with-strong-secret"
python build_solver.py
```

如果你要迁移历史“无签名”checkpoint（仅过渡期）：

```python
attach_checkpoint_resume(
    solver,
    checkpoint_dir="runs/checkpoints",
    auto_resume=True,
    unsafe_allow_unsigned=True,   # 仅临时兼容旧文件
)
```

```powershell
$env:NSGABLACK_CHECKPOINT_HMAC_KEY = "replace-with-strong-secret"
python build_solver.py
```

建议：迁移完成后立刻改回 `unsafe_allow_unsigned=False`。
