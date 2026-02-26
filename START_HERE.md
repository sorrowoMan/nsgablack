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
    trust_checkpoint=False,
)
```

```powershell
$env:NSGABLACK_CHECKPOINT_HMAC_KEY = "replace-with-strong-secret"
python build_solver.py --enable-checkpoint --checkpoint-dir runs/checkpoints
```

只在迁移历史无签名 checkpoint 时临时加：

```powershell
python build_solver.py --enable-checkpoint --trust-checkpoint
```

## 7) Plugin Strict 何时开/关

- 开（审计/复现/CI）：`python build_solver.py --plugin-strict`
  - 插件报错即停止，避免静默退化。
- 关（探索调参）：默认关闭
  - 插件异常仅告警并继续，迭代更快。

## 8) Thread 并发隔离（Bias）

- 使用 `--thread-bias-isolation deepcopy`（推荐默认）可避免线程共享状态污染。
- 可选 `disable_cache`（性能优先）或 `off`（完全关闭隔离，不推荐）。

## 9) 平台依赖与回归建议

- Run Inspector 需要 Tk。
- Python 3.10 自动使用 `tomli` fallback。
- 建议回归命令：

```powershell
python -m pytest -q tests/test_refactoring.py tests/test_tomli_fallback.py tests/test_optional_numba_probe.py
python -m nsgablack project doctor --path . --strict
```

## 10) Directory Responsibility (evaluation vs solver_backends)
- `plugins/evaluation/`: evaluation-time accelerators and numerical tools (MC/surrogate/multi-fidelity/newton solver).
- `plugins/solver_backends/`: nested orchestration helpers (inner solver runner, contract bridge, timeout budget).
- Rule: put reusable evaluation operators in `evaluation`; put cross-layer orchestration in `solver_backends`.

## 11) 深度 × 广度打通入口（推荐）
- 深度（嵌套）：`docs/user_guide/INNER_SOLVER_BACKENDS.md`
- 数值求解：`docs/user_guide/NUMERICAL_SOLVER_PLUGINS.md`
- Redis 后端：`docs/user_guide/REDIS_CONTEXT_BACKEND.md`
- 总览：`docs/user_guide/DEPTH_BREADTH_WORKFLOW.md`
- 三层示例：`examples/nested_three_layer_demo.py`


## Redis Context Backend (optional)

Enable Redis as context backend (context contract/API stays the same):

```python
solver = BlackBoxSolverNSGAII(
    problem,
    context_store_backend="redis",
    context_store_redis_url="redis://127.0.0.1:6379/0",
    context_store_key_prefix="nsgablack:ctx",
)
```

Quick verify:

```powershell
python -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379, db=0); print('ping=', r.ping())"
```

Docker lifecycle (recommended):

```powershell
docker run --name nsgablack-redis -p 6379:6379 -d --restart unless-stopped redis:7
(这是“通用稳妥默认”，你可以按场景改：

最小临时跑（不保活）
docker run --name nsgablack-redis -p 6379:6379 -d redis (line 7)

需要重启后自动拉起（推荐长期开发机）
--restart unless-stopped

想本机隔离多个项目
改端口，例如 -p 6381 (line 6379)

不想占用公网监听（更安全）
-p 127.0.0.1 (line 6379, column 6379)

需要持久化（容器删了数据还在）
加卷：-v redis-data:/data)

# next time after reboot:
docker start nsgablack-redis
# stop when not needed:
docker stop nsgablack-redis
```


常见问题：
- 第一次使用要不要执行 `docker run`？
  - 要。首次需要创建容器；之后通常只需 `docker start/stop`。
- 每次都要重新创建容器吗？
  - 不需要。`docker start/stop` 只控制启停，不会删除容器。
- 不启用 Redis 可以吗？
  - 可以。将 `context_store_backend="memory"` 即可回到内存后端。

## Catalog 注册边界（强规则）

- 框架级组件（`nsgablack.*`）必须注册到全局 Catalog。
  原因：框架组件是团队共享资产，必须可搜索、可审计、可复用；否则会出现“能跑但查不到”的治理断层。
- 项目级组件（非 `nsgablack.*`）允许不注册。
  原因：项目迭代阶段可能快速试验，强制注册会增加摩擦，不利于探索。

在 `project doctor --build --strict` 下：

- 框架级未注册：报错（阻断）。
- 项目级未注册：输出信息项 `project-component-unregistered`，列出具体组件，不给建议文案。
