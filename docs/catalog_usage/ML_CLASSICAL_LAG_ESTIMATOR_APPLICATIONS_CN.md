# 滞后估计器：先冻结训练模型，再做递归验证

本例按源码静态核对，未执行数据构造、拟合、预测或Project。使用 `mlblack/examples/cases/catalog_codec_demo/` 的独立完整副本，保留原 Project/default 的 linear_point Case 和 L0。这里明确补齐本Case的训练边界与只读恢复，不假定任意第三方估计器都能这样保存。

## classical.lag_estimator

**什么时候用：** 已有fit/predict估计器，希望它吃lag特征后递归预测。本例实际使用 `LagEstimatorForecastModel.fit` / `forecast`，训练只发生在Problem.prepare，之后forecast不因history改变而自动重新拟合。这与自带 LinearAutoregressiveForecastModel 的history-refit语义不同。

**先准备什么：** 三仓、NumPy、完整Project副本。48条合成日序列，最后8条留出；训练段40条。lags=(1,2,7)，horizon=1，训练窗口不再拆验证，因此训练窗口数为40-7=33。lag1是预测起点当下的已知值，目标是下一步；不是把未来值混入训练输入。

**放在哪：** 新增 Case pipeline/ridge.py，完整内容见本书下一节。替换 config.py、pipeline/main.py、problem/__init__.py、build_solver.py；保存 `ML_CLASSICAL_ESTIMATOR_APPLICATIONS_CN.md` 的 classical.estimator.run 节完整报告入口。其余旧工厂不被新builder使用。

**接入步骤：** 以下是其余完整文件。ForecastModelSpecRepresentation只带一个配置哨兵，不在decode拟合；Problem显式截取40点训练前缀，随后调用已存在的LagEstimatorForecastModel.fit。

```python
# cases/linear_point/config.py
RIDGE = .1
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import TimeSeriesDataView
from mlblack.pipeline.time_series import TimeSeriesWindowConfig
from mlblack.representations import ForecastModelSpecRepresentation

def build_pipeline():
    t = np.arange(48, dtype=float)
    return TimeSeriesDataView(y=10.+.1*t+2.*np.sin(2.*np.pi*t/7.),
        time_index=tuple(range(48)), target_name="demand", frequency="D")

def window_config():
    return TimeSeriesWindowConfig(lags=(1, 2, 7), horizon=1,
                                 valid_size=0, include_exogenous=False)

def build_representation():
    return ForecastModelSpecRepresentation({"kind": "case_ridge_lag_fit"})
```

```python
# cases/linear_point/problem/__init__.py
from dataclasses import replace
import numpy as np
from mlblack.models.time_series import LagEstimatorForecastModel
from mlblack.pipeline.data_views import TimeSeriesDataView
from mlblack.problems import TimeSeriesForecastingProblem
from ..config import RIDGE
from ..pipeline.ridge import RidgeEstimator
from ..pipeline.main import window_config

class FrozenLagProblem(TimeSeriesForecastingProblem):
    def prepare_model_for_evaluation(self, model, state, context):
        if model != {"kind": "case_ridge_lag_fit"}:
            raise TypeError("unexpected lag estimator specification")
        train = TimeSeriesDataView(y=self.data.y[:-8],
            time_index=self.data.time_index[:-8], target_name=self.data.target_name,
            frequency=self.data.frequency)
        return LagEstimatorForecastModel.fit(RidgeEstimator(RIDGE), train,
            window_config(), metadata={"fit_history_size": 40})

    def evaluate(self, model, state, context):
        if not isinstance(model, LagEstimatorForecastModel):
            raise TypeError("expected frozen fitted lag estimator")
        feedback = super().evaluate(model, state, context)
        coefficients = np.asarray(model.estimator.coef_, dtype=float)
        if coefficients.shape != (4,) or not np.all(np.isfinite(coefficients)):
            raise ValueError("invalid fitted lag coefficients")
        return replace(feedback, info={**dict(feedback.info),
            "case_lag_coefficients": coefficients.tolist(),
            "case_lag_ridge": float(model.estimator.ridge)})

    def restore_model_for_evaluation(self, model, state, feedback, context):
        coef = np.asarray(feedback.info["case_lag_coefficients"], dtype=float)
        if coef.shape != (4,) or not np.all(np.isfinite(coef)):
            raise ValueError("missing fitted lag evidence")
        estimator = RidgeEstimator(feedback.info["case_lag_ridge"])
        estimator.coef_ = coef.copy()
        estimator.n_features_in_ = 3
        return LagEstimatorForecastModel(estimator=estimator,
            window_config=window_config(), feature_names=("lag_1", "lag_2", "lag_7"),
            metadata={"fit_history_size": 40})

    def build_model_artifact(self, model, context):
        if not isinstance(model, LagEstimatorForecastModel):
            raise TypeError("refuse to publish an unfitted spec")
        return {"schema": "case.frozen_lag_ridge/v1", "model": model.describe(),
            "coefficients": model.estimator.coef_.tolist(),
            "ridge": float(model.estimator.ridge), "fit_history_size": 40,
            "training_history": self.data.y[:-8].tolist()}

def build_problem(data):
    return FrozenLagProblem(data, validation_size=8,
                            objective_metrics=("valid.rmse",), seasonal_period=7)
```

```python
# cases/linear_point/build_solver.py
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.adapters import FixedCandidateAdapter
from .pipeline.main import build_pipeline, build_representation
from .problem import build_problem

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit components")
    solver = build_learning_solver(problem=build_problem(build_pipeline()),
        representation=build_representation(), adapter=FixedCandidateAdapter(),
        compute_backend="numpy", resource_context=resource_context,
        run_name="catalog_frozen_lag_ridge")
    solver.set_bias_module(None, enable=False)
    solver.set_max_steps(1)
    return solver
```

原LagEstimatorForecastModel.forecast只调用已拟合estimator.predict；每次预测追加预测值，递归8步，不灌入验证真值。由于本例在Problem准备期只训练前40条，验证对象与发布Artifact使用同一组四系数，没有“先用完整序列训练、再临时refit前缀”的额外语义。restore只按保存的反馈系数构造估计器，既不fit也不重算反馈；layout/ridge仍须随原Case配置匹配，不能跨不同lag结构恢复。

**怎样判断接对：** classical.json单目标与loss为valid.rmse，metrics包含history_size40/validation_size8。候选仍只有一个哨兵，不能把它称ridge搜索；模型蓝图有截距+3lag系数、窗口和已知历史。best_model_ref交付原生JSON，不能按model.describe中estimator_type字段重建任意估计器。需要预测时，从已验证蓝图恢复相同RidgeEstimator.coef_并构造相同LagEstimatorForecastModel，不能重新fit验证段。

**运行入口：** 副本根先 `python run_project.py --check --build-check`，再 `python run_classical_and_report.py`，一次正式Project返回指标与引用。原L0授权直接注入，不额外分配线程。这里未运行测试或训练，静态hooks不能代替真实checkpoint往返验收。

### 变体：改变训练正则，不变验证边界

**目的：** 检查相同33个训练窗口上更强的系数收缩。**改在哪里：** config.py完整替换如下。

```python
RIDGE = 1.
```

**行为变化：** 训练拟合的对角惩罚增大，四系数和预测可能改变；截距不惩罚，验证与递归策略不变。**限制：** 更强正则不保证更好，不自动搜索超参数；使用验证反复选择ridge后，该尾段已参与模型选择，需另留最终测试区间。

来源：mlblack `models/time_series.py` 的 LagEstimatorForecastModel、`pipeline/time_series.py` 的lag索引和递归契约、`problems/time_series.py` 与共享只读模型恢复协议。

## classical.lag_estimator.ridge

同一Case的完整 `pipeline/ridge.py`，只实现被原LagEstimatorForecastModel消费的fit/predict契约，不拥有控制循环或Project资源。

```python
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
```
