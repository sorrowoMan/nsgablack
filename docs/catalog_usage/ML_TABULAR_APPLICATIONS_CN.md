# ML 表格应用：点预测、分类概率和区间不是同一种评估

下面三节各使用 `mlblack/examples/cases/catalog_codec_demo/` 的一个**独立副本**，不是把三种任务同时塞进原 Case。保留完整 Project、L0、Case 标记、规范运行入口及别名；每节路径相对副本根目录。依赖当前 blackbase、nsgablack、mlblack 和 NumPy，不需要在线模型、Torch 或网络下载。只做源码、来源与语法核对，未执行训练或下列运行命令，没有生成运行收据。

## mlblack.problem.supervised_regression · 线性点预测与 NumPy MLP

**什么时候用：** 特征是二维表格，标签是连续数；先用有明确参数含义的线性模型，再只更换模型结构检验非线性。实际涉及 `mlblack.model.linear_point`、`mlblack.model.numpy_mlp_point` 与 `mlblack.representation.neural_graph`。

**先准备什么：** 使用上面完整 Project 的独立副本，保留其默认只运行 `cases/linear_point` 的 Project 配置。32 条训练样本、12 条独立验证样本，每条两个特征。验证集只观察，主例优化训练 MSE；预算为 8 个逻辑提交，不承诺收敛。不要在构造表示时调用 init 来猜维度。

**放在哪：** 依次完整替换 `cases/linear_point/config.py`、`pipeline/main.py`、`problem/__init__.py`、`adapter/__init__.py` 和 `build_solver.py`。保留 pipeline 包原有 `from .main import build_pipeline`。在 Project 根新增下方 `run_tabular_and_report.py`；它只包装现有正式 Project 执行器。

**接入步骤：** 先保存配置，基线明确为 linear；后面的变体只切换此字段。

```python
# cases/linear_point/config.py
MODEL = "linear"
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import NumericDataView
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations import NeuralGraphRepresentation
from mlblack.representations.heads import PointHead

def build_pipeline(*, seed=17):
    rng = np.random.default_rng(int(seed))
    X = rng.uniform(-1., 1., (32, 2))
    V = rng.uniform(-1., 1., (12, 2))
    def target(a):
        return 1. + 2.*a[:, 0] - .5*a[:, 1] + .3*a[:, 0]*a[:, 1]
    return NumericDataView(X_train=X, y_train=target(X),
        X_valid=V, y_valid=target(V), feature_names=("x0", "x1"))

def build_representation(data, model, *, seed=17):
    if model == "linear":
        return LinearPointRepresentation(LinearPointConfig(
            n_features=data.n_features, feature_names=data.effective_feature_names,
            random_seed=int(seed)), head=PointHead())
    if model == "mlp":
        return NeuralGraphRepresentation.mlp(input_dim=data.n_features,
            hidden_layers=(4,), output_dim=1, activation="tanh", dropout=0.,
            random_seed=int(seed), representation_name="small_numpy_regression")
    raise ValueError("model must be linear or mlp")
```

主例 Codec 把 `[截距,w0,w1]` 解释成 LinearPointModel，PointHead 直接输出 `(n,)`。MLP 分支由正式 NeuralGraphRepresentation/NeuralGraphCodec 和指定的 NumPy backend 构造 NumpyMLPPointModel；本页没有手写神经网络运行器。布局是 `(2,4)/(4,)/(4,1)/(1,)` 四块，共 17 个参数；它不支持这里的解析 parameter_gradient，因此两个分支统一使用不依赖梯度的搜索。

```python
# cases/linear_point/problem/__init__.py
from mlblack.models import LinearPointModel, NumpyMLPPointModel
from mlblack.problems import SupervisedRegressionProblem

class PointProblem(SupervisedRegressionProblem):
    def build_model_artifact(self, model, context):
        if isinstance(model, LinearPointModel):
            return model.as_dict()
        if isinstance(model, NumpyMLPPointModel):
            return {"schema": "case.numpy_mlp_point/v1",
                "activation": model.activation,
                "weights": [w.tolist() for w in model.weights],
                "biases": [b.tolist() for b in model.biases]}
        raise TypeError("unexpected decoded point model")

def build_problem(data):
    return PointProblem(data, l2=0., complexity_weight=0., use_valid_objective=False)
```

原生线性模型有安全 `as_dict`；NumPy MLP 没有通用 Artifact 导出方法，本 Case 显式发布带形状的权重蓝图，避免退到 unsafe pickle。蓝图是本 Case 的持久值，不声称框架已经提供它的通用加载器。这里的模型由参数直接解码，没有 estimator.fit 或额外准备副作用；默认只读恢复规则不会重新训练。

```python
# cases/linear_point/adapter/__init__.py
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter

def build_adapter():
    return build_optimization_adapter("search.random_gaussian", population_size=8,
        mutation_scale=.15, random_seed=17, objective_aggregation="first")
```

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides
from .config import MODEL
from .pipeline.main import build_pipeline, build_representation
from .problem import build_problem
from .adapter import build_adapter

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {"seed": 17, "max_steps": 8, **dict(config or {})}
    data = build_pipeline(seed=settings["seed"])
    solver = build_learning_solver(problem=build_problem(data),
        representation=build_representation(data, MODEL, seed=settings["seed"]),
        adapter=build_adapter(), compute_backend="numpy",
        resource_context=resource_context, run_name="tabular_point")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(int(settings["seed"]))
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

以下薄入口从正式 Case 返回值读指标；不要先运行一次 Project、再调用它来“补报告”，那会运行第二次。

```python
# run_tabular_and_report.py
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
    if value.best_feedback is None:
        raise ValueError("no evaluated incumbent")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "metrics": dict(value.best_feedback.metrics),
        "signals": dict(value.best_feedback.signals),
        "best_model_ref": None if value.best_model_ref is None else value.best_model_ref.as_dict()}
    path = root / "results" / "tabular.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False,
        allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 检查本次正式 Case 状态与 `results/tabular.json` 的新 run_id。原始目标是 `[train.mse,0]`；指标同时有 train/valid 的 mse/rmse/mae/r2 和 `loss.regularized_train`。不是“验证误差加到训练目标”。当前配置 l2=0，loss 等于训练 MSE；l2 非零只改损失/已有解析梯度，不自动改两项目标。Gaussian 本例比较第一目标；Solver 默认求和，在第二项为零时与它一致。模型来自已评估 incumbent，不是最后一次未评估后继。交互项让线性模型存在表达限制，训练小预算的 MLP 也不保证更好。

**运行入口：** 在副本根执行 `python run_project.py --check --build-check`，然后 `python run_tabular_and_report.py`。前者装配检查，后者实际运行一次正式 Project 并写报告。资源继续由原 Project L0 发放，NumPy 选择不自行申请线程或 GPU；有效后端仍须服从 grant。模型 Artifact 的正式引用和本地报告分开核对，旧 JSON 不能证明新运行成功。本轮没有执行这些命令。

### 变体一：相同数据与目标，改为 17 参数 NumPy MLP

**目的：** 验证非线性结构能否表达交互关系，而不是换标签或暗中调用 Torch。

**改在哪里：** 从本节主例完整替换同一 config.py，其余代码均已包含对应分支。

```python
# cases/linear_point/config.py
MODEL = "mlp"
```

**行为变化：** 表示在正式 setup 解析神经布局，之后初始化 17 参数候选；NumPy backend 解码为 NumpyMLPPointModel，Problem 和搜索方法保持不变。反馈 `has_gradient` 为 False；不应把这条路线叫 Adam 训练或反向传播。Artifact 保存真实权重和 biases 蓝图。

**限制：** 更大的搜索空间通常需要重新考虑步长、样本量与预算；不能按同 seed 假定两种结构得到相同候选。SupervisedRegressionProblem 的复杂度实现以 `state.values[1:]` 计数，它不是逐层排除 MLP bias 的参数统计，所以本例 complexity_weight 与 l2 都保持零。此 NumPy MLP predict 只读输出第一列，本例明确 output_dim=1。

源码依据：`mlblack/models/linear.py`、`models/neural.py`、`representations/linear_point.py`、`representations/neural_graph.py`、`backends/numpy_neural/capabilities/neural_lowering.py`、`problems/supervised.py`、`core/artifact_provider.py`。

## mlblack.problem.supervised_classification · 二分类概率与三分类

**什么时候用：** 希望分类指标来自概率，而不把连续回归 MSE 当分类目标。主例实际组合 BinaryLogisticHead、LinearPointRepresentation 和 SupervisedClassificationProblem，解码后是 `mlblack.model.binary_logistic_probability`；变体解码为 `mlblack.model.softmax_probability`。

**先准备什么：** 使用 `mlblack/examples/cases/catalog_codec_demo` 的另一份独立副本；依赖三仓与 NumPy。保留默认 Project 和 `cases/linear_point` 名字，虽然任务已变成分类。训练 36 行、验证 18 行、两特征。类别显式为 `(0,1)` 或 `(0,1,2)`，不传 one-hot，也不依赖验证集恰好出现全部类别来推断列含义。

**放在哪：** 完整替换 Case 的 config、pipeline/main、problem、adapter、build_solver 五个文件；原 pipeline 包入口只导出 build_pipeline，下面 builder 从 `.pipeline.main` 导入两个工厂。新增 Project 根 `run_classification_and_report.py`。

**接入步骤：** 参数块随同一个配置一起变化，不能只把二分类标签换成三类。

```python
# cases/linear_point/config.py
N_CLASSES = 2
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import NumericDataView
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import BinaryLogisticHead, SoftmaxHead

def build_pipeline(n_classes):
    if n_classes not in (2, 3):
        raise ValueError("this data recipe defines two or three classes")
    rng = np.random.default_rng(17)
    X = rng.uniform(-1., 1., (36, 2))
    V = rng.uniform(-1., 1., (18, 2))
    def labels(a):
        if n_classes == 2:
            return (a[:, 0] + .4*a[:, 1] > 0.).astype(int)
        logits = np.column_stack((a[:, 0], a[:, 1], -a[:, 0]-a[:, 1]))
        return np.argmax(logits, axis=1)
    return NumericDataView(X_train=X, y_train=labels(X),
        X_valid=V, y_valid=labels(V), feature_names=("x0", "x1"))

def build_representation(data, n_classes):
    head = (BinaryLogisticHead(classes=(0, 1), threshold=.5)
        if n_classes == 2 else SoftmaxHead(n_classes=3, classes=(0, 1, 2)))
    return LinearPointRepresentation(LinearPointConfig(n_features=data.n_features,
        feature_names=data.effective_feature_names, random_seed=17), head=head)
```

二分类三个参数定义一个 logit，模型 predict_proba 为 `(n,2)`；三分类每类独立一个三参数 logit，共九参数，输出 `(n,3)`。classes 顺序就是概率列顺序。Head 负责这些参数和输出含义；Problem 负责使用哪一份数据、哪一组指标；Adapter 不读取标签。

```python
# cases/linear_point/problem/__init__.py
from mlblack.models import BinaryLogisticProbabilityModel, SoftmaxProbabilityModel
from mlblack.problems import SupervisedClassificationProblem

class ClassificationProblem(SupervisedClassificationProblem):
    def build_model_artifact(self, model, context):
        if isinstance(model, BinaryLogisticProbabilityModel):
            return {"schema": "case.linear_classifier/v1", "kind": "binary",
                "classes": list(model.classes_), "temperature": model.temperature,
                "threshold": model.threshold, "logits": [model.logit_model.as_dict()]}
        if isinstance(model, SoftmaxProbabilityModel):
            return {"schema": "case.linear_classifier/v1", "kind": "softmax",
                "classes": list(model.classes_), "temperature": model.temperature,
                "logits": [m.as_dict() for m in model.logit_models]}
        raise TypeError("unexpected probability model")

def build_problem(data):
    return ClassificationProblem(data, use_valid_objective=False,
        objective_metrics=("log_loss",), complexity_weight=0.)
```

Artifact hook 发布实际线性 logit 蓝图，不直接 pickle 活 Python 包装器；这不是通用自动加载器。本例不拟合外部 estimator，默认恢复只重建解码模型，不再次求值。

```python
# cases/linear_point/adapter/__init__.py
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter

def build_adapter():
    return build_optimization_adapter("search.random_gaussian", population_size=8,
        mutation_scale=.25, random_seed=17, objective_aggregation="first")
```

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides
from .config import N_CLASSES
from .pipeline.main import build_pipeline, build_representation
from .problem import build_problem
from .adapter import build_adapter

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {"max_steps": 8, **dict(config or {})}
    data = build_pipeline(N_CLASSES)
    solver = build_learning_solver(problem=build_problem(data),
        representation=build_representation(data, N_CLASSES), adapter=build_adapter(),
        compute_backend="numpy", resource_context=resource_context,
        run_name="tabular_classification")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

```python
# run_classification_and_report.py
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
    if value.best_feedback is None:
        raise ValueError("no evaluated classification feedback")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "metrics": dict(value.best_feedback.metrics),
        "signals": dict(value.best_feedback.signals),
        "best_model_ref": None if value.best_model_ref is None else value.best_model_ref.as_dict()}
    path = root / "results" / "classification.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False,
        allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 新报告中 objectives 只有一项，等于 `train.log_loss`；train/valid 都有 accuracy/error_rate/log_loss、宏平均 precision/recall/f1；二分类另有 auc_roc/average_precision 等。当前 Problem 返回的 `primary_prefix` 为 train，没有梯度，故不装 gradient.sgd。准确率只观测、不要求八步达到某阈值。**分类 Problem 对 predict_proba 直接取 argmax，不调用模型 predict；调 BinaryLogisticHead.threshold 不会改变本 Problem 的 accuracy/error_rate。** 本例保留 .5。若业务需要非 .5 决策阈值，应明确实现自己的指标/Problem，而不能把显示参数当作已生效。验证类别在固定 classes 内；代码不会自动替用户检查未知类别，接入真实数据时先做词表验证。

**运行入口：** 在副本根执行 `python run_project.py --check --build-check`，然后 `python run_classification_and_report.py`。只运行原默认单 Case 一次。读正式 TrainerResult.best_feedback 与 best_model_ref，不假定 report 或 best_model 永远内联，不重新训练来“读取”结果。旧 JSON/构造成功/本页静态检查均不替代运行收据。

### 变体一：同时切换数据规则、参数块与类别词表

**目的：** 保持同一 Case 与外层执行结构，变成三分类而不误用二分类一个 logit。

**改在哪里：** 从本节主例完整替换 config.py，其它文件已共同消费这个值。

```python
# cases/linear_point/config.py
N_CLASSES = 3
```

**行为变化：** 标签由三个线性分数的 argmax 产生；SoftmaxHead 创建三块 logit，9 参数，概率列对应 `(0,1,2)`。Artifact 同时变为三个线性蓝图。仍以训练 log_loss 为唯一目标，验证只报告。

**限制：** 参数含义变了，要新建运行或使用匹配的恢复状态；不能恢复旧三参数 checkpoint。softmax 不是三个互不约束的二分类概率；本例不覆盖多标签分类、类别不平衡加权或概率校准。

源码依据：`mlblack/representations/heads/probability.py`、`models/probability.py`、`problems/classification.py`、`representations/linear_point.py`、`core/artifact_provider.py`。

## mlblack.problem.supervised_interval_regression · 预测上下界与覆盖约束

**什么时候用：** 希望解码得到预测区间，并同时衡量宽度、漏覆盖距离与覆盖率。实际使用 `mlblack.model.center_radius_interval`；变体使用 `mlblack.model.interval_prediction`。它不是 Normal 分布、不提供“90%置信保证”，target_coverage 是本样本上的目标约束。

**先准备什么：** 使用 `catalog_codec_demo` 第三份独立副本，保留默认 Project/L0/Case。两特征连续标签：32 行训练、12 行独立验证；噪声在建数据时固定一次，不在每次求值时重抽。默认只按训练样本评分，验证指标用于观察。无 Torch、外部服务或预训练依赖。

**放在哪：** 完整替换 `cases/linear_point` 的 config、pipeline/main、problem、adapter、build_solver 五个文件。保留已有规范入口与 pipeline 包导出。新增 Project 根 `run_interval_and_report.py`。

**接入步骤：** 主例使用中心/半径结构，两个三参数线性块共六参数。

```python
# cases/linear_point/config.py
MODE = "center_radius"
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import NumericDataView
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import CenterRadiusIntervalHead, TwoModelIntervalHead

def build_pipeline():
    rng = np.random.default_rng(17)
    X = rng.uniform(-1., 1., (32, 2))
    V = rng.uniform(-1., 1., (12, 2))
    def target(a):
        return 1. + a[:, 0] - .4*a[:, 1] + rng.normal(0., .1, len(a))
    return NumericDataView(X_train=X, y_train=target(X),
        X_valid=V, y_valid=target(V), feature_names=("x0", "x1"))

def build_representation(data, mode):
    if mode == "center_radius":
        head = CenterRadiusIntervalHead(radius_transform="softplus")
    elif mode == "two_model":
        head = TwoModelIntervalHead(enforce_order=True)
    else:
        raise ValueError("unknown interval layout")
    return LinearPointRepresentation(LinearPointConfig(n_features=data.n_features,
        feature_names=data.effective_feature_names, random_seed=17), head=head)
```

CenterRadiusIntervalHead 把前半参数解释成中心、后半成 raw radius，softplus 使半径非负，predict_interval 返回两个 `(n,)` 数组。`predict` 返回 `(n,2)` 上下界；不能塞进点回归 Problem 的 reshape(-1) 路径。

```python
# cases/linear_point/problem/__init__.py
from mlblack.models import CenterRadiusIntervalModel, IntervalPredictionModel
from mlblack.problems import SupervisedIntervalRegressionProblem

class IntervalProblem(SupervisedIntervalRegressionProblem):
    def build_model_artifact(self, model, context):
        if isinstance(model, CenterRadiusIntervalModel):
            return {"schema": "case.linear_interval/v1", "kind": "center_radius",
                "radius_transform": model.radius_transform,
                "blocks": [model.center_model.as_dict(), model.radius_model.as_dict()]}
        if isinstance(model, IntervalPredictionModel):
            return {"schema": "case.linear_interval/v1", "kind": "two_model",
                "enforce_order": model.enforce_order,
                "blocks": [model.lower_model.as_dict(), model.upper_model.as_dict()]}
        raise TypeError("unexpected interval model")

def build_problem(data):
    return IntervalProblem(data, target_coverage=.9, width_weight=1.,
        miss_weight=10., use_valid_objective=False)
```

Artifact 发布区间模式与两个真实线性参数块，避免 pickle；没有自动加载保证。原 Problem 返回三目标 `[width + 10*miss, width, miss]` 和一个 signed constraint `[.9-coverage]`；控制面按正违反量处理。宽度与 miss 都是非负量，但约束负值表示达到了该样本覆盖要求。

```python
# cases/linear_point/adapter/__init__.py
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter

def build_adapter():
    return build_optimization_adapter("search.random_gaussian", population_size=8,
        mutation_scale=.25, random_seed=17, objective_aggregation="sum")
```

这里显式选择 sum，使 Adapter 与 Solver 默认最终 scalarizer 一致：在可行性比较之后比较三个 raw 目标之和，即 `2*width + 11*miss`。它**不是**只优化第一目标。若你想第一目标唯一主导，需要同时配置真正的最终比较契约，不要只改 Adapter 参数后误读结果为同一个偏好。本节选透明的一致默认，不声称多目标 Pareto 搜索。

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides
from .config import MODE
from .pipeline.main import build_pipeline, build_representation
from .problem import build_problem
from .adapter import build_adapter

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {"max_steps": 8, **dict(config or {})}
    data = build_pipeline()
    solver = build_learning_solver(problem=build_problem(data),
        representation=build_representation(data, MODE), adapter=build_adapter(),
        compute_backend="numpy", resource_context=resource_context,
        run_name="tabular_interval")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

```python
# run_interval_and_report.py
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
    if value.best_feedback is None:
        raise ValueError("no evaluated interval feedback")
    payload = {"run_id": run.run_id, "objectives": value.best_objectives.tolist(),
        "constraints": value.best_feedback.constraints.tolist(),
        "metrics": dict(value.best_feedback.metrics),
        "best_model_ref": None if value.best_model_ref is None else value.best_model_ref.as_dict()}
    path = root / "results" / "interval.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False,
        allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

**怎样判断接对：** 对本次 `results/interval.json` 核对 run_id、三项目标、一项 constraints 和 train/valid 的 coverage/mean_width/mean_miss_distance/center_mse。主例 objectives[0] 应等于 `train.mean_width + 10*train.mean_miss_distance`，constraint[0] 为 `.9-train.coverage`。loss 是第一目标，不等于三个目标之和；残差是区间中心减标签，不是 miss。八步小搜索完全可能没有可行模型，报告应如实呈现正违反量，不能把“运行结束”写成“已达90%覆盖”。

**运行入口：** 在副本根执行 `python run_project.py --check --build-check`，然后 `python run_interval_and_report.py`。正式 Project 负责 L0 与发布；模型引用在 finalization 成功后读取，JSON 是结果观察副本。这里没有额外硬接纳过滤，所以不可行候选仍可被算法比较；无梯度的 Problem 不应装 SGD。仅静态源码检查，未实际运行。

### 变体一：两个独立边界模型，由输出层保证顺序

**目的：** 表达两个边界不同的线性趋势，使用已有上下界模型而不手工在 Adapter 内裁剪输出。

**改在哪里：** 从本节主例完整替换 config.py，其余工厂已有真实分支。

```python
# cases/linear_point/config.py
MODE = "two_model"
```

**行为变化：** 两个三参数块现在是 lower/upper；IntervalPredictionModel 在预测时逐行取 min/max，保持上下界有序。目标、覆盖约束、运行与 Artifact 发布链不变，Artifact kind 同步变为 two_model。

**限制：** 虽然仍为六参数，语义已改变，不能直接恢复 center/radius checkpoint。min/max 排序会交换上下界模型角色，不代表训练了两个固定分位数，也不保证样本外90%覆盖。若关闭 enforce_order，当前 Problem 的 width 用 max(upper-lower,0)，不足以单独惩罚所有交叉边界；本例明确保持 True。

源码依据：`mlblack/representations/heads/interval.py`、`models/outputs.py`、`problems/supervised.py::SupervisedIntervalRegressionProblem/_interval_metrics`、`integrations/nsgablack_control.py`、`core/artifact_provider.py`；`nsgablack/adapters/gaussian_search/adapter.py` 的原始可行性及聚合比较。
