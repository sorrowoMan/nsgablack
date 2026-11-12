# ML与优化的接缝：工厂桥、正式子Case与旧训练代理

以下仅补中文用法并核对源码，没有执行算法、训练、子Case、数据库或网络。桥连接已有职责，不另造控制循环；Model Codec仍是模型布局权威，Unit仍归具体Adapter。

## bridge.learning

**什么时候用：** 把ML Problem/Representation接入nsgablack共享控制面，或从稳定方法ID选择优化策略。实际消费者是build_learning_solver，不需要用户手工先new两层Bridge再new一个裸ComposableSolver。

**先准备什么：** 完整复制 `mlblack/examples/cases/catalog_codec_demo/`，保留原Project/default/linear_point Case与CPU L0、pipeline/main.py的24行两特征数据工厂。依赖三仓/NumPy，不需要Torch。以下使用直接线性[b,w0,w1]布局，Gaussian搜索不消费解析梯度。

**放在哪：** 替换 Case config.py、problem/__init__.py、build_solver.py；保留数据工厂。保存《ML_CLASSICAL_ESTIMATOR_APPLICATIONS_CN.md》classical.estimator.run完整结果入口。旧adapter工厂不被调用。

**接入步骤：** 完整文件如下，工厂已创建并bind真正的MLRepresentationBridge和MLLearningProblemBridge，类型检查只读，不初始化候选或Unit。

```python
# cases/linear_point/config.py
METHOD = "search.random_gaussian"
```

```python
# cases/linear_point/problem/__init__.py
from mlblack.problems import SupervisedRegressionProblem

class PortablePointProblem(SupervisedRegressionProblem):
    def build_model_artifact(self, model, context):
        return model.as_dict()

def build_problem(data):
    return PortablePointProblem(data, l2=0., complexity_weight=0., use_valid_objective=False)
```

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_control import (
    build_learning_solver, MLRepresentationBridge, MLLearningProblemBridge)
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from .pipeline import build_pipeline
from .problem import build_problem
from .config import METHOD

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit bridge inputs")
    data = build_pipeline(seed=17, n_samples=24)
    rep = LinearPointRepresentation(LinearPointConfig(n_features=2,
        feature_names=data.effective_feature_names, random_seed=17))
    problem = build_problem(data)
    if METHOD == "search.random_gaussian":
        adapter = build_optimization_adapter(METHOD, population_size=4,
            mutation_scale=.2, random_seed=17, objective_aggregation="first")
    elif METHOD == "evaluation.fixed":
        adapter = build_optimization_adapter(METHOD)
    else:
        raise ValueError("this recipe supports Gaussian or fixed evaluation")
    solver = build_learning_solver(problem=problem, representation=rep,
        adapter=adapter, resource_context=resource_context,
        compute_backend="numpy", run_name="catalog_framework_bridge")
    if not isinstance(solver.representation_pipeline, MLRepresentationBridge):
        raise TypeError("missing ML representation boundary")
    if not isinstance(solver.problem, MLLearningProblemBridge):
        raise TypeError("missing ML evaluation boundary")
    if solver.representation_pipeline.representation is not rep:
        raise ValueError("unexpected model layout owner")
    if solver.problem.semantic_problem is not problem:
        raise ValueError("unexpected evaluation owner")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(4)
    return solver
```

MLRepresentationBridge在控制边界传递UnknownState、metadata并转发init/repair/encode/decode，不替Codec决定模型含义。MLLearningProblemBridge通过token/provenance找到对应语义状态，解码→Problem.prepare→evaluate→ML Bias→记录本候选模型handle，保留富Feedback；不能对裸Bridge.evaluate直接传一个数组就假定已经有权威候选身份和已bind控制面。init只在正式运行发生，读取dimension或Doctor检查不得抽样造一个模型。

build_optimization_adapter当前只接受gradient.sgd/adam/adamw、search.random_gaussian、evaluation.fixed与已列别名；各自参数必须匹配具体Config。evaluation.fixed不收任何参数。梯度方法需要真实梯度/Provider状态接线，应使用build_gradient_trainer的完整配方；仅把METHOD改"adam"不等于自动生成模型梯度或启用Torch。

**怎样判断接对：** classical.json三参数state、原始目标[train.mse,0]、训练loss与ModelRef。桥不把ML模型结构变成Adapter Unit，不从相等数值推断候选身份。最终引用保存同一个已评估LinearPointModel的原生JSON蓝图，不是裸模型对象；无需手动再跑一次decode/evaluate来“补结果”。

**运行入口：** 副本根 `python run_project.py --check --build-check`，再 `python run_classical_and_report.py`，正式Project只运行一次。前者验证类型/装配而不搜索；模型、性能与恢复必须以之后真实收据为准。本轮仅静态核对。

### 变体：只评估一次语义初值

**目的：** 检查Problem/Codec/Artifact链而不搜索。**改在哪里：** config.py完整替换：

```python
METHOD = "evaluation.fixed"
```

**行为变化：** FixedCandidateAdapter送评一次初值后完成，四步预算不强迫重复四次。**限制：** 只证明当前候选可送评；分数不会因为类名含learning自动变好，也不证明Gaussian/梯度方法的算法正确性。

## bridge.nested.case

**什么时候用：** 外层搜索一个超参数，每次候选都调用完整内层训练Case并取其正式结果；真正使用NsgablackLearningCaseEvaluator，而不是在Problem中直接trainer.fit。外层解与内层模型参数不是同一对象，也不自动共享SolutionPool。

**先准备什么：** 完整复制 `mlblack/examples/cases/cross_framework/`，保留两个Case cross_framework/inner_training、Project L0和默认outer_search组。内层原pipeline生成40行一特征，随机留出25%，原builder装配orthogonal_linear_point并接受learning_rate/max_steps显式覆盖；不是时序验证。需要三仓/NumPy。

**放在哪：** 替换外层Case的problem/example_problem.py、evaluation/__init__.py、build_solver.py；复用原pipeline/main.py的[-2,-.7]初始化/clip。内层全部代码保留。Project配置末尾设置 `L0["artifacts"]["allow_unsafe_serializers"] = False`，原生正交模型可安全JSON，无须沿用历史unsafe许可。结果入口见下一节。

**接入步骤：** evaluator本身的can_handle/evaluate不是nsgablack EvaluationProvider的完整四方法协议，因此用一个小的显式Provider适配它；真实调度、预算、取消、Artifact和资源子grant仍由原CaseRuntime处理。

```python
# cases/cross_framework/problem/example_problem.py
from nsgablack.core.base import BlackBoxProblem

class ChildLearningProblem(BlackBoxProblem):
    def __init__(self):
        super().__init__(name="inner_validation_mse", dimension=1,
            bounds={"log10_learning_rate": (-2., -.7)}, objectives=("validation_mse",))
        self.variables = ["log10_learning_rate"]
    def evaluate(self, candidate):
        raise RuntimeError("complete ML Case provider must handle this evaluation")
```

```python
# cases/cross_framework/evaluation/__init__.py
import numpy as np
from mlblack.integrations.nsgablack_learning_case import NsgablackLearningCaseEvaluator

def component_overrides(candidate, context):
    values = candidate.as_array()
    if values.shape != (1,) or not np.all(np.isfinite(values)):
        raise ValueError("one finite log learning rate required")
    return {"learning_rate": float(10.**values[0]), "max_steps": 2}

def result_projector(result, candidate, context):
    feedback = result.best_feedback
    if feedback is None or result.best_model_ref is None:
        raise ValueError("child omitted evaluated feedback or published model")
    value = float(feedback.metrics["valid.mse"])
    if not np.isfinite(value):
        raise ValueError("nonfinite child validation metric")
    violation = float(np.sum(np.maximum(0., np.asarray(feedback.constraints))))
    return np.array([value]), violation

class LearningCaseProvider:
    name = "case_complete_learning"
    semantic_mode = "exact"
    priority = 10
    def __init__(self):
        self.evaluator = NsgablackLearningCaseEvaluator("inner_training", max_steps=2,
            result_projector=result_projector, component_overrides=component_overrides,
            resource_request={"workers": 1, "threads": 1, "memory_mb": 512,
                              "device": "cpu", "backend": "local"})
    def can_handle_individual(self, solver, x, context):
        return self.evaluator.can_handle(solver=solver, x=x)
    def evaluate_individual(self, solver, x, context, individual_id=None):
        if individual_id is None:
            raise ValueError("missing original candidate index")
        return self.evaluator.evaluate(solver=solver, x=x,
            individual_id=int(individual_id), context=context)
    def can_handle_population(self, solver, population, context):
        return False
    def evaluate_population(self, solver, population, context):
        raise RuntimeError("this provider only accepts individual dispatch")
```

```python
# cases/cross_framework/build_solver.py
from nsgablack.core.composable_solver import ComposableSolver
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
from .problem.example_problem import ChildLearningProblem
from .pipeline.main import build_pipeline
from .evaluation import LearningCaseProvider

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this reference uses explicit Case wiring")
    problem = ChildLearningProblem()
    solver = ComposableSolver(problem,
        representation_pipeline=build_pipeline(problem, resource_context=resource_context),
        adapter=build_optimization_adapter("search.random_gaussian", population_size=2,
            mutation_scale=.35, initialization="population", random_seed=17,
            objective_aggregation="first"), resource_context=resource_context)
    solver.register_evaluation_provider(LearningCaseProvider())
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(1)
    return solver
```

Provider没有自己的run/fit/线程池，can_handle只确认已有CaseRuntime，不能自己创建grant；选中后失败直接传播，不再偷偷调次优Provider。population请求被正式拒绝为不支持，由控制面的逐行路径调用individual并保留原index；不能广播给全部子Case。

**怎样判断接对：** 外层只优化一个valid.mse，原内层目标/训练loss/模型引用保留在child TrainerResult。component_overrides确实被现有inner builder消费；请求inputs中的candidate/max_steps本身不会让任意Case自动懂超参数或重绑定初始模型。本例显式覆盖learning_rate/max_steps，不把外层一维值当内层权重。两名候选可产生两次独立内Case调用；每内Case两步仍要区分物理尝试、逻辑提交与实际fit/梯度次数。

**运行入口：** 下一节给完整一次Project读取脚本。原Project L0负责父子资源、lineage和取消；不直接调用evaluator.evaluate来跳过注入，不把仅构造成功称已验收三级嵌套或checkpoint恢复。

### 变体：冻结学习率范围，只改变内层预算

**目的/改在哪里：** evaluation/__init__.py中只将component_overrides完整函数替换如下，同时evaluator.max_steps仍为请求摘要，不替代显式覆盖：

```python
def component_overrides(candidate, context):
    values = candidate.as_array()
    if values.shape != (1,) or not np.all(np.isfinite(values)):
        raise ValueError("one finite log learning rate required")
    return {"learning_rate": float(10.**values[0]), "max_steps": 4}
```

**行为变化：** 原inner builder从覆盖参数设置四步；外层候选/目标口径不变。**限制：** 预算增加不保证更优；不同预算对应不同外层任务，不能拿旧缓存或旧checkpoint结果混称相同评估。

## bridge.nested.run

Project根完整 `run_nested_and_report.py`，不提前运行原run_project再补跑它。

```python
import json
from pathlib import Path
from blackbase.project import CaseRunResult
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    outer = next(x for x in run.case_results if x.request.case_name == "cross_framework")
    outer.raise_for_failure()
    child_rows = outer.metadata["runtime_audit"]["child_invocations"]["results"]
    children = []
    for row in child_rows:
        child = CaseRunResult.from_dict(row)
        child.raise_for_failure()
        result = TrainerResult.from_dict(child.output)
        children.append({"child_id": child.identity.case_run_id,
            "parent_id": child.identity.parent_case_run_id,
            "grant": child.request.child_grant.as_dict(),
            "objectives": result.best_objectives.tolist(),
            "model_ref": None if result.best_model_ref is None else result.best_model_ref.as_dict()})
    path = root/"results"/"nested.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run_id": run.run_id, "children": children},
        ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

在副本根 `python run_project.py --check --build-check`，再 `python run_nested_and_report.py`。核对child parent_id等于本次outer的case_run_id、子grant不越过父授权、子模型ModelRef非空和正式终态；某子失败必须让外层失败。本轮未执行任何子Case。

## bridge.training_proxy.boundary

**什么时候用：** 搜到MLBlackTrainingProxy两个Catalog别名，想用外层候选映射成TrainingTask。它仍是有效的任务/结果值代理，但当前run_task直接build_trainer→trainer.fit，不是上节完整子Case调用。

**先准备什么：** 当前三仓与已有NumericDataView；仅构造任务不需要拟合。希望多Case、父子L0 grant、Artifact收据与取消联动时，应选上节NsgablackLearningCaseEvaluator。

**放在哪：** mapper只负责数值候选→trainer_spec/max_steps；真实跨Case在正式CaseRuntime，不能在example里用此代理私搭嵌套运行器。以下只展示纯任务生成，明确不调用run_task/evaluate_individual/evaluate_population。

**接入步骤：** 将已有DataView、当前候选和有效资源描述传入下面的纯任务工厂；只读取返回值，不调用代理的直接拟合入口。随后按上节正式子Case接线替代run_task。

```python
from mlblack.problems.proxy import MLBlackTrainingProxy

def make_task_only(data, candidate, resource_context):
    proxy = MLBlackTrainingProxy(data, max_steps=2,
        base_trainer_spec={"preset": "linear_point", "params": {"learning_rate": .03}})
    return proxy.make_task(candidate, {"resource_context": resource_context}).as_dict()
```

**怎样判断接对：** 返回TrainingTask值含配置/outer_candidate/资源描述，没有模型、反馈或权威Artifact。run_task当前artifact_refs只有{"trainer":run_name}之类字符串，不是正式DataRef/ModelRef收据；它也不申请Project子grant。不能拿TrainingResultRecord类型名推断完整模型交付或恢复能力已接通。

**运行入口：** 本节是迁移参考，不提供把直接fit当正式嵌套的命令。完整可装配替代是本书上节的原双Case Project。迁移完成应包括CaseRuntime请求、真实Artifact结果/预算/取消及错误传播；不修改底层源码便宣称代理自动拥有这些能力。

### 变体：请求另一内部步数仍只是任务值

**目的/改在哪里：** make_task_only的proxy.max_steps从2改4；真实训练仍不执行。**行为变化：** TrainingTask.max_steps变化。**限制：** 不产生子Case、训练结果或授权，不能算已验证算法性能。

源码：mlblack `integrations/nsgablack_control.py`、`integrations/nsgablack_optimization.py`、`integrations/nsgablack_learning_case.py`、`problems/proxy.py`、`problems/training.py`；nsgablack `core/evaluation_runtime.py` 与正式cross_framework Project。
