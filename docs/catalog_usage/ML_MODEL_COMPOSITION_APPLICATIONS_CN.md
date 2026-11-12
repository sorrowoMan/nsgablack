# 模型组合：分段、温度与具名预测整合

模型路由与搜索编排是两件事：本页 Router 按输入行选择预测分支，不决定哪个 Adapter 运行；预测整合也不启动内层训练。三节分别改造 `mlblack/examples/cases/catalog_codec_demo/` 的三个独立副本，保留默认 `linear_point` Case、Project L0 与正式入口。以下仅核对源码/语法/来源，没有运行 Case、训练、外部模型或数据库请求。

## composition.shared_case · 三种组合共用的正式构造和结果入口

安装当前 blackbase、nsgablack、mlblack、NumPy。保留每个 Project 副本的 project_config.py、run_project.py 与 `cases/linear_point/` 的 Case 标记、规范入口和别名。下列三个应用分别给出完整 config、pipeline/main 与 problem 文件；不要将三节覆盖到同一副本。

各节均完整替换 `cases/linear_point/adapter/__init__.py`：

```python
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter


def build_adapter():
    return build_optimization_adapter("search.random_gaussian", population_size=8,
        mutation_scale=.25, random_seed=17, objective_aggregation="first")
```

完整替换 `cases/linear_point/build_solver.py`：

```python
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides
from .pipeline.main import build_components
from .problem import build_problem
from .adapter import build_adapter


def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {"max_steps": 8, **dict(config or {})}
    data, representation = build_components()
    solver = build_learning_solver(problem=build_problem(data),
        representation=representation, adapter=build_adapter(),
        compute_backend="numpy", resource_context=resource_context,
        run_name="model_composition")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

原 pipeline 包仍会导入 build_pipeline，下面各应用都提供该函数；builder 用 build_components 同时取得同一份数据与表示。没有靠 init 推断维度，也没有私有训练循环。八个逻辑提交只是教学预算，不保证达到最优。三节原始目标分别为 `[MSE,0]` 或单项损失，故本配置的 first 与 Solver 默认 sum 选择一致；加入复杂度或其它目标后须重新明确比较规则。

在各 Project 副本根新增完整 `run_composition_and_report.py`：

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
        raise ValueError("expected evaluated feedback and a published model artifact")
    payload = {
        "run_id": run.run_id,
        "objectives": value.best_objectives.tolist(),
        "constraints": value.best_feedback.constraints.tolist(),
        "metrics": dict(value.best_feedback.metrics),
        "signals": dict(value.best_feedback.signals),
        "best_model_ref": value.best_model_ref.as_dict(),
    }
    path = root / "results" / "composition.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False,
        allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
```

**运行入口：** 在所改的 Project 副本根执行 `python run_project.py --check --build-check`，再执行 `python run_composition_and_report.py`。后者只运行一次原 default 组，然后读取正式 Case 返回的 TrainerResult；不要先跑 Project 再跑它来“补报告”。有效资源仍由 Project L0 发放，NumPy 不是额外资源授权。

每节的 Problem-owned build_model_artifact 交付可传输 JSON 蓝图，由既有 CaseRuntimeArtifactProvider 在正式 finalization 发布，best_model_ref 让结果传输不必内联活模型。蓝图不声称有通用自动加载器；报告是观察副本，不替代权威引用或运行收据。核对新 run_id 与 Case 状态，旧 JSON 不证明新运行成功。本书也未验收 checkpoint 互换或重放。

## mlblack.model.piecewise · 固定路由与两条可搜索的预测分支

**什么时候用：** 输入不同区域使用不同的点预测模型，希望直接写清路由、分支布局、目标和分支占比，而不是用 context 暗中切换训练任务。

**先准备什么：** 共用入口节的第一个完整 Project 副本。训练 48 行、验证 20 行，每行两个特征；标签在 `x0+.4*x1=0` 两侧由不同线性函数生成。主例路由只看 x0，可能无法完整表达真实边界；验证数据只报告，不参与主目标。

**放在哪：** 分别完整替换 Case 的 config.py、pipeline/main.py、problem/__init__.py，并保存共用入口节的 Adapter、builder 和报告入口。包的原 build_pipeline 导出继续有效。

**接入步骤：** config.py：

```python
LAYOUT = "branches"
ROUTING = "axis"
```

完整 pipeline/main.py：

```python
import numpy as np
from mlblack.models import Router, ThresholdRouter
from mlblack.pipeline.data_views import NumericDataView
from mlblack.representations import (
    LinearPointConfig, LinearPointRepresentation,
    PiecewiseRepresentation, PiecewiseRepresentationConfig, PiecewiseHead,
)
from ..config import LAYOUT, ROUTING


class HalfPlaneRouter(Router):
    name = "half_plane_router"

    def route(self, X):
        a = np.asarray(X, dtype=float)
        if a.ndim != 2 or a.shape[1] != 2:
            raise ValueError("router requires two feature columns")
        return (a[:, 0] + .4*a[:, 1] >= 0.).astype(int)

    def describe(self):
        return {"name": self.name, "weights": [1., .4], "threshold": 0.}


def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (48, 2)), rng.uniform(-1., 1., (20, 2))
    def target(a):
        return np.where(a[:, 0]+.4*a[:, 1] >= 0.,
                        1.+2.*a[:, 0], -1.+.5*a[:, 1])
    return NumericDataView(X_train=X, y_train=target(X),
        X_valid=V, y_valid=target(V), feature_names=("x0", "x1"))


def build_components():
    data = build_pipeline()
    if ROUTING == "axis":
        router = ThresholdRouter(feature_index=0, thresholds=(0.,))
    elif ROUTING == "half_plane":
        router = HalfPlaneRouter()
    else:
        raise ValueError("unknown routing")
    if LAYOUT == "branches":
        branches = tuple(LinearPointRepresentation(LinearPointConfig(
            n_features=2, feature_names=("x0", "x1"), random_seed=17+i))
            for i in range(2))
        representation = PiecewiseRepresentation(router=router, branches=branches,
            config=PiecewiseRepresentationConfig(branch_names=("left", "right")))
    elif LAYOUT == "head":
        representation = LinearPointRepresentation(LinearPointConfig(
            n_features=2, feature_names=("x0", "x1"), random_seed=17),
            head=PiecewiseHead(n_branches=2, router=router))
    else:
        raise ValueError("unknown branch layout")
    return data, representation
```

ThresholdRouter 用 searchsorted(side="right")：x0<0 进分支0，x0≥0 进分支1；thresholds 必须由调用者按升序给出，组件不会替你排序。Router 是扩展基类，不能单独当默认可运行路由；HalfPlaneRouter 展示了实际的自定义实现。它与 Adapter Router/阶段编排无关。

每条线性分支是 `[截距,w0,w1]`，总共六参数；路由固定，不占参数、不自动被算法学习。PiecewiseRepresentation 拼接两份实际表示，PiecewiseHead 则把同一 base Codec 分成两个块，两种都解码为 PiecewiseModel。此例不用语义参数补零或截断恢复旧布局。

完整 problem/__init__.py：

```python
from mlblack.models import PiecewiseModel
from mlblack.problems import PiecewiseRegressionProblem


class BranchProblem(PiecewiseRegressionProblem):
    def build_model_artifact(self, model, context):
        if not isinstance(model, PiecewiseModel):
            raise TypeError("expected PiecewiseModel")
        return {"schema": "case.piecewise_linear/v1",
            "router": model.router.describe(), "default_branch": model.default_branch,
            "branches": [branch.as_dict() for branch in model.branch_models]}


def build_problem(data):
    return BranchProblem(data, use_valid_objective=False, l2=0., complexity_weight=0.)
```

JSON 蓝图保存路由规则与每条实际线性模型，不 pickle router/closure。自定义路由的 describe 还须有足够重建语义；本例显式记录权重和阈值，但不自动安装通用加载器。PiecewiseModel 非法 route index 会走 default_branch；这里两个 router 都只给0/1，不依赖 fallback 掩盖错误。

**怎样判断接对：** composition.json 目标为 `[train.mse,0]`；train/valid 各有 mse/rmse/mae/r2 以及 branch_count、各出现分支的 branch_i.ratio，ratio 按本批实际路由统计，不保证每个分支都有键。占比不等于分支预测质量或算法角色权重。模型无 parameter_gradient，故使用 Gaussian 搜索；路由替换不是 Bias，不改已记录的 raw 反馈。

**运行入口：** 用共用入口节的正式 Project 命令，读取本次结果与模型引用。8步不保证找到生成标签的两条直线。

### 变体一：用斜分界替换单特征阈值

**目的：** 路由按两个特征共同判断，不修改 Adapter 或 Problem 的数据/损失。

**改在哪里：** config.py 完整替换为：

```python
LAYOUT = "branches"
ROUTING = "half_plane"
```

**行为变化：** 分支边界与本例标签的生成边界一致，候选参数仍六维；读取新路由比例和新 MSE。**限制：** 路由知识由使用者明确给出，不是框架学出的决策树；不要把旧路由的 checkpoint、分支比例或模型引用当作新模型结果。

### 变体二：用输出 Head 复用同一个基础 Codec

**目的：** 两条分支使用同一种参数布局时，减少两份表示的装配。

**改在哪里：** config.py 完整替换为：

```python
LAYOUT = "head"
ROUTING = "axis"
```

**行为变化：** PiecewiseHead 实际分配两块三参数点预测模型，参数总数仍六；不是两次独立训练。**限制：** LinearPointRepresentation.init 只随机初始化首个基础块，后续块初始为零，和两份独立表示的初始分布不同；不能按同 seed 期待相同轨迹。两个配置应分开记录结果。

## mlblack.model.temperature_calibrated_probability · 冻结基础模型，仅搜索温度

**什么时候用：** 已有概率模型，希望保持其基础参数不动，仅在校准样本上优化一个温度。它会改变所评估模型的概率，不是把 Problem 目标作为 Bias 软化。

**先准备什么：** 共用入口节的第二个 Project 副本。本例给出固定基础 logit `[0,4,-1.6]`，不声称已训练它；train 字段装40条校准样本，valid装21条只观察样本。两类明确为0/1，基础模型不使用校准/验证标签进行拟合。

**放在哪：** 完整替换以下 config、pipeline/main、problem 文件，Adapter/builder/Project/L0 使用共用入口节。

**接入步骤：** config.py：

```python
MODE = "temperature"
```

pipeline/main.py 完整内容：

```python
import numpy as np
from mlblack.core.representation import ModelRepresentation
from mlblack.core.types import UnknownState
from mlblack.models import (LinearPointModel, BinaryLogisticProbabilityModel,
    TemperatureCalibratedProbabilityModel, ProbabilityCalibrationModel)
from mlblack.pipeline.data_views import NumericDataView
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import ProbabilityCalibrationHead
from ..config import MODE


class TemperatureRepresentation(ModelRepresentation):
    dimension = 1

    def __init__(self, mode):
        if mode not in ("temperature", "probability"):
            raise ValueError("unsupported frozen-model wrapper")
        self.mode = mode
        self.base = BinaryLogisticProbabilityModel(LinearPointModel(
            intercept=0., weights=np.array([4., -1.6])), classes_=(0, 1))
        self.layout = "case.frozen_temperature/v1:" + mode + ":0,4,-1.6"

    def init(self, context):
        return UnknownState(values=np.array([0.]), metadata={"layout": self.layout})

    def _values(self, state):
        a = np.asarray(state.values, dtype=float).reshape(-1)
        if a.size != 1 or not np.all(np.isfinite(a)):
            raise ValueError("temperature candidate requires one finite parameter")
        if state.metadata.get("layout") != self.layout:
            raise ValueError("frozen base or wrapper identity changed")
        return a

    def repair(self, state, context=None):
        return state.with_values(np.clip(self._values(state), -10., 10.))

    def decode(self, state, context=None):
        raw = self._values(state)[0]
        temperature = float(np.clip(.05 + np.logaddexp(0., raw), .05, 10.))
        wrapper = (TemperatureCalibratedProbabilityModel
                   if self.mode == "temperature" else ProbabilityCalibrationModel)
        return wrapper(base_model=self.base, temperature=temperature)


def build_pipeline():
    def inputs(n, shift):
        t = np.linspace(-2.+shift, 2.-shift, n)
        return np.column_stack((t, np.cos(t)))
    def labels(a):
        y = (a[:, 0] + .4*a[:, 1] >= 0.).astype(int)
        y[::7] = 1 - y[::7]
        return y
    X, V = inputs(40, 0.), inputs(21, .07)
    return NumericDataView(X_train=X, y_train=labels(X),
        X_valid=V, y_valid=labels(V), feature_names=("x0", "x1"))


def build_components():
    data = build_pipeline()
    if MODE == "joint_head":
        representation = LinearPointRepresentation(LinearPointConfig(
            n_features=2, feature_names=("x0", "x1"), random_seed=17),
            head=ProbabilityCalibrationHead(min_temperature=.05, max_temperature=10.))
    else:
        representation = TemperatureRepresentation(MODE)
    return data, representation
```

这里只在表示的正式 decode 内构造包装模型；不是调用外部训练或在恢复时重跑 fitter。维度声明为1，init 发生在 Solver/Pool 建立以后。repair 保留同一 UnknownState metadata，并拒绝不匹配的基础布局；没有 deepcopy 活 Provider。初始 raw temperature=0 对应约 .743，而不是温度1。

problem/__init__.py 完整内容：

```python
import numpy as np
from mlblack.core.types import Feedback
from mlblack.models import (LinearPointModel, BinaryLogisticProbabilityModel,
    TemperatureCalibratedProbabilityModel, ProbabilityCalibrationModel)
from mlblack.problems import SupervisedClassificationProblem


class CalibrationProblem(SupervisedClassificationProblem):
    def evaluate(self, model, state, context):
        feedback = super().evaluate(model, state, context)
        base = model.base_model
        if not hasattr(base, "predict_proba"):
            base = BinaryLogisticProbabilityModel(base, classes_=(0, 1))
        metrics = dict(feedback.metrics)
        for prefix, X, y in (("train", self.data.X_train, self.data.y_train),
                              ("valid", self.data.X_valid, self.data.y_valid)):
            p = np.clip(base.predict_proba(X), 1e-12, 1.)
            metrics[f"base.{prefix}.log_loss"] = -float(
                np.log(p[np.arange(len(y)), np.asarray(y, dtype=int)]).mean())
        return Feedback(objectives=feedback.objectives, constraints=feedback.constraints,
            loss=feedback.loss, residuals=feedback.residuals, metrics=metrics,
            signals={**dict(feedback.signals), "temperature": float(model.temperature)})

    def build_model_artifact(self, model, context):
        if not isinstance(model, (TemperatureCalibratedProbabilityModel, ProbabilityCalibrationModel)):
            raise TypeError("unexpected calibration model")
        base = model.base_model
        if isinstance(base, BinaryLogisticProbabilityModel):
            logit = base.logit_model
            base_kind = "binary_probability"
        elif isinstance(base, LinearPointModel):
            logit, base_kind = base, "scalar_logit"
        else:
            raise TypeError("this recipe publishes linear logits only")
        return {"schema": "case.linear_temperature/v1", "wrapper": type(model).__name__,
            "temperature": float(model.temperature), "clip_eps": float(model.clip_eps),
            "classes": [0, 1], "base_kind": base_kind, "base_logit": logit.as_dict()}


def build_problem(data):
    return CalibrationProblem(data, use_valid_objective=False,
        objective_metrics=("log_loss",), complexity_weight=0.)
```

**怎样判断接对：** composition.json 的单项目标等于 train.log_loss，这是被评估包装模型在校准样本上的真实损失；base.train/valid.log_loss 另记录未加温度的基础预测，不覆盖成“零成本原始目标”。温度在 .05..10。主例基础 logit 固定，改变温度不会学习新分类边界；不保证验证损失变好。两个包装器均没有透传 classes_ 属性，本例标签固定0/1且两类均出现，不能直接套到任意词表。

**运行入口：** 执行共用入口节命令并核对本次 JSON/模型引用。这里 train 指校准集；若反复依验证结果改温度，验证就不再是独立评估。raw feedback 指 Problem 对当前包装模型的测量，不等于基础模型测量或 Bias 选择视图。

### 变体一：换用普通概率校准包装器

**目的：** 复用相同冻结概率模型和温度候选，只换包装组件。

**改在哪里：** config.py 完整替换为：

```python
MODE = "probability"
```

**行为变化：** ProbabilityCalibrationModel 读取现有 predict_proba，再做 log 概率/温度归一；两个包装器采用同一归一形式，但 TemperatureCalibratedProbabilityModel 在 exp 前额外 clip 到[-60,60]，极端概率/小温度下不保证逐元素完全一致。**限制：** 普通包装器的 predict 返回列索引，另一包装器会尝试映射基础 classes_；当前 Problem 用概率 argmax、类别固定0/1，所以这里没有类别含义差异。若直接传线性原始 logit，普通包装器的 fallback 会将 predict 当作概率，而另一包装器会先套 sigmoid，不能互换。

### 变体二：让 Head 联合搜索基础 logit 与温度

**目的：** 看清已有 ProbabilityCalibrationHead 的实际语义，避免把它误认成冻结模型的后处理。

**改在哪里：** config.py 完整替换为：

```python
MODE = "joint_head"
```

**行为变化：** 三个线性基础参数加一个 raw temperature，共四参数；Head 解码为 TemperatureCalibratedProbabilityModel，基础预测也会变化，报告的 base 指标随候选变。**限制：** 这已经是联合建模，train 字段须按训练集理解，不再是“只校准已有模型”；不能加载旧一参数状态。基础 logit 与温度缩放存在冗余，不能据四参数搜索声称可识别或校准保证。

## mlblack.model.integrated_prediction · 两种输入形状，组合成一项预测

**什么时候用：** 已有两个可预测的参数模型，希望按具名输入、显式 I/O 和权重规则组合；权重是本 Case 的搜索候选，组合器只做推断，不负责训练各个基础模型。

**先准备什么：** 共用入口节的第三个 Project 副本。基础模型由下文固定系数构成，不声称从数据拟合过。表格三列中第一列送 trend，后两列送 correction；40条训练、16条验证共用严格行顺序。只有两个权重被搜索，验证仅报告。

**放在哪：** 完整替换以下三个 Case 文件；共用 Adapter/builder/Project/report 入口继续使用。

**接入步骤：** config.py：

```python
KIND = "additive"
```

pipeline/main.py 完整内容：

```python
import numpy as np
from mlblack.core.representation import ModelRepresentation
from mlblack.core.types import UnknownState
from mlblack.models import (LinearPointModel, PredictionInputSpec, PredictionOutputSpec,
    PredictionIOContract, PredictionIntegrationSpec, PredictionIntegrationComponent)
from mlblack.pipeline.data_views import NumericDataView
from ..config import KIND


class WeightRepresentation(ModelRepresentation):
    dimension = 2

    def __init__(self, kind):
        if kind not in ("additive", "mean"):
            raise ValueError("unknown integration rule")
        self.kind = kind

    def init(self, context):
        return UnknownState(values=np.ones(2), metadata={"integration_kind": self.kind})

    def _values(self, state):
        a = np.asarray(state.values, dtype=float).reshape(-1)
        if a.size != 2 or not np.all(np.isfinite(a)):
            raise ValueError("expected two finite weights")
        if state.metadata.get("integration_kind") != self.kind:
            raise ValueError("integration meaning changed")
        return a

    def repair(self, state, context=None):
        a = np.clip(self._values(state), 0., 2.)
        if a.sum() <= 1e-12:
            a = np.ones(2)
        return state.with_values(a)

    def decode(self, state, context=None):
        weights = self._values(state)
        if np.any(weights < 0.) or np.any(weights > 2.) or weights.sum() <= 1e-12:
            raise ValueError("decode requires repaired nonzero weights in 0..2")
        components = {
            "trend": LinearPointModel(intercept=1., weights=np.array([2.])),
            "correction": LinearPointModel(intercept=0., weights=np.array([-.3, .4])),
        }
        io = PredictionIOContract.by_component({
            "trend": PredictionInputSpec(key="trend_rows", ndim=2, n_features=1),
            "correction": PredictionInputSpec(key="weather_rows", ndim=2, n_features=2),
        }, output=PredictionOutputSpec(kind="point_vector", requires_aligned_rows=True))
        integration = PredictionIntegrationSpec(kind=self.kind,
            component_order=("trend", "correction"),
            weights={"trend": float(weights[0]), "correction": float(weights[1])},
            intercept=0.)
        return PredictionIntegrationComponent(integration=integration, io_contract=io).compose(components)


def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (40, 3)), rng.uniform(-1., 1., (16, 3))
    def target(a):
        return .6*(1.+2.*a[:, 0]) + .4*(-.3*a[:, 1]+.4*a[:, 2])
    return NumericDataView(X_train=X, y_train=target(X),
        X_valid=V, y_valid=target(V), feature_names=("time", "rain", "temperature"))


def build_components():
    return build_pipeline(), WeightRepresentation(KIND)
```

普通数组会被 IOContract 当作共享输入，不能自动切成1列/2列；下面 Problem 必须提供具名映射。`shared` 是 Mapping 缺少专名时的 fallback，不应当作补齐缺失输入的捷径。显式 required=True 的默认值会在两种键都缺少时拒绝。

problem/__init__.py 完整内容：

```python
import numpy as np
from mlblack.core.problem import LearningProblem
from mlblack.core.types import Feedback
from mlblack.models import IntegratedPredictionModel


class IntegrationProblem(LearningProblem):
    objective_count = 1

    def __init__(self, data):
        self.data = data

    def evaluate(self, model, state, context):
        metrics = {}
        for prefix, X, y in (("train", self.data.X_train, self.data.y_train),
                              ("valid", self.data.X_valid, self.data.y_valid)):
            inputs = {"trend_rows": X[:, :1], "weather_rows": X[:, 1:]}
            prediction = np.asarray(model.predict(inputs), dtype=float)
            if prediction.shape != y.shape or not np.all(np.isfinite(prediction)):
                raise ValueError("integrated prediction must align with labels")
            metrics[f"{prefix}.mse"] = float(np.mean((prediction-y)**2))
            for name, values in model.component_predictions(inputs).items():
                metrics[f"{prefix}.{name}.mse"] = float(np.mean((values-y)**2))
        loss = metrics["train.mse"]
        return Feedback(objectives=np.array([loss]), loss=loss, metrics=metrics,
            signals={"has_gradient": False, "integration_kind": model.integration.kind})

    def build_model_artifact(self, model, context):
        if not isinstance(model, IntegratedPredictionModel):
            raise TypeError("expected IntegratedPredictionModel")
        return {"schema": "case.weighted_linear_models/v1",
            "components": {name: component.as_dict() for name, component in model.components.items()},
            "integration": model.integration.describe(), "io_contract": model.io_contract.describe()}


def build_problem(data):
    return IntegrationProblem(data)
```

requires_aligned_rows 检查组件间行数，不检查业务 row_id 或标签语义。本 Problem 从同一个 X 按列切分，保持行顺序并检查最终 prediction/y 形状；如果外部两张表错排但行数相同，契约无法猜出正确关联。模型组件要求 point vector 或单列二维输出；概率矩阵、区间或不同长度序列不能直接相加。

**怎样判断接对：** composition.json 的一项目标等于 train.mse；valid.mse 只观测；train/valid 各另有 trend.mse、correction.mse，这是未加权基础预测相对于同一标签的误差，不是两项训练损失。additive 预测为 w0×trend+w1×correction，权重范围0..2且不全零，不默认归一。理论生成权重为(.6,.4)，八步不保证找到；两个组件的固定参数不会随权重搜索改变。Artifact 同时保存模型系数、实际权重规则和 I/O 描述。

**运行入口：** 依共用入口节通过正式 Project 运行，读本次 JSON/TrainerResult/模型引用。这不是跨 Case 的顺序训练、残差再拟合或多 Adapter 融合；若基础模型本身需要训练，应由各自正式 Case 与 Artifact 交付完成。

### 变体一：按权重总量归一，组合改为 mean

**目的：** 对比原始加权和与归一化混合，不改变基础预测或输入行对齐。

**改在哪里：** config.py 完整替换为：

```python
KIND = "mean"
```

**行为变化：** mean 输出除以绝对权重和；本例权重非负，所以为普通正权归一。初始权重(1,1)由两项和变成均值。**限制：** 相同比例的权重给相同预测，不能把候选身份按预测相同合并；当前实现若允许负权也按绝对值和归一，且 intercept 也参与被除，不能擅自按标准统计均值解释。此例 intercept=0且修复排除全零。旧 additive 状态含义不同，不混用恢复。

源码依据：`mlblack/models/conditional.py`、`models/probability.py`、`models/composition.py`、`representations/conditional.py`、`representations/heads/conditional.py`、`representations/heads/probability.py`、`problems/conditional.py`、`problems/classification.py`、`core/artifact_provider.py`、`core/problem.py`、`core/representation.py`，以及现有 catalog_codec_demo 的 Project 和 Case 入口。
