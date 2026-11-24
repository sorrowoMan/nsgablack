# 传统预测：同一正式 Case 下区分基线搜索、固定拟合与诊断

本书只进行了源码和文档静态核对，没有执行拟合、预测、Project、数据库或下载。每个主例用 `mlblack/examples/cases/catalog_codec_demo/` 的独立完整副本，保留原 Project/default 的 linear_point Case 和 L0；不要把不同主例的文件混在一起。

## classical.forecast.presets

**什么时候用：** 在同一条有序序列上比较朴素策略搜索、线性自回归或 NumPy AR/SARX。三个分支实际调用不同 preset；不是把每种模型都当 Gaussian 可训练权重。需要完整 MA 项最大似然的 statsmodels 路线见迁移说明，不把 NumPy fallback 叫完整 SARIMAX。

**先准备什么：** 三仓、NumPy和完整 Project 副本。48 条合成日序列，最后 8 条连续留出。外生变量关闭；没有验证真值逐步回灌，也不把这个已用于选择的尾段叫独立最终测试集。

**放在哪：** 替换 Case config.py、pipeline/main.py、build_solver.py，新增 runtime/forecast_format.py；旧 problem/adapter 工厂保留但本 builder 使用 preset 内置工厂。保存本书引用的 `ML_CLASSICAL_ESTIMATOR_APPLICATIONS_CN.md` 的 `classical.estimator.run` 节完整 run_classical_and_report.py。

**接入步骤：** 先保存下列配置、数据和安全 Serializer；下一节继续 builder、结果解释与变体。

```python
# cases/linear_point/config.py
MODE = "baseline"  # baseline / linear_ar / arx
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import TimeSeriesDataView

def build_pipeline():
    t = np.arange(48, dtype=float)
    y = 10. + .1*t + 2.*np.sin(2.*np.pi*t/7.)
    return TimeSeriesDataView.from_values(y, time_index=tuple(range(48)),
        target_name="demand", frequency="D", sort_by_time=True)
```

模型的 describe 不一定包含完整预测所需历史；以下 Serializer 保存真实已拟合对象的历史与参数，而不是只写一个类名或返回活对象。它通过现有 CaseRuntimeArtifactProvider 参与统一发布事务。

```python
# cases/linear_point/runtime/forecast_format.py
import json
from pathlib import Path
import numpy as np
from blackbase.resources import ArtifactSerializer
from mlblack.models.time_series import (NaiveForecastModel,
    LinearAutoregressiveForecastModel, ARIMASARIMAXForecastModel)

def dump_forecast(model, path):
    if not isinstance(model, (NaiveForecastModel,
            LinearAutoregressiveForecastModel, ARIMASARIMAXForecastModel)):
        raise TypeError("no safe serializer for this forecast model")
    payload = {"schema": "case.forecast/v1", "model": model.describe()}
    if not isinstance(model, NaiveForecastModel):
        payload["training_history"] = np.asarray(model.training_history).tolist()
        payload["training_exogenous"] = (None if model.training_exogenous is None
            else np.asarray(model.training_exogenous).tolist())
    if isinstance(model, ARIMASARIMAXForecastModel):
        payload["differenced_history"] = model.differenced_history.tolist()
    Path(path).write_text(json.dumps(payload, ensure_ascii=False,
                                    allow_nan=False), encoding="utf-8")

def select_serializer(model):
    return ArtifactSerializer(name="case_forecast_json", extension=".json",
        media_type="application/json", dump=dump_forecast)
```

本 Case 的 JSON 是可传输蓝图，不声称框架自带通用加载器。只读重建原对象的完整工具如下；函数只构造模型，不调用 fit/forecast，也不自行读 Artifact 路径。真实调用前按正式 ModelRef 获取并验证本次发布的文件。

```python
# 接在 cases/linear_point/runtime/forecast_format.py 后
from mlblack.models.time_series import ARIMASARIMAXSpec
from mlblack.pipeline.time_series import TimeSeriesWindowConfig

def from_blueprint(payload):
    if payload.get("schema") != "case.forecast/v1":
        raise ValueError("unknown forecast artifact schema")
    m = dict(payload["model"])
    kind = m.pop("model_type")
    if kind == "naive_forecast":
        return NaiveForecastModel(**m)
    history = np.asarray(payload["training_history"], dtype=float)
    exog = payload["training_exogenous"]
    if kind == "linear_autoregressive_forecast":
        return LinearAutoregressiveForecastModel(intercept=m["intercept"],
            weights=m["weights"], window_config=TimeSeriesWindowConfig(**m["window_config"]),
            feature_names=m["feature_names"], training_history=history,
            training_exogenous=exog, metadata=m["metadata"])
    if kind == "arima_sarimax_forecast":
        return ARIMASARIMAXForecastModel(spec=ARIMASARIMAXSpec(**m["spec"]),
            intercept=m["intercept"], ar_params=m["ar_params"],
            seasonal_ar_params=m["seasonal_ar_params"], exog_params=m["exog_params"],
            training_history=history, training_exogenous=exog,
            differenced_history=payload["differenced_history"], metadata=m["metadata"])
    raise ValueError("unsupported forecast model type")
```

该工具不等于 LearningProblem 的 checkpoint restore hook；默认 TimeSeriesForecastingProblem 覆盖了 prepare，却没有只读 restore。当前预设路线的训练期恢复仍不能据此宣称已支持。需要那项能力时，按估计器主例设计明确的反馈模型状态与 Problem.restore_model_for_evaluation，不可恢复时重新 fit。

## classical.forecast.presets.wiring

以下继续同一主例。完整 build_solver.py：

```python
from mlblack.presets import (build_baseline_forecast_search_trainer,
    build_linear_autoregressive_forecast_trainer, build_arima_sarimax_forecast_trainer)
from mlblack.core.artifact_provider import CaseRuntimeArtifactProvider
from .config import MODE
from .pipeline.main import build_pipeline
from .runtime.forecast_format import select_serializer

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit Case factories")
    data = build_pipeline()
    common = dict(validation_size=8, objective_metrics=("valid.rmse",),
                  seasonal_period=7, run_name="catalog_forecast_"+MODE)
    if MODE == "baseline":
        solver = build_baseline_forecast_search_trainer(data,
            strategies=("naive", "seasonal_naive", "moving_average"),
            window_bounds=(2, 7), seasonal_period_bounds=(7, 7),
            population_size=4, mutation_scale=.4, **common)
    elif MODE == "linear_ar":
        solver = build_linear_autoregressive_forecast_trainer(data,
            lags=(1, 2, 7), horizon=1, ridge=.01, include_exogenous=False, **common)
    elif MODE == "arx":
        solver = build_arima_sarimax_forecast_trainer(data, order=(2, 0, 0),
            seasonal_order=(1, 0, 0, 7), trend="c", backend="numpy_fallback", **common)
    else:
        raise ValueError("unknown forecast mode")
    if resource_context is not None:
        solver.set_resource_context(resource_context)
    solver.set_artifact_provider(CaseRuntimeArtifactProvider(serializer_selector=select_serializer))
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(4)
    return solver
```

三个 preset 没有显式 resource_context 参数，额外参数会传给 Problem；不能在调用 preset 时塞 resource_context，再假定授权已经绑定。本例运行前用已有 setter 接受 Project L0 grant，不制造私有资源。baseline 的 Representation 内部默认 seed 为42，与控制面的 seed17不同，不能声称一个 seed 覆盖所有组件。

**怎样判断接对：** `results/classical.json` 单目标/损失等于 valid.rmse，metrics 还含 valid.mae/mse/mape/smape/mase 和验证/历史大小。正确输出应为 history_size40、validation_size8，而不是训练误差。原始目标只有一项，不依赖求和/最大化猜测。Artifact 有 schema、模型参数、实际历史；基线没有数据拟合权重，另两分支有真实拟合系数。

baseline 用三坐标策略/窗口/季节长度，BaselineForecastSearchConfig→BaselineForecastRepresentation→NaiveForecastModel，Gaussian多轮搜索。linear_ar 和 arx 则用 ForecastModelSpecRepresentation 的**一维身份哨兵**，FixedCandidateAdapter只评估一个声明拟合请求；max_steps4不意味着重复拟合四次。LinearAutoregressiveFitSpec 持有窗口配置，ARIMASARIMAXSpec 持有阶数和后端，拟合由原 TimeSeriesForecastingProblem/Provider承担，不在 decode 中执行。

必须理解现有语义：Problem.prepare 对完整序列拟合。线性模型内部 build_lagged_numeric_view 又按窗口配置的 valid_size=.2 使用前段窗口拟合；当 evaluate 传入40点history时，已拟合模型发现其与 training_history48点不同，会对40点历史**重新拟合**再递归预测8步。NumPy ARX也在history不同时重新拟合，因此尾段评估不直接读取后8点目标，但一次送评可能包含多次拟合。最后发布的是最初完整序列模型，**不是验证时临时前缀模型**。以后改history调用forecast仍会触发拟合；它不是参数固定的廉价推理器，也不能把其系数直接归因于验证预测。

NumPy路线仅实现AR/SARX加有限差分：d/D∈{0,1}；q/Q非零只记入ignored_ma_terms而不建MA递推。本例明确q=Q=0。线性窗口horizon设1，与递归单步预测对齐；不要随意改成多步horizon却继续宣称一步递推。

**运行入口：** 在独立副本根先 `python run_project.py --check --build-check`，再 `python run_classical_and_report.py`，后者只运行一次正式 Project。核对新 run_id、Case终态、model_ref与蓝图，不能拿旧文件称本轮完成。本轮未执行这些命令，也未验证预测效果或checkpoint恢复。

### 变体一：将策略搜索替换为固定线性自回归

**目的：** 不再优化策略编号，使用lags1/2/7的声明拟合。

**改在哪里：** config.py完整替换如下，其余文件已有该分支。

```python
MODE = "linear_ar"
```

**行为变化：** 候选维度从3变为1哨兵，Gaussian变为Fixed；模型Artifact从基线规则变为截距/三个lag系数/窗口/历史。**限制：** 不是梯度训练，也没有搜索lags或ridge；内部窗口留出和前缀refit行为如上。

### 变体二：显式季节AR/SARX近似

**目的：** 加入lag7的季节自回归项。

**改在哪里：** config.py完整替换如下：

```python
MODE = "arx"
```

**行为变化：** 用ARIMASARIMAXProvider拟合AR2+季节AR1，Artifact含两项ar_params和一项seasonal_ar_params。**限制：** 无外生变量时exog_params为空；此处的ARX名称表示支持该结构族，不代表本例真的使用了外生数据。不得仅把q改为1便宣称完整ARIMA。

## classical.forecast.statsmodels.boundary

**什么时候用：** 确实需要MA项、似然估计或statsmodels的完整SARIMAX结果时。这是当前组件的迁移说明，尚不是本书已闭合交付的训练Case。

**先准备什么：** 本地statsmodels/pandas等依赖、合法阶数与有足够历史的数据；Provider backend="statsmodels"实际构造StatsmodelsSARIMAXForecastModel。NumPy fallback不是自动等价替代。

**放在哪：** 阶数/后端归Case的pipeline/model spec，拟合归Problem/Provider，result持久化归显式安全Artifact格式。不能把statsmodels Results对象塞context、直接JSON化或启用unsafe pickle后称安全模型交付。

**接入步骤：** 以下只构造并检查声明，不执行fit；完整NumPy正式Case可用前两节。Statsmodels模型的describe只有阶数/类名/aic/bic/metadata，不含所有参数和滤波状态，不能按describe重建已拟合结果。

```python
from mlblack.models.time_series import ARIMASARIMAXSpec, ARIMASARIMAXProvider

def build_requested_provider():
    spec = ARIMASARIMAXSpec(order=(1, 0, 1), seasonal_order=(0, 0, 0, 0),
                           backend="statsmodels", include_exogenous=False)
    return ARIMASARIMAXProvider(spec)
```

**怎样判断接对：** 源码路由确为statsmodels，而不是默默退到NumPy；对应Model.forecast遇不同history会再次fit。完成正式接入还需明确结果安全格式与读取器、无重拟合restore，以及授权/拟合次数审计。只打印Provider.describe不证明后端安装可用。

**运行入口：** 本节没有承诺完整Case运行命令；前两节的Serializer显式拒绝Statsmodels模型。新增正式Artifact/恢复规则前，不要直接切backend后沿用该Serializer。当前可运行替代是明确限制为q=Q=0的NumPy路线，而不是相同数学模型。

### 变体：只更改请求声明，不伪装已拟合

**目的/改在哪里：** 上述工厂将order改为(2,0,1)会请求AR2/MA1；必须保留backend="statsmodels"。**行为变化：** 增加了声明阶数，没有拟合/优化器或Artifact结果。**限制：** 这是迁移前的配置检查，不能替代正式模型交付。

来源：mlblack `presets/time_series.py`、`models/time_series.py`、`representations/time_series.py`、`pipeline/time_series.py`、`problems/time_series.py`、`core/artifact_provider.py`。
