# 单轨迹自适应：让步长真正进入变异算子

本例使用现有 `examples/cases/catalog_recipes/cases/composite` 标准 Case 的副本，改成一个单轨迹搜索。保留原 Project、Problem、Case 包和 CLI；以下目录相对这个 Case。只核对当前源码与接线，未执行本例算法或新增运行收据。

## adapter.single_trajectory_adaptive · 一个当前点，多次邻域试探

**什么时候用：** 每轮只维护一个当前点，希望按近期成功率调整邻域尺度，而不是保留整个种群。每次可以提出多个邻居；batch_size 是试探上限，不是种群容量。

**先准备什么：** 安装当前 nsgablack、blackbase、NumPy，复制整个 catalog_recipes Project。原 QuadraticProblem 是二维平方和，候选 shape `(2,)`、单目标反馈 `(n,1)`；初始化与问题修复范围为 `[-2,2]`。原 composite 的 wide/narrow 不再装配。所有随机性通过 Solver 和正式算子的种子接口控制，不使用模块级 `np.random`。

**放在哪：** 新建 `adapter/adaptive_search.py`、`plugins/trajectory_report.py`；替换 `pipeline/main.py` 中的 build_pipeline 函数，并补其 imports，保留该文件的 build_unit_binding/run_pipeline_slot 两个原有 helper；最后完整替换 build_solver.py。无需改原 Project default 组，它已经运行这个 Case。

**接入步骤：**

`adapter/adaptive_search.py` 完整内容：

```python
from nsgablack.adapters import (
    SingleTrajectoryAdaptiveAdapter, SingleTrajectoryAdaptiveConfig,
)

def build_adapter():
    return SingleTrajectoryAdaptiveAdapter(
        config=SingleTrajectoryAdaptiveConfig(
            batch_size=4, initial_sigma=.2, min_sigma=.02, max_sigma=.8,
            target_success_rate=.25, adapt_gain=1.2,
            success_window=8, restart_patience=6, accept_worse_prob=.05,
            objective_aggregation="sum", violation_penalty=1e6,
        ), name="trajectory",
    )
```

在原 `pipeline/main.py` 补以下 imports，并用完整函数替换同名函数，其余 helper 保留：

```python
from nsgablack.representation import (
    PipelineSpec, build_pipeline_kernel, UniformInitializer,
    ContextGaussianMutation, ClipRepair,
)

def build_pipeline(*, resource_context=None, component_overrides=None):
    del resource_context
    overrides = dict(component_overrides or {})
    registry = {
        "initialize": UniformInitializer(low=-2., high=2.),
        "mutate": ContextGaussianMutation(base_sigma=.2),
        "repair": ClipRepair(low=-2., high=2.),
    }
    registry.update(dict(overrides.get("pipeline_operators", {}) or {}))
    spec = PipelineSpec.from_value(overrides.get("pipeline_spec", {
        "key": "default", "slots": (
            {"slot": "init", "operators": ("initialize",)},
            {"slot": "mutate", "operators": ("mutate",)},
            {"slot": "repair", "operators": ("repair",)},
        ),
    }))
    return build_pipeline_kernel(spec, operator_registry=registry).representation_pipeline
```

Adapter 将自己的 sigma 放到本次调用上下文的 mutation_sigma，ContextGaussianMutation 读取这个值；base_sigma 只是键不存在时的后备值。若仍使用原固定 GaussianMutation(.1)，Adapter 的 sigma 会变化，但变异算子的噪声尺度不会随之变化。本例不再设置直属 mutator，也不手工调用 mutate/repair。变异只产生提案，问题修复由正式送评流程执行；初值准备是另一个阶段。

`plugins/trajectory_report.py` 完整内容：

```python
from pathlib import Path
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json

class TrajectoryReport(Plugin):
    def __init__(self, search, path):
        super().__init__(name="trajectory_report")
        self.search, self.path = search, Path(path)
        self.rows = []

    def on_generation_committed(self, generation, outcome):
        self.rows.append({
            "generation": int(generation),
            "runtime": self.search.get_runtime_context_projection(self.solver),
        })

    def on_solver_finish(self, result):
        control = self.solver
        refs = tuple(self.search.get_pool_refinement_results(control))
        if not refs:
            raise RuntimeError("trajectory did not deliver an evaluated result")
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        self.payload = {
            "run_id": control.run_session.run_id,
            "steps": self.rows,
            "runtime": self.search.get_runtime_context_projection(control),
            "current_score": self.search.current_score,
            "selected_refs": [ref.as_dict() for ref in refs],
            "selected_candidates": batch.numeric_matrix.tolist(),
            "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
        }

    def on_solver_finalized(self, result):
        atomic_write_json(self.path, self.payload)
```

这个观察器在 finishing 复制已评估结果，finalized 后写本地观察文件；不是新的权威 Artifact，也不是通用 checkpoint 观察器。历史只记录本例有限的提交代，失败尝试不冒充新代。本例没有装配恢复插件，不声称这份观察历史支持跨进程恢复。

`build_solver.py` 完整内容：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.project import apply_solver_component_overrides
from .adapter.adaptive_search import build_adapter
from .pipeline import build_pipeline
from .plugins.trajectory_report import TrajectoryReport
from .problem import build_problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("this recipe configures the local adapter factory explicitly")
    search = build_adapter()
    control = ComposableSolver(
        problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=search, resource_context=resource_context,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance(),
        plugin_strict=True, snapshot_strict=True,
    )
    control.set_random_seed(37)
    control.set_max_steps(12)
    control.add_plugin(TrajectoryReport(search,
        Path(__file__).resolve().parent / "results" / "trajectory.json"))
    apply_solver_component_overrides(control, component_overrides)
    return control
```

首次提案是单个起点评估，之后才按 batch_size 试探邻域。当前实现以 `exp(adapt_gain × (target_success_rate − 近期成功率))` 缩放 sigma，并裁到 min/max：低于目标时放大，高于目标时缩小；这里是在说明实际规则，不保证它适合任意问题。停滞达到 restart_patience 后重新初始化当前点，下次先做新基准评估。violation_penalty 是内部排序参数，硬准入仍由 FeasibleEvaluationAcceptance 消费 raw 约束。

**怎样判断接对：** 正常完成后读取 Case 副本 `results/trajectory.json` 并核对本轮 run_id。selected_candidates 通常一行两列，raw_objectives 为对应平方和、raw_violations 为零。steps 中的 runtime 含 single_traj_sigma/single_traj_state；sigma 在声明范围内，但可以因成功率恰好相等而暂时不变。初始基准代不等同于一次步长适应。

selected_refs 是 Adapter 交付的历史最好已评估版本，不是全部试探，也未必等于当前点。允许较差接受时当前点可移开；重启后 current_score 还可能是 None，不能用新初值冒充已评估结果。本例没有 Bias，且双方采用相同单目标比较，Solver incumbent 与轨迹历史最好可以重合；更换任务投影或选择规则后须分别读取，不能把这些概念当成固定同一个对象，也不能认为它们必然不同。

**运行入口：** 在 Project 副本根目录执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。前者只检查构造。旧 JSON 不代表新运行成功，数值和实际提交次数以本次运行结果为准；本书没有执行这些命令。

### 变体一：关闭较差接受，便于检查贪心移动

只在 adapter/adaptive_search.py 中替换完整工厂；其它文件与入口继续用上文：

```python
from nsgablack.adapters import SingleTrajectoryAdaptiveAdapter, SingleTrajectoryAdaptiveConfig

def build_adapter():
    return SingleTrajectoryAdaptiveAdapter(SingleTrajectoryAdaptiveConfig(
        batch_size=4, initial_sigma=.2, min_sigma=.02, max_sigma=.8,
        target_success_rate=.25, adapt_gain=1.2, success_window=8,
        restart_patience=100, accept_worse_prob=0.,
    ), name="trajectory")
```

本例12代内不会达到100次连续停滞，较差接受关闭，便于对照当前分数与历史最好。代价是失去这条随机跳出路径；sigma 适应仍启用，不能称为固定步长算法。换成硬约束问题时仍须核对原始违反量与准入规则。

源码依据：`adapters/single_trajectory_adaptive/adapter.py`、`adapters/pool_results.py`、`representation/continuous.py::ContextGaussianMutation`，以及原 catalog_recipes/composite 的 Problem、Pipeline 和 Project。
