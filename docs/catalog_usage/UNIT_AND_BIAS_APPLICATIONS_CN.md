# Unit 与 Bias：从实例视图到可解释的软选择

本书按当前源码编写。每章都是独立操作方案：在现有正式 Project 的副本中只选一章应用，不把六份同名入口叠加。六章基线已做导入和工厂构造检查，Unit 均未创建；变体只做编译检查，没有执行 setup、提案、算法、模型或运行入口。报告区分算法成员、原始评估、选择投影和 Solver incumbent；构造通过不能被描述为运行成功。

## tool.unit_view · 在真实搜索实例上观察只读结构

**什么时候用：** 想知道 NSGA2 当前到底持有哪些成员、视图来自哪个实例和版本，而不把 Adapter 的可写内部数组交给观察代码。UnitView 是脱离的结构快照；这里实际得到具有成员能力的 PopulationView。

**先准备什么：** 当前 nsgablack、blackbase 和 NumPy；复制现有 `examples/cases/bias_gallery` Project 到自己的工作目录，保留 `project_config.py`、`run_project.py` 和完整 `cases/bias_gallery/`。该 Project 的 `default` 组只有 `main` 阶段，会调用 `bias_gallery` Case，Project L0 提供 ResourceContext。本章不使用策略参数或组件覆盖；要换 Adapter/Bias，须同步修改绑定和报告，不能让旧观察器读取已被替换的实例。

**放在哪：** 新增下面的本地 Bias/Plugin 文件、追加包导出，再完整替换副本中的 `cases/bias_gallery/build_solver.py`。现有 `problem/example_problem.py::SphereProblem` 接受 dimension，定义有 [-5,5] 边界、单个平方和目标且无硬约束。下面明确使用二维问题；保留该 Problem、包标记及原 Case 运行薄入口。Case 根包无需改名；本章工厂仍叫 build_solver，Bias/Plugin 的实际包导出与跨模块导入一并列出。

**接入步骤：** 按下面逐个文件接入，各文件完整且不依赖别章。显式 initializer 和 mutator 归 Adapter；ClipRepair 归问题管线。

新增完整 `cases/bias_gallery/bias/learning.py`，只定义本章偏好/报告摘要函数，不构造 Solver 或 Unit：

```python
import numpy as np
from nsgablack.units import UnitView

OWNER = ("bias_gallery", "search")

def describe(adapter, view, control):
    if not isinstance(view, UnitView):
        raise TypeError("expected a declared Unit view")
    return dict(
        view_type=type(view).__name__,
        identity_complete=view.membership_identity_complete,
        slots=len(view.population),
        readonly=not view.population.flags.writeable,
        schema=view.schema.as_dict(),
    )
```

新增完整 `cases/bias_gallery/plugins/learning_report.py`。观察器接收明确 Adapter、视图标签和摘要函数；它只观察已有 Unit：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class Report(Plugin):
    def __init__(self, adapter, path, *, describe, owner_path):
        super().__init__("unit_bias_report")
        self.adapter = adapter
        self.path = Path(path)
        self.describe = describe
        self.owner_path = tuple(owner_path)

    def on_solver_finish(self, result):
        control = self.solver
        view = self.adapter.preference_view(owner_path=self.owner_path)
        if view is None:
            raise RuntimeError("search Unit was never activated")
        refs = self.adapter.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selection_f, selection_v = self.adapter.get_population_snapshot()
        self.payload = dict(
            run_id=control.run_session.run_id,
            owner_path=list(view.owner_path), unit_id=view.unit_id,
            revision=view.revision, tokens=list(view.candidate_tokens),
            refs=[ref.as_dict() for ref in refs],
            candidates=batch.numeric_matrix.tolist(),
            raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist(),
            selection_objectives=selection_f.tolist(),
            selection_violations=selection_v.tolist(),
            detail=self.describe(self.adapter, view, control),
        )

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

保留原包文件内容，在 `cases/bias_gallery/bias/__init__.py` 末尾追加导出：

```python
from .learning import OWNER, describe
```

在 `cases/bias_gallery/plugins/__init__.py` 末尾追加导出，保留原有其它导出：

```python
from .learning_report import Report
```

完整替换规范入口 `cases/bias_gallery/build_solver.py`，只做工厂与插件接线：

```python
from pathlib import Path
from nsgablack.adapters import NSGA2Adapter
from nsgablack.core import ComposableSolver
from nsgablack.representation import (
    RepresentationPipeline, ClipRepair, UniformInitializer, GaussianMutation,
)
from .problem.example_problem import SphereProblem
from .bias import OWNER, describe
from .plugins import Report

def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this learning assembly uses its declared components")
    adapter = NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3))
    solver = ComposableSolver(
        problem=SphereProblem(dimension=2), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(-5., 5.)),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(None, enable=False)
    solver.add_plugin(Report(adapter, Path(__file__).resolve().parents[2]
                             / "results" / "unit_view.json", describe=describe, owner_path=OWNER))
    return solver
```


构造 Adapter、读取 get_unit_id 或装配 UnitBinding 都不创建运行结构。实际初始化/提案需要结构时才 ensure_unit；preference_view 在未激活时返回 None，观察者不能为了拿视图调用 ensure_unit。这里在 on_solver_finish 读取，完整正常运行已有实际成员。视图 identity 由 owner_path、unit_id、schema 组成，revision 标识该 codec 内容的快照；它不授予修改或搜索决策权，也不是全局进度计数。OWNER 是本章明确指定的实例标签，不能靠类名推断其他组合里的路径。

标准调用链是 Project → Case build_solver → Adapter 提案 → 问题管线修复 → Problem 原始反馈 → 可选 Bias 选择投影 → 接纳 → Adapter 更新/NSGA2 生存选择 → 步骤提交。Report 在 finishing 时只读取最终成员及已评估反馈，在 finalized 后写本地副本，不求值、不构造 Unit、不手动控制事务。Adapter 提交的成员与 accepted 历史不同；Project 的单个 best_solution/best_objectives 是 Solver incumbent，不能代替本报告的成员集合。

**怎样判断接对：** 打开 `results/unit_view.json`。detail.view_type 应为 PopulationView、readonly 为 true、完整送评后 identity_complete 为 true。比较 revision 时同时比较 identity；相同数值或相同 revision 不能跨实例冒充同一 Unit。所有章节的 refs、tokens、candidates、raw 与 selection 行序应对应；二维 Sphere 的 raw_objectives 每行应为坐标平方和，raw_violations 应为零。selection 是成员当次送评时的选择反馈，不是用最终参考群体重新评分所得；不要在报告阶段重算它来“校正”历史。

**运行入口：** 在该 Project 副本根目录先执行 `python run_project.py --check --build-check`，核对默认组仍是 bias_gallery；再执行 `python run_project.py`。构建检查不会证明评分或收敛。JSON 只在最终成功发布通知后写入，是本地观察文件；核对本轮 run_id，旧文件不代表本轮成功。上面是供用户执行的入口，本轮未运行。

### 变体一：按 token 列出重复占位，而非偷偷去重

**目的：** 为可能出现一个候选占多个槽位的结构报告成员位置，保留“槽位属于视图、token 属于候选”的区别。

**改在哪里：** 只替换 `bias/learning.py` 的 describe，保留完整工厂和 Report：

```python
def describe(adapter, view, control):
    slots_by_token = {}
    unknown_slots = []
    for index, token in enumerate(view.candidate_tokens):
        if token is None:
            unknown_slots.append(index)
        else:
            slots_by_token.setdefault(token, []).append(index)
    return dict(slots_by_token=slots_by_token,
                unknown_slots=unknown_slots,
                readonly=not view.population.flags.writeable)
```

**行为变化：** detail 显示每个 token 的所有行号；重复数值但不同 token 仍是不同候选，同 token 多槽位保留全部行。本节 NSGA2 未必产生重复占位，此分组用于正确解释实际观察到的成员。

**限制：** 行号仅属于当前 view/revision，不是持久候选 ID；未知 token 保留 None 语义，不以坐标或自增编号伪造身份。不能把只读数组改回 writable，也不能把这个报告作为完整 population 恢复格式。

源码核对：`units/views.py`、`adapters/unit_backed.py::preference_view`、`adapters/nsga2/adapter.py::get_population_solution_refs`；正式宿主的 `project_config.py`、`cases/bias_gallery/build_solver.py` 和 `problem/example_problem.py`。这里只给装配及结果检查办法，没有性能或收敛承诺。

## bias.population_diversity · 度量成员分散程度，先不改变搜索

**什么时候用：** 需要解释搜索是否挤在同一区域，先记录群体平均最近邻距离，避免把一个评分对象误当成会自动选父代、填种群或拒绝重复点的算法。

**先准备什么：** 当前 nsgablack、blackbase 和 NumPy；复制现有 `examples/cases/bias_gallery` Project 到自己的工作目录，保留 `project_config.py`、`run_project.py` 和完整 `cases/bias_gallery/`。该 Project 的 `default` 组只有 `main` 阶段，会调用 `bias_gallery` Case，Project L0 提供 ResourceContext。本章不使用策略参数或组件覆盖；要换 Adapter/Bias，须同步修改绑定和报告，不能让旧观察器读取已被替换的实例。

**放在哪：** 新增下面的本地 Bias/Plugin 文件、追加包导出，再完整替换副本中的 `cases/bias_gallery/build_solver.py`。现有 `problem/example_problem.py::SphereProblem` 接受 dimension，定义有 [-5,5] 边界、单个平方和目标且无硬约束。下面明确使用二维问题；保留该 Problem、包标记及原 Case 运行薄入口。Case 根包无需改名；本章工厂仍叫 build_solver，Bias/Plugin 的实际包导出与跨模块导入一并列出。

**接入步骤：** 按下面逐个文件接入，各文件完整且不依赖别章。显式 initializer 和 mutator 归 Adapter；ClipRepair 归问题管线。

新增完整 `cases/bias_gallery/bias/learning.py`，只定义本章偏好/报告摘要函数，不构造 Solver 或 Unit：

```python
import numpy as np
from nsgablack.bias import PopulationDiversityPreference, PreferenceQuery

OWNER = ("bias_gallery", "search")

def describe(adapter, view, control):
    score = PopulationDiversityPreference().evaluate(
        PreferenceQuery("unit", unit=view))
    return dict(scope="unit", value=score.value,
                direction=score.direction, reason=score.reason)
```

新增完整 `cases/bias_gallery/plugins/learning_report.py`。观察器接收明确 Adapter、视图标签和摘要函数；它只观察已有 Unit：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class Report(Plugin):
    def __init__(self, adapter, path, *, describe, owner_path):
        super().__init__("unit_bias_report")
        self.adapter = adapter
        self.path = Path(path)
        self.describe = describe
        self.owner_path = tuple(owner_path)

    def on_solver_finish(self, result):
        control = self.solver
        view = self.adapter.preference_view(owner_path=self.owner_path)
        if view is None:
            raise RuntimeError("search Unit was never activated")
        refs = self.adapter.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selection_f, selection_v = self.adapter.get_population_snapshot()
        self.payload = dict(
            run_id=control.run_session.run_id,
            owner_path=list(view.owner_path), unit_id=view.unit_id,
            revision=view.revision, tokens=list(view.candidate_tokens),
            refs=[ref.as_dict() for ref in refs],
            candidates=batch.numeric_matrix.tolist(),
            raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist(),
            selection_objectives=selection_f.tolist(),
            selection_violations=selection_v.tolist(),
            detail=self.describe(self.adapter, view, control),
        )

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

保留原包文件内容，在 `cases/bias_gallery/bias/__init__.py` 末尾追加导出：

```python
from .learning import OWNER, describe
```

在 `cases/bias_gallery/plugins/__init__.py` 末尾追加导出，保留原有其它导出：

```python
from .learning_report import Report
```

完整替换规范入口 `cases/bias_gallery/build_solver.py`，只做工厂与插件接线：

```python
from pathlib import Path
from nsgablack.adapters import NSGA2Adapter
from nsgablack.core import ComposableSolver
from nsgablack.representation import (
    RepresentationPipeline, ClipRepair, UniformInitializer, GaussianMutation,
)
from .problem.example_problem import SphereProblem
from .bias import OWNER, describe
from .plugins import Report

def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this learning assembly uses its declared components")
    adapter = NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3))
    solver = ComposableSolver(
        problem=SphereProblem(dimension=2), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(-5., 5.)),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(None, enable=False)
    solver.add_plugin(Report(adapter, Path(__file__).resolve().parents[2]
                             / "results" / "population_diversity.json", describe=describe, owner_path=OWNER))
    return solver
```


本章故意不挂 BiasModule：PopulationDiversityPreference.evaluate 是纯评分，Report 明确消费其结果，搜索仍由 NSGA2 决策。unit scope 的值是每个槽位到最近其他槽位距离的平均；不足两个槽位为零。方向 maximize 已写进 PreferenceScore，但不会自动改变 Solver。距离使用原始决策坐标；量纲悬殊的变量不能直接把较大距离解释成更好的覆盖。unit_transition 另需同 identity 的两个真实视图，不能拿另一个 Adapter 充当 proposed_unit。

标准调用链是 Project → Case build_solver → Adapter 提案 → 问题管线修复 → Problem 原始反馈 → 可选 Bias 选择投影 → 接纳 → Adapter 更新/NSGA2 生存选择 → 步骤提交。Report 在 finishing 时只读取最终成员及已评估反馈，在 finalized 后写本地副本，不求值、不构造 Unit、不手动控制事务。Adapter 提交的成员与 accepted 历史不同；Project 的单个 best_solution/best_objectives 是 Solver incumbent，不能代替本报告的成员集合。

**怎样判断接对：** 打开 `results/population_diversity.json`。detail 应有 scope=unit、direction=maximize、reason=mean_nearest_member_distance，value 非负。值为零可能来自重合成员或不足两个槽位，不等于运行失败；大值也不证明目标更优、可行或覆盖前沿。所有章节的 refs、tokens、candidates、raw 与 selection 行序应对应；二维 Sphere 的 raw_objectives 每行应为坐标平方和，raw_violations 应为零。selection 是成员当次送评时的选择反馈，不是用最终参考群体重新评分所得；不要在报告阶段重算它来“校正”历史。

**运行入口：** 在该 Project 副本根目录先执行 `python run_project.py --check --build-check`，核对默认组仍是 bias_gallery；再执行 `python run_project.py`。构建检查不会证明评分或收敛。JSON 只在最终成功发布通知后写入，是本地观察文件；核对本轮 run_id，旧文件不代表本轮成功。上面是供用户执行的入口，本轮未运行。

### 变体一：逐成员解释“它离其他候选有多远”

**目的：** 从群体概况切换到候选在明确群体中的最近邻新颖性，找出拥挤成员。

**改在哪里：** 只替换 `bias/learning.py` 的 describe：

```python
def describe(adapter, view, control):
    policy = PopulationDiversityPreference()
    scores = []
    for candidate, token in zip(view.population, view.candidate_tokens):
        score = policy.evaluate(PreferenceQuery("candidate_in_unit",
            candidate=candidate, candidate_token=token, unit=view))
        scores.append(dict(token=token, value=score.value,
                           direction=score.direction, reason=score.reason))
    return dict(scope="candidate_in_unit", members=scores)
```

**行为变化：** 只有已知同 token 的槽位被排除；不同 token 即使坐标相同仍算零距离。token=None 时不猜“自身”，这是初始化草稿的保守行为。本节最终已评估成员正常应有完整 token。

**限制：** candidate scope 不受该策略支持；候选维度必须与 PopulationView 一致。此报告仍不产生 Bias 或硬筛选；要把候选新颖性投影到选择目标，采用下一类 UnitPreferenceBias 装配。

源码核对：`bias/preferences.py::PreferenceQuery`、`PopulationDiversityPreference.evaluate` 和 `units/views.py::PopulationView`；正式宿主的 `project_config.py`、`cases/bias_gallery/build_solver.py` 和 `problem/example_problem.py`。这里只给装配及结果检查办法，没有性能或收敛承诺。

## bias.unit_preference · 把实例绑定的新颖性接入选择目标

**什么时候用：** 同一 Sphere 搜索容易聚在少数位置，希望给远离当前成员的新提案一点软奖励，同时保留平方和原始目标、候选身份与正常接纳过程。

**先准备什么：** 当前 nsgablack、blackbase 和 NumPy；复制现有 `examples/cases/bias_gallery` Project 到自己的工作目录，保留 `project_config.py`、`run_project.py` 和完整 `cases/bias_gallery/`。该 Project 的 `default` 组只有 `main` 阶段，会调用 `bias_gallery` Case，Project L0 提供 ResourceContext。本章不使用策略参数或组件覆盖；要换 Adapter/Bias，须同步修改绑定和报告，不能让旧观察器读取已被替换的实例。

**放在哪：** 新增下面的本地 Bias/Plugin 文件、追加包导出，再完整替换副本中的 `cases/bias_gallery/build_solver.py`。现有 `problem/example_problem.py::SphereProblem` 接受 dimension，定义有 [-5,5] 边界、单个平方和目标且无硬约束。下面明确使用二维问题；保留该 Problem、包标记及原 Case 运行薄入口。Case 根包无需改名；本章工厂仍叫 build_solver，Bias/Plugin 的实际包导出与跨模块导入一并列出。

**接入步骤：** 按下面逐个文件接入，各文件完整且不依赖别章。显式 initializer 和 mutator 归 Adapter；ClipRepair 归问题管线。

新增完整 `cases/bias_gallery/bias/learning.py`，只定义本章偏好/报告摘要函数，不构造 Solver 或 Unit：

```python
import numpy as np
from nsgablack.bias import (BiasModule, UnitPreferenceBias,
    PopulationDiversityPreference)

OWNER = ("bias_gallery", "search")

def build_bias(adapter):
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(
        PopulationDiversityPreference(), adapter, owner_path=OWNER,
        name="population_novelty", weight=.1))
    return module

def describe(adapter, view, control):
    bias = control.bias_module.get_bias("population_novelty")
    return dict(binding=bias.get_state(),
                active_names=control.bias_module.list_biases())
```

新增完整 `cases/bias_gallery/plugins/learning_report.py`。观察器接收明确 Adapter、视图标签和摘要函数；它只观察已有 Unit：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class Report(Plugin):
    def __init__(self, adapter, path, *, describe, owner_path):
        super().__init__("unit_bias_report")
        self.adapter = adapter
        self.path = Path(path)
        self.describe = describe
        self.owner_path = tuple(owner_path)

    def on_solver_finish(self, result):
        control = self.solver
        view = self.adapter.preference_view(owner_path=self.owner_path)
        if view is None:
            raise RuntimeError("search Unit was never activated")
        refs = self.adapter.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selection_f, selection_v = self.adapter.get_population_snapshot()
        self.payload = dict(
            run_id=control.run_session.run_id,
            owner_path=list(view.owner_path), unit_id=view.unit_id,
            revision=view.revision, tokens=list(view.candidate_tokens),
            refs=[ref.as_dict() for ref in refs],
            candidates=batch.numeric_matrix.tolist(),
            raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist(),
            selection_objectives=selection_f.tolist(),
            selection_violations=selection_v.tolist(),
            detail=self.describe(self.adapter, view, control),
        )

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

保留原包文件内容，在 `cases/bias_gallery/bias/__init__.py` 末尾追加导出：

```python
from .learning import OWNER, describe, build_bias
```

在 `cases/bias_gallery/plugins/__init__.py` 末尾追加导出，保留原有其它导出：

```python
from .learning_report import Report
```

完整替换规范入口 `cases/bias_gallery/build_solver.py`，只做工厂与插件接线：

```python
from pathlib import Path
from nsgablack.adapters import NSGA2Adapter
from nsgablack.core import ComposableSolver
from nsgablack.representation import (
    RepresentationPipeline, ClipRepair, UniformInitializer, GaussianMutation,
)
from .problem.example_problem import SphereProblem
from .bias import OWNER, describe, build_bias
from .plugins import Report

def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this learning assembly uses its declared components")
    adapter = NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3))
    solver = ComposableSolver(
        problem=SphereProblem(dimension=2), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(-5., 5.)),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(build_bias(adapter), enable=True)
    solver.add_plugin(Report(adapter, Path(__file__).resolve().parents[2]
                             / "results" / "unit_preference.json", describe=describe, owner_path=OWNER))
    return solver
```


from_adapter 在装配时只绑定已有 UnitBinding、稳定 Unit ID 和视图提供者，不提前建 Unit。候选送评时读取该实例当时的 PopulationView，以 candidate_in_unit scope 算最近邻距离；maximize 转为负的最小化增量，再按 weight 加入选择目标。它不修改 Problem raw feedback，不替换 NSGA2 的父代/生存选择，也不使硬不合格候选变合格。

owner_path 声明“参考谁”，不表示“只作用谁”。默认 apply_to_paths=() 不按提案来源过滤；在本章单 Adapter Case 中正好消费该搜索提案。组合场景只有显式传入真实 StrategyOrigin 实例路径才能限制候选作用域，路径按前缀匹配，不能把本地标签 OWNER 当路由器已生成的来源。未激活参考 Unit 会明确报错；不能自动跳过或建 Unit 掩盖接线错误。

标准调用链是 Project → Case build_solver → Adapter 提案 → 问题管线修复 → Problem 原始反馈 → 可选 Bias 选择投影 → 接纳 → Adapter 更新/NSGA2 生存选择 → 步骤提交。Report 在 finishing 时只读取最终成员及已评估反馈，在 finalized 后写本地副本，不求值、不构造 Unit、不手动控制事务。Adapter 提交的成员与 accepted 历史不同；Project 的单个 best_solution/best_objectives 是 Solver incumbent，不能代替本报告的成员集合。

**怎样判断接对：** 打开 `results/unit_preference.json`。detail.binding.binding 应包含 OWNER、此 Adapter 的 unit_id/schema，active_names 包含 population_novelty。raw 仍是平方和；selection 可因当时的新颖性奖励而低于 raw，不要求每行一定不同，也不能拿最终群体距离倒推每次历史奖励。所有章节的 refs、tokens、candidates、raw 与 selection 行序应对应；二维 Sphere 的 raw_objectives 每行应为坐标平方和，raw_violations 应为零。selection 是成员当次送评时的选择反馈，不是用最终参考群体重新评分所得；不要在报告阶段重算它来“校正”历史。

**运行入口：** 在该 Project 副本根目录先执行 `python run_project.py --check --build-check`，核对默认组仍是 bias_gallery；再执行 `python run_project.py`。构建检查不会证明评分或收敛。JSON 只在最终成功发布通知后写入，是本地观察文件；核对本轮 run_id，旧文件不代表本轮成功。上面是供用户执行的入口，本轮未运行。

### 变体一：压缩极远提案的奖励，避免大距离支配原目标

**目的：** 让最近邻新颖性继续单调奖励，同时降低极远提案对选择分数的影响；不是只改权重数字。

**改在哪里：** 在 `bias/learning.py` 额外导入 PreferenceScore，并用以下策略和工厂替换原 build_bias：

```python
from nsgablack.bias import PreferenceScore

class LogNovelty(PopulationDiversityPreference):
    def evaluate(self, query):
        score = super().evaluate(query)
        if query.scope.value != "candidate_in_unit":
            return score
        return PreferenceScore(float(np.log1p(score.value)),
                               "maximize", "log_nearest_other_member_distance")

def build_bias(adapter):
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(
        LogNovelty(), adapter, owner_path=OWNER,
        name="population_novelty", weight=.1))
    return module
```

**行为变化：** 候选距离 d 的选择增量由 -0.1d 改为 -0.1log(1+d)，保留当前 Unit 和 token 的排除语义；群体/transition scope 仍使用原策略定义。

**限制：** 仍是软引导而非多样性下限；不处理坐标量纲。策略类型已变化，旧 checkpoint 绑定校验不等价，应开启新运行，不能声称与原策略恢复兼容。

源码核对：`bias/preferences.py::UnitPreferenceBias.from_adapter/compute/get_state`、`core/solver_helpers/bias_helpers.py::project_bias_feedback`；正式宿主的 `project_config.py`、`cases/bias_gallery/build_solver.py` 和 `problem/example_problem.py`。这里只给装配及结果检查办法，没有性能或收敛承诺。

## bias.module · 把两类软引导放进一个运行门面

**什么时候用：** 需要同时使用依赖当前结构的新颖性奖励和带记忆的重复访问惩罚，统一进入 Solver 的评分、回滚和恢复生命周期，而不是在 Problem.evaluate 内临时改写目标。

**先准备什么：** 当前 nsgablack、blackbase 和 NumPy；复制现有 `examples/cases/bias_gallery` Project 到自己的工作目录，保留 `project_config.py`、`run_project.py` 和完整 `cases/bias_gallery/`。该 Project 的 `default` 组只有 `main` 阶段，会调用 `bias_gallery` Case，Project L0 提供 ResourceContext。本章不使用策略参数或组件覆盖；要换 Adapter/Bias，须同步修改绑定和报告，不能让旧观察器读取已被替换的实例。

**放在哪：** 新增下面的本地 Bias/Plugin 文件、追加包导出，再完整替换副本中的 `cases/bias_gallery/build_solver.py`。现有 `problem/example_problem.py::SphereProblem` 接受 dimension，定义有 [-5,5] 边界、单个平方和目标且无硬约束。下面明确使用二维问题；保留该 Problem、包标记及原 Case 运行薄入口。Case 根包无需改名；本章工厂仍叫 build_solver，Bias/Plugin 的实际包导出与跨模块导入一并列出。

**接入步骤：** 按下面逐个文件接入，各文件完整且不依赖别章。显式 initializer 和 mutator 归 Adapter；ClipRepair 归问题管线。

新增完整 `cases/bias_gallery/bias/learning.py`，只定义本章偏好/报告摘要函数，不构造 Solver 或 Unit：

```python
import numpy as np
from nsgablack.bias import (BiasModule, UnitPreferenceBias,
    PopulationDiversityPreference, TabuSearchBias)

OWNER = ("bias_gallery", "search")

def build_bias(adapter):
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(
        PopulationDiversityPreference(), adapter, owner_path=OWNER,
        name="population_novelty", weight=.1))
    module.add(TabuSearchBias(weight=.15, tabu_size=30,
                             distance_threshold=.3, penalty_scale=.5))
    return module

def describe(adapter, view, control):
    module = control.bias_module
    return dict(names=module.list_biases(),
        novelty_binding=module.get_bias("population_novelty").get_state(),
        tabu=module.get_bias("tabu_search_bias").get_state())
```

新增完整 `cases/bias_gallery/plugins/learning_report.py`。观察器接收明确 Adapter、视图标签和摘要函数；它只观察已有 Unit：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class Report(Plugin):
    def __init__(self, adapter, path, *, describe, owner_path):
        super().__init__("unit_bias_report")
        self.adapter = adapter
        self.path = Path(path)
        self.describe = describe
        self.owner_path = tuple(owner_path)

    def on_solver_finish(self, result):
        control = self.solver
        view = self.adapter.preference_view(owner_path=self.owner_path)
        if view is None:
            raise RuntimeError("search Unit was never activated")
        refs = self.adapter.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selection_f, selection_v = self.adapter.get_population_snapshot()
        self.payload = dict(
            run_id=control.run_session.run_id,
            owner_path=list(view.owner_path), unit_id=view.unit_id,
            revision=view.revision, tokens=list(view.candidate_tokens),
            refs=[ref.as_dict() for ref in refs],
            candidates=batch.numeric_matrix.tolist(),
            raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist(),
            selection_objectives=selection_f.tolist(),
            selection_violations=selection_v.tolist(),
            detail=self.describe(self.adapter, view, control),
        )

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

保留原包文件内容，在 `cases/bias_gallery/bias/__init__.py` 末尾追加导出：

```python
from .learning import OWNER, describe, build_bias
```

在 `cases/bias_gallery/plugins/__init__.py` 末尾追加导出，保留原有其它导出：

```python
from .learning_report import Report
```

完整替换规范入口 `cases/bias_gallery/build_solver.py`，只做工厂与插件接线：

```python
from pathlib import Path
from nsgablack.adapters import NSGA2Adapter
from nsgablack.core import ComposableSolver
from nsgablack.representation import (
    RepresentationPipeline, ClipRepair, UniformInitializer, GaussianMutation,
)
from .problem.example_problem import SphereProblem
from .bias import OWNER, describe, build_bias
from .plugins import Report

def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this learning assembly uses its declared components")
    adapter = NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3))
    solver = ComposableSolver(
        problem=SphereProblem(dimension=2), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(-5., 5.)),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(build_bias(adapter), enable=True)
    solver.add_plugin(Report(adapter, Path(__file__).resolve().parents[2]
                             / "results" / "bias_module.json", describe=describe, owner_path=OWNER))
    return solver
```


BiasModule.add 按真实 AlgorithmicBias/DomainBias 类型注册，返回是否加入；本章名字各不重复。算法类 Bias 提供软启发，不拥有 propose/update 搜索循环，TabuSearchBias 也不是完整 Tabu Search Adapter。module 将当前启用项的加权增量聚合后加到选择目标；不要额外在 Problem 或 Adapter 再加一遍。weight 放在对象构造里；对已构造 Bias 再传 add(..., weight=...) 并不会代替对象权重。

该 module 由一个 Solver 持有；多 Adapter 共用时，其状态不是按 role 自动分库。依赖 Unit 的策略声明 cacheable=False，带记忆 Tabu 也不使用旧分数缓存；不要把状态依赖评分强行缓存为“相同坐标总同分”。有状态记忆由运行事务/恢复负责，不把对象图塞进共享 context。

标准调用链是 Project → Case build_solver → Adapter 提案 → 问题管线修复 → Problem 原始反馈 → 可选 Bias 选择投影 → 接纳 → Adapter 更新/NSGA2 生存选择 → 步骤提交。Report 在 finishing 时只读取最终成员及已评估反馈，在 finalized 后写本地副本，不求值、不构造 Unit、不手动控制事务。Adapter 提交的成员与 accepted 历史不同；Project 的单个 best_solution/best_objectives 是 Solver incumbent，不能代替本报告的成员集合。

**怎样判断接对：** 打开 `results/bias_module.json`。detail.names 包含 population_novelty、tabu_search_bias，tabu.policy 是 committed_admitted_proposals；raw 仍可独立核对平方和。两种增量可互相抵消，所以 selection 恰好等于 raw 不能单独证明未启用。所有章节的 refs、tokens、candidates、raw 与 selection 行序应对应；二维 Sphere 的 raw_objectives 每行应为坐标平方和，raw_violations 应为零。selection 是成员当次送评时的选择反馈，不是用最终参考群体重新评分所得；不要在报告阶段重算它来“校正”历史。

**运行入口：** 在该 Project 副本根目录先执行 `python run_project.py --check --build-check`，核对默认组仍是 bias_gallery；再执行 `python run_project.py`。构建检查不会证明评分或收敛。JSON 只在最终成功发布通知后写入，是本地观察文件；核对本轮 run_id，旧文件不代表本轮成功。上面是供用户执行的入口，本轮未运行。

### 变体一：加入明确领域偏好，并保留现有两项

**目的：** 平方和之外，希望第一坐标达到 1；这是可权衡的区域偏好，不把 x0<1 宣布为硬不可行。

**改在哪里：** 保留 `bias/learning.py` 的原 build_bias，在其定义之后追加如下包装；包导出会取得新工厂，薄 builder 调用它：

```python
_base_bias = build_bias

def build_bias(adapter):
    module = _base_bias(adapter)
    module.add(lambda x: max(0., 1. - float(x[0])) ** 2,
               name="preferred_region", weight=.2)
    return module
```

**行为变化：** add 将该单参函数包装成 CallableBias（domain penalty），聚合第三个正增量；detail.names 会多出 preferred_region。原始平方和与原无硬约束问题不变。

**限制：** 不能拿此处 weight 当全局约束策略；实际不可违反的限制要在 Problem/正式接纳规则中定义。此函数不读 context、不写状态，无需制造未注册共享键。更改策略后使用新运行，不沿用旧组合 checkpoint。

源码核对：`bias/bias_module.py::add/_compute_bias_value/record_accepted`、`bias/core/manager.py::UniversalBiasManager.compute_total_bias` 和 `bias/domain/callable_bias.py`；正式宿主的 `project_config.py`、`cases/bias_gallery/build_solver.py` 和 `problem/example_problem.py`。这里只给装配及结果检查办法，没有性能或收敛承诺。

## bias.tabu · 对已提交接纳提案附近的位置施加软记忆惩罚

**什么时候用：** 想减少连续试探同一区域，同时允许 NSGA2 继续按自己的种群策略选择成员；需要能解释“记住了什么”，而非只看当前 survivor 就猜禁忌表。

**先准备什么：** 当前 nsgablack、blackbase 和 NumPy；复制现有 `examples/cases/bias_gallery` Project 到自己的工作目录，保留 `project_config.py`、`run_project.py` 和完整 `cases/bias_gallery/`。该 Project 的 `default` 组只有 `main` 阶段，会调用 `bias_gallery` Case，Project L0 提供 ResourceContext。本章不使用策略参数或组件覆盖；要换 Adapter/Bias，须同步修改绑定和报告，不能让旧观察器读取已被替换的实例。

**放在哪：** 新增下面的本地 Bias/Plugin 文件、追加包导出，再完整替换副本中的 `cases/bias_gallery/build_solver.py`。现有 `problem/example_problem.py::SphereProblem` 接受 dimension，定义有 [-5,5] 边界、单个平方和目标且无硬约束。下面明确使用二维问题；保留该 Problem、包标记及原 Case 运行薄入口。Case 根包无需改名；本章工厂仍叫 build_solver，Bias/Plugin 的实际包导出与跨模块导入一并列出。

**接入步骤：** 按下面逐个文件接入，各文件完整且不依赖别章。显式 initializer 和 mutator 归 Adapter；ClipRepair 归问题管线。

新增完整 `cases/bias_gallery/bias/learning.py`，只定义本章偏好/报告摘要函数，不构造 Solver 或 Unit：

```python
import numpy as np
from nsgablack.bias import BiasModule, TabuSearchBias

OWNER = ("bias_gallery", "search")

def build_bias(adapter):
    module = BiasModule()
    module.add(TabuSearchBias(weight=.15, tabu_size=30,
                             distance_threshold=.3, penalty_scale=.5))
    return module

def describe(adapter, view, control):
    state = control.bias_module.get_bias("tabu_search_bias").get_state()
    current = set(view.candidate_tokens)
    return dict(memory=state,
        memory_tokens_also_members=[token for token in state["tokens"]
                                   if token in current])
```

新增完整 `cases/bias_gallery/plugins/learning_report.py`。观察器接收明确 Adapter、视图标签和摘要函数；它只观察已有 Unit：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class Report(Plugin):
    def __init__(self, adapter, path, *, describe, owner_path):
        super().__init__("unit_bias_report")
        self.adapter = adapter
        self.path = Path(path)
        self.describe = describe
        self.owner_path = tuple(owner_path)

    def on_solver_finish(self, result):
        control = self.solver
        view = self.adapter.preference_view(owner_path=self.owner_path)
        if view is None:
            raise RuntimeError("search Unit was never activated")
        refs = self.adapter.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selection_f, selection_v = self.adapter.get_population_snapshot()
        self.payload = dict(
            run_id=control.run_session.run_id,
            owner_path=list(view.owner_path), unit_id=view.unit_id,
            revision=view.revision, tokens=list(view.candidate_tokens),
            refs=[ref.as_dict() for ref in refs],
            candidates=batch.numeric_matrix.tolist(),
            raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist(),
            selection_objectives=selection_f.tolist(),
            selection_violations=selection_v.tolist(),
            detail=self.describe(self.adapter, view, control),
        )

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

保留原包文件内容，在 `cases/bias_gallery/bias/__init__.py` 末尾追加导出：

```python
from .learning import OWNER, describe, build_bias
```

在 `cases/bias_gallery/plugins/__init__.py` 末尾追加导出，保留原有其它导出：

```python
from .learning_report import Report
```

完整替换规范入口 `cases/bias_gallery/build_solver.py`，只做工厂与插件接线：

```python
from pathlib import Path
from nsgablack.adapters import NSGA2Adapter
from nsgablack.core import ComposableSolver
from nsgablack.representation import (
    RepresentationPipeline, ClipRepair, UniformInitializer, GaussianMutation,
)
from .problem.example_problem import SphereProblem
from .bias import OWNER, describe, build_bias
from .plugins import Report

def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this learning assembly uses its declared components")
    adapter = NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3))
    solver = ComposableSolver(
        problem=SphereProblem(dimension=2), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(-5., 5.)),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(build_bias(adapter), enable=True)
    solver.add_plugin(Report(adapter, Path(__file__).resolve().parents[2]
                             / "results" / "tabu.json", describe=describe, owner_path=OWNER))
    return solver
```


compute 只读记忆；到最近记忆点距离小于 distance_threshold 时返回线性衰减的正惩罚，再乘 weight。阈值以二维坐标的欧氏距离为单位，不是目标差或可行性阈值。超出半径不罚，不代表被奖励。

真实顺序是接纳裁剪后的 CandidateBatch → Adapter.update → BiasModule.record_accepted。记录处仍在步骤事务内，失败会回滚，只有提交留下记忆。它记录的是接纳的提案，而不是“所有评估过”“最终生存者”或“最佳解”；某候选被 NSGA2 淘汰也可在禁忌记忆内。初始化路径不保证每个最终成员都进这段提案记忆。相同 token 重入不追加，不同 token 相同坐标仍是不同提案记录；容量满时移出最旧记录。不要在评估回调里手工 record_accepted，或在报告时重新送评以填表。

标准调用链是 Project → Case build_solver → Adapter 提案 → 问题管线修复 → Problem 原始反馈 → 可选 Bias 选择投影 → 接纳 → Adapter 更新/NSGA2 生存选择 → 步骤提交。Report 在 finishing 时只读取最终成员及已评估反馈，在 finalized 后写本地副本，不求值、不构造 Unit、不手动控制事务。Adapter 提交的成员与 accepted 历史不同；Project 的单个 best_solution/best_objectives 是 Solver incumbent，不能代替本报告的成员集合。

**怎样判断接对：** 打开 `results/tabu.json`。detail.memory 的 schema、policy、config 与本节策略对应，tokens/candidates 对齐且长度不超过30。memory_tokens_also_members 只显示交集，不要求等于全部最终成员。正常运行最早尚无历史时惩罚为零；某次评估触发但步骤未提交，不能据此要求出现记忆。所有章节的 refs、tokens、candidates、raw 与 selection 行序应对应；二维 Sphere 的 raw_objectives 每行应为坐标平方和，raw_violations 应为零。selection 是成员当次送评时的选择反馈，不是用最终参考群体重新评分所得；不要在报告阶段重算它来“校正”历史。

**运行入口：** 在该 Project 副本根目录先执行 `python run_project.py --check --build-check`，核对默认组仍是 bias_gallery；再执行 `python run_project.py`。构建检查不会证明评分或收敛。JSON 只在最终成功发布通知后写入，是本地观察文件；核对本轮 run_id，旧文件不代表本轮成功。上面是供用户执行的入口，本轮未运行。

### 变体一：对 Sphere 的镜像位置共享“附近”评分

**目的：** 在关于原点镜像对称的二维问题中，把仅改变坐标符号的候选视为同一访问区域，减少对称重复探索。

**改在哪里：** 在 `bias/learning.py` 增加子类并完整替换 build_bias：

```python
class SymmetricTabu(TabuSearchBias):
    def compute(self, x, context):
        points = np.asarray(self.get_state()["candidates"], dtype=float)
        if len(points) == 0:
            return 0.
        distance = float(np.min(np.linalg.norm(
            np.abs(points) - np.abs(x), axis=1)))
        if distance >= self.distance_threshold:
            return 0.
        return self.penalty_scale * (
            1. - distance / max(self.distance_threshold, 1e-9))

def build_bias(adapter):
    module = BiasModule()
    module.add(SymmetricTabu(weight=.15, tabu_size=30,
                            distance_threshold=.3, penalty_scale=.5))
    return module
```

**行为变化：** 只改变距离解释，记忆仍保存真实全坐标和 token，接纳/提交/回滚路径不变。报告中的记忆坐标不会被绝对值覆盖。

**限制：** 仅适用于问题和领域偏好确实有此符号对称性；有方向约束或非对称目标时不要采用。它不合并候选身份，不将镜像硬删除；新子类应作为新装配运行，不能冒充原类 checkpoint。

源码核对：`bias/algorithmic/tabu_search.py`、`bias/bias_module.py::record_accepted` 和 `core/composable_solver.py` 中 accepted_update_batch 的提交前记录；正式宿主的 `project_config.py`、`cases/bias_gallery/build_solver.py` 和 `problem/example_problem.py`。这里只给装配及结果检查办法，没有性能或收敛承诺。

## bias.dynamic_penalty · 随逻辑代数提高区域软偏好的压力

**什么时候用：** 希望先按平方和广泛探索，再逐渐偏向第一坐标不小于1的区域，并能分清原目标、软罚和真实硬约束。该条件在本章是领域偏好，允许付出偏好代价。

**先准备什么：** 当前 nsgablack、blackbase 和 NumPy；复制现有 `examples/cases/bias_gallery` Project 到自己的工作目录，保留 `project_config.py`、`run_project.py` 和完整 `cases/bias_gallery/`。该 Project 的 `default` 组只有 `main` 阶段，会调用 `bias_gallery` Case，Project L0 提供 ResourceContext。本章不使用策略参数或组件覆盖；要换 Adapter/Bias，须同步修改绑定和报告，不能让旧观察器读取已被替换的实例。

**放在哪：** 新增下面的本地 Bias/Plugin 文件、追加包导出，再完整替换副本中的 `cases/bias_gallery/build_solver.py`。现有 `problem/example_problem.py::SphereProblem` 接受 dimension，定义有 [-5,5] 边界、单个平方和目标且无硬约束。下面明确使用二维问题；保留该 Problem、包标记及原 Case 运行薄入口。Case 根包无需改名；本章工厂仍叫 build_solver，Bias/Plugin 的实际包导出与跨模块导入一并列出。

**接入步骤：** 按下面逐个文件接入，各文件完整且不依赖别章。显式 initializer 和 mutator 归 Adapter；ClipRepair 归问题管线。

新增完整 `cases/bias_gallery/bias/learning.py`，只定义本章偏好/报告摘要函数，不构造 Solver 或 Unit：

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.domain.dynamic_penalty import DynamicPenaltyBias

OWNER = ("bias_gallery", "search")

def region_cost(x):
    return max(0., 1. - float(x[0])) ** 2

def build_bias(adapter):
    module = BiasModule()
    module.add(DynamicPenaltyBias(name="region_schedule",
        penalty_func=region_cost, weight=.2, schedule="linear",
        start_scale=.1, end_scale=1., max_generations=6))
    return module

def describe(adapter, view, control):
    bias = control.bias_module.get_bias("region_schedule")
    return dict(schedule=bias.schedule, start_scale=bias.start_scale,
        end_scale=bias.end_scale, max_generations=bias.max_generations,
        region_costs=[region_cost(x) for x in view.population])
```

新增完整 `cases/bias_gallery/plugins/learning_report.py`。观察器接收明确 Adapter、视图标签和摘要函数；它只观察已有 Unit：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class Report(Plugin):
    def __init__(self, adapter, path, *, describe, owner_path):
        super().__init__("unit_bias_report")
        self.adapter = adapter
        self.path = Path(path)
        self.describe = describe
        self.owner_path = tuple(owner_path)

    def on_solver_finish(self, result):
        control = self.solver
        view = self.adapter.preference_view(owner_path=self.owner_path)
        if view is None:
            raise RuntimeError("search Unit was never activated")
        refs = self.adapter.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selection_f, selection_v = self.adapter.get_population_snapshot()
        self.payload = dict(
            run_id=control.run_session.run_id,
            owner_path=list(view.owner_path), unit_id=view.unit_id,
            revision=view.revision, tokens=list(view.candidate_tokens),
            refs=[ref.as_dict() for ref in refs],
            candidates=batch.numeric_matrix.tolist(),
            raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist(),
            selection_objectives=selection_f.tolist(),
            selection_violations=selection_v.tolist(),
            detail=self.describe(self.adapter, view, control),
        )

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

保留原包文件内容，在 `cases/bias_gallery/bias/__init__.py` 末尾追加导出：

```python
from .learning import OWNER, describe, build_bias
```

在 `cases/bias_gallery/plugins/__init__.py` 末尾追加导出，保留原有其它导出：

```python
from .learning_report import Report
```

完整替换规范入口 `cases/bias_gallery/build_solver.py`，只做工厂与插件接线：

```python
from pathlib import Path
from nsgablack.adapters import NSGA2Adapter
from nsgablack.core import ComposableSolver
from nsgablack.representation import (
    RepresentationPipeline, ClipRepair, UniformInitializer, GaussianMutation,
)
from .problem.example_problem import SphereProblem
from .bias import OWNER, describe, build_bias
from .plugins import Report

def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this learning assembly uses its declared components")
    adapter = NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3))
    solver = ComposableSolver(
        problem=SphereProblem(dimension=2), adapter=adapter,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(-5., 5.)),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.set_bias_module(build_bias(adapter), enable=True)
    solver.add_plugin(Report(adapter, Path(__file__).resolve().parents[2]
                             / "results" / "dynamic_penalty.json", describe=describe, owner_path=OWNER))
    return solver
```


惩罚函数只返回未加权的区域代价。DynamicPenaltyBias 在 compute 内乘调度 scale，Bias 管理层再乘 weight，最终加到选择目标；不要把 .2 或 schedule 在 region_cost 中重复乘。这里显式 max_generations=6，避免假定 Solver 会自动填满 metrics 的所有字段。

调度读取 OptimizationContext.generation（逻辑代数），不是物理尝试数、墙钟时间或不存在的 stage 属性。linear 为 start_scale+(end_scale-start_scale)*min(generation/6,1)；不承诺在本次最后一次送评时恰好用到 end_scale。每行 selection 保留其送评代数的投影，旧成员不会因为后来 scale 增大而自动重新求值/重投影。Problem 的边界 repair 和 raw 反馈继续原语义；区域罚没有新增硬约束，不能把高罚候选叫“被拒绝”。

标准调用链是 Project → Case build_solver → Adapter 提案 → 问题管线修复 → Problem 原始反馈 → 可选 Bias 选择投影 → 接纳 → Adapter 更新/NSGA2 生存选择 → 步骤提交。Report 在 finishing 时只读取最终成员及已评估反馈，在 finalized 后写本地副本，不求值、不构造 Unit、不手动控制事务。Adapter 提交的成员与 accepted 历史不同；Project 的单个 best_solution/best_objectives 是 Solver incumbent，不能代替本报告的成员集合。

**怎样判断接对：** 打开 `results/dynamic_penalty.json`。detail 显示实际调度配置，region_costs 是最终坐标的未加权代价，raw 仍为平方和；它不记录各行送评时的 generation，所以不能用最终 generation 反算每个成员的历史 selection。观察新提案反馈/求值事件才能逐次对账，不能声称所有最终行都使用了最终 scale。所有章节的 refs、tokens、candidates、raw 与 selection 行序应对应；二维 Sphere 的 raw_objectives 每行应为坐标平方和，raw_violations 应为零。selection 是成员当次送评时的选择反馈，不是用最终参考群体重新评分所得；不要在报告阶段重算它来“校正”历史。

**运行入口：** 在该 Project 副本根目录先执行 `python run_project.py --check --build-check`，核对默认组仍是 bias_gallery；再执行 `python run_project.py`。构建检查不会证明评分或收敛。JSON 只在最终成功发布通知后写入，是本地观察文件；核对本轮 run_id，旧文件不代表本轮成功。上面是供用户执行的入口，本轮未运行。

### 变体一：到指定逻辑代数再启用耦合区域偏好

**目的：** 前期完全不加区域罚，达到代数3后一次启用“两个坐标之和至少1”的软偏好，表达有阈值的阶段策略。

**改在哪里：** 在 `bias/learning.py` 完整替换 region_cost 和 build_bias，Report 与 describe 保留：

```python
def region_cost(x):
    return max(0., 1. - float(x[0] + x[1])) ** 2

def build_bias(adapter):
    module = BiasModule()
    module.add(DynamicPenaltyBias(name="region_schedule",
        penalty_func=region_cost, weight=.2, schedule="step",
        start_scale=0., end_scale=1., step_generation=3,
        max_generations=6))
    return module
```

**行为变化：** generation<3 时该项增量为零，达到3后为0.2倍的耦合区域代价；修复和硬接纳仍由原控制面负责。区域定义也由单坐标变为坐标和，不能仅把变体当预算数字调整。

**限制：** 不把它当 Router 阶段切换，不依赖未声明 context.stage。达到阈值前后保留的旧成员仍携带当时反馈；若业务要求所有成员在同一新偏好下竞争，须另行设计正式重评/选择流程，不能改写池内 raw 目标。

源码核对：`bias/domain/dynamic_penalty.py::_schedule_scale/_resolve_max_generations`、`bias/core/base.py::OptimizationContext`、`core/solver_helpers/bias_helpers.py`；正式宿主的 `project_config.py`、`cases/bias_gallery/build_solver.py` 和 `problem/example_problem.py`。这里只给装配及结果检查办法，没有性能或收敛承诺。
