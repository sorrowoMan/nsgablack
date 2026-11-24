# 软偏好、场景求值与历史档案的装配扩展

下面的变体承接各组件已有主例。先复制所指的完整标准 Project，再修改明确列出的文件；不在网页执行代码，不给共享 context 写候选矩阵。运行状态以本版独立收据为准。

## extension.bias.callable

### 变体一：在真实目标之外，奖励一个偏好的参数区间

**目的：** “希望参数接近零”和“希望落在业务偏好区间”是不同规则。本例复用 `algorithm_semantics/synchronous_bo`：Problem 仍计算 `(x-.25)^2`，另外奖励接近 `x=.5` 的候选。它是软折中，不把 `.5` 改成 Problem 的真最优，也不把区间外候选当作不可行。

**改在哪里：** 在 `examples/cases/algorithm_semantics/` 的独立副本中，将 `cases/synchronous_bo/bias/__init__.py` 完整替换为：

```python
import numpy as np
from nsgablack.bias import BiasModule
from nsgablack.bias.domain.callable_bias import CallableBias


def prefer_operating_band(candidate):
    x = np.asarray(candidate, dtype=float).reshape(-1)
    if x.shape != (1,) or not np.all(np.isfinite(x)):
        raise ValueError("this preference requires one finite parameter")
    reward = max(0.0, 0.25 - abs(float(x[0]) - 0.5))
    return {"reward": reward}


def build_bias(weight):
    module = BiasModule()
    if weight:
        module.add(CallableBias("operating_band", prefer_operating_band,
                                weight=float(weight), mode="reward"))
    return module
```

该工厂保留宿主的 `build_bias(weight)` 签名，`weight=0` 仍表示关闭。为了在这次运行显式启用它，在该 Project 的 `project_config.py` 中、原 `STAGES` 定义之后加入以下配置；只覆盖同名独立阶段，不更改另外两种算法：

```python
for stage in STAGES:
    if stage["name"] == "synchronous_bo":
        stage["component_overrides"] = {
            "synchronous_bo": {"config": {"bias_weight": 0.2, "max_steps": 2}}
        }
```

**如何运行：** 从 nsgablack 仓库根目录运行副本对应的 `run_project.py --group synchronous_bo --check --build-check`，通过后去掉 `--check --build-check` 真正运行。这次覆盖把例子缩成两步，便于查看起点之后的第一批模型提案。若直接使用原示例目录，命令为 `python examples/cases/algorithm_semantics/run_project.py --group synchronous_bo`。这个显式覆盖只属于该组；默认 `semantics` 组不会因此自动获得同一个覆盖。

**怎样检查：** 按本页的“公用观察器”保存 `cases/synchronous_bo/plugins/feedback_observation.py`，在该 Case 的 builder 返回前挂载它。终端 `feedback-observation` 中，对每个候选，选择目标应为 `raw - 0.2 * max(0, .25-abs(x-.5))`。例如 `x=.5` 时 raw 为 `.0625`、奖励贡献为 `.05`、选择目标为 `.0125`；`x=.25` 时奖励为零。这里只是在说明可手算的规则，不是承诺算法本轮一定提到这两个点。正式 `results/synchronous_bo/summary.json` 的 `observations[*].y` 和 `raw_best` 仍是原问题值；不能把它们解释成已扣奖励的曲线，也不要再调用一次 Problem 伪造对照数据。

**边界：** 字典里的 `reward` 是 CallableBias 支持的返回值形态，降低目标由 `mode="reward"` 决定，函数不要再手工取负或乘权重。函数不读取种群、不依赖 Unit，也不写历史；真正的区间硬约束仍应写进 Problem/问题修复与硬接纳。这里更换偏好不会使同步 BO 的模型观测改成偏好分数。

## extension.bias.risk

### 变体一：最坏观测超过风险预算时才增加软成本

**目的：** 有些任务接受小范围波动，只希望对“观察到的最坏损失超过 3”增加选择压力。直接使用 `RiskBias(mode="worst_case")` 会把整个最坏损失都加进去；下面复用它的指标读取，只惩罚超预算部分。

**改在哪里：** 在 `examples/cases/risk_bias/` 的独立副本中，将 `cases/risk_bias/bias/risk.py` 完整替换为下列代码。`build_solver.py` 已调用 `build_risk_bias()`，无需换算法或另注册 Provider；保留原 `evaluation/risk_evaluation.py` 的 `reduce="mean"` 和 8 场景配置。

```python
import numpy as np
from nsgablack.bias import BiasModule, RiskBias


class BudgetedWorstCaseRisk(RiskBias):
    cacheable = False
    requires_metrics = ("mc_max",)
    missing_metrics_policy = "error"

    def __init__(self, loss_budget=3.0):
        super().__init__(name="budgeted_worst_case", mode="worst_case",
                         weight=0.2, metric_prefix="mc")
        self.loss_budget = float(loss_budget)
        if not np.isfinite(self.loss_budget):
            raise ValueError("loss_budget must be finite")

    def compute(self, candidate, context):
        observed = np.asarray(context.metrics["mc_max"], dtype=float).reshape(-1)
        if observed.shape != (1,) or not np.all(np.isfinite(observed)):
            raise ValueError("this risk budget requires one finite loss metric")
        worst_loss = super().compute(candidate, context)
        return max(0.0, worst_loss - self.loss_budget)


def build_risk_bias():
    module = BiasModule()
    module.add(BudgetedWorstCaseRisk(loss_budget=3.0))
    return module
```

**如何运行：** 使用该副本的正式 `run_project.py --check --build-check`，再运行 `run_project.py`。从原仓库目录运行则是 `python examples/cases/risk_bias/run_project.py`。仍由 Project 发放 CPU 授权，Case 保持原来的两步 TrustRegionDFO 搜索与场景求值。

**怎样检查：** 按“公用观察器”保存 `cases/risk_bias/plugins/feedback_observation.py` 并在该 builder 返回前挂载它，读取终端的 `feedback-observation`。当前候选 `mc_max` 为 `[7]` 时，新增选择成本为 `.2*(7-3)=.8`；为 `[2]` 时贡献为零。原始目标仍为同候选 8 个场景损失的均值，原始违反量也不变。上述指标示例用来核对公式，不是本轮随机搜索的固定输出。该叶组件标为 `cacheable=False`，避免把一次场景统计得到的标量复用于之后的另一组场景。

**边界：** `super().compute` 返回未加权风险值，框架随后统一乘 `.2`，不能在函数里再次乘权重。超预算只增加软成本，不是拒绝接纳、机会约束或概率保证；样本最大值也不是整个随机分布的真实最坏情况。此类显式只接受单目标损失，不能把多个单位不同的目标直接平均成业务风险预算。仍需按实际反馈检查指标已产生；不以缺指标时的零值宣称风险约束已满足。

## extension.plugin.monte_carlo_eval

### 变体一：把经验上尾损失直接定义为原始目标，取消重复风险偏好

**目的：** 如果业务真正优化的是“最差四分之一场景的平均损失”，应让求值方返回这个目标，而不是保持均值 raw 后又把一个名为 CVaR 的近似 Bias 当作真目标。本例保留同一个候选、同样的 8 场景和算法，只改变求值解释及偏好装配。

**改在哪里：** 在 `risk_bias` Project 独立副本中，将 `cases/risk_bias/evaluation/risk_evaluation.py` 完整替换为：

```python
from nsgablack.plugins.evaluation.monte_carlo_evaluation import (
    MonteCarloEvaluationConfig, MonteCarloEvaluationProviderPlugin,
)


def attach_scenario_evaluation(solver):
    plugin = MonteCarloEvaluationProviderPlugin(
        config=MonteCarloEvaluationConfig(
            mc_samples=8, reduce="cvar", cvar_alpha=0.25, random_seed=7,
        ))
    solver.add_plugin(plugin)
    return plugin
```

同一个副本的 `cases/risk_bias/bias/risk.py` 改为下面的完整空偏好工厂，避免在已经按尾部计价的原始目标上再加一次近似 RiskBias：

```python
from nsgablack.bias import BiasModule


def build_risk_bias():
    return BiasModule()
```

**如何运行：** 先运行副本的 `run_project.py --check --build-check`，确认仍是 TrustRegionDFO、场景求值插件及真实 Problem；再运行 `run_project.py`。原目录入口为 `python examples/cases/risk_bias/run_project.py`。添加插件已经登记 Provider，不再额外调用 `register_evaluation_provider`。

**怎样检查：** 按“公用观察器”接入同 Case，终端 `feedback-observation` 给出本批候选的原始/选择目标和统计。对每个目标列，将 8 个损失从小到大排序，取最大的 `ceil(.25*8)=2` 个求均值。比如样本 `[0,1,2,3,4,5,6,20]` 的均值为 `5.125`，本变体 raw 目标应为 `13`；这组数是公式示例，不是这次随机 Problem 的运行日志。实际反馈仍有 `mc_mean/mc_std/mc_min/mc_max`；现在 `raw_objectives` 应是上尾聚合，通常不等于 `mc_mean`，且因空 Bias 而与选择目标相同。每个候选仍调用 Problem 8 次，控制面的候选求值次数不能直接当成场景调用次数。

**边界：** 这是有限样本的最小化损失上尾均值，不是分布无误差的 CVaR 证明；最大化收益须先明确损失方向。`evaluate_constraints` 仍按现有协议每候选检查一次，不会自动对约束也进行 8 次场景概率估计。它与 `RiskBias` 的 `mean+sqrt(1/alpha)*std` 近似是不同评价含义；更换含义后，不要把旧均值实验的性能曲线、模型拟合分数或旧 checkpoint 当成同一任务直接续跑。

## extension.plugin.pareto_archive

### 变体一：给两个独立种群建立公共历史档案，保留各自 Unit

**目的：** 两个搜索群体可以共享结果观察，而无需把它们的工作种群拼在一起。本例使用 `catalog_recipes/cases/composite`：两个 NSGA-II 子实例都求同一个二维平方和问题，候选宽度、目标标签和反馈含义一致，档案可从已提交的两个 partition 收集候选并按 token 保留身份。

**改在哪里：** 在 `examples/cases/catalog_recipes/` 的独立副本中，新建 `cases/composite/plugins/archive.py`，内容完整如下：

```python
import json
from nsgablack.plugins import ParetoArchiveConfig, ParetoArchivePlugin
from nsgablack.plugins.base import Plugin


class SharedArchiveReport(Plugin):
    context_requires = context_provides = context_mutates = context_cache = ()

    def __init__(self):
        super().__init__(name="shared_archive_report")

    def on_solver_finalized(self, result):
        del result
        solver = self.solver
        archive = solver.get_plugin("shared_history")
        snapshot = solver.pareto_population_snapshot
        if snapshot is None:
            raise ValueError("the archive did not publish semantic candidates")
        tokens = tuple(snapshot.candidate_tokens)
        if any(token is None for token in tokens) or len(set(tokens)) != len(tokens):
            raise ValueError("archive identities are missing or repeated")
        print("shared-archive " + json.dumps({
            "partitions": len(solver.adapter.get_population_partitions()),
            "segments": archive.segment_count,
            "total_history_members": archive.total_archive_size(),
            "active_tokens": list(tokens),
            "objectives": snapshot.objectives.tolist(),
        }, sort_keys=True))


def attach_shared_archive(solver):
    solver.add_plugin(ParetoArchivePlugin(
        name="shared_history", config=ParetoArchiveConfig(
            keep_infeasible=False, max_size=8, update_every=1,
        )))
    solver.add_plugin(SharedArchiveReport())
```

在同 Case 已有 `build_solver.py` 的 `solver.set_adapter(CompositeAdapter(...))` 之后、`apply_solver_component_overrides` 之前，加入以下两行。`solver` 就是原函数已创建的实例；其余 Problem、Pipeline、两个 NSGA-II 的构造和返回保持原文：

```python
from .plugins.archive import attach_shared_archive
attach_shared_archive(solver)
```

**如何运行：** 从仓库根目录运行副本对应的 `run_project.py --check --build-check`，再运行 `run_project.py`；原目录命令为 `python examples/cases/catalog_recipes/run_project.py`，默认组只启动 composite Case。这里新增观察器在最终发布后打印信息，不增加候选求值，不写共享 context 或改变子 Adapter 的生存选择。

**怎样检查：** 终端 `shared-archive` JSON 中 `partitions` 应仍为 2、`segments` 为 1；`active_tokens` 数量与输出目标行数一致，均非空身份且无重复，当前段最多 8 行。两个子种群仍各有 4 个成员；档案不必有 8 行，因为它保留非支配历史成员，而不是所有当前成员。这个单目标例子中，不应把“档案更多”当成质量更好。若多个不同身份恰有相同数值，不能为了去重而伪造或合并其 token。

**边界：** 这条公共档案路径只适用于候选维度、目标列及标签都兼容的已提交 partitions。不能用它把 A* 路径代价与 MOEA/D 方向标量混成一个前沿；异质标签须另立明确结果含义。当前宿主无 Bias，才可把这里的目标解释为原始目标；以后加 Bias 必须重新核对 authority 的反馈视图。`max_size` 是每个目标段的历史档案上限，既不是每个种群容量，也不是解池容量；保留历史档案同样不授权直接从算法 Unit 删除候选。

## extension.feedback_observation

### 公用观察器：把最后一次真实求值的 raw、选择视图与场景统计打印出来

保存到本次所改 Case 的 `plugins/feedback_observation.py`，内容完整如下。它在 `on_solver_finish` 读取已经存在的最后求值 Event，不构造 Unit、不修改 Pool、不再调用 Problem；不会在 `on_evaluate_end` 提前假设 Event 已经发布。

```python
import json
import numpy as np
from blackbase.types import CandidateBatch
from nsgablack.core.evaluation_feedback import OptimizationFeedbackBatch
from nsgablack.plugins.base import Plugin


class FeedbackObservation(Plugin):
    context_requires = context_provides = context_mutates = context_cache = ()

    def __init__(self):
        super().__init__(name="feedback_observation")

    def on_solver_finish(self, result):
        del result
        event = self.solver.get_last_evaluation_event()
        if event is None or not event.semantic_complete:
            raise ValueError("a complete evaluation event is required")
        candidates = CandidateBatch.from_dict(event.candidate_payload)
        feedback = OptimizationFeedbackBatch.from_dict(event.feedback_payload)
        statistics = []
        for item in feedback.items:
            statistics.append({key: np.asarray(value).tolist()
                               for key, value in item.metrics.items()
                               if key in {"mc_samples", "mc_mean", "mc_std", "mc_min", "mc_max"}})
        print("feedback-observation " + json.dumps({
            "event_id": event.event_id,
            "candidates": candidates.numeric_matrix.tolist(),
            "raw_objectives": feedback.raw_objectives.tolist(),
            "objectives": feedback.objectives.tolist(),
            "raw_violations": feedback.raw_violations.tolist(),
            "violations": feedback.violations.tolist(),
            "statistics": statistics,
        }, sort_keys=True))
```

在该 Case 的 `build_solver.py` 中、构造同一 Solver 之后且 `return solver` 之前加入下列两行。名字相同的观察器只挂一次；它没有替换任何评估 Provider。

```python
from .plugins.feedback_observation import FeedbackObservation
solver.add_plugin(FeedbackObservation())
```

同时检查正式 Project 退出成功和这行数据；只有一行日志不能证明最终发布成功。这里打印的是最后一次求值批次，不是最终种群、任务最终精修结果或完整搜索历史，候选是否最终留下仍由 Adapter 决定。`raw_objectives/raw_violations` 保留本次问题求值含义，`objectives/violations` 是选择视图；MC 统计与自己的行对齐，CallableBias 不使用 MC 时相应统计字典为空是正常的。
