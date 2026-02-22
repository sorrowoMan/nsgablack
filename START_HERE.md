# START_HERE

NSGABlack 的推荐入口：先脚手架，再组件化装配，再严格审计。

## 1) 先创建标准项目结构

```powershell
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

## 2) 最小工作流

1. `problem/`：实现问题定义（`evaluate` / `evaluate_constraints`）。
2. `pipeline/`：实现 initializer/mutator/repair（硬约束优先放这里）。
3. `bias/`：表达软偏好（非硬约束）。
4. `adapter/`：实现 propose/update 流程。
5. `plugins/`：添加工程能力（日志、缓存、恢复、报告）。
6. `build_solver.py`：只做装配，不重复实现框架内核。

## 3) Catalog 使用

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show suite.multi_strategy
python -m nsgablack project catalog search context_requires --field context --path . --global
```

注册路径优先级：

- 优先：`catalog/entries.toml`
- 备选：`project_registry.py`

## 4) Run Inspector

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

空启动：

```powershell
python -m nsgablack run_inspector --empty --workspace .
```

## 5) Strict 快速排障

```powershell
python -m nsgablack project doctor --path . --strict
```

高频错误码：

- `runtime-bypass-write`
- `class-contract-missing`
- `contracts-not-explicit`
- `template-not-implemented`
- `plugin-direct-solver-state-access`
- `solver-mirror-write`
- `metrics-provider-missing`
- `metrics-fallback-invalid`
- `metrics-fallback-nonliteral`
- `algorithm-as-bias`

启动错误优先修：

- `build-solver-import-failed`
- `build-solver-missing`
- `build-solver-instantiate-failed`

## 6) Checkpoint HMAC（CLI）

```python
from nsgablack.utils.suites import attach_checkpoint_resume

attach_checkpoint_resume(
    solver,
    checkpoint_dir="runs/checkpoints",
    auto_resume=True,
    hmac_env_var="NSGABLACK_CHECKPOINT_HMAC_KEY",
    unsafe_allow_unsigned=False,
)
```

```powershell
$env:NSGABLACK_CHECKPOINT_HMAC_KEY = "replace-with-strong-secret"
python build_solver.py
```

只在迁移历史无签名 checkpoint 时临时设 `unsafe_allow_unsigned=True`。

## 7) 平台依赖与回归建议

- Run Inspector 需要 Tk。
- Python 3.10 自动使用 `tomli` fallback。
- 建议回归命令：

```powershell
python -m pytest -q tests/test_refactoring.py tests/test_tomli_fallback.py tests/test_optional_numba_probe.py
python -m nsgablack project doctor --path . --strict
```
