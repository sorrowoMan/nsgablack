# ML Bias：软反馈与显式消费的上下文提示

这里使用当前 LearningSolver 的正式 add_bias 接缝，而非 nsgablack 的标量 BiasModule。本文只做源码、AST、示例抽取与API静态核对，没有训练、运行搜索、调用服务或下载模型。ML的模型Codec与搜索Unit仍各自负责自己的结构。

## ml_bias.host · 一个完整正式Project的装配与报告

完整复制 `mlblack/examples/cases/catalog_codec_demo` 到独立工作目录。保留原 project_config.py、run_project.py、default组、linear阶段、linear_point Case、所有包与规范入口。原Project只调度linear_point，L0仍发放1 CPU线程；不在Case重新创建授权。以下Case路径相对 `cases/linear_point/`。

原 pipeline/main.py 生成固定seed=17的24行双特征数据：y=1+2*x0-.5*x1。保留该文件。新建 `problem/bias_problem.py`：

```python
from dataclasses import replace
from mlblack.problems import SupervisedRegressionProblem


class BiasRegression(SupervisedRegressionProblem):
    def __init__(self, data):
        super().__init__(data, l2=0., complexity_weight=.1, use_valid_objective=False)

    def evaluate(self, model, state, context):
        measured = super().evaluate(model, state, context)
        return replace(measured, metrics={**dict(measured.metrics),
            "case.bias.values": state.as_array().tolist(),
            "case.bias.step": int(context["step"])})
```

Problem原始目标是 `[train.mse, .1*非零斜率数]`，约束为空，loss是未加额外正则的训练MSE。这里明确加一个非恒零第二目标，便于看到重权重真的作用于二维向量。LinearPointRepresentation的候选布局恰为 `[截距, w0, w1]`；这也是本例 `exclude_bias=True` 能成立的原因，不能外推到任意Codec。

新建 `adapter/bias_search.py`：

```python
from nsgablack.adapters import GaussianSearchAdapter, GaussianSearchConfig


def build_adapter():
    return GaussianSearchAdapter(config=GaussianSearchConfig(population_size=4,
        mutation_scale=.15, initialization="center", include_center_candidate=True,
        objective_aggregation="sum", random_seed=17))
```

这是真正无导数的Adapter；ML表示仍负责init/decode，算法Unit保留轨迹与随机数。Bias不修改原始梯度和loss，所以不能把此例直接换成梯度Adapter再声称“按加偏好后的梯度训练”。

新建 `plugins/bias_report.py`，只观察最后正式评估批，不再次求值：

```python
import numpy as np
from nsgablack.plugins.base import Plugin
from nsgablack.utils.engineering.file_io import atomic_write_json
from ..bias.preference import MODE, expected_objectives


class BiasReport(Plugin):
    def __init__(self, output):
        super().__init__(name="ml_bias_report")
        self.output = output

    def on_solver_finish(self, result):
        control = self.solver
        batch = control.get_last_feedback_batch()
        rows = []
        if batch is not None:
            for index, item in enumerate(batch.items):
                expected = expected_objectives(batch.raw_objectives[index], item.metrics)
                rows.append({"values": item.metrics["case.bias.values"],
                    "step": item.metrics["case.bias.step"],
                    "raw": batch.raw_objectives[index].tolist(),
                    "selection": batch.objectives[index].tolist(),
                    "expected": expected.tolist(),
                    "matches": bool(np.allclose(batch.objectives[index], expected)),
                    "hints": item.metrics.get("case.bias.hints")})
        self.payload = {"run_id": control.run_session.run_id, "mode": MODE,
            "generation": int(control.generation), "last_evaluated_rows": rows}

    def on_solver_finalized(self, result):
        atomic_write_json(self.output, self.payload)
```

新建下节完整 `bias/preference.py`，然后完整替换 `build_solver.py`：

```python
from pathlib import Path
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from nsgablack.core import FeasibleEvaluationAcceptance
from nsgablack.project import apply_solver_component_overrides
from .adapter.bias_search import build_adapter
from .bias.preference import build_biases
from .pipeline.main import build_pipeline
from .plugins.bias_report import BiasReport
from .problem.bias_problem import BiasRegression


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config:
        raise ValueError("edit this recipe's explicit factories")
    data = build_pipeline(seed=17, n_samples=24)
    representation = LinearPointRepresentation(LinearPointConfig(n_features=2,
        feature_names=data.effective_feature_names, random_seed=17))
    solver = build_learning_solver(problem=BiasRegression(data), representation=representation,
        adapter=build_adapter(), resource_context=resource_context, run_name="bias_linear")
    solver.set_bias_module(None, enable=False)
    for bias in build_biases():
        solver.add_bias(bias)
    solver.set_evaluation_acceptance_policy(FeasibleEvaluationAcceptance())
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    solver.add_plugin(BiasReport(Path(__file__).resolve().parents[2] / "results" / "ml_bias.json"))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

Case新建或合并context_keys.json，保留已有其它声明：

```json
["metrics.case.bias.values", "metrics.case.bias.step", "metrics.case.bias.hints", "signal.pool"]
```

这几个Case指标有实际产出方；project_context返回的字典只属于本次ML调用，不把model、数据或大数组塞入共享ContextStore。系统已有bias.*通用键声明不等于它们都在本次上下文中实际出现。

Project根新增 `run_bias_and_report.py`：

```python
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project


def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    case = next(c for c in run.case_results if c.request.case_name == "linear_point")
    case.raise_for_failure()
    result = TrainerResult.from_dict(case.output)
    if result.best_feedback is None or result.best_model_ref is None:
        raise ValueError("evaluated feedback and published model reference required")
    print(json.dumps({"run_id": run.run_id,
        "best_objectives": result.best_objectives.tolist(),
        "model_ref": result.best_model_ref.as_dict()}, ensure_ascii=False, indent=2))
    return run.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
```

best_model_ref由正式CaseRuntimeArtifactProvider发布，Report JSON只是观察副本。报告读最后一批的raw/selection，而不是把它误认成Gaussian历史最佳或最终模型。失败时旧JSON可能仍在，必须核对run_id与本次成功Case状态。

## ml_bias.feedback · 权重、状态L2和条件权重按顺序投影

**什么时候用：** 不改变Problem的评估含义，希望无导数搜索用可追溯的软反馈比较；需要能看到多个Bias的确切顺序与二维反馈。

**先准备什么：** 完成本书host全套文件，NumPy与当前三仓可导入；不需要Torch、sklearn或网络。无新Provider、无直接模型fit。初始化、repair、送评、接纳仍由同一个控制面执行。

**放在哪：** 新建 `cases/linear_point/bias/preference.py`。下面是整个文件，非省略的factory片段。

**接入步骤：**

```python
import numpy as np
from mlblack.bias import NoopBias, ObjectiveWeightBias, ObjectivePolicyBias, StateL2Bias

MODE = "chain"


def build_biases():
    if MODE == "noop":
        return [NoopBias()]
    if MODE == "l2":
        return [StateL2Bias(weight=.2, exclude_bias=True)]
    if MODE == "weights":
        return [ObjectiveWeightBias(weights=(.5, 2.))]
    if MODE == "policy":
        return [ObjectivePolicyBias(weights=(.5, 2.),
            metric_thresholds={"train.mse": .5}, threshold_multiplier=2.)]
    if MODE == "chain":
        return [NoopBias(), StateL2Bias(weight=.2, exclude_bias=True),
            ObjectiveWeightBias(weights=(.5, 2.)),
            ObjectivePolicyBias(weights=(1., 1.),
                metric_thresholds={"train.mse": .5}, threshold_multiplier=2.)]
    raise ValueError("unknown bias mode")


def expected_objectives(raw, metrics):
    out = np.asarray(raw, dtype=float).copy()
    if MODE in {"l2", "chain"}:
        values = np.asarray(metrics["case.bias.values"], dtype=float)
        out[0] += .2 * float(values[1:] @ values[1:])
    if MODE in {"weights", "policy", "chain"}:
        out *= np.asarray([.5, 2.])
    if MODE in {"policy", "chain"} and float(metrics["train.mse"]) >= .5:
        out *= 2.
    return out
```

调用路径是ML Problem.evaluate→按add_bias顺序adjust_feedback→原始证据保留→正式OptimizationFeedbackBatch→准入与Adapter.update。StateL2只给objective[0]加 `.2*(w0²+w1²)`；不是改loss、不是修复模型、不是重算梯度。ObjectiveWeight逐维乘且长度必须精确相等，本例两维；不做求和或scalarize。ObjectivePolicy在本例阈值触发后对两个目标都再乘2，读取的train.mse来自Problem原始指标，不是前一Bias修改后的objective。

Noop的实际行为是传递上下文与反馈；虽声明bias.noop，不实际插入这个键。它适合基线切换，不应把“有声明”当作“发生了某种事件”。ObjectivePolicy的长度行为和ObjectiveWeight不同：单权重广播、短向量尾部补1、长向量截断；每一个满足 `>=` 的指标阈值都再乘一次multiplier，多个阈值可能叠乘。当前缺失指标直接不触发；若业务要求必有某指标，应在自己的Problem/消费者中显式验证，不把缺失当零。

**怎样判断接对：** ml_bias.json每行matches应为True；raw第二维是0/.1/.2的复杂度成本，selection第二维按有效权重变化。chain模式的第一维是 `(raw_mse+.2*斜率平方和)*.5*factor`，不是把所有权重相加，也没有nsgablack旧DomainBias的双重weight。硬准入仍读raw约束；本问题没有约束，不能据此推断所有Bias都是硬可行性过滤器。所有正权重仅表达同一最小化方向，不要用负权重暗中翻转Problem含义。

**运行入口：** 副本根 `python run_project.py --check --build-check` 后运行 `python run_bias_and_report.py`；查看results/ml_bias.json和命令输出的正式模型引用。本轮没有执行上述命令，不承诺6步收敛。

### 变体一：隔离L2的效果，保留二维原始问题

**目的：** 区分正则软成本与重权重，而非同时改多个部件。

**改在哪里：** 保留整个preference.py，只将MODE的赋值替换为：

```python
MODE = "l2"
```

**行为变化：** 第二目标不变，第一目标只增加斜率L2；报告同一expected函数按模式验证。**限制：** `exclude_bias=True`是跳过第一个数值坐标的规则，只对本LinearPoint布局解释为不惩罚截距；任意新Codec须重新确认。

### 变体二：完全无偏好基线

**目的：** 确认原始Problem与反馈管线自身可用。

**改在哪里：** 同文件只换MODE。

```python
MODE = "noop"
```

**行为变化：** raw与selection逐维一致。**限制：** Noop不是关闭模型求值或暂停Adapter，预算仍照常消耗，不能把基线结果当性能对照证据。

源码：mlblack/bias/policies.py、bias/base.py、integrations/nsgablack_control.py、problems/supervised.py；base.py模块头仍有“adjust_feedback已移除”旧文字，但类方法和当前调用链均保留正式投影，应以实际源码接口为准并记录该文档漂移。

## ml_bias.context · 提示由谁读，必须在Case里写清楚

**什么时候用：** 需要随逻辑步变化的软正则系数，或给自己的显式消费者提供分支/候选模型集合提示。这里演示真实project_context与消费，不声称DynamicPool操作SolutionPool或BranchPolicy自动选模型。

**先准备什么：** 同一host的完整正式Project。这个变体仍用LinearPoint、无导数Gaussian和二维Problem；没有条件网络、动态模型拼装或字符串到SolutionRef的隐式转换。

**放在哪：** 完整替换同一个 `bias/preference.py`。其它host文件保持原装配。下面的OptimizationBias实际由Case子类覆盖，不实例化一个空壳后冒称有新行为。

**接入步骤：**

```python
from dataclasses import replace
import numpy as np
from mlblack.bias import (OptimizationBias, L2ScaleBias,
    BranchPolicyBias, DynamicPoolBias, StateL2Bias)

MODE = "context"
SWITCH_AT = 3


class PoolHintSignal(OptimizationBias):
    name = "case_pool_hint_signal"
    context_provides = ("signal.pool",)

    def project_context(self, control, context):
        return {**dict(context), "signal.pool":
            "fallback" if control.step_index >= SWITCH_AT else "normal"}


class ConsumeAndAuditHints(OptimizationBias):
    name = "case_consume_and_audit_hints"
    context_requires = ("bias.l2_scale",)

    def adjust_feedback(self, control, states, feedback, context):
        strength = float(context["bias.l2_scale"])
        if not np.isfinite(strength) or strength < 0:
            raise ValueError("this Case requires nonnegative finite L2 scale")
        projected = StateL2Bias(weight=strength, exclude_bias=True).adjust_feedback(
            control, states, feedback, context)
        hints = {"l2_scale": strength,
            "preferred": context.get("bias.branch.preferred"),
            "weights": list(context.get("bias.branch.weights", ())),
            "pool_name": context["bias.dynamic_pool.name"],
            "members": list(context["bias.dynamic_pool.members"]),
            "signal": context["signal.pool"]}
        return tuple(replace(item, metrics={**dict(item.metrics),
            "case.bias.hints": hints}) for item in projected)


def build_biases():
    return [PoolHintSignal(), L2ScaleBias(base=.01, step_scale=.02, max_value=.1),
        BranchPolicyBias(preferred_branch=1, branch_weights=(.3, .7)),
        DynamicPoolBias(pool_name="candidate_model_hints", members=("linear", "quadratic"),
            fallback_members=("linear",)), ConsumeAndAuditHints()]


def expected_objectives(raw, metrics):
    out = np.asarray(raw, dtype=float).copy()
    strength = min(.01 + .02 * int(metrics["case.bias.step"]), .1)
    values = np.asarray(metrics["case.bias.values"], dtype=float)
    out[0] += strength * float(values[1:] @ values[1:])
    return out
```

L2Scale本身只写bias.l2_scale；原SupervisedRegressionProblem不读这个键，所以直接add L2Scale并不会自动改变正则。上面的**Case消费器**明确把它作为StateL2反馈投影的weight，仍不改Problem的训练loss/梯度。这是新实现的Case行为，不是给内核补一个隐藏默认。步数来自control.step_index，即已提交逻辑generation，不是物理尝试计数。

BranchPolicy只写 `.preferred/.weights`，这里Audit实际读取并记录，**没有据此切换LinearPoint模型分支**。若要选条件模型，须在自己的Representation/Problem中消费并验证分支编号与权重，不从字符串自动推断布局。DynamicPool只写名称和字符串members，这里Audit实际读取；signal恰为字面量fallback才切换。它没有创建子池、移动候选、更新Unit、选择Adapter或执行FunctionPool搜索。真正解池操作须用nsgablack的SolutionPool/PoolTask正式契约，不应把这两个pool概念混同。

**怎样判断接对：** 最后批matches按候选记录的当时step验证；hints.l2_scale应随step增加且最高.1。normal时members是linear/quadratic，step>=3时为linear；preferred=1、weights=[.3,.7]仅为声明的观察字段。输出显示这些提示被消费，不代表框架完成了模型切换。raw保持原二维目标，不产生新求值或新SolutionRef；只有正式候选提交才入运行池。当前projector是纯函数，无须额外checkpoint可变状态；以后加入历史或随机选择不能照抄这个无状态假设。

**运行入口：** 同一副本根 `python run_project.py --check --build-check` 后 `python run_bias_and_report.py`，读取results/ml_bias.json；只用这一个正式Case流程。

### 变体一：从第一步就给出fallback提示

**目的：** 核对DynamicPool使用哪个信号值、由谁负责决定切换时刻。

**改在哪里：** 同一preference.py只换常量，保留完整消费者。

```python
SWITCH_AT = 0
```

**行为变化：** 每次ML上下文中的字符串members都为linear，报告直接显示；L2和模型布局不变。**限制：** 这是Case固定逻辑条件，不是运行时模型集合自动退化，也没有暂停、删除或构建任何Adapter。

源码：mlblack/bias/base.py与policies.py；integrations/nsgablack_control.py的enrich_ml_context/adjust_feedback_with_biases。缺失或自定义context_key时须同步消费端，不能只改声明。本文没有把本地context投影当共享ContextStore写入。
