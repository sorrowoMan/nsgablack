# 有限差分精修：沿现有 MOEA/D 方向做局部搜索

本文只做源码和语法核对，未执行算法、调用模型或取得 AI 审核结论。

## adapter.gradient_descent · 没有解析梯度时，精修已有方向候选

**什么时候用：** Problem 能计算目标、没有解析梯度，希望局部精修。本例最小化到 `(1,1)` 和 `(-1,-1)` 的两个平方距离；有限差分分别沿 MOEA/D 方向比较，原双目标含义保留，不保证精修更好。

**先准备什么：** blackbase、nsgablack、NumPy 和现有 `examples/cases/solution_pool/` Project 副本。保留运行入口、`_bootstrap.py`、Project L0 与完整 `cases/moead_refinement/`。下列路径相对此 Project，保留原实现：

- `problem/__init__.py` 的 `TwoCenters/build_problem`：二维候选，边界 `[-2,2]`，两个最小化目标。
- `pipeline/main.py` 及其包导出：`UniformInitializer(-2,2)`、`ContextGaussianMutation`、`ClipRepair(-2,2)`。
- `adapter/refinement.py` 的 `build_refinement_adapter`、`local_search` 和阶段策略。已有 `finite_difference` 分支实际构造 `GradientDescentAdapter(name=..., max_directions=2)`；原默认分支是 VNS。
- Case 包标记、`run_solver.py`、其它原组件文件。不要启用 `nested_refinement=True`：原两层工厂装配的是 VNS→VNS。

**放在哪：** 新增下面两个本地文件、追加 Plugin 导出、替换 Case 的 `build_solver.py`，在原 Project 追加组。builder 只装配，观察逻辑归 `plugins/`。

**接入步骤：**

新增完整 `cases/moead_refinement/adapter/finite_difference_config.py`：

```python
FD_OPTIONS = dict(
    directions=8, view_count=4, workers=1,
    local_steps=3, seed=37,
)
```

8 个方向中随机选 4 个，一个局部实例依次处理；`workers` 不是 CPU 线程数。`local_steps=3` 才包含起点、探针、下降提案各自送评；两步未完成下降点评估。`GradientDescentConfig` 默认 `epsilon=1e-3`、`learning_rate=.15`；探针不由 pipeline mutator 生成。

新增完整 `cases/moead_refinement/plugins/finite_difference_report.py`：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class FiniteDifferenceReport(Plugin):
    def __init__(self, path):
        super().__init__("finite_difference_report")
        self.path = Path(path)

    def on_solver_finish(self, result):
        control = self.solver
        pool = control.solution_pool
        def read(refs):
            refs = tuple(refs)
            if not refs:
                return dict(refs=[], candidates=[], raw_objectives=[], raw_violations=[])
            batch = control.read_solutions(refs)
            raw_f, raw_v = pool.read_raw_feedback(refs)
            return dict(refs=[ref.as_dict() for ref in refs],
                        candidates=batch.numeric_matrix.tolist(),
                        raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist())
        units = control.adapter.units
        moead = next(unit.adapter.inner for unit in units if unit.role == "moead")
        tasks = []
        for unit in units:
            if unit.role != "local":
                continue
            task = unit.adapter
            status = task.task_status
            selected = task.get_pool_task_results(control) if status["status"] == "done" else ()
            history_count = len(pool.subpool_refs(status["output"])) if status["output"] else 0
            tasks.append(dict(worker=unit.unit_id, algorithm=type(task.inner).__name__,
                              task=status, selected=read(selected),
                              accepted_history_count=history_count))
        self.payload = dict(run_id=control.run_session.run_id, tasks=tasks,
                            moead_members=read(moead.get_population_solution_refs(control)))

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
                             allow_nan=False, indent=2), encoding="utf-8")
```

`control` 是 Plugin 所属 Solver。`adapter.units` 是 Router 执行实例表；`unit.adapter` 为 `PoolTaskAdapter`，`inner` 是算法。结束通知读取已提交值，最终发布后只写脱离摘要，不保留活 Pool。

保留 `cases/moead_refinement/plugins/__init__.py` 原内容，末尾追加：

```python
from .finite_difference_report import FiniteDifferenceReport
```

完整替换 `cases/moead_refinement/build_solver.py`：

```python
from pathlib import Path
from nsgablack.core import PoolRetentionPolicy
from nsgablack.project.starter import build_starter_solver
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter.refinement import build_refinement_adapter
from .adapter.finite_difference_config import FD_OPTIONS
from .plugins import FiniteDifferenceReport

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if component_overrides:
        raise ValueError("this report requires the declared refinement assembly")
    options = {**FD_OPTIONS, **dict(config or {})}
    directions, workers = int(options["directions"]), int(options["workers"])
    view_count, local_steps = options["view_count"], int(options["local_steps"])
    if not 1 <= workers or local_steps < 3:
        raise ValueError("use at least one worker and three updates per direction")
    problem = build_problem()
    adapter = build_refinement_adapter(directions=directions, view_count=view_count,
        workers=workers, local_steps=local_steps, local_algorithm="finite_difference")
    selected = directions if view_count is None else int(view_count)
    return_candidates = selected * (1 + 2 * problem.dimension * (local_steps - 1))
    default_steps = ((directions + 15) // 16 + 1
        + ((selected + workers - 1) // workers) * local_steps
        + (return_candidates + 15) // 16 + 2)
    solver = build_starter_solver(problem=problem, pipeline=build_pipeline(),
        max_steps=int(options.get("max_steps", default_steps)),
        resource_context=resource_context, component_overrides={"adapter": adapter})
    solver.set_random_seed(int(options["seed"]))
    solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=2))
    solver.add_plugin(FiniteDifferenceReport(
        Path(__file__).resolve().parent / "results" / "finite_difference.json"))
    return solver
```

预算估算沿原 builder；更改批次、准入或停止条件须重核，不能当求值次数。入口显式接收 `resource_context/component_overrides`，拒绝非空覆盖以保护观察器依赖；构造检查不创建叶 Unit。

在原 `project_config.py` 的 `STAGES/GROUPS` 定义之后追加，不覆盖 L0 或原组：

```python
STAGES.append(dict(name="finite_difference_demo", cases=["moead_refinement"],
    policy="serial", resource_requests={
        "moead_refinement": dict(threads=1, gpus=0, backend="local"),
    }))
GROUPS["finite_difference"] = dict(stages=["finite_difference_demo"])
```

原工厂依次等待方向视图、初始化独立 GA、局部精修、返回竞争、继续搜索。任务冻结起点版本、方向权重和参考点，投影供局部比较、raw feedback 保留。下降点自己经过 repair/求值/接纳，不能沿用探针分数。ClipRepair 沿现有 coordinate 策略；改变其它坐标的修复会被拒绝。

**怎样判断接对：** 查看本次 `cases/moead_refinement/results/finite_difference.json`，核对新 `run_id` 和正式 Project 收据。基线正常完成且未另加停止/拒绝策略时：

- `tasks` 应有一个 worker，`algorithm` 为 `GradientDescentAdapter`，`task.status` 为 `done`、`task.count` 为 4；`selected.refs` 按任务次序给出每个方向的最终选择，可有相同候选引用。
- `selected.candidates/raw_objectives` 均为两列，按两个中心逐行重算；原问题无约束，`raw_violations` 应为零。
- `accepted_history_count` 是共享 `refined` 接纳历史；完成后的 `get_pool_task_results` 才是请求最终选择，可能是起点、探针或下降点中的最好已评估版本。
- `moead_members` 有 8 个方向槽位，允许同引用占多槽。MOEA/D 自行决定返回结果能否留在成员中；独立 GA 不在该表中。

Solver 默认运行级聚合为 sum，best 可来自其它角色，不等于方向成员或局部最终选择。本地 JSON 是观察副本，不是权威 Artifact 或成功收据。

**运行入口：** 从仓库根目录执行，使用副本时替换路径；先按上文启用有限差分，原默认是 VNS：

```powershell
python examples/cases/solution_pool/run_project.py --group finite_difference --check --build-check
python examples/cases/solution_pool/run_project.py --group finite_difference
```

第一条只构造检查；第二条由 Project L0 运行指定 Case。Case CLI 没有 `--config`，参数写入上述本地配置。

### 变体一：覆盖所有方向，检查整个方向面的局部机会

**目的：** 不再随机挑部分方向，希望逐个方向都尝试同一局部改进，便于检查哪些方向有可用下降机会。

**改在哪里：** 完整替换同一个 `adapter/finite_difference_config.py`，其它文件与入口保持上文：

```python
FD_OPTIONS = dict(
    directions=8, view_count=None, workers=1,
    local_steps=3, seed=37,
)
```

**行为变化：** 原工厂从 `subpools.random(4, moead)` 切为 `subpools.all(moead)`，覆盖该实例全部方向。builder 随之增加预算；正常完成时 `task.count/selected.refs` 数量为 8，MOEA/D 容量仍为 8。

**限制：** all 不分配并行资源或隐含等待；单实例开销增加，方向可共享候选，不能按数值去重。阶段屏障仍由原 Router 决定，返回竞争可能保留原成员。

源码依据：`examples/cases/solution_pool/cases/moead_refinement/` 的 builder、refinement 工厂、Problem/Pipeline，以及 `adapters/gradient_descent/adapter.py`、`adapters/pool_tasks.py::get_pool_task_results`。
