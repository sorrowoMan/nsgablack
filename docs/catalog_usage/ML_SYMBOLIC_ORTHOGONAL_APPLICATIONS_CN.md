# 正交特征与模型条件目标：两个不同的准备步骤

两例各复制完整 `mlblack/examples/cases/catalog_codec_demo/`，保留原 Project/default单Case、L0及规范运行入口；都只用当前三仓和NumPy。本书没有执行数据拟合、模型、搜索或外部请求；源码中的fit是教程使用者运行时的数据准备，不是本轮执行证据。

## orthogonal.shared_report · 两例共用的正式结果读取

两例分别替换 `cases/linear_point/` 的指定文件，原pipeline包仍导出build_pipeline。在Project副本根新增完整 `run_orthogonal_and_report.py`：

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
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None or value.best_model_ref is None:
        raise ValueError("expected evaluated feedback and published model")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "metrics": dict(value.best_feedback.metrics), "signals": dict(value.best_feedback.signals),
        "model_ref": value.best_model_ref.as_dict()}
    path = root / "results" / "orthogonal.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

先 `python run_project.py --check --build-check`，再 `python run_orthogonal_and_report.py`，后者只调用一次正式Project并读取TrainerResult；不用第二个训练循环。检查新run_id/Case状态；旧JSON、构造成功或本页静态核对不能替代运行收据。JSON蓝图不等于已经提供通用模型加载器，正式model_ref和观察副本分开核对。

## mlblack.preset.orthogonal_logistic_classification · 训练集拟合特征基，再搜索分类参数

**什么时候用：** 两个原始特征的平方和交互有意义，希望先在训练数据上构造正交坐标，再搜索二分类logit，而不是把新基当作Adapter Unit或用验证样本重做SVD。

**先准备什么：** 第一份Project副本和共用报告入口。40训练/16验证；原始维度2，展开raw2+square2+interaction1共5列。最多保留3个主成分，不声称一定保留99.9%能量。

**放在哪：** 替换Case config.py、pipeline/main.py、build_solver.py；新增 `runtime/model_format.py`。旧problem/adapter目录可以保留，但本builder使用preset自身正式工厂，不调用旧工厂。

**接入步骤：** config.py：

```python
MAX_COMPONENTS = 3
```

pipeline/main.py：

```python
import numpy as np
from mlblack.pipeline import NumericDataView

def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (40, 2)), rng.uniform(-1., 1., (16, 2))
    def labels(a):
        return (a[:, 0]**2 + .7*a[:, 0]*a[:, 1] - .35 > 0.).astype(int)
    return NumericDataView(X_train=X, y_train=labels(X),
        X_valid=V, y_valid=labels(V), feature_names=("x0", "x1"))
```

runtime/model_format.py完整内容：

```python
import json
from pathlib import Path
from blackbase.resources import ArtifactSerializer
from mlblack.models import BinaryLogisticProbabilityModel, OrthogonalLinearPointModel

def dump_orthogonal_classifier(model, path):
    if not isinstance(model, BinaryLogisticProbabilityModel):
        raise TypeError("expected binary probability model")
    if not isinstance(model.logit_model, OrthogonalLinearPointModel):
        raise TypeError("expected orthogonal linear logit")
    payload = {"schema": "case.orthogonal_binary/v1", "classes": list(model.classes_),
        "temperature": model.temperature, "threshold": model.threshold,
        "logit": model.logit_model.as_dict()}
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")

def select_serializer(model):
    return ArtifactSerializer(name="case_orthogonal_binary_json", extension=".json",
        media_type="application/json", dump=dump_orthogonal_classifier)
```

build_solver.py完整内容：

```python
from mlblack.presets import build_orthogonal_logistic_classification_trainer
from mlblack.core.artifact_provider import CaseRuntimeArtifactProvider
from .pipeline.main import build_pipeline
from .runtime.model_format import select_serializer
from .config import MAX_COMPONENTS

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit factories")
    solver = build_orthogonal_logistic_classification_trainer(build_pipeline(),
        classes=(0, 1), objective_metrics=("log_loss",), max_components=MAX_COMPONENTS,
        energy_threshold=.999, population_size=8, mutation_scale=.25,
        run_name="orthogonal_classifier")
    if resource_context is not None:
        solver.set_resource_context(resource_context)
    solver.set_artifact_provider(CaseRuntimeArtifactProvider(serializer_selector=select_serializer))
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(8)
    return solver
```

preset实际调用OrthogonalPointLinearRepresentation.from_data(data.X_train)：OrthogonalFeatureMap扩展训练列、中心化后SVD，保存mean/components；同一映射处理验证数据。OrthogonalLinearPointCodec把[截距,q权重...]解码成OrthogonalLinearPointModel，BinaryLogisticHead再包概率。representation.orthogonal_linear与orthogonal_point_linear是同类目录别名，不需要装两套。

特征基先按energy_threshold选秩，再被max_components裁小；最终selected_energy才是真实保留量。坐标为中心化展开特征乘components.T，不是白化，也不承诺验证样本列互不相关。候选维度=1+实际output_dim，不应固定猜成原始维度+1。

此preset没有开放resource_context或Problem替换参数；本例通过已有set_resource_context在运行前接收Project授权。默认分类Problem没有安全组合模型导出hook，所以显式通过正式ArtifactProvider/ArtifactSerializer把原生logit和特征基写成JSON，不能省略它再假定活概率包装器可自动传输。Serializer不是另一个发布事务，仍由正式finalization发布。

**怎样判断接对：** orthogonal.json单项目标等于valid.log_loss，因为preset的Problem默认use_valid_objective=True；train/valid指标各保留，不能把验证当完全没参与选择的测试集。模型JSON内logit.feature_map保存训练mean/components、expanded names、selected_energy，与weights维度相符。无梯度分类走Gaussian，Head.threshold不改变分类Problem对predict_proba的argmax。最终比较只有log_loss一项，避免默认多指标的隐式聚合歧义。

**运行入口：** 按共用报告节的两条正式Project命令，核对模型引用和本次run_id；有效后端/授权以运行审计为准，preset不发放L0。

### 变体一：保留完整五维展开空间

**目的：** 对比降维与保留全部展开方向。

**改在哪里：** config.py完整替换为：

```python
MAX_COMPONENTS = 5
```

**行为变化：** 上限从3到5，但energy_threshold仍可能先截断，实际秩以Artifact为准。**限制：** 不是始终六参数；不能恢复旧基的checkpoint，推理也不能重新对待测数据fit。更多分量不保证验证效果更好，未使用独立最终测试集。

## mlblack.pipeline.model_conditioned_target · 固定参考模型定义残差目标

**什么时候用：** 已有一个参考预测，下一阶段只学习剩余误差。目标变换是数据准备，不是特殊Trainer；参考模型是本例给定系数，不声称从本数据训练过。

**先准备什么：** 第二份Project副本与共用报告入口；32训练/12验证，两原始特征。参考函数1+2*x0，真实目标另加.5*x1；标签和参考预测都固定。

**放在哪：** 完整替换Case config、pipeline/main、problem、build_solver；本builder自行装配Gaussian，因此不调用旧adapter工厂。

**接入步骤：** config.py：

```python
APPEND_PREDICTION = False
```

pipeline/main.py：

```python
import numpy as np
from mlblack.models import LinearPointModel
from mlblack.pipeline import NumericDataView
from mlblack.pipeline.model_conditioning import (
    ModelConditionedTargetComponent, ModelConditionedTargetBuilder, ModelConditionedTargetConfig)
from ..config import APPEND_PREDICTION

def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (32, 2)), rng.uniform(-1., 1., (12, 2))
    reference = LinearPointModel(intercept=1., weights=np.array([2., 0.]))
    def target(a):
        return reference.predict(a) + .5*a[:, 1]
    raw = NumericDataView(X_train=X, y_train=target(X), X_valid=V, y_valid=target(V),
        feature_names=("x0", "x1"), metadata={"reference_blueprint": reference.as_dict()})
    component_type = ModelConditionedTargetBuilder if APPEND_PREDICTION else ModelConditionedTargetComponent
    component = component_type(reference_model=reference,
        config=ModelConditionedTargetConfig(mode="residual", reference_name="base",
            append_prediction_feature=APPEND_PREDICTION, prediction_feature_name="base_prediction"))
    return component.build(raw)
```

ModelConditionedTargetBuilder是同一Component的公开别名，不是第二套运行器。build会fit_transform；fit仅记录参考预测统计，transform重新调用predict得到y-reference，既不训练参考模型也不记住未来真实标签。reference_model显式构造绑定，避免把活模型塞进共享context；若使用reference_context_key，那也只是本次本地调用的输入，不构成跨Case活对象授权。

problem/__init__.py：

```python
from mlblack.problems import SupervisedRegressionProblem

class ResidualTargetProblem(SupervisedRegressionProblem):
    def build_model_artifact(self, model, context):
        return {"schema": "case.reference_plus_linear_residual/v1",
            "reference": dict(self.data.metadata["reference_blueprint"]),
            "target_transform": dict(self.data.metadata["pipeline.model_conditioned_target"]),
            "residual_model": model.as_dict()}

def build_problem(data):
    return ResidualTargetProblem(data, use_valid_objective=False, l2=0., complexity_weight=0.)
```

build_solver.py：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from .pipeline.main import build_pipeline
from .problem import build_problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit components")
    data = build_pipeline()
    rep = LinearPointRepresentation(LinearPointConfig(n_features=data.n_features,
        feature_names=data.effective_feature_names, random_seed=17))
    solver = build_learning_solver(problem=build_problem(data), representation=rep,
        adapter=build_optimization_adapter("search.random_gaussian", population_size=8,
            mutation_scale=.25, objective_aggregation="first"),
        resource_context=resource_context, compute_backend="numpy", run_name="residual_target")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(8)
    return solver
```

**怎样判断接对：** orthogonal.json目标[train.mse,0]是残差标签上的误差，valid.mse只观察。因目标=y-reference，reference+残差预测对原y的误差在同一行上相等；但候选模型本身只输出残差，不能把它直接当最终原目标预测。Artifact同时保存参考系数、目标变换和残差系数，尚未提供通用组合加载器。该变换不擦除原Problem测量或Bias证据；这里是显式新任务含义。

**运行入口：** 执行共用报告节命令并读取正式结果与引用。实际跨Case参考须用Artifact交付，再按同一原始特征布局重建；本例不通过context复用另一个Case的活模型。

### 变体一：把参考预测作为额外特征

**目的：** 下一阶段除原始输入外，显式读参考输出。

**改在哪里：** config.py完整替换为：

```python
APPEND_PREDICTION = True
```

**行为变化：** 同一Builder别名将base_prediction追加为第三列，候选从3到4参数；标签仍为残差。**限制：** 它不是自动boosting或独立训练序列。推理先用原两列算参考预测，再组成三列给残差模型，最后相加；参考模型不能误读追加后的三列。线性参考预测与原特征冗余，不能据此保证增益或参数可识别，旧布局状态不混用。

来源：mlblack/models/linear.py、representations/orthogonal_point.py、representations/codecs/linear.py、presets/classification.py、pipeline/model_conditioning.py、core/artifact_provider.py。
