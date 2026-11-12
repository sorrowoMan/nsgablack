# 传统估计器：搜索的是拟合配置，交付的是已拟合模型

所有代码均按当前源码静态核对；本轮没有运行拟合、算法、Project 或网络请求。每个主例使用 mlblack `examples/cases/catalog_codec_demo/` 的独立完整副本，保留原 Project L0、默认 linear 组、Case `linear_point`、包入口与别名。不要只复制一个 build_solver.py。

## classical.estimator.ridge

**什么时候用：** 外部方法有 `fit(X,y)` / `predict(X)`，希望 Adapter 搜索其超参数，而不是把它的已拟合权重误当成搜索向量。本例只用 NumPy 实现一个可完整保存的岭回归估计器，实际消费 EstimatorSpecRepresentation、EstimatorSpecCodec、TunableParameterSpec、EstimatorSpecModel、FittedEstimatorModel 和 SupervisedEstimatorFitRegressionProblem。

**先准备什么：** 三仓、NumPy、上述完整 Project 副本。训练与验证分别构造，不在验证集拟合；只有一个搜索坐标 ridge∈[0,2]，候选不是三维线性权重。`problem.supervised_estimator_fit` 与 `problem.supervised_estimator_fit_regression` 当前索引到同一回归类，不是两种训练算法。

**放在哪：** 以下路径相对 Project 副本。替换 `pipeline/main.py`、`problem/__init__.py`、`adapter/__init__.py`、`build_solver.py`，新增 `pipeline/ridge.py`；原 pipeline 包仍能导出 build_pipeline。再保存下节共用的结果入口。

**接入步骤：** 工厂只构造未拟合对象。原 Problem 在正式送评中调用 fit，然后包装 FittedEstimatorModel，计算真实训练与验证指标。Case 子类只补齐本模型的持久系数、只读恢复和安全 Artifact，不重造训练循环。

```python
# cases/linear_point/pipeline/ridge.py
import numpy as np

class RidgeEstimator:
    def __init__(self, ridge=0.):
        self.ridge = float(ridge)
        self.coef_ = None

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        design = np.column_stack([np.ones(len(X)), X])
        penalty = self.ridge*np.eye(design.shape[1])
        penalty[0, 0] = 0.
        self.coef_ = np.linalg.solve(design.T@design + penalty,
                                     design.T@np.asarray(y, dtype=float))
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X):
        if self.coef_ is None:
            raise RuntimeError("unfitted ridge")
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != len(self.coef_)-1:
            raise ValueError("feature layout differs from fitted coefficients")
        return np.column_stack([np.ones(len(X)), X]) @ self.coef_

def make_ridge(params):
    return RidgeEstimator(ridge=params["ridge"])
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import NumericDataView
from mlblack.representations.estimator_specs import EstimatorRouteConfig, EstimatorSpecRepresentation
from mlblack.representations.codecs.estimators import TunableParameterSpec
from .ridge import make_ridge

def build_pipeline():
    rng = np.random.default_rng(17)
    X = rng.normal(size=(24, 2))
    y = 1. + 2.*X[:, 0] - .5*X[:, 1] + .15*rng.normal(size=24)
    return NumericDataView(X_train=X[:16], y_train=y[:16],
        X_valid=X[16:], y_valid=y[16:], feature_names=("a", "b"))

def build_representation():
    return EstimatorSpecRepresentation(EstimatorRouteConfig(
        family="case_ridge", route="ridge", factory=make_ridge,
        tunables=(TunableParameterSpec("ridge", low=0., high=2.),)))
```

```python
# cases/linear_point/problem/__init__.py
from dataclasses import replace
import numpy as np
from mlblack.models.estimators import EstimatorSpecModel, FittedEstimatorModel
from mlblack.problems import SupervisedEstimatorFitRegressionProblem
from ..pipeline.ridge import RidgeEstimator

class PortableRidgeProblem(SupervisedEstimatorFitRegressionProblem):
    def evaluate(self, model, state, context):
        feedback = super().evaluate(model, state, context)
        if not isinstance(model, FittedEstimatorModel):
            raise TypeError("expected fitted ridge wrapper")
        coef = np.asarray(model.estimator.coef_, dtype=float)
        if coef.shape != (3,) or not np.all(np.isfinite(coef)):
            raise ValueError("invalid ridge coefficient evidence")
        return replace(feedback, info={**dict(feedback.info),
            "case_ridge_coefficients": coef.tolist()})

    def restore_model_for_evaluation(self, model, state, feedback, context):
        if not isinstance(model, EstimatorSpecModel):
            raise TypeError("expected original decoded ridge specification")
        coef = np.asarray(feedback.info["case_ridge_coefficients"], dtype=float)
        if coef.shape != (3,) or not np.all(np.isfinite(coef)):
            raise ValueError("missing portable fitted ridge evidence")
        estimator = RidgeEstimator(model.params["ridge"])
        estimator.coef_ = coef.copy()
        estimator.n_features_in_ = 2
        return FittedEstimatorModel(estimator, model.family, model.route,
                                    params=dict(model.params))

    def build_model_artifact(self, model, context):
        if not isinstance(model, FittedEstimatorModel):
            raise TypeError("refuse to publish an unfitted specification")
        return {"schema": "case.ridge/v1", "feature_names": ["a", "b"],
            "ridge": float(model.params["ridge"]),
            "coefficients": model.estimator.coef_.tolist()}

def build_problem(data):
    return PortableRidgeProblem(data, use_valid_objective=True,
                                complexity_weight=0.)
```

默认 Problem 的 EstimatorStateArtifact 包装活估计器；它的 fitted_state_summary 只是摘要，不是任何 sklearn 模型的通用加载器。本例只为明确的三系数模型发布 JSON 蓝图。恢复只从已保存反馈还原系数，禁止重新 fit；这不是所有第三方估计器均可恢复的承诺。

```python
# cases/linear_point/adapter/__init__.py
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter

def build_adapter():
    return build_optimization_adapter("search.random_gaussian", population_size=4,
        mutation_scale=.3, random_seed=17, objective_aggregation="first")
```

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides
from .pipeline.main import build_pipeline, build_representation
from .problem import build_problem
from .adapter import build_adapter

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {"max_steps": 4, **dict(config or {})}
    solver = build_learning_solver(problem=build_problem(build_pipeline()),
        representation=build_representation(), adapter=build_adapter(),
        compute_backend="numpy", resource_context=resource_context,
        run_name="catalog_ridge_estimator")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(int(settings["max_steps"]))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

**怎样判断接对：** 读下节 JSON：候选仅一个 ridge 参数；原始目标 `[valid.mse,0]`，loss 是 train.mse，不能混读。metrics 包含 train/valid 的 mse/rmse/mae/r2，以及 estimator.family/route/type 与实际 fit 生命周期摘要；best_model_ref 指向已拟合系数蓝图，不能把 EstimatorSpecModel 当拟合结果。一个候选送评对应一次 fit；Gaussian 不会拿解析梯度优化系数。

**运行入口：** 保存下节结果入口后，在副本根 `python run_project.py --check --build-check`，再 `python run_classical_and_report.py`，正式 Project 只运行一次。原 L0 注入 resource_context，Case 不分配全局线程；NumPy 依赖可用性、运行效果和 checkpoint 行为都须以后真实验收。本轮只有静态检查。

### 变体：固定岭强度，使用相同 Codec 路线

**目的：** 不搜索超参数，只验证同一 estimator.fit 交付链。

**改在哪里：** 将 pipeline/main.py 中 build_representation 完整替换如下，同时把 adapter 工厂替换为固定候选；其他文件不变。

```python
def build_representation():
    return EstimatorSpecRepresentation(EstimatorRouteConfig(
        family="case_ridge", route="ridge", factory=make_ridge,
        tunables=(TunableParameterSpec("ridge", low=.25, high=.25),)))
```

```python
# cases/linear_point/adapter/__init__.py
from nsgablack.adapters import FixedCandidateAdapter

def build_adapter():
    return FixedCandidateAdapter()
```

**行为变化：** 保留一个上下界相等的真实 ridge 坐标，所有系数由这次 Problem.fit 决定，固定 Adapter 完成后自然结束，不执行四次重复拟合。**限制：** 当前 EstimatorSpecCodec 没有 ForecastModelSpecRepresentation 那种自动哨兵：零 tunable 会产生零维向量，不宜直接送入要求非空候选的搜索控制面。换成另一种估计器必须同步更换 factory、Artifact 和只读恢复逻辑，不能仅替换类名。

## classical.estimator.run

以下文件可复用于本书和明确引用本节的传统预测主例。保留默认 linear 组，仅选 `linear_point`，从一次正式 Project 的可传输 Case 输出读取结果。

```python
# run_classical_and_report.py
import json
from pathlib import Path
from blackbase.types import TrainerResult
from mlblack.project.project_runner import execute_project

def main():
    root = Path(__file__).resolve().parent
    run = execute_project(root)
    case = next(x for x in run.case_results if x.request.case_name == "linear_point")
    case.raise_for_failure()
    value = TrainerResult.from_dict(case.output)
    if value.best_feedback is None:
        raise RuntimeError("no evaluated incumbent")
    payload = {"run_id": run.run_id,
        "state": value.best_state.as_array().tolist(),
        "loss": value.best_feedback.loss,
        "objectives": value.best_objectives.tolist(),
        "metrics": dict(value.best_feedback.metrics),
        "signals": dict(value.best_feedback.signals),
        "model_ref": None if value.best_model_ref is None else value.best_model_ref.as_dict()}
    path = root/"results"/"classical.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False,
                              allow_nan=False, indent=2), encoding="utf-8")
    return run.exit_code

if __name__ == "__main__":
    raise SystemExit(main())
```

结果输出不是 Artifact 的替代。检查本次 run_id、Case 状态、引用收据后再读取模型；旧报告不证明本次成功。源码依据为 mlblack 的 `representations/estimator_specs.py`、`representations/codecs/estimators.py`、`models/estimators.py`、`problems/supervised.py`、`core/problem.py` 与 `integrations/nsgablack_control.py`。
