# 连续候选算子：从正式 Case 接上变化与修复

三节各自给出完整操作，分别应用到 `examples/cases/catalog_recipes/` Project 的独立副本，不叠加同名文件。只做静态源码、语法与来源绑定检查，没有执行教程、算法或外部模型。算子处理数值草稿，不拥有候选身份、算法 Unit 或运行循环。

## representation.polynomial_mutation · 有边界连续变量的多项式扰动

**什么时候用：** 希望按变量范围生成连续扰动，而不是固定标准差的高斯噪声。本例仍优化二维 `x0²+x1²`，边界 `[-2,2]`；多项式变异只改变提案，不改变 Problem 的目标含义。

**先准备什么：** 当前 blackbase、nsgablack、NumPy 和现有 `catalog_recipes` Project 副本。保留 `cases/composite/problem/__init__.py::build_problem`（返回 `QuadraticProblem`）、运行入口、Project L0/default 组；该组只运行 composite。原 builder 为两个 NSGA2 直属绑定 GaussianMutation；必须按下文移除，才能消费共享 pipeline 的 PolynomialMutation。

**放在哪：** 本节路径相对该 Project。只替换 `cases/composite/pipeline/main.py` 的 `build_pipeline` 函数，保留其余 `build_unit_binding/run_pipeline_slot`，因此 `pipeline/__init__.py` 的既有导出继续有效。新增报告文件并追加导出，再完整替换 builder。

**接入步骤：** 完整替换 `pipeline/main.py::build_pipeline`：

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, UniformInitializer, PolynomialMutation, ClipRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
        mutator=PolynomialMutation(eta_m=20., mutation_rate=None, low=-2., high=2.),
        repair=ClipRepair(-2., 2.))
```

`mutate(x, context=None)` 输入一行 `(2,)`，返回副本。`mutation_rate=None` 表示每坐标概率 `1/d`，这里为 1/2；不保证每个孩子都有坐标改变。`eta_m` 控制扰动分布，不是步长或种群数量。显式 low/high 提供范围，无需从轻量 context 猜 Problem。

新增完整 `cases/composite/plugins/operator_report.py`：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class OperatorReport(Plugin):
    def __init__(self, owners, path):
        super().__init__("operator_report")
        self.owners, self.path = tuple(owners), Path(path)

    def on_solver_finish(self, result):
        control, rows = self.solver, []
        for owner in self.owners:
            refs = owner.get_population_solution_refs(control)
            batch = control.read_solutions(refs)
            raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
            rows.append(dict(name=owner.name, refs=[r.as_dict() for r in refs],
                candidates=batch.numeric_matrix.tolist(),
                raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist()))
        self.payload = dict(run_id=control.run_session.run_id, members=rows)

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

在 `plugins/__init__.py` 末尾追加，保留原内容：

```python
from .operator_report import OperatorReport
```

完整替换 `cases/composite/build_solver.py`：

```python
from pathlib import Path
from nsgablack.adapters import CompositeAdapter, NSGA2Adapter
from nsgablack.project.starter import build_starter_solver
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins import OperatorReport

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this learning Case uses explicit components")
    a = NSGA2Adapter(name="a", population_size=4, offspring_size=4)
    b = NSGA2Adapter(name="b", population_size=4, offspring_size=4)
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
        resource_context=resource_context, max_steps=4,
        component_overrides={"adapter": CompositeAdapter(adapters=[a, b])})
    solver.set_random_seed(37)
    solver.add_plugin(OperatorReport((a, b),
        Path(__file__).resolve().parent / "results" / "operators.json"))
    return solver
```

父代来自各 NSGA2 自己的已评估成员；原生路径先按 crossover_rate 做算术交叉或复制父代，再调用 pipeline 的多项式变异。两个实例共享同一算子和随机流，不表示独立随机实验；它们的 Unit/成员仍独立。没有完整 change 或直属 mutator 抢走该消费位置。

变异内部 clip 是这个算子的数值行为，不替代独立 ProblemRepair。正常新提案由 Solver 先裁预算，再调用一次 pipeline repair，通知原 Adapter 对账，随后送评/接纳/update；不要在变异或 propose 再手动 repair。初始化的 `pipeline.init` 自带修复属于初始化阶段，不能据此声称整次运行只调用一次修复。

**怎样判断接对：** 本次 `cases/composite/results/operators.json` 的两个 members 分别对应 a/b，各有四个二维最终成员；raw_objectives 为一列，逐行等于平方和，raw_violations 为零，坐标在边界内。概率变异可以原样返回，不能靠“每行都变了”验收。refs 保留真实版本/顺序，不按数值去重。它们不是 accepted 历史，也不是 Solver 的单个 best。报告在结束时复制已提交值、最终发布后写本地 JSON；须核对本轮 run_id 与 Project 收据。

**运行入口：** 从仓库根目录执行，使用副本时替换路径：

```powershell
python examples/cases/catalog_recipes/run_project.py --group default --check --build-check
python examples/cases/catalog_recipes/run_project.py --group default
```

第一条只构造检查；第二条才运行。builder 只挂载组件，观察器不会为读取而创建 Unit。

### 变体一：两个算法选择不同变化，共享同一问题修复

**目的：** 一个种群用多项式变化，另一个保留高斯变化，比较两类探索方式而不复制 Problem/Pipeline。

**改在哪里：** 完整替换同一 `build_pipeline` 函数：

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, UniformInitializer, PolynomialMutation,
        GaussianMutation, ClipRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
        mutation_operators={
            "polynomial": PolynomialMutation(low=-2., high=2.),
            "gaussian": GaussianMutation(sigma=.2, low=-2., high=2.),
        }, repair=ClipRepair(-2., 2.))
```

在上文 builder 创建 a/b 后、构造 Composite 前插入：

```python
a.set_mutation_operator("polynomial")
b.set_mutation_operator("gaussian")
```

**行为变化：** 真实叶 Adapter 选择注册名称，分别消费两个独立算子；共享 initializer 和独立问题修复阶段不变。原生交叉仍在各自变异之前。

**限制：** 名称不会自动广播到子 Adapter。未指定算子时本变体没有默认 mutator，会报错；不能同时给 a/b 再绑定直属 mutator 或完整 change。报告依然分种群比较，不能据一次随机输出宣称某分布更优。

源码：`representation/continuous.py::PolynomialMutation`、`representation/base.py::mutate`、`adapters/nsga2/adapter.py::propose`、`core/composable_solver.py`。

## representation.sbx_crossover · 先重组双亲，再对孩子变异

**什么时候用：** 连续向量的两个父代要共同产生新候选，期望使用 SBX 的重组分布。`crossover(parent1, parent2, context=None)` 返回两个一维孩子，不能把它当作 `mutate(x, context)`。

**先准备什么：** 使用当前 blackbase、nsgablack、NumPy 和独立的 `examples/cases/catalog_recipes/` 副本。保留 composite 的二维平方和 Problem、Project L0/default 组、Case 运行入口。原 default 组只运行 composite。此节按下文替换 builder，移除原两个直属 Gaussian mutator，改由共享 pipeline 提供变化。

**放在哪：** 以下路径均相对该 Project。替换 `cases/composite/pipeline/main.py::build_pipeline`，保留该文件其它函数和 `pipeline/__init__.py` 导出。新增本节报告插件、追加包导出，再完整替换 builder。

**接入步骤：** 完整替换 `build_pipeline`：

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, UniformInitializer, SBXCrossover,
        GaussianMutation, ClipRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
        crossover=SBXCrossover(eta_c=15., low=-2., high=2.),
        mutator=GaussianMutation(sigma=.1, low=-2., high=2.),
        repair=ClipRepair(-2., 2.))
```

新增完整 `cases/composite/plugins/operator_report.py`：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class OperatorReport(Plugin):
    def __init__(self, owners, path):
        super().__init__("operator_report")
        self.owners, self.path = tuple(owners), Path(path)

    def on_solver_finish(self, result):
        control, rows = self.solver, []
        for owner in self.owners:
            refs = owner.get_population_solution_refs(control)
            batch = control.read_solutions(refs)
            raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
            rows.append(dict(name=owner.name, refs=[r.as_dict() for r in refs],
                candidates=batch.numeric_matrix.tolist(),
                raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist()))
        self.payload = dict(run_id=control.run_session.run_id, members=rows)

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

在 `plugins/__init__.py` 末尾追加，保留原内容：

```python
from .operator_report import OperatorReport
```

完整替换 `cases/composite/build_solver.py`：

```python
from pathlib import Path
from nsgablack.adapters import CompositeAdapter, NSGA2Adapter
from nsgablack.project.starter import build_starter_solver
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins import OperatorReport

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this learning Case uses explicit components")
    a = NSGA2Adapter(name="a", population_size=4, offspring_size=4, crossover_rate=1.)
    b = NSGA2Adapter(name="b", population_size=4, offspring_size=4, crossover_rate=1.)
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
        resource_context=resource_context, max_steps=4,
        component_overrides={"adapter": CompositeAdapter(adapters=[a, b])})
    solver.set_random_seed(37)
    solver.add_plugin(OperatorReport((a, b),
        Path(__file__).resolve().parent / "results" / "operators.json"))
    return solver
```

NSGA2 从自己的成员选双亲，原生 `_crossover` 调用 pipeline.crossover；本例 rate=1 确保进入 SBX。虽然 SBX 返回两个孩子，该原生消费点随机选其中一个，再调用 GaussianMutation，组成一个后代槽。每个实例每次最多四个后代，不因交叉返回两行就自动翻倍。

交叉先重组父代信息，变异再扰动孩子；把变异提前到双亲上，会改变孩子的生成分布。SBX 自身可 clip 到指定边界，Gaussian 也可 clip；这些不是独立 ProblemRepair 调度。普通新提案在预算裁剪后由 Solver 单独 repair 一次，再对账、求值、接纳；不要在交叉函数手动送评或再修复。`pipeline.init` 的初始化修复另属初始化阶段。

**怎样判断接对：** 查看本次 `cases/composite/results/operators.json`：a/b 各有四个二维最终成员，目标一列且等于平方和、原始违反量为零、坐标在 `[-2,2]`。report 读取工厂保留的真实 owner，两个种群不合并排名。最终成员不等于全部后代，也不等于单个 Solver incumbent；随机结果不能证明 SBX 比算术交叉更好。JSON 是结束时复制并在最终发布后写出的观察副本，核对新 run_id，不能拿旧文件证明已跑新算子。

**运行入口：** 仓库根目录，副本则替换路径：

```powershell
python examples/cases/catalog_recipes/run_project.py --group default --check --build-check
python examples/cases/catalog_recipes/run_project.py --group default
```

### 变体一：同一对父代产生并交付两个独立孩子

**目的：** 复用一次 SBX 计算，保留两个孩子各自变异后的提案，而不是在原生消费点丢掉一个。

**改在哪里：** 新增完整 `cases/composite/adapter/paired_sbx.py`：

```python
from nsgablack.adapters import ChangeBatchResult, ChangeResult
from nsgablack.representation import RepresentationPipeline, SBXCrossover, GaussianMutation

def paired_sbx(request, *, rng):
    if len(request.parents) != 2 or len(request.source_refs) != 2:
        raise ValueError("this change needs two exactly identified parents")
    operators = RepresentationPipeline(
        crossover=SBXCrossover(low=-2., high=2.),
        mutator=GaussianMutation(sigma=.1, low=-2., high=2.))
    operators.set_random_seed(int(rng.integers(0, 2**63 - 1)))
    context = dict(request.context)
    first, second = operators.crossover.crossover(*request.parents, context)
    return ChangeBatchResult(results=tuple(
        ChangeResult(operators.mutate(child, context), source_refs=request.source_refs)
        for child in (first, second)[:min(2, request.max_outputs)]))
```

在 builder 创建 a/b 后、构造 Composite 前插入：

```python
from .adapter.paired_sbx import paired_sbx
a.set_change(paired_sbx)
b.set_change(paired_sbx)
```

**行为变化：** 完整 change 接管原生交叉和变异，旧 pipeline 的这两项不再叠加；仍复用其初始化和独立 repair。request 的双亲与精确来源由 NSGA2 提供，剩余后代许可为 max_outputs；最后一次调用可只交一个孩子。局部算子的随机种子来自所属 Adapter 提供的 rng，没有捕获跨调用可变算子。

**限制：** ChangeBatchResult/ChangeResult 保留逐孩子身份与父来源，不返回裸二维矩阵。每实例 offspring_size 仍为四，成对产出不增加该预算。新孩子仍须正常修复和评估，不共享父代反馈。局部构造算子有开销，没有速度或性能保证；改变函数身份后用新运行，不套旧 checkpoint。

源码：`representation/continuous.py::SBXCrossover`、`representation/base.py::set_random_seed/mutate`、`adapters/nsga2/adapter.py::_crossover/_propose_changes`、`adapters/change_batch.py`。

## representation.parallel_repair · 有限资源内批量执行问题修复

**什么时候用：** 同批多个候选需要独立、无共享副作用的修复，希望将每行工作交给有限线程。本例先用 ClipRepair 展示接线；二维 clip 很便宜，线程调度可能更慢，不能据此承诺加速。

**先准备什么：** 当前 blackbase、nsgablack、NumPy；使用独立的 `examples/cases/catalog_recipes/` Project 副本。保留 composite 的平方和 Problem、Case/Project 运行薄入口和原 L0。下面把这个 Case 的资源请求改为两线程，不能仅在修复器里增加 worker 绕过 Project 授权。

**放在哪：** 替换 `cases/composite/pipeline/main.py::build_pipeline`，其它函数及包导出保留；新增独立报告插件、追加其导出，再替换 builder。在原 `project_config.py` 末尾调整既有 stage_1 的 composite 请求，不创建另一个 Project。

**接入步骤：** 在 `project_config.py` 的 STAGES/GROUPS 定义之后追加。原 L0 offer 已有四线程；这里只申请两线程，默认组仍只运行 composite：

```python
STAGES[0]["resource_requests"]["composite"] = dict(threads=2, gpus=0, backend="local")
```

完整替换 `pipeline/main.py::build_pipeline`：

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, UniformInitializer, GaussianMutation,
        ClipRepair, ParallelRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(initializer=UniformInitializer(-2., 2.),
        mutator=GaussianMutation(sigma=.3),
        repair=ParallelRepair(ClipRepair(-2., 2.), backend="thread",
            max_workers=2, min_batch_size=4, strict=True))
```

内层 Gaussian 不 clip，独立修复负责边界。ParallelRepair 的单点 `repair(candidate, context)` 直接调用 inner；`repair_batch(candidates, contexts=...)` 保持输入行序，contexts 数量必须匹配。小于四行时串行；四行及以上最多两个线程。这里不写共享 context，`report_errors_to_context=False` 保持默认，避免未注册的大错误列表进入共享命名空间。

新增完整 `cases/composite/plugins/operator_report.py`：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class OperatorReport(Plugin):
    def __init__(self, owners, repair, path):
        super().__init__("operator_report")
        self.owners, self.repair, self.path = tuple(owners), repair, Path(path)

    def on_solver_finish(self, result):
        control, rows = self.solver, []
        for owner in self.owners:
            refs = owner.get_population_solution_refs(control)
            batch = control.read_solutions(refs)
            raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
            rows.append(dict(name=owner.name, refs=[r.as_dict() for r in refs],
                candidates=batch.numeric_matrix.tolist(),
                raw_objectives=raw_f.tolist(), raw_violations=raw_v.tolist()))
        self.payload = dict(run_id=control.run_session.run_id, members=rows,
                            last_batch_errors=list(self.repair.last_batch_errors))

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

在 `plugins/__init__.py` 末尾追加，保留原内容：

```python
from .operator_report import OperatorReport
```

完整替换 `cases/composite/build_solver.py`：

```python
from pathlib import Path
from nsgablack.adapters import CompositeAdapter, NSGA2Adapter
from nsgablack.project.starter import build_starter_solver
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins import OperatorReport

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this learning Case uses explicit components")
    pipeline = build_pipeline()
    a = NSGA2Adapter(name="a", population_size=4, offspring_size=4)
    b = NSGA2Adapter(name="b", population_size=4, offspring_size=4)
    solver = build_starter_solver(problem=build_problem(), pipeline=pipeline,
        resource_context=resource_context, max_steps=4,
        component_overrides={"adapter": CompositeAdapter(adapters=[a, b])})
    solver.set_random_seed(37)
    solver.add_plugin(OperatorReport((a, b), pipeline.problem_repair,
        Path(__file__).resolve().parent / "results" / "operators.json"))
    return solver
```

正常每轮 Composite 拼接两个实例提案，由 Solver 裁剪预算，再通过 pipeline.repair_batch 调用此 wrapper；修复后的候选沿原提案映射对账，再求值/接纳/update。提案阶段不另加 repair 调用，也不把 ParallelRepair 放到 mutator 槽。初始化 `pipeline.init` 自带的单点修复另属初始化过程，不是并行批次。

**怎样判断接对：** 构造检查应显示两线程资源上下文，不能把 max_workers 当授权。本次 `cases/composite/results/operators.json` 中 a/b 各四个最终成员、每行二维且在边界内，raw_objectives 一列为平方和、raw_violations 为零。`last_batch_errors` 只表示最近一次非空 repair_batch 的错误记录，不是整次运行的错误总数或并行次数。strict=True 的线程修复失败会抛错，不改成原候选成功送评；小批串行错误同样传播。未成功最终发布时不得拿旧 JSON 证明成功。成员与 accepted 历史、Solver 单点 best 分开。

**运行入口：** 仓库根目录，副本则替换路径：

```powershell
python examples/cases/catalog_recipes/run_project.py --group default --check --build-check
python examples/cases/catalog_recipes/run_project.py --group default
```

只通过 Project 执行以取得授权；单独调用 Case builder 并不会给线程池发放资源。wrapper 不自动读取或申请 L0，必须维持 worker 不超过本例有效授权。线程实现要求 inner 对共享使用安全；不借此并行执行 Adapter 或 Problem 求值。

### 变体一：把盒约束改为总和为一的非负权重

**目的：** 搜索两个分配权重，要求每项非负、总和为一；仅 clip 不能修复这个耦合约束。

**改在哪里：** 完整替换 `cases/composite/problem/__init__.py`，保留同名 build_problem 导出：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem

class WeightProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="weights", dimension=2,
            bounds=[(0., 1.), (0., 1.)], objectives=["min"])

    def evaluate(self, candidate):
        return float(np.sum(np.asarray(candidate, dtype=float) ** 2))

    def evaluate_constraints(self, candidate):
        x = np.asarray(candidate, dtype=float)
        return np.concatenate((-x, x - 1., [abs(float(np.sum(x)) - 1.) - 1e-8]))

def build_problem():
    return WeightProblem()
```

并完整替换同一 `build_pipeline` 函数，报告与 builder 不变：

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, UniformInitializer, GaussianMutation,
        ProjectionRepair, ParallelRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(initializer=UniformInitializer(0., 1.),
        mutator=GaussianMutation(sigma=.3),
        repair=ParallelRepair(ProjectionRepair(sum_target=1., low=0., high=1.),
            backend="thread", max_workers=2, min_batch_size=4, strict=True))
```

**行为变化：** 同一批量入口调用单纯形投影，Problem 同时声明真实约束；结果每行总和应接近 1，原始违反量按 `g<=0` 满足、正部累加计算。raw_objectives 仍为平方和，不为了可行性把目标重写。

**限制：** 该 ProjectionRepair 在本例纯数值、无副作用，可共享线程；其它 inner 的线程安全须另查。这里没有 JointRepairPolicy/UnitRepair，不宣称 wrapper 具备联合修复 validator。`backend="process"` 另需 inner 与候选/context 可序列化；不能只改字符串就保证进程池可用，也不承诺并行更快。

源码：`representation/base.py::ParallelRepair/repair_batch`、`representation/continuous.py::ProjectionRepair`、`core/base.py::evaluate_constraints`、`core/joint_repair.py::repair_problem_batch`。
