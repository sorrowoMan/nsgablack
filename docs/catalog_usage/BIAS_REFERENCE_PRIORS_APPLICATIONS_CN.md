# 分布距离与参考位置：CMA/PSO名称在这里仅表示软先验

本文实际装配四个可用的标量评分类，每个实验只选其中一个。它们不维护CMA协方差适应、PSO速度、粒子个体最优或真实全局最好；需要完整算法时使用相应Adapter/Unit，而不是把本页当作算法实现。全部代码按源码核对，未执行算法、模型或命令。

## priors.host · 完整正式Case与候选局部指标来源

复制完整 `examples/cases/bias_gallery` Project，保留Project default组、L0、所有包和规范Case入口。下面路径相对 `cases/bias_gallery/`。新增 `problem/prior_sphere.py` 完整文件：

```python
import numpy as np
from blackbase.types import Feedback
from nsgablack.core import BlackBoxProblem


class PriorSphere(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="sphere_with_declared_priors", dimension=2,
            bounds=[(-2., 2.)] * 2, objectives=["sphere"])

    def evaluate(self, x, context):
        a = np.asarray(x, dtype=float)
        return Feedback(objectives=[float(a @ a)], metrics={
            "mean": [.5, -.5], "cov": [[1., 0.], [0., 1.]], "sigma": .8,
            "global_best_x": [1., 1.], "local_best_x": [-.5, .5],
            "max_generations": 6,
            "case.prior_generation": int(context.get("generation", 0)),
            "case.prior_x": a.tolist(),
        })
```

这些是Case明确声明的**固定先验**。两个历史名称含best的指标不是从其它算法偷读的运行最好；这里仅用来演示同名字段的距离成本。若真要使用某个活Unit的best/mean/cov，须另设计明确所有者读取，不把本例固定值改成共享可写数组。小型2维先验随每候选Feedback交付，标准评估边界将其送给该候选的Bias metrics；不是靠上一行全局ContextStore缓存。

在Case的context_keys.json注册以下键；若已有声明则向数组追加去重，不覆盖其它声明：

```json
["metrics.mean", "metrics.cov", "metrics.sigma", "metrics.global_best_x",
 "metrics.local_best_x", "metrics.max_generations", "metrics.case.prior_generation",
 "metrics.case.prior_x"]
```

新增 `adapter/prior_search.py`：

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation


def build_adapter():
    return NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-2., 2.), mutator=GaussianMutation(sigma=.3))
```

新增 `pipeline/prior_pipeline.py`：

```python
from nsgablack.representation import RepresentationPipeline, ClipRepair


def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-2., 2.))
```

评分工厂与独立公式读取放下一节的 `bias/reference.py`。新增 `plugins/prior_report.py`：

```python
import numpy as np
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json
from ..bias.reference import KIND, expected_delta


class PriorReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="prior_report")
        self.search, self.output = search, output

    def on_solver_finish(self, result):
        control = self.solver
        refs = tuple(self.search.get_population_solution_refs(control))
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selected_f, selected_v = self.search.get_population_snapshot()
        last = control.get_last_feedback_batch()
        expected = [expected_delta(item.metrics["case.prior_x"],
                    item.metrics["case.prior_generation"]) for item in last.items]
        self.payload = {
            "run_id": control.run_session.run_id, "kind": KIND,
            "refs": [ref.as_dict() for ref in refs],
            "candidates": control.read_solutions(refs).numeric_matrix.tolist(),
            "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
            "selection_objectives": selected_f.tolist(),
            "selection_violations": selected_v.tolist(),
            "last_metrics": [dict(item.metrics) for item in last.items],
            "last_raw": last.raw_objectives.tolist(),
            "last_selection": last.objectives.tolist(),
            "last_delta_matches": bool(np.allclose(
                last.objectives[:, 0] - last.raw_objectives[:, 0], expected)),
        }

    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

Report只重算明确公式，不再次调用Bias.compute。动态先验的最终成员可能来自不同代，因此只对最后评估批的本候选metrics验公式，不用最后一代系数重算整个历史种群。

## priors.assembly · 只装配一次，保留原始目标

完整替换 `build_solver.py`：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from .adapter.prior_search import build_adapter
from .bias.reference import build_bias
from .pipeline.prior_pipeline import build_pipeline
from .plugins.prior_report import PriorReport
from .problem.prior_sphere import PriorSphere


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this recipe uses explicitly declared priors")
    search = build_adapter()
    control = ComposableSolver(problem=PriorSphere(), adapter=search,
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    control.set_random_seed(17)
    control.set_max_steps(6)
    control.set_bias_module(build_bias(), enable=True)
    control.add_plugin(PriorReport(search,
        Path(__file__).resolve().parents[2] / "results" / "reference_priors.json"))
    return control
```

BiasModule关闭缓存，以免把有代数系数的先验误当恒定评分。没有硬约束的本例raw违反量为0；显式FeasibleEvaluationAcceptance仍按raw判断，而非先验软化后的选择值。Source、数值算子、问题修复、Unit、求值和环境选择继续各自负责，不在Bias内生成新候选或重复评估。

**运行入口：** 在Project副本根执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。只有后者运行；本轮未执行。检查本次 `results/reference_priors.json` 的run_id与Project终态。它是成功finalized后写出的本地观察，不是独立权威Artifact；旧文件不能代表本轮成功。

## bias.cmaes · 固定均值与协方差下的距离成本

**什么时候用：** 原问题平方和保持不变，额外偏好靠近一个明确的二维分布中心。此处CMAESBias只是软先验，不执行CMA-ES整批采样/排序/协方差更新。

**先准备什么：** 使用共用两节的完整正式Case、Problem/Adapter/Pipeline/Report/薄builder及context键声明。mean=(.5,-.5)、cov=I、sigma=.8来自当前候选Feedback，weight=.2、scale=.1。

**放在哪：** 新建 `bias/reference.py`，完整内容：

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.algorithmic.cma_es import CMAESBias, AdaptiveCMAESBias

KIND = "cma_distance"


def build_bias():
    module = BiasModule()
    module.cache_enabled = False
    if KIND == "cma_distance":
        component = CMAESBias(weight=.2, scale=.1)
    elif KIND == "cma_adaptive":
        component = AdaptiveCMAESBias(weight=.2, min_scale=.02, max_scale=.2)
    else:
        raise ValueError("unknown distribution prior")
    module.add(component)
    return module


def expected_delta(x, generation):
    distance = float(np.linalg.norm(np.asarray(x) - np.array([.5, -.5])))
    ratio = min(1., max(0., float(generation) / 6.))
    scale = .1 if KIND == "cma_distance" else .2 - (.2 - .02) * ratio
    return .2 * scale * .8 * distance / (1. + distance)
```

**接入步骤：** 使用上述固定先验工厂后按共用builder挂载。compute不再乘weight，基类只乘一次，所以本例不是weight平方。cov不提供时用欧氏距离；提供时用伪逆的Mahalanobis距离，出错会退回欧氏距离；生产使用仍须验证cov是期望的有限正定/半正定矩阵。本例I避免将异常回退伪装成已使用协方差。

**怎样判断接对：** raw等于x²+y²、raw_violations=0，selection增加非负距离成本；last_delta_matches应true。mean/sigma/cov应出现在每个last_metrics中。缺mean时返回0，不是“自动找到了均值”；本例明确提供它。别用这份报告声称CMA-ES分布收敛。

**运行入口：** 共用正式Project两条命令，结果路径与运行身份按共用节核对。

### 变体一：使用随逻辑代数减弱的分布成本

**目的：** 验证AdaptiveCMAESBias真实消费的是本候选generation与max_generations。**改在哪里：** 只将同文件KIND改为：

```python
KIND = "cma_adaptive"
```

**行为变化：** scale由.2线性降到.02，超过计划6代后钳在.02；原始目标不变。**限制：** 这是评分强度日程，不是协方差/步长学习；max_generations必须为正。报告只按各行保存的代数验公式，不把不同代数的选择值等同于固定真实损失。

## bias.pso · 两个明确参考位置的距离成本

**什么时候用：** 想给候选与两个固定参考位置的距离加软成本。指标沿用旧global_best_x/local_best_x名称，但本配方明确将它们当Case先验，不冒充活算法的全局/个体最优。

**先准备什么：** 共用两节的另一个独立Project副本。候选、raw目标和报告完全相同，两个参考点为(1,1)与(-.5,.5)，无需创建粒子Unit。

**放在哪：** 完整替换此副本 `bias/reference.py`：

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.algorithmic.pso import ParticleSwarmBias, AdaptivePSOBias

KIND = "pso_distance"


def build_bias():
    module = BiasModule()
    module.cache_enabled = False
    if KIND == "pso_distance":
        component = ParticleSwarmBias(weight=.2, social_weight=1.5,
                                      cognitive_weight=1., scale=.1)
    elif KIND == "pso_adaptive":
        component = AdaptivePSOBias(weight=.2, scale=.1,
            min_social=.5, max_social=2., min_cognitive=.5, max_cognitive=2.)
    else:
        raise ValueError("unknown reference-position prior")
    module.add(component)
    return module


def expected_delta(x, generation):
    a = np.asarray(x, dtype=float)
    global_distance = float(np.linalg.norm(a - np.array([1., 1.])))
    local_distance = float(np.linalg.norm(a - np.array([-.5, .5])))
    ratio = min(1., max(0., float(generation) / 6.))
    social, cognitive = ((1.5, 1.) if KIND == "pso_distance" else
                         (.5 + 1.5 * ratio, 2. - 1.5 * ratio))
    return .2 * .1 * (social * global_distance / (1. + global_distance)
                       + cognitive * local_distance / (1. + local_distance))
```

**接入步骤：** 共用builder实际挂此module。ParticleSwarmBias.compute只输出距离成本，基类乘weight一次；没有速度方程、逐粒子pbest更新、gBest仲裁或候选移动。两个指标缺失时返回0；本例逐候选提供，避免“能运行但没评分”。真正引用某个活Unit最佳时，应另定义正式依赖，不让Problem读取其它Adapter私有字段。

**怎样判断接对：** last_delta_matches按两个饱和距离系数核对；raw平方和不变，选择值不小于raw。source_refs与Unit成员仍由NSGA2维护，不能把参考点坐标注册为真实已求值候选，或因为称为best就将它们写回池。

**运行入口：** 同一Project default的共用命令；本轮没有执行或验证PSO算法。

### 变体一：从个体参考偏重逐渐转向群体参考偏重

**目的：** 展示AdaptivePSOBias实际参数日程。**改在哪里：** 只改KIND：

```python
KIND = "pso_adaptive"
```

**行为变化：** social从.5升到2，cognitive从2降到.5，max_generations=6且ratio钳在[0,1]。**限制：** 参考点仍固定，日程改变的只是软评分；没有因此恢复PSO速度或个体记忆。不同代数选择值可以使用不同系数，不在报告中用终代参数重算旧成员。

源码：`bias/algorithmic/cma_es.py`、`bias/algorithmic/pso.py`、`bias/core/base.py::compute_with_tracking`、`core/solver_helpers/bias_helpers.py::project_bias_feedback`。本页没有给旧类补核心状态机制，也没有把常量先验当作算法产生的数据。
