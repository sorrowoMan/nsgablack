# 04. mlblack 学习流、装配与 Artifact 对齐

覆盖路径：

- `schema/*`
- `numericizer/*`
- `pipeline/*`
- `config/assembly.py`, `config/registry.py`, `config/defaults.py`
- `core/common/base_trainer.py`
- `core/trainers/*`, `core/*/trainer_family.py`
- `core/artifacts/*`
- `core/orchestration/*`, `workflow/*`
- `plugins/*`

## 1. Schema 层

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `DatasetSchema` | dataset schema / data contract | 定义 feature/target/id/strict。 | 训练流从语义契约开始，而不是直接 ndarray。 |
| `FeatureSpec` | feature schema / column spec | 定义 dtype、encoder、modality、constraints。 | 特征语义进入 numericizer 和 pipeline。 |
| `TargetSpec` | target schema / label spec | 定义目标字段。 | 支持多 target 和 output head 扩展。 |
| `parse_row/parse_rows` | schema validation / row parser | 数据解析与验证。 | 数据质量成为正式框架边界。 |
| `view_builder` | target/feature view builder | 构建训练视图。 | 支持 ModelSpec 子空间训练。 |

## 2. Numericizer 层

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `BaseNumericizer` | feature encoder interface | 语义到数值转换接口。 | 明确 schema 与模型数值输入的边界。 |
| `DefaultNumericizer` | default tabular encoder | 默认数值化器。 | 支持 modality encoder 和 target codec。 |
| `NumericizationPlan` | encoding plan / feature mapping manifest | 记录如何数值化。 | 让特征转换可追踪、可复现。 |
| `TargetCodec` | label/target encoder | target 编码。 | 将分类、二元、数值目标统一为可训练形式。 |
| `SEMANTIC_NUMERICIZER_KEYS` | config field boundary | numericizer 专属配置键。 | 防止 numericizer 参数误塞 trainer_params。 |

## 3. Pipeline 层

| 代码叫法 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `BasePipeline` | preprocessing pipeline | 特征变换接口。 |
| `IdentityPipeline` | identity transform | 空变换。 |
| `ZScorePipeline` | standardization / z-score normalization | 标准化。 |
| `FeatureSpaceBuilder` | feature construction / representation builder | 构造特征空间。 |
| `learnable_conv.py` | learnable convolution component / feature extractor | 可学习卷积组件。 |
| `feature_space.py` | feature space object | 特征空间对象。 |

差异点：pipeline 不是简单预处理脚本，而是 trainer assembly 的一部分，可被 catalog、resource context、component override 管理。

## 4. 装配配置

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `MLBlackConfig` | component registry container | 管 trainers/pipelines/biases/numericizers。 | 框架能力从注册表创建，不是散落 import。 |
| `ComponentRegistry` | factory registry / plugin registry | key -> factory + metadata。 | registry 也服务 catalog/UI。 |
| `TrainerAssemblySpec` | estimator assembly spec | trainer、pipeline、bias、resource、component overrides。 | 不只指定模型名，还指定训练组件装配。 |
| `FlowAssemblySpec` | training workflow assembly spec | numericizer、trainer、capabilities、resource。 | 将一条训练流的各层声明化。 |
| `ExecutionSpec` | execution backend spec | backend、workers、GPU strategy。 | L0 资源上下文有正式配置入口。 |
| `component_overrides` | component-level override / targeted config patch | 对 pipeline/trainer/bias/capability 局部覆盖。 | 支持外层搜索修改内层组件，不破坏整体 spec。 |
| `flow_assembly_with_resource_context` | resource context propagation | 将资源上下文注入训练装配。 | 支持 nsgablack 外层资源约束传递到 mlblack。 |

## 5. Trainer 基类与 family

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `BaseSurrogateTrainer.fit(data)` | estimator.fit / learner fit | 训练主入口。 | 兼容旧式 data-only trainer。 |
| `fit_task(task, init)` | structured training task / fit result protocol | 结构化训练入口。 | 输出 `FitResult`，包含 artifact、state、report、lineage。 |
| `capabilities()` | estimator capability metadata | 声明 trainer 行为。 | 支持 registry/UI/兼容性检查。 |
| `execution_resource_request()` | resource demand declaration | 声明单次训练资源需求。 | 资源调度不必写 trainer-specific if/else。 |
| `set_resource_context()` | resource grant injection | 接收外部资源上下文。 | 与 shared Project L0 资源边界对齐。 |
| `TrainingInit` | warm-start/resume init policy | 训练初始化策略。 | 支持 resume、warm start、compatibility 检查。 |
| `TrainingLineage` | training lineage record | 记录训练来源。 | artifact 可追溯到 task、parent artifact/state。 |
| `TaskSignature` | training task fingerprint | 训练任务指纹。 | 用于 resume drift 和复现。 |

## 6. Trainer family 对齐

| 代码路径 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `core/linear/trainer_family.py` | linear model family | 线性/岭回归等。 |
| `core/tree/trainer_family.py` | tree model family | 单树或树式模型。 |
| `core/tree_boosting/trainer_family.py` | boosting family | XGBoost/boosting 族。 |
| `core/neural/trainer_family.py` | neural network family | MLP/torch/sklearn neural。 |
| `core/symbolic/trainer_family.py` | symbolic regression family | 符号建模。 |
| `core/trainers/random_forest_trainer.py` | random forest | bagging tree ensemble。 |
| `core/trainers/extra_trees_trainer.py` | extremely randomized trees | 随机树集成。 |
| `core/trainers/bagging_trainer.py` | bagging ensemble | bootstrap aggregation。 |
| `core/trainers/adaboost_trainer.py` | boosting ensemble | boosting。 |
| `core/trainers/torch_trainer.py` | PyTorch trainer | 神经网络训练器。 |
| `core/trainers/xgboost_trainer.py` | gradient boosted trees | XGBoost 训练器。 |

## 7. Artifact 层

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `SurrogateArtifact` | fitted model artifact | 训练后的可预测对象。 | artifact 是主产物，不和 report/state 混淆。 |
| `LinearSurrogateArtifact` | linear fitted estimator | 线性模型产物。 | 带 uncertainty、validity、pipeline state。 |
| `TorchMLPSurrogateArtifact` | neural model artifact | 神经网络产物。 | 持久化模型参数和预测接口。 |
| `XGBoostSurrogateArtifact` | tree boosting artifact | XGBoost 产物。 | 与其他 artifact 统一接口。 |
| `SymbolicSurrogateArtifact` | symbolic expression artifact | 符号表达式产物。 | 支持表达式、metadata、basis 信息。 |
| `uncertainty(X)` | predictive uncertainty | 预测不确定性。 | 代理模型可服务 outer solver 风险控制。 |
| `validity(X)` | OOD validity / applicability domain | 输入有效性评分。 | 有利于识别代理外推风险。 |
| `save/load` | artifact persistence | 产物持久化。 | 与 run surface / artifact record 对齐。 |

## 8. Orchestration 与 Capability

| 代码叫法 | 社区常用叫法 | 机制含义 | 你的差异点 |
| --- | --- | --- | --- |
| `FlowCapability` | callback / lifecycle capability | 训练流能力基类。 | 插件式增强训练流，不改 trainer 主体。 |
| `CapabilityManager` | callback dispatcher | 管理 capabilities。 | 能输出 capability report。 |
| `LifecycleRuntime` | lifecycle engine | 事件分发和报告。 | 支持 flow/stage 统一生命周期。 |
| `ExperimentOrchestrator` | staged experiment runner | 多 stage 实验编排。 | 每个 stage 产出 payload，并形成 lifecycle report。 |
| `HookBus` | hook dispatcher | hook 总线。 | 兼容 runtime/capability/hook。 |
| `ExperimentLifecycleReport` | lifecycle audit report | 生命周期审计报告。 | 把能力、事件、状态和 stage 汇总。 |

## 9. Plugin 层

| 代码路径 | 社区常用叫法 | 机制含义 |
| --- | --- | --- |
| `runtime_resource_plugin.py` | resource audit plugin | 资源上下文审计。 |
| `trainer_state_checkpoint_plugin.py` | checkpoint plugin | trainer state checkpoint。 |
| `reproducibility_plugin.py` | reproducibility plugin | 复现信息记录。 |
| `report_writer_plugin.py` | report writer plugin | 报告输出。 |
| `report_writer.py` | report renderer / writer | 报告写入实现。 |

## 10. 这一层的核心价值

| 传统写法 | 你的写法 |
| --- | --- |
| 直接把 CSV 变 ndarray 喂模型。 | schema -> numericizer -> pipeline -> trainer。 |
| trainer.fit 返回一个模型对象。 | fit_task 返回 artifact/state/report/lineage。 |
| 资源参数散落在 trainer 参数里。 | ResourceContext/ExecutionSpec 统一注入。 |
| 回调、报告、checkpoint 写在训练循环里。 | FlowCapability 和 plugins 管副作用。 |
