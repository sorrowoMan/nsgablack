# 图Bias：先固定编码，再区分软验证与图算法

本文完整装配当前可解释的树/匹配/着色验证成本及自定义基类扩展；七个旧图评分器和三个不完整路径验证器另作迁移说明，旧类未装配。没有运行算法、NetworkX、场景或外部API；不存在数学性质或执行成功收据。

## graph.shared_host · 两种候选布局共用正式入口和报告

各主例使用完整 `examples/cases/bias_gallery` Project的独立副本，保留default组、Project L0、包目录和规范Case入口。以下相对 `cases/bias_gallery/`。新增 `adapter/graph_search.py`：

```python
from nsgablack.adapters import NSGA2Adapter


def build_adapter():
    return NSGA2Adapter(population_size=12, offspring_size=6, crossover_rate=0.0)
```

问题Pipeline提供实际初始化/变异/修复；不启用算术交叉混淆离散编码。新增 `plugins/graph_report.py`：

```python
import numpy as np
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json
from ..bias.graph_scores import expected_delta


class GraphReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="graph_bias_report")
        self.search, self.output = search, output

    def on_solver_finish(self, result):
        control = self.solver
        refs = tuple(self.search.get_population_solution_refs(control))
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selected_f, selected_v = self.search.get_population_snapshot()
        last = control.get_last_feedback_batch()
        expected = [expected_delta(item.metrics["case.graph_x"]) for item in last.items]
        self.payload = {
            "run_id": control.run_session.run_id,
            "refs": [ref.as_dict() for ref in refs],
            "candidates": control.read_solutions(refs).numeric_matrix.tolist(),
            "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
            "selection_objectives": selected_f.tolist(),
            "selection_violations": selected_v.tolist(),
            "last_candidates": [item.metrics["case.graph_x"] for item in last.items],
            "last_raw": last.raw_objectives.tolist(),
            "last_selection": last.objectives.tolist(),
            "delta_matches": bool(np.allclose(
                last.objectives[:, 0] - last.raw_objectives[:, 0], expected)),
        }

    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

完整替换 `build_solver.py`：

```python
from pathlib import Path
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from .adapter.graph_search import build_adapter
from .bias.graph_scores import build_bias
from .pipeline.graph_pipeline import build_pipeline
from .plugins.graph_report import GraphReport
from .problem.graph_problem import build_problem


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this graph recipe has an explicit encoding")
    search = build_adapter()
    control = ComposableSolver(problem=build_problem(), adapter=search,
        representation_pipeline=build_pipeline(), resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    control.set_random_seed(17)
    control.set_max_steps(6)
    control.set_max_step_attempts(40)
    control.set_bias_module(build_bias(), enable=True)
    control.add_plugin(GraphReport(search, Path(__file__).resolve().parents[2]
                                  / "results" / "graph_scores.json"))
    return control
```

在Case context_keys.json追加 `"metrics.case.graph_x"`；有旧声明时保留并去重。完整文件中具体Problem/Pipeline/Bias由以下各节提供。报告在finishing复制已提交成员，在finalized后写本地观察；不是新权威Artifact或恢复信封。

**运行入口：** 在Project副本根执行 `python run_project.py --check --build-check`，再 `python run_project.py`。检查本轮 `results/graph_scores.json` 的run_id及Project终态；旧JSON不证明本轮成功。本书不执行这些命令。

## bias.graph_tree_constraint · 无向边位上的树、匹配和组合成本

**什么时候用：** 一个候选是四节点无向图的六条可能边，想把不满足结构条件的图加有限软成本。以下实际使用TreeConstraintBias、MatchingConstraintBias、CompositeGraphConstraintBias以及GraphConstraintBias的Case子类；不是图路径、城市顺序或邻接矩阵的混合编码。

**先准备什么：** 共用正式Project/报告/builder，NumPy和当前框架。节点0..3，边按 `(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)` 排列；候选 `(6,)` 位值，raw目标是所选边数。本主例没有Problem拓扑硬条件，因此raw违反量为0，有限软罚不是硬接纳。

**放在哪：** 新建 `problem/graph_problem.py`：

```python
import numpy as np
from blackbase.types import Feedback
from nsgablack.core import BlackBoxProblem


class EdgeCountProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="four_node_edge_count", dimension=6,
            bounds=[(0, 1)] * 6, objectives=["selected_edge_count"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return Feedback(objectives=[float(a.sum())], metrics={"case.graph_x": a.tolist()})


def build_problem():
    return EdgeCountProblem()
```

新建 `pipeline/graph_pipeline.py`：

```python
from nsgablack.representation import (
    RepresentationPipeline, BinaryInitializer, BitFlipMutation, BinaryRepair,
)


def build_pipeline():
    return RepresentationPipeline(initializer=BinaryInitializer(probability=.5),
        mutator=BitFlipMutation(rate=1./6.), repair=BinaryRepair(threshold=.5))
```

评分工厂和独立公式放下一节；共同入口实际调用它。各类只检查阈值>.5的选边，不独立拒绝小数/错误长度；本例由Problem.dimension和BinaryRepair先保证布局。不得把六位截断、缺位补空后称为另一种图的同一语义。

**接入步骤：** 将本节两文件与下一节完整工厂、共用builder/Report一起保存。基线MODE='tree'要求3条边且四节点全连通/无环；不满足返回50软罚。Matching变体要求所有节点度数恰好1，是完美匹配，不是任意匹配的空图解。

**怎样判断接对：** raw目标为边数，selection增加0或50，delta_matches核对最后评估批。手工按列出的边序还原图：tree满足3条且连通；matching满足每节点度1；组合要求树且最大度2。算法6步可能还保留无效候选，不能因给了50就声称所有成员可行。要硬过滤，另在Problem明确拓扑违反量并使用raw门，不把Bias.validate_constraints当成接纳权限。

**运行入口：** 共用Project正式命令，未执行图搜索或验证算法效果。

## graph.edge_scores · 实际工厂、基类扩展与两个替换方式

新建 `bias/graph_scores.py` 完整文件：

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.specialized.graph.constraints import (
    GraphConstraintBias, ValidationResult, TreeConstraintBias,
    MatchingConstraintBias, CompositeGraphConstraintBias,
)

EDGES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
MODE = "tree"


def edge_properties(x):
    values = np.asarray(x)
    selected = [edge for flag, edge in zip(values, EDGES) if flag > .5]
    adjacency = [set() for _ in range(4)]
    for u, v in selected:
        adjacency[u].add(v)
        adjacency[v].add(u)
    reached, stack = set(), [0]
    while stack:
        u = stack.pop()
        if u not in reached:
            reached.add(u)
            stack.extend(adjacency[u] - reached)
    degrees = [len(row) for row in adjacency]
    return selected, degrees, len(reached) == 4


class DegreeAtMostTwo(GraphConstraintBias):
    def __init__(self):
        super().__init__("degree_at_most_two", penalty_scale=50.)

    def validate_constraints(self, x, context):
        _, degrees, _ = edge_properties(x)
        return ValidationResult(is_valid=max(degrees) <= 2)


def build_bias():
    if MODE == "tree":
        component = TreeConstraintBias(num_nodes=4, penalty_scale=50.)
    elif MODE == "matching":
        component = MatchingConstraintBias(num_nodes=4, is_perfect=True, penalty_scale=50.)
    elif MODE == "path_tree":
        component = CompositeGraphConstraintBias(
            constraints=[TreeConstraintBias(num_nodes=4), DegreeAtMostTwo()], penalty_scale=50.)
    elif MODE == "degree_only":
        component = DegreeAtMostTwo()
    else:
        raise ValueError("unknown explicit graph rule")
    module = BiasModule()
    module.cache_enabled = False
    module.add(component)
    return module


def expected_delta(x):
    selected, degrees, connected = edge_properties(x)
    tree = len(selected) == 3 and connected
    valid = {"tree": tree, "matching": all(d == 1 for d in degrees),
             "path_tree": tree and max(degrees) <= 2, "degree_only": max(degrees) <= 2}[MODE]
    return 0. if valid else 50.
```

GraphConstraintBias是扩展基类，必须实现validate_constraints返回ValidationResult，不能直接把空基类add后当作具体约束。失败默认penalty_value=inf由compute替换为本类penalty_scale；不改raw_violations。这里各类weight=1，不重复叠总体权重。

Composite按顺序返回首个失败，不求各子成本之和；这里外层50决定默认inf失败的最终软罚，不是内层Tree默认1e6也加一次。它要求**同一编码**；不能把城市排列TSP与六位边Tree放进同一Composite来碰运气。

### 变体一：由树切到完美匹配

**目的：** 同一边位布局，换一条结构判据。**改在哪里：** 只改评分模块常量：

```python
MODE = "matching"
```

**行为变化：** 需要两条互不相接且覆盖四节点的边，raw目标仍边数。**限制：** 完美匹配不要求整个图连通；不能继续沿用tree检查。若is_perfect=False，空图也是合法匹配，目标最少边会偏好空图。

### 变体二：要求树同时满足最大度2

**目的：** 用现有Composite及显式GraphConstraintBias子类组合叶判据。**改在哪里：** 只改常量：

```python
MODE = "path_tree"
```

**行为变化：** 合法图是一条覆盖四节点的无向路径树。**限制：** 没有指定路径起终点或访问顺序，不等于PathConstraintBias/HamiltonianPathConstraintBias的全部语义；只是在六位无向边编码上明确组合两个条件。

## bias.graph_coloring_constraint · 节点颜色不是边向量

**什么时候用：** 固定四节点环，给每节点一种颜色，希望减少颜色数并对冲突加成本。GraphColoringConstraintBias返回有限正成本，不是旧GraphColoringBias的负冲突评分。

**先准备什么：** 共用另一个独立Project副本。候选4维整数0..2，图固定环 `(0,1),(1,2),(2,3),(3,0)`；raw是不同标签数，max_colors=2统计不同标签个数，不要求标签本身只为0/1。

**放在哪：** `problem/graph_problem.py` 完整文件：

```python
import numpy as np
from blackbase.types import Feedback
from nsgablack.core import BlackBoxProblem


class ColorCountProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="cycle_color_count", dimension=4,
            bounds=[(0, 2)] * 4, objectives=["different_color_labels"])

    def evaluate(self, x):
        a = np.asarray(x, dtype=float)
        return Feedback(objectives=[float(len(np.unique(a)))], metrics={"case.graph_x": a.tolist()})


def build_problem():
    return ColorCountProblem()
```

`pipeline/graph_pipeline.py` 完整文件：

```python
from nsgablack.representation import (
    RepresentationPipeline, IntegerInitializer, IntegerMutation, IntegerRepair,
)


def build_pipeline():
    return RepresentationPipeline(initializer=IntegerInitializer(low=0, high=2),
        mutator=IntegerMutation(sigma=1., low=0, high=2), repair=IntegerRepair(low=0, high=2))
```

`bias/graph_scores.py` 完整文件：

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.specialized.graph.constraints import GraphColoringConstraintBias

MAX_COLORS = 2
ADJACENCY = np.array([[0, 1, 0, 1], [1, 0, 1, 0], [0, 1, 0, 1], [1, 0, 1, 0]])


def build_bias():
    module = BiasModule()
    module.cache_enabled = False
    module.add(GraphColoringConstraintBias(ADJACENCY, max_colors=MAX_COLORS, penalty_scale=50.))
    return module


def expected_delta(x):
    colors = np.asarray(x, dtype=int)
    too_many = len(set(colors)) > MAX_COLORS
    conflicts = any(ADJACENCY[i, j] > 0 and colors[i] == colors[j]
                    for i in range(4) for j in range(i + 1, 4))
    return 50. if too_many or conflicts else 0.
```

**接入步骤：** 共用builder和Report不变，只替换这三文件。GraphColoringConstraintBias会round候选，但不独立保证颜色域与长度；本例由IntegerRepair和Problem维数明确保障。不能传六位边向量给它，也不能从“约束”类名推断raw门在过滤冲突。

**怎样判断接对：** 报告候选4维整数，raw是标签数，selection加0或50；delta_matches按固定环冲突检查。理想合法两色交替，但有限预算不保证找到。整体标签重命名可等价，身份仍按token/版本，不能按同分数合并候选。

**运行入口：** 共用default组命令，未执行。

### 变体一：允许最多三种标签

**目的：** 放宽颜色上限，同时保留最少颜色raw目标。**改在哪里：** 只将评分模块常量改为：

```python
MAX_COLORS = 3
```

**行为变化：** 三种标签不再单独触发上限罚，邻接冲突仍罚50。**限制：** raw仍偏好较少标签；修改上限不会改变图拓扑、整数布局或自动切换算法。

## migration.bias.graph_scores · 七个旧图评分器未装配

**什么时候用：** 命中 `bias.graph_connectivity`、`graph_sparsity`、`graph_degree_distribution`、`graph_shortest_path`、`graph_max_flow`、`graph_coloring`、`graph_community`（均bias.前缀），期待常见图性质会自动按正确最小化方向施加。

**先准备什么：** 当前源码 `bias/specialized/graph/base.py`。GraphStructure仅传adjacency_matrix会调用不存在的_build_edge_list_from_matrix（源码定义的是另一个名字），可能在评分前就失败。本书不通过猴子补丁绕开它；实际可用替代是本书明确边位/颜色布局的完整Case，未构造GraphStructure。

**放在哪：** 七个旧类都不add。图结构硬条件归Problem，明确软成本可用当前GraphConstraint类或Case纯CallableBias；需要新的流/路径/社区目标则在Problem明确实现，不能把更换符号说成修好了整个旧类。

**接入步骤：** 各key的具体阻碍如下。

- ConnectivityBias：空图与断开返回负罚，连通给正奖励；直接加到最小化目标方向相反。NetworkX只add边，未add孤立节点，单条边也可能被当作已连通。
- SparsityBias：偏离target_edges越大返回越负的指数值，最小化会奖励偏离，且极端值可溢出。
- DegreeDistributionBias：uniform返回负方差，scale_free返回正Gini，small_world返回正聚类；不能统一解释成“接近相应结构更好”。
- ShortestPathBias：不连通/空图给大负值；NetworkX遗漏孤立节点。GraphUtils只按i<j抽边，不提供完整有向候选语义。
- MaxFlowBias：较大flow给正成本，空图给负成本；容量被max(weight,1)改变，不是任意业务容量的忠实转交。
- GraphColoringBias：冲突数返回负成本，最小化奖励冲突；维数不匹配也给负成本，不能用来安全验证节点色。
- CommunityDetectionBias：正modularity直接加到最小化目标会压低模块度；权重矩阵与按正边计度的混用也需明确，不等于通用加权社区目标。

七者多数compute内外重复乘weight。给负weight并不能同时解决孤立节点、编码、有向边、构造器和有限值问题；不能在教程里补几项私有属性就宣称正常。

**怎样判断接对：** 先选本书树/匹配/着色主例的一种完整配方，用精确候选与独立0/50公式核对soft成本；需要硬连通性时参考配套候选布局的显式Problem约束。它们不等价于最大流、最短路径或社区检测，后者仍须正确Problem/Provider实现。迁移记录不计作七个旧类已可用。

**运行入口：** 本书正式Project命令运行实际替代组件，旧七类没有正常执行声明。

### 变体一：改纯评分为独立raw目标

**目的：** 不让业务图目标藏在Bias里。**改在哪里：** 在树/匹配Case的EdgeCountProblem.evaluate把原边数目标换成明确加权边成本，例如：

```python
def evaluate(self, x):
    a = np.asarray(x, dtype=float)
    return Feedback(objectives=[float(a @ np.array([1., 4., 5., 2., 6., 3.]))],
                    metrics={"case.graph_x": a.tolist()})
```

**行为变化：** raw是显式边成本，结构条件仍由已装配的正软罚判断。**限制：** 最低成本树不是最短路径或最大流；没有新建旧GraphStructure，也没有修复七个评分器。

## migration.bias.graph_paths · 三个旧路径验证器未装配

**什么时候用：** 命中 `bias.graph_tsp_constraint`、`bias.graph_path_constraint`、`bias.graph_hamiltonian_constraint`，期待完整的路径合法性与边存在检查。

**先准备什么：** 看 `bias/specialized/graph/constraints.py` 的实际逻辑。TSP只按unique个数/重复检查，未完整校验0..N-1域，闭合检查是pass；二进制提取无边时还会自行选未访问节点。Path._is_connected和Hamiltonian._are_adjacent直接返回True，不检查业务图；Path较长编码会直接生成range(num_nodes)。

**放在哪：** 旧三类不装配。需要城市访问顺序时使用配套《候选布局》repr.permutation的完整Project/Problem/Pipeline/Adapter/Report，严格PermutationFixRepair保障0..5，Problem自己计算真实闭合距离。它是当前可用排列路径示例，不是已实现任意稀疏图路径合法性。

**接入步骤：** 先按配套完整TourProblem、PermutationInitializer/Swap/Fix和VNS builder接通候选；要限制允许边，在Case Problem.evaluate_constraints明确检查所有相邻对和必要闭合边。不在Bias里补一份假“全相连”图，也不把排序键编码与排列本体互换。

**怎样判断接对：** 对候选严格核对覆盖域/长度/唯一性，再按业务允许边逐项检查；raw路径长度来自同一版本。输出有序城市候选本身，不把“x找到y”解释成“x的分数等于y”。配套默认VNS按违反罚比较，不是硬门：若要求严格准入须显式装配FeasibleEvaluationAcceptance并合理处理无可行初值情况。

**运行入口：** 配套正式catalog_recipes Project default组；运行的是明确Problem与排列算子，旧三类未装配或修复。

### 变体一：为已有TourProblem显式声明允许边

**目的：** 把缺失的拓扑检查放回Problem。**改在哪里：** 在配套Problem文件中给TourProblem增加下方evaluate_constraints，原evaluate/工厂/排列Pipeline保留。这里允许边为六节点环，示例并不保证短预算找得到合法路线。

```python
def evaluate_constraints(self, x):
    a = np.asarray(x, dtype=float)
    if a.shape != (6,) or not np.array_equal(np.sort(a), np.arange(6)):
        return np.array([1.])
    p = a.astype(int)
    allowed = {frozenset((i, (i + 1) % 6)) for i in range(6)}
    forbidden = sum(frozenset((int(p[i]), int(p[(i + 1) % 6]))) not in allowed
                    for i in range(6))
    return np.array([float(forbidden)])
```

**行为变化：** raw违反量真正记录不允许边数量；配套VNS比较可看到它。**限制：** 它是闭合无向Tour检查，不是一般有向路径、多起终点或Hamiltonian求解器；旧验证器的恒True方法没有因此被修复。未执行可行性搜索或验收。
