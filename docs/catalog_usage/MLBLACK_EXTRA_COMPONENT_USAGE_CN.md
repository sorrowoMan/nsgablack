# MLBlack 问题、运行边界、工具与后端逐组件用法

本页按组件逐项给出调用片段，供既有标准Case的对应位置使用；函数参数明确代表由Case提供的实际输入。它不是另一个训练runner，也不把调用片段称为已完成训练。
语法与接口核对和实际运行是两种状态：以下均为源码核对示例。完整运行应通过Project → Case → build_solver/run_solver与L0授权。

## `assembly.build_trainer` · build_trainer

用途：Builds one ML trainer Case surface; orchestration belongs to the shared Project substrate.

输入：NumericDataView及Project注入的resource_context。

```python
from mlblack.assembly import build_trainer
def assemble_case(data, resource_context):
    spec = {"preset": "linear_point", "params": {"max_steps": 3},
            "resource_context": resource_context}
    return build_trainer(spec, data)
```

输出与消费：装配好的LearningSolver；由Case/Project负责运行与Artifact发布。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `bias.branch_policy` · BranchPolicyBias

用途：Exposes branch preferences for conditional/piecewise representations.

输入：Case已约定分支编号/FunctionPool成员名，策略上下文键需按本地契约注册。

```python
from mlblack.bias.policies import BranchPolicyBias
policy = BranchPolicyBias(preferred_branch=1)
context = policy.project_context(None, {"step": 3})
description = policy.describe()
```

输出与消费：新策略上下文与可审计的策略描述；消费者仍明确选择这些信号。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `bias.dynamic_pool` · DynamicPoolBias

用途：Projects a context-dependent candidate/model pool hint.

输入：Case已约定分支编号/FunctionPool成员名，策略上下文键需按本地契约注册。

```python
from mlblack.bias.policies import DynamicPoolBias
policy = DynamicPoolBias(pool_name="candidate_terms", members=("x0", "sin_x0"))
context = policy.project_context(None, {"step": 3})
description = policy.describe()
```

输出与消费：新策略上下文与可审计的策略描述；消费者仍明确选择这些信号。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `bias.l2_scale` · L2ScaleBias

用途：Expose a dynamic L2 scale to problems/adapters through context.

输入：逻辑step=5的轻量上下文；实际Problem须显式消费bias.l2_scale。

```python
from mlblack.bias.policies import L2ScaleBias
policy = L2ScaleBias(base=0.001, step_scale=0.0001, max_value=0.01)
context = policy.project_context(None, {"step": 5})
assert context["bias.l2_scale"] == 0.0015
```

输出与消费：新的上下文值；不修改原Problem的求值结果。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `bias.noop` · NoopBias

用途：Soft preference component for optimization feedback/context.

输入：同一候选的UnknownState及原始Feedback；权重个数与目标数一致。

```python
from mlblack.bias.policies import NoopBias
from mlblack.core.types import Feedback, UnknownState
import numpy as np
state = UnknownState(values=np.array([1.0, 2.0, 3.0]))
raw = Feedback(objectives=np.array([2.0]), constraints=np.zeros(0))
policy = NoopBias()
selected, = policy.adjust_feedback(None, (state,), (raw,), {})
assert raw.objectives[0] == 2.0
```

输出与消费：选择反馈selected；raw保持原值，完整Solver路径保存raw_evaluation证据。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `bias.objective_policy` · ObjectivePolicyBias

用途：Context-aware objective reweighting policy.

输入：同一候选的UnknownState及原始Feedback；权重个数与目标数一致。

```python
from mlblack.bias.policies import ObjectivePolicyBias
from mlblack.core.types import Feedback, UnknownState
import numpy as np
state = UnknownState(values=np.array([1.0, 2.0, 3.0]))
raw = Feedback(objectives=np.array([2.0, 0.5]), constraints=np.zeros(0))
policy = ObjectivePolicyBias(weights=(1.0, 0.2))
selected, = policy.adjust_feedback(None, (state,), (raw,), {})
assert raw.objectives[0] == 2.0
```

输出与消费：选择反馈selected；raw保持原值，完整Solver路径保存raw_evaluation证据。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `bias.objective_weight` · ObjectiveWeightBias

用途：Reweights objective dimensions before adapter update.

输入：同一候选的UnknownState及原始Feedback；权重个数与目标数一致。

```python
from mlblack.bias.policies import ObjectiveWeightBias
from mlblack.core.types import Feedback, UnknownState
import numpy as np
state = UnknownState(values=np.array([1.0, 2.0, 3.0]))
raw = Feedback(objectives=np.array([2.0, 0.5]), constraints=np.zeros(0))
policy = ObjectiveWeightBias(weights=(1.0, 0.2))
selected, = policy.adjust_feedback(None, (state,), (raw,), {})
assert raw.objectives[0] == 2.0
```

输出与消费：选择反馈selected；raw保持原值，完整Solver路径保存raw_evaluation证据。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `bias.optimization` · OptimizationBias

用途：Soft preference component for optimization feedback/context.

输入：同一候选的UnknownState及原始Feedback；权重个数与目标数一致。

```python
from mlblack.bias.base import OptimizationBias
from mlblack.core.types import Feedback, UnknownState
import numpy as np
state = UnknownState(values=np.array([1.0, 2.0, 3.0]))
raw = Feedback(objectives=np.array([2.0]), constraints=np.zeros(0))
policy = OptimizationBias()
selected, = policy.adjust_feedback(None, (state,), (raw,), {})
assert raw.objectives[0] == 2.0
```

输出与消费：选择反馈selected；raw保持原值，完整Solver路径保存raw_evaluation证据。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `bias.state_l2` · StateL2Bias

用途：Adds a soft L2 penalty to feedback objectives.

输入：同一候选的UnknownState及原始Feedback；权重个数与目标数一致。

```python
from mlblack.bias.policies import StateL2Bias
from mlblack.core.types import Feedback, UnknownState
import numpy as np
state = UnknownState(values=np.array([1.0, 2.0, 3.0]))
raw = Feedback(objectives=np.array([2.0]), constraints=np.zeros(0))
policy = StateL2Bias(weight=0.001)
selected, = policy.adjust_feedback(None, (state,), (raw,), {})
assert raw.objectives[0] == 2.0
```

输出与消费：选择反馈selected；raw保持原值，完整Solver路径保存raw_evaluation证据。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `capability.experiment_tracker` · ExperimentTrackerCapability

用途：Records fit/step/evaluation events to an experiment store.

输入：已装配LearningSolver；明确选择内存或SQLite记录存储。

```python
from mlblack.capabilities.tracking import ExperimentTrackerCapability, InMemoryExperimentStore
def attach_tracking(solver):
    store = InMemoryExperimentStore()
    solver.add_plugin(ExperimentTrackerCapability(store=store))
    return store  # 运行后用store.list(run_name=solver.run_name)读取本轮记录
```

输出与消费：共享生命周期中的实际实验记录，而非另一个训练循环。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `capability.resource_audit` · ResourceAuditCapability

用途：Audits effective ResourceContext during fit.

输入：由Project注入有效ResourceContext的LearningSolver。

```python
from mlblack.capabilities.resource_audit import ResourceAuditCapability
def attach_resource_audit(solver):
    audit = ResourceAuditCapability()
    solver.add_plugin(audit)
    return audit.get_context_contract()
```

输出与消费：记录实际资源绑定的观察能力；不能通过它增加授权。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `catalog.materialize_db` · materialize catalog DB

用途：Materializes the authoritative TOML catalog into a SQLite DB snapshot.

输入：开发者明确选择的本地SQLite输出路径。

```python
from mlblack.catalog.store import materialize_catalog_db
def rebuild_local_index(path):
    return materialize_catalog_db(db_path=path, profile="default")
```

输出与消费：从源码重建的目录索引统计；不是新增第二份手工权威定义。

依赖与边界：SQLite内置；本函数会写指定的开发数据库，勿指向生产库。

---

## `catalog.query` · catalog query

用途：Search catalog entries with facets and deep-link payload.

输入：源码Catalog对象及查询条件；显式catalog参数避免隐式访问数据库。

```python
from mlblack.catalog.query import query_catalog
from mlblack.catalog.registry import get_catalog
result = query_catalog({"kind": "codec", "query": "linear", "limit": 5}, catalog=get_catalog())
keys = [entry.key for entry in result.entries]
```

输出与消费：匹配组件与facets/deep link，不实例化模型。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `catalog.query_db` · DB-only catalog query

用途：Query a materialized catalog DB without loading the TOML source surface.

输入：已物化、只读使用的本地Catalog SQLite路径。

```python
from mlblack.catalog.query import query_catalog_db
def search_published_index(path):
    result = query_catalog_db({"kind": "problem", "limit": 10}, db_path=str(path))
    return [entry.key for entry in result.entries]
```

输出与消费：数据库中的Problem条目；不触发模型或训练。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `catalog.resolve_store` · resolve_catalog_store

用途：Resolves SQLite or PostgreSQL catalog stores from URL/path/env configuration.

输入：已存在索引路径或明确配置的数据库URL。

```python
from mlblack.catalog.store import resolve_catalog_store
def read_store(path):
    store = resolve_catalog_store(path, readonly=True)
    return store.catalog_summary(profile="default")
```

输出与消费：只读store的统计摘要；不创建缺失schema。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `catalog.store_postgresql` · PostgresCatalogStore

用途：PostgreSQL implementation of the DB-only catalog store surface.

输入：已有数据库的路径/URL，从私有运行配置取得，示例不填写任何真实凭据。

```python
from mlblack.catalog.store import PostgresCatalogStore
def inspect_published_catalog(location):
    store = PostgresCatalogStore(location, readonly=True)
    return store.catalog_summary(profile="default")
```

输出与消费：只读Catalog统计；连接失败会报告，不能默认为源码查询成功。

依赖与边界：SQLite内置；PostgreSQL需要psycopg与已授权数据库。

---

## `catalog.store_sqlite` · SQLiteCatalogStore

用途：SQLite implementation of the DB-only catalog store surface.

输入：已有数据库的路径/URL，从私有运行配置取得，示例不填写任何真实凭据。

```python
from mlblack.catalog.store import SQLiteCatalogStore
def inspect_published_catalog(location):
    store = SQLiteCatalogStore(location, readonly=True)
    return store.catalog_summary(profile="default")
```

输出与消费：只读Catalog统计；连接失败会报告，不能默认为源码查询成功。

依赖与边界：SQLite内置；PostgreSQL需要psycopg与已授权数据库。

---

## `core.provider_backed_learning` · ProviderBackedLearningProblem

用途：保留 ML Problem 语义并通过 BlackBase EvaluationGateway 绑定 Provider 的正式 Problem facade。

输入：真实semantic_problem与实现Provider协议、声明EvaluationProviderSpec的Provider。

```python
from mlblack.core.provider_problem import ProviderBackedLearningProblem
def attach_provider(semantic_problem, provider):
    problem = ProviderBackedLearningProblem.from_provider(semantic_problem, provider)
    return problem, problem.gateway
```

输出与消费：保持原问题语义的Provider facade与共享EvaluationGateway。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.functional_gradient_learning` · FunctionalGradientLearningProblem

用途：在 ML Problem/Provider 边界生成函数式梯度，交由 NSGABlack gradient.* Adapter 消费。

输入：实现compute_functional_gradient的Problem、匹配模型/state与JAX或TF已授权会话上下文。

```python
from mlblack.core.provider_problem import FunctionalGradientLearningProblem
def evaluate_with_functional_gradient(semantic_problem, model, state, context):
    problem = FunctionalGradientLearningProblem(semantic_problem)
    feedback = problem.evaluate(model, state, context)
    assert feedback.gradients.shape == state.as_array().shape
    return feedback
```

输出与消费：保留原目标/约束并附加扁平梯度的Feedback，由gradient.* Adapter消费。

依赖与边界：JAX或TensorFlow可选后端及相应autograd能力。

---

## `core.artifact_bundle` · ArtifactBundle

用途：Final output bundle with explicit product boundaries.

输入：已完成并可被ArtifactProvider处理的模型。

```python
from mlblack.core.artifacts import ArtifactBundle, ModelArtifact, RunReport
def bundle_result(finished_model):
    bundle = ArtifactBundle(model_artifact=ModelArtifact("example", finished_model),
                            run_report=RunReport("example", "finished"))
    return bundle, bundle.describe()
```

输出与消费：模型、报告等边界明确的ArtifactBundle；正式保存由发布事务处理。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.capability` · Capability

用途：ML semantic Plugin with fit-oriented hook names.

输入：Case构造的具体Capability子类实例与LearningSolver。

```python
from mlblack.core.capability import Capability
def attach_capability(solver, capability: Capability):
    solver.add_plugin(capability)
    return capability.get_context_contract()
```

输出与消费：加入共享Plugin生命周期的ML能力；不建立第二个调度器。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.diagnostic` · DiagnosticProblem

用途：Problem surface for a single non-search ML diagnostic evaluation.

输入：轻量诊断回调；大型诊断产物另由Artifact保存。

```python
from mlblack.core.diagnostic import DiagnosticProblem
from mlblack.core.types import UnknownState
import numpy as np
problem = DiagnosticProblem(lambda context: {"objective": 0.25, "metrics": {"rows": 4}}, name="row_audit")
feedback = problem.evaluate(None, UnknownState(values=np.zeros(1)), {})
assert feedback.metrics["rows"] == 4
```

输出与消费：一次诊断的Feedback；正式运行采用build_diagnostic_solver。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.diagnostic_representation` · DiagnosticRepresentation

用途：诊断 Case 的固定语义候选表示；控制生命周期由 NSGABlack FixedCandidateAdapter 提供。

输入：Project授权的resource_context；诊断逻辑通过runner提供。

```python
from mlblack.core.diagnostic import DiagnosticRepresentation
from mlblack.integrations.nsgablack_diagnostic import build_diagnostic_solver
def assemble_diagnostic_case(resource_context):
    solver = build_diagnostic_solver(lambda context: {"objective": 0.0},
                                    name="diagnostic_example", resource_context=resource_context)
    assert isinstance(solver.model_representation, DiagnosticRepresentation)
    return solver
```

输出与消费：使用固定语义表示和FixedCandidateAdapter的正式Solver；不在装配前调用init。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.estimator_state_artifact` · EstimatorStateArtifact

用途：EstimatorStateArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'estimator_state', estimator_state: 'Mapping[str, Any]' = <factory>)

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import EstimatorStateArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = EstimatorStateArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.head_block` · HeadBlock

用途：Contiguous parameter block consumed by an output head.

输入：一个具有明确[start,stop)位置的数值向量。

```python
from mlblack.core.head import HeadBlock
import numpy as np
block = HeadBlock(name="point", start=1, stop=3)
slice_values = block.values(np.array([9.0, 2.0, 4.0]))
assert slice_values.tolist() == [2.0, 4.0]
layout = block.describe()
```

输出与消费：该Head的数值切片与布局描述；不改变候选本身。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.integrated_model_artifact` · IntegratedModelArtifact

用途：IntegratedModelArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'integrated_model')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import IntegratedModelArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = IntegratedModelArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.learning` · LearningProblem

用途：定义数据相关的 loss、指标与约束；具有拟合或内层求解准备的模型，须用 restore_model_for_evaluation 从已保存证据恢复。

输入：实际LearningProblem子类实例、Codec模型与同版本state。

```python
from mlblack.core.problem import LearningProblem
def consume_problem(problem: LearningProblem, model, state, context):
    feedback = problem.evaluate(model, state, context)
    assert len(feedback.objectives) == problem.get_num_objectives()
    return feedback
```

输出与消费：共享Feedback；LearningProblem本身是抽象角色，不直接实例化。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.model` · ModelRepresentation

用途：解释候选的模型含义，提供 Codec、布局与修复；维度来自模型布局，真实初始化在共享 Pool 建立后的运行阶段执行。

输入：具体ModelRepresentation实现，以及共享Solver已生成的UnknownState。

```python
from mlblack.core.representation import ModelRepresentation
def decode_at_evaluation(representation: ModelRepresentation, state, context):
    # state已由Solver在Pool建立后初始化；此处只解释其模型含义。
    model = representation.decode(state, context)
    return model, representation.fingerprint(state)
```

输出与消费：解码模型及语义指纹；不将它当作Adapter Unit或再次初始化。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.model_artifact` · ModelArtifact

用途：Serializable boundary around the trained model payload.

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import ModelArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = ModelArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.neural_graph_artifact` · NeuralGraphArtifact

用途：NeuralGraphArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'neural_graph', graph_spec: 'Mapping[str, Any]' = <factory>, parameter_layout: 'Mapping[str, Any]' = <factory>, head_artifact: 'Mapping[str, Any]' = <factory>, audit_artifact: 'Mapping[str, Any]' = <factory>, graph_spec_digest: 'str' = '', parameter_layout_digest: 'str' = '')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import NeuralGraphArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = NeuralGraphArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.output` · OutputHead

用途：Decoder-side output semantics.

输入：具体OutputHead实例、符合该Head长度的候选值，以及Codec提供的base_decode。

```python
from mlblack.core.head import OutputHead
def decode_head(head: OutputHead, values, base_decode, context):
    dimension = 3
    blocks = head.blocks(dimension)
    decoded = head.decode(values, base_dimension=dimension,
                          base_decode=base_decode, context=context)
    return decoded, blocks
```

输出与消费：带输出语义的模型/预测对象和HeadBlock布局。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.representation_pipeline` · RepresentationPipeline

用途：Unknown-state encoder/decoder, equivalent to nsgablack Representation.

输入：具体ModelRepresentation实现，以及共享Solver已生成的UnknownState。

```python
from mlblack.core.representation import RepresentationPipeline
def decode_at_evaluation(representation: RepresentationPipeline, state, context):
    # state已由Solver在Pool建立后初始化；此处只解释其模型含义。
    model = representation.decode(state, context)
    return model, representation.fingerprint(state)
```

输出与消费：解码模型及语义指纹；不将它当作Adapter Unit或再次初始化。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.run_report` · RunReport

用途：Auditable run summary distinct from artifact and trainer state.

输入：本次真实run的指标、组件和已生效资源描述；示例数值只说明字段。

```python
from mlblack.core.artifacts import RunReport
report = RunReport(run_name="example", status="finished", metrics={"valid.rmse": 0.5},
                   components={"problem": "regression"}, resources={"threads": 1})
payload = report.describe()
assert payload["metrics"]["valid.rmse"] == 0.5
```

输出与消费：可序列化RunReport；示例字段不是本轮训练成绩。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.sklearn_mlp_artifact` · SklearnMLPArtifact

用途：SklearnMLPArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'sklearn_mlp')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import SklearnMLPArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = SklearnMLPArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.symbolic_interval_artifact` · SymbolicIntervalArtifact

用途：SymbolicIntervalArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'symbolic_interval')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import SymbolicIntervalArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = SymbolicIntervalArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.symbolic_model_artifact` · SymbolicModelArtifact

用途：SymbolicModelArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'symbolic_model')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import SymbolicModelArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = SymbolicModelArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.torch_model_artifact` · TorchModelArtifact

用途：TorchModelArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'torch_model')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import TorchModelArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = TorchModelArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.trainer_state_artifact` · TrainerStateArtifact

用途：Checkpoint-style trainer state payload.

输入：安全阶段可读取状态的实际LearningSolver；state是脱离后的Mapping。

```python
from mlblack.core.artifacts import TrainerStateArtifact
def package_checkpoint(solver):
    state = solver.get_state()
    artifact = TrainerStateArtifact(payload=state, metadata={"run_name": solver.run_name})
    return artifact, artifact.describe()
```

输出与消费：TrainerStateArtifact描述；恢复仍排队进入统一post-setup事务。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.tree_ensemble_artifact` · TreeEnsembleArtifact

用途：TreeEnsembleArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'tree_ensemble')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import TreeEnsembleArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = TreeEnsembleArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.typed_model_artifact` · TypedModelArtifact

用途：TypedModelArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'model')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import TypedModelArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = TypedModelArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `core.xg_boost_artifact` · XGBoostArtifact

用途：XGBoostArtifact(name: 'str', model: 'Any', family: 'str' = '', head: 'str' = 'point', representation: 'Mapping[str, Any]' = <factory>, metadata: 'Mapping[str, Any]' = <factory>, artifact_type: 'str' = 'xgboost')

输入：与该Artifact类型对应的已完成模型，以及Codec布局报告；NeuralGraph/Tree/Torch等不可混用。

```python
from mlblack.core.artifacts import XGBoostArtifact
def wrap_finished_model(trained_model, representation_report):
    artifact = XGBoostArtifact(name="demo_model", model=trained_model,
                        representation=representation_report)
    payload = artifact.describe()
    assert payload["name"] == "demo_model"
    return artifact, payload
```

输出与消费：类型化Artifact及序列化描述；正式权威交付仍经FinalizationHooks/ArtifactProvider。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `dashboard.artifact_html` · artifact dashboard export

用途：Exports a static HTML viewer for typed mlblack artifacts.

输入：开发输出HTML路径与可信模型Artifact描述Mapping/JSON路径。

```python
from mlblack.catalog.artifacts import export_artifact_html
def export_model_view(path, artifact):
    return export_artifact_html(path, artifact)
```

输出与消费：静态模型查看页，不执行模型训练。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `dashboard.backend_matrix_html` · backend capability matrix export

用途：Exports a static HTML matrix of backend capability support.

输入：开发输出HTML路径；矩阵来自已声明backend contracts。

```python
from mlblack.catalog.backend_dashboard import export_backend_matrix_html
def export_capability_matrix(path):
    return export_backend_matrix_html(path)
```

输出与消费：后端能力矩阵；声明可见性不等于依赖已安装或执行已通过。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `dashboard.catalog_html` · catalog dashboard export

用途：Exports a lightweight HTML catalog report.

输入：开发输出HTML路径及当前源码Catalog。

```python
from mlblack.catalog.dashboard import export_catalog_html
from mlblack.catalog.registry import get_catalog
def export_catalog(path):
    return export_catalog_html(path, get_catalog())
```

输出与消费：可离线查看的静态目录页。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `dashboard.catalog_streamlit` · catalog Streamlit dashboard

用途：Launches an interactive Streamlit catalog dashboard similar to the nsgablack catalog UI.

输入：mlblack/catalog/dashboard.py实际脚本路径；仅在用户明确启动本地UI时调用。

```python
from mlblack.catalog.dashboard import launch_catalog_dashboard
def launch_local_catalog(script_path):
    return launch_catalog_dashboard(script_path=script_path, profile="default",
                                    host="127.0.0.1", port=8767, headless=True)
```

输出与消费：本机Streamlit目录进程退出码；页面浏览不训练模型。

依赖与边界：Streamlit；示例不在审计时启动监听器。

---

## `dashboard.catalog_web` · catalog query web app

用途：Serves a lightweight catalog query UI and JSON API without external web dependencies.

输入：已物化本地目录库；端口仅绑定loopback，启动和关闭由使用者明确控制。

```python
from mlblack.catalog.web_app import serve_catalog_web
def local_server(db_path):
    server = serve_catalog_web(host="127.0.0.1", port=8767, db_path=str(db_path))
    return server  # 调用方负责serve_forever()/shutdown()与访问控制
```

输出与消费：HTTPServer对象；不是AI Operator Shell，不复用退休8765服务。

依赖与边界：Python标准库及本地数据库；示例不自动启动网络服务。

---

## `dashboard.experiment_html` · experiment dashboard export

用途：Exports a lightweight HTML experiment record report.

输入：ExperimentQuery返回的ExperimentRecord列表与HTML输出路径。

```python
from mlblack.catalog.experiment.dashboard import export_experiment_html
def export_records(path, records):
    return export_experiment_html(path, records)
```

输出与消费：实验记录HTML报告，保留原run与step信息。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `example.etf_temporal_forecast` · ETF Temporal Forecast

用途：ETF walk-forward temporal forecast case with ridge/boosting baselines and rank-IC, hit-rate, Sharpe, drawdown and turnover metrics.

输入：已准备的ETF panel_builder、walk-forward配置、输出目录与Project授权。

```python
from mlblack.integrations.etf_temporal_forecast import run_etf_temporal_forecast_multi_seed
def evaluate_existing_panel(panel_builder, config, resource_context, output_dir):
    return run_etf_temporal_forecast_multi_seed(cfg=config, seeds=(42,),
        panel_builder=panel_builder, output_dir=output_dir, resource_context=resource_context)
```

输出与消费：含多种预测/组合指标的真实结果；不能把历史收益或示例预期当本次结果。

依赖与边界：配置指定的数据与可选统计/boosting依赖；示例不联网取金融数据，也不执行投资操作。

---

## `example.traffic_arimax_attribution` · ARIMAX Factor Attribution on Traffic CI

用途：ARIMAX(2,0,1) factor group attribution decomposing CI variation into Weather/AQI/Holiday/CI_Lags/Time_Cyclic groups.

输入：该Case README声明的真实交通数据、依赖与配置；父Project提供resource_context。

```python
from mlblack.examples.cases.traffic_congestion.cases.arimax_factor_attribution.build_solver import build_solver
def assemble_registered_case(config, resource_context):
    return build_solver(config=config, resource_context=resource_context)
```

输出与消费：该Case实际Solver；正式运行入口是examples/cases/traffic_congestion/run_project.py。

依赖与边界：依Case需要statsmodels/scipy/sklearn/xgboost/shap等可选依赖；发布包不默认携带业务数据。

本片段只演示正确的canonical装配入口，未执行交通分析；修复了旧examples.*命名空间歧义。

---

## `example.traffic_gam_linearity` · GAM Nonlinearity Check on Traffic CI

用途：B-spline GAM vs linear regression comparison diagnosing whether linear assumptions hold for traffic CI prediction.

输入：该Case README声明的真实交通数据、依赖与配置；父Project提供resource_context。

```python
from mlblack.examples.cases.traffic_congestion.cases.gam_linearity_check.build_solver import build_solver
def assemble_registered_case(config, resource_context):
    return build_solver(config=config, resource_context=resource_context)
```

输出与消费：该Case实际Solver；正式运行入口是examples/cases/traffic_congestion/run_project.py。

依赖与边界：依Case需要statsmodels/scipy/sklearn/xgboost/shap等可选依赖；发布包不默认携带业务数据。

本片段只演示正确的canonical装配入口，未执行交通分析；修复了旧examples.*命名空间歧义。

---

## `example.traffic_granger_causality` · Granger Causality Check on Traffic CI

用途：Pairwise Granger causality tests between CI and external factors (weather, AQI, holidays) on real traffic data.

输入：该Case README声明的真实交通数据、依赖与配置；父Project提供resource_context。

```python
from mlblack.examples.cases.traffic_congestion.cases.granger_causality_check.build_solver import build_solver
def assemble_registered_case(config, resource_context):
    return build_solver(config=config, resource_context=resource_context)
```

输出与消费：该Case实际Solver；正式运行入口是examples/cases/traffic_congestion/run_project.py。

依赖与边界：依Case需要statsmodels/scipy/sklearn/xgboost/shap等可选依赖；发布包不默认携带业务数据。

本片段只演示正确的canonical装配入口，未执行交通分析；修复了旧examples.*命名空间歧义。

---

## `example.traffic_shap_consistency` · SHAP Contribution Consistency on Traffic CI

用途：Cross-paradigm feature importance comparison: Linear coefficients vs XGBoost gain vs SHAP vs Permutation on traffic CI.

输入：该Case README声明的真实交通数据、依赖与配置；父Project提供resource_context。

```python
from mlblack.examples.cases.traffic_congestion.cases.shap_contribution_check.build_solver import build_solver
def assemble_registered_case(config, resource_context):
    return build_solver(config=config, resource_context=resource_context)
```

输出与消费：该Case实际Solver；正式运行入口是examples/cases/traffic_congestion/run_project.py。

依赖与边界：依Case需要statsmodels/scipy/sklearn/xgboost/shap等可选依赖；发布包不默认携带业务数据。

本片段只演示正确的canonical装配入口，未执行交通分析；修复了旧examples.*命名空间歧义。

---

## `example.traffic_symbolic_regression` · Symbolic Regression on Traffic CI

用途：Gradient-descent linear regression on traffic CI mechanism reconstruction (same-day features), baseline for symbolic approach.

输入：该Case README声明的真实交通数据、依赖与配置；父Project提供resource_context。

```python
from mlblack.examples.cases.traffic_congestion.cases.symbolic_regression.build_solver import build_solver
def assemble_registered_case(config, resource_context):
    return build_solver(config=config, resource_context=resource_context)
```

输出与消费：该Case实际Solver；正式运行入口是examples/cases/traffic_congestion/run_project.py。

依赖与边界：依Case需要statsmodels/scipy/sklearn/xgboost/shap等可选依赖；发布包不默认携带业务数据。

本片段只演示正确的canonical装配入口，未执行交通分析；修复了旧examples.*命名空间歧义。

---

## `example.traffic_xgboost_baseline` · XGBoost Baseline for Traffic CI Prediction

用途：XGBoost baseline on traffic CI forward prediction (lag-only features), using mlblack tree_boosting preset.

输入：该Case README声明的真实交通数据、依赖与配置；父Project提供resource_context。

```python
from mlblack.examples.cases.traffic_congestion.cases.xgboost_baseline.build_solver import build_solver
def assemble_registered_case(config, resource_context):
    return build_solver(config=config, resource_context=resource_context)
```

输出与消费：该Case实际Solver；正式运行入口是examples/cases/traffic_congestion/run_project.py。

依赖与边界：依Case需要statsmodels/scipy/sklearn/xgboost/shap等可选依赖；发布包不默认携带业务数据。

本片段只演示正确的canonical装配入口，未执行交通分析；修复了旧examples.*命名空间歧义。

---

## `experiment.query` · experiment query

用途：Query SQLite experiment records with simple filters and facets.

输入：ExperimentTracker已写出的SQLite实验记录路径。

```python
from mlblack.catalog.experiment.query import query_experiments
def inspect_run(path):
    result = query_experiments(str(path), {"run_name": "demo", "min_step": 1, "limit": 20})
    return result.as_dict()
```

输出与消费：符合run与步数条件的真实记录及facets；空集不是训练成功证据。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `integration.hf_sft` · build_hf_sft_solver

用途：真实 HF + PEFT 会话 SFT：复用 LearningSolver、EvaluationGateway 与 Case Artifact，完整 fit 是一次评估，非逐 optimizer step 回滚。

输入：本地已准备的模型与对话JSONL路径、Project授权；不会默认访问或下载远程权重。

```python
from mlblack.integrations.hf_sft import HFSFTConfig, build_hf_sft_solver
def build_solver(local_model_path, dataset_path, resource_context):
    config = HFSFTConfig(model_name_or_path=str(local_model_path),
                         optimizer_steps=2, max_length=128, local_files_only=True)
    return build_hf_sft_solver(config, dataset_path, resource_context=resource_context)
```

输出与消费：一次完整SFT fit作为一个求值的正式Solver；不是逐optimizer step回滚。

依赖与边界：Torch、transformers、PEFT、accelerate；资源取自Project，不在本示例训练。

---

## `integration.nsgablack_gradient` · build_gradient_trainer

用途：稳定 method ID 装配：nsgablack GradientOptimizerAdapter + mlblack Problem/Provider + BlackBase L0/StateRef runtime。

输入：ML神经Problem、布局匹配的表示及Project CPU/GPU授权。

```python
from mlblack.integrations.nsgablack_gradient import build_gradient_trainer
def build_solver(problem, representation, resource_context):
    return build_gradient_trainer(problem=problem, representation=representation,
          method="gradient.adamw", compute_backend="torch", learning_rate=0.001,
          resource_context=resource_context)
```

输出与消费：统一的GradientOptimizerAdapter/Provider/LearningSolver组合。

依赖与边界：Torch及统一框架栈；不在装配示例中执行训练。

---

## `integration.nsgablack_optimization` · build_optimization_adapter

用途：把 ML 用户词汇解析为稳定优化方法标识，并装配 nsgablack 的 provider-neutral Adapter。

输入：稳定method ID及对应参数；Problem/Provider须提供梯度。

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
adapter = build_optimization_adapter("gradient.adam", learning_rate=0.001)
state = adapter.get_state()
```

输出与消费：provider-neutral优化Adapter，装配给LearningSolver使用。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `integration.learning_solver` · LearningSolver

用途：ML 语义 facade：复用共享 Pool、Unit、编排和唯一 Solver 生命周期；v7 状态保存池值闭包，正式 checkpoint 保存 ML 最佳反馈绑定。

输入：支持解析梯度的Problem、布局已知的ModelRepresentation、Project授权资源。

```python
from mlblack.integrations.nsgablack_control import LearningSolver
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
def build_solver(problem, representation, resource_context):
    adapter = build_optimization_adapter("gradient.sgd", learning_rate=0.05)
    return LearningSolver(problem=problem, representation=representation,
                          adapter=adapter, resource_context=resource_context)
```

输出与消费：由同一个ComposableSolver驱动的ML求解器；正式Case负责fit/run与发布。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `integration.ml_learning_problem_bridge` · MLLearningProblemBridge

用途：把 MLBlack LearningProblem 的模型/状态/Feedback 语义投影为 NSGABlack BlackBoxProblem。

输入：已知dimension、真实ML Problem和ModelRepresentation；完整控制绑定由LearningSolver完成。

```python
from mlblack.integrations.nsgablack_control import MLLearningProblemBridge, MLRepresentationBridge
def bridge_problem(semantic_problem, representation, dimension):
    representation_bridge = MLRepresentationBridge(representation)
    bridge = MLLearningProblemBridge(semantic_problem, representation_bridge, dimension=dimension)
    return bridge, bridge.get_num_objectives()
```

输出与消费：供NSGABlack控制面使用的Problem边界及目标数，不重复训练。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `integration.ml_representation_bridge` · MLRepresentationBridge

用途：在仓库边界转换 UnknownState 与 ndarray；模型布局、初始化、修复和解码仍由 ML Codec 独占。

输入：支持encode/decode的具体ModelRepresentation与已知模型；不调用init来猜维度。

```python
from mlblack.integrations.nsgablack_control import MLRepresentationBridge
def bridge_evaluated_model(representation, model, context):
    bridge = MLRepresentationBridge(representation)
    state = bridge.encode(model, context)
    restored_model = bridge.decode(state, context)
    return state, restored_model
```

输出与消费：保持模型语义metadata的UnknownState以及解码模型；不是算法Unit转换。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `integration.nsgablack_learning_case_evaluator` · NsgablackLearningCaseEvaluator

用途：Invoke a complete ML semantic child Case through the shared CaseRuntime.

输入：已在同一Project注册的linear_point内层Case；当前调用身份与CaseRuntime由外层提供。

```python
from mlblack.integrations.nsgablack_learning_case import NsgablackLearningCaseEvaluator
def evaluate_inner_case(control, x, current_call_id, context):
    evaluator = NsgablackLearningCaseEvaluator(case_name="linear_point", max_steps=3)
    return evaluator.evaluate(solver=control, x=x,
                              individual_id=current_call_id, context=context)
```

输出与消费：Evaluation Provider可调用的内层Case桥，结果经正式payload/Artifact返回。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `integration.pretrained_checkpoint_mapper` · PretrainedCheckpointMapper

用途：Map an external checkpoint state_dict into an mlblack neural graph.

输入：已加载可信state_dict及布局匹配的目标NeuralGraph模型。

```python
from mlblack.integrations.transformers_bridge import PretrainedCheckpointMapper
def map_known_checkpoint(state_dict, target_neural_model):
    mapper = PretrainedCheckpointMapper()
    report = mapper.map_state_dict(state_dict, target_neural_model)
    flat_values = mapper.flat_values_from_model(target_neural_model)
    return report, flat_values
```

输出与消费：映射报告与目标模型布局下的扁平值；不把外部权重误当成Adapter Unit。

依赖与边界：具体模型路线所需Torch/transformers；加载可信文件由调用者负责。

---

## `integration.pretrained_model_bridge` · PretrainedModelBridge

用途：Lazy pretrained-model loader for external-model/component use cases.

输入：本地模型目录；device_from_grant必须来自已授权ResourceContext。

```python
from mlblack.integrations.transformers_bridge import PretrainedModelBridge, PretrainedModelBridgeConfig
def load_local_model(local_model_path, device_from_grant):
    bridge = PretrainedModelBridge(PretrainedModelBridgeConfig(
        model_name_or_path=str(local_model_path), task="base", device=device_from_grant,
        kwargs={"local_files_only": True}))
    return bridge.load()
```

输出与消费：惰性加载的外部模型供正式Provider消费，不另拥有训练生命周期。

依赖与边界：transformers、Torch及本地模型；不默认联网下载。

---

## `integration.pretrained_tokenizer_bridge` · PretrainedTokenizerBridge

用途：Lazy bridge to HuggingFace tokenizers.

输入：本地已准备的tokenizer目录与字符串批次。

```python
from mlblack.integrations.transformers_bridge import PretrainedTokenizerBridge, PretrainedTokenizerBridgeConfig
def encode_text(local_model_path):
    bridge = PretrainedTokenizerBridge(PretrainedTokenizerBridgeConfig(
        model_name_or_path=str(local_model_path), max_length=16,
        kwargs={"local_files_only": True}))
    encoded = bridge.encode(["hello framework"])
    return encoded["input_ids"], encoded.get("attention_mask")
```

输出与消费：token ID及attention mask矩阵，可作为模型数据输入。

依赖与边界：transformers与本地tokenizer文件；不默认联网下载。

---

## `nsgablack_neural.transformer_spec_search` · TransformerSpecSearchProblem

用途：nsgablack-facing problem for outer TransformerSpec search.

输入：适配分类或LM任务的NumericDataView与父Project资源授权。

```python
from mlblack.integrations.nsgablack_neural.transformer_spec_search import TransformerSpecSearchProblem
def build_outer_problem(token_data, resource_context):
    problem = TransformerSpecSearchProblem(token_data, resource_context=resource_context)
    spec = problem.decode_spec([0.0] * problem.dimension)
    return problem, spec
```

输出与消费：外层结构搜索Problem与解码后的Transformer规格；真实evaluate会调用内层ML训练。

依赖与边界：Torch等内层神经后端；嵌套执行仍走正式Case/共享授权。

---

## `nsgablack_neural.transformer_spec_search_space` · TransformerSpecSearchSpace

用途：Auto-discovered mlblack component `nsgablack_neural.transformer_spec_search_space`.

输入：8维[0,1]外层配置向量；task约定由TransformerSpecSearchConfig提供。

```python
from mlblack.integrations.nsgablack_neural.transformer_spec_search import TransformerSpecSearchSpace
space = TransformerSpecSearchSpace()
spec = space.decode([0.0] * space.dimension)
bounds = space.bounds()
assert len(bounds) == 8
```

输出与消费：NeuralGraphSpec与外层边界；解码配置不执行内层训练。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.basis_conditioned_symbolic_task` · BasisConditionedSymbolicTaskProblem

用途：nsgablack-compatible Stage 2 problem.

输入：Stage1已发布的OrthogonalBasisSetArtifact、同语义DataView和派生资源授权。

```python
from mlblack.integrations.nsgablack_symbolic.task_symbolic_problem import BasisConditionedSymbolicTaskProblem
def stage_two_problem(data, basis_artifact, resource_context):
    problem = BasisConditionedSymbolicTaskProblem(data, basis_artifact=basis_artifact,
                                                 resource_context=resource_context)
    return problem, problem.describe()
```

输出与消费：条件于已冻结基组的Stage2 Problem；不隐式重做Stage1。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.expression_graph_cache` · ExpressionGraphCache

用途：Reusable cache for symbolic expression values and derivative expressions.

输入：合法的符号表达式树及样本矩阵；相同批次缓存键必须符合输入内容。

```python
from mlblack.integrations.nsgablack_symbolic.graph_cache import ExpressionGraphCache
from mlblack.models.symbolic import feature_expr
import numpy as np
cache = ExpressionGraphCache(backend="memory")
try:
    values = cache.evaluate_expression(feature_expr(0), np.array([[1.0], [2.0]]))
    stats = cache.stats()
finally:
    cache.close()
```

输出与消费：表达式数值与缓存统计；缓存不是模型训练状态。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.function_pool_index_search_space` · FunctionPoolIndexSearchSpace

用途：Index-coded outer search space over a symbolic FunctionPool.

输入：至少2项且与本次数据匹配的FunctionPool。

```python
from mlblack.integrations.nsgablack_symbolic.search_space import FunctionPoolIndexSearchSpace
def decode_candidates(function_pool):
    space = FunctionPoolIndexSearchSpace(function_pool=function_pool, dimension=2)
    indices = space.decode_indices([0.0, 1.0])
    terms = space.decode_terms([0.0, 1.0])
    return indices, terms
```

输出与消费：规范化索引和CandidateTerm；不把索引当作已拟合系数。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.orthogonal_basis_outer` · OrthogonalBasisOuterProblem

用途：nsgablack-compatible Stage 1 problem for symbolic basis search.

输入：NumericDataView、候选FunctionPool、父Project授权。

```python
from mlblack.integrations.nsgablack_symbolic.orthogonal_problem import OrthogonalBasisOuterProblem
def stage_one_problem(data, function_pool, resource_context):
    problem = OrthogonalBasisOuterProblem(data, function_pool=function_pool,
                                          resource_context=resource_context)
    return problem, problem.describe()
```

输出与消费：Stage1正交基搜索Problem，由外层Adapter送评；运行后build_artifact交付Stage2。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.orthogonal_basis_set_artifact` · OrthogonalBasisSetArtifact

用途：Stage 1 output boundary consumed by Stage 2.

输入：Stage1正式Artifact与对应NumericDataView，特征顺序必须一致。

```python
from mlblack.integrations.nsgablack_symbolic.artifacts import OrthogonalBasisSetArtifact
def use_basis(artifact: OrthogonalBasisSetArtifact, data):
    transformed = artifact.to_basis_data_view(data)
    function_pool = artifact.as_function_pool(data.X_train, y=data.y_train)
    return transformed, function_pool
```

输出与消费：可传给Stage2的基空间DataView和FunctionPool；旧SymbolicBasisArtifact索引已退役。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_basis_consensus_analyzer` · SymbolicBasisConsensusAnalyzer

用途：Artifact/report capability for basis consensus and overlap.

输入：多次独立Stage1产物序列和同特征顺序样本X。

```python
from mlblack.integrations.nsgablack_symbolic.basis_consensus import SymbolicBasisConsensusAnalyzer
def inspect_symbolic_result(artifacts, X):
    component = SymbolicBasisConsensusAnalyzer()
    report = component.analyze(artifacts, X=X)
    return report
```

输出与消费：专门的审计/一致性/过拟合/结构报告；由搜索策略显式决定如何使用，不自动改Problem。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_branch_evaluator` · SymbolicBranchEvaluator

用途：Branch/regime audit evaluator for fitted symbolic task artifacts.

输入：已拟合SymbolicTaskArtifact与NumericDataView。

```python
from mlblack.integrations.nsgablack_symbolic.evaluation import SymbolicBranchEvaluator
def inspect_symbolic_result(artifact, data):
    component = SymbolicBranchEvaluator()
    report = component.evaluate_task_artifact(artifact, data)
    return report
```

输出与消费：专门的审计/一致性/过拟合/结构报告；由搜索策略显式决定如何使用，不自动改Problem。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_candidate_scorer` · SymbolicCandidateScorer

用途：Candidate scoring policy for nsgablack symbolic outer search.

输入：同一候选原始目标/约束与训练验证指标；若用path memory须明确实例。

```python
from mlblack.integrations.nsgablack_symbolic.search_policy import SymbolicCandidateScorer
scorer = SymbolicCandidateScorer()
report = scorer.score(objectives=[0.2, 0.1], constraints=[0.0],
                       metrics={"train.rmse": 0.3, "valid.rmse": 0.4}, record_memory=False)
```

输出与消费：CandidateScoreReport供外层搜索排序；不把评分覆盖为原始测量。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_expression_audit_producer` · SymbolicExpressionAuditProducer

用途：Produces symbolic artifact audit sections from expressions and term metadata.

输入：合法expression Mapping序列与真实feature_names。

```python
from mlblack.integrations.nsgablack_symbolic.expression_audit import SymbolicExpressionAuditProducer
def inspect_symbolic_result(expressions, feature_names):
    component = SymbolicExpressionAuditProducer()
    report = component.analyze(expressions, feature_names=feature_names)
    return report
```

输出与消费：专门的审计/一致性/过拟合/结构报告；由搜索策略显式决定如何使用，不自动改Problem。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_fold_evaluator` · SymbolicFoldEvaluator

用途：Lightweight fold evaluator for symbolic artifacts.

输入：SymbolicTaskArtifact与已配置验证切分的NumericDataView。

```python
from mlblack.integrations.nsgablack_symbolic.evaluation import SymbolicFoldEvaluator
def inspect_symbolic_result(artifact, data):
    component = SymbolicFoldEvaluator()
    report = component.evaluate_task_artifact(artifact, data)
    return report
```

输出与消费：专门的审计/一致性/过拟合/结构报告；由搜索策略显式决定如何使用，不自动改Problem。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_orthogonal_nested_suite` · SymbolicOrthogonalNestedSuite

用途：Serial Stage 1 -> Stage 2 symbolic plan surface.

输入：Stage1正式Problem、Stage2配置、共同数据与父授权。

```python
from mlblack.integrations.nsgablack_symbolic.builders import SymbolicOrthogonalNestedSuite
def prepare_stages(data, stage1_problem, stage2_config, resource_context):
    suite = SymbolicOrthogonalNestedSuite(data, stage1_problem, stage2_config,
                                          resource_context=resource_context)
    return suite.as_spec()
```

输出与消费：串行Stage1→Stage2计划描述；由共享Project执行阶段与授权。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_overfit_guard` · SymbolicOverfitGuard

用途：Scores train/validation drift for symbolic structure search.

输入：同一候选train/valid指标Mapping，不能混用不同运行的指标。

```python
from mlblack.integrations.nsgablack_symbolic.overfit_guard import SymbolicOverfitGuard
def inspect_symbolic_result(metrics):
    component = SymbolicOverfitGuard()
    report = component.evaluate(metrics, metric_name="rmse")
    return report
```

输出与消费：专门的审计/一致性/过拟合/结构报告；由搜索策略显式决定如何使用，不自动改Problem。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_path_memory` · SymbolicPathMemory

用途：Persistent memory for symbolic structure search paths.

输入：稳定表达式键及本次真实评价增量；独立实验用独立namespace。

```python
from mlblack.integrations.nsgablack_symbolic.path_memory import SymbolicPathMemory
from tempfile import TemporaryDirectory
from pathlib import Path
with TemporaryDirectory() as folder:
    memory = SymbolicPathMemory(db_path=str(Path(folder) / "path.sqlite"), namespace="example")
    try:
        memory.record_expr_outcome("feature:x0", selected_score=0.5, delta_score=-0.1, success=True)
        prior = memory.get_expr_prior("feature:x0")
    finally:
        memory.close()
```

输出与消费：可用于下轮搜索的PathPrior；不与候选Pool身份混为一谈。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_replay_record_builder` · SymbolicReplayRecordBuilder

用途：Builds JSON-compatible replay records for nested symbolic candidates.

输入：正式evaluate_detailed返回的record与本轮资源上下文。

```python
from mlblack.integrations.nsgablack_symbolic.replay import SymbolicReplayRecordBuilder
def record_evaluation(record, resource_context):
    builder = SymbolicReplayRecordBuilder()
    return builder.build(record, stage="stage1", problem_name="basis",
                         resource_context=resource_context)
```

输出与消费：JSON兼容的候选replay记录；记录不隐式重跑求值。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_structure_guard` · SymbolicStructureGuard

用途：Outer-search structural guard for symbolic candidates.

输入：CandidateTerm或等价Mapping序列，已声明表达式结构。

```python
from mlblack.integrations.nsgablack_symbolic.structure_guard import SymbolicStructureGuard
def inspect_symbolic_result(selected_terms):
    component = SymbolicStructureGuard()
    report = component.evaluate(selected_terms)
    return report
```

输出与消费：专门的审计/一致性/过拟合/结构报告；由搜索策略显式决定如何使用，不自动改Problem。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `nsgablack_symbolic.symbolic_task_artifact` · SymbolicTaskArtifact

用途：Stage 2 task-expression artifact.

输入：Stage2运行后正式发布的SymbolicTaskArtifact。

```python
from mlblack.integrations.nsgablack_symbolic.artifacts import SymbolicTaskArtifact
def read_task_result(artifact: SymbolicTaskArtifact):
    report = artifact.describe()
    schema = artifact.schema()
    return report, schema.as_dict()
```

输出与消费：含表达式、拟合状态、指标和schema的可审计产物描述。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `problem.fixed_symbolic_regression` · FixedSymbolicRegressionProblem

用途：Regression evaluator for fixed symbolic expression decoders.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.symbolic import FixedSymbolicRegressionProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = FixedSymbolicRegressionProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.orthogonal_basis_evaluation` · OrthogonalBasisEvaluationProblem

用途：Evaluate a fitted symbolic basis set for orthogonality objectives.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.symbolic import OrthogonalBasisEvaluationProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = OrthogonalBasisEvaluationProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.piecewise_regression` · PiecewiseRegressionProblem

用途：Regression evaluator with branch distribution metrics for piecewise models.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.conditional import PiecewiseRegressionProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = PiecewiseRegressionProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.rolling_origin_forecasting` · RollingOriginForecastingProblem

用途：Rolling-origin evaluator for horizon-specific forecast quality.

输入：TimeSeriesDataView：有时间顺序的单变量序列及验证窗口；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.time_series import RollingOriginForecastingProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = RollingOriginForecastingProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.supervised_classification` · SupervisedClassificationProblem

用途：Evaluator for classification accuracy and log-loss objectives.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.classification import SupervisedClassificationProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = SupervisedClassificationProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.tabular_neural_classification` · TabularNeuralClassificationProblem

用途：表格 NeuralGraph 分类语义：定义交叉熵、验证目标和分类指标，由 EvaluationProvider 执行 backend loss/autograd。

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TabularNeuralClassificationProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TabularNeuralClassificationProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.tabular_neural_regression` · TabularNeuralRegressionProblem

用途：表格 NeuralGraph 回归语义：定义 MSE、验证目标和回归指标，由 EvaluationProvider 执行 backend loss/autograd。

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TabularNeuralRegressionProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TabularNeuralRegressionProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.supervised_estimator_fit` · SupervisedEstimatorFitRegressionProblem

用途：Fits decoded estimator specs and scores the fitted estimator.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.supervised import SupervisedEstimatorFitRegressionProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = SupervisedEstimatorFitRegressionProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.supervised_estimator_fit_regression` · SupervisedEstimatorFitRegressionProblem

用途：Evaluator that fits decoded external estimator specs before scoring.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.supervised import SupervisedEstimatorFitRegressionProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = SupervisedEstimatorFitRegressionProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.supervised_interval_regression` · SupervisedIntervalRegressionProblem

用途：Evaluator for decoded interval-output models.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.supervised import SupervisedIntervalRegressionProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = SupervisedIntervalRegressionProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.supervised_regression` · SupervisedRegressionProblem

用途：Data-dependent evaluator for point regression.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.supervised import SupervisedRegressionProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = SupervisedRegressionProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.temporal_neural_forecasting` · TemporalNeuralForecastingProblem

用途：Evaluate temporal neural graph models (LSTM/TCN/Transformer) for sequence forecasting.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TemporalNeuralForecastingProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TemporalNeuralForecastingProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.temporal_neural_probabilistic_forecasting` · TemporalNeuralProbabilisticForecastingProblem

用途：Evaluate temporal neural graph models with negative log-likelihood loss for probabilistic forecasting.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TemporalNeuralProbabilisticForecastingProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TemporalNeuralProbabilisticForecastingProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.temporal_neural_rolling_origin` · TemporalNeuralRollingOriginProblem

用途：Rolling-origin evaluation for temporal neural graph forecasters.

输入：TimeSeriesDataView：有时间顺序的单变量序列及验证窗口；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TemporalNeuralRollingOriginProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TemporalNeuralRollingOriginProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.time_series_forecasting` · TimeSeriesForecastingProblem

用途：Evaluator for univariate time-series forecasting models.

输入：TimeSeriesDataView：有时间顺序的单变量序列及验证窗口；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.time_series import TimeSeriesForecastingProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TimeSeriesForecastingProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.tiny_cnn_image_classification` · TinyCNNImageClassificationProblem

用途：Evaluate tiny CNN image classification heads.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TinyCNNImageClassificationProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TinyCNNImageClassificationProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.tiny_cnn_image_contrastive` · TinyCNNImageContrastiveProblem

用途：Triplet contrastive/retrieval loss over tiny CNN embedding heads.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TinyCNNImageContrastiveProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TinyCNNImageContrastiveProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.tiny_gnn_graph_classification` · TinyGNNGraphClassificationProblem

用途：Evaluate tiny GNN graph classification heads.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TinyGNNGraphClassificationProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TinyGNNGraphClassificationProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.tiny_transformer_classification` · TinyTransformerClassificationProblem

用途：Evaluate tiny Transformer classification heads with torch autograd.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TinyTransformerClassificationProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TinyTransformerClassificationProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.tiny_transformer_dpo_preference` · TinyTransformerDPOPreferenceProblem

用途：DPO-style preference loss over chosen/rejected token sequences.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TinyTransformerDPOPreferenceProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TinyTransformerDPOPreferenceProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.tiny_transformer_language_model` · TinyTransformerLanguageModelProblem

用途：Evaluate tiny Transformer LM heads on next-token prediction.

输入：与当前模型语义匹配的DataView：分类标签/连续目标/图/图像/偏好对；训练验证切分已由Case完成；decoded_model与state是同一候选版本；context来自正式Solver求值调用。

```python
from mlblack.problems.neural import TinyTransformerLanguageModelProblem
def evaluate_in_case(data, decoded_model, state, context):
    problem = TinyTransformerLanguageModelProblem(data)
    # decoded_model/state由本Case模型Codec给出；context包含已授权backend。
    feedback = problem.evaluate(decoded_model, state, context)
    return feedback.objectives, feedback.constraints, feedback.metrics
```

输出与消费：Feedback的原始目标、约束与指标；交回共享评估链，偏好和接纳另行处理。

依赖与边界：统一框架栈；神经任务需所声明的Torch/JAX/TF能力，ARIMA路线可选statsmodels。

这是Problem叶接口示例，不能把未知模型直接传入；完整运行仍由正式Case负责。

---

## `problem.training_proxy` · MLBlackTrainingProxy

用途：Framework-neutral proxy for outer optimizers invoking mlblack inner training.

输入：数值DataView、已确认的内层trainer_spec、外层候选与资源上下文。

```python
from mlblack.problems.proxy import MLBlackTrainingProxy
def make_inner_task(data, trainer_spec, candidate, context):
    proxy = MLBlackTrainingProxy(data, base_trainer_spec=trainer_spec, max_steps=3)
    task = proxy.make_task(candidate, context)
    return task  # 由正式内层Case/共享runner消费，不把Task当作已执行结果
```

输出与消费：可传递TrainingTask；真实训练结果必须由正式inner Case交付。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `problem_bridge.ml_black_training` · MLBlackTrainingProxy

用途：Framework-neutral proxy for outer optimizers.

输入：数值DataView、已确认的内层trainer_spec、外层候选与资源上下文。

```python
from mlblack.problems.proxy import MLBlackTrainingProxy
def make_inner_task(data, trainer_spec, candidate, context):
    proxy = MLBlackTrainingProxy(data, base_trainer_spec=trainer_spec, max_steps=3)
    task = proxy.make_task(candidate, context)
    return task  # 由正式内层Case/共享runner消费，不把Task当作已执行结果
```

输出与消费：可传递TrainingTask；真实训练结果必须由正式inner Case交付。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `provider.torch_evaluation` · TorchEvaluationProvider

用途：Torch 评估 Provider：在 Project L0 grant 内执行 ML Problem 的 loss/autograd/device 语义，并持有版本化参数、梯度与 optimizer slot；优化方法仍由 nsgablack Adapter 选择。

输入：带backend loss语义的ML Problem及匹配representation。

```python
from mlblack.backends.torch_neural.evaluation_provider import TorchEvaluationProvider
from mlblack.core.provider_problem import ProviderBackedLearningProblem
def bind_evaluation(problem, representation):
    provider = TorchEvaluationProvider(problem, representation)
    wrapped = ProviderBackedLearningProblem.from_provider(problem, provider)
    return wrapped, provider
```

输出与消费：共享Gateway绑定的Provider facade；活参数/梯度/slot由Provider版本化持有。

依赖与边界：Torch与Project授权；不手工绕过Gateway调用状态转移。

---

## `provider.arimasarimax` · ARIMASARIMAXProvider

用途：Provider that fits ARIMA/SARIMAX specs through numpy or statsmodels.

输入：TimeSeriesDataView及Case求值上下文，预测3步；此fit应在Problem/Provider求值内部。

```python
from mlblack.models.time_series import ARIMASARIMAXProvider, ARIMASARIMAXSpec
def fit_forecast(data, context):
    provider = ARIMASARIMAXProvider(ARIMASARIMAXSpec(order=(1, 0, 0), include_exogenous=False))
    model = provider.fit(data, context=context)
    return model.forecast(data.y, horizon=3, context=context)
```

输出与消费：已拟合时序模型的预测，不新建Trainer控制循环。

依赖与边界：NumPy；选择statsmodels实现时需该可选包。

---

## `schema.scaffold_config` · ScaffoldConfig

用途：Top-level JSON-compatible scaffold contract.

输入：明确原始字段与目标的schema及内层训练定义。

```python
from mlblack.assembly.schema.spec import ScaffoldConfig
config = ScaffoldConfig(name="numeric_regression",
    schema={"features": ["x0", "x1"], "target": "y"},
    inner_training={"trainer": {"preset": "linear_point", "params": {"max_steps": 3}}})
payload = config.as_dict()
schema = config.schema_spec()
```

输出与消费：JSON兼容ScaffoldConfig和DatasetSchema；数据仍由Case pipeline解析。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `trainer.learning_solver` · LearningSolver

用途：复用 NSGABlack 的 Pool、Unit 和求解生命周期；fit/TrainerResult 投影 ML 结果，状态与正式 checkpoint 保留候选及最佳反馈身份。

输入：支持解析梯度的Problem、布局已知的ModelRepresentation、Project授权资源。

```python
from mlblack.integrations.nsgablack_control import LearningSolver
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
def build_solver(problem, representation, resource_context):
    adapter = build_optimization_adapter("gradient.sgd", learning_rate=0.05)
    return LearningSolver(problem=problem, representation=representation,
                          adapter=adapter, resource_context=resource_context)
```

输出与消费：由同一个ComposableSolver驱动的ML求解器；正式Case负责fit/run与发布。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `trainer.diagnostic_solver` · build_diagnostic_solver

用途：通过 NSGABlack FixedCandidateAdapter 运行一次 ML 诊断，不建立私有 Trainer 循环。

输入：只执行一次的诊断回调与Project授权。

```python
from mlblack.integrations.nsgablack_diagnostic import build_diagnostic_solver
def build_solver(resource_context):
    def audit_rows(context):
        return {"objective": 0.0, "metrics": {"rows_checked": 4}}
    return build_diagnostic_solver(audit_rows, name="rows", resource_context=resource_context)
```

输出与消费：固定候选的一次正式求值；原core.diagnostic错误import已迁移到integration实现。

依赖与边界：统一框架栈与NumPy；仅展示组件调用，不在此创建训练或资源循环。

---

## `backend.jax` · jax

用途：查看 jax 后端的聚合能力，并在装配 Problem/Provider 前核对需求。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('jax')
contract = backend.contract()
required = ('tensor.from_numpy',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('jax', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='jax')
assert selected_backend.contract().name == 'jax'
provided_operations = tuple(contract.provides)
method_signatures = dict(contract.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。contract.provides 是聚合后的能力名元组；contract.methods 是聚合后的签名描述表，值是字符串，不是可调用方法。两者不要求一一对应。 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods；不能只以方法表键判断能力。

选择规则：resolve_backend(required, preferred='jax') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：get_backend('jax') 取得注册的后端对象，不选择具体训练算法。真正计算由相应 tensor/losses/autograd 等能力对象执行；后端本身不创建 Project L0 授权。

依赖与验证：这里仅演示合同发现与装配前检查；实际 jax 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/registry.py、mlblack/backends/contracts.py。

---

## `backend_capability.jax.tensor` · jax.tensor

用途：把输入数组规范为本后端的张量，并提供设备表达与张量转移入口。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('jax')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'tensor')
required = ('tensor',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('jax', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='jax')
assert selected_backend.contract().name == 'jax'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='jax') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：JAX 张量规范化不等于完整 L0 设备放置桥接；当前 device/to_device 的具体行为应按 JaxTensorCapability 核对，不由 supports_gpu 或字符串设备名推导。

依赖与验证：这里仅演示合同发现与装配前检查；实际 jax 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/jax_neural/capabilities/tensor.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.jax.neural_lowering` · jax.neural_lowering

用途：将 NeuralGraphSpec 降为本后端模型，提供参数布局、初始化和导入能力。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('jax')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'neural_lowering')
required = ('neural.lowering',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('jax', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='jax')
assert selected_backend.contract().name == 'jax'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='jax') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：当前降层针对 MLP，产出提供 predict_from_values 的函数式 JAX 模型；不能据此声称已覆盖 Torch 的所有模型路线。

依赖与验证：这里仅演示合同发现与装配前检查；实际 jax 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/jax_neural/capabilities/neural_lowering.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.jax.losses` · jax.losses

用途：为 LearningProblem 提供本后端的任务损失与指标；它不拥有训练循环或结果选择。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('jax')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'losses')
required = ('loss.mse',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('jax', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='jax')
assert selected_backend.contract().name == 'jax'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='jax') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：当前是标量回归损失与回归指标，公开输出转成 Python/NumPy；需要可微内部对象的消费者不能直接把这些公开返回值当训练图。

依赖与验证：这里仅演示合同发现与装配前检查；实际 jax 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/jax_neural/capabilities/losses.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.jax.autograd` · jax.autograd

用途：提供本后端的梯度计算、模式或参数读取能力；实际梯度路径由 Problem/Provider 消费。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('jax')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'autograd')
required = ('autograd.functional.grad',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('jax', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='jax')
assert selected_backend.contract().name == 'jax'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='jax') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：JAX 使用函数式 grad/value_and_grad，没有 Torch 风格 backward() 合同；Provider 需要函数式梯度时应检查 autograd.functional.grad 等真实键。

依赖与验证：这里仅演示合同发现与装配前检查；实际 jax 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/jax_neural/capabilities/autograd.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.jax.optimizers` · jax.optimizers

用途：提供本后端的优化更新能力；优化器如何参与候选提出、送评和恢复仍由正式 Provider/Adapter 路径管理。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('jax')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'optimizers')
required = ('optimizer.sgd_step',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('jax', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='jax')
assert selected_backend.contract().name == 'jax'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='jax') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：这里只提供函数式 optimizer.sgd_step：sgd_step(values, gradients, learning_rate) 返回新参数数组；没有声明有状态优化器构造、step(optimizer) 或 optimizer.state。

依赖与验证：这里仅演示合同发现与装配前检查；实际 jax 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/jax_neural/capabilities/optimizers.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.jax.artifacts` · jax.artifacts

用途：为模型或参数提供描述、摘要和审计数据；生成这些数据不等于发布正式 Artifact 收据。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('jax')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'artifacts')
required = ('artifact.parameters.summary',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('jax', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='jax')
assert selected_backend.contract().name == 'jax'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='jax') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：函数式模型描述与参数摘要不携带已执行训练或已发布模型的证明；接入正式 Artifact 发布时仍走共享结果生命周期。

依赖与验证：这里仅演示合同发现与装配前检查；实际 jax 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/jax_neural/capabilities/artifacts.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend.numpy` · numpy

用途：查看 numpy 后端的聚合能力，并在装配 Problem/Provider 前核对需求。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('numpy')
contract = backend.contract()
required = ('tensor.from_numpy',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('numpy', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='numpy')
assert selected_backend.contract().name == 'numpy'
provided_operations = tuple(contract.provides)
method_signatures = dict(contract.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。contract.provides 是聚合后的能力名元组；contract.methods 是聚合后的签名描述表，值是字符串，不是可调用方法。两者不要求一一对应。 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods；不能只以方法表键判断能力。

选择规则：resolve_backend(required, preferred='numpy') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：get_backend('numpy') 取得注册的后端对象，不选择具体训练算法。真正计算由相应 tensor/losses/autograd 等能力对象执行；后端本身不创建 Project L0 授权。

依赖与验证：这里仅演示合同发现与装配前检查；实际 numpy 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/registry.py、mlblack/backends/contracts.py。

---

## `backend_capability.numpy.tensor` · numpy.tensor

用途：把输入数组规范为本后端的张量，并提供设备表达与张量转移入口。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('numpy')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'tensor')
required = ('tensor',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('numpy', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='numpy')
assert selected_backend.contract().name == 'numpy'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='numpy') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：NumPy 的 device 返回 cpu，to_device 返回输入；这不提供 GPU 传输或 autograd。实际数值转换调用 backend.tensor.float_tensor(value)，不是调用签名字符串。

依赖与验证：这里仅演示合同发现与装配前检查；实际 numpy 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/numpy_neural/capabilities/tensor.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.numpy.neural_lowering` · numpy.neural_lowering

用途：将 NeuralGraphSpec 降为本后端模型，提供参数布局、初始化和导入能力。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('numpy')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'neural_lowering')
required = ('neural.lowering',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('numpy', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='numpy')
assert selected_backend.contract().name == 'numpy'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='numpy') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：当前降层针对 MLP，产出 NumPy 点模型；不能从 neural.lowering 推断支持 Transformer/CNN/GNN。实际模型构造走 backend.decode_neural_graph(values, spec, ...)。

依赖与验证：这里仅演示合同发现与装配前检查；实际 numpy 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/numpy_neural/capabilities/neural_lowering.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.numpy.losses` · numpy.losses

用途：为 LearningProblem 提供本后端的任务损失与指标；它不拥有训练循环或结果选择。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('numpy')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'losses')
required = ('loss.mse',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('numpy', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='numpy')
assert selected_backend.contract().name == 'numpy'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='numpy') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：当前是 CPU 标量回归损失与回归指标，无反向图；不能因为有 loss.mse 就为 NumPy 选择需要 autograd.backward 的训练路线。

依赖与验证：这里仅演示合同发现与装配前检查；实际 numpy 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/numpy_neural/capabilities/losses.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.numpy.artifacts` · numpy.artifacts

用途：为模型或参数提供描述、摘要和审计数据；生成这些数据不等于发布正式 Artifact 收据。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('numpy')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'artifacts')
required = ('artifact.parameters.summary',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('numpy', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='numpy')
assert selected_backend.contract().name == 'numpy'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='numpy') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：parameter_layout_summary 与 describe_model 返回描述数据；描述字典没有替代模型 Artifact 的持久化、引用和权威发布收据。

依赖与验证：这里仅演示合同发现与装配前检查；实际 numpy 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/numpy_neural/capabilities/artifacts.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend.tensorflow` · tensorflow

用途：查看 tensorflow 后端的聚合能力，并在装配 Problem/Provider 前核对需求。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('tensorflow')
contract = backend.contract()
required = ('tensor.from_numpy',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('tensorflow', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='tensorflow')
assert selected_backend.contract().name == 'tensorflow'
provided_operations = tuple(contract.provides)
method_signatures = dict(contract.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。contract.provides 是聚合后的能力名元组；contract.methods 是聚合后的签名描述表，值是字符串，不是可调用方法。两者不要求一一对应。 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods；不能只以方法表键判断能力。

选择规则：resolve_backend(required, preferred='tensorflow') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：get_backend('tensorflow') 取得注册的后端对象，不选择具体训练算法。真正计算由相应 tensor/losses/autograd 等能力对象执行；后端本身不创建 Project L0 授权。

依赖与验证：这里仅演示合同发现与装配前检查；实际 tensorflow 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/registry.py、mlblack/backends/contracts.py。

---

## `backend_capability.tensorflow.tensor` · tensorflow.tensor

用途：把输入数组规范为本后端的张量，并提供设备表达与张量转移入口。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('tensorflow')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'tensor')
required = ('tensor',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('tensorflow', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='tensorflow')
assert selected_backend.contract().name == 'tensorflow'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='tensorflow') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：TensorFlow 张量转换和设备上下文仍消费 Project L0 授权；合同查询不会创建 GPU grant。

依赖与验证：这里仅演示合同发现与装配前检查；实际 tensorflow 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/tensorflow_neural/capabilities/tensor.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.tensorflow.neural_lowering` · tensorflow.neural_lowering

用途：将 NeuralGraphSpec 降为本后端模型，提供参数布局、初始化和导入能力。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('tensorflow')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'neural_lowering')
required = ('neural.lowering',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('tensorflow', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='tensorflow')
assert selected_backend.contract().name == 'tensorflow'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='tensorflow') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：当前降层针对 MLP，产出提供 predict_from_values 的 TensorFlow 函数式模型；不能由通用 neural.lowering 标识推断任意网络都可转换。

依赖与验证：这里仅演示合同发现与装配前检查；实际 tensorflow 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/tensorflow_neural/capabilities/neural_lowering.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.tensorflow.losses` · tensorflow.losses

用途：为 LearningProblem 提供本后端的任务损失与指标；它不拥有训练循环或结果选择。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('tensorflow')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'losses')
required = ('loss.mse',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('tensorflow', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='tensorflow')
assert selected_backend.contract().name == 'tensorflow'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='tensorflow') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：当前公开的回归损失返回 Python/NumPy 值；训练中的梯度计算应通过适配的 autograd 路径，不由这个返回形式猜测反向传播。

依赖与验证：这里仅演示合同发现与装配前检查；实际 tensorflow 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/tensorflow_neural/capabilities/losses.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.tensorflow.autograd` · tensorflow.autograd

用途：提供本后端的梯度计算、模式或参数读取能力；实际梯度路径由 Problem/Provider 消费。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('tensorflow')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'autograd')
required = ('autograd.functional.grad',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('tensorflow', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='tensorflow')
assert selected_backend.contract().name == 'tensorflow'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='tensorflow') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：TensorFlow 使用 GradientTape 的函数式梯度入口，没有 Torch 风格 backward() 合同；不要要求所有后端暴露同一训练对象。

依赖与验证：这里仅演示合同发现与装配前检查；实际 tensorflow 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/tensorflow_neural/capabilities/autograd.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.tensorflow.optimizers` · tensorflow.optimizers

用途：提供本后端的优化更新能力；优化器如何参与候选提出、送评和恢复仍由正式 Provider/Adapter 路径管理。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('tensorflow')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'optimizers')
required = ('optimizer.sgd_step',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('tensorflow', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='tensorflow')
assert selected_backend.contract().name == 'tensorflow'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='tensorflow') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：这里只提供函数式 optimizer.sgd_step，输入参数、梯度和学习率并返回新数组；不能把它当 Torch 优化器对象，也不能假定存在动量 slot 恢复。

依赖与验证：这里仅演示合同发现与装配前检查；实际 tensorflow 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/tensorflow_neural/capabilities/optimizers.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.tensorflow.artifacts` · tensorflow.artifacts

用途：为模型或参数提供描述、摘要和审计数据；生成这些数据不等于发布正式 Artifact 收据。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('tensorflow')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'artifacts')
required = ('artifact.parameters.summary',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('tensorflow', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='tensorflow')
assert selected_backend.contract().name == 'tensorflow'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='tensorflow') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：参数摘要与模型描述是发布输入，不是成功结果；必须由正式 Case 的 Artifact/结果协议决定何时成为权威引用。

依赖与验证：这里仅演示合同发现与装配前检查；实际 tensorflow 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/tensorflow_neural/capabilities/artifacts.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend.torch` · torch

用途：查看 torch 后端的聚合能力，并在装配 Problem/Provider 前核对需求。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('torch')
contract = backend.contract()
required = ('tensor.from_numpy',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('torch', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='torch')
assert selected_backend.contract().name == 'torch'
provided_operations = tuple(contract.provides)
method_signatures = dict(contract.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。contract.provides 是聚合后的能力名元组；contract.methods 是聚合后的签名描述表，值是字符串，不是可调用方法。两者不要求一一对应。 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods；不能只以方法表键判断能力。

选择规则：resolve_backend(required, preferred='torch') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：get_backend('torch') 取得注册的后端对象，不选择具体训练算法。真正计算由相应 tensor/losses/autograd 等能力对象执行；后端本身不创建 Project L0 授权。

依赖与验证：这里仅演示合同发现与装配前检查；实际 torch 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/registry.py、mlblack/backends/contracts.py。

---

## `backend_capability.torch.tensor` · torch.tensor

用途：把输入数组规范为本后端的张量，并提供设备表达与张量转移入口。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('torch')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'tensor')
required = ('tensor',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('torch', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='torch')
assert selected_backend.contract().name == 'torch'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='torch') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：类别标签、token ids、浮点张量各有真实入口：backend.tensor.class_labels、token_ids、float_tensor；它们不是可以互换的 dtype 说明。设备来自授权上下文。

依赖与验证：这里仅演示合同发现与装配前检查；实际 torch 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/torch_neural/capabilities/tensor.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.torch.neural_lowering` · torch.neural_lowering

用途：将 NeuralGraphSpec 降为本后端模型，提供参数布局、初始化和导入能力。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('torch')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'neural_lowering')
required = ('neural.lowering',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('torch', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='torch')
assert selected_backend.contract().name == 'torch'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='torch') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：Torch 合同分别声明 MLP、Transformer、CNN、GNN、temporal 路线。需要某路线时检查其精确能力键，不以 neural.lowering 一个宽键代替。

依赖与验证：这里仅演示合同发现与装配前检查；实际 torch 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/torch_neural/capabilities/neural_lowering.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.torch.autograd` · torch.autograd

用途：提供本后端的梯度计算、模式或参数读取能力；实际梯度路径由 Problem/Provider 消费。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('torch')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'autograd')
required = ('autograd.mode.train',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('torch', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='torch')
assert selected_backend.contract().name == 'torch'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='torch') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：Torch 的 backward、no_grad、train/eval 与参数导出各有独立声明；autograd.functional.grad 并未因此自动成立。需要后者的消费者应让合同匹配失败。

依赖与验证：这里仅演示合同发现与装配前检查；实际 torch 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/torch_neural/capabilities/autograd.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.torch.optimizers` · torch.optimizers

用途：提供本后端的优化更新能力；优化器如何参与候选提出、送评和恢复仍由正式 Provider/Adapter 路径管理。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('torch')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'optimizers')
required = ('optimizer.build',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('torch', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='torch')
assert selected_backend.contract().name == 'torch'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='torch') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：特别注意：optimizer.state 出现在 provides 中，却没有 methods["optimizer.state"]。应使用 backend.contract().supports("optimizer.state") 或 missing(...) 判断能力；只检查 methods 会误报。真实方法是 backend.optimizers.build_optimizer/step/zero_grad，methods 中的三个值只是签名文本。

依赖与验证：这里仅演示合同发现与装配前检查；实际 torch 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/torch_neural/capabilities/optimizers.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.torch.losses` · torch.losses

用途：为 LearningProblem 提供本后端的任务损失与指标；它不拥有训练循环或结果选择。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('torch')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'losses')
required = ('loss.cross_entropy',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('torch', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='torch')
assert selected_backend.contract().name == 'torch'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='torch') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：交叉熵、下一 token、DPO、triplet、Gaussian NLL 是不同方法；Problem 必须声明实际需要的精确键，并按对应模型输出/Head/标签形状调用。不能因为存在 losses 就任选损失。

依赖与验证：这里仅演示合同发现与装配前检查；实际 torch 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/torch_neural/capabilities/losses.py，以及 mlblack/backends/registry.py、contracts.py。

---

## `backend_capability.torch.artifacts` · torch.artifacts

用途：为模型或参数提供描述、摘要和审计数据；生成这些数据不等于发布正式 Artifact 收据。

输入：在本 Case 的 Problem/Provider 工厂确定 required 所需能力标识，再按该后端查询；这里不分配设备、创建 session 或启动训练。

```python
from mlblack.backends.registry import (
    get_backend, explain_backend_requirements, resolve_backend,
)

backend = get_backend('torch')
contract = backend.contract()
capability = next(c for c in contract.capabilities if c.capability == 'artifacts')
required = ('artifact.neural_graph.audit',)
missing = contract.missing(required)
assert not missing, missing
report = explain_backend_requirements('torch', required)
assert report["ok"] and not report["missing"]
selected_backend = resolve_backend(required, preferred='torch')
assert selected_backend.contract().name == 'torch'
provided_operations = tuple(capability.provides)
method_signatures = dict(capability.methods)
assert all(isinstance(signature, str) for signature in method_signatures.values())
```

输出与消费：report["ok"] 与 missing 说明合同是否匹配；selected_backend 是后端对象；provided_operations 是声明键，method_signatures 是可供人和装配检查读取的签名文本。实际执行调用后端/能力对象的公开方法，不调用 method_signatures 中的字符串。capability.provides 是该组件声明的能力名元组；capability.methods 是方法签名描述表，值是字符串，不是可调用对象。两者不要求一一对应。聚合后的 contract.supports(requirement) 与 contract.missing(requirements) 同时检查 provides 和 methods。

选择规则：resolve_backend(required, preferred='torch') 明确选定本后端；若缺能力则抛 ValueError，不尝试次优后端。只有省略 preferred 时才按注册名排序遍历后端，返回第一个合同匹配者；这种选择仍不证明可选计算包已安装、设备可用或该任务能运行。换后端须重新核对模型路线、梯度形式和任务需要，不能只换名称。

使用边界：神经图审计和参数摘要使用不同入口。artifact.torch_model.describe 属于 provides 声明，并不意味着 methods 必须有同名键；需要可调用实现时继续核对组件公开方法，不能执行签名字符串。

依赖与验证：这里仅演示合同发现与装配前检查；实际 torch 计算须具备相应依赖并消费 Project L0 授权。支持声明、签名文本和匹配成功均不是 GPU、梯度、模型或 checkpoint 已执行的记录。本节按源码核对，未在此执行计算或训练。

源码：mlblack/backends/torch_neural/capabilities/artifacts.py，以及 mlblack/backends/registry.py、contracts.py。

---
