# 算法名称下的旧 Bias：先分清评分、状态与真正的搜索

本页所有绑定到旧 key 的记录都是**迁移说明，旧类未装配**。替代装配的完整代码按每节列出的正式来源一起展示；替代组件不一定与旧名称数学等价。没有执行算法、训练、命令或模型请求，也没有修复这些旧类的核心实现。

## migration.bias.diversity · 五个旧多样性类未装配

**什么时候用：** 搜索需要“候选相对明确种群的新颖性”，但 Catalog 命中了 `bias.diversity`、`bias.diversity_adaptive`、`bias.diversity_crowding`、`bias.diversity_niche` 或 `bias.diversity_sharing`。本节说明为什么不能仅按名字 add，然后给出当前可用的 Unit 偏好装配。

**先准备什么：** 采用配套来源《多样性偏好》的 `bias.unit_preference` 完整主例：复制整个 `examples/cases/bias_gallery`，二维 Sphere、边界[-5,5]、NSGA2容量12/后代6、6逻辑步、Project default组和L0都已明确。该来源完整列出 builder、初始化/变异、ClipRepair、UnitPreferenceBias、Reference Report及运行命令。

**放在哪：** 按配套主例替换 `cases/bias_gallery/build_solver.py`，挂 `UnitPreferenceBias.from_adapter(PopulationDiversityPreference(), search, owner_path=OWNER, ...)`。search是实际NSGA2实例，OWNER只标识该实例，不是类型名。不要在装配、Doctor或观察时调用ensure_unit；实际算法使用时才建结构。

**接入步骤：** 不装配这五个旧类，理由逐项如下。

- DiversityBias：负最近距离的最小化方向是合理的，但来源是旧population_ref单种群权威，不接受明确Adapter实例，不按token排除自身；不能用同一个全局快照代表多个Unit。
- AdaptiveDiversityBias：正的最近距离乘适应系数，最小化中反而压低新颖性；compute内外重复乘weight，current_diversity在逐候选评分时覆盖，不是已提交世代控制器。
- CrowdingDistanceBias：候选空间至多三个近邻的均距，不是NSGA2目标空间拥挤距离；返回正距离且重复加权，稀疏点可能更贵；邻居不足时可返回inf。
- SharingFunctionBias：阈值内核求和后用weight/sharing_sum，拥挤越大成本反而越低；自己也参与核和，无正式实例/token语义。
- NicheDiversityBias：compute读niches，但没有自动调用update_niches的正式所有者；默认空字典不是已跟踪种群。超额格子给负成本，且计数字典没有Unit事务/恢复归属。

来源是 `bias/algorithmic/diversity.py`、`bias/bias_module.py` 的旧population权威读取和 `bias/core/base.py::compute_with_tracking`；不以构造/导入成功代替语义完成。禁止给共享context塞population数组、给旧类负weight或在Case包装里翻一次符号就宣称完成迁移。

**怎样判断接对：** 按配套Report读 `results/population_preference.json`。owner_path/unit_id/revision必须来自明确search，raw平方和和选择反馈分开；正权重新颖性桥接产生负选择增量。最终平均最近邻距离只是一项观察，不是成员送评时分数的重算依据。旧类的sharing、生态位上限、k近邻和自适应规则**没有**因为迁移为最近邻新颖性就得到实现。

**运行入口：** 在Project副本运行配套的check/build-check和run_project.py。运行的是新Unit偏好，不是这五个旧类；本轮未执行。

### 变体一：先只观察，再决定是否施加偏好

**目的：** 分清“群体是否分散”和“要不要改变选择压力”。**改在哪里：** 使用配套主例的完整观察变体，把build_solver替换为其中禁用Bias的版本，Report保留。**行为变化：** raw与selection一致，仍输出同一实际Unit的平均最近邻距离。**限制：** 不提供生态位保留/共享核/自适应功能，也不为旧类补运行收据。

## migration.bias.convergence · 五个收敛类和Levy名称未装配

**什么时候用：** 命中 `bias.convergence`、`bias.convergence_adaptive`、`bias.convergence_precision`、`bias.convergence_late_stage`、`bias.convergence_multi_stage` 或 `bias.levy`，但真正想表达的是“更靠近某个Unit的参考位置”，或“后期换成更精细的搜索”。两者分别属于偏好和算法/算子编排，不能靠一个阶段常量混成一件事。

**先准备什么：** 使用与上一节相同的完整Unit偏好主例，保留其正式Project、Sphere、NSGA2、Pipeline、Report与L0。下面新增的叶偏好只读PopulationView，不维护第二份种群或历史。配套Report仍观测整体新颖性；那项指标与新的中心距离成本分开解释。

**放在哪：** 在配套主例的build_solver.py imports后定义下方完整类。在构造UnitPreferenceBias的那一行，把第一个实参 `PopulationDiversityPreference()` 改为 `CenterDistancePreference()`；search、OWNER、weight=.15和其它接线不变。不要替换Report里做整体观测的评分器。

**接入步骤：**

```python
import numpy as np
from nsgablack.bias import PreferenceScope, PreferenceScore
from nsgablack.units import PopulationView


class CenterDistancePreference:
    supported_scopes = (PreferenceScope.CANDIDATE_IN_UNIT,)

    def evaluate(self, query):
        if query.scope != PreferenceScope.CANDIDATE_IN_UNIT:
            raise ValueError("this preference scores a candidate against one population")
        if not isinstance(query.unit, PopulationView):
            raise TypeError("an explicit PopulationView is required")
        population = query.unit.population
        value = (0.0 if not len(population) else
                 float(np.linalg.norm(query.numeric_candidate - population.mean(axis=0))))
        return PreferenceScore(value, "minimize", "distance_to_bound_population_center")
```

旧实现的差异不能隐藏：ConvergenceBias用正的1/(1+距中心)并重复加权，靠中心更近反而成本更高；AdaptiveConvergenceBias把每候选调用当作fitness_history追加，且elite_solutions不是自动注册的算法精英所有者。PrecisionBias读取best/current_fitness，命中后返回常量，precision_radius未参与数值变化。LateStageConvergenceBias只按代数加常量，MultiStageConvergenceBias按阶段加常量：同代所有候选一起平移不产生同批选择区分，但跨代分数和incumbent仍可能被污染。LevyFlightBias只是对距旧population中心的饱和距离切换正负号，根本没有生成Levy随机步。

这些事实见 `bias/algorithmic/convergence.py` 与 `levy_flight.py`。上述新类仅是明确方向的参考Unit成本，不是六种旧算法的等价重实现；没有自动适应学习率或改变变异步长。

**怎样判断接对：** 新选择增量是 `.15 * 到送评时参考种群中心的距离`，因此selection应不小于对应raw；不要继续沿用新颖性奖励主例“selection不大于raw”的检查。Report的mean_nearest_distance仍是最终群体观察，不能反推历史中心。偏好不会让问题修复、硬接纳或NSGA成员选择失去各自所有权。

**运行入口：** 同一正式bias_gallery副本的run_project.py，完整命令在配套来源中。运行的是CenterDistancePreference桥接；旧六类未装配。

### 变体一：要扩大步幅时改真实算子，而非把Levy名字当随机分布

**目的：** 改变提案几何。**改在哪里：** 在同一主例构造NSGA2时，将直属mutator一项改为下段表达式，imports补齐；偏好绑定可保留或按观察变体禁用。

```python
from nsgablack.representation import GaussianMutation

large_step_mutator = GaussianMutation(sigma=0.8)
```

将该对象传入原 `NSGA2Adapter(..., mutator=large_step_mutator)`，其余字段不动。**行为变化：** 真正改变候选变化尺度，仍通过ClipRepair与正式送评。**限制：** 这是高斯大步，明确不是Levy分布；如果需要真正Levy步长，应实现有独立随机状态契约的变化组件，不在Bias里隐藏采样或用同名类冒充。

## migration.bias.local_search · 六个旧局部搜索Bias未装配

**什么时候用：** 命中 `bias.local_gd`、`bias.local_newton`、`bias.local_line_search`、`bias.local_trust_region`、`bias.local_nelder_mead`、`bias.local_quasi_newton`，希望通过已有候选做精修并拿回真正的后继解。

**先准备什么：** 采用配套《有限差分精修》的完整 `solution_pool/cases/moead_refinement` 配方。它保留二维双目标TwoCenters、共享Pipeline、MOEA/D方向池、一个真实GradientDescentAdapter worker、完整配置/薄builder/Report/Project分组与L0。无需解析梯度，不启用nested_refinement的两层VNS分支。

**放在哪：** 按配套主例逐文件保存 finite_difference_config.py、Report、包导出和build_solver.py，并追加finite_difference组。原build_refinement_adapter显式消费local_algorithm='finite_difference'。不要把旧Bias类add到module，也不要往problem_data放eval_func。

**接入步骤：** 旧GradientDescentBias.compute会在评分里直接调用eval_func估差分、更新动量，还可能额外评估lookahead；这些调用不天然经过Solver预算/repair/证据链。其它五类主要方法名是apply(x,eval_func,context)，没有覆盖compute；BiasModule实际调用共同compute接口，因此不能声称add后就在做Newton、线搜索、TR、单纯形或BFGS。共同基类的compute默认0，不会猜着转派到apply。

正式替代让起点、有限差分探针、下降提案分别经过评估/接纳；下降点必须单独送评，不能把其坐标或分数悄悄交给原候选。配套local_steps=3包含这三个阶段，steps=2不等于已评估下降解。修复后探针位移、部分接纳及精确结果由现有Adapter契约处理。来源：`bias/specialized/local_search.py`、`bias/core/base.py` 和 `adapters/gradient_descent/adapter.py`。

**怎样判断接对：** 读本轮finite_difference.json，核对4个方向任务、selected精确引用、raw双目标及MOEA/D真实成员。接纳历史、局部最终选择、返回后方向竞争不同。替代方案没有Newton Hessian、Armijo/Wolfe线搜索、Nelder-Mead单纯形或BFGS矩阵，不能把缺失的数学操作写成迁移已完成。

**运行入口：** 配套来源的正式finite_difference单Case组；未运行，不给旧六类背书。

### 变体一：精修更多方向，保留同一求值语义

**目的：** 扩大真正要精修的候选任务范围。**改在哪里：** 使用配套来源的完整变体，把配置view_count改为None，以正式subpools.all选择该MOEA/D实例全部方向；保留同一工厂/Report和预算推算。**行为变化：** worker依次消费全部方向，不复制其它Adapter的Unit。**限制：** 增加的是实际送评任务；这不提供旧局部算法缺失的Newton/线搜索/单纯形功能。

## migration.bias.bayesian · 三个旧贝叶斯Bias未装配

**什么时候用：** 命中 `bias.bayesian_guidance`、`bias.bayesian_exploration`、`bias.bayesian_convergence`，实际想要模型根据真实观测决定下一个候选，而不是把不确定性来源藏进评分。

**先准备什么：** 使用配套《贝叶斯与图搜索》adapter.bayesian_optimization的完整Case：`algorithm_semantics/cases/synchronous_bo`，一维[0,1]的(x-.25)²、正式ClipRepair、BOReport、checkpoint组件、Project L0和独立synchronous_bo组。只有NumPy，不调用外部模型API。

**放在哪：** 只替换配套所示 `adapter/__init__.py` 完整工厂：真实FixedRBFPosterior、LowerConfidenceBound和GridAcquisitionOptimizer传给BayesianOptimizationAdapter；保留原薄builder、Problem和Report。不添加三个旧Bias。

**接入步骤：** SimpleBayesianOptimizer只是观测列表与gp=None容器，没有在observe中拟合GP；Guidance的_update_model_simple为no-op，旧分支可能把种群顺序当y或直接重新调用Problem。Exploration的简单采集同样使用顺序伪标签，gp未训练时_uncertainty返回0；即使有不确定性，其正增量方向也不能被当作最小化奖励。Convergence只实现apply而非compute，历史列表也没有完整生产者。见 `bias/specialized/bayesian_biases.py`。

正式BO从归属自己的Evaluation Event取得raw观测，采集规则读取mean/std，网格优化器产生真正下一提案。接纳拒绝不抹掉已发生求值；训练数据不是随意读取某个全局种群。它目前只实现单目标BO，不能把旧多目标装配直接替换后宣称完全等价。

**怎样判断接对：** 在本轮results/synchronous_bo/summary.json看problem_calls、observations、model_revision和last_acquisition。observations.y是raw值，acquisition是选点依据，两者分开；不能把gp存在、构造成功或模型预测当真实Problem结果。原始checkpoint身份需同时核对模型/采集/初值/网格。

**运行入口：** `python examples/cases/algorithm_semantics/run_project.py --group synchronous_bo`，完整装配和变体随配套来源展示；本轮未执行。

### 变体一：业务只允许三个档位

**目的：** 将采集域限制为合法的有限决策集合。**改在哪里：** 使用配套完整档位变体，同时把初始点改为(.2,.8)，网格改为(.2,.4,.8)。**行为变化：** 真正只提出这些档位，不改Problem raw含义。**限制：** 这不意味着连续最优.25仍可达，也不提供任意多目标/投影池BO精修能力。

## migration.bias.surrogate_control · 控制建议不是可自动装配的标量Bias

**什么时候用：** 命中 `bias.surrogate_control`、`bias.surrogate_phase_schedule` 或 `bias.surrogate_uncertainty_budget`，期待自动切换真评估与近似评估比例。当前这些类是控制建议工具，未接入正式运行消费者，本节不把它们挂成运行策略。

**先准备什么：** 使用配套《评估Provider》的plugin.surrogate_eval完整Case，宿主是assembled_parallel_cases/de_bowl。已有完整DE、BowlProblem、ClipRepair、Provider工厂、只读报告、薄builder和Project L0；需要scikit-learn。该问题很便宜，只能演示接口，不能据此声称加速。

**放在哪：** 按配套文件保存plugins/evaluation.py和build_solver.py，实际装配SurrogateEvaluationProviderPlugin。三个旧控制类未装配。不要将return mapping的对象传入BiasModule，源码会明确抛TypeError。

**接入步骤：** SurrogateControlBias.apply返回{}；PhaseScheduleBias按进度选择区间并返回updates字典；UncertaintyBudgetBias读取surrogate_ready/population/surrogate_manager.get_uncertainty，返回prefilter或surrogate_eval建议。全仓运行面没有自动应用这些建议的消费者；返回了ratio不等于预算控制已生效，也不拥有L0授权。它自己的抽样RNG与多阶段变更也不能通过一个日志钩子冒充已恢复的控制策略。

正式Provider则明确接管评估、暖启真实数据、声明allow_approximate，返回逐行true/surrogate保真标记及raw约束；真实调用与控制面送评行数分别统计。不是把预测当真实值，也不是完成了上述自动自适应建议。

**怎样判断接对：** 从de_bowl/results/surrogate.json看本轮provider_stats、problem_calls和last_fidelity。固定Config确实被装配；没有auto ratio随代数变化的证明。若需要动态预算，需先完善声明的Controller/Provider配置变更、状态codec、任务冻结与恢复契约，本页没有在Case里私造该机制。

**运行入口：** 配套完整Project命令；默认还运行独立sa_valley，不能把总计数当成DE计数。没有运行或训练。

### 变体一：保留代理观察，但要求整批重新真评估

**目的：** 对账近似值与真实值，先不节省Problem调用。**改在哪里：** 在配套plugins/evaluation.py中完整替换attach_evaluation，ProviderReport和builder保留。

```python
from nsgablack.plugins import SurrogateEvaluationConfig, SurrogateEvaluationProviderPlugin


def attach_evaluation(control):
    owner = SurrogateEvaluationProviderPlugin(
        config=SurrogateEvaluationConfig(min_train_samples=12, min_true_evals=12,
            topk_exploit=0, topk_explore=0, retrain_every_call=True, random_seed=17),
        model_type="rf")
    control.configure_evaluation_policy(allow_approximate=True)
    control.add_plugin(owner)
    control.add_plugin(ProviderReport(owner))
```

**行为变化：** 原DE每批12行，此Config最低真评估配额覆盖整批；原代理预测/训练仍可能发生，报告保真应为true。**限制：** 不会自动停止模型训练开销，更不是动态阶段调度。ProviderReport来自配套同文件，不能把这段脱离正式Case单独运行；旧三个控制建议类仍未装配。
