# 01. 创建标准项目并跑通第一版

本章目标是把一个空目录变成可运行的 `nsgablack` 标准项目，并理解每个生成文件在系统中的位置。不要先改算法，先保证装配、检查和审计链路跑通。

## 1. 创建 scaffold

在任意工作目录执行：

```powershell
python -m nsgablack project init C:\path\to\my_nsgablack_project
cd C:\path\to\my_nsgablack_project
```

如果目标目录已有文件，需要显式允许覆盖模板文件：

```powershell
python -m nsgablack project init C:\path\to\my_nsgablack_project --force
```

生成后的关键结构：

```text
my_nsgablack_project/
  build_solver.py
  run_solver.py
  config.py
  assembly.py
  project_registry.py
  problem/
  pipeline/
  adapter/
  bias/
  plugins/
  solver/
  evaluation/
  runtime/
  catalog/
  docs/
  tests/
```

第一遍只需要记住三类文件：

| 类型 | 文件 | 作用 |
| --- | --- | --- |
| 入口 | `run_solver.py` | CLI 薄入口，解析参数后调用 `build_solver()` |
| 装配 | `build_solver.py`、`assembly.py` | 选择 problem/pipeline/adapter/plugin 并挂到 solver |
| 组件 | `problem/`、`pipeline/`、`adapter/`、`bias/`、`plugins/` | 真正的业务语义和运行能力 |

## 1.1 从空项目到正式项目的 10 步路线

第一次接入真实问题时，不要同时改所有层。推荐按下面顺序推进，每一步只改一个主职责：

| 步骤 | 改哪里 | 目的 | 通过标准 |
| --- | --- | --- | --- |
| 1 | 不改代码，只跑 `--check` | 确认 scaffold 本身可导入 | `python run_solver.py --check` 成功 |
| 2 | `problem/<name>_problem.py` | 写目标、约束、bounds | 单点 `evaluate(x)` shape 稳定 |
| 3 | `problem/config.py` | 注册 problem key | `build_solver(problem_key=...)` 可用 |
| 4 | `pipeline/<name>_pipeline.py` | 写初始化、变异、repair、decode | 输出维度和 problem 一致 |
| 5 | `pipeline/config.py` | 注册 pipeline key | `build_solver(pipeline_key=...)` 可用 |
| 6 | `adapter/config.py` | 选择搜索策略或 group | `solver.set_adapter(...)` 已挂载 |
| 7 | `bias/` | 可选，加入 domain seed 或软先验 | report 可见 bias 开关 |
| 8 | `plugins/` | 加 trace/checkpoint/report | 生命周期 hook 可见 |
| 9 | `catalog/` 或 `project_registry.py` | 让组件可发现 | `project catalog search` 能查到 |
| 10 | `docs/` / `README.md` | 写清楚问题、输入输出、运行命令 | 其他人能复现第一版 |

推荐每完成一步就跑一次：

```powershell
python run_solver.py --check
python -m nsgablack project doctor --path . --build --strict --format problem
```

不要等所有组件都改完再检查。否则出错时很难判断是 problem、pipeline、adapter 还是 plugin 的责任。

## 2. 第一次只检查装配

先不要跑优化，先确认 `build_solver()` 能被导入并构建 solver：

```powershell
python run_solver.py --check
```

再跑严格 doctor：

```powershell
python -m nsgablack project doctor --path . --build --strict --format problem
```

这一步的意义是验证“结构正确”，不是验证“优化效果好”。如果这里失败，优先修入口、registry、组件契约，不要先调算法参数。

建议把第一轮检查分成三层：

| 层级 | 命令 | 说明 |
| --- | --- | --- |
| import check | `python run_solver.py --check` | 验证入口和 `build_solver()` |
| project doctor | `python -m nsgablack project doctor --path . --build --strict --format problem` | 验证标准脚手架和契约 |
| smoke run | `python run_solver.py --max-generations 1` | 验证一代 propose/evaluate/update 能闭环 |

如果 `run_solver.py` 暂时没有 `--max-generations` 参数，也应在项目 CLI 中补一个等价的 smoke 参数。smoke run 的目标不是效果，而是快速暴露 shape、bounds、context、plugin hook 等问题。

常见错误和处理方式：

| 错误现象 | 高概率原因 | 正确处理 |
| --- | --- | --- |
| `ModuleNotFoundError` | 运行目录不对，或入口里写了相对路径假设 | 从项目根目录运行，或者只在 thin wrapper 中修 bootstrap |
| `Problem key not registered` | `ProblemSpec.key` 没注册，或 `build_solver()` 传错 key | 检查 `problem/config.py` 的 registry 和 builder |
| `Pipeline key not registered` | pipeline registry 没补新 key | 检查 `pipeline/config.py` |
| `Unknown adapter key` | adapter 没注册 builder | 检查 `adapter/config.py::_register_builtin_adapters()` |
| doctor 报 context key | 插件写了未注册或不稳定 key | 使用 `core/state/context_keys.py` 的 canonical key |
| doctor 报大对象 context | population/history/trace 直接塞 context | 改成 snapshot + `*_ref` |

## 3. 理解 `build_solver.py` 的标准形态

标准 `build_solver()` 应该只做装配，不做重计算：

```python
def build_solver(
    run_id: str | None = None,
    *,
    problem_key: str = "example",
    pipeline_key: str = "default",
    bias_key: str = "none",
    flow_plugin_keys: tuple[str, ...] = (),
    ops_plugin_keys: tuple[str, ...] = (),
    component_overrides: dict[str, dict[str, object]] | None = None,
):
    cfg = get_project_config()

    problem = build_problem(cfg.problems, problem_key)
    bias = build_bias(cfg.biases, bias_key, component_overrides=component_overrides)
    solver = create_evolution_solver(problem, bias_module=bias, store_registry=cfg.store_profiles)

    pipeline = build_pipeline(cfg.pipelines, pipeline_key)
    solver.set_representation_pipeline(pipeline)

    register_evaluation_runtime(solver, cfg.evaluation, ())
    apply_runtime_profile(solver, cfg.runtime, "local_cpu")

    search_adapter = compose_search(cfg.adapters, primary_key="vns", mode="single")
    if search_adapter is not None:
        solver.set_adapter(search_adapter)

    for plugin in build_flow_plugins(cfg.flow_plugins, flow_plugin_keys, component_overrides=component_overrides):
        solver.add_plugin(plugin)
    for plugin in build_ops_plugins(cfg.ops_plugins, ops_plugin_keys, component_overrides=component_overrides):
        solver.add_plugin(plugin)

    return solver
```

逐行语义：

| 代码 | 含义 |
| --- | --- |
| `get_project_config()` | 读取项目所有 registry，不直接创建重对象 |
| `build_problem(...)` | 建立目标、约束、bounds 和评估语义 |
| `build_bias(...)` | 建立软引导模块，可为空 |
| `create_evolution_solver(...)` | 创建控制平面 |
| `solver.set_representation_pipeline(...)` | 挂候选表示流转管线 |
| `register_evaluation_runtime(...)` | 挂评估 provider 或短路评估能力 |
| `apply_runtime_profile(...)` | 挂 L0 runtime profile、资源需求、worker/backend/store/transport 配置 |
| `compose_search(...)` | 组装 adapter 或多策略编排 |
| `solver.set_adapter(...)` | 把搜索策略交给 solver 控制平面 |
| `solver.add_plugin(...)` | 挂 trace/checkpoint/report/backend 等运行能力 |

不要在 `build_solver()` 中做这些事情：

```python
# 错误：build 阶段读大数据、跑训练、跑优化
large_dataset = load_big_file()
result = inner_training_loop(large_dataset)
solver.run()
```

正确做法是：

```python
# 正确：build 阶段只声明和挂载，重计算留到 run/evaluate 阶段
problem = build_problem(cfg.problems, problem_key)
solver = create_evolution_solver(problem)
return solver
```

## 4. 第一次跑优化

```powershell
python run_solver.py
```

`run_solver.py` 应保持薄入口：

```python
from build_solver import build_solver

solver = build_solver(run_id=args.run_id)
result = solver.run(return_dict=True)
print(result)
```

运行入口只处理 CLI、run id、输出路径和展示，不应该写 problem 目标、adapter 参数或 plugin 内部逻辑。

建议 `run_solver.py` 至少暴露这些薄参数：

| 参数 | 传给哪里 | 用途 |
| --- | --- | --- |
| `--problem-key` | `build_solver(problem_key=...)` | 切换问题 |
| `--pipeline-key` | `build_solver(pipeline_key=...)` | 切换表示 |
| `--adapter-profile` | `compose_search(...)` | 切换搜索策略 |
| `--run-id` | solver/report/plugin | 标识本次运行 |
| `--output-dir` | report/checkpoint plugin | 输出位置 |
| `--check` | 只 build 不 run | 快速检查 |
| `--max-generations` | solver/controller | smoke 或预算控制 |

入口参数只负责选择，不负责创建业务对象。业务对象仍然应由 config/spec/builder 创建。

## 5. 修改第一个真实问题

假设你要做一个二维多目标问题：

```text
x = [allocation_ratio, safety_level]
f1 = latency proxy, 越小越好
f2 = energy proxy, 越小越好
constraint = safety_level 必须覆盖 risk
```

落点建议：

```text
problem/offloading_problem.py
problem/config.py
pipeline/offloading_pipeline.py
pipeline/config.py
```

`problem/offloading_problem.py` 示例：

```python
from __future__ import annotations

import numpy as np


class OffloadingProblem:
    name = "offloading"
    dimension = 2
    objectives = ("latency", "energy")

    def __init__(self, risk_level: float = 0.6) -> None:
        self.risk_level = float(risk_level)
        self.bounds = {"allocation_ratio": [0.0, 1.0], "safety_level": [0.0, 1.0]}

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        allocation, safety = np.asarray(x, dtype=float)
        latency = 1.2 - 0.7 * allocation + 0.2 * safety
        energy = 0.5 + 0.3 * allocation + 0.4 * safety
        return np.asarray([latency, energy], dtype=float)

    def evaluate_constraints(self, x: np.ndarray) -> np.ndarray:
        _allocation, safety = np.asarray(x, dtype=float)
        violation = max(0.0, self.risk_level - safety)
        return np.asarray([violation], dtype=float)
```

在 `problem/config.py` 中注册：

```python
@dataclass(frozen=True)
class OffloadingProblemConfig:
    risk_level: float = 0.6


def _build_offloading_problem(params: dict[str, object]) -> OffloadingProblem:
    return OffloadingProblem(risk_level=float(params.get("risk_level", 0.6)))


def get_problem_registry() -> ProblemRegistry:
    return ProblemRegistry(
        registry=(
            ProblemSpec(key="example", params={"dimension": 8}),
            ProblemSpec(key="offloading", params={"risk_level": 0.6}),
        )
    )


def _register_builtin_problems() -> None:
    register_problem_builder("example", _example_builder)
    register_problem_builder("offloading", _build_offloading_problem)
```

然后检查：

```powershell
python -m nsgablack project doctor --path . --build --strict --format problem
python run_solver.py --check
```

## 6. 修改第一个候选表示管线

如果问题维度从 8 改成 2，pipeline 的 bounds 也要一致。最小可用管线：

```python
from nsgablack.representation import ClipRepair, GaussianMutation, RepresentationPipeline, UniformInitializer


def build_offloading_pipeline() -> RepresentationPipeline:
    return RepresentationPipeline(
        initializer=UniformInitializer(low=0.0, high=1.0),
        mutator=GaussianMutation(sigma=0.08, low=0.0, high=1.0),
        repair=ClipRepair(low=0.0, high=1.0),
        encoder=None,
    )
```

注册到 `pipeline/config.py`：

```python
PipelineSpec(key="offloading", params={"low": 0.0, "high": 1.0, "mutation_sigma": 0.08})
register_pipeline_builder("offloading", lambda p: build_offloading_pipeline())
```

运行时使用：

```python
solver = build_solver(problem_key="offloading", pipeline_key="offloading")
```

## 7. 用 Run Inspector 看结构

```powershell
python -m nsgablack run_inspector --entry build_solver.py:build_solver
```

Run Inspector 看的是 wiring，不是最终优化效果。重点检查：

| 检查项 | 应看到什么 |
| --- | --- |
| problem | 当前 problem key 对应的对象已经挂载 |
| representation | pipeline 不为空，且 context contract 清晰 |
| adapter | 当前 search adapter 已挂载 |
| plugins | flow/ops/checkpoint 插件按预期启用 |
| context/snapshot | 大对象不直接进入 context |

如果 UI load 阶段很慢，通常说明 `build_solver()` 里混入了重计算，需要拆回 `solver.run()` 或 `evaluate_*`。

Run Inspector 的最小解读顺序：

1. 先看 solver 类型是否符合预期，例如 `EvolutionSolver` 或 `ComposableSolver`。
2. 再看 problem 名称、dimension、objectives、constraints。
3. 再看 representation pipeline 是否挂上，bounds/repair 是否和 problem 对齐。
4. 再看 adapter 名称，如果是 group/serial/event，应能看到 controller 名称。
5. 最后看 plugins、context store、snapshot store。

如果 problem/pipeline/adapter 显示为空，优先检查 `build_solver.py` 是否真的调用了：

```python
solver.set_representation_pipeline(pipeline)
solver.set_adapter(adapter)
solver.add_plugin(plugin)
```

## 8. 第一版完成标准

第一版不是追求效果，而是完成下面 5 条：

- `python run_solver.py --check` 成功。
- `python -m nsgablack project doctor --path . --build --strict --format problem` 没有新增 error。
- `python run_solver.py` 能产生结果。
- `run_inspector` 能看到 problem、pipeline、adapter 和 plugin。
- 所有新组件都能在 project catalog 或 registry 中解释来源。
