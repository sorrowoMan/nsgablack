# 局部搜索：从正式 Case 装配到已评估结果

每节都从一个实际存在的 Project/Case 开始。代码块按注明的文件分别保存，不把多个工厂拼成另一个运行器。Project 继续发放 L0 资源，Case 的规范 builder 负责装配；本页没有执行算法或模型。

Solver 的权威 incumbent、Adapter 当前轨迹、每次送评批次是不同对象。Adapter 的 `objective_aggregation` 只配置局部比较，不会自动配置 Solver 的最终 scalarizer；没有显式 scalarizer 时，Solver 默认把原始目标求和并结合可行性比较。下面的单目标数值例子没有多目标标量化歧义。

## adapter.sa · 温度决定接受，邻域组件决定怎么移动

**什么时候用：** 希望搜索能够暂时接受较差的邻居，离开当前局部区域；同时希望温度降低时，连续变量的扰动也逐渐缩小。SA 保存一条轨迹，并不因为 `batch_size` 大于一就拥有一份可共享种群。

**先准备什么：** 使用 [assembled_parallel_cases/cases/sa_valley](../../examples/cases/assembled_parallel_cases/cases/sa_valley/build_solver.py)。原 `ValleyProblem` 的候选是 `(2,)`，边界均为 `[-4,4]`，单目标是 `(x0+1.5)^2+4*(x1-0.75)^2`。保留 `pipeline/main.py` 的 `ClipRepair(-4,4)`、`config.py` 的 `MAX_STEPS=40/SEED=29`，以及原 builder。Project 还会运行独立的 `de_bowl`；两者没有候选交接。

**放在哪：** 完整替换该 Case 的 `adapter/search.py`。原 `adapter/__init__.py` 已导出 `build_adapter`，原 `build_solver.py` 已调用它，无需额外配置分支。

**接入步骤：**

```python
# assembled_parallel_cases/cases/sa_valley/adapter/search.py
from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
from nsgablack.representation import ContextGaussianMutation, UniformInitializer


def build_adapter():
    return SimulatedAnnealingAdapter(
        name="sa_valley",
        initializer=UniformInitializer(-4.0, 4.0),
        mutator=ContextGaussianMutation(base_sigma=0.65),
        config=SAConfig(
            batch_size=1, initial_temperature=1.0, cooling_rate=0.94,
            min_temperature=1e-6, base_sigma=0.65,
            sigma_temperature_scale=1.0, objective_aggregation="sum",
            random_seed=29,
        ),
    )
```

首次提案只交出起点，经过问题管线 repair、正式求值和接纳后才建立当前分数。之后 SA 在本次局部 context 写入 `temperature` 和 `mutation_sigma`；上述 mutator 读取后者产生邻居。反馈回来后，SA 按当前温度执行接受判断，可能向较差点移动；每次邻域更新降温一次。`batch_size>1` 时邻居都从本次当前点提出，反馈按顺序处理并在首次接受后停止选择，不能称为“一步连续走了整个批次”。

**怎样判断接对：** 正式 Project 输出中找到 `request.case_name == "sa_valley"`，读取 `output.best_solution.values`（两维）、`output.best_objectives`（一项）及 `output.report.steps/evaluation_count`。当前轨迹可能比历史最佳差；在同一次 Solver 的提交后观察回调里，用下面函数区分两者。`control` 是回调实际收到的 Solver，代码不启动运行。

```python
def inspect_sa(control):
    adapter = control.adapter
    refs = tuple(adapter.get_pool_refinement_results(control))
    return {
        "trajectory": adapter.get_runtime_context_projection(control),
        "best_refs": refs,
        "best_raw": control.solution_pool.read_raw_feedback(refs) if refs else None,
    }
```

`trajectory` 的真实键包括 `temperature/sa_accepted/sa_current_x/sa_current_score`；`best_refs` 交付该 SA 选择的最好已评估版本，不能拿 `sa_current_x` 代替它。根 Solver 最佳与 SA 任务结果也须分别标注来源。

**运行入口：** 从 nsgablack 仓库根目录运行 `python examples/cases/assembled_parallel_cases/run_project.py`。原 `run_and_report.py` 额外假设 SA 为 40 步、每步一行；修改批量或组合以后应使用标准 Project 入口并同步报告假设。

**配套组件 key：** `repr.context_gaussian`、`tool.pool_task_spec`、`adapter.pool_search`。

**接口依据：** [SA 配置、起点与接受规则](../../adapters/simulated_annealing/adapter.py)、[实际 SA 工厂](../../examples/cases/assembled_parallel_cases/cases/sa_valley/adapter/search.py)、[正式结果读法](../../examples/cases/assembled_parallel_cases/run_and_report.py)。

### 变体一：固定邻域尺度，只让温度改变接受概率

**目的：** 不希望冷却同时让邻域几何越来越小，希望单独观察接受规则的作用。

**改在哪里：** 仍完整替换 `sa_valley/adapter/search.py`，原 builder、边界 repair 与入口保持。

```python
from nsgablack.adapters import SAConfig, SimulatedAnnealingAdapter
from nsgablack.representation import GaussianMutation, UniformInitializer


def build_adapter():
    return SimulatedAnnealingAdapter(
        name="sa_valley",
        initializer=UniformInitializer(-4.0, 4.0),
        mutator=GaussianMutation(sigma=0.65),
        config=SAConfig(
            batch_size=1, initial_temperature=1.0, cooling_rate=0.94,
            min_temperature=1e-6, sigma_temperature_scale=0.0,
            objective_aggregation="sum", random_seed=29,
        ),
    )
```

**行为变化：** 变化组件改成固定 sigma 的 GaussianMutation，温度仍降、Metropolis 接受仍生效；`sigma_temperature_scale=0` 使 SA 不再写随温度计算的 sigma。

**限制：** 原管线的 ClipRepair 仍可能把邻居裁到边界。固定 sigma 不保证效果更好；不能据仅改温度参数就断言邻域也改变，实际消费者是 mutator。

### 变体二：让 SA 在种群停滞时恢复供给

**目的：** 把 SA 用作候选准备与停滞恢复者，而不是与两个种群无交接地轮流运行。

**改在哪里：** 改用正式 [assembled_pool_recovery/cases/pool_recovery](../../examples/cases/assembled_pool_recovery/cases/pool_recovery/build_solver.py)，完整替换其 `adapter/composition.py`。该 Case 的 builder 已把 `DemoConfig` 传入这个工厂；保留默认配置（每种群初始 3 行、停滞门槛 1、恢复 2 步、总上限 8）及二维 PlateauProblem 和边界管线。

```python
from nsgablack.adapters import (
    NSGA2Adapter, SPEA2Adapter, PoolSearchAdapter, PoolSearchSpec,
    SimulatedAnnealingAdapter,
)
from nsgablack.representation import (
    UniformInitializer, GaussianMutation, ContextGaussianMutation,
)


def build_adapter(settings):
    producer = SimulatedAnnealingAdapter(
        name="seed_and_recovery_sa", batch_size=settings.producer_batch_size,
        base_sigma=settings.sigma, initial_temperature=0.4, cooling_rate=0.9,
        initializer=UniformInitializer(-0.15, 0.15),
        mutator=ContextGaussianMutation(base_sigma=settings.sigma),
    )
    searchers = [
        NSGA2Adapter(name="population_a", population_size=settings.population_size,
                     offspring_size=settings.offspring_size,
                     mutator=GaussianMutation(sigma=settings.sigma)),
        SPEA2Adapter(name="population_b", population_size=settings.population_size,
                     offspring_size=settings.offspring_size,
                     mutator=GaussianMutation(sigma=settings.sigma)),
    ]
    return PoolSearchAdapter(
        producer=producer,
        searches=[PoolSearchSpec(owner, initial_count=settings.initial_count_per_population)
                  for owner in searchers],
        stagnation_steps=settings.stagnation_steps,
        recovery_steps=settings.recovery_steps, restart_recovery=True,
        name="pooled_search",
    )
```

**行为变化：** PoolSearch 管准备、搜索、停滞恢复和返回竞争；两个种群各自持有成员，SA 的接纳候选通过正式池路径进入供给。恢复重开 SA 的温度和局部轨迹，不复制种群 Unit。运行 `python examples/cases/assembled_pool_recovery/run_project.py`，原 `results/trace.json` 的 `records[*].executed_phase/phase_after/stagnation/recovery_count/sa_temperature` 用来辨认实际阶段。

**限制：** 这是另一个明确的 Plateau Case，不是谷地任务的效果对照；停滞门槛并不保证任意问题都会恢复。保留其原 PoolTracePlugin 和有界记录容量，不能把旧 trace 当作本轮结果。[实际组合](../../examples/cases/assembled_pool_recovery/cases/pool_recovery/adapter/composition.py)与[观察器](../../examples/cases/assembled_pool_recovery/cases/pool_recovery/plugins/trace.py)是依据。

## adapter.gaussian_search · 在模型参数空间做无梯度搜索

**什么时候用：** 评估能返回目标，但没有梯度；或者想在同一个模型 Case 中对比“围绕最好点采样”和“每步重新初始化”。这里的 `population_size` 是每批提案上限，GaussianSearch 仍保存自己的最好轨迹，不提供 NSGA 式完整 population。

**先准备什么：** 使用 mlblack 的正式 [catalog_codec_demo/cases/linear_point](../../../mlblack/examples/cases/catalog_codec_demo/cases/linear_point/build_solver.py)。保留原 `build_solver.py`、数据/Problem/表示：24 行两特征，目标 `y=1+2*x0-0.5*x1`，模型候选为 `[intercept,w0,w1]` 共 3 维。Problem 原始目标为 `[train.mse,0]`，默认复杂度权重为零；即使它提供梯度，本节算法也不消费梯度。三仓和 NumPy 即可，不需模型 API 或 GPU。

**放在哪：** 完整替换该 Case 的 `adapter/__init__.py`。原 builder 已调用 `build_adapter(learning_rate=settings["learning_rate"])`，因此必须保留这个函数签名；其它工厂不改。

**接入步骤：**

```python
# mlblack/examples/cases/catalog_codec_demo/cases/linear_point/adapter/__init__.py
from nsgablack.adapters import GaussianSearchAdapter, GaussianSearchConfig


def build_adapter(*, learning_rate):
    del learning_rate
    return GaussianSearchAdapter(GaussianSearchConfig(
        population_size=8, mutation_scale=0.15, random_seed=17,
        initialization="population", exploit_best=True,
        include_center_candidate=True, objective_aggregation="first",
    ))
```

首批用正式 initializer 生成 8 个模型参数候选；每个都走表示修复、模型解释和 Problem 求值。反馈接纳后，Adapter 按可行性和第一目标保存最好已评估版本；下一批包含中心以及围绕中心的高斯提案。变化由 GaussianSearch 自己生成，不能通过再挂一个 pipeline mutator 推断它会自动改变本算法的高斯采样。

**怎样判断接对：** 同一次正式 Case 的 `solver.run()/fit()` 返回 TrainerResult，读 `result.best_state.values`（3 维）、`result.best_model.predict(data.X_train)`（24 行）、`result.best_feedback.objectives/metrics`。`data` 是该 builder 调用数据工厂的返回值。它们属于 Solver 权威 incumbent；局部 `first` 不配置最终 scalarizer，本例默认最终 sum 为 `MSE+0`。Adapter 的 `get_current_candidates()` 是局部最好参数，不是另一个最终结果报告。提交后精确读取其已评估选择可用：

```python
def read_gaussian_selection(solver):
    refs = tuple(solver.adapter.get_pool_refinement_results(solver))
    if not refs:
        return None
    return {
        "refs": refs,
        "candidates": solver.read_solutions(refs),
        "raw_feedback": solver.solution_pool.read_raw_feedback(refs),
    }
```

把函数放在同 Case 的观察/结果整理模块，`solver` 必须来自同一次正式运行。它读取长期池中的精确版本，不保存回调的活 Pool，也不重新初始化或重新求值。该例通常选一项，不能把 8 个提案称作 8 个最终成员。

**运行入口：** 从 mlblack 仓库根目录执行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check` 检查装配，再按需执行同一入口的 `--no-record`。保留默认组和一线程 CPU 配置；默认 `max_steps=3` 只是很短的接线预算。

**配套组件 key：** `mlblack.integration.learning_solver`、`mlblack.codec.linear_point`、`tool.solution_pool`。

**接口依据：** [Gaussian 配置、提案与精确结果](../../adapters/gaussian_search/adapter.py)、[原模型 Case builder](../../../mlblack/examples/cases/catalog_codec_demo/cases/linear_point/build_solver.py)、[模型 Problem](../../../mlblack/problems/supervised.py)、[TrainerResult 投影](../../../mlblack/integrations/nsgablack_control.py)。

### 变体一：每批从初始化分布重采样，保留历史最佳作记录

**目的：** 避免把新提案持续集中在同一个最好点附近，明确改成重复独立供给。

**改在哪里：** 同一个 `adapter/__init__.py` 完整替换为下段，其它原 Case 接线与入口保持。

```python
from nsgablack.adapters import GaussianSearchAdapter, GaussianSearchConfig


def build_adapter(*, learning_rate):
    del learning_rate
    return GaussianSearchAdapter(GaussianSearchConfig(
        population_size=8, mutation_scale=0.15, random_seed=17,
        initialization="population", exploit_best=False,
        include_center_candidate=False, objective_aggregation="first",
    ))
```

**行为变化：** `exploit_best=False` 配合 population 初始化，使以后每次 propose 都调用正式初始化；新批次不以历史最好点为中心。历史最佳仍由反馈选择和精确池引用维护，不因为重新采样就清空。这里实际控制新分布的是 Case 的模型 initializer，`mutation_scale` 不再决定这些独立初值的尺度。

**限制：** `exploit_best=False` 与 `initialization="center"` 组合不会进入该重新初始化分支，必须保留两项配套设置。重复初始化不是从池里抽已有成员；仍有正常求值成本，也不保证覆盖全局空间或改善效果。

## adapter.gradient_optimizer · 由反馈梯度推进 SGD、Adam 或 AdamW

**什么时候用：** Problem 或正式 Provider 能为当前候选返回对应梯度，希望用一阶更新，而不在 Adapter 中实现自动微分、训练数据访问或设备管理。没有梯度时应选择别的搜索器，不能把缺项填成零梯度。

**先准备什么：** 使用 mlblack 的正式 [catalog_codec_demo/cases/linear_point](../../../mlblack/examples/cases/catalog_codec_demo/cases/linear_point/build_solver.py)。其数据是 24×2 连续回归，表示候选为 3 维；原 `SupervisedRegressionProblem(use_valid_objective=False)` 返回 `[train.mse,0]`、训练损失与长度 3 的解析梯度。保留该 Problem、表示、数据工厂和 `DEFAULTS`；默认无 L2 正则。不要把本节直接移到不提供梯度的分类或区间 Problem。

**放在哪：** 完整替换该 Case 的 `adapter/__init__.py`；原 builder 已调用同名工厂并传 `learning_rate=0.05`。不增加第二个 Trainer、Provider 或运行循环。

**接入步骤：**

```python
# mlblack/examples/cases/catalog_codec_demo/cases/linear_point/adapter/__init__.py
from nsgablack.adapters import GradientOptimizerAdapter, GradientOptimizerConfig


def build_adapter(*, learning_rate):
    return GradientOptimizerAdapter(GradientOptimizerConfig.from_method(
        "gradient.sgd", learning_rate=float(learning_rate),
        weight_decay=0.0, objective_aggregation="sum", skip_infeasible=True,
    ))
```

首步先提交并评估初始化参数。Adapter 对收到的这一行 Feedback 检查梯度非空、有限且与候选同形，再按 SGD 计算下一点；下一点的原始目标要等下一次 propose、repair、evaluate、admission 后才成立。每步只消费一个候选；`current_x` 在 update 后可能已是尚未评估的后继，而 `current_score` 被清成 None。候选编解码归表示，梯度产生归 Problem/Provider。

**怎样判断接对：** 对同一次 Case 读取 TrainerResult 的 `best_state.values`（3 维）、`best_feedback.gradients`（3 维）、`best_feedback.metrics` 中的 `train.mse` 和 `result.report`。权威 `result.best_*` 来自 Solver incumbent，不等于 Adapter 最后计算的参数。本例原始目标 `[MSE,0]` 默认最终求和为 MSE；局部 `objective_aggregation` 不设置 Solver scalarizer，更不自动变换梯度。观察 Adapter 的 `step_index/last_gradient_norm` 可解释更新次数和最后实际使用的梯度范数，不据此认定最后后继已有反馈。

**运行入口：** 从 mlblack 仓库根目录运行 `python examples/cases/catalog_codec_demo/run_project.py --check --build-check`，需要执行时使用同入口 `--no-record`。默认 3 个逻辑步只评估三次参数位置，不能把第三次 update 生成的第四个位置冒充第四次已评估结果。

**配套组件 key：** `mlblack.integration.learning_solver`、`mlblack.representation.linear_point`、`tool.solution_pool`。

**接口依据：** [梯度配置、反馈检查、更新与结果](../../adapters/gradient_optimizer/adapter.py)、[原 Adapter 工厂](../../../mlblack/examples/cases/catalog_codec_demo/cases/linear_point/adapter/__init__.py)、[解析梯度与原始目标](../../../mlblack/problems/supervised.py)、[ML 权威投影](../../../mlblack/integrations/nsgablack_control.py)。

### 变体一：改用 AdamW 的矩状态与解耦参数衰减

**目的：** 对尺度不同的参数使用自适应矩更新，同时明确区分优化器衰减与 Problem 里的 L2 损失。

**改在哪里：** 完整替换同一 `adapter/__init__.py`，保持原 Problem 的 `l2=0` 默认值、3 维布局和梯度来源。

```python
from nsgablack.adapters import GradientOptimizerAdapter, GradientOptimizerConfig


def build_adapter(*, learning_rate):
    return GradientOptimizerAdapter(GradientOptimizerConfig.from_method(
        "gradient.adamw", learning_rate=float(learning_rate),
        weight_decay=0.01, max_gradient_norm=1.0,
        objective_aggregation="sum", skip_infeasible=True,
    ))
```

**行为变化：** Adapter 按梯度形状建立并恢复第一、第二矩；先进行范数裁剪，再计算 Adam 自适应步和解耦衰减项。`weight_decay` 施加到本例完整参数向量，包括截距；它不自动向原始 objectives/metrics 增加正则项，也不自动修改 Solver 的最终比较规则。

**限制：** 若同时开启 Problem 的 L2 和优化器衰减，就叠加了两个来源，不能称作同一个配置。这里没有启用 Provider 状态转移：那条路径还需显式 EvaluationGateway 与 Provider 管理的 StateRef，不能仅打开一个布尔值。改变参数布局时不能沿用不匹配的 Adam 矩状态。

### 变体二：只把已评估的局部最佳交给结果消费者

**目的：** 运行预算用完时读取一个有原始反馈的参数版本，排除 Adapter 最后保存的未评估下一点。

**改在哪里：** 在同 Case 的提交后观察/结果整理模块加入完整读取函数；由持有同次 `solver` 的正式调用方调用。算法工厂和运行入口不变。

```python
def read_evaluated_gradient_result(solver):
    refs = tuple(solver.adapter.get_pool_refinement_results(solver))
    if not refs:
        return None
    batch = solver.read_solutions(refs)
    raw_f, raw_v = solver.solution_pool.read_raw_feedback(refs)
    return {"refs": refs, "states": batch.semantic_states,
            "raw_objectives": raw_f, "raw_violations": raw_v}
```

**行为变化：** 正式结果方法交付保留精确版本的最好已评估选择；返回的原始反馈逐行与 refs 对齐。本例通常一行、目标两列。它和 TrainerResult 都不需要再次求值，但二者分别属于 Adapter 的局部比较和 Solver 的权威 incumbent，不能无条件声称同一身份。

**限制：** 这个读取函数不是自动接入其它算法的池任务；如需交接，还须显式装配来源和消费者。GradientOptimizer 声明不支持 objective-only 投影，并在反馈含 `subpool_projection` 时拒绝；不能把 MOEA/D 标量目标写回而保留旧梯度。新的投影须有完整梯度变换或 Provider 能力，本页不虚构这条接线。

## adapter.pattern_search · 用坐标轮询替代随机邻域

**什么时候用：** 没有梯度，希望每轮明确评估当前点两侧的坐标探针，而非先选择一种随机 mutator。成功时扩步，未改善时缩步；探针只是提案，经过原问题管线和反馈后才可能成为当前点。

**先准备什么：** 使用 nsgablack 的正式 [assembled_parallel_cases/cases/sa_valley](../../examples/cases/assembled_parallel_cases/cases/sa_valley/build_solver.py) 作为同问题宿主。保留两维谷地 Problem、`ClipRepair(-4,4)` 和原 builder；本节把该 Case 的算法替换为 PatternSearch，Case 名仍叫 sa_valley，不再把它解释成 SA 结果。原 Project 会同时运行独立的 DE Case。

**放在哪：** 完整替换 `sa_valley/adapter/search.py`。它的 `build_adapter()` 已由原 builder 调用；`adapter/__init__.py` 保持导出，不需要另设 algorithm 开关。

**接入步骤：**

```python
# assembled_parallel_cases/cases/sa_valley/adapter/search.py
from nsgablack.adapters import PatternSearchAdapter, PatternSearchConfig
from nsgablack.representation import UniformInitializer


def build_adapter():
    return PatternSearchAdapter(
        name="valley_pattern", initializer=UniformInitializer(-4.0, 4.0),
        config=PatternSearchConfig(
            max_directions=2, step_size=0.2, expansion=1.2,
            contraction=0.6, min_step=1e-4, objective_aggregation="sum",
        ),
    )
```

先评估一行起点；以后每轮在两维中选两个坐标，由自己的 PollUnit 生成正、负方向，共至多四个探针。预算裁剪和 repair 可能改变实际送评；Adapter 会对齐修复后的位移，再消费同批反馈，选改善点扩步或保持当前点并缩步。它不消费原 SA 的温度或管线 mutator，因此无需重复改 Pipeline。

**怎样判断接对：** 标准 Project 输出的 `sa_valley.output.best_solution.values` 仍为两维、原始目标仍一项。对持有的同次 Solver，`adapter.get_state()["step_size"]` 是真实局部步长，`get_runtime_context_projection(solver)` 提供 `mutation_sigma/adapter_best_score`；`get_pool_refinement_results(solver)` 交付已评估的最好引用。以上字段读取不会构造新的 Unit。Solver 最佳是权威 incumbent，和本轮四个探针、当前点应分别解释。

**运行入口：** `python examples/cases/assembled_parallel_cases/run_project.py`。不要沿用 `run_and_report.py` 针对原 SA 每步一行的硬编码计数断言；本节会改变该 Case 的每步提案量。

**配套组件 key：** `repr.continuous`、`tool.unit_binding`、`adapter.search_plan`、`tool.pool_task_spec`。

**接口依据：** [Pattern 配置、poll、repair 与反馈](../../adapters/pattern_search/adapter.py)、[正式 Pattern 精修用例](../../examples/cases/assembly_workbench/cases/directions/adapter/composition.py)、[本节宿主 builder](../../examples/cases/assembled_parallel_cases/cases/sa_valley/build_solver.py)。

### 变体一：坐标搜完后，把已评估最佳交给 SA 继续精修

**目的：** 先利用规则坐标探针，再让温度搜索探索局部点周围；明确交接候选身份，不让“阶段串行”冒充已经传递结果。

**改在哪里：** 完整替换同一个 `sa_valley/adapter/search.py`。原 Pipeline、Problem、40 步外层上限和 Project 入口保留。

```python
from nsgablack.adapters import (
    MultiStrategyConfig, PatternSearchAdapter, PoolTaskSpec,
    SAConfig, SearchPlanAdapter, SimulatedAnnealingAdapter, StrategySpec,
    serial, stage,
)
from nsgablack.representation import ContextGaussianMutation, UniformInitializer


def pattern_result(control, context):
    del context
    owner = next(unit.adapter for unit in control.adapter.units
                 if unit.role == "pattern")
    return owner.get_pool_refinement_results(control)


def build_adapter():
    pattern = PatternSearchAdapter(
        name="pattern_seed", max_directions=2, step_size=0.2,
        initializer=UniformInitializer(-4.0, 4.0),
    )
    anneal = SimulatedAnnealingAdapter(
        name="anneal_result", mutator=ContextGaussianMutation(base_sigma=0.1),
        config=SAConfig(batch_size=1, base_sigma=0.1, random_seed=29),
    )
    return SearchPlanAdapter(
        serial(stage("pattern", steps=5), stage("anneal")),
        strategies=[
            StrategySpec(pattern, "pattern"),
            StrategySpec(anneal, "anneal", pool_task=PoolTaskSpec(
                pattern_result, mode="refine", count="all", steps=10,
                output=None, shuffle=False,
            )),
        ],
        config=MultiStrategyConfig(total_batch_size=4, adapt_weights=False),
        name="pattern_then_anneal",
    )
```

**行为变化：** 第一个叶实际更新五次后，选择函数通过本工厂明确命名的 pattern 实例取得已评估结果。SA 从冻结引用重新建立基准并完成十次本地更新（包括基准一步）；`stage("anneal")` 不设 steps，由任务完成控制交还。完成后可从 SearchPlan 根的 `get_pool_task_results(control,"anneal")` 读取本请求最终选择，再用池读 raw feedback；`output=None` 不影响这项交付。

**限制：** 此选择函数专属于本节根 SearchPlan 拓扑，不能把另一个包装层的 `units` 当作同一角色表。40 是外层提交上限，不承诺一定用满；本装配在局部任务完成后结束。SA 当前点可能走差，最终任务结果取其最好已评估点；没有共享两个算法的 Unit 或可写排名。不要保存活 Pool 对象跨回调使用。

## adapter.trust_region_dfo · 在受控区域内采样并适应半径

**什么时候用：** 连续变量没有梯度，希望围绕当前中心在一个有界盒区域内采样，并通过实际改善决定扩大或收缩半径。这里的 radius 是各坐标偏移的无穷范数界限，不是“所有候选距中心的欧氏距离都相同”。

**先准备什么：** 使用正式 [trust_region_dfo/cases/trust_region_dfo](../../examples/cases/trust_region_dfo/cases/trust_region_dfo/build_solver.py)。保留原 `problem/example_problem.py::SphereProblem`：默认 8 维、各维 `[-5,5]`、原始单目标平方和。本节给出清楚的规范 builder，复用原 Project 的单 Case、CPU L0 及入口，不沿用模板中其它可选策略分支。

**放在哪：** 完整替换该 Case 的 `build_solver.py`，保留所有标准目录和原 `run_solver.py`。以下参数保留原入口签名；非默认 strategy 明确拒绝，避免其它分支随后覆盖本 Adapter。

**接入步骤：**

```python
# trust_region_dfo/cases/trust_region_dfo/build_solver.py
from nsgablack.adapters import TrustRegionDFOAdapter, TrustRegionDFOConfig
from nsgablack.core import ComposableSolver
from nsgablack.project import apply_solver_component_overrides
from nsgablack.representation import ClipRepair, RepresentationPipeline, UniformInitializer
from .problem.example_problem import SphereProblem


def build_solver(run_id=None, *, strategy=None, quickstart=False,
                 resource_context=None, component_overrides=None):
    del run_id, quickstart
    if strategy not in (None, "", "none", "default"):
        raise ValueError("this recipe uses the trust-region adapter")
    pipeline = RepresentationPipeline(
        initializer=UniformInitializer(-5.0, 5.0), repair=ClipRepair(-5.0, 5.0),
    )
    adapter = TrustRegionDFOAdapter(TrustRegionDFOConfig(
        batch_size=8, initial_radius=0.5, min_radius=1e-6, max_radius=2.0,
        radius_expand=1.5, radius_shrink=0.7, success_tolerance=1e-8,
        include_center=True, random_seed=17,
    ))
    solver = ComposableSolver(
        problem=SphereProblem(dimension=8), adapter=adapter,
        representation_pipeline=pipeline, resource_context=resource_context,
        plugin_strict=True, snapshot_strict=True,
    )
    solver.set_random_seed(17)
    solver.set_max_steps(12)
    apply_solver_component_overrides(solver, component_overrides)
    return solver
```

起点先单独送评；随后每轮至多八行，包括一个中心与七个盒内随机点。Adapter 先裁到 Problem 边界，正式问题管线仍处理送评版本；repair 若把邻居移出当前区域，Adapter 的修复核对会拒绝。反馈选出的改善超过本地 tolerance 才移动中心并扩半径，否则缩半径。`min_radius` 是半径下界，不是自动停机条件。

**怎样判断接对：** 同次 Solver 的 `adapter.get_state()` 有 `center/radius/best_score/selection_objectives`，中心为 8 维；`get_pool_refinement_results(solver)` 给精确已评估结果引用，池 raw feedback 为 `(n,1)/(n,)`。标准 Case 输出读 `best_solution.values`、`best_objectives` 和 `report.steps/evaluation_count`；这属于 Solver incumbent。DFO 本地默认目标和加违反量惩罚仍有自身半径容差，不能假定 Solver 最佳必定就是当前中心，也不把最后一批采样当作完整 population。

**运行入口：** 从 nsgablack 根目录运行 `python examples/cases/trust_region_dfo/run_project.py`。本 builder 明确把原两步演示换成 12 步上限，未增加资源 lease、模型后端或私有运行循环。

**配套组件 key：** `repr.continuous`、`tool.solution_pool`、`tool.pool_task_spec`、`tool.subpools`。

**接口依据：** [DFO 真实配置与盒采样](../../adapters/trust_region_dfo/adapter.py)、[基准、区域 repair 与半径更新](../../adapters/trust_region_base/adapter.py)、[原 SphereProblem](../../examples/cases/trust_region_dfo/cases/trust_region_dfo/problem/example_problem.py)、[Solver incumbent 评分](../../core/composable_solver.py)。

### 变体一：作为 MOEA/D 方向池的局部消费者

**目的：** 局部区域沿每个方向的冻结比较规则精修，再把候选交还方向所有者竞争，而非对两个目标直接求和后冒充 MOEA/D 精修。

**改在哪里：** 改用正式 `solution_pool/cases/moead_refinement`，保留 [adapter/refinement.py](../../examples/cases/solution_pool/cases/moead_refinement/adapter/refinement.py) 已有 `local_algorithm="trust_region"` 分支。它实际返回 TrustRegionDFOAdapter；在该 Case `build_solver.py` 只把原 `options = dict(config or {})` 替换为以下一行，其余原 builder 保留：

```python
options = {**dict(config or {}), "directions": 8, "view_count": 3,
           "workers": 1, "local_steps": 3, "local_algorithm": "trust_region"}
```

`config` 是这个原 builder 的真实参数。不要只改 `CaseConfig.adapter_key` 或传给不消费这些项的其它 Case；上述 options 确实传给 `build_refinement_adapter` 并用于原步数推算。

**行为变化：** 使用该 Case 自带的二维 TwoCenters 与 `[-2,2]` 共享管线。MOEA/D 先发布 8 个已评估方向视图，局部任务选择其中 3 个；单个 TR worker 依次消费冻结输入，基准重新求值，使用冻结权重/参考点解释本层新反馈。原始目标始终两列。三个本地更新包含基准一步，输出不是一个未评估的新中心。

完成并提交后，持有同次 Solver 的结果消费者可这样读局部任务最终选择：

```python
def read_local_region_results(solver):
    worker = next(unit.adapter for unit in solver.adapter.units
                  if unit.role == "local" and unit.unit_id == 0)
    refs = tuple(worker.get_pool_task_results(solver))
    return {"refs": refs,
            "raw_feedback": solver.solution_pool.read_raw_feedback(refs) if refs else None}
```

**限制：** 原 factory 的 `output="refined"` 累积接纳试探，并把该集合交回 MOEA/D 重新评估竞争；它不是上面每个任务最终选择的别名，也不承诺这些局部结果全部成为 MOEA/D 成员。运行中未完成请求不能提前取最终结果。运行 `python examples/cases/solution_pool/run_project.py` 会按原默认组同时执行其余两个 Case；不要把那个 Project 的总计数当作本局部任务计数。该变体保留正式 [builder 的默认预算推算](../../examples/cases/solution_pool/cases/moead_refinement/build_solver.py)，不手写嵌套搜索循环。
