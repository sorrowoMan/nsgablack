# Artifact类型的真实接线：载荷、描述与发布不是同一件事

本页只读源码和静态片段；没有执行拟合、算法、Project、模型加载、数据库或API。Artifact值类型不会自动提供算法、序列化器或运行授权。两套正式Case在原完整配方上替换明确的Problem hook，依旧通过共享Case finalization交付；不调用本地ArtifactBundle.save来冒充发布。

## core.artifact.estimator · 给可恢复岭回归蓝图添加已拟合状态描述

**什么时候用：** 外部估计器已经在Problem.prepare中拟合，希望同时交付可推断的有限系数和估计器状态摘要。EstimatorStateArtifact包含model载荷与额外estimator_state；它不是把任意Python估计器自动变成通用可恢复模型的工具。

**先准备什么：** 使用《ML_CLASSICAL_ESTIMATOR_APPLICATIONS_CN.md》的 `classical.estimator.ridge` 与 `classical.estimator.run` 两节完整配方：独立catalog_codec_demo副本、NumPy岭估计器、单坐标ridge超参数、16训练/8验证、Gaussian、完整builder与正式Project结果入口。原配方已经保存三系数反馈证据，并提供不重新fit的restore_model_for_evaluation。

**放在哪：** 原配方的problem/__init__.py完整内容先保存为 `problem/ridge_base.py`，保留其中PortableRidgeProblem及原相对导入。再用下面文件完整替换 `problem/__init__.py`和config.py。原数据、factory、Adapter、builder和run_classical_and_report.py均不改；builder依然从.problem导入build_problem，因此新类是真实消费者。

**接入步骤：** 只替换已拟合模型的Artifact构造，继承原评价/只读恢复规则。先调用原hook得到同一模型的JSON系数蓝图，再由正式Provider消费typed边界。

```python
# cases/linear_point/config.py
INCLUDE_STATE_SUMMARY = True
```

```python
# cases/linear_point/problem/__init__.py
from mlblack.core.artifacts import EstimatorStateArtifact
from mlblack.models import FittedEstimatorModel
from .ridge_base import PortableRidgeProblem
from ..config import INCLUDE_STATE_SUMMARY

class StateDescribedRidgeProblem(PortableRidgeProblem):
    def build_model_artifact(self, model, context):
        if not isinstance(model, FittedEstimatorModel):
            raise TypeError("publish only the evaluated fitted ridge")
        blueprint = super().build_model_artifact(model, context)
        return EstimatorStateArtifact(name="portable_ridge", model=blueprint,
            family=model.family, head="regression", artifact_type="case_ridge_state",
            representation={"route": model.route, "params": dict(model.params)},
            estimator_state=(model.fitted_state_summary() if INCLUDE_STATE_SUMMARY
                             else {"fitted": True, "n_features": 2}),
            metadata={"payload_kind": "coefficients_json", "restore_owner": "PortableRidgeProblem"})

def build_problem(data):
    return StateDescribedRidgeProblem(data, use_valid_objective=True, complexity_weight=0.)
```

EstimatorStateArtifact.describe增加estimator_state；model中保存的是原有限三系数蓝图，进入正式原生JSON发布。`fitted_state_summary()`仅作摘要：不替代coef证据，不把它写回原始反馈，也不擅自将第三方活对象塞入context。EstimatorSpecModel只有拟合配置，不可作为已拟合模型发布。

**怎样判断接对：** 本次classical.json仍是一个ridge搜索坐标、`[valid.mse,0]`，loss仍训练MSE；best_model_ref元数据semantic_artifact中有artifact_type=case_ridge_state、route/params及estimator_state，引用载荷为ridge/feature_names/coefficients。预测能力来自真实系数和原RidgeEstimator，不来自type标签或摘要。formal结果模型引用非空且Case成功才说明交付，不以本地文件名作收据。

**运行入口：** 在该副本根先 `python run_project.py --check --build-check`，再只执行一次 `python run_classical_and_report.py`。沿用原Project L0。没有新训练循环，也没有运行过本章变体。

### 变体一：保留摘要类型，收窄可公开的训练元数据

**目的：** 发布系数与必要布局时不额外携带估计器详细摘要。**改在哪里：** config.py完整替换为：

```python
INCLUDE_STATE_SUMMARY = False
```

**行为变化：** 模型载荷及原始反馈完全相同，摘要更少。**限制：** 不得把摘要减为“checkpoint”并声称可以恢复任意估计器；本配方的只读恢复仍消费原反馈的case_ridge_coefficients。

## core.artifact.integrated · 给具名输入的组合模型交付明确typed蓝图

**什么时候用：** 要交付两个真实预测组件及其I/O和权重规则，明确它们是一个IntegratedPredictionModel的描述，而不是把若干任意Artifact路径混称模型融合。

**先准备什么：** 使用《ML_MODEL_COMPOSITION_APPLICATIONS_CN.md》的 `composition.shared_case` 与 `mlblack.model.integrated_prediction` 完整配方：第三份独立Project、两列组件权重候选、两个固定线性模型、40训练/16验证、具名trend_rows/weather_rows输入、Gaussian和正式Project报告。基础组件固定，不声称在本Case训练过它们。

**放在哪：** 将原配方problem/__init__.py完整内容先保存为 `problem/integration_base.py`，然后用下列文件替换problem/__init__.py。继承IntegrationProblem真实evaluate，不修改PredictionIOContract/IntegrationComponent；builder原来导入的build_problem会指向这个新类。

**接入步骤：** 原hook生成包含components/integration/io_contract的JSON蓝图；新hook把同一蓝图放进IntegratedModelArtifact，真实Provider剥离载荷并保存typed描述。类型不同不改变权重含义。

```python
# cases/linear_point/problem/__init__.py
from mlblack.core.artifacts import IntegratedModelArtifact
from .integration_base import IntegrationProblem

class TypedIntegrationProblem(IntegrationProblem):
    def build_model_artifact(self, model, context):
        blueprint = super().build_model_artifact(model, context)
        return IntegratedModelArtifact(name="weighted_linear_components", model=blueprint,
            family="integrated_prediction", head="point",
            representation={"parameter_count": 2, "order": ["trend", "correction"]},
            metadata={"input_keys": ["trend_rows", "weather_rows"],
                      "integration_kind": model.integration.kind})

def build_problem(data):
    return TypedIntegrationProblem(data)
```

该类的默认artifact_type=integrated_model，所有额外语义在明示的model/representation/metadata中。它没有通用自动反序列化IntegratedPredictionModel的方法；本例的两个LinearPointModel可用各自原生schema重建，I/O/组合规则也必须匹配，不能忽略blueprint中的具名输入。

**怎样判断接对：** 本次composition.json仍只有train.mse目标，valid与trend/correction各自MSE只观测；typed元数据和载荷的integration_kind必须一致。best_model_ref应指向同一已评估权重的两个模型蓝图，而不是之后生成的未评估权重。正式Provider/事务没有因返回typed值而跳过验证。

**运行入口：** 依原完整配方的 `run_composition_and_report.py` 正式执行一次Project，检查新run_id/Case状态与模型引用。本章仅提供静态用法，未训练或加载模型。

### 变体一：权重由additive变为mean，Artifact必须随规则变化

**目的：** 比较加权和与归一混合。**改在哪里：** 依原配方完整替换config.py：

```python
KIND = "mean"
```

**行为变化：** 同一两个权重经绝对权重和归一，蓝图integration与metadata一起记录mean；Artifact标签仍integrated_model。**限制：** 不能只改Artifact metadata却保留additive预测，旧候选/恢复的integration含义不能混用。

## core.artifact.legacy_tags · 三个仍有效的值类，没有自动接通所有模型族

**什么时候用：** 搜到TreeEnsembleArtifact、SklearnMLPArtifact、XGBoostArtifact，想判断“返回这个类”是否已经实现了训练、原生加载和权威发布。本节是准确接线边界，标为迁移说明，不作为三个已运行/完整装配的算法用法；这三个值类本身仍存在，并未宣称删除或弃用。

**先准备什么：** 核对core/artifacts.py、core/artifact_provider.py、problems/supervised.py及presets/tree.py、presets/neural.py。三类仅在TypedModelArtifact上改默认artifact_type。ArtifactBuilder的内部分类分支按model类型/route名称选择它们；那是本地ArtifactBundle构造，不是CaseRuntimeArtifactProvider每次自动执行的分类器。

**放在哪：** 训练和拟合仍由具体Representation/Problem/Provider装配，用户不把这些Artifact类放进Adapter或当bias。正式默认SupervisedEstimatorFitRegressionProblem.build_model_artifact返回的是EstimatorStateArtifact，model保留FittedEstimatorModel、estimator_state保留摘要；不保证返回这三个更专门的类。

**接入步骤：** 当前源码障碍必须分别理解。tree/xgboost具有fitted_state_summary时，ArtifactBuilder本身也会优先返回带相应artifact_type的EstimatorStateArtifact；MLP与Integrated分类只有真正经过该Builder才发生。正式Provider不会因为Catalog页面显示SklearnMLPArtifact就调用它。Provider剥离FittedEstimatorModel后将estimator送序列化器：暴露save_model的实际模型可走原生文件，其它任意Python估计器回退unsafe pickle，默认Project未授权则拒绝。仅把外层类名换成SklearnMLPArtifact/TreeEnsembleArtifact不会让pickle变安全，也不会补齐只读restore_model_for_evaluation。默认拟合Problem未覆盖该恢复方法，不能为了还原最佳模型再次fit。

可用替代是上节完整NumPy岭估计器配方：显式保存系数证据、只读恢复、JSON模型蓝图、正式发布。Torch神经模型用已有《ML_NEURAL_TABULAR_APPLICATIONS_CN.md》的正式NeuralGraph/Provider/NPZ配方；它不是SklearnMLPArtifact的别名。确实需要sklearn树/MLP或XGBoost时，应按选定模型版本实现受支持的模型状态导出/导入和显式Problem恢复，再从Problem-owned hook交付对应typed Artifact；当前Catalog不能用一个通用“训练模型→tag”片段声称这些消费者都已补完。本页不要求启用不受控pickle或安装新依赖。

**怎样判断接对：** 先核对实际hook返回的类、model载荷类型及实际序列化器，再核对正式Case的模型引用和发布收据；metadata中的artifact_type字符串既不证明拟合成功，也不证明能加载预测。ArtifactBuilder/Bundle.save的本地.pkl/.json与Run权威发布分开统计。未来补齐专门模型路线，应增加真正完整Case和恢复/发布验收，本项才能从迁移说明变成可直接装配用法。

**运行入口：** 本节没有捏造可执行的通用树/MLP/XGBoost Case，也没有运行命令；需要现成可闭合路线时使用本书明确引用的完整ridge或Torch Project入口。

### 变体一：只需要模型摘要时，不声称能够推断

**目的：** 先检查模型描述与类型路由。**改在哪里：** 使用《ARTIFACT_BUNDLE_APPLICATION_CN.md》的正式finalized后Bundle观察器，只保存describe/RunReport。**行为变化：** 产生可查看的本地摘要，不发布新模型、不建立恢复能力。**限制：** 摘要不能替代模型参数或正式引用，也不能据此把本节三项计为已补齐独立算法。
