# 进化搜索：从独立种群、差分替换到分布和分格档案

本书按当前 Catalog key 与源码编写。每章独立使用，不要求先完成上一章；代码是供用户放进正式 Project/Case 的完整替换片段，本轮没有执行这些装配、算法或命令。问题反馈、算法最终成员、Solver incumbent 与历史接纳记录分别核对，不以数值相同猜候选身份。

## adapter.nsga3 · 三个目标之间保留不同折中方向

**什么时候用：** 两个连续决策变量要同时靠近三个不同位置，希望保留一组折中解，而非只看三个距离的总和。这里用三个平方距离演示 NSGA3 的非支配前沿填充与末层参考方向生态位选择；不是精确求解或覆盖保证。

**先准备什么：** 安装当前 nsgablack、blackbase 与 NumPy。在 nsgablack 仓库根目录创建新的标准 Project；这些命令使用当前 `new/add-case` 参数，`add-case` 会把唯一的 search Case 加入默认组并声明资源请求：

```powershell
python -m nsgablack project new examples/cases/nsga3_application
cd examples/cases/nsga3_application
python -m nsgablack project add-case search --type solver --framework nsgablack
```

这采用现有 `assembled_parallel_cases/de_bowl` 的 Problem、Adapter、Pipeline、builder 分工。原生 NSGA3 池组合另见 `examples/cases/solution_pool/cases/pool_search/adapter/pool_example.py`；不把那个单目标池例子的旧结果当作本节三目标结果。

**放在哪：** 以下路径均相对新 Project。替换所列文件，保留脚手架生成的 `project_config.py`、`run_project.py`、Case 的运行薄入口和其余包标记。资源授权来自 Project，不能自行构造 grant。

**接入步骤：** 先写完整问题工厂 `cases/search/problem/__init__.py`：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array

class ThreeCenters(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="three_centers", dimension=2,
            bounds=[(-4., 4.)] * 2, objectives=["origin", "right", "up"])

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        centers = np.array([[0., 0.], [2., 0.], [0., 2.]])
        return np.sum((centers - x) ** 2, axis=1)

def build_problem():
    return ThreeCenters()
```

`cases/search/pipeline/__init__.py` 只处理问题边界：

```python
from nsgablack.representation import RepresentationPipeline, ClipRepair

def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-4., 4.))
```

`cases/search/adapter/__init__.py`：

```python
from nsgablack.adapters import NSGA3Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation

def build_adapter():
    return NSGA3Adapter(population_size=12, offspring_size=12, divisions=3,
        initializer=UniformInitializer(-4., 4.),
        mutator=GaussianMutation(sigma=.2))
```

为取得本次正式成员而非根池历史，新增完整观察器 `cases/search/plugins/members.py`：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class MemberReport(Plugin):
    def __init__(self, path):
        super().__init__("member_report")
        self.path = Path(path)

    def on_solver_finish(self, result):
        control = self.solver
        refs = control.adapter.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        f, v = control.solution_pool.read_raw_feedback(refs)
        self.payload = dict(run_id=control.run_session.run_id,
            refs=[ref.as_dict() for ref in refs],
            candidates=batch.numeric_matrix.tolist(),
            raw_objectives=f.tolist(), raw_violations=v.tolist())

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

最后替换规范入口 `cases/search/build_solver.py`；它实际调用以上四个模块：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins.members import MemberReport

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    solver = ComposableSolver(problem=build_problem(),
        representation_pipeline=build_pipeline(), adapter=build_adapter(),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(int(options.get("seed", 17)))
    solver.set_max_steps(int(options.get("max_steps", 6)))
    solver.add_plugin(MemberReport(Path(__file__).resolve().parents[2]
                                   / "results" / "members.json"))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

首次提案通过显式 initializer 建立已评估成员，后续交叉/变化产生新候选；问题管线修复、Solver 求值与接纳后，NSGA3 合并旧成员和新反馈做生存选择。`divisions` 用于参考方向；它不是种群容量。普通 population 视图只有提交后可读，accepted 只是接纳历史。

**怎样判断接对：** 本次成功结束后看 `results/members.json`：refs、candidates、raw_objectives、raw_violations 行序对应，完整默认预算下应有 12 个二维成员、每行 3 个原始目标。每行目标应符合三个距离定义；文件是本地观察副本，要核对本轮 run_id，不用旧文件证明新运行。Project 的单个 `best_solution/best_objectives` 是 Solver incumbent，有自己的标量比较，不能代替参考方向选出的成员集合或证明前沿覆盖。观察器不调用 Problem，不重抽候选。

**运行入口：** 在新 Project 根目录执行 `python run_project.py --check --build-check`，检查实际 Adapter 为 NSGA3Adapter；再执行 `python run_project.py`。网页或文档展示命令不代表已执行。结果文件只在最终成功发布通知后写入。

### 变体一：一次交叉交付两个有独立来源的孩子

**目的：** 对同一对父代只生成一次交叉掩码，产生互补孩子，保留每个孩子的来源和剩余后代许可。

**改在哪里：** 完整替换新 Project 的 `cases/search/adapter/__init__.py`：

```python
import numpy as np
from nsgablack.adapters import NSGA3Adapter, ChangeBatchResult, ChangeResult
from nsgablack.representation import UniformInitializer

def paired_change(request, *, rng):
    if len(request.parents) != 2 or len(request.source_refs) != 2:
        raise ValueError("this crossover requires two exact parents")
    a, b = request.parents
    mask = rng.random(a.shape) < .5
    children = (np.where(mask, a, b), np.where(mask, b, a))
    return ChangeBatchResult(results=tuple(
        ChangeResult(child + rng.normal(0., .2, child.shape),
                     source_refs=request.source_refs)
        for child in children[:min(2, request.max_outputs)]))

def build_adapter():
    return NSGA3Adapter(population_size=12, offspring_size=12, divisions=3,
        initializer=UniformInitializer(-4., 4.), change=paired_change)
```

**行为变化：** `change` 接管完整变化，不再叠加基线 GaussianMutation 或默认交叉。两个孩子分别生成提案身份，统一经过原修复、送评和接纳；最后一对可因 max_outputs 只交一名。参考方向 survivor 仍由 NSGA3 决定。

**限制：** 不自行 repair/evaluate，不把二维矩阵直接当批返回。`source_refs` 不是数值相等推导出的身份。修改代码后旧 checkpoint 的函数身份不兼容，使用新运行；没有性能改进或收敛证明。依据为 `adapters/nsga3/adapter.py`、`nsga2/adapter.py` 和 `change_batch.py`。

## adapter.spea2 · 用强度与密度维持双目标折中成员

**什么时候用：** 两个二维距离目标互相冲突，希望比较强度适应度与密度截断产生的成员分布。这里保留 SPEA2 的实际环境选择；不要把它等同于把目标相加后取最小。

**先准备什么：** 当前 nsgablack、blackbase、NumPy。以下独立创建新 Project，不复用上一章目录：

```powershell
python -m nsgablack project new examples/cases/spea2_application
cd examples/cases/spea2_application
python -m nsgablack project add-case search --type solver --framework nsgablack
```

现有正式组合可参考 `examples/cases/assembled_pool_recovery/cases/pool_recovery/adapter/composition.py` 中的 SPEA2 实例。本节是独立双目标装配，不沿用该平坦问题/池恢复示例的旧结果。保留生成器的 Project L0、默认组和 Case 运行入口。

**放在哪：** 新 Project 中下列五个文件。直接导入所给工厂，不依赖未展示的前一章节对象。

**接入步骤：** `cases/search/problem/__init__.py`：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem
from nsgablack.units.contracts import candidate_array

class TwoCenters(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="two_centers", dimension=2,
            objectives=["left", "right"], bounds=[(-4., 4.)] * 2)

    def evaluate(self, candidate):
        x = candidate_array(candidate)
        return [float(np.sum(x ** 2)), float(np.sum((x - [2., 0.]) ** 2))]

def build_problem():
    return TwoCenters()
```

`cases/search/pipeline/__init__.py`：

```python
from nsgablack.representation import RepresentationPipeline, ClipRepair

def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(-4., 4.))
```

`cases/search/adapter/__init__.py`：

```python
from nsgablack.adapters import SPEA2Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation

def build_adapter():
    return SPEA2Adapter(population_size=12, offspring_size=12, k_nearest=1,
        initializer=UniformInitializer(-4., 4.),
        mutator=GaussianMutation(sigma=.2))
```

`cases/search/plugins/members.py` 只观察已选成员，不做第二次选择：

```python
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class MemberReport(Plugin):
    def __init__(self, path):
        super().__init__("member_report")
        self.path = Path(path)

    def on_solver_finish(self, result):
        control = self.solver
        refs = control.adapter.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        f, v = control.solution_pool.read_raw_feedback(refs)
        self.payload = dict(run_id=control.run_session.run_id,
            refs=[ref.as_dict() for ref in refs], candidates=batch.numeric_matrix.tolist(),
            raw_objectives=f.tolist(), raw_violations=v.tolist())
        history = (control.solution_pool.subpool_refs("spea_history")
                   if control.solution_pool.has_subpool("spea_history") else ())
        self.payload["history_refs"] = [ref.as_dict() for ref in history]

    def on_solver_finalized(self, result):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

规范入口 `cases/search/build_solver.py`：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .problem import build_problem
from .pipeline import build_pipeline
from .adapter import build_adapter
from .plugins.members import MemberReport

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    solver = ComposableSolver(problem=build_problem(),
        representation_pipeline=build_pipeline(), adapter=build_adapter(),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True)
    solver.set_random_seed(int(options.get("seed", 23)))
    solver.set_max_steps(int(options.get("max_steps", 6)))
    solver.add_plugin(MemberReport(Path(__file__).resolve().parents[2]
                                   / "results" / "members.json"))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

显式初始化先送评，之后保留父代与提案的精确引用；继承的 NSGA 更新合并成员，SPEA2 用强度、被支配者强度和近邻密度选择，超额非支配成员按近邻距离截断。问题 raw feedback 保存在解池；算法消费选择反馈。当前无 Bias，两者数值相同也不能用数值相等代替引用对齐。

**怎样判断接对：** 本次 `results/members.json` 中默认完整预算应有 12 行二维候选、12 行双目标反馈；refs 逐行标识最终成员。`population_size` 是实际容量：当前 `SPEA2Config.archive_size` 虽有声明，源码环境选择没有用它控制另一份档案，不能据此声称已经建立独立 archive。Solver incumbent 是单独比较的已评估代表，不是 SPEA2 全部成员；根 accepted 还含被环境选择淘汰的提案。本地报告要核对本轮 run_id，不是权威 Artifact 收据。

**运行入口：** 在该新 Project 根目录先用 `python run_project.py --check --build-check` 核对 SPEA2Adapter，再用 `python run_project.py`。报告由 finish 阶段捕获已提交成员，最终成功后才写文件；本书未运行。

### 变体一：保持 SPEA2 选择，另存曾入选成员的折中档案

**目的：** 下游想保留跨代曾成为正式成员的候选，而不是收集所有硬接纳但随后淘汰的试探。

**改在哪里：** 完整替换本章 `cases/search/adapter/__init__.py`；builder 的原 `build_adapter()` 调用不变：

```python
import numpy as np
from nsgablack.adapters import SPEA2Adapter, Pool
from nsgablack.representation import UniformInitializer, GaussianMutation

def archive_key(pool):
    f, v = pool.raw_feedback()
    return np.column_stack((v > 0., np.maximum(v, 0.), np.sum(f, axis=1)))

def maintain_members(request, *, rng):
    if request.members is None:
        raise ValueError("this archive requires final population members")
    names = request.pool.describe()["subpools"]
    old = (request.pool.subpool("spea_history") if "spea_history" in names
           else request.members.take(()))
    kept = old.merge(request.members).chosen(
        lambda offered: offered.top(12, key=archive_key), rng=rng)
    Pool(parent=request.pool, name="spea_history").inject(kept, replace=True)

def build_adapter():
    return SPEA2Adapter(population_size=12, offspring_size=12, k_nearest=1,
        initializer=UniformInitializer(-4., 4.), mutator=GaussianMutation(sigma=.2),
        pool_maintenance=maintain_members)
```

**行为变化：** 维护发生在实际叶 update 完成成员选择后；合并的是 request.members，不是 request.accepted。历史按精确版本去重，按本例 raw 可行性、违反量、目标和保留至多 12 项，随原步骤事务提交；不改变 SPEA2 的 strength/density survivor。

**限制：** 这是显式总和折中档案，不是额外 Pareto 档案。本章 MemberReport 在真实 solver 仍存活时读取提交后的 `spea_history`，写入同一 `members.json` 的 history_refs；与当前成员 refs 分开，不保留活 request/Pool，也不在 CLI 退出后凭空访问旧 solver。若后来放入受限 PoolTask，还须声明准确 `change_sources=("spea_history",)` 读取旧档案。依据为 `spea2/adapter.py`、`nsga2/adapter.py` 与 `pool_maintenance.py`。

## adapter.de · 对提案时目标槽位做差分 trial 替换

**什么时候用：** 二维连续变量最小化 `(x0-1)^2+(x1+2)^2`，需要保持差分供体、二项交叉与目标槽位比较，而不是让全体候选做一次 GA survivor。

**先准备什么：** 使用现有 `examples/cases/assembled_parallel_cases` Project 的 `cases/de_bowl`。已有二维 BowlProblem、`[-4,4]` ClipRepair 与唯一 builder；config.py 为 seed=17、population_size=12、batch_size=12、max_steps=16。保留这套配置，标准 Project 默认还会并行运行独立的 sa_valley，它不与 DE 交换解。

**放在哪：** 完整替换 `cases/de_bowl/adapter/search.py`。其 `adapter/__init__.py` 已导出 build_adapter，原 build_solver 已调用它，无需新增运行循环：

**接入步骤：**

```python
from nsgablack.adapters import DifferentialEvolutionAdapter, DEConfig
from nsgablack.representation import UniformInitializer
from ..config import POPULATION_SIZE, BATCH_SIZE

def build_adapter():
    return DifferentialEvolutionAdapter(name="de_bowl",
        initializer=UniformInitializer(-4., 4.),
        config=DEConfig(population_size=POPULATION_SIZE, batch_size=BATCH_SIZE,
            differential_weight=.7, crossover_rate=.9,
            strategy="rand1bin", objective_aggregation="sum"))
```

第一批是初始化候选，经正式修复、评估和接纳建立已有反馈的种群。后续每个 trial 冻结一个提案时目标槽位及其比较分数；差分供体与交叉先生成 trial，问题 repair 再修边界。Solver 统一送评/接纳，DE 才用反馈决定替换。batch 内目标索引允许重复，比较基准仍是提案时状态，不能用前一个 trial 的胜出结果偷换后一个基准；同槽多行更新按原批次顺序处理。

**怎样判断接对：** 原 `run_and_report.py` 使用正式 execute_project，写 `results/project_result.json`、`summary.json` 和 `results/cases/de_bowl.json`，其中 best_candidate/best_objectives 是 Solver incumbent 及解析重算核对，不是完整 DE 种群。默认无额外截断时可按“首次 12 个初始化 + 后续每步 12 个 trial”核对求值预算；不预填随机最优值。需要当前成员时，在本次运行仍保留的 solver 或既有观察回调内读 `solver.adapter.get_population_solution_refs(solver)`，再用 `solver.solution_pool.read_raw_feedback(refs)` 和 `solver.read_solutions(refs)`；CLI 退出后不能凭空取得那个 solver。根 accepted 是历史，包含未赢过目标槽位的已接纳 trial。检查同次 run_id，旧 RESULTS.md 不证明改动后运行。

**运行入口：** 在 nsgablack 根目录执行 `python examples/cases/assembled_parallel_cases/run_project.py --check --build-check`；正式运行可用原 `python examples/cases/assembled_parallel_cases/run_and_report.py`，它会运行两个原 Case 并保存本次报告。只查看已有同次结果可加 `--report-only`；不能用它制造新运行证据。本书均未执行。

### 变体一：相等分数时保留原目标，不漂移到 trial

**目的：** 对平台值或离散化反馈，要求严格改善才替换目标。默认 DE 使用 trial_score <= frozen_target_score，相等时也可能换候选身份。

**改在哪里：** 完整替换同一 `adapter/search.py`：

```python
from nsgablack.adapters import DifferentialEvolutionAdapter, DEConfig
from nsgablack.representation import UniformInitializer
from ..config import POPULATION_SIZE, BATCH_SIZE

class StrictReplacement:
    stateless = True

    def checkpoint_identity(self):
        return {"schema": "example.strict_de_replacement/v1"}

    def select(self, request, *, rng):
        if request.purpose != "replacement" or request.count != 1:
            raise ValueError("this policy only selects a target/trial pair")
        if request.scores is None or len(request.scores) != 2:
            raise ValueError("proposal-time comparison scores are required")
        return [1 if request.scores[1] < request.scores[0] else 0]

def build_adapter():
    return DifferentialEvolutionAdapter(name="de_bowl",
        initializer=UniformInitializer(-4., 4.), selector=StrictReplacement(),
        config=DEConfig(population_size=POPULATION_SIZE, batch_size=BATCH_SIZE,
            differential_weight=.7, crossover_rate=.9,
            strategy="rand1bin", objective_aggregation="sum"))
```

**行为变化：** 每次请求仅比较两行：0 为冻结目标，1 为已评估 trial。返回局部索引，保留提案时分数，不能返回全局种群下标；不改变差分/交叉或初始化容量。它使用 DE 提供的 sum+违反量罚分，不声称是独立 Pareto 或可行性优先规则。

**限制：** 只有平分处理不同，不保证更快；即使 trial 未替换槽位，真实评估和 accepted 仍已发生。此规则不能替代 NSGA 的 survivor；也不能据 Adapter 的 objective_aggregation 推断 Solver incumbent 政策相同。依据为 `adapters/differential_evolution/adapter.py` 的 propose/update/_scores 与 `adapters/selection.py`。

## adapter.cmaes · 整批观测后更新均值、协方差和步长

**什么时候用：** 连续、无约束的单个原始目标，需要根据整批采样的相对好坏自适应搜索分布。这里是二维平方距离 `(x0-.2)^2+(x1+.1)^2`；分布参数不是一组已评估种群成员。

**先准备什么：** 使用现有 `examples/cases/algorithm_semantics/cases/cmaes_distribution`，Project 有独立组 cmaes_distribution。默认 CMASettings 为 seed=19、max_steps=3、fixture=None、evaluation_budget=None；Problem 为二维，pipeline 是 identity，不做 clip。原 builder 已装配 CheckpointResumePlugin 与 DistributionReport，资源来自 Project L0。这里不添加 Bias/约束或 PoolTask。

**放在哪：** 完整保留或替换该 Case 的 `adapter/__init__.py`。原 build_solver 实际调用 build_adapter(settings)，并依 fixture 同步选择 Problem 维度。

**接入步骤：**

```python
from nsgablack.adapters.cmaes import CMAESAdapter, CMAParameters, GaussianCohortSampler

def build_adapter(settings):
    scalar = settings.fixture == "scalar"
    fixed = ([[[-1.], [0.], [1.], [2.]]] if scalar else
             [[[-1., 0.], [0., 1.], [1., 0.], [0., -1.]]]
             if settings.fixture == "matrix" else ())
    parameters = (CMAParameters(weights=(.5, .5), cc=.5, cs=.5,
        c1=.25, cmu=.25, damping=1.) if scalar else CMAParameters())
    return CMAESAdapter([0.] if scalar else [0., 0.],
        sigma=1. if scalar else .5, parameters=parameters,
        sampler=GaussianCohortSampler(settings.seed, fixed_batches=fixed))
```

默认参数 lambda=4、重组父代数 mu=2，属于 CMAParameters；不要写成 CMAESAdapter(population_size=...)。sampler 先产生标准正态 cohort，Adapter 用当前均值/协方差/步长变换为候选；四个真实反馈齐全后，ranking 按 raw 单目标稳定排序，正权重更新分布。均值可能未被单独求值，不能作为 best_solution 交付。候选改变的 repair 会在送评前拒绝；预算裁成残批或接纳缺行也拒绝，不会把 lambda 静默缩小，已消耗求值成本仍保留。

**怎样判断接对：** 本次 `algorithm_semantics/results/cmaes_distribution/summary.json` 有 run_id、evaluations、logical_steps、mean、covariance、sigma、path_c、path_sigma、iteration、cohort_count、selected_indices、best_objective、best_candidate。cohort_count 表示最近整批观测；selected_indices 是重组父代位置；mean 是下一分布中心；best_candidate 是实际评估过的最佳点。这四者不可混成最终 population。正式 Case 还发布 summary Artifact，本地 JSON 只是观察副本；按同次运行身份及发布收据核对，不以旧文件证明已跑新配置。Solver incumbent 另属运行级结果，不用它替代协方差或 cohort 状态。

**运行入口：** 在 nsgablack 根目录先执行 `python examples/cases/algorithm_semantics/run_project.py --group cmaes_distribution --check --build-check`，再执行同路径 `run_project.py --group cmaes_distribution`。该组只运行此 Case。本轮未执行，不沿用仓库 RESULTS 的数值作为新配置结果。

### 变体一：切换到成套一维固定首批夹具

**目的：** 检查正权重分布更新的输入/父代排序是否能逐项解释，而非凭随机运行的一次好结果判断公式。

**改在哪里：** 原 `cases/cmaes_distribution/build_solver.py` 中已有 `overrides = dict(component_overrides or {})`。紧接它，把原 settings 构造行完整替换为：

```python
settings = CMASettings(**{
    **dict(config or {}), **dict(overrides.pop("config", {})),
    "fixture": "scalar", "max_steps": 1,
})
```

**行为变化：** 原 builder 选择一维目标 `(x-1)^2`，上方工厂同步使用一维 mean、sigma=1、首批 z 为 -1/0/1/2、显式正权重与学习率。Problem、采样 shape、分布维度一起改变，仍用原报告；这是解析输入夹具，不是只减一个迭代数字。

**限制：** 固定的是首批标准正态输入，不能把“未单独评估的重组均值”当最佳候选。保留 identity pipeline，不加 ClipRepair；若显式 evaluation_budget，必须容纳整批。此首版没有声明 PoolTask 的 initialize/refine/compete 能力。依据为 `adapters/cmaes/adapter.py`、`components.py`、上述 Case builder/config/report。

## adapter.map_elites · 每个行为格子保留一个质量冠军

**什么时候用：** 不只找一个总最优点，而想保留行为不同的候选。例如二维坐标作为行为描述，原始质量为到 `(.2,.8)` 的平方距离，每格保留可行性更好、质量更低的精确候选版本。

**先准备什么：** 使用 `examples/cases/algorithm_semantics/cases/map_elites_archive`，独立 Project group 为 map_elites_archive。原 ArchiveConfig 为 seed=31、batch_size=5、max_steps=3；Problem 为二维 `[0,1]`，pipeline 做 ClipRepair。原 builder 已调用 build_adapter(settings) 并挂 ArchiveSummary；不改其报告为“最佳单点就是全部档案”。

**放在哪：** 完整替换或保留该 Case 的 `adapter/__init__.py`。五个候选在工厂内给全，没有隐藏数据源。

**接入步骤：**

```python
from nsgablack.adapters.map_elites import (
    MapElitesAdapter, MapElitesConfig, IdentityDescriptor,
    GridCells, MinimizeObjective, SequenceEmitter,
)

POINTS = ((.1, .1), (.4, .4), (.6, .4), (.6, .8), (.8, .2))

def build_adapter(settings):
    return MapElitesAdapter(
        MapElitesConfig(batch_size=settings.batch_size, random_seed=settings.seed),
        descriptor=IdentityDescriptor(),
        cells=GridCells(lower=(0., 0.), upper=(1., 1.), bins=(2, 2)),
        competition=MinimizeObjective(objective=0), emitter=SequenceEmitter(POINTS))
```

emitter 提案后，Solver repair、评估和接纳；descriptor 使用实际送评后候选定位格子。competition 比较 raw 可行性、违反量和第 0 原始目标，同分保留旧冠军；只更新真正接纳的行。Unit.entries 是冠军权威，普通 `map_elites/archive` 视图与同次事务发布，不是额外复制候选。SequenceEmitter 发完有限五点后 exhausted=True，正常结束；max_steps=3 是上限，不保证提交三步。

**怎样判断接对：** 本次 `algorithm_semantics/results/map_elites_archive/summary.json` 的 cells、candidates、costs、refs 描述冠军，components 中 accepted_observations 是已接纳观测数，archive_size 是冠军格数。基线无额外筛行时，按五点/二维 2×2 网格与质量公式可预期三个冠军格；这是源码推导的检查，不是本轮实测数值。`get_population_solution_refs(control)`/`get_population_snapshot()` 返回档案冠军，不是最近整批提案；accepted 历史还可包含被同格更好者替换的版本。Solver 的单个 incumbent 不是整个地图。报告有本轮 run_id，正式 Case 另以 finalization 事务发布 summary Artifact，旧本地 JSON 不算新运行成功证据。

**运行入口：** 在 nsgablack 根目录先执行 `python examples/cases/algorithm_semantics/run_project.py --group map_elites_archive --check --build-check`，再执行同路径 `run_project.py --group map_elites_archive`；只运行这个 Case，不使用带默认冠军断言的另一套报告脚本来验收改过的地图。本书未执行。

### 变体一：质量仍是二维问题，行为只按第一坐标分格

**目的：** “行为相似”不一定等于所有决策变量都接近。只用 x0 区分行为，让 x1 在同一个行为格内竞争质量。

**改在哪里：** 完整替换同一 `adapter/__init__.py`：

```python
from nsgablack.adapters.map_elites import (
    MapElitesAdapter, MapElitesConfig, IdentityDescriptor,
    GridCells, MinimizeObjective, SequenceEmitter,
)

POINTS = ((.1, .1), (.4, .4), (.6, .4), (.6, .8), (.8, .2))

def build_adapter(settings):
    return MapElitesAdapter(
        MapElitesConfig(batch_size=settings.batch_size, random_seed=settings.seed),
        descriptor=IdentityDescriptor(indices=(0,)),
        cells=GridCells(lower=(0.,), upper=(1.,), bins=(4,)),
        competition=MinimizeObjective(objective=0), emitter=SequenceEmitter(POINTS))
```

**行为变化：** 描述符和网格同时变成一维，候选与原始质量函数仍为二维。不是把 Problem.dimension 改为 1，也不是只扩大档案容量；在 x0 落同一格时，第二坐标仅通过质量参与竞争。原 ArchiveSummary 按实际 cell 记录，不假定 cell 有两个坐标。

**限制：** 五个点只是有限示例，不代表四个格都会被充分探索。更换 emitter 时，空返回不自动代表结束，有限 emitter 须显式 exhausted；本组件没有声明依赖整批反馈自适应的 CMA emitter。依据为 `adapters/map_elites/adapter.py`、`components.py` 与实际 Case Problem/Pipeline/ArchiveSummary。
