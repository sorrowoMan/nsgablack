# 多样性偏好：先绑定参考种群，再解释软评分

本书区分当前正式 Unit 偏好与五个仍可导入的旧类。第一节给出完整的新装配；后五节是对应旧 Catalog key 的边界与迁移说明，不表示旧类已装入该 Case。正文按源码静态核对，未运行算法、模型或文中命令，没有新增运行收据。

## bias.unit_preference · 把候选新颖性绑定到一个明确的种群实例

**什么时候用：** 同一原始目标下，希望更远离参考种群的试探点获得软奖励；还需要知道参考的是哪个 Adapter、哪一版 Unit。这里实际使用 `PopulationDiversityPreference`，不是把整个解池误当作种群，也不把偏好当作硬接纳。

**先准备什么：** 当前 nsgablack、blackbase、NumPy。复制现有 `examples/cases/bias_gallery/` Project，保留 `project_config.py`、`run_project.py`、`cases/bias_gallery/` 的包文件和规范运行入口。其 default 组的 main 阶段调用 bias_gallery，资源由 Project 的 L0 发放。现有 `problem/example_problem.py::SphereProblem(dimension=2)` 定义二维 `[-5,5]` 候选、平方和原始目标、空硬约束。本节只改副本，不依赖本书其它节。

**放在哪：** 完整替换副本的 `cases/bias_gallery/build_solver.py` 为下方文件。为便于独立照做，本例把小型观察器也放在同一入口；正式大项目可以再把它移入 plugins/，但不能遗漏导入和挂载。参考 Adapter 就是这里的 `search`，OWNER 是给该实例绑定的稳定标签；不是类名，也不负责创建 Unit。

**接入步骤：** 构造 NSGA2、绑定新颖性评分器，再挂到 Solver。`UnitPreferenceBias.from_adapter` 只登记身份和读取方式，不提前 ensure_unit。实际初始化/提案需要结构时由 Adapter 建立 PopulationUnit；求值阶段读取它的脱离只读视图。初始化、变异由 Adapter 调用，ClipRepair 仍属于问题管线。

```python
# cases/bias_gallery/build_solver.py
import json
from pathlib import Path
from nsgablack.adapters import NSGA2Adapter
from nsgablack.bias import (
    BiasModule, PopulationDiversityPreference, PreferenceQuery, UnitPreferenceBias,
)
from nsgablack.core import ComposableSolver, FeasibleEvaluationAcceptance
from nsgablack.plugins.base import Plugin
from nsgablack.representation import (
    RepresentationPipeline, ClipRepair, UniformInitializer, GaussianMutation,
)
from .problem.example_problem import SphereProblem

OWNER = ("bias_gallery", "population_search")


class PreferenceReport(Plugin):
    def __init__(self, search, output):
        super().__init__(name="population_preference_report")
        self.search = search
        self.output = Path(output)

    def on_solver_finish(self, result):
        control = self.solver
        view = self.search.preference_view(owner_path=OWNER)
        if view is None:
            raise RuntimeError("reference Adapter never created its Unit")
        refs = self.search.get_population_solution_refs(control)
        batch = control.read_solutions(refs)
        raw_f, raw_v = control.solution_pool.read_raw_feedback(refs)
        _, selection_f, selection_v = self.search.get_population_snapshot()
        whole = PopulationDiversityPreference().evaluate(
            PreferenceQuery("unit", unit=view))
        self.payload = {
            "run_id": control.run_session.run_id,
            "owner_path": list(view.owner_path), "unit_id": view.unit_id,
            "revision": view.revision,
            "tokens": list(view.candidate_tokens),
            "refs": [ref.as_dict() for ref in refs],
            "candidates": batch.numeric_matrix.tolist(),
            "raw_objectives": raw_f.tolist(), "raw_violations": raw_v.tolist(),
            "selection_objectives": selection_f.tolist(),
            "selection_violations": selection_v.tolist(),
            "mean_nearest_distance": whole.value,
            "distance_direction": whole.direction,
            "evaluations": control.evaluation_count,
        }

    def on_solver_finalized(self, result):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this example uses its explicitly bound components")
    search = NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3))
    module = BiasModule()
    module.add(UnitPreferenceBias.from_adapter(
        PopulationDiversityPreference(), search, owner_path=OWNER,
        name="reference_population_novelty", weight=.15))
    control = ComposableSolver(problem=SphereProblem(dimension=2),
        adapter=search,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(-5., 5.)),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    control.set_bias_module(module)
    control.set_random_seed(17)
    control.set_max_steps(6)
    control.add_plugin(PreferenceReport(search,
        Path(__file__).resolve().parents[2] / "results" / "population_preference.json"))
    return control
```

`search` 同时是搜索所有者和参考 Unit 所有者；本例只有这一个 Adapter，没有把多策略中的其它种群混进来。未来换成复合搜索时须保留真实叶实例并分别绑定，不把顶层容器冒充参考种群。默认空 apply_to_paths 表示此 Solver 的全部候选都可消费偏好；OWNER 只标记参考身份，并不自动限制候选来源范围。

候选范围的分数是到参考群体的最近欧氏距离，方向为 maximize。桥接层把它转为最小化增量，再由 Bias 的 weight 乘一次：本例选择目标是原始目标减去 `0.15 × 当次新颖性`。已知 token 时排除它占据的所有槽位；未知 token 不伪造身份，数值相等也不等于同一个候选。变量单位应先明确，本组件不自动归一化。

Report 还用同一评分器的 unit 范围记录最终群体平均最近邻距离；这个观测值不是另一次 Problem 求值。报告读取的是同一批最终成员的精确引用，写出发生在 finalized 后，只是本地观察文件。它不新增权威 Artifact，也不重新计算成员过去的选择分数。

**怎样判断接对：** 正常完成后打开 Project 副本的 `results/population_preference.json`，核对本轮 run_id。refs、tokens、candidates、两套反馈的行序对应；默认完整预算下成员容量为 12。逐行核对 raw_objectives 为坐标平方和，raw_violations 为零；正权重的新颖性奖励使 selection_objectives 不大于对应 raw 值，初始或零距离成员可以相等。不能用最终 mean_nearest_distance 倒推每个成员送评时的偏好：当时的参考群体可能不同。distance_direction 应为 maximize，owner_path 应为本节 OWNER；Unit 的 revision 是结构内容版本，不是 generation。这里显式装配 FeasibleEvaluationAcceptance，硬门按 raw 违反量判断；Sphere 空约束不能演示拒绝案例。换有约束 Problem 时，保留该门也不能让软选择分数冒充可行性依据。

**运行入口：** 在该 Project 副本根目录执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。前者检查装配，不证明行为正确。文件只在成功完成的发布通知后更新；旧文件或原项目历史结果不能证明本次运行。本书没有执行这些命令，也不给出随机最优值或性能提升保证。

### 变体一：只观察群体多样性，保持原始选择目标

想先知道种群是否挤在一起，而不改变 NSGA2 的选择压力时，保留上面的 imports、OWNER、PreferenceReport，只把整个 build_solver 函数替换为下面版本。Report 中的 `PopulationDiversityPreference().evaluate(PreferenceQuery("unit", ...))` 仍读取同一个实际 Unit；无需挂一个空的 Bias。

```python
def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    if strategy not in (None, "", "default", "none") or component_overrides:
        raise ValueError("this example uses its explicitly bound components")
    search = NSGA2Adapter(population_size=12, offspring_size=6,
        initializer=UniformInitializer(-5., 5.),
        mutator=GaussianMutation(sigma=.3))
    control = ComposableSolver(problem=SphereProblem(dimension=2),
        adapter=search,
        representation_pipeline=RepresentationPipeline(repair=ClipRepair(-5., 5.)),
        resource_context=resource_context, plugin_strict=True, snapshot_strict=True,
        evaluation_acceptance_policy=FeasibleEvaluationAcceptance())
    control.set_bias_module(None, enable=False)
    control.set_random_seed(17)
    control.set_max_steps(6)
    control.add_plugin(PreferenceReport(search,
        Path(__file__).resolve().parents[2] / "results" / "population_preference.json"))
    return control
```

此时 raw 与 selection 应相同，mean_nearest_distance 仍可读。改变选择规则后，实际搜索轨迹与成员也可能改变；不能只比较两次文件的一个距离数就认定算法更好。该变体只是观察模式，不把整体 Unit 分数自动变成一次成员替换决策。

源码入口：`bias/preferences.py::PopulationDiversityPreference/UnitPreferenceBias`、`bias/core/base.py::compute_with_tracking`、`adapters/unit_backed.py::preference_view`、`tests/test_unit_preferences.py` 与 `tests/test_bias_acceptance_boundary.py`。本节是来源用法，未新增执行证据。

## bias.diversity · 旧最近距离 Bias 的范围与迁移

**先准备什么：** 这是 `bias/algorithmic/diversity.py::DiversityBias` 的迁移说明，前一节没有装配该旧类。它的 metric 可选 euclidean、manhattan、chebyshev；`compute` 返回负最近距离，`compute_with_tracking` 再乘 weight。`diversity_history` 是求值时追加的诊断列表，不能当作正式恢复后的搜索状态。

**放在哪：** 新的正式 Case 请按前一节绑定 UnitPreferenceBias 和 PopulationDiversityPreference，而不是把 `bias_module.add(DiversityBias())` 当作已完成 Unit 绑定。前一节新组件只有欧氏距离；需要其它度量时应先提供明确的新 Preference 实现，不能声称改变了不存在的 metric 参数。

**边界：** 旧类声明 population_ref，BiasModule 需要已存在、可读、单种群的权威快照；无引用或 partitioned authority 会拒绝。它没有接受具体 Adapter/PopulationView 的接口，也不按 token 排除自身。不能为了装配先 ensure_unit，不能将两个种群合并或塞进共享 context 来绕过依赖。`tests/test_unit_preferences.py::test_legacy_diversity_rewards_distance_without_guessing_identity` 与 `test_legacy_population_dependency_rejects_missing_and_partitioned_source` 分别覆盖旧方向和缺失来源拒绝；这不等于旧类已通过完整新 Case 接入。

**推荐操作：** 用前一节主例完成显式参考；只做观测时用其变体。保留 raw 目标/违反量；迁移后的平均最近邻指标与旧诊断历史不是同一个统计量。本节不提供旧类的正常运行命令或运行结果。

## bias.diversity_crowding · 旧邻近距离均值尚非正式 Unit 稀疏奖励

**先准备什么：** 对应 CrowdingDistanceBias，构造参数只有 weight。当前实现是在候选空间算最多三个最近邻距离的均值，不是 NSGA2 目标空间的 crowding distance，也没有可调的 k 参数。

**放在哪：** 当前不提供将此旧类作为正常稀疏奖励挂入 Case 的配方。正式最近邻新颖性可按前一节接入；若业务确实要 k 邻域均值，需要一个按明确 PopulationView 评分、返回 maximize 的新策略，现有 PopulationDiversityPreference 不能通过参数切成它。

**边界：** 旧 compute 返回正的 `weight × 距离均值`，外层又乘 weight；在最小化选择中更稀疏反而增加目标值。它按数值相等排除成员，剩余邻居不足两个时返回 inf。当前 PreferenceScore 要求有限值，不能直接把该返回值塞进正式桥接层。population_ref 也未提供明确实例绑定。不能靠负 weight 或在 Case 代理里翻转一次来掩盖所有权、有限性和双重加权问题。

**推荐操作：** 先用正式新颖性/观察主例理解参考实例和反馈边界；保留本节作为修复待办。当前未找到该旧类的专门行为测试，不以导入和签名存在当作稀疏选择语义已验证；本节没有装配旧类。

## bias.diversity_sharing · 旧共享公式尚不能宣称降低拥挤选择压力

**先准备什么：** 对应 SharingFunctionBias。sigma_share 是候选距离阈值，alpha 是阈值内核的形状参数，weight 是外层偏好权重。它不创建、合并或选择解池，也不会自动限制相似成员数量。

**放在哪：** 本节只说明当前旧组件，不把它加入前一节 BiasModule。正式 Unit 新颖性可使用前一节；共享核与最近邻距离不是等价量，现有评分器没有 sigma_share/alpha 参数，不能把迁移说成参数改名。

**边界：** 代码累加阈值内的 `1 - (distance / sigma_share) ** alpha`，有贡献时返回 `weight / sharing_sum`，否则返回 weight；外层再次乘 weight。因而 sharing_sum 越大，最小化增量反而越小，不能按类名解释为自动惩罚拥挤。当前 population_ref 仍依赖单种群快照；同一候选自身也计入共享和，没有正式 token 排除。默认缓存键没有自动包含所引用种群的修订，不能宣称群体变化后一定重算。

**推荐操作：** 需要这种语义时，先明确共享核方向、重复身份、缓存与实例绑定契约，再实现/修复叶评分器。不要在 Case 中手工缓存 population 或给它假接入 Unit。未找到该旧类的专门行为测试，本书不提供其正常搜索用法或优化效果。

## bias.diversity_niche · 当前旧类没有自动维护的生态位成员

**先准备什么：** 对应 NicheDiversityBias。niche_radius 用于对坐标除以半径再 floor 分格，max_niche_size 是公式里的计数阈值；它不是解池容量，也不是一次硬接纳上限。

**放在哪：** 当前不把该旧类挂进正式 Case。代码虽然有 `update_niches(population)`，但没有发现框架为它调用该方法的正式路径；不能因为存在这个方法就声称已跟踪所属 Unit 的成员。

**边界：** 新实例 niches 为空；compute 只查询这个字典，不会按当前种群填充。即使外部手动填了计数，满格公式返回负增量，在最小化中会奖励超额，未满时却返回正增量；随后还要再乘外层 weight。niches 的候选列表没有正式状态 codec、提交事件和步骤回滚归属。把 update_niches 塞到日志钩子或纯评分回调，会额外制造未定义的更新时序，不能作为正式装配。

**推荐操作：** 若只需要观察分散程度，运行前一节的观察变体；若要严格保留每格冠军，应另外考虑实际档案/成员选择组件，不能以 Bias 名字代替。当前 PopulationDiversityPreference 没有生态位格子计数语义。本节是缺口说明，未装配旧类，也没有其专门行为测试或运行结果。

## bias.diversity_adaptive · 旧自适应名称不等于当前权重控制器

**先准备什么：** 对应 AdaptiveDiversityBias。target_diversity 比较的是参考种群平均成对欧氏距离，adaptation_rate 选择本次系数；目标距离与候选坐标单位一致，不是通用的 0 到 1 比例。

**放在哪：** 当前不提供旧类的正常自动增强多样性配方。前一节的新颖性是固定 weight 的显式 Unit 偏好；它没有 target_diversity/adaptation_rate 参数，也不会因为名字叫 UnitPreference 就自动成为自适应控制器。

**边界：** 少于两个参考成员返回零；否则代码比较平均成对距离与目标，用 `weight × (1 + rate)` 或 `weight × (1 - 0.5 × rate)` 再乘候选最近距离，外层 compute_with_tracking 又乘 weight。正距离增量在最小化中偏向更靠近成员，与“增强探索”描述不能直接对上。它不把 adapted_weight 写回自身 weight；current_diversity 只在评分时覆盖，未声明正式持久状态，候选自身排除仍按数值相等。旧 population_ref 也未绑定明确 Unit。

**推荐操作：** 先用前一节主例/观察变体分清原始目标、软奖励和参考群体。真正需要自适应时，应先确定按哪个已提交指标调整、何时调整、如何恢复，再修复对应组件；不能由教程临时代理或日志 Plugin 偷换决策。当前未找到该旧类的专门行为测试；此节不是已可运行的自适应组件说明。
