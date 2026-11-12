# 条件特征与残差组合：把可调用位置写清楚

两例各用 `mlblack/examples/cases/catalog_codec_demo/` 的完整独立副本。依赖当前三仓和 NumPy；保留原 Project/L0/default 单 Case。共用 [模型组合书的正式入口](ML_MODEL_COMPOSITION_APPLICATIONS_CN.md#compositionshared_case--三种组合共用的正式构造和结果入口)：保存其 Adapter、薄 builder、run_composition_and_report.py。下列 config/pipeline/problem 替换文件与共用入口一起构成完整操作。没有运行这些数据、模型或算法；文中源码核对不等于执行收据。

## mlblack.pipeline.conditional_primitive_feature · 特征列先扩展，模型再消费

**什么时候用：** 固定阈值、平滑门、折线、类别指示或自己的确定性特征能表达先验，希望它们成为真实模型输入列，而不是仅放入说明或共享 context。

**先准备什么：** 完整 catalog_codec_demo 副本及共用入口文件。原始两列：x0连续、group为0/1。32训练/12验证先分开；门参数由使用者给定，不用验证标签调阈值。没有外部拟合器。

**放在哪：** 完整替换 `cases/linear_point/config.py`、`pipeline/main.py`、`problem/__init__.py`；共用 builder 调 build_components，原 pipeline 包的 build_pipeline 导出保留。

**接入步骤：** config.py：

```python
INCLUDE_ORIGINAL = True
```

pipeline/main.py：

```python
import numpy as np
from mlblack.pipeline import DataPipeline, NumericDataView
from mlblack.pipeline.conditional import (ConditionalPrimitive, ConditionalPrimitiveSpec,
    BinaryGate, SoftGate, HingeFeature, OneHotGate, PrimitiveFeatureComposer)
from mlblack.pipeline.feature_space import ConditionalPrimitiveFeatureComponent, FeatureSpaceComponent
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from ..config import INCLUDE_ORIGINAL


class AbsoluteFeature(ConditionalPrimitive):
    name = "absolute_x0"
    def transform(self, X):
        return np.abs(np.asarray(X, dtype=float)[:, :1])


def build_pipeline():
    rng = np.random.default_rng(17)
    def rows(n):
        return np.column_stack((rng.uniform(-1., 1., n), rng.integers(0, 2, n)))
    def target(a):
        return .4*a[:, 0] + .7*np.abs(a[:, 0]) + 2.*(a[:, 0] >= 0.) - .3*a[:, 1]
    X, V = rows(32), rows(12)
    raw = NumericDataView(X_train=X, y_train=target(X),
        X_valid=V, y_valid=target(V), feature_names=("x0", "group"))
    spec = ConditionalPrimitiveSpec(name="binary_gate", family="gate",
        source_features=("x0",), parameters={"feature_index": 0, "threshold": 0.})
    binary = BinaryGate(**dict(spec.parameters))
    composer = PrimitiveFeatureComposer(primitives=(binary,
        SoftGate(feature_index=0, threshold=0., temperature=.3),
        HingeFeature(feature_index=0, knot=0., side="right"),
        OneHotGate(feature_index=1, values=(0., 1.)), AbsoluteFeature()),
        include_original=INCLUDE_ORIGINAL)
    pipeline = DataPipeline([
        ConditionalPrimitiveFeatureComponent(primitives=composer.primitive_objects(),
            include_original=composer.include_original),
        FeatureSpaceComponent(group="conditional"),
    ])
    return pipeline.fit_transform(raw)


def build_components():
    data = build_pipeline()
    rep = LinearPointRepresentation(LinearPointConfig(n_features=data.n_features,
        feature_names=data.effective_feature_names, random_seed=17))
    return data, rep
```

ConditionalPrimitive 是 transform 扩展基类；直接实例化它会抛 NotImplementedError。上面的 AbsoluteFeature 才是被实际消费的自定义实现。ConditionalPrimitiveSpec 是说明值，不能直接丢给 primitive_from_spec 当组件；这里明确用 parameters 构造 BinaryGate。若要字典分派，现有 composer 接受 `{"name":"binary_gate","params":...}`，不是自动理解 spec.describe 的全部字段。

BinaryGate 输出≥阈值的0/1；SoftGate 是 sigmoid，temperature控制陡峭程度，不是采样概率；HingeFeature 输出max(x0,0)；OneHotGate按给定值顺序产生两列，未知值全零；最后一列是绝对值。包含原列时共8列，线性候选含截距共9参数；不含原列时6列、7参数。FeatureSpaceComponent 将实际扩展列名记录到数据 metadata，不凭名字分配 Adapter Unit。

problem/__init__.py：

```python
from mlblack.problems import SupervisedRegressionProblem


class ConditionalRegression(SupervisedRegressionProblem):
    def build_model_artifact(self, model, context):
        return {"schema": "case.conditional_linear/v1", "model": model.as_dict(),
            "features": dict(self.data.metadata["conditional_primitives"]),
            "feature_space": dict(self.data.metadata["feature_space"])}


def build_problem(data):
    return ConditionalRegression(data, use_valid_objective=False,
        l2=0., complexity_weight=0.)
```

**怎样判断接对：** composition.json 原始目标为[train.mse,0]；valid.mse只观测。Artifact蓝图含实际条件变换、扩展列序与线性系数，不能把这些系数直接乘原始两列。推理须复用同一确定性特征定义；自定义AbsoluteFeature的重建由本Case代码负责，describe不是通用代码序列化。既没有自动发现分段阈值，也没有搜索这些特征的结构。

**运行入口：** 共用入口的 Project check/build-check 后，仅运行一次 run_composition_and_report.py；核对本次 run_id、Case状态和best_model_ref。没有训练性能或恢复证明。

### 变体一：只保留条件特征，不带原始两列

**目的：** 检验明确先验特征本身能表达多少目标关系。

**改在哪里：** config.py完整替换为：

```python
INCLUDE_ORIGINAL = False
```

**行为变化：** 变成6特征/7参数；Problem与正式执行链不变。**限制：** 不能用旧9参数状态恢复；原始group仍经OneHot保留信息，但原始x0不再独立输入，不能保证误差不变。两个Catalog别名conditional.composer/primitive_feature_composer只指一份类，不要装两遍来凑数量。

## mlblack.conditional.shared_backbone_residual_composer · 共享预测加具名区域残差

**什么时候用：** 所有输入共用一个基础模型，再按路由只加对应分支残差；希望这条预测关系是模型对象，不在 Adapter 或生命周期插件里偷偷加分。

**先准备什么：** 第二个独立 Project 副本与共用入口。两特征，32训练/12验证；固定路由x0<0/≥0，基础和两个残差都是线性模型。总9参数一起搜索，不是三个独立训练任务。

**放在哪：** 同样完整替换 Case config、pipeline/main、problem，并用共用正式Adapter/builder/报告入口。

**接入步骤：** config.py：

```python
USE_ROUTER = True
```

pipeline/main.py：

```python
import numpy as np
from mlblack.core.representation import ModelRepresentation
from mlblack.core.types import UnknownState
from mlblack.pipeline import NumericDataView
from mlblack.pipeline.conditional import RouteThenFormulaComposer, SharedBackboneResidualComposer
from mlblack.models import ThresholdRouter
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from ..config import USE_ROUTER


class ResidualRepresentation(ModelRepresentation):
    dimension = 9
    def __init__(self):
        self.parts = tuple(LinearPointRepresentation(LinearPointConfig(
            n_features=2, feature_names=("x0", "x1"), random_seed=17+i)) for i in range(3))

    def init(self, context):
        return UnknownState(values=np.concatenate([part.init(context).values for part in self.parts]),
                            metadata={"routed_residual": USE_ROUTER})

    def decode(self, state, context=None):
        a = np.asarray(state.values, dtype=float).reshape(-1)
        if a.size != 9 or not np.all(np.isfinite(a)):
            raise ValueError("expected three finite linear parameter blocks")
        if state.metadata.get("routed_residual") != USE_ROUTER:
            raise ValueError("residual routing meaning changed")
        models = tuple(part.decode(UnknownState(values=a[3*i:3*i+3]), context)
                       for i, part in enumerate(self.parts))
        descriptor = RouteThenFormulaComposer(
            router=ThresholdRouter(feature_index=0, thresholds=(0.,)),
            branch_formulas=("left_linear", "right_linear"))
        return SharedBackboneResidualComposer(backbone=models[0], residual_branches=models[1:],
            router=descriptor if USE_ROUTER else None)


def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (32, 2)), rng.uniform(-1., 1., (12, 2))
    def target(a):
        return 1.+2.*a[:, 0] + np.where(a[:, 0] < 0., -.5*a[:, 1], .5*a[:, 1])
    return NumericDataView(X_train=X, y_train=target(X), X_valid=V, y_valid=target(V),
                           feature_names=("x0", "x1"))


def build_components():
    return build_pipeline(), ResidualRepresentation()
```

RouteThenFormulaComposer.route实际被ResidualComposer.predict调用，但branch_formulas在当前实现只是描述，不执行公式、不拟合模型。两个实际分支来自residual_branches，不得把字符串公式当成已接上的模型。残差路由未知值只不加任何残差；本例明确0/1，不拿这种行为隐藏错误。

problem/__init__.py：

```python
from mlblack.problems import SupervisedRegressionProblem


class ResidualProblem(SupervisedRegressionProblem):
    def build_model_artifact(self, model, context):
        return {"schema": "case.routed_linear_residual/v1",
            "backbone": model.backbone.as_dict(),
            "residuals": [branch.as_dict() for branch in model.residual_branches],
            "router": None if model.router is None else model.router.describe()}


def build_problem(data):
    return ResidualProblem(data, use_valid_objective=False, l2=0., complexity_weight=0.)
```

**怎样判断接对：** composition.json目标为[train.mse,0]；Artifact保留三模型系数及路由描述。实际预测是backbone+对应区域残差，不能解读成平均或选一个基础模型。组合器没有parameter_gradient，使用Gaussian搜索；基础/残差的分解可能冗余，不声称各自系数可识别或自动避免过拟合。

**运行入口：** 按共用正式Project命令运行并读取本次TrainerResult和模型引用，原始反馈保留实际预测误差。无运行收据。

### 变体一：取消路由，所有残差都相加

**目的：** 明确“区域残差”与“全局叠加”的区别。

**改在哪里：** config.py完整替换为：

```python
USE_ROUTER = False
```

**行为变化：** 两个残差对每行都贡献，预测=backbone+r0+r1；参数仍9个。**限制：** 三个线性模型之和仍是线性函数，不能自动表达原来的分段关系；同维度不表示同checkpoint含义，不能沿用带路由的候选结果。组合器不负责训练顺序、独立Case调用或L0分配。

来源：mlblack/pipeline/conditional/primitives.py、composer.py、pipeline/feature_space.py、core/representation.py、problems/supervised.py；完整执行与Artifact边界沿用共用正式Case入口。
