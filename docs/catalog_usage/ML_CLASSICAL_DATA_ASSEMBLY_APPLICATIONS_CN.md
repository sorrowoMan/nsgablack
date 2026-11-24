# 数据诊断与装配入口：只做各自负责的事情

本书未执行数据计算、拟合、Project、数据库或网络。各主例独立复制完整 `mlblack/examples/cases/catalog_codec_demo/`，保留原 Project/default 的 linear_point Case、L0、包和别名；结果读取共用 `ML_CLASSICAL_ESTIMATOR_APPLICATIONS_CN.md` 的 `classical.estimator.run` 完整入口。

## classical.assembly.trainer

**什么时候用：** 已经选定受支持 preset，想用结构化配置集中记录模型装配，而不自己重写 build_learning_solver 的接线。本例实际调用 `mlblack.assembly.build_trainer`；它不是通用编排器，不处理多Case/租约/执行顺序。

**先准备什么：** 完整Project副本、三仓、NumPy。只用合成两特征32训练/12验证；配置中的 `preset="linear_point"` 在**此装配入口**当前映射到 orthogonal_linear_point，并不等同直接调用 build_linear_point_trainer。区别必须认识，不能根据同名推断模型布局。

**放在哪：** 替换 Case config.py、pipeline/main.py、build_solver.py。原 problem/adapter 工厂不被本入口调用；保存共用正式结果入口。

**接入步骤：** 完整文件如下。resource_context 是已有 Project grant，不是资源申请；从 ResourceContext 显式 as_dict 后传到 TrainerAssemblySpec。

```python
# cases/linear_point/config.py
LEARNING_RATE = .03
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import NumericDataView

def build_pipeline():
    rng = np.random.default_rng(17)
    X, V = rng.uniform(-1., 1., (32, 2)), rng.uniform(-1., 1., (12, 2))
    def target(a):
        return 1.+2.*a[:, 0]-.5*a[:, 1]
    return NumericDataView(X_train=X, y_train=target(X), X_valid=V, y_valid=target(V),
                           feature_names=("a", "b"))
```

```python
# cases/linear_point/build_solver.py
from blackbase.resources import coerce_resource_context
from mlblack.assembly import TrainerAssemblySpec, build_trainer
from .config import LEARNING_RATE
from .pipeline.main import build_pipeline

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit assembly specifications")
    grant = {} if resource_context is None else coerce_resource_context(resource_context).as_dict()
    spec = TrainerAssemblySpec(preset="linear_point",
        params={"learning_rate": LEARNING_RATE, "l2": 0., "complexity_weight": 0.,
                "max_components": 3, "energy_threshold": .999},
        run_name="catalog_assembly", resource_context=grant)
    solver = build_trainer(spec, build_pipeline())
    solver.set_bias_module(None, enable=False)
    solver.set_random_seed(17)
    solver.set_max_steps(6)
    return solver
```

该preset在训练X上拟合正交特征基，再用梯度SGD改变线性坐标。原生 OrthogonalLinearPointModel.as_dict 含特征映射/均值/基/系数，默认Artifact可安全保存；不是活 sklearn 模型或裸Torch Module。目标默认使用valid.mse，loss为train MSE，数据准备SVD不是Adapter Unit。

build_trainer先按preset构造，然后set_resource_context，最后依次add_bias/add_plugin；它不接受runtime/workflow/resource_request/orchestration作为调度配置。spec.compute_backend会被放进preset参数，并非每个preset都接受：本例不传该字段，运行后端仍由原preset/授权决定。component_overrides的preset_params/trainer是参数覆盖，不能据名字假定替换任意内部对象。

**怎样判断接对：** classical.json原始目标 `[valid.mse,0]`、训练loss、train/valid指标和model_ref；Artifact中的实际基秩决定候选维度，不能写死为3。正式Case输出中Adapter为梯度路线；成功构造spec不等于跑过六步。

**运行入口：** 副本根 `python run_project.py --check --build-check`，再 `python run_classical_and_report.py`；第二条只运行一次正式Project。检查本次run_id/Case终态与正式模型引用，不自行 fit 两次。

### 变体：更换步长，不改装配路径

**目的：** 比较相同数据/正交基下的SGD步长。**改在哪里：** config.py完整替换如下。

```python
LEARNING_RATE = .01
```

**行为变化：** 每次权重更新幅度改变，数据与基构造不变。**限制：** 更小步长不保证小预算内更好；不能把训练步骤数与数据fit次数混为一谈，也不能跨不同基加载旧checkpoint。

## classical.seasonal.diagnostic

**什么时候用：** 看一条已经观测完整的序列是否有趋势/周期，保存 original=trend+seasonal+resid 的事后分解。这里实际使用 seasonal_decompose、SeasonalDecompositionResult 和 STLSeasonalDecompositionComponent；它们是数据分析能力，不是预测器。

**先准备什么：** 另一份完整Project副本、三仓和NumPy。42条日序列、period7，至少满足两完整周期。当前实现为居中移动平均+各周期相位均值的加性分解，model="stl"也只是别名，并非statsmodels稳健STL/LOESS。

**放在哪：** 替换 Case config.py、pipeline/main.py、problem/__init__.py、build_solver.py；保存共用正式结果入口。大数组仅存在本次Problem对象和Artifact蓝图，不写共享context。

**接入步骤：** 完整文件如下。一个固定哨兵候选触发一次诊断；原DiagnosticProblem保留结果、返回紧凑反馈，子类补齐明确的原生字典Artifact。

```python
# cases/linear_point/config.py
TREND_WINDOW = 7
```

```python
# cases/linear_point/pipeline/main.py
import numpy as np
from mlblack.pipeline.data_views import TimeSeriesDataView

def build_pipeline():
    t = np.arange(42, dtype=float)
    return TimeSeriesDataView(y=10.+.2*t+2.*np.sin(2.*np.pi*t/7.),
        time_index=tuple(range(42)), target_name="observed", frequency="D")
```

```python
# cases/linear_point/problem/__init__.py
import numpy as np
from mlblack.core.diagnostic import DiagnosticProblem
from mlblack.pipeline.time_series import (SeasonalDecompositionConfig,
    STLSeasonalDecompositionComponent, seasonal_decompose)
from ..config import TREND_WINDOW

def diagnostic_runner(data):
    def run(context):
        config = SeasonalDecompositionConfig(period=7, trend_window=TREND_WINDOW,
                                              residual_target=False)
        component = STLSeasonalDecompositionComponent(config)
        state = component.fit(data, context)
        result = component.transform(data, state, context)
        direct = seasonal_decompose(data, config)
        if not np.allclose(result.resid, direct.resid):
            raise ValueError("component and direct operation disagree")
        error = float(np.max(np.abs(result.original-result.trend-result.seasonal-result.resid)))
        if error > 1e-10:
            raise ValueError("decomposition identity violated")
        residual_view = result.to_data_view(component="resid")
        return {"schema": "case.seasonal_diagnostic/v1", "status": "ok", "objective": 0.,
            "metrics": {"reconstruction_error": error, "resid_std": float(np.std(result.resid)),
                        "n_obs": residual_view.n_obs},
            "description": result.describe(), "fit_summary": dict(state),
            "time_index": list(result.time_index), "original": result.original.tolist(),
            "trend": result.trend.tolist(), "seasonal": result.seasonal.tolist(),
            "resid": result.resid.tolist()}
    return run

class SeasonalDiagnosticProblem(DiagnosticProblem):
    def build_model_artifact(self, model, context):
        if not isinstance(self.last_result, dict):
            raise RuntimeError("no diagnostic result available")
        return dict(self.last_result)

def build_problem(data):
    return SeasonalDiagnosticProblem(diagnostic_runner(data), name="case_seasonal_diagnostic")
```

```python
# cases/linear_point/build_solver.py
from mlblack.core.diagnostic import DiagnosticRepresentation
from mlblack.integrations.nsgablack_control import build_learning_solver
from nsgablack.adapters import FixedCandidateAdapter
from .pipeline.main import build_pipeline
from .problem import build_problem

class ReportRepresentation(DiagnosticRepresentation):
    def decode(self, state, context=None):
        return {"kind": "seasonal_diagnostic_report"}

def build_solver(config=None, *, resource_context=None, component_overrides=None):
    if config or component_overrides:
        raise ValueError("this recipe uses explicit components")
    solver = build_learning_solver(problem=build_problem(build_pipeline()),
        representation=ReportRepresentation(), adapter=FixedCandidateAdapter(),
        compute_backend="numpy", resource_context=resource_context,
        run_name="catalog_seasonal_diagnostic")
    solver.set_bias_module(None, enable=False)
    solver.set_max_steps(1)
    return solver
```

ReportRepresentation保留原诊断初始化，但decode返回非None的报告描述；默认DiagnosticRepresentation.decode返回None，会使正式ArtifactProvider跳过模型发布，不能只增加Problem hook便声称有model_ref。注意fit返回的是统计摘要，transform忽略该state并在传入数据上重新分解。本诊断为了核对两个公开入口，实际分解三次（fit、transform、direct），不是只付一次计算成本。居中趋势用两侧数据、周期均值用整段数据；不能先分解全序列再随机拆分，或用未来验证目标去构造训练残差并称无泄漏。也不能把fit(train)的摘要传给transform(valid)当作冻结预处理。

**怎样判断接对：** classical.json只有占位目标[0]，它不衡量预测效果；metrics有reconstruction_error/resid_std/n_obs与diagnostic.status。正式model_ref指向诊断JSON，含42条对齐数组与时间标签；这是报告Artifact，不是可对新输入forecast的模型。恒等式成立不说明周期选择正确、可因果预测或残差独立。

**运行入口：** 同一正式Project检查与run_classical_and_report.py；L0来自原Project，运行仅一个诊断Case。当前Problem的last_result是运行内结果，本例未提供checkpoint后恢复完整诊断蓝图的规则；需要恢复时必须显式持久值，禁止在恢复中再次运行诊断冒充原结果。

### 变体：放宽趋势平滑窗口

**目的：** 对比同一period下的趋势平滑。**改在哪里：** config.py完整替换：

```python
TREND_WINDOW = 15
```

**行为变化：** 居中移动平均更宽，trend/seasonal/resid都可能改变；数组数与重构恒等式保持。**限制：** 不改变周期、不变成在线或因果滤波器；边界使用edge padding，不能当真实未来值。

来源：mlblack `assembly/builders.py`、`assembly/spec.py`、`presets/linear.py`、`pipeline/time_series.py`、`core/diagnostic.py` 与正式 ArtifactProvider。
