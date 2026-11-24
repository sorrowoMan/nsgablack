# 候选布局：连续比例、整数矩阵、二进制边和排列

四节各自使用完整 `examples/cases/catalog_recipes/` Project 的独立副本，不把互斥的 Problem/Pipeline 叠加。以下是源码核对后的操作说明，没有执行这些改装 Case、调用模型或生成运行收据。候选布局与算法 Unit 分开：本例的 VNS 持有当前候选与邻域结构，数组仍表示问题的一个解。

## layout.shared_case · 四种布局共用的正式入口和结果观察器

先复制整个 `examples/cases/catalog_recipes/`，保留 Project 的 `project_config.py`、`run_project.py`、L0 与 `cases/composite/` 的包和规范 CLI。该 Project 的 default 组已经只运行 composite。下面所有路径相对 `cases/composite/`；不新增私有运行循环。

四种布局均新增完整 `plugins/layout_report.py`：

```python
from pathlib import Path
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json


class LayoutReport(Plugin):
    def __init__(self, search, path):
        super().__init__(name="layout_report")
        self.search, self.path = search, Path(path)

    def on_solver_finish(self, result):
        control = self.solver
        refs = tuple(self.search.get_pool_refinement_results(control))
        if not refs:
            raise RuntimeError("no evaluated VNS result was delivered")
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        self.payload = {
            "run_id": control.run_session.run_id,
            "refs": [ref.as_dict() for ref in refs],
            "candidates": batch.numeric_matrix.tolist(),
            "raw_objectives": raw_f.tolist(),
            "raw_violations": raw_v.tolist(),
            "current_score": self.search.current_score,
            "runtime": self.search.get_runtime_context_projection(control),
        }

    def on_solver_finalized(self, result):
        atomic_write_json(self.path, self.payload)
```

完整替换同 Case 的 `build_solver.py`：

```python
from pathlib import Path
from nsgablack.adapters import VNSAdapter, VNSConfig
from nsgablack.core import ComposableSolver
from .pipeline import build_pipeline
from .plugins.layout_report import LayoutReport
from .problem import build_problem


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("edit this recipe's declared factories explicitly")
    search = VNSAdapter(name="layout_search", config=VNSConfig(
        batch_size=4, k_max=2, base_sigma=.15, scale=2.,
        restart_on_stagnation=False,
    ))
    solver = ComposableSolver(
        problem=build_problem(), representation_pipeline=build_pipeline(),
        adapter=search, resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True,
    )
    solver.set_random_seed(37)
    solver.set_max_steps(12)
    solver.add_plugin(LayoutReport(search,
        Path(__file__).resolve().parent / "results" / "layout.json"))
    return solver
```

此 builder 不提前创建 Unit，也不自行调用 evaluate/repair。先正常评估一个起点，后续由 VNS 提出邻居。`restart_on_stagnation=False` 避免在运行最后留下尚未评估的新初值；这也意味着停滞后不会随机重启。

每节提供的 `build_pipeline` **完整替换原 `pipeline/main.py` 的同名函数**，保留该文件的 `build_unit_binding/run_pipeline_slot`，因此原 `pipeline/__init__.py` 导出仍有效。新增 imports 写在函数内，不依赖其它例子的导入。`problem/__init__.py` 则按本节整文件替换。

**运行入口：** 在 Project 副本根目录依次执行：

```powershell
python run_project.py --group default --check --build-check
python run_project.py --group default
```

第一条只检查构造，第二条才求解。读本次 `cases/composite/results/layout.json`，核对 run_id 与 Project 终态；旧 JSON 不会因为新运行失败而自动消失。观察器在 finishing 复制已提交结果，finalized 后写本地文件，它不是新建的权威 Artifact 或 checkpoint 历史。

结果 `refs/candidates/raw_objectives/raw_violations` 逐行对齐。数值矩阵可能用浮点表示 0/1 或整数，判断离散语义时检查数值，不凭 dtype 下结论。VNS 本例交付自己的最终已评估当前点，不是所有试探、整个解池或一个种群；没有自定义 selector、重启或 Bias，比较规则为原目标加 `1e6 × violation`。这不是“硬可行性接纳”：不满足约束的试探仍可能被默认接纳进池，再由 VNS 拒绝移动；下文分别说明实际约束保障。

Pipeline 会按正式种子接口设置顶层算子的 RNG；本书未验证 checkpoint 重放。包装器内部算子的种子传递与持久状态须另查，不能从一次 `set_random_seed(37)` 推断任意嵌套对象的恢复能力。

## repr.continuous · 在非负单纯形上搜索三个分配比例

**什么时候用：** 解是一行三个连续数，必须非负且和为 1；目标是接近期望分配比例。`UniformInitializer` 负责来源，`ProjectionRepair` 负责问题约束，VNS 的 Unit 不承担比例编码。

**先准备什么：** 当前 nsgablack、blackbase、NumPy，以及共用入口节的独立 Project 副本、builder 和 LayoutReport。候选 `(3,)`；反馈 `(n,1)`，违反量 `(n,)`。保留 Project 的 L0，不需要外部服务。

**放在哪：** `problem/__init__.py` 整文件如下；在 `pipeline/main.py` 只替换所示工厂，保留两个 helper。其余按共用入口节保存。

**接入步骤：** Problem 完整内容：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class AllocationProblem(BlackBoxProblem):
    def __init__(self, total=1.):
        self.total = float(total)
        self.target = self.total * np.array([.2, .3, .5])
        super().__init__(name="simplex_allocation", dimension=3,
            bounds=[(0., self.total)] * 3, objectives=["allocation_error"])

    def evaluate(self, x):
        return float(np.sum((np.asarray(x, dtype=float) - self.target) ** 2))

    def evaluate_constraints(self, x):
        a = np.asarray(x, dtype=float)
        return np.array([max(0., -float(a.min())),
                         max(0., abs(float(a.sum()) - self.total) - 1e-9)])


def build_problem():
    return AllocationProblem(total=1.)
```

Pipeline 工厂完整内容：

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, UniformInitializer,
        ContextGaussianMutation, ProjectionRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(
        initializer=UniformInitializer(low=0., high=1.),
        mutator=ContextGaussianMutation(base_sigma=.15),
        repair=ProjectionRepair(sum_target=1., nonnegative=True, low=0.),
    )
```

Uniform 生成器只按 dimension 独立采样，不自动读取每一维 bounds，也不会自行生成和为 1 的值。Pipeline 初值准备会修复它。后续 ContextGaussianMutation 读取 VNS 的调用局部 mutation_sigma；Solver 在裁预算后统一修复提案再求值。不要在 mutate 中又加一遍问题修复。

`ProjectionRepair(sum_target=1.)` 是投影到非负且**等于**指定总量的单纯形；`cap` 在当前实现中也走同一等式投影，不能把它当作“总量不超过 cap”。再设置太小的逐坐标 high 会在投影后截断并破坏总和，本例故意不叠加该参数。上面的 Problem 仍独立检查最终值。

**怎样判断接对：** layout.json 一行三个坐标，均非负、总和在 `1e-9` 容差内为 1，raw_violations 为 0，raw_objectives 等于到 `[.2,.3,.5]` 的平方距离。有限 12 步不保证达到该已知最优点；修复后的坐标变化不是新 token 的理由，控制面保留同一提案身份并通知 VNS 重建候选 Unit。

**运行入口：** 执行共用入口节的两条 Project 命令，读本次 `results/layout.json`。源码可核对不等于本书运行成功。

### 变体一：从单位比例改为总量为 2 的分配

**目的：** 改变问题总量，同时保持初始化、修复和目标语义一致。

**改在哪里：** 保留 AllocationProblem 类，把其文件末尾工厂和 Pipeline 工厂分别完整替换为：

```python
def build_problem():
    return AllocationProblem(total=2.)
```

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, UniformInitializer,
        ContextGaussianMutation, ProjectionRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(
        initializer=UniformInitializer(low=0., high=2.),
        mutator=ContextGaussianMutation(base_sigma=.15),
        repair=ProjectionRepair(sum_target=2., nonnegative=True, low=0.),
    )
```

**行为变化：** 候选仍三维，和变成 2，目标变成 `[.4,.6,1.]`；按新目标检查 raw 值。**限制：** VNS 仍用原绝对 sigma，搜索尺度不随总量自动归一；只改 repair 而不改 Problem 会造成契约冲突。

## repr.integer · 六个整数数量，矩阵只是问题布局

**什么时候用：** 六个整数决策表示两台机器、三天的数量，先用一个小目标验证整数来源、变异与修复是否接通；此例没有产品切换、物料流、提前期等生产约束，不能当完整排程模型。

**先准备什么：** 共用入口节的另一个独立 Project 副本和当前 NumPy/nsgablack/blackbase。候选固定为扁平 `(6,)`；Problem 在读取时 reshape 成 `(2,3)`，反馈仍是单目标。

**放在哪：** 整体替换 `problem/__init__.py`，只替换 `pipeline/main.py::build_pipeline`；builder、观察器、L0 沿用共用入口节。

**接入步骤：** Problem 完整内容：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class QuantityProblem(BlackBoxProblem):
    matrix_shape = (2, 3)

    def __init__(self):
        super().__init__(name="integer_quantity", dimension=6,
            bounds=[(0, 5)] * 6, objectives=["quantity_error"])
        self.target = np.array([[2, 1, 3], [1, 4, 0]])

    def evaluate(self, x):
        quantity = np.asarray(x, dtype=float).reshape(self.matrix_shape)
        return float(np.sum((quantity - self.target) ** 2))

    def evaluate_constraints(self, x):
        a = np.asarray(x, dtype=float)
        return np.array([float(np.max(np.abs(a - np.rint(a)))),
                         max(0., -float(a.min())), max(0., float(a.max()) - 5.)])


def build_problem():
    return QuantityProblem()
```

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, IntegerInitializer, IntegerMutation, IntegerRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(
        initializer=IntegerInitializer(low=0, high=5),
        mutator=IntegerMutation(sigma=1., low=0, high=5),
        repair=IntegerRepair(low=0, high=5),
    )
```

high=5 包含端点。IntegerMutation 加高斯噪声、round、clip；这不是“每次加减一个整数”，也不保证提案改变。IntegerRepair 在正式问题修复位置再次保障整数和范围。显式整数边界避免依赖浮点 bounds 的 floor/ceil 扩张。

VNS 写 sigma 不代表该 IntegerMutation 会读取它；本主例使用一个固定离散邻域，k 变化不改变 sigma。变化只是提案，是否移动仍由 VNS 比较已评估反馈，不在算子内做隐藏求值。

**怎样判断接对：** layout.json 每行长度 6，所有值等于其四舍五入且位于 0..5；reshape 后两行三列，raw_objectives 等于与 target 的平方差和，raw_violations 为 0。没有行/列总量约束，不能因为字段叫 matrix_shape 就推断机器产能被满足。

**运行入口：** 用共用入口节的正式 Project check/build-check 与运行命令，按本次 run_id 读取结果；没有新运行收据。

### 变体一：显式用二维初始化和矩阵变异组件

**目的：** 让布局在候选来源处可见，而不是让用户猜 `dimension=6` 对应哪个矩阵。

**改在哪里：** Problem 和 builder 保留，完整替换 Pipeline 工厂：

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, IntegerMatrixInitializer,
        IntegerMatrixMutation, IntegerRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(
        initializer=IntegerMatrixInitializer(rows=2, cols=3, low=0, high=5),
        mutator=IntegerMatrixMutation(sigma=1., low=0, high=5),
        repair=IntegerRepair(low=0, high=5),
    )
```

**行为变化：** 初始化先生成 `(2,3)`，按行展平后返回六维；IntegerMatrixMutation 仍对传入的一维向量逐坐标加噪声，并不做跨行搬移。结果和检查字段不变。**限制：** 该矩阵来源不是种群 Unit；rows×cols 必须等于 Problem.dimension。MatrixRowColSumRepair 不是自动接上的功能，尤其非方阵不能依赖 sqrt(length) 猜形状。

## repr.binary · 位选择与无向图的边向量

**什么时候用：** 六个开关中最多选三个，收益各为 9/8/7/6/5/4。BinaryInitializer 生成位，BitFlipMutation 翻位，BinaryCapacityRepair 限制被选个数；Problem 用负收益把最大化转换为最小化。

**先准备什么：** 共用入口节的新 Project 副本、NumPy/nsgablack/blackbase。候选 `(6,)`，每个数只有 0 或 1；不是概率、连续权重或一个单独的布尔值。

**放在哪：** `problem/__init__.py` 整体替换；`pipeline/main.py` 只换工厂，其余 helper 保留。通用 builder 与 LayoutReport 仍使用同一个 VNS。

**接入步骤：** Problem 完整内容：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class SelectionProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="binary_selection", dimension=6,
            bounds=[(0, 1)] * 6, objectives=["negative_reward"])
        self.reward = np.array([9., 8., 7., 6., 5., 4.])

    def evaluate(self, x):
        return -float(np.dot(np.asarray(x, dtype=float), self.reward))

    def evaluate_constraints(self, x):
        a = np.asarray(x, dtype=float)
        binary_error = np.minimum(np.abs(a), np.abs(a - 1.)).max()
        return np.array([binary_error, max(0., float(a.sum()) - 3.)])


def build_problem():
    return SelectionProblem()
```

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, BinaryInitializer, BitFlipMutation, BinaryCapacityRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(
        initializer=BinaryInitializer(probability=.5),
        mutator=BitFlipMutation(rate=1. / 6.),
        repair=BinaryCapacityRepair(capacity=3, exact=False),
    )
```

probability 是每个位初始为 1 的概率，不是固定一半被选中；rate 是每个位被翻转的概率。容量修复会先二值化，超过三个时随机清除多余位；它不是按收益删最差的搜索策略。exact=False 允许少于三个。当前组件声明的 capacity 键已在框架注册；本例使用构造值，不往共享 context 写大对象。

**怎样判断接对：** layout.json 六个位、和不超过 3、raw_violation 为 0；raw_objectives 为对应收益的负和。已知最优为 `[1,1,1,0,0,0]`、目标 -24，但不保证有限预算得到它。VNS 只移动到更好分数，仍可能停在当前邻域局部最优。

**运行入口：** 执行共用入口节的 Project 命令并核对本轮结果。主例不需要图数据或网络库。

### 变体一：同样六个位表示四节点无向图

**目的：** 展示图的候选布局与连接约束，而不把图算法状态混入候选。

**改在哪里：** 整体替换本节 Problem 文件和 Pipeline 工厂，保留共用入口。Problem 完整内容如下：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class NetworkProblem(BlackBoxProblem):
    num_nodes = 4
    edges = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))

    def __init__(self):
        super().__init__(name="binary_network", dimension=6,
            bounds=[(0, 1)] * 6, objectives=["edge_cost"])
        self.costs = np.array([1., 4., 5., 2., 6., 3.])

    def evaluate(self, x):
        return float(np.dot(np.asarray(x, dtype=float), self.costs))

    def evaluate_constraints(self, x):
        a = np.asarray(x, dtype=float)
        adjacency = [set() for _ in range(self.num_nodes)]
        for enabled, (u, v) in zip(a, self.edges):
            if enabled > .5:
                adjacency[u].add(v)
                adjacency[v].add(u)
        unseen, components = set(range(self.num_nodes)), 0
        while unseen:
            components += 1
            stack = [unseen.pop()]
            while stack:
                for v in adjacency[stack.pop()]:
                    if v in unseen:
                        unseen.remove(v)
                        stack.append(v)
        binary_error = np.minimum(np.abs(a), np.abs(a - 1.)).max()
        return np.array([binary_error, float(components - 1)])


def build_problem():
    return NetworkProblem()
```

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, GraphEdgeInitializer, GraphEdgeMutation, BinaryRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(
        initializer=GraphEdgeInitializer(num_nodes=4, density=1.),
        mutator=GraphEdgeMutation(rate=1. / 6.),
        repair=BinaryRepair(threshold=.5),
    )
```

**行为变化：** 边严格按 i<j 排列，总长度 n(n−1)/2=6，不是 4×4 邻接矩阵。density=1 给出确定连通初始全图；后续翻边仍可能断开。BinaryRepair 只保证位值，Problem 才测连通性。VNS 用 1e6×违反量惩罚；本例边总成本最多 21，因此从可行起点不会因为节省边成本接受断图。**限制：** 池中仍可能保存被硬接纳但未被 VNS 留下的断图；这不是 GraphConnectivityRepair，也不是硬准入过滤。其它量级、Bias 或比较规则下不能沿用这个罚值论证。读结果须检查原始违反量为 0。

## repr.permutation · 一个解是一条城市访问顺序

**什么时候用：** 每个城市恰好出现一次，使用交换或反转邻域探索旅行路线；数组值是城市编号，不是待排序的连续随机键。

**先准备什么：** 共用入口节的独立 Project 副本和当前 NumPy/nsgablack/blackbase。六城市闭合回路，不使用外部地图。候选 `(6,)` 是 0..5 的排列，Problem 直接按该顺序计算长度。

**放在哪：** 整体替换 `problem/__init__.py`；在 `pipeline/main.py` 替换完整工厂并保留 helper；VNS builder 与观察器使用共用入口节。

**接入步骤：** Problem 完整内容：

```python
import numpy as np
from nsgablack.core import BlackBoxProblem


class TourProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="six_city_tour", dimension=6,
            bounds=[(0, 5)] * 6, objectives=["tour_length"])
        xy = np.array([[0., 0.], [1., 0.], [2., 1.], [1., 2.], [0., 2.], [-1., 1.]])
        self.distances = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)

    def evaluate(self, x):
        p = np.asarray(x, dtype=int)
        if not np.array_equal(np.sort(p), np.arange(self.dimension)):
            raise ValueError("tour must be a permutation of city ids")
        return float(self.distances[p, np.roll(p, -1)].sum())

    def evaluate_constraints(self, x):
        a = np.asarray(x, dtype=float)
        return np.array([0. if np.array_equal(np.sort(a), np.arange(6)) else 1.])


def build_problem():
    return TourProblem()
```

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, PermutationInitializer,
        PermutationSwapMutation, PermutationFixRepair,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(
        initializer=PermutationInitializer(),
        mutator=PermutationSwapMutation(), repair=PermutationFixRepair(),
    )
```

PermutationInitializer 读取 Problem.dimension，生成 0..5。Swap 只交换两个位置；VNS 不额外插入算术交叉。PermutationFixRepair 在问题修复位置修重复/缺失值，对合法排列保留顺序；不要替换为 PermutationRepair：后者当前按 argsort 排名，合法排列也可能改变含义，并非同一操作。也不需要 RandomKeyPermutationDecoder，否则会把城市顺序再次当排序键解释。

**怎样判断接对：** layout.json 六个整数恰好覆盖 0..5，raw_violations 为 0；raw_objectives 等于相邻城市距离加最后回首城距离。不同起点轮转和反向路线可能同长，不能以分数相同判定候选身份相同。有限邻域搜索不提供全局最短路线保证。

**运行入口：** 使用共用入口节的正式 Project 命令，核对本轮 layout.json 和 Project 终态。没有执行收据。

### 变体一：让 VNS 的 k 真正选择交换和反转两个邻域

**目的：** 从单一交换邻域切到“交换失败后试反转”，不改变 Problem 或候选布局。

**改在哪里：** 完整替换 Pipeline 工厂；共用 VNS 的 k_max=2 保留，k≥1 都会使用最后一个算子。

```python
def build_pipeline(*, resource_context=None, component_overrides=None):
    from nsgablack.representation import (
        RepresentationPipeline, PermutationInitializer, PermutationSwapMutation,
        PermutationInversionMutation, PermutationFixRepair, ContextSelectMutator,
    )
    if component_overrides:
        raise ValueError("this recipe uses its declared pipeline")
    return RepresentationPipeline(
        initializer=PermutationInitializer(),
        mutator=ContextSelectMutator([
            PermutationSwapMutation(), PermutationInversionMutation(),
        ]),
        repair=PermutationFixRepair(),
    )
```

**行为变化：** ContextSelectMutator 读取本次 VNS 写出的 vns_k：0 选 swap，1/2 选 inversion。Inversion 反转 `[i:j]`，不含 j；选到相邻位置时可能没有实际改变。**限制：** wrapper 当前没有递归种子/状态转发契约，本变体不保证与主例同 seed 轨迹一致或精确恢复；换邻域不自动获得 2-opt 的接受改进、距离矩阵读取或更强最优性。raw 结果仍按原路线问题核对。

源码依据：`representation/continuous.py`、`integer.py`、`matrix.py`、`binary.py`、`graph.py`、`permutation.py`、`context_mutators.py`、`base.py`，`adapters/vns/adapter.py` 及原 catalog_recipes/composite 的正式 Project/Case 入口。
