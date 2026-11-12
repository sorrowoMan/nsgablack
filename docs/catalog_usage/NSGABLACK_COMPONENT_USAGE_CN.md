# NSGABlack 组件逐项使用示例

这些是正式 Case 中的装配/回调片段，不是另一个求解循环。`solver`、`problem`、`pipeline`、`adapter` 等自由变量均由同一 Case 的工厂或实际调用提供；每条前置说明限定输入，不按名称猜算法语义。完整运行继续用 Project/Case 标准入口。

卡片核对当前导入路径、签名和源码；运行状态按各条同版本收据分别记录，不能由某一条推及全书。
FixedCandidate 的独立数值 Project 已实际运行并核对池反馈；其余没有收据的章节仍是源码用法。数字结果只在确实执行后报告。

## 共同装配位置

- Adapter：Case `adapter/` 工厂中构造，`build_solver.py` 挂载。
- 问题候选处理：Case `pipeline/` 工厂中构造；Problem保留原始评估。
- Bias：Case `bias/` 工厂中构造；只提供选择偏好，不擦除原始反馈或硬约束。
- Plugin：Case `plugins/` 工厂中构造，评估Provider须正式注册，资源服从Project L0。
- Unit/Pool/事务契约：结构由实际Adapter拥有，草稿回调只在本次声明作用域操作。


## adapter.search_plan · SearchPlanAdapter

自然搜索编排：共享可恢复游标表达串行、并行和有限循环；复用唯一算法实例、Router评估与池任务，不手算全局代数。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import SearchPlanAdapter, StrategySpec, NSGA2Adapter, VNSAdapter, stage, serial, repeat
plan = repeat(times=2, body=serial(stage('ga', steps=5), stage('vns', steps=3)))
adapter = SearchPlanAdapter(plan, [StrategySpec(NSGA2Adapter(), 'ga'), StrategySpec(VNSAdapter(), 'vns')])
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.fixed_candidate · FixedCandidateAdapter

**什么时候用：** 已经确定参数，只让候选经过问题修复、求值、接纳和结果发布；例如基线评分或诊断。下面是完整的二维数值例子，只有一个逻辑步、一次求值，不要求先理解 ML 内层 Case。

**先准备什么：** 使用仓库已有的 `examples/cases/catalog_fixed_candidate/` 标准 Project，默认只运行 `cases/fixed/`。需要已安装兼容的blackbase、nsgablack和NumPy；不需要数据库、GPU或模型API。候选为二维数组，两个坐标范围均为[0,1]，Problem返回平方和。Project只发放1个CPU线程，Case接收授权，不自行分配资源。

**放在哪：** 下方路径均相对 `examples/cases/catalog_fixed_candidate/cases/fixed/`，每个代码块都是对应文件的完整内容。保留Project的run_project.py/project_config.py与生成的Case入口；修改的是这一个Case。`adapter/__init__.py` 导出build_adapter，`pipeline/__init__.py` 导出build_pipeline，`plugins/__init__.py` 导出FixedCandidateTrace；对应导出在下面一并给出。

**接入步骤：** 按路径核对以下文件，再用下方正式Project命令运行。builder只装配，不自己调用evaluate，也不预先建立Unit。

`problem/__init__.py`：

```python
"""二维平方和：候选、目标和问题边界均在本 Case 内明确。"""
import numpy as np
from nsgablack.core import BlackBoxProblem


class FixedPointProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="fixed_point", dimension=2,
                         bounds=[(0.0, 1.0), (0.0, 1.0)],
                         objectives=["squared_norm"])

    def evaluate(self, x):
        return float(np.sum(np.asarray(x, dtype=float) ** 2))


def build_problem():
    return FixedPointProblem()
```

`pipeline/main.py`：

```python
"""同一问题管线提供默认随机初值和 [0,1] 问题修复。"""
from nsgablack.representation import RepresentationPipeline, UniformInitializer, ClipRepair


def build_pipeline():
    return RepresentationPipeline(
        initializer=UniformInitializer(low=0.0, high=1.0),
        repair=ClipRepair(low=0.0, high=1.0),
    )
```

`pipeline/__init__.py`：

```python
from .main import build_pipeline

__all__ = ["build_pipeline"]
```

`adapter/main.py`：

```python
"""直属初始化只给候选；问题修复和评估仍由控制面执行。"""
import numpy as np
from nsgablack.adapters import FixedCandidateAdapter


class FixedSeed:
    stateless = True

    def __init__(self, candidate=(0.25, 0.75)):
        value = np.asarray(candidate, dtype=float)
        if value.shape != (2,) or not np.all(np.isfinite(value)):
            raise ValueError("candidate must contain two finite numbers")
        self._candidate = tuple(float(item) for item in value)

    def checkpoint_identity(self):
        return {"name": "catalog_fixed_seed", "version": 1,
                "candidate": list(self._candidate)}

    def initialize(self, problem, context):
        return np.array(self._candidate, dtype=float)


def build_adapter(*, candidate=(0.25, 0.75), use_pipeline_initializer=False):
    initializer = None if use_pipeline_initializer else FixedSeed(candidate)
    return FixedCandidateAdapter(initializer=initializer)
```

`adapter/__init__.py`：

```python

from .main import build_adapter

__all__ = ["build_adapter"]
```

`plugins/trace.py`：

```python
"""只读、无文件写入的结果观察；不另外调用 evaluate。"""
import json
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin


class FixedCandidateTrace(Plugin):
    participation = ParticipationContract()
    context_requires = ()
    context_provides = ()
    context_mutates = ()
    context_cache = ()
    context_notes = ("Read exact pool references after the run; no context writes.",)

    def __init__(self):
        super().__init__(name="fixed_candidate_trace")

    def on_solver_finish(self, result):
        solver = self.solver
        refs = solver.adapter.get_solution_pool_roots(solver) or ()
        objectives, violations = solver.solution_pool.read_raw_feedback(refs)
        payload = {
            "steps": int(solver.run_progress_steps),
            "evaluations": int(solver.evaluation_count),
            "candidates": solver.solution_pool.read(refs).numeric_matrix.tolist(),
            "raw_objectives": objectives.tolist(),
            "raw_violations": violations.tolist(),
            "accepted_refs": len(refs),
        }
        print("fixed-candidate-result " + json.dumps(payload, sort_keys=True))
```

`plugins/__init__.py`：

```python

from .trace import FixedCandidateTrace

__all__ = ["FixedCandidateTrace"]
```

`build_solver.py`：

```python
"""唯一规范装配入口；不在这里另写评估或搜索循环。"""
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from .adapter import build_adapter
from .pipeline import build_pipeline
from .problem import build_problem
from .plugins import FixedCandidateTrace


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    options = dict(config or {})
    solver = ComposableSolver(
        problem=build_problem(),
        representation_pipeline=build_pipeline(),
        adapter=build_adapter(
            candidate=options.get("candidate", (0.25, 0.75)),
            use_pipeline_initializer=bool(options.get("use_pipeline_initializer", False)),
        ),
        resource_context=resource_context,
    )
    solver.set_random_seed(17)
    solver.set_max_steps(1)
    solver.add_plugin(FixedCandidateTrace())
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

**怎样判断接对：** 终端应出现一行 `fixed-candidate-result` JSON：steps=1、evaluations=1、accepted_refs=1、candidates=[[0.25,0.75]]、raw_objectives=[[0.625]]、raw_violations=[0.0]。这是只读Plugin从本次实际接纳的精确池引用读取的结果，不是再次求值；目标0.625来自0.25²+0.75²。只看到Project退出码为0还不够，请同时检查这行。装配后、运行前current_unit为None正常；首次提案才建立候选Unit。

**运行入口：** 从nsgablack仓库根目录执行以下两条命令。第一条只检查装配和实际授权；第二条真正运行。`--no-record`不保存Project运行清单，不改变一次求值语义；共享底座仍可维护自己的资源控制与Artifact目录。

```powershell
python examples/cases/catalog_fixed_candidate/run_project.py --check --build-check
python examples/cases/catalog_fixed_candidate/run_project.py --no-record
```

**边界：** FixedCandidate每步重新请求一个初值，不自动把随机初值冻结。单次评估由max_steps=1保证；本例没有变异或生存竞争。ML模型参数、UnknownState与ClosedFormDataPipeline有自己的语义，不能直接用这里的二维数组替换它们；需要ML时看对应Representation和LearningProblem。读取候选不是解码另一个Adapter的Unit。

**配套组件 key：** `solver.composable`、`repr.pipeline`、`tool.solution_pool`。

**接口依据与验证状态：** 本例通过正式Project的check/build-check与单步运行；实际读到上述0.625目标。针对性测试另检查越界候选修复后才评估，以及移除直属初始化改走共享Pipeline。目录中的运行标签仍以当前发布版本的独立收据为准；本页不会自动运行。

### 变体一：故意给越界初值，看谁负责修复

在本Case的build_solver.py中，把传给build_adapter的默认候选改成下面这一行，其余文件保持不变：

```python
candidate=options.get("candidate", (0.25, 1.5)),
```

仍从同一个Project入口运行。FixedSeed交出[0.25,1.5]，问题管线ClipRepair把最终候选变成[0.25,1.0]，随后才求值。结果应为raw_objectives=[[1.0625]]，仍只评一次。观察器从池中读取的是修复后的精确候选版本；不能继续拿原数组1.5计算目标，也不能在Adapter里再手工repair一次。

### 变体二：不使用直属初始化，让问题管线给初值

在本Case的build_solver.py中，把build_adapter调用中的这一项改为True，其余保持原装配：

```python
use_pipeline_initializer=True,
```

这会让工厂使用 `FixedCandidateAdapter(initializer=None)`，由共享Pipeline的UniformInitializer提供[0,1]内的二维初值。仍只评一个候选，观察值不再保证是[0.25,0.75]；应核对原始目标等于该行候选的平方和。示例solver随机种子为17，不需要手工调用init预热。若把max_steps增加，每步都会重新初始化；fixed只描述这类单候选请求，不是随机采样冻结器。

## adapter.gradient_optimizer · GradientOptimizerAdapter

通用一阶优化：SGD/Adam/AdamW 消费 Provider 梯度，支持普通池精修并交付已评估任务最佳；目标单独投影不冒充梯度变换。Provider slot 事务与资源授权保留原边界。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.gradient_optimizer import GradientOptimizerAdapter
adapter = GradientOptimizerAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.gaussian_search · GaussianSearchAdapter

高斯随机搜索：支持直接 initializer/结构 repair 与池精修；高斯采样分布仍由算法维护，不声称消费通用 mutator 或 selector。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import GaussianSearchAdapter, GaussianSearchConfig
adapter = GaussianSearchAdapter(GaussianSearchConfig(population_size=8, mutation_scale=0.1))
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.role · RoleAdapter

角色包装器：元数据与候选配额协作。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import RoleAdapter, NSGA2Adapter
role = RoleAdapter('explorer', NSGA2Adapter(), name='coarse')
solver.set_adapter(role)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：RoleAdapter代理一个已有搜索决策者；它不是另一个候选编码器。

## adapter.multi_role_controller · MultiRoleControllerAdapter

多角色控制器：共享上下文与预算调度。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import RoleAdapter, NSGA2Adapter, VNSAdapter
from nsgablack.adapters.role_adapters import MultiRoleControllerAdapter
roles = [RoleAdapter('population', NSGA2Adapter()), RoleAdapter('local', VNSAdapter())]
solver.set_adapter(MultiRoleControllerAdapter(roles))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：孩子保持各自Unit与分区；并行角色不自动构成GA→VNS候选交接。

## adapter.composite · CompositeAdapter

**什么时候用：** 你希望几个搜索器在同一个问题上各自搜索，把本轮产生的候选一起交给 Solver 求值。例如下面有两个独立的 NSGA-II 种群：`wide` 走大步，`narrow` 走小步。每个种群都保留 4 个成员，并各提出 4 个后继候选。这样可以尝试两种搜索尺度，同时保留各自的演化过程。

**先准备什么：** 先使用仓库已有的 `examples/cases/catalog_recipes/` Project；默认组只运行其中的 `composite` Case，无需先生成一套新脚手架。该 Case 已有二维问题 `min x[0]² + x[1]²`，两个变量范围均为 `[-2, 2]`，`pipeline/` 负责随机初值和越界修复。两个搜索器使用同一 Problem 的原始目标；不同的是变化尺度，不是把目标或种群混成一个。

**放在哪：** 下方是 `examples/cases/catalog_recipes/cases/composite/build_solver.py` 的装配主体，可以直接在该文件修改。`build_problem()` 和 `build_pipeline()` 来自同 Case 的现有工厂；`resource_context` 由 Project 传入，不需要自己创建一个授权。`wide` 和 `narrow` 每次装配各构造一个实例，随后由框架反复调用。

```python
from nsgablack.project.starter import build_starter_solver
from nsgablack.project import apply_solver_component_overrides
from .pipeline import build_pipeline
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    solver = build_starter_solver(problem=build_problem(), pipeline=build_pipeline(),
                                  resource_context=resource_context, max_steps=2)
    from nsgablack.adapters import CompositeAdapter, NSGA2Adapter
    from nsgablack.representation import GaussianMutation
    solver.set_adapter(CompositeAdapter(adapters=[
        NSGA2Adapter(name="wide", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.4)),
        NSGA2Adapter(name="narrow", population_size=4, offspring_size=4,
                     mutator=GaussianMutation(sigma=0.05)),
    ]))
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

**接入步骤：**

1. 在仓库根目录使用下方正式 Project 命令。先保持两个孩子的 `population_size=4`、`offspring_size=4` 和 `max_steps=2`，确认这个小例子能完成。
2. 一轮中，Composite 按列表顺序向 `wide`、`narrow` 要候选，把两批提案接在一起；Solver 对候选做问题修复、求值和接纳。正常完整接纳时，这一轮的对外提案是 `4 + 4 = 8` 个。
3. 评分后，`wide` 只收到自己那 4 个候选的反馈，`narrow` 也只收到自己的反馈；各自做生存选择并保留自己的 4 个成员。若预算或接纳筛掉部分候选，只回传各自实际被接纳的行，不把别人的结果补给它。
4. 想改搜索尺度，修改对应孩子的 `sigma`；想改其中一个种群的大小，只改该孩子的 `population_size`。`offspring_size` 是每轮新提案数，和最终成员数不是一个参数。共享初值、问题修复仍在 `pipeline/`；不必为两个孩子复制两套 Problem。

**怎样判断接对：** 终端应显示 `composite` Case 成功完成。通过正式 Case 接口检查时，运行后的 `solver.run_progress_steps` 应为 2，`solver.evaluation_count` 为 16；`solver.adapter.get_population_partitions()` 应有 `child:0:wide/population` 和 `child:1:narrow/population` 两个分区，每个 `population.shape` 为 `(4, 2)`，`objectives.shape` 为 `(4, 1)`。这表示两个搜索器各留 4 个二维候选，不是拼成一个 8 人种群；最后一批送评候选也不等于最终成员。此配置的首轮从私有数值种子变化后送出首批提案，第二轮再送出后继；共两批、每批 8 次求值，没有额外一批初始求值。分区检查的完整代码见本 Case 的 README，它是只读检查，不是默认终端会打印的内容。换成显式 initializer、语义初值或限制预算后，不能继续照搬该次数；也不能据两轮结果声称已找到最优解。

**运行入口：** 先在仓库根目录执行 `python examples/cases/catalog_recipes/run_project.py --check --build-check` 检查装配与资源，再执行 `python examples/cases/catalog_recipes/run_project.py`。默认组只运行上面的 `composite` Case；网页仅展示命令，不会自动运行。

**边界：** Composite 按顺序调用孩子，不会因此开启线程或进程并行，也不替孩子去重、统一选择胜者或自动交换成员。把 `NSGA2Adapter()` 和 `VNSAdapter()` 并列放进去，只表示分别提案，不表示 VNS 会取得 GA 的精英来精修。需要“GA → 选精英 → VNS → 返回 GA”时，使用 `SearchPlanAdapter` 与显式 PoolTask 交接，完整例子见 `examples/cases/assembled_ga_vns/`；不能用当前两行旧片段代替这份编排。

**配套组件 key：** `adapter.nsga2`、`repr.gaussian_mutation`、`repr.pipeline`；需要顺序精修时查看 `adapter.search_plan`。

**接口依据与验证状态：** `adapters/algorithm_adapter.py` 的 `CompositeAdapter` 与上述正式 Case。文档片段绑定源码，页面的 `source_checked` 表示源码核对，不等同于本次服务器发布已取得该 Project 的执行收据。

## adapter.astar · AStarAdapter

A* 搜索内核：UnitBinding 构建节点，Adapter 决定扩展与优先级；显式 pool_start_policy='new_root' 从池初始化并保留节点精确版本，不继承旧路径代价。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.adapters import AStarAdapter
def neighbors(state, context):
    return [np.asarray(state) + 1.0]
adapter = AStarAdapter(neighbors=neighbors, start_state=np.array([0.0]),
    goal_test=lambda state, context: state[0] >= 3,
    edge_cost=lambda parent, child, context: 1.0)
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：候选是图节点状态；A*路径g/父边代价与Problem目标不同。默认reject修复策略保护边代价不变量；本段只配置边与终止规则。 本段起点是一维，所以Problem.dimension必须为1。

## adapter.moa_star · MOAStarAdapter

多目标 A*：Pareto 标签与支配剪枝；显式 pool_start_policy='new_root' 接入单个池种子，保留精确路径引用，不接受通用标量投影。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.adapters import MOAStarAdapter
def neighbors(state, context):
    return [np.asarray(state) + 1.0]
adapter = MOAStarAdapter(neighbors=neighbors, start_state=np.array([0.0]),
    goal_test=lambda state, context: state[0] >= 3,
    edge_cost=lambda parent, child, context: np.array([1.0, 0.5]))
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：候选是图节点状态；A*路径g/父边代价与Problem目标不同。默认reject修复策略保护边代价不变量；本段只配置边与终止规则。 本段起点是一维、边代价为双目标，所以Problem.dimension=1且原始反馈提供两个目标。

## adapter.async_event_driven · AsyncEventDrivenAdapter

事件队列编排：驱动 propose/update。

输入与位置：同一正式Case已构造的solver与问题候选管线；声明的局部context键：generation。

```python
from nsgablack.adapters import AsyncEventDrivenAdapter, EventStrategySpec, NSGA2Adapter, VNSAdapter
strategies = [EventStrategySpec(NSGA2Adapter(), 'global'), EventStrategySpec(VNSAdapter(), 'local')]
solver.set_adapter(AsyncEventDrivenAdapter(strategies))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：队列/信号驱动调度；并不自动建立候选精修输入，池任务仍须单独声明。

## adapter.single_trajectory_adaptive · SingleTrajectoryAdaptiveAdapter

单轨迹自适应搜索：可直接装配初始化、变化、结构修复；selector 的 candidate 选择只选本批候选，接受与步长适应仍由 Adapter 决定。

输入与位置：同一正式Case已构造的solver与问题候选管线；声明的局部context键：generation。

```python
from nsgablack.adapters.single_trajectory_adaptive import SingleTrajectoryAdaptiveAdapter
adapter = SingleTrajectoryAdaptiveAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.de · DifferentialEvolutionAdapter

差分进化：保留差分供体与交叉，直属 mutator 只处理 trial；selector 在 replacement 位置比较 trial 与提案时冻结目标，不做全局种群选择。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import DifferentialEvolutionAdapter
adapter = DifferentialEvolutionAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.gradient_descent · GradientDescentAdapter

有限差分精修：起点、成对探针、下降提案各自评估；支持普通／投影池任务，不把探针分数套给未评估的新点。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import GradientDescentAdapter
adapter = GradientDescentAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.mas · MASAdapter

Model-and-Search：支持普通／投影池精修，明确起点与任务最佳；代理模型历史按精确版本保存和裁剪，不隐式借其他算法的全局最优点。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import MASAdapter
adapter = MASAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.moead · MOEADAdapter

**什么时候用：** 多个目标需要按一组方向分别维护解，并希望把某些方向交给 VNS 等局部算法精修。若只是单目标随机搜索，不必先引入方向、邻域和参考点。

**先准备什么：** Problem 声明 `d` 个决策变量和 `m` 个目标；每个候选 shape 为 `(d,)`，一批原始目标为 `(n,m)`。正式 `assembly_workbench/directions` Case 是一维候选、两个最小化目标 `[(x-1)^2, (x+1)^2]`，候选区间 `[-2,2]`。`population_size` 是方向槽位数，`batch_size` 是每次提案量，两者不等于解池容量。

**放在哪：** Case 的 `adapter/composition.py::build_adapter(settings)` 负责 MOEA/D 和子算法；`pipeline/main.py` 负责问题边界修复；`build_solver.py` 负责把二者装配并传入 Project 发放的 `resource_context`。

**接入步骤：** 以下是该正式 Case 中方向所有者的装配片段，`settings` 来自该 Case 的配置对象，含 `directions` 和 `seed`：

```python
from nsgablack.adapters import MOEADAdapter
from nsgablack.representation import UniformInitializer, GaussianMutation

def build_direction_owner(settings):
    return MOEADAdapter(
        name="direction_owner", population_size=settings.directions,
        batch_size=3, neighborhood_size=3, decomposition="tchebycheff",
        random_seed=settings.seed,
        initializer=UniformInitializer(low=-2.0, high=2.0),
        mutator=GaussianMutation(sigma=0.3),
    )
```

先让该实例完成已评估的初始化，再用 `subpools.all(moead)` 选择它发布的方向视图。局部精修和返回竞争的完整接法见该 Case 的 `adapter/composition.py`：`PoolTaskSpec` 冻结方向权重和参考点，精修结果由原 MOEA/D 实例竞争接回。不要把方向标量分数写进 Problem 的原始双目标。

**运行入口：** 在 nsgablack 仓库根目录使用 `python examples/cases/assembly_workbench/run_project.py --group directions`。这是现有正式 Project 的入口，本轮未执行。

**怎样判断接对：** 在收到本 Case `solver` 的观察回调中，用已装配的 MOEA/D 实例 `adapter.get_population_solution_refs(solver)` 取得成员引用，再用 `solver.solution_pool.read_raw_feedback(refs)` 检查原始目标仍有两列。`adapter` 是前面工厂创建的那一个实例。`get_population_snapshot()` 返回按槽位对齐的 `(X,F,V)`，不是把方向标量拼成原始目标。精修返回的候选重新评估后才参与替换；方向尚未完成初始化时，空视图不能表示已完成。

**配套组件 key：** `repr.continuous`、`repr.gaussian_mutation`、`repr.pipeline`、`tool.subpools`、`tool.pool_task_spec`、`adapter.vns`、`adapter.search_plan`。

**接口依据与验证状态：** `adapters/moead/adapter.py`、`examples/cases/assembly_workbench/cases/directions/`；仅源码核对。

## adapter.multi_strategy · StrategyRouterAdapter

多策略控制器：StrategyTask 隔离子任务，StrategyOrigin 记录来源；working_pool 绑定普通工作区，未指定输入的池任务继承最近组合来源，新接纳候选进入最近工作区。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import StrategyRouterAdapter, StrategySpec, NSGA2Adapter, VNSAdapter
strategies = [StrategySpec(NSGA2Adapter(), 'global'), StrategySpec(VNSAdapter(), 'local')]
solver.set_adapter(StrategyRouterAdapter(strategies))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.nsga2 · NSGA2Adapter

**什么时候用：** 需要维护一个种群，通过非支配排序与拥挤度保留多目标折衷解；也可作为单目标全局搜索阶段，与池精修组合。先保留默认生存选择，只有明确要改变比较规则时才传 `selector`。

**先准备什么：** Problem 给出维数 `d`、目标数 `m`、每个变量的实际上下界；初始化返回 shape `(d,)` 的候选。容量 `N=population_size`，后代上限 `offspring_size` 单独配置。初始化预算不足时不能把未评估种子当成完整种群。以下 `settings` 是正式 `assembled_ga_vns` Case 的 `DemoConfig`，不是共享 context；它提供 `population_size` 和 `ga_sigma`。

**放在哪：** 在 Case 的 `adapter/` 工厂构造；在 `build_solver.py` 把返回的 Adapter 传给 `ComposableSolver`，同处传入 `problem=build_problem()` 和 `representation_pipeline=build_pipeline()`。Problem、管线分别由各自目录工厂产生。

**接入步骤：** 下段可作为该 Case 工厂中的 GA 子实例；原例的 Router 与 VNS 接线继续保留在外层工厂：

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation

def build_ga(settings):
    return NSGA2Adapter(
        name="ga", population_size=settings.population_size,
        offspring_size=settings.population_size,
        initializer=UniformInitializer(low=-4.0, high=4.0),
        mutator=GaussianMutation(sigma=settings.ga_sigma),
    )
```

该正式宿主的候选是二维向量，Problem 返回 `(x0-2)^2+(x1+1)^2`，问题管线修复 `[-4,4]` 边界。若换成自己的多目标 Problem，同步更改维数和边界即可，NSGA2 不接收手工构造的目标矩阵。`parent_selector` 选父成员精确引用；`selector` 决定合并候选中的生存行，这两个位置不能互换。

**运行入口：** `python examples/cases/assembled_ga_vns/run_project.py` 运行现有 GA → VNS → 返回竞争 Project；它演示装配，不是纯 NSGA2 对比基准。本轮未运行。

**怎样判断接对：** 完成初始化后，用该实例的 `get_population_snapshot()` 读 `(X,F,V)`，应分别为 `(n,d)`、`(n,m)`、`(n,)`，且 `n<=N`；用 `get_population_solution_refs(control)` 取得同一成员顺序的精确引用，再按引用读取池中的原始反馈。输出是保留的已评估种群，不保证一轮收敛。正式宿主的 `results/trace.json` 中 `records[*].units` 记录 `population_members`，`initial.operation_contracts` 记录实际算子绑定；根池历史不能替代成员列表。

**配套组件 key：** `solver.composable`、`repr.continuous`、`repr.gaussian_mutation`、`repr.pipeline`、`tool.solution_pool`；精修组合另用 `tool.pool_task_spec`、`adapter.vns`。

**接口依据与验证状态：** `adapters/nsga2/adapter.py` 与 `examples/cases/assembled_ga_vns/cases/hybrid_search/`；仅源码核对。

## adapter.nsga3 · NSGA3Adapter

NSGA-III：参考点生存选择；继承 NSGA 独立初始化、变化、精确父代与结构修复，显式 selector 覆盖 survivor 位置，默认保留参考方向生态位。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import NSGA3Adapter
adapter = NSGA3Adapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.pattern_search · PatternSearchAdapter

坐标模式搜索：初始化与结构修复可独立装配，candidate selector 选已评估轮询点；坐标几何、实际位移与步长更新仍属于算法。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import PatternSearchAdapter
adapter = PatternSearchAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.sa · SimulatedAnnealingAdapter

模拟退火：独立装配初始化、变化与结构修复；selector 仅通过 proposal_order 重排本批邻域，Metropolis 接受与温度调度仍由 Adapter 执行。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import SimulatedAnnealingAdapter
adapter = SimulatedAnnealingAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.spea2 · SPEA2Adapter

SPEA2：强度与密度生存选择；继承独立初始化、变化、精确父代与结构修复，selector 明确覆盖 survivor 而非父代来源。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import SPEA2Adapter
adapter = SPEA2Adapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.trust_region_dfo · TrustRegionDFOAdapter

信赖域无梯度精修：支持普通／投影池任务，起点先评估，邻域修复守半径，交付精确已评估结果。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import TrustRegionDFOAdapter
adapter = TrustRegionDFOAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.trust_region_mo_dfo · TrustRegionMODFOAdapter

多目标信赖域 DFO：原生任务冻结权重，外部投影采用冻结任务规则；普通换方向先重评分历史向量，支持精确池结果。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import TrustRegionMODFOAdapter
adapter = TrustRegionMODFOAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.trust_region_nonsmooth · TrustRegionNonSmoothAdapter

非光滑信赖域：原生 Linf 聚合；投影池任务采用明确比较坐标，保留原始反馈与精确结果。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import TrustRegionNonSmoothAdapter
adapter = TrustRegionNonSmoothAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.trust_region_subspace · TrustRegionSubspaceAdapter

子空间信赖域：使用本任务实际接纳的有界参考样本，裁剪保持子空间；支持普通／投影池精修与精确引用保留。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import TrustRegionSubspaceAdapter
adapter = TrustRegionSubspaceAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.vns · VNSAdapter

**什么时候用：** 有一个起点，希望在不同尺度的邻域中继续找改进；典型用法是接收 NSGA2 的成员逐个精修。VNS 自己决定接受和切换邻域，变异组件负责生成候选。

**先准备什么：** 每个起点是 Problem 能解释的候选，数值部分 shape 为 `(d,)`。单独运行时提供 initializer；从池接入时由 `PoolTaskSpec` 指定已发布来源。每个起点会先重新评估以建立本任务基准，`steps` 预算须包含这一步。需要变化尺度随邻域切换时，使用 `ContextGaussianMutation`，因为固定 `GaussianMutation` 不读取 VNS 的局部尺度。

**放在哪：** Case 的 `adapter/composition.py` 构造 VNS 及其 `PoolTaskSpec`；问题边界修复放 `pipeline/`。下面函数没有未绑定全局变量：配置为二维盒问题常用的局部扰动，维数仍由宿主 Problem 决定。

**接入步骤：**

```python
from nsgablack.adapters import VNSAdapter
from nsgablack.representation import ContextGaussianMutation

def build_local_search():
    return VNSAdapter(
        name="vns", batch_size=1, k_max=3,
        base_sigma=0.2, scale=1.5, max_sigma=0.8,
        restart_on_stagnation=False,
        mutator=ContextGaussianMutation(base_sigma=0.2),
    )
```

要精修 GA 的全部成员，在同一 Router/SearchPlan 中给该实例配置 `PoolTaskSpec(subpools.all(ga), mode="refine", count="all", steps=2, output="refined", shuffle=False)`；其中 `ga` 是同一工厂刚创建的 NSGA2 实例。完整阶段与返回竞争见正式 `assembled_ga_vns` 工厂。`output="refined"` 收集接纳历史；本轮最终选中结果应通过父级 `get_pool_task_results(control, "vns")` 读取。

**运行入口：** `python examples/cases/assembled_ga_vns/run_project.py --group plan`。该组装使用现有自然搜索计划和正式资源授权，本轮未执行。

**怎样判断接对：** 完整 plan 组运行后读取 `results/plan/trace.json`：`records[*].phase` 区分 GA、VNS、return；return 记录的 `selected_return` 是本轮最终引用，`aggregate_return.refs` 是聚合接纳历史，两者含义不同。也可通过父级 `get_pool_task_results(control, "vns")` 获取本请求结果，再按引用读原始反馈。`count="all"` 才表示覆盖全部成员；refined 池中的每条记录不一定都是改进，不能据其数量断言精修成功。

**配套组件 key：** `repr.context_gaussian`、`repr.pipeline`、`tool.pool_task_spec`、`tool.subpools`、`adapter.search_plan`、`adapter.nsga2`。

**接口依据与验证状态：** `adapters/vns/adapter.py`、`examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py`；仅源码核对。

## adapter.serial_strategy · StrategyChainAdapter

串行策略控制器：按 phase 顺序切换子 Adapter；working_pool 绑定公共普通集合，子组合可继承或显式覆盖，输入来源与精选输出仍分别声明。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import StrategyChainAdapter, SerialPhaseSpec, NSGA2Adapter, VNSAdapter
phases = [SerialPhaseSpec('global', NSGA2Adapter(), steps=5), SerialPhaseSpec('local', VNSAdapter(), steps=3)]
solver.set_adapter(StrategyChainAdapter(phases))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：串行阶段给出执行顺序；需要精修交接时同时声明PoolTask输入和返回竞争。

## adapter.elite_retention · EliteRetentionAdapter

在正式步骤事务内注入精英派生候选，并透明委托内层 Adapter 权威状态。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import EliteRetentionAdapter, EliteRetentionConfig, NSGA2Adapter
solver.set_adapter(EliteRetentionAdapter(NSGA2Adapter(), EliteRetentionConfig()))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.bayesian_optimization · BayesianOptimizationAdapter

**什么时候用：** 单目标最小化、真实求值比代理计算昂贵，希望用已有真实观测选择下一点。当前组件是同步、固定 RBF 后验、LCB 与有限网格提案，不等于异步 BO 或联合 q-batch。

**先准备什么：** 本例 Problem 为 `dimension=1`、一个最小化目标，候选 shape `(1,)`、区间 `[0,1]`，真实目标为 `(x-0.25)^2`。默认初始化点是 `((0.0,), (1.0,))`；采集网格是 shape `(3,1)` 的 `0.25/0.5/0.75`。更改维数时，初始化点矩阵和网格列数都必须一起更改。此实现读取直接 Problem 的完整原始 Evaluation Event，不能接一个私自短路求值的 Provider 然后假定兼容。

**放在哪：** `algorithm_semantics/cases/synchronous_bo/adapter/__init__.py` 组装模型、采集函数与网格；Problem 在 `problem/`，修复在 `pipeline/`，预算和插件在 `build_solver.py`。

**接入步骤：**

```python
from nsgablack.adapters.bayesian_optimization import (
    BayesianOptimizationAdapter, FixedRBFPosterior,
    LowerConfidenceBound, GridAcquisitionOptimizer,
)

def build_adapter():
    return BayesianOptimizationAdapter(
        model=FixedRBFPosterior(),
        acquisition=LowerConfidenceBound(beta=2.0),
        optimizer=GridAcquisitionOptimizer(grid=((0.25,), (0.5,), (0.75,))),
    )
```

由现有 `build_solver.py` 将此工厂接入 `ComposableSolver`。先实际评估初始化点，再让模型根据正式观测计算网格均值、标准差和 LCB；选中的网格点仍必须送 Problem 求值。

**运行入口：** `python examples/cases/algorithm_semantics/run_project.py --group synchronous_bo`。`project_config.py` 中该组指向 `synchronous_bo` 正式 Case；本轮未执行。

**怎样判断接对：** 读取此 Case 输出的 `results/synchronous_bo/summary.json`：`observations` 是验证过的真实观测，`last_acquisition` 的 `mean/std/acquisition` 是网格预测与采集值，`problem_calls`、`evaluations`、`resource_binding_current` 分别记录调用、实际求值计数和生效资源。观测保留真实 Event 身份与原始反馈；低 LCB 是提案理由，不是已实现的目标值。候选从当前成员退出也不应删除已经验证的观测。

**配套组件 key：** `solver.composable`、`repr.pipeline`、`tool.solution_pool`、`plugin.checkpoint_resume`；模型、采集与网格类以本节真实导入路径为准。

**接口依据与验证状态：** `adapters/bayesian_optimization/adapter.py`、`components.py`、`examples/cases/algorithm_semantics/cases/synchronous_bo/`；仅源码核对。

## adapter.cmaes · CMAESAdapter

正权重完整协方差CMA-ES：采样、排名、分布更新分别装配；保存演化路径和完整cohort，严格拒绝改变候选的repair及残缺更新。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import CMAESAdapter
solver.set_adapter(CMAESAdapter([0.0, 0.0], sigma=0.3))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：Problem须为与mean同维的连续单目标；整批队列与更新由CMAESAdapter管理。

## adapter.map_elites · MapElitesAdapter

MAP-Elites：描述符、格子映射、冠军竞争与生成器分别装配；Unit唯一维护格子冠军，Pool发布精确成员视图，支持逐条竞争与事务恢复。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import MapElitesAdapter
adapter = MapElitesAdapter()
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：默认descriptor/cells按二维候选分格，本段需二维Problem；descriptor与cell边界应按实际行为特征设计，原始目标仍由Problem提供。

## tool.bo_model · FixedRBFPosterior

可独立装配的 FixedRBFPosterior；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.bayesian_optimization import BayesianOptimizationAdapter, FixedRBFPosterior
adapter = BayesianOptimizationAdapter(model=FixedRBFPosterior())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.bo_acquisition · LowerConfidenceBound

可独立装配的 LowerConfidenceBound；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.bayesian_optimization import BayesianOptimizationAdapter, LowerConfidenceBound
adapter = BayesianOptimizationAdapter(acquisition=LowerConfidenceBound(beta=2.0))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.bo_acquisition_optimizer · GridAcquisitionOptimizer

可独立装配的 GridAcquisitionOptimizer；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.bayesian_optimization import BayesianOptimizationAdapter, GridAcquisitionOptimizer
adapter = BayesianOptimizationAdapter(optimizer=GridAcquisitionOptimizer(grid=((0.25,), (0.5,), (0.75,))))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.cma_sampler · GaussianCohortSampler

可独立装配的 GaussianCohortSampler；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.cmaes import CMAESAdapter, GaussianCohortSampler
adapter = CMAESAdapter([0.0, 0.0], sampler=GaussianCohortSampler(seed=19))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.cma_ranking · StableObjectiveRanking

可独立装配的 StableObjectiveRanking；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.cmaes import CMAESAdapter, StableObjectiveRanking
adapter = CMAESAdapter([0.0, 0.0], ranking=StableObjectiveRanking())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.cma_update · PositiveCMAUpdate

可独立装配的 PositiveCMAUpdate；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.cmaes import CMAESAdapter, PositiveCMAUpdate
from nsgablack.adapters.cmaes import CMAParameters
parameters = CMAParameters(population_size=4, parents=2)
adapter = CMAESAdapter([0.0, 0.0], parameters=parameters, updater=PositiveCMAUpdate(parameters))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.map_descriptor · IdentityDescriptor

可独立装配的 IdentityDescriptor；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.map_elites import MapElitesAdapter, IdentityDescriptor
adapter = MapElitesAdapter(descriptor=IdentityDescriptor(indices=(0, 1)))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.map_cells · GridCells

可独立装配的 GridCells；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.map_elites import MapElitesAdapter, GridCells
adapter = MapElitesAdapter(cells=GridCells(lower=(0.0, 0.0), upper=(1.0, 1.0), bins=(2, 2)))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.map_competition · MinimizeObjective

可独立装配的 MinimizeObjective；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.map_elites import MapElitesAdapter, MinimizeObjective
adapter = MapElitesAdapter(competition=MinimizeObjective(objective=0, tolerance=0.0))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.map_sequence_emitter · SequenceEmitter

可独立装配的 SequenceEmitter；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.map_elites import MapElitesAdapter, SequenceEmitter
adapter = MapElitesAdapter(emitter=SequenceEmitter(((0.1, 0.1), (0.4, 0.4), (0.6, 0.4), (0.6, 0.8), (0.8, 0.2))))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.map_gaussian_emitter · GaussianArchiveEmitter

可独立装配的 GaussianArchiveEmitter；职责、限制和已有标准 Case 见下列契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters.map_elites import MapElitesAdapter, GaussianArchiveEmitter
adapter = MapElitesAdapter(emitter=GaussianArchiveEmitter(sigma=0.1))
# Also provide solver RepresentationPipeline(initializer=UniformInitializer(...)) for an empty archive.
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.unit_view · UnitView

按实例路径、Unit 身份和 revision 交付脱离只读视图；PopulationView 提供成员能力。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import PopulationUnit, UnitBinding
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units.views import PopulationView
from nsgablack.bias import PreferenceQuery, PopulationDiversityPreference
unit = PopulationUnit('reference', population=np.array([[0., 0.], [1., 1.]]))
view = PopulationView.capture(unit, UnitBinding(PopulationUnitBuilder()), owner_path=('reference',))
score = PopulationDiversityPreference().evaluate(PreferenceQuery('unit', unit=view))
print(score.value, score.direction)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：这是显式只读参考Unit的纯评分；Adapter选择权与Problem原始目标保留。正式绑定示例见下方UnitPreferenceBias专条。

## tool.preference_query · PreferenceQuery

显式区分 candidate、candidate_in_unit、unit、unit_transition 四种评价范围。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import PopulationUnit, UnitBinding
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units.views import PopulationView
from nsgablack.bias import PreferenceQuery, PopulationDiversityPreference
unit = PopulationUnit('reference', population=np.array([[0., 0.], [1., 1.]]))
view = PopulationView.capture(unit, UnitBinding(PopulationUnitBuilder()), owner_path=('reference',))
score = PopulationDiversityPreference().evaluate(PreferenceQuery('unit', unit=view))
print(score.value, score.direction)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：这是显式只读参考Unit的纯评分；Adapter选择权与Problem原始目标保留。正式绑定示例见下方UnitPreferenceBias专条。

## bias.population_diversity · PopulationDiversityPreference

纯评分：候选最近邻新颖性、群体平均最近邻距离及同一 Unit 的变化增益。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.units import PopulationUnit, UnitBinding
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units.views import PopulationView
from nsgablack.bias import PreferenceQuery, PopulationDiversityPreference
unit = PopulationUnit('reference', population=np.array([[0., 0.], [1., 1.]]))
view = PopulationView.capture(unit, UnitBinding(PopulationUnitBuilder()), owner_path=('reference',))
score = PopulationDiversityPreference().evaluate(PreferenceQuery('unit', unit=view))
print(score.value, score.direction)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：这是显式只读参考Unit的纯评分；Adapter选择权与Problem原始目标保留。正式绑定示例见下方UnitPreferenceBias专条。 Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.unit_preference · UnitPreferenceBias

绑定参考 Unit，并可按 StrategyOrigin 实例路径限定候选，将偏好投影为选择增量。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias import BiasModule, UnitPreferenceBias, PopulationDiversityPreference
bias_module = BiasModule()
bias_module.add(UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), adapter, owner_path=('search',)))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：adapter是已装配的种群Adapter；惰性绑定不会为了Catalog展示构建Unit。评分需要该Adapter运行后有合法PopulationView。 Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.module · BiasModule

统一聚合算法偏置与领域偏置的运行门面。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias import BiasModule
from nsgablack.bias.domain.callable_bias import CallableBias
bias_module = BiasModule()
bias_module.add(CallableBias('small_norm', lambda x: float((x*x).sum()), weight=0.1))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.diversity_adaptive · AdaptiveDiversityBias

自适应调整多样性压力。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.diversity import AdaptiveDiversityBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(AdaptiveDiversityBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.diversity_niche · NicheDiversityBias

基于小生境的多样性保持。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.diversity import NicheDiversityBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(NicheDiversityBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.diversity_crowding · CrowdingDistanceBias

基于拥挤距离偏好稀疏/前沿解。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.diversity import CrowdingDistanceBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(CrowdingDistanceBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.diversity_sharing · SharingFunctionBias

适应度共享以降低拥挤。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.diversity import SharingFunctionBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(SharingFunctionBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.convergence_adaptive · AdaptiveConvergenceBias

自适应平衡探索与收敛。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.convergence import AdaptiveConvergenceBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(AdaptiveConvergenceBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.convergence_precision · PrecisionBias

强调精度与局部精修。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.convergence import PrecisionBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(PrecisionBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.convergence_late_stage · LateStageConvergenceBias

加速后期收敛。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.convergence import LateStageConvergenceBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(LateStageConvergenceBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.convergence_multi_stage · MultiStageConvergenceBias

多阶段收敛调度。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.convergence import MultiStageConvergenceBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(MultiStageConvergenceBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.pso_adaptive · AdaptivePSOBias

自适应 PSO 参数。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.pso import AdaptivePSOBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(AdaptivePSOBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.cmaes_adaptive · AdaptiveCMAESBias

按代数调节已有分布距离偏好的强度；不执行 CMA-ES 的分布更新。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.cma_es import AdaptiveCMAESBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(AdaptiveCMAESBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.constraint · ConstraintBias

将约束显式注入评分。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.constraint import ConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ConstraintBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.feasibility · FeasibilityBias

可行性优先。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.constraint import FeasibilityBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(FeasibilityBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.preference · PreferenceBias

编码偏好/权重。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.constraint import PreferenceBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(PreferenceBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.rule_based · RuleBasedBias

规则驱动的加权/惩罚。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.constraint import RuleBasedBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(RuleBasedBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.callable · CallableBias

**什么时候用：** 有一条容易写成函数的软偏好，例如在原目标接近时偏向参数较小的解。硬约束仍由 Problem 和接纳策略定义；“超限必须拒绝”不能只写成 CallableBias。

**先准备什么：** `func(x)` 接收当前候选的数值向量 `(d,)`，返回有限标量；下面返回平方范数。也可用 `func(x, context)`，其中 context 是 `OptimizationContext`，不是任意 Solver 字典。无需依赖 Unit 时不要从共享 context 猜当前种群。

**放在哪：** Case 的 `bias/__init__.py::build_bias()`；`build_solver.py` 构造 Solver 时传 `bias_module=build_bias()`。同一 Case 的 Problem 保留真实目标定义。

**接入步骤：**

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.domain.callable_bias import CallableBias

def prefer_small_parameters(x):
    values = np.asarray(x, dtype=float)
    return float(np.dot(values, values))

def build_bias():
    module = BiasModule()
    module.add(CallableBias("small_parameters", prefer_small_parameters,
                            weight=0.1, mode="penalty"))
    return module
```

若宿主现有工厂调用 `build_bias(weight)`，保留该参数签名并把 `weight` 传给 CallableBias。`penalty` 的正值增加选择目标，`reward` 的正值降低选择目标。不要在函数里求值、修复或修改候选。

**运行入口：** 可在正式 `examples/cases/algorithm_semantics/cases/synchronous_bo/bias/__init__.py` 的工厂中替换现有 `LinearSelectionBias`，保持 `build_bias(weight)` 签名；替换后仍由 `python examples/cases/algorithm_semantics/run_project.py --group synchronous_bo` 运行。当前原 Case 使用的是 `LinearSelectionBias`，没有声称它已经运行过本段 CallableBias。

**怎样判断接对：** 在正式反馈消费者中，对同一批 `OptimizationFeedbackBatch` 比较 `raw_objectives` 与 `objectives`，前者是原始目标，后者是选择目标；`raw_violations` 保留硬约束含义。单目标、weight=0.1 时，本函数的加权惩罚贡献应为 `0.1*||x||²`。原始已接纳反馈也可通过 `solution_pool.read_raw_feedback(refs)` 读取；原 BO 宿主的 `summary.json` 不单独输出 CallableBias 增量，不能假定有现成的同名报告字段。偏好不能绕过硬接纳，原始与选择反馈不能混作同一性能曲线。

**配套组件 key：** `solver.composable`、`adapter.nsga2` 或 `adapter.bayesian_optimization`、`tool.solution_pool`。

**接口依据与验证状态：** `bias/domain/callable_bias.py`、`bias/bias_module.py`；函数与宿主接线仅源码核对，未执行替换后的 Project。

## bias.engineering_design · EngineeringDesignBias

工程设计约束/先验。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.engineering import EngineeringDesignBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(EngineeringDesignBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.safety · SafetyBias

安全/风险优先。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.engineering import SafetyBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(SafetyBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.manufacturing · ManufacturingBias

制造可行性约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.engineering import ManufacturingBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ManufacturingBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.scheduling · SchedulingBias

调度偏好。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.scheduling import SchedulingBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(SchedulingBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.resource_constraint · ResourceConstraintBias

资源容量约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.scheduling import ResourceConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ResourceConstraintBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.time_window · TimeWindowBias

时间窗约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.scheduling import TimeWindowBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(TimeWindowBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.bayesian_guidance · BayesianGuidanceBias

历史引导软偏好；内置模型为占位辅助，不构成完整贝叶斯优化。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.bayesian_biases import BayesianGuidanceBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(BayesianGuidanceBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.bayesian_exploration · BayesianExplorationBias

偏好高不确定区域。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.bayesian_biases import BayesianExplorationBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(BayesianExplorationBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.bayesian_convergence · BayesianConvergenceBias

在后验置信区间内收敛。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.bayesian_biases import BayesianConvergenceBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(BayesianConvergenceBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.engineering_precision · EngineeringPrecisionBias

精度/公差偏置。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.engineering import EngineeringPrecisionBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(EngineeringPrecisionBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.engineering_constraint · EngineeringConstraintBias

工程规则约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.engineering import EngineeringConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(EngineeringConstraintBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.engineering_robustness · EngineeringRobustnessBias

对扰动的鲁棒性。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.engineering import EngineeringRobustnessBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(EngineeringRobustnessBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.local_gd · GradientDescentBias (LocalSearch)

局部梯度精修。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.local_search import GradientDescentBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(GradientDescentBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.local_newton · NewtonMethodBias

牛顿式精修。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.local_search import NewtonMethodBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(NewtonMethodBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.local_line_search · LineSearchBias

线搜索步长控制。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.local_search import LineSearchBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(LineSearchBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.local_trust_region · TrustRegionBias

信赖域精修。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.local_search import TrustRegionBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(TrustRegionBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.local_nelder_mead · NelderMeadBias

Nelder-Mead 单纯形精修。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.local_search import NelderMeadBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(NelderMeadBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.local_quasi_newton · QuasiNewtonBias

拟牛顿精修。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.local_search import QuasiNewtonBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(QuasiNewtonBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_connectivity · ConnectivityBias

图连通性约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.base import GraphStructure
graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)])
from nsgablack.bias.specialized.graph.base import ConnectivityBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ConnectivityBias(graph=graph))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_sparsity · SparsityBias

图稀疏性偏置。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.base import GraphStructure
graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)])
from nsgablack.bias.specialized.graph.base import SparsityBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(SparsityBias(graph=graph))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_degree_distribution · DegreeDistributionBias

目标度分布约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.base import GraphStructure
graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)])
from nsgablack.bias.specialized.graph.base import DegreeDistributionBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(DegreeDistributionBias(graph=graph))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_shortest_path · ShortestPathBias

最短路径偏好。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.base import GraphStructure
graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)])
from nsgablack.bias.specialized.graph.base import ShortestPathBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ShortestPathBias(graph=graph, source=0, target=2))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_max_flow · MaxFlowBias

最大流偏好。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.base import GraphStructure
graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)])
from nsgablack.bias.specialized.graph.base import MaxFlowBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(MaxFlowBias(graph=graph, source=0, sink=2))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_coloring · GraphColoringBias

图着色偏置。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.base import GraphStructure
graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)])
from nsgablack.bias.specialized.graph.base import GraphColoringBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(GraphColoringBias(graph=graph))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_community · CommunityDetectionBias

社区结构偏置。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.base import GraphStructure
graph = GraphStructure(num_nodes=3, num_edges=2, edge_list=[(0,1,1.), (1,2,1.)])
from nsgablack.bias.specialized.graph.base import CommunityDetectionBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(CommunityDetectionBias(graph=graph))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_constraint · GraphConstraintBias

图结构约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias import BiasModule
from nsgablack.bias.specialized.graph.constraints import GraphConstraintBias, ValidationResult
class NonnegativeGraphValues(GraphConstraintBias):
    def validate_constraints(self, x, context):
        valid = bool((x >= 0.).all())
        return ValidationResult(is_valid=valid)
bias_module = BiasModule()
bias_module.add(NonnegativeGraphValues(name='nonnegative_graph_values'))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界：基类是扩展协议，不能直接GraphConstraintBias()；这是数值非负教学规则，不声称完整图合法性。软评分不替代Problem硬约束。 Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_tsp_constraint · TSPConstraintBias

TSP 约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.constraints import TSPConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(TSPConstraintBias(num_cities=3))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_path_constraint · PathConstraintBias

路径约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.constraints import PathConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(PathConstraintBias(num_nodes=3, start_node=0, end_node=2))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_tree_constraint · TreeConstraintBias

树结构约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.constraints import TreeConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(TreeConstraintBias(num_nodes=3))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_coloring_constraint · GraphColoringConstraintBias

着色约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.constraints import GraphColoringConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(GraphColoringConstraintBias(adjacency_matrix=np.array([[0,1,0],[1,0,1],[0,1,0]])))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_matching_constraint · MatchingConstraintBias

匹配约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.constraints import MatchingConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(MatchingConstraintBias(num_nodes=4))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_hamiltonian_constraint · HamiltonianPathConstraintBias

哈密顿路径约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.constraints import HamiltonianPathConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(HamiltonianPathConstraintBias(num_nodes=3))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.graph_composite_constraint · CompositeGraphConstraintBias

复合图约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
import numpy as np
from nsgablack.bias.specialized.graph.constraints import TSPConstraintBias
from nsgablack.bias.specialized.graph.constraints import CompositeGraphConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(CompositeGraphConstraintBias(constraints=[TSPConstraintBias(num_cities=3)]))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.surrogate_control · SurrogateControlBias

代理控制策略：返回控制更新映射；当前没有正式自动消费者，不能加入标量BiasModule。

输入与位置：显式SurrogateBiasContext值；本段只计算控制建议映射，当前没有正式自动消费者。

```python
from nsgablack.bias.surrogate import SurrogateBiasContext
context = SurrogateBiasContext(generation=5, max_generations=10, population=None,
    surrogate_manager=None, surrogate_ready=False, n_training_samples=0,
    model_quality={}, real_eval_count=0, surrogate_eval_count=0,
    prefilter={}, score_bias={}, surrogate_eval={}, constraint_eval={})
from nsgablack.bias.surrogate import SurrogateControlBias
updates = SurrogateControlBias().apply(context)
assert updates == {}
```

预期结果：得到控制建议Mapping；没有正式消费者接入，所以不会自动改变Solver、Provider或真实求值预算。

依赖：当前nsgablack与blackbase；NumPy。

边界：这是控制策略基类，返回更新映射而非标量评分；当前没有正式自动消费者，不添加到BiasModule。扩展者须明确更新映射由哪个已授权控制面消费。

## bias.surrogate_phase_schedule · PhaseScheduleBias

代理控制策略：返回控制更新映射；当前没有正式自动消费者，不能加入标量BiasModule。

输入与位置：显式SurrogateBiasContext值；本段只计算控制建议映射，当前没有正式自动消费者。

```python
from nsgablack.bias.surrogate import SurrogateBiasContext
context = SurrogateBiasContext(generation=5, max_generations=10, population=None,
    surrogate_manager=None, surrogate_ready=False, n_training_samples=0,
    model_quality={}, real_eval_count=0, surrogate_eval_count=0,
    prefilter={}, score_bias={}, surrogate_eval={}, constraint_eval={})
from nsgablack.bias.surrogate import PhaseScheduleBias
policy = PhaseScheduleBias([{'start':0., 'end':1., 'updates':{'prefilter':{'enabled':True, 'ratio':1.0}}}])
updates = policy.apply(context)
assert updates['prefilter']['ratio'] == 1.0
```

预期结果：得到控制建议Mapping；没有正式消费者接入，所以不会自动改变Solver、Provider或真实求值预算。

依赖：当前nsgablack与blackbase；NumPy。

边界：返回阶段控制映射，不是标量偏好。当前没有正式自动消费者，不能把此对象添加到BiasModule或声称已改变Provider预算。

## bias.surrogate_uncertainty_budget · UncertaintyBudgetBias

代理控制策略：返回控制更新映射；当前没有正式自动消费者，不能加入标量BiasModule。

输入与位置：显式SurrogateBiasContext值；本段只计算控制建议映射，当前没有正式自动消费者。

```python
from nsgablack.bias.surrogate import SurrogateBiasContext
context = SurrogateBiasContext(generation=5, max_generations=10, population=None,
    surrogate_manager=None, surrogate_ready=False, n_training_samples=0,
    model_quality={}, real_eval_count=0, surrogate_eval_count=0,
    prefilter={}, score_bias={}, surrogate_eval={}, constraint_eval={})
from nsgablack.bias.surrogate import UncertaintyBudgetBias
updates = UncertaintyBudgetBias().apply(context)
assert updates['prefilter']['ratio'] == 1.0
```

预期结果：得到控制建议Mapping；没有正式消费者接入，所以不会自动改变Solver、Provider或真实求值预算。

依赖：当前nsgablack与blackbase；NumPy。

边界：模型未就绪时建议全真评估；ready分支还需要提供get_uncertainty的真实surrogate_manager。当前没有正式自动消费者，此映射不会自动修改预算，也不添加到标量BiasModule。

## bias.production_constraint · ProductionConstraintBias

生产约束。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.production.scheduling import ProductionConstraintBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ProductionConstraintBias(machine_bom={'A':['material']}, inventory_data={'material':100.}, machine_ids=['A'], days=2))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.production_diversity · ProductionDiversityBias

生产多样性偏好。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.production.scheduling import ProductionDiversityBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ProductionDiversityBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.production_continuity · ProductionContinuityBias

生产连续性偏好。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.specialized.production.scheduling import ProductionContinuityBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ProductionContinuityBias(machine_ids=['A','B'], days=2))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.cmaes · CMAESBias

读取已有 mean/cov/sigma 计算分布距离软偏好；不执行协方差自适应。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.cma_es import CMAESBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(CMAESBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.convergence · ConvergenceBias

收敛加速。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.convergence import ConvergenceBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ConvergenceBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.diversity · DiversityBias

旧单种群距离奖励（最小化负增量）；新装配推荐显式 UnitPreferenceBias。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.diversity import DiversityBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(DiversityBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.dynamic_penalty · DynamicPenaltyBias

约束违反的动态惩罚。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias import BiasModule
from nsgablack.bias.domain.dynamic_penalty import DynamicPenaltyBias
bias_module = BiasModule()
bias_module.add(DynamicPenaltyBias(penalty_func=lambda x: max(0.0, float(x.sum())-1.0), weight=0.1))
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.levy · LevyFlightBias

Levy 飞行探索。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.levy_flight import LevyFlightBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(LevyFlightBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.pso · ParticleSwarmBias

相对给定最好位置的距离软偏好；不维护粒子速度或执行完整 PSO。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.pso import ParticleSwarmBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(ParticleSwarmBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.risk · RiskBias

**什么时候用：** 同一候选在不同随机场景中有不同损失，想在平均损失之外加入波动或最坏观测的软偏好。前提是评估方确实产生了每候选的场景统计；只挂 RiskBias 不会自动做蒙特卡洛采样。

**先准备什么：** 正式 `risk_bias` Case 的候选 shape 为 `(2,)`，Problem 每次调用返回一个带噪声的标量损失：`sum((x-1)^2)+(0.1+abs(x0))*normal_noise`。`MonteCarloEvaluationProviderPlugin` 对同一个候选重复求值 8 次，形成样本矩阵 `(8,1)`，聚合为原始均值目标，并在该候选的 `Feedback.metrics` 中给出 `mc_mean/mc_std/mc_min/mc_max`（本例各为 `(1,)`）及 `mc_samples=8`。共享反馈边界把这些候选局部指标交给 Bias 的 `OptimizationContext.metrics`。

**放在哪：** 随机场景的损失在 Case `problem/risk_cost.py`；场景评估插件在 `evaluation/risk_evaluation.py`；RiskBias 在 `bias/risk.py`；`build_solver.py` 先构造 Problem/Pipeline/Adapter 与 Bias，再挂载场景评估插件。不要把场景统计塞成长期共享的单份 metrics，以免下一候选读到上一候选数据。

**接入步骤：** 以下分别对应 Case 的 bias 工厂与 evaluation 挂载函数，`solver` 是规范 `build_solver.py` 刚构造的同一 Solver：

```python
from nsgablack.bias import BiasModule, RiskBias
from nsgablack.plugins.evaluation.monte_carlo_evaluation import (
    MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig,
)

def build_risk_bias():
    module = BiasModule()
    module.add(RiskBias(weight=0.2, mode="cvar", alpha=0.2,
                        std_scale=1.0, metric_prefix="mc"))
    return module

def attach_scenario_evaluation(solver):
    solver.add_plugin(MonteCarloEvaluationProviderPlugin(
        config=MonteCarloEvaluationConfig(
            mc_samples=8, reduce="mean", cvar_alpha=0.25, random_seed=7,
        )))
```

在 `build_solver.py` 用 `bias_module=build_risk_bias()` 构造 Solver，随后调用 `attach_scenario_evaluation(solver)`；插件 attach 会自动登记它的 Evaluation Provider，无需再手动重复注册。它重复调用 Problem，Problem 自己必须体现随机场景；重复调用确定性函数不会凭空创造噪声。当前 `reduce="mean"` 规定原始目标是场景均值，`cvar_alpha` 只在 Provider 选择 `reduce="cvar"` 时生效。

**运行入口：** 在 nsgablack 仓库根目录使用 `python examples/cases/risk_bias/run_project.py`。现有正式组合为 `RiskCostProblem + TrustRegionDFOAdapter + MonteCarloEvaluationProviderPlugin(mean) + RiskBias`，Case 配置最大 2 个提交步，资源由 Project L0 发放。本轮未执行。

**怎样判断接对：** 在实际反馈消费者中读取 `feedback.items[i].metrics`，核对本候选确有上述四项数组和 `mc_samples=8`；再比较 `feedback.raw_objectives` 与 `feedback.objectives`。当前 RiskBias 的 `cvar` 是 `mean+sqrt(1/alpha)*std_scale*std` 的近似评分，不是样本尾部均值；单目标时加权贡献为它的 `0.2` 倍，原始均值仍须保留。源码声明 `metrics_fallback="safe_zero"`：缺 mean/std 时返回 0，没报错不表示风险引导生效。`worst_case` 模式优先读 mc_max，不能在最小化/最大化方向不同的业务里不检查含义就套用。

**配套组件 key：** `plugin.monte_carlo_eval`（本例统计来源）、`adapter.trust_region_dfo`、`repr.pipeline`、`solver.composable`、`tool.solution_pool`。其它 Provider 若要替换，必须提供同一候选的统计指标与正式反馈，不能只发布一份全局平均数。

**接口依据与验证状态：** `bias/domain/risk_bias.py`、`plugins/evaluation/monte_carlo_evaluation.py` 与 `examples/cases/risk_bias/cases/risk_bias/`；仅源码核对。当前配置参数以上述实际 Config 类为准；若 Catalog 仍展示旧的 n_samples/noise_std/aggregation 等名称，那是与源码不一致的旧元数据。

## bias.robustness · RobustnessBias

扰动下的鲁棒性评分。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.signal_driven.robustness import RobustnessBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(RobustnessBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.structure_prior · StructurePriorBias

结构/对称先验。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.domain.structure_prior import StructurePriorBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(StructurePriorBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.tabu · TabuSearchBias

只读禁忌评分；记忆记录已提交步骤中接纳的提案，通过 BiasModule 参与回滚与恢复。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.tabu_search import TabuSearchBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(TabuSearchBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## bias.uncertainty_exploration · UncertaintyExplorationBias

优先探索高不确定区域。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。候选布局须匹配该领域Bias；依赖population/历史/指标的Bias须由相应所有者提供数据，缺数据不代表完成该算法。

```python
from nsgablack.bias.algorithmic.signal_driven.uncertainty_exploration import UncertaintyExplorationBias
from nsgablack.bias import BiasModule
bias_module = BiasModule()
bias_module.add(UncertaintyExplorationBias())
solver.set_bias_module(bias_module)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界： Bias只改软评分；不因类名含PSO/CMA/梯度/贝叶斯就声称执行完整同名优化算法。

## tool.catalog_curate · Catalog AI 资料整理

依据受限源码证据增量整理组件用途、输入输出、装配思路与资料缺项；生成说明独立保存，不改运行契约。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.catalog.curate import curate_packets
# packets/store/generator来自部署者的独立writer配置；不从浏览器接收凭据。
def curate_selected(packets, store, generator, model):
    return curate_packets(packets, store, generator, model=model,
        limit=1, workers=1, keys=('adapter.nsga2',))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：这是writer任务调用片段；示例不调用模型、不配置API key、不把网页reader升格为写权限。

## tool.unit_binding · UnitBinding

**什么时候用：** 使用内置算法的默认结构时，通常无需手动传 UnitBinding。需要增加成员年龄、保留领域标签或替换符合算法契约的结构时，才把自己的 builder/数据 codec 绑定给实际 Adapter。不要为了给模型参数命名而自定义 Unit；那属于候选 Representation/Codec。

**先准备什么：** 先明确算法要求的结构 schema。NSGA2 使用 PopulationUnit，运行中的数值候选为 `(n,d)`，反馈为 `(n,m)` 和 `(n,)`。builder 必须声明 schema、支持所需构建操作，并实现 `build/dump/restore`；现成 `PopulationUnitBuilder` 已提供这些。构造 binding 不需要传候选矩阵、反馈、Solver 或 ResourceContext。

**放在哪：** 在 Case 的 `adapter/` 工厂给 NSGA2 传 `unit_binding=...`；自定义结构和 builder 可放在该 Case 的 `pipeline/population.py`。正式 `assembled_ga_vns` 正是这样保存结构声明，再由 `adapter/composition.py` 绑定给 GA。

**接入步骤：** 以下展示显式绑定默认种群结构；所有变量均由函数内创建，候选仍由实际 Problem 的维数决定：

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import (
    PopulationUnitBuilder, UniformInitializer, GaussianMutation,
)
from nsgablack.units import UnitBinding

def build_ga():
    return NSGA2Adapter(
        name="ga", population_size=12, offspring_size=12,
        initializer=UniformInitializer(low=-4.0, high=4.0),
        mutator=GaussianMutation(sigma=0.45),
        unit_binding=UnitBinding(PopulationUnitBuilder()),
    )
```

需要年龄字段时，按下一节实现 `AgePopulationBuilder`，在 Case 工厂导入它并仅把最后一项改为 `unit_binding=UnitBinding(AgePopulationBuilder())`；现有 Project 的 GA 子实例已采用此绑定。Adapter 第一次真正初始化/操作种群时调用自己的 `ensure_unit()` 建立结构，此后复用同一运行实例；用户不要在装配、目录预览或观察钩子中手动调用 ensure_unit。fresh reset 使结构失效，暂停继续不重建，恢复已有结构使用 `restore` 数据 codec，不重放 builder 或修复候选。

**运行入口：** `python examples/cases/assembled_ga_vns/run_project.py --group plan` 使用现有正式 Case 及其 AgePopulationBuilder；本段默认 builder 示例仅用于说明替换位置，本轮没有运行或切换原 Case 的绑定。

**怎样判断接对：** 构造返回的 `ga.algorithm_unit` 应为 `None`；`ga.unit_binding.describe()` 可在不构建 Unit 的情况下读 schema 和 binding 身份。实际运行后，从正式 `results/plan/trace.json` 的 `records[*].units` 读取 GA 的 `structure_exists/population_members/member_age`，而非为了检查而创建 Unit。每个 Adapter 拥有自己的运行 Unit；UnitBinding 的 `dump/restore` 保存算法结构数据，模型 Codec 的 `encode/decode` 解释模型候选，两种职责不能互换。

**配套组件 key：** `adapter.nsga2`、`repr.unit_population`、`tool.population_unit`、`tool.population_change`；模型候选编码另看实际 Representation/Codec 条目。

**接口依据与验证状态：** `units/contracts.py::UnitBinding`、`adapters/unit_backed.py`、`examples/cases/assembled_ga_vns/cases/hybrid_search/pipeline/population.py` 与 `adapter/composition.py`；仅源码核对，本轮未构造运行 Unit。

## tool.population_unit · PopulationUnit

**什么时候用：** 种群算法除了候选、反馈和 token，还需要维护每成员的领域字段，例如“连续保留了几次环境选择”。只使用内置 X/F/V/token 时无需自定义；加入行字段时应让 Unit 自己声明维护规则，不能让 Adapter 按字段名称猜含义。

**先准备什么：** 成员矩阵是 `(n,d)`，目标 `(n,m)`、违反量 `(n,)`、candidate_tokens 长度为 `n`；新增 `member_age` 也必须是 `(n,)`。正式 GA/VNS 例子的候选 `d=2`、目标 `m=1`。年龄定义为“旧成员经过一次环境选择并保留则加 1，新成员为 0”，不是运行的全局 generation。

**放在哪：** Case `pipeline/population.py` 定义结构与 builder；Case `adapter/composition.py` 给 GA 传 `UnitBinding(AgePopulationBuilder())`。以下复用 `assembled_ga_vns` 的实际实现，成员选择和提案仍由原 NSGA2 负责：

**接入步骤：**

```python
from dataclasses import dataclass, field
import numpy as np
from nsgablack.representation import PopulationUnitBuilder
from nsgablack.units import PopulationUnit, PopulationChange, UnitSchema

@dataclass
class AgePopulationUnit(PopulationUnit):
    member_age: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=int))
    member_fields = ("member_age",)
    schema = UnitSchema(
        "assembled_ga_vns.age_population",
        required_fields=(*PopulationUnit.schema.required_fields, "member_age"),
        candidate_projection=False,
    )

    def on_members_changed(self, change: PopulationChange):
        increment = int(change.operation == "selection")
        return {"member_age": np.asarray([
            0 if previous is None else self.member_age[previous] + increment
            for previous in change.previous_member_indices
        ], dtype=int)}

    def validate(self):
        super().validate()
        if self.member_age.dtype.kind not in "iu" or np.any(self.member_age < 0):
            raise ValueError("member_age must contain nonnegative integers")

class AgePopulationBuilder(PopulationUnitBuilder):
    unit_type = AgePopulationUnit
    compatible_schemas = (PopulationUnit.schema,)
```

接着在 `adapter/composition.py` 绑定它。下段 `settings` 是该 Case 的 `DemoConfig`，由 `build_solver.py` 传入，提供 `population_size` 和 `ga_sigma`；`build_ga` 的返回值用作原组合工厂中的 GA 子实例，VNS 与 Router/计划的接线仍沿用该文件：

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation
from nsgablack.units import UnitBinding
from ..pipeline.population import AgePopulationBuilder

def build_ga(settings):
    return NSGA2Adapter(
        name="ga", population_size=settings.population_size,
        offspring_size=settings.population_size,
        initializer=UniformInitializer(low=-4.0, high=4.0),
        mutator=GaussianMutation(sigma=settings.ga_sigma),
        unit_binding=UnitBinding(AgePopulationBuilder()),
    )
```

`PopulationChange` 由成员操作传入，不需用户手工构造。它的 `previous_member_indices` 对应最终行：整数表示来自原 Unit 的成员，None 表示新成员；`incoming_member_indices` 可定位本次 incoming 的候选、反馈、token、metadata 和 provenance。钩子只读取旧字段与这些脱离只读输入，返回所有 `member_fields` 的更新映射；不得直接写 self、求值或重新决定成员去留。基类将候选/反馈/token 与扩展字段一起对齐、校验草稿，通过后才发布。局部替换不增加其他成员的年龄，单纯刷新反馈也不构成一次环境选择。

**运行入口：** `python examples/cases/assembled_ga_vns/run_project.py --group plan`。原正式 Case 已绑定上述 AgePopulationBuilder，本轮只修改说明，没有运行算法。

**怎样判断接对：** 完整运行后读 `results/plan/trace.json` 的 GA `records[*].units`：`population_members` 与 `member_age` 长度一致，`member_age_min/max` 由该字段计算。按此规则，旧成员 `[A,B,C]` 年龄 `[10,4,7]`，若环境选择结果为 `[C,D,A]`，应得到 `[8,0,11]`；这是规则示意，不是本轮运行结果。需要准确成员身份时从所属 Adapter 的 `get_population_solution_refs(control)` 读取，不能用数值相等或年龄反推 token。Unit 的 objectives/violations 是算法选择视图，原始反馈仍按池引用读取；Unit 不是模型的编码/解码器，也不持有 Provider、RNG 或全局资源授权。

**配套组件 key：** `tool.unit_binding`、`tool.population_change`、`repr.unit_population`、`adapter.nsga2`、`tool.solution_pool`。

**接口依据与验证状态：** `units/collections.py::PopulationUnit`、`units/population_operations.py::PopulationChange`、`docs/architecture/UNIT_MEMBER_OPERATIONS_CN.md` 和上述正式 Case；仅源码核对。成员字段复用 builder 的数据 codec 随所属 Adapter 回滚/恢复，不通过重放维护钩子重建历史。

## tool.bo_unit · BayesianOptimizationUnit

由实际 Adapter 按需持有的算法结构，经显式 codec 回滚与恢复。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import BayesianOptimizationUnit, UnitBinding, StructureBuildRequest
from nsgablack.representation.bayesian_builder import BayesianUnitBuilder
binding = UnitBinding(BayesianUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {}}))
assert isinstance(unit, BayesianOptimizationUnit)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：单独演示结构与codec，不持有模型服务、RNG或Provider。正式运行由相应Adapter惰性创建；新增关系需显式维护。

## tool.cma_unit · CMAUnit

由实际 Adapter 按需持有的算法结构，经显式 codec 回滚与恢复。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import CMAUnit, UnitBinding, StructureBuildRequest
from nsgablack.representation.cmaes_builder import CMAUnitBuilder
binding = UnitBinding(CMAUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'mean': np.zeros(2), 'covariance': np.eye(2), 'path_c': np.zeros(2), 'path_sigma': np.zeros(2)}}))
assert isinstance(unit, CMAUnit)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：单独演示结构与codec，不持有模型服务、RNG或Provider。正式运行由相应Adapter惰性创建；新增关系需显式维护。

## tool.map_elites_unit · MapElitesUnit

由实际 Adapter 按需持有的算法结构，经显式 codec 回滚与恢复。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import MapElitesUnit, UnitBinding, StructureBuildRequest
from nsgablack.representation.map_elites_builder import MapElitesUnitBuilder
binding = UnitBinding(MapElitesUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {}}))
assert isinstance(unit, MapElitesUnit)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：单独演示结构与codec，不持有模型服务、RNG或Provider。正式运行由相应Adapter惰性创建；新增关系需显式维护。

## doc.authoritative_examples · AUTHORITATIVE_EXAMPLES

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/project/AUTHORITATIVE_EXAMPLES.md`。

内容用途：权威可运行示例与基线参考。 / Authoritative runnable examples and baseline references.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.component_examples_index · COMPONENT_EXAMPLES_INDEX

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/indexes/COMPONENT_EXAMPLES_INDEX.md`。

内容用途：组件到示例的映射索引。 / Component-to-example mapping index.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.index_manual · INDEX_MANUAL

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/indexes/INDEX_MANUAL.md`。

内容用途：文档与模块导航索引。 / Manual index for docs and module navigation.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.getting_started · User Guide: getting_started

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/getting_started.rst`。

内容用途：首个可运行流程的入门指南。 / Getting started guide for first runnable workflow.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.project_scaffold · User Guide: PROJECT_SCAFFOLD

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/PROJECT_SCAFFOLD.md`。

内容用途：项目脚手架使用与边界说明。 / Project scaffold usage and boundary guidance.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.catalog · User Guide: catalog

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/catalog.md`。

内容用途：Catalog 搜索/列表/查看的用法与模式。 / Catalog search/list/show usage and patterns.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.context_contracts · User Guide: CONTEXT_CONTRACTS

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/CONTEXT_CONTRACTS.md`。

内容用途：组件的 Context 契约规则。 / Context contract rules for components.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.context_field_rules · User Guide: CONTEXT_FIELD_RULES

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/CONTEXT_FIELD_RULES.md`。

内容用途：Context 字段命名与治理规则。 / Context field naming and governance rules.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.run_inspector · User Guide: RUN_INSPECTOR

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/RUN_INSPECTOR.md`。

内容用途：Run Inspector 使用与诊断流程。 / Run Inspector usage and diagnostics workflow.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.plugin_system · User Guide: PLUGIN_SYSTEM

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/PLUGIN_SYSTEM.md`。

内容用途：插件生命周期、契约与接线模式。 / Plugin lifecycle, contracts, and wiring patterns.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.plugin_selection · User Guide: PLUGIN_SELECTION

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/PLUGIN_SELECTION.md`。

内容用途：按场景选择插件组合的方法。 / How to select plugin combinations by scenario.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.parallel_evaluation · User Guide: parallel_evaluation

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/parallel_evaluation.md`。

内容用途：并行评估配置与安全措施。 / Parallel evaluation setup and safeguards.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.surrogate_workflow · User Guide: surrogate_workflow

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/SURROGATE_CAPABILITY_PATTERN.md`。

内容用途：代理辅助优化流程。 / Surrogate-assisted optimization workflow.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.surrogate_cheatsheet · User Guide: surrogate_cheatsheet

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/surrogate_cheatsheet.md`。

内容用途：代理模型配置速查表。 / Quick reference for surrogate configuration.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.signal_driven_bias · User Guide: signal_driven_bias

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/signal_driven_bias.md`。

内容用途：信号驱动 Bias 设计与接入。 / Signal-driven bias design and integration.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.how_to_build_optimization · User Guide: HOW_TO_BUILD_OPTIMIZATION

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/HOW_TO_BUILD_OPTIMIZATION.md`。

内容用途：分步构建优化流程。 / Step-by-step optimization build process.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.optimization_strategies · User Guide: optimization_strategies

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/optimization_strategies.md`。

内容用途：策略与 Adapter 选型参考。 / Strategy and adapter selection reference.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.extension_contracts · User Guide: EXTENSION_CONTRACTS

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/EXTENSION_CONTRACTS.md`。

内容用途：扩展契约与兼容性要求。 / Extension contracts and compatibility requirements.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.enhanced_search · User Guide: enhanced_search

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/enhanced_search.md`。

内容用途：Catalog 增强搜索技巧。 / Enhanced catalog search techniques.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.db_event_logging · User Guide: DB_EVENT_LOGGING

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/DB_EVENT_LOGGING.md`。

内容用途：数据库事件日志集成指南。 / Database event logging integration guide.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.guides.decoupling_problem · Guide: DECOUPLING_PROBLEM

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/guides/DECOUPLING_PROBLEM.md`。

内容用途：将问题语义与运行过程解耦。 / Decouple problem semantics from runtime process.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.guides.decoupling_representation · Guide: DECOUPLING_REPRESENTATION

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/guides/DECOUPLING_REPRESENTATION.md`。

内容用途：表示层管线解耦实践。 / Representation pipeline decoupling practice.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.guides.decoupling_bias · Guide: DECOUPLING_BIAS

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/guides/DECOUPLING_BIAS.md`。

内容用途：Bias 解耦与偏好设计：说明哪些逻辑应放在 bias，哪些应放在 adapter/pipeline。 / Bias decoupling and preference design; explains what should stay in bias vs adapter/pipeline.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.guides.decoupling_adapter · Guide: DECOUPLING_ADAPTER

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/guides/DECOUPLING_ADAPTER.md`。

内容用途：Adapter 解耦与流程接线。 / Adapter decoupling and process wiring.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.guides.decoupling_capabilities · Guide: DECOUPLING_CAPABILITIES

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/guides/DECOUPLING_CAPABILITIES.md`。

内容用途：能力层拆解方法论。 / Capability-layer decomposition methodology.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.guides.production_walkthrough · Guide: PRODUCTION_SCHEDULING_WALKTHROUGH

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/guides/PRODUCTION_SCHEDULING_WALKTHROUGH.md`。

内容用途：生产排程端到端实战。 / Production scheduling walkthrough (end-to-end).

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.cases.production_scheduling · Case: production_scheduling

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/cases/production_scheduling.md`。

内容用途：生产排程案例文档。 / Production scheduling case documentation.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.quickstart · Quickstart

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/quickstart.rst`。

内容用途：首次安装与运行的快速入口。 / Quickstart entry for first setup and run.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.readme · Docs README

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/README.md`。

内容用途：文档中心与导航总览。 / Docs hub and navigation overview.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.algorithm_decomposition_hands_on · ALGORITHM_DECOMPOSITION_HANDS_ON

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/guides/ALGORITHM_DECOMPOSITION_HANDS_ON.md`。

内容用途：分解实践教程（含步骤）。 / Hands-on decomposition tutorial with practical steps.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.bias_system · User Guide: bias_system

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/bias_system.md`。

内容用途：Bias 系统设计与组合指南。 / Bias system design and composition guide.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.bias_baby_guide · User Guide: bias_baby_guide

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/bias_baby_guide.md`。

内容用途：新手友好的 Bias 编写指南。 / Beginner-friendly bias writing walkthrough.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.external_api_navigation · User Guide: external_api_navigation

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/external_api_navigation.md`。

内容用途：外部 API 导航与检索指南。 / External API navigation and lookup guide.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.indexes.api_index · Indexes: API_INDEX

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/indexes/API_INDEX.md`。

内容用途：用于组件检索的 API 索引。 / API index for component lookup.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.indexes.bias_index · Indexes: BIAS_INDEX

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/indexes/BIAS_INDEX.md`。

内容用途：Bias 模块索引。 / Bias index for bias module lookup.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.indexes.tools_index · Indexes: TOOLS_INDEX

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/indexes/TOOLS_INDEX.md`。

内容用途：运维脚本工具索引。 / Tools index for operational scripts.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.redis_context_backend · User Guide: REDIS_CONTEXT_BACKEND

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/REDIS_CONTEXT_BACKEND.md`。

内容用途：Redis Context 后端配置、TTL 策略与排障。 / Redis context backend setup, TTL policy, and troubleshooting.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.redis_context_snapshot_workflow · User Guide: REDIS_CONTEXT_SNAPSHOT_WORKFLOW

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/REDIS_CONTEXT_SNAPSHOT_STORES.md`。

内容用途：Redis 下 ContextStore 与 SnapshotStore：契约、键流、TTL 与排障。 / ContextStore vs SnapshotStore with Redis: contracts, key flow, TTL, and troubleshooting.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.user_guide.decision_replay_engine · User Guide: DECISION_REPLAY_ENGINE

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/user_guide/DECISION_REPLAY_ENGINE.md`。

内容用途：决策路径回放指南：原因/证据结构与用法。 / Decision-path replay guide with reason/evidence schema and usage.

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## doc.architecture.catalog_usage · 当前架构 Catalog 使用说明

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/architecture/CATALOG_USAGE_CN.md`。

内容用途：从概念定位装配角色、实际组件、方法、边界和标准 Case；不把索引声明当作数学证明。

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## example.phi_bundle_image_search · PhiBundle Image Search

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准跨框架 Project：nsgablack 搜索表示公式包，独立 mlblack Trainer Case 负责拟合与指标。

```bash
python examples/cases/phi_bundle_image_search/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.anomaly_detection_de · Anomaly Detection with DE

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：用差分进化搜索异常检测配置。

```bash
python examples/cases/anomaly_detection/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.arima_order_search_de · ARIMA Order Search with DE

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：搜索 ARIMA 阶数。

```bash
python examples/cases/arima_order_search/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.causal_discovery_pc_lingam · Causal Discovery

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：把因果结构发现建模为黑盒优化。

```bash
python examples/cases/causal_discovery/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.classification_threshold_calibration · Classification Threshold Calibration

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：多目标校准分类阈值。

```bash
python examples/cases/classification_threshold_calibration/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.gmm_em_vs_de · GMM EM vs DE

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：比较 GMM 的 EM 与差分进化路线。

```bash
python examples/cases/gmm_em_vs_de/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.l0_distributed_worker · L0 Distributed Worker

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：演示 Project L0 授权与分布式 Worker。

```bash
python examples/cases/l0_distributed_worker/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.residual_boosting · Residual Boosting

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准跨框架 Case：外层搜索残差提升装配。

```bash
python examples/cases/residual_boosting/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.tsp_permutation_sa · TSP / VRP Permutation Search

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：排列表示下的 TSP/VRP 搜索。

```bash
python examples/cases/tsp_vrp/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.algorithm_units_candidate_search · Candidate Unit Pipeline

本条目是正式示例项目入口，不新建另一套求解循环。

用途：正式 Unit Case：问题管线保障候选可行性，算法管线构建结构，Adapter 执行搜索。

```bash
python examples/cases/algorithm_units/cases/candidate_search/run_solver.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## example.algorithm_units_symbolic_beam · Symbolic Beam Unit Pipeline

本条目是正式示例项目入口，不新建另一套求解循环。

用途：正式 Unit Case：问题管线保障候选可行性，算法管线构建结构，Adapter 执行搜索。

```bash
python examples/cases/algorithm_units/cases/symbolic_beam/run_solver.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## tool.problem_repair · ProblemRepair

问题修复 Protocol：修复候选并只读验证最终语义版本，与 UnitRepair 共同验收。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.representation import RepresentationPipeline
class NonnegativeRepair:
    def repair(self, candidate, context): return np.maximum(candidate, 0.)
    def validate(self, candidate, context): return bool(np.all(candidate.as_array() >= 0.))
pipeline = RepresentationPipeline(repair=NonnegativeRepair())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：repair处理数值草稿；validate核对最终语义候选，不在修复中调用Problem.evaluate。

## tool.unit_repair · UnitRepair

Unit 修复 Protocol：修改 codec 草稿，验证最终候选与结构；部分接纳投影在 Adapter disposition 之后执行，保留已整理坐标。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import UnitRepair
class KeepCompatibleUnit:
    def repair(self, unit, evidence, context): return evidence.after
    def validate(self, unit, evidence, context): return len(evidence.after.semantic_states) > 0
component = KeepCompatibleUnit()
assert isinstance(component, UnitRepair)
adapter.set_unit_repair(component)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：这是无变化协议示例，不声称修复特定算法不变量。真实实现须验证半径、父边等结构，并与ProblemRepair经JointRepairPolicy共同验收；部分接纳需另实现project_admission。

## tool.joint_repair_policy · JointRepairPolicy

显式启用 ProblemRepair/UnitRepair 共同验收；有限轮协调，零接纳恢复局部状态；拒绝后串行推进须整体规划、事务执行。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core.composable_solver import ComposableSolver
from nsgablack.representation import JointRepairPolicy
solver = ComposableSolver(problem, adapter=adapter, representation_pipeline=pipeline,
    joint_repair_policy=JointRepairPolicy(max_rounds=2, on_rejection='stop'))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：problem repair和unit repair必须均提供只读validate；次数耗尽不能以最后修复者宣布成功。

## tool.change_request · ChangeRequest

NSGA/VNS/MOEA-D 普通完整变化函数的只读输入：父候选矩阵、精确引用、Unit参数、max_outputs及调用期request.pool。读取来源保持精确版本；批量消费者明确许可孩子数量，池访问不进入checkpoint。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import VNSAdapter
def change(request, *, rng):
    return request.candidate + rng.normal(0., 0.1, request.candidate.shape)
adapter = VNSAdapter(change=change)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.change_result · ChangeResult

普通 change 的可选返回：单个候选、可选精确 source_refs 与 PoolOutput 目标。读取依赖自动保留，声明来源不能绕过任务范围；评估、硬接纳与池事务仍由控制面执行。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import VNSAdapter, ChangeResult, PoolOutput
def change(request, *, rng):
    child = request.candidate + rng.normal(0., 0.1, request.candidate.shape)
    return ChangeResult(child, outputs=(PoolOutput('trials', create=True),))
adapter = VNSAdapter(change=change)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：只把已评估且接纳的精确版本送入trials；这不是最终Unit胜出者。

## tool.pool_output · PoolOutput

change 的具名普通引用集合输出声明：缺省要求目标已存在，create=True 允许控制面在接纳后创建；声明本身不写池，不允许把候选追加进算法投影视图。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import VNSAdapter, ChangeResult, PoolOutput
def change(request, *, rng):
    child = request.candidate + rng.normal(0., 0.1, request.candidate.shape)
    return ChangeResult(child, outputs=(PoolOutput('trials', create=True),))
adapter = VNSAdapter(change=change)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：只把已评估且接纳的精确版本送入trials；这不是最终Unit胜出者。

## tool.pool_edit · PoolEdit

普通子池的精确成员替换计划，冻结目标身份和revision；replace_members(create=True)也可冻结缺失目标并创建。经change的静态edits或每批更新后maintenance提交，复用生存choose副结果的同一计划事务，不直接写算法结果视图。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import ChangeResult
def change(request, *, rng):
    members = request.pool.main(stage='accepted').take(range(2))
    edit = request.pool.replace_members('elite', members.refs, create=True)
    return ChangeResult(request.candidate, edits=(edit,))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：至少2个已发布引用；额外母池读取和elite写入须显式授权，计划只在对应提案接纳并提交后生效。

## tool.change_selection · ChangeSelection

公开Pool的兼容类型名：调用内有序精确引用选择；保留旧take/random/where/top用法，复用同一引用存储与授权，不产生第二套候选集合。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
def inspect_selection(request, *, rng):
    source = request.pool.main(stage='accepted')
    sample = source.sample(min(2, len(source)), rng=rng)
    return sample.refs, sample.values
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：位于拥有合法ChangePool作用域的回调；任务内读取母池须显式change_allow_main。

## tool.pool · Pool

调用内候选集合：chosen执行纯选择，Pool(parent=..., name=...)创建空草稿，inject追加或显式精确替换。GA生存选择或成员维护将具名副Pool草稿交给原池事务；不改raw、不扩读权限、不创建调度器。旧主Pool和具名副Pool映射返回仍支持。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import Pool, NSGA2Adapter, NSGA2Config
population_size = 8
def choose(pool, *, rng):
    kept = pool.take(range(population_size))
    Pool(parent=kept, name='elite').inject(kept.take(range(2)), replace=True)
    return kept
adapter = NSGA2Adapter(NSGA2Config(population_size=population_size), selector=choose)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：这是按考察顺序留存的教学规则，不宣称Pareto最优。输入必须至少有8行；在PoolTask中写elite还须显式授权该集合。

## tool.pool_partition · partition

对非空Pool调用一次普通choose，空输入不调用；返回所选位置与有序补集两个Pool。重复引用的不同位置分别处理，结果映回原调用者坐标；不改成员、不建子池、不求值。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import partition
def first_two(pool, *, rng): return pool.take(range(min(2, len(pool))))
def split(pool, *, rng):
    selected, remaining = partition(pool, by=first_two, rng=rng)
    return selected, remaining
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：partition按本次输入位置取补集，不以SolutionRef差集代替重复位置语义。

## tool.change_batch_result · ChangeBatchResult

一次完整变化的有序多个ChangeResult；每个孩子独立派生身份、修复、预算和接纳坐标。实际消费者给出max_outputs，不能让单候选算法隐式接收任意批量。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import NSGA2Adapter, ChangeBatchResult, ChangeResult
def change(request, *, rng):
    parent = request.parents[0]
    noise = rng.normal(0., 0.1, parent.shape)
    children = (ChangeResult(parent + noise), ChangeResult(parent - noise))
    return ChangeBatchResult(children[:request.max_outputs])
adapter = NSGA2Adapter(change=change)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.pool_maintenance_request · PoolMaintenanceRequest

实际叶Adapter更新后的只读维护输入：受限来源、本批accepted及有序最终种群members；轨迹算法members为None。二者保留各自选择反馈，合并历史显式使用raw；返回PoolEdit与同一Authority/manifest提交，不开放其他pending或重复求值。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
def maintain(request, *, rng):
    if request.members is None:
        raise ValueError('requires a population result')
    elite = request.members.take(range(min(2, len(request.members))))
    return (request.pool.replace_members('elite', elite.refs, create=True),)
adapter.set_pool_maintenance(maintain)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：members是算法最终槽位成员；accepted是本批硬接纳集合，两者不相同。elite需要本任务写入声明。

## tool.operator_binding · OperatorBinding

独立初始化、变化、选择或结构修复的身份与状态绑定；由实际叶 Adapter 一并 checkpoint/回滚，有状态组件只允许一个绑定所有者。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import GaussianMutation
adapter = NSGA2Adapter()
adapter.set_mutator(GaussianMutation(sigma=0.1))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：叶Adapter拥有绑定组件的事务/codec；使用setter，由Adapter创建OperatorBinding，用户不直接改内部绑定字典。

## tool.parent_selection_request · ParentSelectionRequest

父代选择输入：有序精确种群引用、脱离的只读 rank/crowding、请求数量及轻量调用上下文。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import NSGA2Adapter
class FirstParents:
    stateless = True
    def checkpoint_identity(self): return {'name': 'first_parents', 'version': 1}
    def select(self, request, *, pool, rng):
        return tuple(request.population_refs[i % len(request.population_refs)] for i in range(request.count))
adapter = NSGA2Adapter(parent_selector=FirstParents())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：父代选择返回精确引用，可有放回；不是生存选择的局部行索引协议。

## tool.mixed_pool_parent_selector · MixedPoolParentSelector

从本种群 rank/crowding 锦标赛与已发布具名子池混合抽取父代，返回准确引用；不修改环境选择或创建精英池。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import MixedPoolParentSelector, NSGA2Adapter
adapter = NSGA2Adapter()
adapter.set_parent_selector(MixedPoolParentSelector('elite', pool_fraction=0.5))
# Publish a nonempty named 'elite' pool before the first parent-selection call.
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## repr.gaussian_mutation · GaussianMutation

**什么时候用：** 连续参数需要逐坐标高斯扰动，且所选 Adapter 明确消费 mutator。用于 NSGA2 时它是变化中的变异；用于 DE 时在差分 trial 后执行，不能据此把 DE 解释为独立高斯搜索。VNS 要随邻域改变尺度时优先选 `repr.context_gaussian`。

**先准备什么：** 输入是数值候选 shape `(d,)`；`sigma` 的单位与变量相同，例如变量范围 `[-4,4]` 时 `sigma=0.2` 表示每个坐标的扰动标准差，而不是 20% 的变异概率。父候选由 Adapter 提供，用户无需在装配期随机造一个候选测试维数。

**放在哪：** Case 的 `adapter/` 工厂把组件绑定到实际所有者。若同一 Case 中有 GA 和 VNS，分别创建变异器实例；有 RNG 的同一对象不能同时归两个 Adapter 或 Pipeline 所有。

**接入步骤：**

```python
from nsgablack.adapters import NSGA2Adapter
from nsgablack.representation import UniformInitializer, GaussianMutation

def build_adapter():
    return NSGA2Adapter(
        population_size=16, offspring_size=16,
        initializer=UniformInitializer(low=-4.0, high=4.0),
        mutator=GaussianMutation(sigma=0.2),
    )
```

再由 Case 的问题管线提供边界修复，例如 `RepresentationPipeline(repair=ClipRepair(low=-4.0, high=4.0))`。这是两个不同步骤：变异先提出草稿，预算裁剪后问题修复得到实际送评候选；不要在 mutator 中再手动调用 Problem.repair。

**运行入口：** 现有正式 `examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py` 为 GA 绑定了 GaussianMutation；入口是 `python examples/cases/assembled_ga_vns/run_project.py`。上面数值是装配示意，不宣称与原 Case 配置完全相同。

**怎样判断接对：** 正式宿主 `results/trace.json` 的 `initial.operation_contracts` 记录实际 Adapter 的绑定组件；候选通过池引用读取后的 `CandidateBatch.numeric_matrix` 应保留 `d` 列。`GaussianMutation.mutate` 返回新的同维数值数组，不原位修改已评估父成员；RNG 状态由其 `get_state/set_state` 参与所属 Adapter 的恢复。`sigma` 改变提案尺度，不返回目标，目标仍以修复后候选的正式求值为准。

**配套组件 key：** `adapter.nsga2`、`repr.continuous`、`repr.pipeline`；动态局部尺度见 `repr.context_gaussian`。ClipRepair 的 Catalog key 以当前目录实际条目为准，不能把类名自行当成键。

**接口依据与验证状态：** `representation/continuous.py`、上述正式 GA 工厂；仅源码核对。

## tool.selection_request · SelectionRequest

评估后只读行选择请求：survivor 保留成员、replacement 比较槽位、candidate 选本批候选、proposal_order 重排本批；不承担父代引用选择或硬接纳。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import DifferentialEvolutionAdapter
class FirstOffered:
    stateless = True
    def checkpoint_identity(self): return {'name': 'first_offered', 'version': 1}
    def select(self, request, *, rng):
        if request.purpose != 'replacement': raise ValueError('replacement only')
        return list(range(request.count))
adapter = DifferentialEvolutionAdapter(selector=FirstOffered())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：示例按次序选，不声称更优；生产规则需按purpose解释评分并返回恰好count个合法局部索引。

## tool.feasibility_first_selection · FeasibilityFirstSelection

显式可行性优先行选择：使用算法提供的 scores 或指定目标；不自动装配，也不等价于 NSGA Pareto 选择、Metropolis 或硬可行性接纳。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import DifferentialEvolutionAdapter, FeasibilityFirstSelection
adapter = DifferentialEvolutionAdapter(selector=FeasibilityFirstSelection())
# Explicitly overrides target/trial replacement; omit selector to retain the native policy.
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.runtime_surface_tracker · RuntimeSurfaceTrackerPlugin

将装配、运行和产物记录写入正式运行面。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import RuntimeSurfaceTrackerPlugin
solver.add_plugin(RuntimeSurfaceTrackerPlugin())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.checkpoint_resume · CheckpointResumePlugin

代级检查点与失败后恢复。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import CheckpointResumePlugin, CheckpointResumeConfig
solver.add_plugin(CheckpointResumePlugin(config=CheckpointResumeConfig(auto_resume=True)))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.monte_carlo_eval · MonteCarloEvaluationProviderPlugin

**什么时候用：** 同一候选在随机场景下会有不同结果，需要重复求值后用均值或损失上尾均值作为正式原始目标，并把波动、最小值和最大值交给报告或风险偏好。插件自己不创造业务场景或噪声；确定性 Problem 重复求值仍是同一结果。

**先准备什么：** Problem 的真实接口仍是 `evaluate(candidate)`，每次返回 `m` 个目标；约束沿用 `evaluate_constraints`，没有另一个必须实现的随机评价方法。正式 `risk_bias` Case 的候选是 `(2,)`，一个目标，每次 evaluate 使用随机噪声。以下就是其问题含义，放在 Case 的 `problem/risk_cost.py`：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem

class RiskCostProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="risk_cost", dimension=2,
                         bounds=[(-2, 2)] * 2, objectives=["scenario_cost"])

    def evaluate(self, x):
        x = np.asarray(x)
        return float(np.sum((x - 1) ** 2)
                     + (0.1 + abs(x[0])) * np.random.normal())
```

**放在哪：** 场景损失留在 `problem/`；`evaluation/risk_evaluation.py` 提供下面挂载函数；规范 `build_solver.py` 构造同一 Solver 后调用一次。`solver` 是该函数显式接收的实例，Problem、Pipeline 和 Adapter 已由同 Case 工厂装配，资源来自外层 Project L0。

**接入步骤：** 推荐按正式 risk_bias Case 使用插件 attach 自动登记 Provider：

```python
from nsgablack.plugins.evaluation.monte_carlo_evaluation import (
    MonteCarloEvaluationProviderPlugin, MonteCarloEvaluationConfig,
)

def attach_scenario_evaluation(solver):
    plugin = MonteCarloEvaluationProviderPlugin(
        config=MonteCarloEvaluationConfig(
            mc_samples=8, reduce="mean", cvar_alpha=0.25, random_seed=7,
        ))
    solver.add_plugin(plugin)
    return plugin
```

若现有装配层统一手动登记 Evaluation Provider，可将上面 `solver.add_plugin(plugin)` **替换为** `solver.register_evaluation_provider(plugin.create_provider())`。这两种方式二选一：使用 add_plugin 就已自动登记，不能再登记同一 Provider。`mc_samples/reduce/cvar_alpha/random_seed` 属于 Config；插件本体另接 `name/config/priority`。

Provider 对每个候选调用 Problem `mc_samples` 次，得到 `(S,m)` 样本矩阵；`reduce="mean"` 返回各目标均值，`reduce="cvar"` 返回最小化损失中最坏 `cvar_alpha` 比例的样本均值。把 `mc_samples` 从 8 改为 32，会把每候选的场景 Problem 调用数变为 4 倍，影响计算成本；它不是种群容量、逻辑提交步数，也不能用候选行数直接代替场景调用数。RiskBias 是可选消费者，插件单独使用也会交付原始聚合反馈与统计。

**运行入口：** `python examples/cases/risk_bias/run_project.py` 使用上述真实 Problem 和场景评估工厂；当前 Case 最大 2 个提交步、每候选 8 次场景求值。本轮未执行命令。

**怎样判断接对：** 实际反馈消费者收到的 `feedback.items[i].metrics` 应含当前候选的 `mc_samples` 及 `mc_mean/mc_std/mc_min/mc_max`，四个统计数组各为 `(m,)`。一批 `feedback.raw_objectives` 是 `(n,m)` 的原始聚合结果；挂载 Bias 后 `feedback.objectives` 是选择视图，统计仍随各自候选交付。使用 `reduce="mean"` 时原始目标应对应 mc_mean，不能把 RiskBias 的近似风险评分或其它候选的全局统计当成原始目标。仅插件构造或 Provider 登记完成，不代表已经进行了这些场景求值。

**配套组件 key：** `bias.risk`、`bias.robustness` 是可选消费者；正式宿主还使用 `adapter.trust_region_dfo`、`repr.pipeline`、`solver.composable`。其它需要候选统计的正式反馈消费者也可读取这些指标，不要求挂载某个 Bias。

**接口依据与验证状态：** `plugins/evaluation/monte_carlo_evaluation.py`、`examples/cases/risk_bias/cases/risk_bias/problem/risk_cost.py`、`evaluation/risk_evaluation.py` 与 `build_solver.py`；仅源码核对，没有启动场景评估。

## plugin.surrogate_eval · SurrogateEvaluationProviderPlugin

代理辅助评估并输出不确定性指标。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import SurrogateEvaluationProviderPlugin, SurrogateEvaluationConfig
solver.register_evaluation_provider(SurrogateEvaluationProviderPlugin(config=SurrogateEvaluationConfig()).create_provider())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.multi_fidelity_eval · MultiFidelityEvaluationProviderPlugin

多保真评估：低/高保真切换。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import MultiFidelityEvaluationProviderPlugin, MultiFidelityEvaluationConfig
solver.register_evaluation_provider(MultiFidelityEvaluationProviderPlugin(config=MultiFidelityEvaluationConfig()).create_provider())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.newton_solver · NewtonSolverProviderPlugin

Newton 求解插件：评估阶段的非线性方程求解。

输入与位置：同一正式Case已构造的solver与问题候选管线；声明的局部context键：problem。

```python
from nsgablack.plugins import NewtonSolverProviderPlugin, NumericalSolverConfig
solver.register_evaluation_provider(NewtonSolverProviderPlugin(config=NumericalSolverConfig(tol=1e-8, max_iter=100)).create_provider())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.broyden_solver · BroydenSolverProviderPlugin

Broyden 求解插件：评估阶段的无 Jacobian 非线性求解。

输入与位置：同一正式Case已构造的solver与问题候选管线；声明的局部context键：problem。

```python
from nsgablack.plugins import BroydenSolverProviderPlugin, NumericalSolverConfig
solver.register_evaluation_provider(BroydenSolverProviderPlugin(config=NumericalSolverConfig(tol=1e-7, max_iter=120)).create_provider())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.contract_bridge · ContractBridgePlugin

契约桥接插件：跨层映射内层结果字段。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import ContractBridgePlugin, BridgeRule
solver.add_plugin(ContractBridgePlugin(rules=[BridgeRule('objective', 'inner_objective', target_layer='L1')]))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.inner_timeout_budget · TimeoutBudgetPlugin

内层超时/预算插件：限制内层调用次数与耗时。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import TimeoutBudgetPlugin, TimeoutBudgetConfig
solver.add_plugin(TimeoutBudgetPlugin(config=TimeoutBudgetConfig(layer='L2', max_calls=200, time_budget_ms=30000)))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## runtime.inner_evaluator · TaskInnerRuntimeEvaluator

问题侧内层运行评估器：通过 problem.inner_runtime_evaluator 执行嵌套评估。

输入与位置：同一正式Case已构造的solver与问题候选管线；声明的局部context键：problem。

```python
from nsgablack.core.nested_solver import InnerRuntimeConfig, TaskInnerRuntimeEvaluator
solver.problem.inner_runtime_evaluator = TaskInnerRuntimeEvaluator(config=InnerRuntimeConfig(source_layer='L2', target_layer='L1'))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.pareto_archive · ParetoArchivePlugin

**什么时候用：** 希望保留各个已提交代中出现的非支配候选，而非只看最终一代的成员。插件负责档案与观察发布，算法的父代、生存和替换选择仍归 Adapter。

**先准备什么：** 宿主有正式 population authority 或可读取的已提交 population partitions，候选 `(n,d)`、目标 `(n,m)`、违反量 `(n,)` 必须对齐，目标名称数等于 `m`。为了让第一次接入易于解释，可使用无 Bias 的 `assembly_workbench/directions` 双目标 Case。

**放在哪：** 在 Case `plugins/` 创建插件，在 `build_solver.py` 组装 Solver 后 `add_plugin`；保留插件实例才能直接检查它的档案统计。下面 `solver` 是同一 `build_solver` 已构造的 Solver 实参。

**接入步骤：**

```python
from nsgablack.plugins import ParetoArchivePlugin, ParetoArchiveConfig

def attach_archive(solver):
    archive = ParetoArchivePlugin(config=ParetoArchiveConfig(
        max_size=200, keep_infeasible=False, update_every=1,
    ))
    solver.add_plugin(archive)
    return archive
```

在 `build_solver.py` 返回 Solver 前调用 `attach_archive(solver)`，不要在每次评估中重建插件。目标名称变化时插件按目标标签分段；跨段不进行支配比较。这里 `max_size` 是每段档案上限，不是种群容量。

**运行入口：** 正式 Case `examples/cases/assembly_workbench/cases/directions/build_solver.py` 已挂载 ParetoArchivePlugin；`python examples/cases/assembly_workbench/run_project.py --group directions` 是其 Project 入口，本轮未执行。

**怎样判断接对：** 运行后 `total_archive_size()` 是各段保留条目总数，`segment_count` 是目标空间段数；档案行保留对应语义候选与 token。只有提交代更新档案，失败或空尝试不应假增一代。存在 Bias 时先确认读到的 authority 反馈是原始还是选择视图，不把偏好档案直接标为原始 Pareto 前沿。

**配套组件 key：** `adapter.nsga2` 或 `adapter.moead`、`solver.composable`、`tool.solution_pool`。

**接口依据与验证状态：** `plugins/runtime/pareto_archive.py` 与 directions 正式 Case；仅源码核对。

## plugin.benchmark_harness · BenchmarkHarnessPlugin

标准化基准产物与指标协议。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import BenchmarkHarnessPlugin, BenchmarkHarnessConfig
solver.add_plugin(BenchmarkHarnessPlugin(config=BenchmarkHarnessConfig(output_dir='runs')))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.module_report · ModuleReportPlugin

模块级审计与贡献报告。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import ModuleReportPlugin, ModuleReportConfig
solver.add_plugin(ModuleReportPlugin(config=ModuleReportConfig(output_dir='runs')))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.profiler · ProfilerPlugin

运行时性能剖析：阶段延迟与吞吐。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import ProfilerPlugin, ProfilerConfig
solver.add_plugin(ProfilerPlugin(config=ProfilerConfig()))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.dynamic_switch · DynamicSwitchPlugin

信号驱动的运行模式/策略切换。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import DynamicSwitchPlugin
plugin = DynamicSwitchPlugin(should_switch_fn=lambda solver, context: False,
    soft_switch_fn=lambda solver, context: None)
solver.add_plugin(plugin)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：教学条件永不切换；真实切换规则由用户定义，不在日志Plugin中偷偷修改算法决策。

## plugin.async_event_hub · AsyncEventHubPlugin

统一异步事件队列与提交边界。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import AsyncEventHubPlugin, AsyncEventHubConfig
solver.add_plugin(AsyncEventHubPlugin(cfg=AsyncEventHubConfig(commit_policy='generation_end')))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.mysql_run_logger · MySQLRunLoggerPlugin

将运行元数据与报告路径落库到 MySQL。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import MySQLRunLoggerPlugin, MySQLRunLoggerConfig
solver.add_plugin(MySQLRunLoggerPlugin(config=MySQLRunLoggerConfig(database='nsgablack')))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；可达MySQL、相应驱动与部署者配置；不在示例或浏览器中填写生产密码。。

## plugin.diversity_init · DiversityInitPlugin

通过重复/相似性控制提升初始多样性。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import DiversityInitPlugin
solver.add_plugin(DiversityInitPlugin())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.elite · BasicElitePlugin (deprecated compatibility bridge)

旧精英 Plugin 的迁移桥；attach 时将现有 Adapter 包装为事务型 EliteRetentionAdapter，不直接写 population authority。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import BasicElitePlugin  # deprecated; remove_in=1.0.0
solver.add_plugin(BasicElitePlugin())  # migrates to EliteRetentionAdapter
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.memory · MemoryPlugin

周期清理内存并记录内存指标快照。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import MemoryPlugin
solver.add_plugin(MemoryPlugin())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.gpu_eval_template · GpuEvaluationTemplateProviderPlugin

最小 GPU 评估短路模板插件。

输入与位置：同一正式Case已构造的solver与问题候选管线；声明的局部context键：problem。

```python
from nsgablack.plugins import GpuEvaluationTemplateProviderPlugin
solver.register_evaluation_provider(GpuEvaluationTemplateProviderPlugin().create_provider())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.otel_tracing · OpenTelemetryTracingPlugin

OpenTelemetry 追踪：评估/适配器/插件运行事件。

输入与位置：同一正式Case已构造的solver与问题候选管线；声明的局部context键：generation。

```python
from nsgablack.plugins import OpenTelemetryTracingPlugin, OpenTelemetryTracingConfig
solver.add_plugin(OpenTelemetryTracingPlugin(config=OpenTelemetryTracingConfig(console_export=True)))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；OpenTelemetry SDK及所选择exporter；未安装依赖时不承诺导出成功。。

## plugin.decision_trace · DecisionTracePlugin

确定性决策路径追踪与回放产物（JSONL + 摘要）。

输入与位置：同一正式Case已构造的solver与问题候选管线；声明的局部context键：generation。

```python
from nsgablack.plugins import DecisionTracePlugin, DecisionTraceConfig
solver.add_plugin(DecisionTracePlugin(config=DecisionTraceConfig(output_dir='runs', run_id='demo')))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## plugin.sequence_graph · SequenceGraphPlugin

记录组件交互顺序并输出序列图产物。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins import SequenceGraphPlugin, SequenceGraphConfig
solver.add_plugin(SequenceGraphPlugin(config=SequenceGraphConfig(output_dir='runs', run_id='demo')))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

## plugin.sensitivity_analysis · SensitivityAnalysisPlugin

敏感性分析插件：批量执行参数 sweep 并产出聚合 study artifact。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.plugins.ops.sensitivity_analysis import SensitivityAnalysisPlugin, SensitivityAnalysisConfig, SensitivityParam
study = SensitivityAnalysisPlugin(config=SensitivityAnalysisConfig(
    params=[SensitivityParam(path='adapter.cfg.base_sigma', values=[0.05, 0.15])]))
solver.add_plugin(study)
def run_authorized_study(build_solver):
    return study.run_study(build_solver)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：以VNS Case为例，base_sigma须确为其实际配置字段。仅挂插件不会自动执行参数扫描；正式工厂须保留Project派生ResourceContext与预算。本卡只配置扫描，不执行批量实验。

## repr.unit_candidate · CandidateUnitBuilder

保留候选语义的轻量 Unit 构建器；由 Adapter 经独立 UnitBinding 使用，构建与恢复不执行搜索或求值。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, UnitBuildRequest
from nsgablack.representation import CandidateUnitBuilder
binding = UnitBinding(CandidateUnitBuilder())
unit = binding.build(UnitBuildRequest('demo', np.array([0., 1.])))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_search_node · SearchNodeBuilder

A* 节点、父关联和代价存储的独立 Unit 构建器；边代价计算、扩展与优先级仍归 Adapter，不进入问题 Pipeline。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, UnitBuildRequest
from nsgablack.representation import SearchNodeBuilder
binding = UnitBinding(SearchNodeBuilder())
unit = binding.build(UnitBuildRequest('demo', np.array([0., 1.]), parameters={'g': 0., 'h': 1., 'f': 1.}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## representation.parallel_repair · ParallelRepair

表示组件：ParallelRepair。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline, ParallelRepair
from nsgablack.representation.continuous import ProjectionRepair
repair = ParallelRepair(ProjectionRepair(low=0.0, high=1.0), backend='thread', max_workers=1)
pipeline = RepresentationPipeline(repair=repair)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：实际并发额度服从Project L0；不会通过repair声明自己获得全局线程授权。

## representation.sbx_crossover · SBXCrossover

连续变量的模拟二进制交叉（SBX）。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import SBXCrossover
pipeline = RepresentationPipeline(crossover=SBXCrossover(eta_c=15.0, low=0., high=1.))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## representation.polynomial_mutation · PolynomialMutation

连续变量多项式变异。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import PolynomialMutation
pipeline = RepresentationPipeline(mutator=PolynomialMutation(eta_m=20.0, low=0., high=1.))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## repr.binary · BinaryInitializer

表示组件：BinaryInitializer。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.binary import BinaryInitializer
pipeline = RepresentationPipeline(initializer=BinaryInitializer(probability=0.5))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：Problem.dimension与语义布局须匹配：图4节点产生6条无向边；矩阵2×3为6维；排列由问题维数决定。组件初始化只生成候选，后续评估仍属于Problem。

## repr.context_gaussian · ContextGaussianMutation

**什么时候用：** VNS 已决定本次邻域尺度，希望高斯变异真正使用该尺度。普通 GaussianMutation 只读自己的固定 sigma，不能自动响应 VNS 的邻域切换；ContextGaussianMutation 负责消费本次调用的局部参数，改进判断仍归 VNS。

**先准备什么：** 数值候选 shape 为 `(d,)`；正式 `assembled_ga_vns` 的 `d=2`，边界为 `[-4,4]`。ContextGaussianMutation 的默认 `base_sigma=0.1`、默认 `sigma_key=KEY_MUTATION_SIGMA`，实际键名为 `"mutation_sigma"`。这是算子在局部键缺失或不能转换为浮点数时的回退值；VNS 自身的默认 `base_sigma=0.2` 是另一个参数，控制邻域几何，两者不能混为一个默认值。

**放在哪：** Case `adapter/composition.py` 直接给实际 VNS 实例传 `mutator`。该 Case 的 `pipeline/main.py` 已负责问题边界 repair，保留它即可；不需要再把同一个变异器放进共享 Pipeline，也不要覆盖 GA 自己的 GaussianMutation。

**接入步骤：** 下段 `settings` 是同 Case 的 `DemoConfig`，由 `build_solver.py` 传入，提供 `local_batch` 和 `vns_sigma`；返回实例用在原组合工厂的 VNS 位置：

```python
from nsgablack.adapters import VNSAdapter
from nsgablack.context_keys import KEY_MUTATION_SIGMA
from nsgablack.representation import ContextGaussianMutation

def build_vns(settings):
    return VNSAdapter(
        name="vns", batch_size=settings.local_batch, k_max=3,
        base_sigma=settings.vns_sigma, scale=1.5, max_sigma=0.8,
        restart_on_stagnation=False,
        mutator=ContextGaussianMutation(
            base_sigma=settings.vns_sigma, sigma_key=KEY_MUTATION_SIGMA,
        ),
    )
```

保留原工厂的 PoolTaskSpec 输入和返回竞争接线。VNS 在生成邻域时复制本次 context，写入 `vns_k` 和 `mutation_sigma`，再经自己的 `mutate_candidate` 调用这个直属算子；算子按传入 sigma 生成同维高斯扰动。通常保留标准 sigma_key：单独改成别的键而没有对应的局部生产者，会使它一直使用 base_sigma 回退。每个实际所有者创建自己的变异器实例，其 RNG 随所属 Adapter 回滚和恢复。

**运行入口：** `python examples/cases/assembled_ga_vns/run_project.py --group plan`。其正式 `adapter/composition.py` 已直接绑定 ContextGaussianMutation，Pipeline 只装问题 BoxRepair；本轮没有运行算法。

**怎样判断接对：** 先看 `results/plan/trace.json` 的 `initial.operation_contracts`，确认 ContextGaussianMutation 归 VNS 而非 GA。运行期可由同一 VNS 实例的 `get_runtime_context_projection(control)` 读到当时的 `vns_k/mutation_sigma`，未开始构建邻域时可为空；不要为检查调用 `ensure_neighborhood_unit()` 触发构建。`mutate` 返回新数值数组，shape 保持 `(d,)`，实际目标仍须由修复后的候选正式求值。邻域尺度是本次调用输入，不能从根级共享 context 猜测另一个 VNS 实例的尺度，也不能用运行后的当前投影追认历史提案。

**配套组件 key：** `adapter.vns`、`repr.pipeline`、`tool.pool_task_spec`、`tool.subpools`；固定扰动见 `repr.gaussian_mutation`。本算子不单独承担候选池交接或阶段调度。

**接口依据与验证状态：** `representation/continuous.py::ContextGaussianMutation`、`adapters/vns/adapter.py::change`、`nsgablack/context_keys.py` 与 `examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py`；仅源码核对，未执行变异或求值。

## repr.context_switch · ContextSelectMutator

表示组件：ContextSelectMutator。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline, ContextSelectMutator
from nsgablack.representation.continuous import GaussianMutation
operator = ContextSelectMutator([GaussianMutation(sigma=0.05), GaussianMutation(sigma=0.2)])
pipeline = RepresentationPipeline(mutator=operator)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：消费者须提供已注册的vns_k局部上下文；不要在共享context中存候选或Unit对象。

## repr.continuous · UniformInitializer

连续均匀候选生成器：可直接绑定 Adapter 的 initializer 或放入既有 Pipeline，显式 RNG codec 支持恢复；池输入与暖启动优先。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import UniformInitializer
pipeline = RepresentationPipeline(initializer=UniformInitializer(low=-1., high=1.))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：Problem.dimension与语义布局须匹配：图4节点产生6条无向边；矩阵2×3为6维；排列由问题维数决定。组件初始化只生成候选，后续评估仍属于Problem。

## repr.dynamic_repair · DynamicRepair

表示组件：DynamicRepair。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.dynamic import DynamicRepair
from nsgablack.representation.continuous import ProjectionRepair
pipeline = RepresentationPipeline(repair=DynamicRepair([(0, ProjectionRepair(low=0., high=1.)), (20, ProjectionRepair(low=0.2, high=0.8))]))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## repr.graph · GraphEdgeInitializer

表示组件：GraphEdgeInitializer。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.graph import GraphEdgeInitializer
pipeline = RepresentationPipeline(initializer=GraphEdgeInitializer(num_nodes=4, density=0.3))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；图组件可能需要SciPy，NetworkX为源码中的可选后端；节点/边布局须由Problem定义。。

边界：Problem.dimension与语义布局须匹配：图4节点产生6条无向边；矩阵2×3为6维；排列由问题维数决定。组件初始化只生成候选，后续评估仍属于Problem。

## repr.integer · IntegerInitializer

表示组件：IntegerInitializer。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.integer import IntegerInitializer
pipeline = RepresentationPipeline(initializer=IntegerInitializer(low=0, high=10))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：Problem.dimension与语义布局须匹配：图4节点产生6条无向边；矩阵2×3为6维；排列由问题维数决定。组件初始化只生成候选，后续评估仍属于Problem。

## repr.matrix · IntegerMatrixInitializer

表示组件：IntegerMatrixInitializer。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.matrix import IntegerMatrixInitializer
pipeline = RepresentationPipeline(initializer=IntegerMatrixInitializer(rows=2, cols=3, low=0, high=5))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：Problem.dimension与语义布局须匹配：图4节点产生6条无向边；矩阵2×3为6维；排列由问题维数决定。组件初始化只生成候选，后续评估仍属于Problem。

## repr.permutation · PermutationInitializer

表示组件：PermutationInitializer。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.permutation import PermutationInitializer
pipeline = RepresentationPipeline(initializer=PermutationInitializer())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：Problem.dimension与语义布局须匹配：图4节点产生6条无向边；矩阵2×3为6维；排列由问题维数决定。组件初始化只生成候选，后续评估仍属于Problem。

## repr.pipeline · RepresentationPipeline

**什么时候用：** 把同一问题的候选初始化、编解码或约束修复接入正式 Solver。多个算法共享 Problem 时，可以只共享问题修复，把各算法的变化分别绑定到各自 Adapter。

**先准备什么：** 明确候选布局、维数和合法范围。下面复用 directions Case：单个候选 shape `(1,)`，取值 `[-2,2]`；MOEA/D 自己持有 initializer 和 mutator，因此 Pipeline 只承担问题修复。若你的 Adapter 未绑定 initializer，必须由管线提供可用初始化组件。

**放在哪：** Case `pipeline/main.py::build_pipeline()`；`pipeline/__init__.py` 导出该工厂，`build_solver.py` 导入并传入 `representation_pipeline=build_pipeline()`。

**接入步骤：**

```python
from nsgablack.representation import RepresentationPipeline, ClipRepair

def build_pipeline():
    return RepresentationPipeline(repair=ClipRepair(low=-2.0, high=2.0))
```

`ClipRepair.repair(x, context)` 逐坐标裁剪且保持 shape；例如数值 `2.5` 变为 `2.0`。它不评估目标，不保证预算平衡、排列合法或其它业务约束；更复杂的约束要替换为能表达该问题的 repair。Solver 在预算裁剪后调用问题修复，并把修复证据交还提案所有者，用户无需手写 repair/evaluate 循环。

**运行入口：** 正式源码位置是 `examples/cases/assembly_workbench/cases/directions/pipeline/main.py`，Project 入口为 `python examples/cases/assembly_workbench/run_project.py --group directions`。本轮只核对装配代码。

**怎样判断接对：** Problem 实际接收修复后的同维候选；原提案 token 保持，目标由 Problem.evaluate 计算。构造 Pipeline 不会生成候选、建立算法 Unit 或进行评估。禁止靠装配期调用 `init` 推断模型维数。

**配套组件 key：** `solver.composable`、`adapter.moead`、`repr.continuous`、`repr.gaussian_mutation`。ClipRepair 是本段真实源码类，其可发现键应由 Catalog 实际登记，不能由使用者猜名。

**接口依据与验证状态：** `representation/continuous.py::ClipRepair`、上述 directions 管线及 `build_solver.py`；仅源码核对。

## repr.projection_repair · ProjectionRepair

表示组件：ProjectionRepair。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline
from nsgablack.representation.continuous import ProjectionRepair
pipeline = RepresentationPipeline(repair=ProjectionRepair(low=0., high=1., sum_target=1.0))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## repr.context_dispatch · ContextDispatchMutator

表示组件：按 strategy/phase 路由不同 mutator。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline, ContextDispatchMutator
from nsgablack.representation.continuous import GaussianMutation
operator = ContextDispatchMutator(routes={'local': GaussianMutation(sigma=0.05)}, default_mutator=GaussianMutation(sigma=0.2))
pipeline = RepresentationPipeline(mutator=operator)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：路由读取strategy_id，不按Adapter类型猜测；跨叶算子不同需求优先使用具名mutation_operators。

## repr.pipeline_orchestrator · PipelineOrchestrator

表示层编排控制器：统一 mutate/repair 的串行、路由与动态 phase 策略。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.representation import RepresentationPipeline, PipelineOrchestrator
from nsgablack.representation.continuous import GaussianMutation
operator = PipelineOrchestrator(mutator=GaussianMutation(sigma=0.1))
pipeline = RepresentationPipeline(mutator=operator)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：共享blackbase.kernel拥有分支执行与授权；这里是候选处理门面，不是搜索阶段调度器。

## repr.unit_pareto_label · ParetoLabelBuilder

ParetoLabelBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, UnitBuildRequest
from nsgablack.representation import ParetoLabelBuilder
binding = UnitBinding(ParetoLabelBuilder())
unit = binding.build(UnitBuildRequest('demo', np.array([0., 1.]), parameters={'g': [0., 0.], 'h': [1., 1.], 'f': [1., 1.]}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_trajectory · TrajectoryUnitBuilder

独立轨迹结构构建器：schema v2 保存候选关联反馈与依赖版本，旧 v1 不自动恢复；Adapter 通过 UnitBinding 按需创建。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import TrajectoryUnitBuilder
binding = UnitBinding(TrajectoryUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'current': np.zeros(2)}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_poll · PollUnitBuilder

PollUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import PollUnitBuilder
binding = UnitBinding(PollUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'current': np.zeros(2)}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_parameters · ParameterUnitBuilder

ParameterUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import ParameterUnitBuilder
binding = UnitBinding(ParameterUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'current': np.zeros(2)}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_population · PopulationUnitBuilder

PopulationUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import PopulationUnitBuilder
binding = UnitBinding(PopulationUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'population': np.array([[0., 1.], [1., 0.]])}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_reference_population · ReferencePopulationBuilder

参考种群结构构建器，显式兼容基础 Population 契约，可由 NSGA2/SPEA2/NSGA3 经独立 UnitBinding 使用；不承担搜索策略。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import ReferencePopulationBuilder
binding = UnitBinding(ReferencePopulationBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'population': np.array([[0., 1.], [1., 0.]])}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_differential_population · DifferentialPopulationBuilder

DifferentialPopulationBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import DifferentialPopulationBuilder
binding = UnitBinding(DifferentialPopulationBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'population': np.array([[0., 1.], [1., 0.]])}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_decomposition · DecompositionUnitBuilder

DecompositionUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import DecompositionUnitBuilder
binding = UnitBinding(DecompositionUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'population': np.array([[0., 1.], [1., 0.]])}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_region · RegionUnitBuilder

独立区域结构构建器：schema v2 关联中心反馈与依赖版本，旧 v1 不自动恢复；半径与搜索决策仍归 Adapter。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import RegionUnitBuilder
binding = UnitBinding(RegionUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'center': np.zeros(2)}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_model_search · ModelSearchUnitBuilder

ModelSearchUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import ModelSearchUnitBuilder
binding = UnitBinding(ModelSearchUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'center': np.zeros(2)}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_archive · ArchiveUnitBuilder

ArchiveUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import ArchiveUnitBuilder
binding = UnitBinding(ArchiveUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'entries': []}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## repr.unit_neighborhood · NeighborhoodUnitBuilder

NeighborhoodUnitBuilder：独立算法结构与显式状态 codec 的构建器，由所属 Adapter 通过 UnitBinding 按需使用；不属于问题候选管线。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import UnitBinding, StructureBuildRequest
from nsgablack.representation import NeighborhoodUnitBuilder
binding = UnitBinding(NeighborhoodUnitBuilder())
unit = binding.build(StructureBuildRequest('demo', parameters={'values': {'scales': (0.1, 0.2)}}))
assert unit.unit_id == 'demo'
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：此片段单独演示builder的值输入与codec契约。正式Case只装配UnitBinding，由实际Adapter惰性创建；不在问题Pipeline预建Unit，不把Unit构建当候选编码。

## adapter.pool_search · PoolSearchAdapter

池驱动优化组合：单解准备候选、独立种群搜索、停滞唤醒与返回竞争；使用既有 Solver 事务。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import PoolSearchAdapter, PoolSearchSpec, VNSAdapter, NSGA2Adapter
adapter = PoolSearchAdapter(VNSAdapter(), [PoolSearchSpec(NSGA2Adapter(), initial_count=8)])
solver.set_adapter(adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## adapter.pool_task · PoolTaskAdapter

为现有多角色调度绑定候选子池、逐起点精修进度与返回引用；子算法沿用正式步骤事务。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import PoolTaskAdapter, PoolTaskSpec, VNSAdapter
task = PoolTaskSpec('elite', count='all', steps=3, output='refined')
solver.set_adapter(PoolTaskAdapter(VNSAdapter(), task, role='local'))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：elite必须是同Case已发布的普通集合；count=all表示逐起点精修，不是隐式种群填满屏障。

## tool.pool_task_spec · PoolTaskSpec

明确母池或具名视图输入；按算法实例选择普通／投影结果视图，递归发布冻结来源与精确选择，沿用角色调度和恢复。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import PoolTaskSpec
task = PoolTaskSpec(mode='initialize')
local = PoolTaskSpec('elite', count='all', steps=5)
# Additional donors for a plain change function are explicit public names.
task = PoolTaskSpec(mode='initialize', change_sources=('reference',), change_allow_main=True)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## example.pool_refinement · GA / VNS Subpool Refinement

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：选取 20 个起点、两类四实例 VNS 精修、返回 NSGA-II 成员竞争；包含基准评估与闲置保护。

```bash
python examples/cases/solution_pool/cases/pool_refinement/run_solver.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## tool.solution_pool · SolutionPool

**什么时候用：** 在同一运行中按准确版本读取候选、在算法间交接起点，或核对某条原始反馈。Solver 已拥有唯一 SolutionPool；不要给每个算法另建一份值池。

**先准备什么：** 先构造正式 Solver，再让运行产生并提交候选。`SolutionRef` 同时确定候选 token 和版本；数值相同不能代替引用。下面 `control` 是已提交钩子或结果整理函数传入的同一 Solver，不是新创建的空 Solver。

**放在哪：** Case `plugins/` 的提交后观察逻辑，或 Case `solver/` 的结果整理函数。需要影响搜索交接时，在 `adapter/` 用 `PoolTaskSpec` 声明输入，不在观察代码里修改池。

**接入步骤：**

```python
def inspect_accepted(control):
    pool = control.solution_pool
    refs = pool.select(at=pool.timestamp, stage="accepted")
    if not refs:
        return None  # 尚无已提交反馈；空选择不能推断维数
    batch = control.read_solutions(refs)
    raw_objectives, raw_violations = pool.read_raw_feedback(refs)
    return {
        "refs": refs,
        "candidates": batch,
        "raw_objectives": raw_objectives,
        "raw_violations": raw_violations,
    }
```

返回的 `CandidateBatch` 含语义候选、数值矩阵 `(n,d)` 和 token；两份原始反馈分别为 `(n,m)` 和 `(n,)`，顺序与 refs 一致。该函数读取根区域已接纳历史，不是算法最终种群；读 NSGA2 成员应先取该实例 `get_population_solution_refs(control)`，再按这些引用读取。使用最近组合 working_pool 时应显式读取那个区域或已知子池。

**运行入口：** 实际交接可沿 `examples/cases/assembled_ga_vns/cases/hybrid_search/adapter/composition.py` 阅读，正式入口为 `python examples/cases/assembled_ga_vns/run_project.py --group plan`。它通过 PoolTaskSpec 交接，不调用上述观察函数代替算法调度。

**怎样判断接对：** 引用指向同一运行的已发布版本，读出的候选、token、raw feedback 行对齐；任务读取的是声明的冻结输入。事务未提交的视图不能被下游枚举，零接纳不会发布新解。若启用了闲置回收，需要长期保留的引用须显式保护，旧 manifest 本身不保证所有候选永久存在。

**配套组件 key：** `solver.composable`、`tool.pool_task_spec`、`tool.subpools`、`adapter.search_plan`、`adapter.nsga2`、`adapter.vns`。

**接口依据与验证状态：** `core/state/solution_pool.py`、`core/blank_solver.py::read_solutions`、上述标准 Case；仅源码核对，未执行池操作。

## tool.subpools · Adapter Result View Selectors

按真实算法实例选择全部或随机 N 个普通／投影结果视图；冻结候选版本、父级与可选比较参数。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import PoolTaskSpec, subpools
task = PoolTaskSpec(subpools.random(20, adapter1), steps=3, output='refined')
next_task = PoolTaskSpec(subpools.all(coarse_vns), steps=3, output='fine')
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.objective_projection · ObjectiveProjection

可传输的 weighted_sum/tchebycheff 比较坐标；原始目标与约束证据保留。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core import ObjectiveProjection
projection = ObjectiveProjection('weighted_sum', (0.8, 0.2))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## example.moead_refinement · MOEA/D / GA / VNS Direction Refinement

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Case：100 方向按来源选择 20 个精修后返回 MOEA/D；可启用 VNS 粗搜→VNS 细搜的嵌套派生视图。

```bash
examples/cases/solution_pool/cases/moead_refinement/README.md
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## tool.solution_ref · SolutionRef

同时定位候选身份和池记录版本的值引用；不以数值相等反查身份。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
refs = solver.store_solutions(candidate_batch)
batch = solver.read_solutions(refs)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.solution_stamp · SolutionStamp

运行身份与池逻辑序号定义可见截止点；失败后保留时钟高水位，墙钟不参与排序。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
stamp = solver.solution_pool.timestamp
refs = solver.solution_pool.select(at=stamp)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.pool_retention_policy · PoolRetentionPolicy

按已提交步数回收无人持有候选，保留指定发布窗口与显式固定的值闭包；不限制池容量。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core import PoolRetentionPolicy
solver.set_solution_pool_retention(PoolRetentionPolicy(idle_steps=20, retained_publications=2))
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## doc.architecture.solution_pool · 解池运行契约

本条目是阅读入口，不是可实例化算法。

阅读文件：`docs/architecture/SOLUTION_POOL_CN.md`。

内容用途：池先启动、候选身份、引用子池与角色任务、独立配额/容量、闲置回收和恢复窗口的正式契约。

使用步骤：先在当前仓库打开上述文件；核对其中引用的公开接口，再把适用片段放入正式Case工厂。

预期结果：理解该主题的职责、输入和边界；阅读或索引成功不表示相关算法已运行。

依赖：仓库中的该文档；如果文档涉及可选后端，依赖以正文声明为准。

## example.solution_pool · Pool Search Prepare / Recover / Return

本条目是正式示例项目入口，不新建另一套求解循环。

用途：标准 Project/Case：准备池候选、双种群搜索、停滞重启 SA 与返回竞争，L0 由 Project 授权。

```bash
python examples/cases/solution_pool/run_project.py
```

输入：使用该Project默认Problem与配置；外部数据、可选后端与资源需求先看对应README。

使用步骤：进入nsgablack仓库根目录；阅读Case build_solver中的实际装配；通过上方正式Project/Case入口运行。

预期结果：Project交付Case结果与运行摘要；具体数值与后端可用性以同版本实际收据为准。

依赖：blackbase、nsgablack，以及对应README实际声明的数据与可选库。

## tool.strategy_task · StrategyTask

多策略子任务：实例路径、阶段、原提案预算和局部区域/种子。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import StrategyTask
def propose(self, solver, context):
    task = StrategyTask.from_context(context)
    print(task.owner_path, task.phase, task.budget)
    return []
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：示例位于组合器已绑定的子Adapter.propose；不是从全局观测猜原提案任务。

## tool.strategy_origin · StrategyOrigin

候选从外到内的策略来源，与 CandidateBatch/token 一起保存和筛选。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.adapters import StrategyOrigin
def inspect_origin(batch, index):
    return StrategyOrigin.from_candidate(batch.semantic_states[index])
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：输入是控制面保留token与provenance的CandidateBatch；同数值候选不能用来猜身份。

## tool.runtime_participant · RuntimeParticipant

通用步骤事务参与者；局部快照、恢复、子参与者与提交后清理。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from blackbase.runtime import RuntimeParticipant
class Counter:
    name = 'counter'
    value = 0
    def snapshot_step_state(self): return {'value': self.value}
    def restore_step_state(self, state): self.value = state['value']
    def commit_step_state(self, state): return None
    def step_transaction_children(self): return ()
counter = Counter()
assert isinstance(counter, RuntimeParticipant)
solver.register_state_participant(counter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：快照为脱离后的Mapping值；不复制锁、Provider session或任意对象图。

## tool.representation_capabilities · RepresentationCapabilities

候选管线显式操作能力声明。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from blackbase.representation import RepresentationCapabilities
class ClipRepair:
    capabilities = RepresentationCapabilities(frozenset({'repair'}), repair_idempotent=True)
    def repair(self, candidate, context):
        import numpy as np
        return np.clip(candidate, 0., 1.)
repair = ClipRepair()
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：只声明实际提供的操作；确定性/幂等性声明须与行为测试一致。

## tool.participation_contract · ParticipationContract

Plugin 与 Controller 的建议、决定和否决域。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from blackbase.participation import ParticipationContract
from nsgablack.plugins.base import Plugin
class RejectEmptyResult(Plugin):
    participation = ParticipationContract(vetoes=('finalization',))
    def on_solver_finalization_prepare(self, result):
        if not result:
            raise ValueError('final result required')
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：展示声明形式；实际prepare阶段的数据可用性须与正式finalization契约核对，此示例不发布Artifact。

## tool.preference_delta · PreferenceDelta

保留原始反馈的偏好增量值。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from blackbase.preferences import PreferenceDelta
delta = PreferenceDelta('objectives.0', -0.5, 'closer to requested target')
print(delta.key, delta.delta, delta.reason)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：这是可审计偏好值，不是对原始目标或硬可行性的写入许可。

## tool.population_authority · PopulationAuthority

运行内 population、身份、分区与发布游标所有者。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
authority = solver.population_authority
state = authority.snapshot_step_state()
assert isinstance(state, dict)
print(authority.mode)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：只读取Solver已持有的同一权威对象；不得创建另一份可写population副本。

## tool.run_session · RunSession

运行身份、进度、预算、恢复队列与结果所有者。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
session = solver.run_session
progress = session.export_run_progress_state()
print(progress)
assert session.rollback_exempt_reason
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：RunSession计数/耗时不随步骤回滚；不能把它注册成RuntimeParticipant。

## tool.finalization_hooks · FinalizationHooks

结果准备和事务发布的显式注册入口。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from blackbase.runtime import FinalizationHooks
def prepare(result): return dict(result)
def freeze(result): return dict(result)
def abort(error): pass
solver.finalization_hooks = FinalizationHooks(prepare=prepare, freeze=freeze, abort=abort)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：最小协议示例不发布外部产物。真实发布须由Artifact/结果事务暂存、校验与原子提交；三个事务钩子须完整。

## tool.semantic_extension · SolverSemanticExtension

提交前语义准备与提交后投影扩展。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core.semantic_extension import SolverSemanticExtension
class ObserveCommitted(SolverSemanticExtension):
    name = 'observe_committed'
    def after_step_committed(self, solver, outcome):
        assert outcome.committed
solver.register_semantic_extension(ObserveCommitted())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：after_step_committed失败不能把已提交代数伪装成回滚。

## tool.dynamic_cli_signal · CLISignalProvider

CLISignalProvider 工具。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.utils.dynamic import CLISignalProvider
provider = CLISignalProvider()
print(type(provider).__name__)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：交互信号是控制输入；正式订阅由动态控制组件处理，不为日志观察构建Unit。

## tool.context_store_redis · RedisContextStore

Context 后端工具：RedisContextStore（共享状态，可选 TTL）。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core.state.context_store import create_context_store
store = create_context_store(backend='redis', redis_url='redis://127.0.0.1:6379/0',
    key_prefix='example:run', ttl_seconds=30)
solver.set_context_store(store)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy；Redis服务与redis Python依赖。。

边界：需要可达Redis及已安装redis依赖；示例地址不是部署凭据，不在示例中写密码。

## solver.blank · SolverBase

工具：SolverBase。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core.blank_solver import SolverBase
solver = SolverBase(problem=problem, representation_pipeline=pipeline)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：problem和pipeline来自同一正式Case工厂；这是装配片段，不在文档另写运行循环。SolverBase是扩展基类，完整搜索优先选ComposableSolver或EvolutionSolver。

## solver.composable · ComposableSolver

工具：ComposableSolver。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core.composable_solver import ComposableSolver
solver = ComposableSolver(problem=problem, representation_pipeline=pipeline, adapter=adapter)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：problem和pipeline来自同一正式Case工厂；这是装配片段，不在文档另写运行循环。SolverBase是扩展基类，完整搜索优先选ComposableSolver或EvolutionSolver。

## solver.nsga2 · EvolutionSolver

工具：EvolutionSolver。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core.evolution_solver import EvolutionSolver
solver = EvolutionSolver(problem=problem, representation_pipeline=pipeline)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：problem和pipeline来自同一正式Case工厂；这是装配片段，不在文档另写运行循环。SolverBase是扩展基类，完整搜索优先选ComposableSolver或EvolutionSolver。

## tool.context_keys · Context Keys

工具：Context Keys。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from blackbase.context import context_keys
from nsgablack.context_keys import KEY_GENERATION
def read_generation(context):
    return context.get(KEY_GENERATION, 0)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：Project自定义共享键须在本地context_keys.json登记；使用常量并不自动取得写权限。

## tool.context_schema · MinimalEvaluationContext

工具：MinimalEvaluationContext。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core.state import MinimalEvaluationContext
local = MinimalEvaluationContext(generation=0, individual_id=0,
    constraints=[], constraint_violation=0.0)
print(local.individual_id)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：individual_id仅属于该次调用，不能回写为跨代候选身份。

## tool.logging · configure_logging

工具：configure_logging。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.utils.engineering import configure_logging
logger = configure_logging(level='INFO', json_format=True)
logger.info('assembly configuration loaded')
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

## tool.metrics · pareto_filter

工具：pareto_filter。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.utils.analysis import pareto_filter
front = pareto_filter([[1.0, 2.0], [2.0, 1.0], [3.0, 3.0]])
print(front)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：输入是最小化目标二维数组，返回非支配目标行而非布尔mask；先由调用方处理原始约束及方向，不把这个工具当硬接纳策略。

## tool.parallel_evaluator · ParallelEvaluator

工具：ParallelEvaluator。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.core.evolution_solver import EvolutionSolver
solver = EvolutionSolver(problem, pop_size=8, enable_parallel=True,
    parallel_backend='thread', parallel_max_workers=1)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：Problem来自当前Case；正式运行仍从Project L0获取grant。不能用本地max_workers自行扩大授权。

## tool.population_change · PopulationChange

成员操作的明确来源映射：Adapter 决策，Unit 对齐候选/反馈/token 并维护自定义行字段。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from dataclasses import dataclass, field
import numpy as np
from nsgablack.units import PopulationUnit
@dataclass
class AgePopulation(PopulationUnit):
    age: object = field(default=None)
    member_fields = ('age',)
    def on_members_changed(self, change):
        return {'age': np.array([0 if i is None else self.age[i]
            for i in change.previous_member_indices])}
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：hook只读旧结构并返回字段更新；新成员age=0，老成员随位置映射保持age。正式使用须配套builder/codec，不由Adapter猜未知字段。

## tool.unit_input_spec · UnitInputSpec

变异算子显式声明 Unit 字段与特征，由实际 Adapter 提供脱离只读输入。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.units import UnitInputSpec
class TowardCenter:
    stateless = True
    unit_inputs = UnitInputSpec(fields=('population',))
    def checkpoint_identity(self): return {'name': 'toward_center', 'version': 1}
    def mutate(self, candidate, context, *, unit):
        return candidate + 0.1 * (unit.fields['population'].mean(axis=0) - candidate)
adapter.set_mutator(TowardCenter())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：需要种群Unit且已有基准；输入由实际叶Adapter按声明捕获，不能从共享ctx猜Unit。

## tool.unit_inputs · UnitInputs

调用局部的只读 Unit 字段/特征投影，携带 unit_id、schema 和依赖版本。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
from nsgablack.units import UnitInputSpec
class TowardCenter:
    stateless = True
    unit_inputs = UnitInputSpec(fields=('population',))
    def checkpoint_identity(self): return {'name': 'toward_center', 'version': 1}
    def mutate(self, candidate, context, *, unit):
        return candidate + 0.1 * (unit.fields['population'].mean(axis=0) - candidate)
adapter.set_mutator(TowardCenter())
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：需要种群Unit且已有基准；输入由实际叶Adapter按声明捕获，不能从共享ctx猜Unit。

## tool.unit_feature · UnitFeature

候选/集合的算法特征声明：显式字段依赖、raw/selection 反馈视图和可选增量更新。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import PopulationUnit, UnitFeature, FeatureUnit
unit = PopulationUnit('demo', population=np.array([[0., 1.], [1., 0.]]))
center = UnitFeature('center', ('population',), lambda data: data['population'].mean(axis=0))
assert isinstance(unit, FeatureUnit)
value = unit.feature(center)
print(value)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：独立结构示例；运行中的Unit归具体Adapter所有。缓存依赖population修订，原始反馈与选择反馈须显式区分。

## tool.feature_unit · FeatureUnit

Unit 的按需派生特征能力：按实例隔离、校验依赖内容、只读结果、缓存不进入 checkpoint。

输入与位置：同一正式Case已构造的solver与问题候选管线；本段中的回调输入由实际所有者传入。

```python
import numpy as np
from nsgablack.units import PopulationUnit, UnitFeature, FeatureUnit
unit = PopulationUnit('demo', population=np.array([[0., 1.], [1., 0.]]))
center = UnitFeature('center', ('population',), lambda data: data['population'].mean(axis=0))
assert isinstance(unit, FeatureUnit)
value = unit.feature(center)
print(value)
```

预期结果：得到已装配组件或回调返回值；搜索反馈、提交状态与产物需从正式Project运行收据确认。

依赖：当前nsgablack与blackbase；NumPy。

边界：独立结构示例；运行中的Unit归具体Adapter所有。缓存依赖population修订，原始反馈与选择反馈须显式区分。
