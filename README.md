# NSGABlack
为什么复杂优化实验会“悄悄退化”，以及我如何试图让它变得可见。

这是一个 **仍在快速演化中的实验性框架**。

我分享它是为了讨论思想，而不是作为已完成的产品。

算法解构的优化生态框架：把“问题/表示/偏好/策略/工程能力”解耦，让你能更快、更稳地把新点子落地到真实问题上。

你可以把它当成一套工程化的优化搭积木：

- 新业务约束/偏好来了：加 Bias，不动算法
- 评估太慢/要并行/要统一输出口径：加 Plugin，不动算法
- 想换搜索策略/做阶段式融合：换/加 Adapter，不动问题定义
- 容易漏配的组合：用 Suite 一键装配
- 不知道有哪些组件：用 Catalog 搜索

这套解耦带来的直接收益是：扩展更“自然”。你可以把新增功能落在最合适的层级，而不是改主循环；因此组件可复用、组合代价低、回归风险可控。
解耦式优化实验框架（Problem / Pipeline / Bias / Adapter / Plugin）。

## 快速开始

```powershell
python -m pip install -U pip
python -m pip install -e .[dev]
python -m nsgablack project init my_project
cd my_project
python -m nsgablack project doctor --path . --build --strict
python build_solver.py
```

## 核心原则

- Problem：定义目标与约束。
- Pipeline：表示与硬约束修复（initializer/mutator/repair）。
- Bias：软偏好，不替代硬约束。
- Adapter：搜索流程内核（propose/update）。
- Plugin：工程能力（日志、评估短路、报告、恢复等）。
- Runtime-first：新功能优先走 Runtime/context 契约，不直接写 solver 运行态字段。

## 常用入口

- `QUICKSTART.md`：安装与最小闭环。
- `START_HERE.md`：工作流入口地图。
- `WORKFLOW_END_TO_END.md`：端到端实践流程。
- `docs/user_guide/RUN_INSPECTOR.md`：Run Inspector 用法。
- `docs/user_guide/CONTEXT_CONTRACTS.md`：context 契约说明。
- `docs/user_guide/EXAMPLE_IO_CONTRACTS.md`：权威示例输入/输出契约。

## Catalog 与搜索

```powershell
python -m nsgablack catalog search vns
python -m nsgablack catalog show suite.multi_strategy
python -m nsgablack catalog search context_requires --field context --kind plugin
```

项目级搜索：

```powershell
python -m nsgablack project catalog search context_mutates --field context --path . --global
```

## Strict 快速排障

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

启动类错误先修：

- `build-solver-import-failed`
- `build-solver-missing`
- `build-solver-instantiate-failed`

## 平台依赖

- Run Inspector 需要 Tk GUI。
- Python 3.10 自动使用 `tomli` 作为 TOML fallback。
- 可选依赖（如 numba）失败会自动降级，不应阻断导入。

## Checkpoint HMAC（安全恢复）

在装配中启用：

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

运行前设置密钥（PowerShell）：

```powershell
$env:NSGABLACK_CHECKPOINT_HMAC_KEY = "replace-with-strong-secret"
python build_solver.py
```

仅迁移历史无签名 checkpoint 时临时开启：

```python
unsafe_allow_unsigned=True
```

迁移完成后恢复为 `False`。

## 质量门禁（建议）

```powershell
python -m pytest -q tests/test_refactoring.py tests/test_tomli_fallback.py tests/test_optional_numba_probe.py
python -m nsgablack project doctor --path . --strict
python tools/catalog_integrity_checker.py --check-usage --strict-usage --check-context --context-kinds plugin --require-context-notes --strict-context --check-context-conflicts --strict-context-conflicts --context-conflicts-waiver tools/context_conflicts_waiver.txt
python tools/context_field_guard.py --strict
```
