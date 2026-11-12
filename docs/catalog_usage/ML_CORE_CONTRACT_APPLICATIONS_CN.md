# ML 核心契约：用一个真实模型贯通参数、Head、Problem和交付

以下仅做源码与静态片段核对，没有运行模型、训练、Project、数据库或网络请求。抽象基类不是需要同时购买/装配的六个组件；本书把扩展点放进完整正式Case，说明实际由谁调用。

## core.contract.model · 自定义参数布局和输出Head，不改变算法Unit

**什么时候用：** 现有Codec的参数顺序不合适，希望明确使用 `[w0,w1,b]`，并让Head把权重块与截距块组合为可预测模型。这里实际实现ModelRepresentation/OutputHead/LearningProblem，HeadBlock真正参与解码；`RepresentationPipeline`是ModelRepresentation的同一类别名，不再包一层同名容器。

**先准备什么：** 复制整个 `mlblack/examples/cases/catalog_codec_demo/` 到独立工作目录，保留正式Project/default组、CPU L0与 `cases/linear_point` 的标准目录和入口。依赖三仓与NumPy。24条训练、8条独立验证，两列输入；train MSE是唯一目标，valid只观察。以下路径相对此副本，不直接改仓库示例。

**放在哪：** 完整替换Case的config.py、pipeline/main.py、problem/__init__.py；新建pipeline/affine.py。再保存下一节的完整builder、观察器和Project报告入口。旧adapter工厂不再被调用。

**接入步骤：** 先声明完整布局，再在decode时调用Head；不在init里拟合模型，不创建Adapter的Unit。

```python
# cases/linear_point/config.py
TYPED_ARTIFACT = True
OBSERVE_STATE = True
```

```python
# cases/linear_point/pipeline/affine.py
import numpy as np
from mlblack.core.head import HeadBlock, OutputHead
from mlblack.core.representation import ModelRepresentation, RepresentationPipeline
from mlblack.core.types import UnknownState
from mlblack.models import LinearPointModel

class AffineHead(OutputHead):
    name = "case_affine_head"
    output_kind = "point"
    def parameter_size(self, base_dimension):
        return int(base_dimension)+1
    def blocks(self, base_dimension):
        n = int(base_dimension)
        return (HeadBlock("weights", 0, n), HeadBlock("intercept", n, n+1))
    def decode(self, values, *, base_dimension, base_decode, context=None):
        values = np.asarray(values, dtype=float).reshape(-1)
        if values.size != self.parameter_size(base_dimension):
            raise ValueError("affine head layout mismatch")
        weights, intercept = self.blocks(base_dimension)
        return LinearPointModel(intercept=float(intercept.values(values)[0]),
            weights=base_decode(weights.values(values), dict(context or {})),
            feature_names=("a", "b"))

class AffineRepresentation(ModelRepresentation):
    dimension = 3
    name = "case_affine_w_w_b"
    layout = "weights_then_intercept/v1"
    def __init__(self):
        self.head = AffineHead()
    def init(self, context):
        return UnknownState(values=np.zeros(3), metadata={"layout": self.layout})
    def _values(self, state):
        values = state.as_array().reshape(-1)
        if values.size != 3 or state.metadata.get("layout") != self.layout:
            raise ValueError("candidate layout or semantic metadata differs")
        return values
    def repair(self, state, context=None):
        values = self._values(state)
        if not np.all(np.isfinite(values)):
            raise ValueError("nonfinite affine candidate")
        return state.with_values(np.clip(values, -5., 5.))
    def decode(self, state, context=None):
        values = self._values(state)
        if not np.all(np.isfinite(values)) or np.any(np.abs(values) > 5.):
            raise ValueError("decode requires a repaired candidate")
        return self.head.decode(values, base_dimension=2,
            base_decode=lambda block, ctx: np.array(block, copy=True), context=context)
    def encode(self, model, context=None):
        if not isinstance(model, LinearPointModel) or len(model.weights) != 2:
            raise TypeError("expected the two-feature affine model")
        return UnknownState(values=np.r_[model.weights, model.intercept],
            metadata={"layout": self.layout})

def build_representation():
    representation = AffineRepresentation()
    if not isinstance(representation, RepresentationPipeline):
        raise TypeError("public representation alias must describe this same object")
    return representation
```

HeadBlock只是半开区间切片，不自动检查参数长度、互斥或完整覆盖，因此本Head明确校验总长。布局与内置LinearPointRepresentation的 `[b,w0,w1]` 不同，不能混用旧候选或梯度顺序。本例使用Gaussian搜索，不调用LinearPointModel的内置参数梯度来更新这套不同顺序的向量。

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline import NumericDataView
from .affine import build_representation

def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.normal(size=(24, 2)), rng.normal(size=(8, 2))
    def target(a):
        return 1.+2.*a[:, 0]-.5*a[:, 1]
    return NumericDataView(X_train=X, y_train=target(X),
        X_valid=V, y_valid=target(V), feature_names=("a", "b"))

def build_components():
    return build_pipeline(), build_representation()
```

```python
# cases/linear_point/problem/__init__.py
import numpy as np
from mlblack.core.problem import LearningProblem
from mlblack.core.types import Feedback
from mlblack.core.artifacts import ModelArtifact, TypedModelArtifact
from ..config import TYPED_ARTIFACT

class AffineProblem(LearningProblem):
    name = "case_affine_problem"
    objective_count = 1
    def __init__(self, data):
        self.data = data
    def evaluate(self, model, state, context):
        metrics = {}
        for prefix, X, y in (("train", self.data.X_train, self.data.y_train),
                            ("valid", self.data.X_valid, self.data.y_valid)):
            prediction = np.asarray(model.predict(X), dtype=float)
            if prediction.shape != y.shape or not np.all(np.isfinite(prediction)):
                raise ValueError("prediction/label alignment differs")
            metrics[prefix+".mse"] = float(np.mean((prediction-y)**2))
        loss = metrics["train.mse"]
        return Feedback(objectives=np.array([loss]), loss=loss, metrics=metrics,
            signals={"has_gradient": False, "parameter_layout": "weights_then_intercept/v1"})
    def build_model_artifact(self, model, context):
        common = dict(name=self.name, model=model.as_dict(), family="case_affine",
            head="point", representation={"dimension": 3, "layout": "weights_then_intercept/v1"},
            metadata={"payload_schema": "mlblack.linear_point_model.v1"})
        if TYPED_ARTIFACT:
            return TypedModelArtifact(**common, artifact_type="case_affine")
        return ModelArtifact(**common)

def build_problem(data):
    return AffineProblem(data)
```

Problem不需要拟合型prepare：decode已经得到可执行模型，因此默认只读restore不重新训练。两个Artifact类均有真实消费者CaseRuntimeArtifactProvider：剥离model中的JSON蓝图，语义describe进入元数据；只有正式finalization成功才交付best_model_ref。frozen dataclass只冻结字段绑定，不深度冻结任意model对象；这里交付的是新建原生字典。

**怎样判断接对：** 本次core.json的best_state_values应是三坐标，signals声明正确布局；objectives只有train.mse，valid.mse不参与搜索。best_model_ref指向线性模型JSON载荷，typed模式另有artifact_type=case_affine语义元数据；类型标签不会自动生成加载器、训练结果或权限收据。head.describe(base_dimension=2)的blocks应为weights[0:2]、intercept[2:3]，不把HeadBlock当算法Unit成员。

**运行入口：** 使用下一节保存的正式Project入口。原Case run_trainer/build_trainer仍是规范别名；不从抽象类另起训练循环。

### 变体一：发布基础Artifact，保留完全相同的模型

**目的：** 区分基础模型边界与额外类型标签。**改在哪里：** config.py完整替换为：

```python
TYPED_ARTIFACT = False
OBSERVE_STATE = True
```

**行为变化：** 实际调用ModelArtifact构造，模型参数/目标/JSON载荷完全保留，仅没有typed的artifact_type。**限制：** 这不是更换模型族，不会把现有Artifact自动转换成别的框架格式。

## core.contract.host · 完整builder、结果及可读的运行状态摘要

这一节与上一节合起来是同一个完整Case。观察器不写共享context，不调用evaluate或decode；在成功finalized后只读正式结果。RunReport与TrainerStateArtifact是不同边界：前者记录指标/组件，后者装已有get_state捕获值及其signature；都不是全局运行权威。

```python
# cases/linear_point/plugins/core_report.py
import json
from pathlib import Path
from mlblack.core.artifacts import RunReport, TrainerStateArtifact
from mlblack.core.state import build_trainer_state
from nsgablack.plugins.base import Plugin

class CoreReportObserver(Plugin):
    def __init__(self, output, *, observe_state):
        super().__init__(name="core_contract_report")
        self.output, self.observe_state = Path(output), bool(observe_state)
    def on_solver_finalized(self, raw_result):
        result = self.solver.export_case_result(raw_result)
        feedback = result.best_feedback
        report = RunReport(run_name=self.solver.run_name,
            status=str(result.report.get("status", "unknown")),
            metrics={} if feedback is None else dict(feedback.metrics),
            components={"representation": "AffineRepresentation", "head": "AffineHead"},
            metadata={"run_id": self.solver.run_session.run_id,
                      "artifact_names": sorted(result.artifact_refs)})
        state_summary = None
        if self.observe_state:
            captured = build_trainer_state(self.solver, metadata={"capture": "after_finalized"})
            state_artifact = TrainerStateArtifact(payload=captured.payload,
                signature=captured.signature, version=captured.version, metadata=captured.metadata)
            state_summary = state_artifact.describe()
        payload = {"report": report.describe(), "state_summary": state_summary}
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2),
                               encoding="utf-8")
```

TrainerStateArtifact自身不会计算/验证signature；这里用build_trainer_state捕获Mapping并生成签名。describe只导出version/signature/keys/metadata，不导出完整payload。本地摘要不能恢复模型或完整优化器；想恢复须使用匹配的正式checkpoint及恢复门闸。也不把这次结束观察产生的文件追认成已提交结果的一部分。

```python
# cases/linear_point/build_solver.py
from pathlib import Path
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
from .config import OBSERVE_STATE
from .pipeline.main import build_components
from .problem import build_problem
from .plugins.core_report import CoreReportObserver

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses its explicit component layout")
    data, representation = build_components()
    solver = build_learning_solver(problem=build_problem(data), representation=representation,
        adapter=build_optimization_adapter("search.random_gaussian", population_size=6,
            mutation_scale=.3, objective_aggregation="first"),
        compute_backend="numpy", resource_context=resource_context, run_name="core_affine")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(5)
    solver.add_plugin(CoreReportObserver(Path(__file__).resolve().parent/"results"/"core_observation.json",
                                        observe_state=OBSERVE_STATE))
    return solver
```

### 变体二：关闭额外状态捕获，只保留运行报告

**目的：** 查看指标时不复制训练状态。**改在哪里：** config.py完整替换为：

```python
TYPED_ARTIFACT = True
OBSERVE_STATE = False
```

**行为变化：** 观察器不调用build_trainer_state，state_summary为None，RunReport仍来自同一次正式结果。**限制：** 正式Solver checkpoint策略不会因这个观察开关改变；RunReport不包含恢复权威。

## core.contract.run · 从正式Project读取已评估模型

下面入口供本书两个独立Project配方复用。保存到各副本根；不覆盖任何Case builder。

```python
# run_core_and_report.py (Project根)
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    case = next(c for c in run.case_results if c.request.case_name == "linear_point")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None or value.best_state is None or value.best_model_ref is None:
        raise ValueError("expected evaluated affine model and formal Artifact reference")
    payload = {"run_id": run.run_id, "best_state_values": value.best_state.as_array().tolist(),
        "objectives": value.best_objectives.tolist(), "metrics": dict(value.best_feedback.metrics),
        "signals": dict(value.best_feedback.signals), "model_ref": value.best_model_ref.as_dict()}
    path = root/"results"/"core.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

在副本根 `python run_project.py --check --build-check` 后，执行一次 `python run_core_and_report.py`。本次results/core.json是正式Case输出的观察副本；Case内results/core_observation.json只描述RunReport和可选状态摘要。核对同轮run_id，旧文件不是新运行证据。5逻辑步不保证收敛。

## core.functional.gradient · 用JAX函数梯度包装相同回归语义

**什么时候用：** 模型有纯函数参数预测，需要JAX对候选向量求梯度，而不是Torch mutable backward。FunctionalGradientLearningProblem是真实Problem包装器，保留语义反馈后补齐梯度，不是新的优化Adapter。

**先准备什么：** 另一份完整catalog_codec_demo副本，当前三仓/NumPy，以及已经可用的JAX可选依赖；不要求下载模型。保留原24行两特征数据工厂与原默认Project L0。这里明确采用 `[b,w0,w1]`，不要复用上一例的自定义顺序。

**放在哪：** 新建pipeline/functional.py，完整替换config.py、problem/__init__.py和build_solver.py。保留原pipeline/main.py::build_pipeline(seed,n_samples)及包导出。复用core.contract.run节的Project报告入口run_core_and_report.py；本例不安装状态观察器，也不使用core.contract.host的builder。

**接入步骤：** 模型的NumPy predict用于真实指标，predict_from_values用于JAX微分，两条公式相同；参数冻结副本不拥有优化器。

```python
# cases/linear_point/config.py
METHOD = "gradient.sgd"
```

```python
# cases/linear_point/pipeline/functional.py
import numpy as np
from mlblack.core.representation import ModelRepresentation
from mlblack.core.types import UnknownState

class FunctionalLinearModel:
    def __init__(self, values):
        self.values = np.array(values, dtype=float, copy=True).reshape(-1)
        if self.values.shape != (3,) or not np.all(np.isfinite(self.values)):
            raise ValueError("expected b,w0,w1")
        self.values.setflags(write=False)
    def predict(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != 2:
            raise ValueError("functional input layout differs")
        return self.values[0]+X@self.values[1:]
    def predict_from_values(self, values, X):
        import jax.numpy as jnp
        return values[0]+jnp.asarray(X)@values[1:]

class FunctionalLinearRepresentation(ModelRepresentation):
    dimension = 3
    def init(self, context):
        return UnknownState(values=np.zeros(3), metadata={"layout": "functional_bww/v1"})
    def decode(self, state, context=None):
        if state.metadata.get("layout") != "functional_bww/v1":
            raise ValueError("functional parameter meaning differs")
        return FunctionalLinearModel(state.as_array())
```

```python
# cases/linear_point/problem/__init__.py
from mlblack.problems import SupervisedRegressionProblem
from mlblack.core.artifacts import TypedModelArtifact

class FunctionalProblem(SupervisedRegressionProblem):
    def build_model_artifact(self, model, context):
        return TypedModelArtifact(name="functional_linear", artifact_type="case_functional_linear",
            model={"schema": "case.functional_linear/v1", "values": model.values.tolist(),
                   "layout": "b,w0,w1", "features": ["a", "b"]}, family="linear", head="point")

def build_problem(data):
    return FunctionalProblem(data, use_valid_objective=False, complexity_weight=0., l2=0.)
```

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_gradient import build_gradient_trainer
from .pipeline import build_pipeline
from .pipeline.functional import FunctionalLinearRepresentation
from .problem import build_problem
from .config import METHOD

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses an explicit functional model")
    solver = build_gradient_trainer(problem=build_problem(build_pipeline(seed=17, n_samples=24)),
        representation=FunctionalLinearRepresentation(), compute_backend="jax",
        method=METHOD, learning_rate=.03, resource_context=resource_context,
        run_name="functional_linear")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(3)
    return solver
```

build_gradient_trainer的jax分支确实创建FunctionalGradientLearningProblem，并让BackendSession注入autograd.functional.grad/flat_export；不要再套第二次包装。SupervisedRegressionProblem.compute_functional_gradient只读训练X/y，JaxAutogradCapability调用predict_from_values；原目标 `[train.mse,0]` 与train指标保留。这里l2=0，避免把不同模型正则化坐标约定当相同公式。

**怎样判断接对：** 本次core.json的signals有has_gradient=True、gradient_owner=mlblack.problem_provider、gradient_backend=jax；best_state为3参数，正式模型引用指向蓝图，非JAX活数组。梯度必须与state.as_array形状一致；有梯度标签不等于已完成数值梯度测试。本轮未安装/执行JAX，也未证明恢复/收敛。

**运行入口：** 副本根 `python run_project.py --check --build-check`，再一次 `python run_core_and_report.py`，原Project负责L0。缺JAX时明确依赖错误，不能悄悄改为随机搜索。

### 变体一：同一个函数梯度，切换SGD为Adam

**目的：** 保留模型和训练MSE，只改变消费梯度的更新策略。**改在哪里：** config.py完整替换为：

```python
METHOD = "gradient.adam"
```

**行为变化：** 正式nsgablack GradientOptimizerAdapter维护Adam状态，Problem包装器仍产出同一坐标梯度。**限制：** 旧SGD状态不能假装已拥有Adam动量；本例未验收跨方法恢复，不支持把Torch专用data_schedule/provider_config传入jax分支。

## core.provider.problem · 通过正式工厂启用Provider，不手拼网关

**什么时候用：** ML损失、训练批次与Autograd由Torch Evaluation Provider执行，希望保留原Problem语义和正式L0授权。ProviderBackedLearningProblem是网关门面，不拥有全局资源，也不是额外fit循环。

**先准备什么：** 使用《ML_DATA_PIPELINE_APPLICATIONS_CN.md》的 `mlblack.pipeline.numeric_batch_schedule` 完整例子：独立catalog_codec_demo副本、8训练/4验证、CPU Torch、batch_size=3。该节提供全部配置、管线、Problem、builder、正式Project读取，不只一行未定义solver的片段。

**放在哪：** 沿用该例全部文件。关键实际接点在规范builder的build_gradient_trainer(compute_backend="torch",data_schedule=schedule,resource_context=...)，无需手造EvaluationGateway。

**接入步骤：** 工厂创建TorchEvaluationProvider，再调用ProviderBackedLearningProblem.from_provider；注册provider.problem_id/request_capabilities，获得实际gateway。evaluate把state、模式、逻辑步与已有ResourceContext交给网关，严格要求单状态返回一份反馈。semantic Problem负责目标/验证；Provider负责训练小批计算，StateRef由Provider管理，不能当UnknownState数组自行复制。

**怎样判断接对：** 本次batch.json的provider.batch_size/indices来自实际送评批次；完整valid.mse仍是固定比较口径，不能拿不同小批train MSE直接比较最终模型。正式TrainerResult引用、StateRef恢复和共享事务由原路径处理；此书没有新增运行收据或独立fallback。can_handle匹配后是交付承诺，失败不自动试下一个Provider。

**运行入口：** 在该独立副本执行其完整run_batch_and_report.py；只运行一次正式Project，不在外层先evaluate一次来“检查Provider”。

### 变体一：整批训练而保留同一Provider

**目的：** 对比固定完整训练集与小批训练。**改在哪里：** 按原例完整替换config.py：

```python
BATCH_SIZE = 8
```

**行为变化：** Schedule下一批包含全部8训练行，ProviderBackedLearningProblem、Problem、模型发布契约不变。**限制：** 关闭Schedule与切换compute_backend="problem"是另一条路径，后者不消费Torch Provider配置，不能只换字符串却保留专用参数。

源码依据：mlblack/core/head.py、representation.py、problem.py、provider_problem.py、state.py、artifacts.py、artifact_provider.py、integrations/nsgablack_gradient.py、backends/jax_neural/capabilities/autograd.py与当前正式catalog_codec_demo。
