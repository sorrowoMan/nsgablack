# 时序验证与概率输出：在正式 ML Case 中保留评估含义

每章使用 mlblack 现有 `examples/cases/catalog_codec_demo/` 的独立副本，不叠加两章文件。保留 Project 的 L0、默认 linear 阶段、linear_point Case 包与 run_solver/run_trainer 薄入口；目录名不等于新的模型类型。只替换正文列出的语义工厂和唯一 builder。源码已静态核对；本书未执行算法、模型或命令，不提供拟合效果、运行成功或恢复兼容性承诺。

## mlblack.problem.time_series_forecasting · 有序尾段验证与滚动起点

**什么时候用：** 对同一条有序单变量序列比较末值、移动平均、季节朴素预测。主例以最后 12 点作为一次连续验证，变体改成多个历史起点的三步预测；不要把逐行随机切分当作时间验证。

**先准备什么：** 当前三仓与 NumPy。从 mlblack 的 catalog_codec_demo 复制完整 Project，默认组仍调用 `cases/linear_point/`，授权来自原 Project。以下是公开合成序列：48 个按日序排列的观测；time_index 只作时间标签，调用方负责顺序。普通构造不排序；本例显式 from_values(sort_by_time=True)，同时排序 y。没有外生变量，也不暗示预测时可读取未来目标。

**放在哪：** 全部路径相对该 Project 副本。替换 `pipeline/main.py`、`problem/__init__.py`、`adapter/__init__.py`、`build_solver.py`，新增 `plugins/material_report.py`；保留原 pipeline 包导出的 build_pipeline。旧 config.py 的线性回归 DEFAULTS 不再被本 builder 消费。

**接入步骤：** 候选的三个参数是策略编号、窗口、季节长度。BaselineForecastRepresentation 拥有这份布局及整数修复，不是把时序数据变成 Adapter Unit。Gaussian 搜索只变化候选参数；LearningSolver 通过共享优化控制面初始化、修复、解码并送评。Problem 调用模型的 forecast(history, horizon)，基线只使用收到的历史。

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import TimeSeriesDataView
from mlblack.representations import BaselineForecastRepresentation, BaselineForecastSearchConfig

def build_pipeline():
    t = np.arange(48, dtype=float)
    y = 20. + .15*t + 3.*np.sin(2.*np.pi*t/7.)
    if not np.all(np.isfinite(y)):
        raise ValueError("finite observations required")
    return TimeSeriesDataView.from_values(y, time_index=tuple(range(48)),
        target_name="demand", frequency="D", sort_by_time=True)

def build_representation(seed):
    return BaselineForecastRepresentation(BaselineForecastSearchConfig(
        strategies=("naive", "moving_average", "seasonal_naive"),
        window_bounds=(2, 8), seasonal_period_bounds=(5, 9), random_seed=seed))
```

```python
# cases/linear_point/problem/__init__.py
from mlblack.models.time_series import NaiveForecastModel
from mlblack.problems import TimeSeriesForecastingProblem

class CaseForecastProblem(TimeSeriesForecastingProblem):
    def restore_model_for_evaluation(self, model, state, feedback, context):
        if not isinstance(model, NaiveForecastModel):
            raise TypeError("this Case restores executable baseline models only")
        return model

    def build_model_artifact(self, model, context):
        return {"schema": "case.naive_forecast/v1", **model.describe()}

def build_problem(data):
    return CaseForecastProblem(data, validation_size=12,
        objective_metrics=("valid.rmse", "valid.mae"), seasonal_period=7)
```

该子类不重写评估；原 Problem 取前 36 点为 history、后 12 点为 target，递归预测 12 步，期间不灌入验证真值。两个原始目标分别是 valid.rmse、valid.mae，空约束、无梯度。此尾段用于策略选择，不能再冒称独立最终测试集。restore 只返回已解码基线，不重跑准备；Artifact hook 交付可传输参数蓝图，避免把无 as_dict 的活模型交给默认 unsafe pickle。它不是所有拟合模型的通用恢复规则。

```python
# cases/linear_point/adapter/__init__.py
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter

def build_adapter():
    return build_optimization_adapter("search.random_gaussian",
        population_size=6, mutation_scale=.3, random_seed=17)
```

```python
# cases/linear_point/plugins/material_report.py
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class MaterialReport(Plugin):
    def __init__(self, output):
        super().__init__(name="forecast_material_report")
        self.output = Path(output)

    def on_solver_finalized(self, raw_result):
        result = self.solver.export_case_result(raw_result)
        feedback = result.best_feedback
        if feedback is None:
            raise RuntimeError("no evaluated result to report")
        payload = {"run_id": self.solver.run_session.run_id,
            "state": result.best_state.as_array().tolist(),
            "objectives": feedback.objectives.tolist(), "metrics": dict(feedback.metrics),
            "residuals": feedback.residuals.tolist(),
            "model_ref": None if result.best_model_ref is None else result.best_model_ref.as_dict()}
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

```python
# cases/linear_point/build_solver.py
from pathlib import Path
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides
from .pipeline.main import build_pipeline, build_representation
from .problem import build_problem
from .adapter import build_adapter
from .plugins.material_report import MaterialReport

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {"seed": 17, "max_steps": 6, **dict(config or {})}
    solver = build_learning_solver(problem=build_problem(build_pipeline()),
        representation=build_representation(settings["seed"]), adapter=build_adapter(),
        resource_context=resource_context, run_name="catalog_forecast")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(settings["seed"])
    solver.set_max_steps(settings["max_steps"])
    solver.add_plugin(MaterialReport(Path(__file__).resolve().parents[2]
        / "results" / "forecast.json"))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

**怎样判断接对：** 看副本 `results/forecast.json`，先核对本轮 run_id。主例 metrics 中 validation_size=12、history_size=36 的完整键是 time_series.validation_size/history_size；residuals 应有 12 项，顺序与最后 12 个观测一致。objectives 两项应对应 valid.rmse/valid.mae；state 三项按管线列出的策略顺序解释。这里没有 Bias，保留原始误差，不用选择投影冒充预测精度。model_ref 指向正式发布的基线蓝图；本地 JSON 是观察副本，不替代 Artifact 收据，也不代表 Pareto 全集或完整搜索轨迹。

**运行入口：** 在 Project 副本根目录执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。默认组仍运行 linear_point，新的 run_name 不会偷偷注册另一个 Case。覆盖 Problem/表示时须同步工厂和报告，旧文件不能证明新配置成功。上面的入口留给用户执行，本轮没有运行。

### 变体一：改成多个起点的三步预测，不复用一次尾段的指标名

只完整替换 `cases/linear_point/problem/__init__.py`；其余文件、时间顺序和 Adapter 保持本节版本。

```python
from mlblack.models.time_series import NaiveForecastModel
from mlblack.problems import RollingOriginForecastingProblem

class CaseRollingProblem(RollingOriginForecastingProblem):
    def restore_model_for_evaluation(self, model, state, feedback, context):
        if not isinstance(model, NaiveForecastModel):
            raise TypeError("this Case restores executable baseline models only")
        return model

    def build_model_artifact(self, model, context):
        return {"schema": "case.naive_forecast/v1", **model.describe()}

def build_problem(data):
    return CaseRollingProblem(data, min_train_size=24, horizon=3, max_origins=6,
        objective_metrics=("rolling.rmse", "rolling.mae"), seasonal_period=7)
```

此时前缀至少 24 点，最多选 6 个起点；每个起点只交付其当时历史，预测三步，但评估只取第三步与 origin+3 处真值比较，不是把每条三步轨迹都平铺计分。报告 residuals 改为 6 项，rolling.origins=6、rolling.horizon=3、rolling.min_train_size=24，目标键改为 rolling.rmse/mae。后一个起点可使用届时已经观测的真值，这与主例一次递归预测 12 步不同。有限次搜索与六个起点不证明未来泛化。这里只使用不需拟合的基线；更换为 ARIMA/神经网络后不能照搬其拟合、恢复和发布规则。

来源：[时序数据视图](../../../mlblack/pipeline/data_views/time_series.py)、[两种评估](../../../mlblack/problems/time_series.py)、[基线表示](../../../mlblack/representations/time_series.py)、[正式宿主](../../../mlblack/examples/cases/catalog_codec_demo/project_config.py)。

## mlblack.head.normal · 连续分布与两个计数输出变体

**什么时候用：** 需要分布参数和 NLL，而非只比较均值 MSE。主例用 NormalHead，Poisson/NB 分别见变体一/二；三者不叠加，也没有 forecast 接口。

**先准备什么：** 独立复制 mlblack 的 catalog_codec_demo，保留 Project L0、默认 linear_point Case 与运行入口。40 行按已知时间坐标排序，前 28 行训练、后 12 行验证，不随机打散。搜索目标是训练 NLL，验证只报告；这是顺序留出分布回归，不是多步预测。

**放在哪：** 按下列路径替换五个工厂/入口文件并新增 report，保留 pipeline 包导出。原 SGD 也要替换，这些模型没有所需解析梯度。

**接入步骤：** LinearPointCodec 每基础块是截距加一个权重。Normal 分配 mu/log_sigma 两块（4 参数），Poisson 一块（2 参数），NB 两块（4 参数）。FAMILY 同时交给数据、Head 和 NLL 消费者；变体只改这一选择，不遗漏配套约束。

```python
# cases/linear_point/config.py
FAMILY = "normal"
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import NumericDataView
from mlblack.representations import LinearPointConfig, LinearPointRepresentation
from mlblack.representations.heads import NormalHead, PoissonHead, NegativeBinomialHead

def build_pipeline(family):
    t = np.arange(40)
    x = t.astype(float) / 39.
    y = 1. + 2.*x + .1*np.cos(8.*x) if family == "normal" else (2+t//8+t%3).astype(float)
    return NumericDataView(X_train=x[:28, None], y_train=y[:28],
        X_valid=x[28:, None], y_valid=y[28:], feature_names=("time",))

def build_representation(data, family):
    if family == "normal":
        head = NormalHead(sigma_transform="softplus")
    elif family == "poisson":
        head = PoissonHead(rate_transform="softplus")
    elif family == "negative_binomial":
        head = NegativeBinomialHead(alpha_transform="softplus")
    else:
        raise ValueError("unknown family")
    return LinearPointRepresentation(LinearPointConfig(n_features=1,
        feature_names=data.effective_feature_names, random_seed=17),
        head=head)
```

```python
# cases/linear_point/problem/__init__.py
import numpy as np
from mlblack.core.problem import LearningProblem
from mlblack.core.types import Feedback

class DistributionNLLProblem(LearningProblem):
    name = "case_distribution_nll"

    def __init__(self, data, family):
        self.data, self.family = data, family
        if family not in ("normal", "poisson", "negative_binomial"):
            raise ValueError("unknown distribution family")
        for x, y in ((data.X_train, data.y_train), (data.X_valid, data.y_valid)):
            if x is None or y is None or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
                raise ValueError("finite train and validation pairs required")
            if family != "normal" and (np.any(y < 0) or np.any(y != np.floor(y))):
                raise ValueError("count heads require nonnegative integer targets")

    def evaluate(self, model, state, context):
        train = -np.asarray(model.log_prob(self.data.X_train, self.data.y_train))
        valid = -np.asarray(model.log_prob(self.data.X_valid, self.data.y_valid))
        if not np.all(np.isfinite(train)) or not np.all(np.isfinite(valid)):
            raise ValueError("nonfinite implemented NLL")
        train_nll, valid_nll = float(np.mean(train)), float(np.mean(valid))
        return Feedback(objectives=[train_nll], loss=train_nll,
            constraints=[], gradients=None, residuals=valid,
            metrics={"train.nll": train_nll, "valid.nll": valid_nll},
            signals={"primary_objective": "train.nll", "has_gradient": False})

    def build_model_artifact(self, model, context):
        slots = {"normal": ("mu_model", "sigma_model"), "poisson": ("rate_model",),
                 "negative_binomial": ("mu_model", "alpha_model")}[self.family]
        return {"schema": "case.linear_distribution/v1", "family": self.family,
                "positive_transform": "softplus",
                "blocks": {slot: getattr(model, slot).as_dict() for slot in slots}}

def build_problem(data, family):
    return DistributionNLLProblem(data, family)
```

此 ML Case 的 residuals 明确存验证 NLL。计数类型由工厂校验，Feedback 约束为空。Artifact hook 发布参数蓝图，避免 unsafe pickle，不提供通用加载器。

```python
# cases/linear_point/adapter/__init__.py
from mlblack.integrations.nsgablack_optimization import build_optimization_adapter

def build_adapter():
    return build_optimization_adapter("search.random_gaussian",
        population_size=6, mutation_scale=.2, random_seed=17)
```

```python
# cases/linear_point/plugins/material_report.py
import json
from pathlib import Path
from nsgablack.plugins.base import Plugin

class MaterialReport(Plugin):
    def __init__(self, output):
        super().__init__(name="distribution_material_report")
        self.output = Path(output)

    def on_solver_finalized(self, raw_result):
        result = self.solver.export_case_result(raw_result)
        feedback = result.best_feedback
        if feedback is None:
            raise RuntimeError("no evaluated result to report")
        payload = {"run_id": self.solver.run_session.run_id,
            "state": result.best_state.as_array().tolist(),
            "objectives": feedback.objectives.tolist(), "metrics": dict(feedback.metrics),
            "validation_nll_rows": feedback.residuals.tolist(),
            "model_ref": None if result.best_model_ref is None else result.best_model_ref.as_dict()}
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(payload, ensure_ascii=False,
            allow_nan=False, indent=2), encoding="utf-8")
```

```python
# cases/linear_point/build_solver.py
from pathlib import Path
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.project import apply_solver_component_overrides
from .pipeline.main import build_pipeline, build_representation
from .problem import build_problem
from .adapter import build_adapter
from .plugins.material_report import MaterialReport
from .config import FAMILY

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    settings = {"seed": 17, "max_steps": 6, **dict(config or {})}
    data = build_pipeline(FAMILY)
    solver = build_learning_solver(problem=build_problem(data, FAMILY),
        representation=build_representation(data, FAMILY), adapter=build_adapter(),
        resource_context=resource_context, run_name="catalog_distribution")
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(settings["seed"])
    solver.set_max_steps(settings["max_steps"])
    solver.add_plugin(MaterialReport(Path(__file__).resolve().parents[2]
        / "results" / "distribution.json"))
    apply_solver_component_overrides(solver, dict(component_overrides or {}))
    return solver
```

**怎样判断接对：** 看 results/distribution.json 的新 run_id。单目标等于 train.nll；12 项 validation_nll_rows 的均值对应 valid.nll。没有 Bias，不混软分数。Normal state 为 4 参数，predict_params 返回 mu/sigma；sigma 是正尺度，不是第二目标。predict 不是概率向量，NB 只有 predict_params 会将 mu/alpha 截正，不能承诺其 predict 非负。Poisson 阶乘项、NB Gamma 项使用近似，因此这里是实现给出的 NLL，不宣称精确似然或校准正确。非有限值明确报错。

**运行入口：** 在副本根执行 `python run_project.py --check --build-check`，再执行 `python run_project.py`。Project 授权，共享控制面驱动，finalized 后写报告，model_ref 引用正式蓝图。旧文件和构造检查不证明训练成功；本轮未执行。

### 变体一：Poisson 计数；同时改数据、Head 和消费者族

完整替换本节 config.py，其余文件不变。builder 同时切换计数数据、PoissonHead 与计数 NLL；不是只改 import。

```python
# cases/linear_point/config.py
FAMILY = "poisson"
```

state 改为 2 参数，模型输出正 rate；标签必须非负整数，不能随意 round 连续观测。Poisson 的均值/方差关系是模型假设，这份合成数据不证明它成立。目标仍是训练实现 NLL，验证只观察。

### 变体二：Negative Binomial 分散参数；保留同一计数数据

以本节完整主例为基础替换 config.py，无需先做变体一；三个工厂同时选择计数数据、NB Head 和对应消费者。

```python
# cases/linear_point/config.py
FAMILY = "negative_binomial"
```

state 为 4 参数，mu/alpha 分块，预测参数由模型截正。分散形式不同不保证更好；近似 NLL 未经本轮精度验收。这三个模型没有 forecast 接口，不能直接塞进上一章时序 Problem。

来源：[Head](../../../mlblack/representations/heads/distribution.py)、[分布公式](../../../mlblack/models/distributions.py)、[Artifact hook](../../../mlblack/core/artifact_provider.py)。
